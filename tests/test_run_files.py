import json
import tempfile
import unittest
from pathlib import Path
import sys
import subprocess,time,signal
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import native_service as service
from mesh_io import read_gmsh

FIXTURE='''$MeshFormat
2.2 0 8
$EndMeshFormat
$PhysicalNames
1
2 7 "Wing rib"
$EndPhysicalNames
$Nodes
6
10 0 0 0
20 1 0 0
30 0 1 0
40 0.5 0 0
50 0.5 0.5 0
60 0 0.5 0
$EndNodes
$Elements
2
100 9 2 7 0 10 20 30 40 50 60
200 1 1 7 10 20
$EndElements
'''

class RunFiles(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=service.WORK,service.JOBS
        service.WORK=Path(self.temp.name);service.JOBS={};self.jid='a'*32
        self.folder=service.WORK/'jobs'/self.jid;self.folder.mkdir(parents=True)
        (self.folder/'request.json').write_text(json.dumps({'name':'CompGeom','revision':'model1'}))
        (self.folder/'engine.log').write_text('Native log')
        (self.folder/'response.json').write_text(json.dumps({'results':[{'name':'Geometry','index':0,'entries':[{'name':'Area','index':0,'values':[2.5,3.5]}]}]}))
    def tearDown(self):
        service.WORK,service.JOBS=self.old;self.temp.cleanup()
    def test_completed_history_and_csv_survive_memory_reset(self):
        jobs=service.list_jobs();self.assertEqual(jobs[0]['status'],'complete')
        service.save_job(service.JOBS[self.jid]);service.JOBS={}
        job=service.job_state(self.jid);self.assertEqual(job['revision'],'model1')
        self.assertIn('Geometry,0,Area,0,1,3.5',service.result_csv(self.jid).decode())
        self.assertIn('engine.log',[f['name'] for f in job['artifacts']])
    def test_interrupted_run_not_reported_as_running_after_restart(self):
        (self.folder/'response.json').unlink()
        (self.folder/'job.json').write_text(json.dumps({'id':self.jid,'name':'CompGeom','started':1,'revision':'x','status':'running'}))
        self.assertEqual(service.job_state(self.jid)['status'],'interrupted')
    def test_failed_run_retains_applied_setup_and_older_requested_overrides(self):
        (self.folder/'response.json').unlink()
        inputs=[dict(name='BaseLen',index=0,type=2,values=[1.5])]
        request=dict(name='CfdMeshAnalysis',inputs=[dict(name='BaseLen',values=[1.5])])
        (self.folder/'request.json').write_text(json.dumps(request))
        (self.folder/'job.json').write_text(json.dumps(dict(id=self.jid,name='CfdMeshAnalysis',status='failed',started=1,revision='x',error='Native engine stopped')))
        before={p.name:p.read_bytes() for p in self.folder.iterdir()}
        old=service.job_state(self.jid)
        self.assertEqual(old['requestedSetup']['inputs'],request['inputs'])
        self.assertNotIn('result',old)
        setup=dict(analysis='CfdMeshAnalysis',inputs=inputs,stage='before native execution')
        (self.folder/'analysis-setup.json').write_text(json.dumps(setup))
        service.JOBS={};new=service.job_state(self.jid)
        self.assertEqual(new['analysisSetup'],setup);self.assertNotIn('requestedSetup',new)
        self.assertNotIn('result',new);self.assertEqual(new['status'],'failed')
        for name,content in before.items():self.assertEqual((self.folder/name).read_bytes(),content)
        (self.folder/'analysis-setup.json').unlink()
        request=dict(name='FeaAssemblyMesh',structure='assembly',inputs=[],formats=['GMSH'],memberInputs=[dict(id='member',inputs=inputs)])
        (self.folder/'request.json').write_text(json.dumps(request))
        service.JOBS={};member_state=service.job_state(self.jid)
        self.assertEqual(member_state['requestedSetup']['memberInputs'],request['memberInputs'])
        self.assertEqual(member_state['requestedSetup']['inputs'],[])
        self.assertNotIn('result',member_state)
    def test_actual_child_signal_is_preserved_in_failed_saved_run_after_reload(self):
        source=service.WORK/'source.vsp3';source.write_text('retained source')
        def launch(request,model,folder,**kwargs):
            (folder/'request.json').write_text(json.dumps(request))
            child=subprocess.Popen([sys.executable,'-c','import os,signal;os.kill(os.getpid(),signal.SIGTERM)'],stdout=kwargs['log'],stderr=kwargs['log'])
            return child,folder/'response.json'
        with patch.object(service,'invoke',side_effect=launch):
            job=service.start_job(dict(name='CompGeom'),model_source=source,source_revision='signal-test')
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                meta=json.loads((service.job_folder(job['id'])/'job.json').read_text())
                if 'finished' in meta:break
                time.sleep(.01)
            self.assertEqual(meta['status'],'failed');self.assertEqual(meta['exitCode'],-signal.SIGTERM);self.assertEqual(meta['terminationSignal'],'SIGTERM')
            self.assertIn('SIGTERM',meta['error']);service.JOBS={}
            reloaded=service.job_state(job['id']);self.assertEqual(reloaded['exitCode'],-signal.SIGTERM);self.assertEqual(reloaded['terminationSignal'],'SIGTERM');self.assertEqual(reloaded['status'],'failed')
            self.assertEqual((service.job_folder(job['id'])/'aircraft.vsp3').read_bytes(),source.read_bytes())
    def test_artifact_access_rejects_traversal_and_symlinks(self):
        outside=service.WORK/'private.txt';outside.write_text('private')
        (self.folder/'link.txt').symlink_to(outside)
        for file in ['../private.txt','link.txt','/etc/passwd','job.json']:
            with self.assertRaises(ValueError):service.artifact_file(self.jid,file)
        with self.assertRaises(ValueError):service.artifact_file('../','engine.log')
    def test_mesh_preserves_ids_coordinates_regions_and_element_types(self):
        path=self.folder/'native.msh';path.write_text(FIXTURE)
        mesh=read_gmsh(path)
        self.assertEqual(mesh['nodeIDs'],[10,20,30,40,50,60]);self.assertEqual(mesh['nodes'][4],[.5,.5,0])
        self.assertEqual(mesh['elements'][0]['nodes'],[0,1,2]);self.assertEqual(mesh['elements'][0]['id'],100)
        self.assertTrue(mesh['higherOrder']);self.assertEqual(mesh['groups'][0]['name'],'Wing rib')
        self.assertEqual(mesh['elements'][1]['kind'],'line')
    def test_invalid_connectivity_and_nonfinite_nodes_rejected(self):
        path=self.folder/'invalid.msh'
        for text in [FIXTURE.replace('40 50 60','40 50 99'),FIXTURE.replace('10 0 0 0','10 nan 0 0')]:
            path.write_text(text)
            with self.assertRaises(ValueError):read_gmsh(path)

if __name__=='__main__':unittest.main()
