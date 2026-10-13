"""All structural exports come from one original native mesh generation."""
import sys,unittest,json,time,os,signal,tempfile
from pathlib import Path
import test_native,test_structural_regions
import native_mesh,native_preview
from mesh_io import read_gmsh
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class NativeMeshExports(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    fixture=test_structural_regions.StructuralRegions.fixture

    def test_actual_native_termination_retains_structural_setup_after_reload(self):
        import native_service as service
        self.fixture();before=self.model.read_bytes();previous=service.WORK,service.JOBS
        process=None
        try:
            with tempfile.TemporaryDirectory() as work:
                service.WORK=Path(work);service.JOBS={}
                values={'BaseLen':.01,'MinLen':.002,'MaxGap':.001,'NCircSeg':24.5,'GrowthRatio':1.4,'RigorLimit':1,'HalfMeshFlag':0}
                job=service.start_job(dict(name='FeaMeshAnalysis',structure=self.sid,formats=['CALCULIX','NASTRAN','MASS'],inputs=[dict(name=n,values=[x]) for n,x in values.items()]),model_source=self.model,source_revision='structural-setup-recovery')
                process=service.JOBS[job['id']]['_process'];folder=service.job_folder(job['id'])
                deadline=time.monotonic()+20
                while not (folder/'analysis-setup.json').exists() and process.poll() is None and time.monotonic()<deadline:time.sleep(.01)
                self.assertTrue((folder/'analysis-setup.json').exists())
                setup=json.loads((folder/'analysis-setup.json').read_text())
                self.assertEqual(setup['structure'],self.sid)
                self.assertEqual({e['name']:e['values'][0] for e in setup['inputs']},values)
                self.assertEqual(set(setup['formats']),{'GMSH','CALCULIX','NASTRAN','MASS'})
                self.assertIsNone(process.poll(),'Native worker must still be live for termination test')
                os.killpg(process.pid,signal.SIGTERM)
                deadline=time.monotonic()+10
                while time.monotonic()<deadline:
                    state=service.job_state(job['id'])
                    if state.get('finished'):break
                    time.sleep(.01)
                self.assertEqual(state['status'],'failed');self.assertEqual(state['terminationSignal'],'SIGTERM')
                service.JOBS={};reloaded=service.job_state(job['id'])
                self.assertEqual(reloaded['analysisSetup'],setup);self.assertNotIn('result',reloaded)
                self.assertEqual((folder/'aircraft.vsp3').read_bytes(),before)
        finally:
            if process and process.poll() is None:
                os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=10)
            service.WORK,service.JOBS=previous
        self.assertEqual(self.model.read_bytes(),before)

    def test_guided_sizing_uses_original_parameter_limits_and_native_types(self):
        self.fixture();v=self.v;spec=native_mesh.fea_schema(v,self.sid)
        self.assertEqual(set(e['name'] for e in spec['inputs']),set(native_mesh.FEA_INPUTS))
        self.assertEqual(set(n for s in spec['guide']['sections'] for n in s['inputs']),set(native_mesh.FEA_INPUTS))
        for e in spec['inputs']:
            p=e['nativeParameter']
            self.assertIn(p,v.FindContainerParmIDs(self.sid))
            self.assertEqual((v.GetParmName(p),v.GetParmGroupName(p)),native_mesh.FEA_PARAMETERS[e['name']])
            self.assertEqual((e['min'],e['max']),(v.GetParmLowerLimit(p),v.GetParmUpperLimit(p)))
            self.assertEqual(e['values'],[v.GetFeaMeshVal(self.gid,v.GetFeaStructIndex(self.sid),getattr(v,native_mesh.FEA_INPUTS[e['name']]))])
        circle=next(e for e in spec['inputs'] if e['name']=='NCircSeg')
        self.assertEqual(circle['type'],v.DOUBLE_DATA)
        for n in ['HalfMeshFlag','RigorLimit']:
            e=next(e for e in spec['inputs'] if e['name']==n)
            self.assertEqual([c['value'] for c in e['choices']],[0,1])

    def test_invalid_sizing_is_rejected_without_partial_native_changes(self):
        self.fixture();v=self.v;sid,gid,index=native_mesh.structure(v,self.sid)
        before={p:v.GetParmVal(p) for p in v.FindContainerParmIDs(sid)}
        for n,x in [('GrowthRatio',.5),('GrowthRatio',11.),('BaseLen',1e-10),('NCircSeg',0.),('HalfMeshFlag',.5),('RigorLimit',2.)]:
            with self.subTest(name=n,value=x),self.assertRaises(ValueError):
                native_mesh.sizing(v,gid,index,[dict(name='MaxGap',values=[.02]),dict(name=n,values=[x])])
            self.assertEqual({p:v.GetParmVal(p) for p in before},before)
        for entries in [[dict(name='MinLen',values=[2.])],[dict(name='MaxGap',values=[.02]),dict(name='MaxGap',values=[.03])],[dict(name='MaxGap',index=1,values=[.02])]]:
            with self.assertRaises(ValueError):native_mesh.sizing(v,gid,index,entries)
            self.assertEqual({p:v.GetParmVal(p) for p in before},before)

    def test_guided_sizing_applies_original_continuous_target_and_flags_exactly(self):
        self.fixture();v=self.v;sid,gid,index=native_mesh.structure(v,self.sid)
        values={'BaseLen':1.,'MinLen':.2,'MaxGap':.03,'NCircSeg':20.5,'GrowthRatio':1.5,'RigorLimit':1,'HalfMeshFlag':1}
        native_mesh.sizing(v,gid,index,[dict(name=n,values=[x]) for n,x in values.items()])
        self.assertEqual({n:v.GetFeaMeshVal(gid,index,getattr(v,enum)) for n,enum in native_mesh.FEA_INPUTS.items()},values)
        v.WriteVSPFile(str(self.model),v.SET_ALL)
        result,path=self.worker(dict(action='analysis',name='FeaMeshAnalysis',structure=sid,formats=['GMSH'],inputs=[]))
        self.assertEqual({e['name']:e['values'][0] for e in result['inputs']},values)
        setup=json.loads((path.parent/'analysis-setup.json').read_text())
        self.assertEqual(setup['inputs'],result['inputs']);self.assertEqual(setup['structure'],sid);self.assertEqual(setup['formats'],result['formats'])
        mesh=read_gmsh(path.parent/'structure.msh')
        self.assertTrue(mesh['nodes']);self.assertGreaterEqual(min(p[1] for p in mesh['nodes']),0.)

    def test_all_formats_use_one_generation_and_native_gmsh_is_not_changed_by_exports(self):
        self.fixture();v=self.v;calls=[];initial=[]
        class OriginalAPI:
            def __getattr__(self,name):return getattr(v,name)
            def ComputeFeaMesh(self,*args):
                calls.append(args);v.ComputeFeaMesh(*args);initial.append(Path('structure.msh').read_bytes())
        result=native_mesh.run_fea(OriginalAPI(),dict(structure=self.sid,formats=list(native_mesh.FEA_EXPORTS),inputs=[dict(name=n,values=[x]) for n,x in [('BaseLen',1.),('MinLen',.2),('MaxGap',.03)]]))
        self.assertEqual(len(calls),1);self.assertEqual(result['meshGenerations'],1)
        self.assertEqual(Path('structure.msh').read_bytes(),initial[0])
        for fmt,ext in native_mesh.FEA_EXPORTS.items():
            self.assertTrue(Path('structure.'+ext).stat().st_size>0,fmt)
        mesh=read_gmsh(Path('structure.msh'));native_nodes={}
        reading=False
        for line in Path('structure.inp').read_text().splitlines():
            if line.startswith('*'):reading=line.upper().startswith('*NODE');continue
            if reading and line.strip():
                fields=line.split(',');native_nodes[int(fields[0])]=list(map(float,fields[1:4]))
        self.assertEqual(len(native_nodes),len(mesh['nodes']))
        self.assertEqual(native_nodes,dict(zip(mesh['nodeIDs'],mesh['nodes'])))
        # Reexporting calls the original retained-mesh writer and leaves its
        # Gmsh coordinates/connectivity unchanged byte-for-byte.
        native_preview.export_fea_mesh(v,self.sid)
        self.assertEqual(Path('structure.msh').read_bytes(),initial[0])

    def test_worker_multi_format_run_generates_once_preserves_source_and_companions(self):
        self.fixture();before=self.model.read_bytes()
        result,path=self.worker(dict(action='analysis',name='FeaMeshAnalysis',structure=self.sid,formats=['GMSH','CALCULIX','NASTRAN','MASS'],inputs=[dict(name=n,values=[x]) for n,x in [('BaseLen',1.),('MinLen',.2),('MaxGap',.03)]]))
        self.assertEqual(result['meshGenerations'],1);self.assertEqual(path.read_bytes(),before)
        for name in ['structure.msh','structure.inp','structure.bdf','structure.dat','structure.txt']:self.assertGreater((path.parent/name).stat().st_size,0)

if __name__=='__main__':unittest.main()
