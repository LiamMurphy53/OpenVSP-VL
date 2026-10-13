"""Native study equality, frozen aircraft, interruption and artifact recovery."""
import csv
import io
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
import zipfile
import test_native
from vsp_runtime import load,interpreter,ROOT
import native_service as service
import native_studies as studies
import native_worker


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativeStudies(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    worker=test_native.NativeIntegration.worker

    def setUp(self):
        test_native.NativeIntegration.setUp(self)
        self.old=(service.WORK,service.MODEL,service.HISTORY,service.FUTURE,service.REVISION,service.JOBS,service.RUN_RESERVATION,studies.RUNNERS)
        service.WORK=self.path;service.MODEL=self.model;service.HISTORY=[];service.FUTURE=[];service.JOBS={};service.REVISION='study-native-verification';service.RUN_RESERVATION=None;studies.RUNNERS={}

    def tearDown(self):
        for context,thread in list(studies.RUNNERS.items()):
            studies.cancel(*context);thread.join(timeout=30)
            self.assertFalse(thread.is_alive(),'Study runner did not stop.')
        service.WORK,service.MODEL,service.HISTORY,service.FUTURE,service.REVISION,service.JOBS,service.RUN_RESERVATION,studies.RUNNERS=self.old
        test_native.NativeIntegration.tearDown(self)

    def save(self,axes,stages=None,**extra):
        return studies.save_study(dict(name='Native verification study',revision=service.REVISION,axes=axes,stages=stages or [dict(name='CompGeom',inputs=[])],**extra))

    def wait(self,sid,bid):
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            batch=studies.batch_state(sid,bid)
            if not batch['live']:return batch
            time.sleep(.03)
        self.fail('The verified native study did not reach a terminal state.')

    def test_native_reference_model_and_table_studies_preserve_effective_axes_and_csv(self):
        v=self.v;before=self.model.read_bytes()
        models=[v.ATMOS_TYPE_US_STANDARD_1976,v.ATMOS_TYPE_HERRINGTON_1966]
        stages=[dict(name='AtmosphereReference',inputs=[dict(name='AltitudeMeters',values=[11001.]),dict(name='TemperatureDeviationKelvin',values=[-10.])]),dict(name='DragEquationReference',inputs=[])]
        plan=self.save([dict(kind='input',stage=0,name='AtmosphereModel',values=models),dict(kind='input',stage=1,name='TableKind',values=[0,3])],stages=stages)
        batch=studies.launch(plan['id']);batch=self.wait(plan['id'],batch['id']);self.assertEqual(batch['status'],'complete');self.assertEqual(len(batch['cases']),4)
        expected=[]
        for case in batch['cases']:
            model,kind=case['values'];atmosphere=service.job_state(case['stages'][0]['job'])['result'];table=service.job_state(case['stages'][1]['job'])['result']
            point={e['name']:e['values'][0] for e in atmosphere['results'][0]['entries']};native=list(v.CalcAtmosphere(11001.,-10.,model));self.assertEqual([point[n] for n in ['Temperature_K','Pressure_kPa','PressureRatio','DensityRatio']],native);expected.append(native[1])
            self.assertEqual(table['nativeFunctions'],[['WriteBodyFFCSVFile'],['WritePartialCfMethodCSVFile']][kind==3])
        field=next(f for f in studies.result_fields(plan['id'],batch['id']) if f['field']=='Pressure_kPa')
        data=studies.comparison(plan['id'],batch['id'],field['key']);self.assertEqual([r['effective'] for r in data['rows']],[c['values'] for c in batch['cases']]);self.assertEqual([r['values'][0] for r in data['rows']],expected)
        rows=list(csv.DictReader(io.StringIO(studies.csv_comparison(plan['id'],batch['id'],field['key']).decode())));self.assertEqual([float(r['value']) for r in rows],expected)
        service.JOBS={};self.assertEqual(studies.comparison(plan['id'],batch['id'],field['key']),data)
        self.assertEqual(self.model.read_bytes(),before)

    def test_member_sizing_study_compares_actual_native_mesh_counts_and_effective_values(self):
        from test_assembly_mesh import AssemblyMesh
        from mesh_io import read_gmsh
        AssemblyMesh.fixture(self);before=self.model.read_bytes()
        stage=dict(name='FeaAssemblyMesh',structure=self.aid,inputs=[],memberInputs=[dict(id=s,inputs=[dict(name='BaseLen',values=[x]),dict(name='MinLen',values=[y])]) for s,x,y in zip(self.members,[.7,1.4],[.14,.28])])
        axes=[dict(kind='input',stage=0,member=s,name='BaseLen',values=values) for s,values in zip(self.members,[[.8,1.],[1.6,1.8]])]
        plan=self.save(axes,stages=[stage]);batch=studies.launch(plan['id']);batch=self.wait(plan['id'],batch['id'])
        self.assertEqual(batch['status'],'complete',batch)
        available=studies.result_fields(plan['id'],batch['id']);self.assertEqual({f['field'] for f in available},{'Nodes','Elements'})
        for field in available:
            data=studies.comparison(plan['id'],batch['id'],field['key'])
            self.assertEqual(len(data['rows']),4)
            for row in data['rows']:
                self.assertEqual(row['effective'],row['requested'])
                mesh=read_gmsh(service.job_folder(row['job'])/'assembly.msh')
                count=len(mesh['nodes']) if field['property']=='nodes' else mesh['totalElements']
                self.assertEqual(row['values'],[count])
                result=service.job_state(row['job'])['result']
                self.assertEqual([m['values']['MinLen'] for m in result['memberSizing']],[.14,.28])
            rows=list(csv.DictReader(io.StringIO(studies.csv_comparison(plan['id'],batch['id'],field['key']).decode())))
            self.assertEqual([int(r['value']) for r in rows],[r['values'][0] for r in data['rows']])
        self.assertEqual(self.model.read_bytes(),before)

    def test_retired_single_point_save_rejects_atomically_and_supported_retry_persists(self):
        plan=self.save([]);folder=studies.study_folder(plan['id']);definition=folder/'definition.json'
        original=definition.read_bytes();aircraft=(folder/'aircraft.vsp3').read_bytes();root=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'retired.*supported single-condition'):
            self.save([],stages=[dict(name='VSPAEROSinglePoint',inputs=[])],id=plan['id'],definitionVersion=plan['version'],baseline='saved')
        self.assertEqual(definition.read_bytes(),original);self.assertEqual((folder/'aircraft.vsp3').read_bytes(),aircraft)
        counts=[dict(name=n,index=0,values=[1]) for n in ('AlphaNpts','BetaNpts','MachNpts','ReCrefNpts')]
        corrected=self.save([],stages=[dict(name='VSPAEROSweep',inputs=counts)],id=plan['id'],definitionVersion=plan['version'],baseline='saved')
        self.assertEqual(corrected['stages'][0]['name'],'VSPAEROSweep');self.assertEqual(corrected['stages'][0]['inputs'],counts)
        actual={e['name']:e['values'] for e in corrected['stageSchemas'][0]['inputs']}
        self.assertTrue(all(actual[e['name']]==[1] for e in counts));self.assertEqual(self.model.read_bytes(),root);self.assertEqual((folder/'aircraft.vsp3').read_bytes(),aircraft)

    def test_retired_geometry_preparation_is_rejected_with_supported_recovery(self):
        baseline=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'VSPAEROComputeGeometry'):
            self.save([],stages=[dict(name='VSPAERODegenGeom',inputs=[])])
        self.assertEqual(self.model.read_bytes(),baseline)
        plan=self.save([],stages=[dict(name='VSPAEROComputeGeometry',inputs=[])])
        self.assertEqual(plan['stages'][0]['name'],'VSPAEROComputeGeometry')
        self.assertEqual(self.model.read_bytes(),baseline)

    def test_cartesian_geometry_cases_and_analysis_batch_equal_direct_native_results(self):
        v=self.v;span=v.FindParm(self.gid,'TotalSpan','WingGeom');sweep=v.FindParm(self.gid,'Sweep','XSec_1');self.assertTrue(v.ValidParm(sweep))
        before=self.model.read_bytes();plan=self.save([dict(kind='parameter',id=span,values=[12.,18.]),dict(kind='parameter',id=sweep,values=[0.,20.])],stages=[dict(name='CompGeom',inputs=[]),dict(name='MassProp',inputs=[])])
        self.assertEqual(plan['caseCount'],4);batch=studies.launch(plan['id']);batch=self.wait(plan['id'],batch['id']);self.assertEqual(batch['status'],'complete',batch)
        for case in batch['cases']:
            model=studies.batch_folder(plan['id'],batch['id'])/'cases'/str(case['index'])/'aircraft.vsp3'
            v.ClearVSPModel();v.ReadVSPFile(str(model));v.Update();self.assertEqual([v.GetParmVal(span),v.GetParmVal(sweep)],case['values'])
            for stage in case['stages']:
                v.ClearVSPModel();v.ReadVSPFile(str(model));v.Update();v.SetVSP3FileName(str(self.path/f'direct-{case["index"]}-{stage["index"]}.vsp3'))
                v.SetAnalysisInputDefaults(stage['name']);v.ExecAnalysis(stage['name']);native_worker.errors(v)
                expected=native_worker.collect_results(v);job=service.job_state(stage['job'])
                for result in expected:
                    actual=next(r for r in job['result']['results'] if r['name']==result['name'] and r['index']==result['index'])
                    for e in result['entries']:
                        if e['name']!='Analysis_Duration_Sec' and e['type'] in (v.INT_DATA,v.DOUBLE_DATA,v.VEC3D_DATA,v.DOUBLE_MATRIX_DATA):self.assertEqual(next(x['values'] for x in actual['entries'] if x['name']==e['name'] and x['index']==e['index']),e['values'],e['name'])
                self.assertEqual([p['value'] for p in job['result']['studyParameters']],case['values'])
                self.assertTrue(service.artifact_file(stage['job'],'native-model-after-analysis.vsp3').is_file())
        self.assertEqual(self.model.read_bytes(),before);self.assertFalse(service.HISTORY)
        fields=studies.result_fields(plan['id'],batch['id']);field=next(f for f in fields if f['field']=='Total_Wet_Area')
        table=studies.comparison(plan['id'],batch['id'],field['key']);self.assertEqual([r['effective'] for r in table['rows']],[c['values'] for c in batch['cases']]);self.assertTrue(all(r['values'] is not None for r in table['rows']))

    def test_native_reference_input_and_vector_coordinate_sweeps_preserve_every_sample(self):
        stages=[dict(name='HersheyBarTheory',inputs=[dict(name='NumPoints',values=[16])]),dict(name='EllipsoidFlowTheory',inputs=[dict(name='NumPointsU',values=[20]),dict(name='NumPointsW',values=[20])])]
        plan=self.save([dict(kind='input',stage=0,name='AngleOfAttackDegrees',values=[0.,6.]),dict(kind='input',stage=1,name='Center',component=0,values=[0.,4.])],stages=stages)
        batch=studies.launch(plan['id']);batch=self.wait(plan['id'],batch['id']);self.assertEqual(batch['status'],'complete',batch)
        v=self.v
        for case in batch['cases']:
            wing=service.job_state(case['stages'][0]['job'])['result'];alpha,center=case['values'];p=v.GetHersheyBarLiftDist(16,math.radians(alpha),100.,10.,True)
            self.assertEqual(next(e['values'] for e in wing['results'][0]['entries'] if e['name']=='cl'),[q.y() for q in p])
            ellipsoid=service.job_state(case['stages'][1]['job'])['result'];nodes=v.GetEllipsoidSurfPnts(v.vec3d(center,0,0),v.vec3d(1,2,3),20,20)
            self.assertEqual(next(e['values'] for e in ellipsoid['results'][0]['entries'] if e['name']=='X_Loc'),[q.x() for q in nodes])
        field=next(f for f in studies.result_fields(plan['id'],batch['id']) if f['field']=='Cp')
        table=studies.comparison(plan['id'],batch['id'],field['key']);self.assertEqual([r['effective'] for r in table['rows']],[c['values'] for c in batch['cases']]);self.assertTrue(all(len(r['values'])==400 for r in table['rows']))

    def test_baseline_is_frozen_and_native_results_csv_bundle_survive_memory_reset(self):
        span=self.v.FindParm(self.gid,'TotalSpan','WingGeom');plan=self.save([dict(kind='parameter',id=span,values=[12.,18.])]);old_source=plan['sourceHash']
        self.v.SetParmValUpdate(span,30.);self.v.WriteVSPFile(str(self.model),self.v.SET_ALL);current=self.model.read_bytes()
        batch=studies.launch(plan['id']);batch=self.wait(plan['id'],batch['id']);self.assertEqual(batch['status'],'complete')
        service.JOBS={};studies.RUNNERS={};self.assertEqual(studies.list_studies()[0]['executions'][0]['status'],'complete')
        field=next(f for f in studies.result_fields(plan['id'],batch['id']) if f['field']=='Total_Wet_Vol')
        table=studies.comparison(plan['id'],batch['id'],field['key']);self.assertEqual(table['sourceHash'],old_source)
        rows=list(csv.DictReader(io.StringIO(studies.csv_comparison(plan['id'],batch['id'],field['key']).decode())));self.assertEqual(len(rows),2);self.assertEqual([float(r['value']) for r in rows],[r['values'][0] for r in table['rows']])
        with zipfile.ZipFile(io.BytesIO(studies.bundle(plan['id'],batch['id']))) as archive:
            self.assertIn('aircraft.vsp3',archive.namelist());self.assertIn('batch.json',archive.namelist());self.assertIn('cases/0/step-0/attempt-0/response.json',archive.namelist());self.assertIn('cases/1/aircraft.vsp3',archive.namelist())
        self.assertEqual(self.model.read_bytes(),current)

    def test_partial_native_failure_and_resume_keep_successful_cases(self):
        plan=self.save([dict(kind='input',stage=0,name='FreestreamSpeed',values=[0.,100.])],stages=[dict(name='HersheyBarTheory',inputs=[dict(name='NumPoints',values=[16])])])
        batch=studies.launch(plan['id']);batch=self.wait(plan['id'],batch['id']);self.assertEqual(batch['status'],'partial');good=batch['cases'][1]['stages'][0]['job'];bad=batch['cases'][0]['stages'][0]['job']
        self.assertIn('positive',batch['cases'][0]['error'])
        resumed=studies.launch(plan['id'],batch['id']);resumed=self.wait(plan['id'],resumed['id']);self.assertEqual(resumed['cases'][1]['stages'][0]['job'],good);self.assertNotEqual(resumed['cases'][0]['stages'][0]['job'],bad)
        self.assertEqual(len(resumed['cases'][0]['stages'][0]['attempts']),2)
        f=next(f for f in studies.result_fields(plan['id'],batch['id']) if f['field']=='cl');data=studies.comparison(plan['id'],batch['id'],f['key']);self.assertIsNone(data['rows'][0]['values']);self.assertEqual(len(data['rows'][1]['values']),32)

    def test_profile_preparation_failure_has_no_pending_calculations_and_corrected_execution_preserves_history(self):
        v=self.v;v.ClearVSPModel();self.gid=v.AddGeom('FUSELAGE')
        x=v.GetXSec(v.GetXSecSurf(self.gid,0),1)
        for name,value in [('Chevron_Type',1),('W01_Mode',1),('W01_Width',.35),('TopAmplitude',.1)]:
            v.SetParmValUpdate(v.GetXSecParm(x,name),value)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        width=v.GetXSecParm(x,'W01_Width');source=self.model.read_bytes()
        axes=[dict(kind='parameter',id=width,values=[0.,.35])]
        stages=[dict(name='CompGeom',inputs=[]),dict(name='MassProp',inputs=[])]
        plan=self.save(axes,stages=stages);batch=studies.launch(plan['id']);batch=self.wait(plan['id'],batch['id'])
        self.assertEqual(batch['status'],'partial')
        bad,good=batch['cases'];self.assertEqual(bad['status'],'failed');self.assertIn('nonzero outline width',bad['error'])
        self.assertTrue(all(s['status']=='not-run' and not s.get('job') and not s['attempts'] for s in bad['stages']))
        self.assertEqual((studies.batch_folder(plan['id'],batch['id'])/'cases/0/aircraft.vsp3').read_bytes(),source)
        self.assertEqual(good['status'],'complete');good_jobs=[s['job'] for s in good['stages']]
        # Recover an older saved batch whose rejected calculations were still
        # labelled pending. Native successful jobs and their data stay intact.
        for stage in bad['stages']:stage['status']='pending'
        studies.write_json(studies.batch_folder(plan['id'],batch['id'])/'batch.json',batch)
        recovered=studies.batch_state(plan['id'],batch['id'])
        self.assertEqual([s['status'] for s in recovered['cases'][0]['stages']],['not-run','not-run'])
        self.assertEqual([s['job'] for s in recovered['cases'][1]['stages']],good_jobs)
        axes[0]['values']=[.2,.35]
        corrected=self.save(axes,stages=stages,id=plan['id'],definitionVersion=plan['version'],baseline='saved')
        completed=studies.launch(plan['id']);completed=self.wait(plan['id'],completed['id'])
        self.assertEqual(completed['status'],'complete')
        self.assertEqual(corrected['sourceHash'],plan['sourceHash'])
        older=studies.batch_state(plan['id'],batch['id'])
        self.assertEqual(older['plan']['axes'][0]['values'],[0.,.35])
        self.assertEqual([s['job'] for s in older['cases'][1]['stages']],good_jobs)
        self.assertEqual(self.model.read_bytes(),source)

    def test_restart_reuses_job_created_before_case_journal_was_updated(self):
        plan=self.save([]);batch=studies.launch(plan['id']);batch=self.wait(plan['id'],batch['id']);stage=batch['cases'][0]['stages'][0];jid=stage.pop('job');stage.update(status='starting',attempts=[]);batch.update(status='running');batch['cases'][0]['status']='running';batch.pop('live',None)
        studies.write_json(studies.batch_folder(plan['id'],batch['id'])/'batch.json',batch);service.JOBS={}
        recovered=studies.batch_state(plan['id'],batch['id']);self.assertEqual(recovered['status'],'complete');self.assertEqual(recovered['cases'][0]['stages'][0]['job'],jid);self.assertEqual(len(service.list_jobs()),1)

    def test_real_worker_survives_server_exit_and_resume_does_not_duplicate_completed_work(self):
        span=self.v.FindParm(self.gid,'TotalSpan','WingGeom');plan=self.save([dict(kind='parameter',id=span,values=[12.,18.])]);script=self.path/'launch-process.py';marker=self.path/'stopped-worker.json'
        script.write_text(f'''import sys,time,os,signal,json
from pathlib import Path
sys.path.insert(0,{str(ROOT)!r})
import native_service as service
import native_studies as studies
service.WORK=Path({str(self.path)!r});service.MODEL=Path({str(self.model)!r})
original=service.start_job
def start(*args,**kwargs):
 job=original(*args,**kwargs);pid=service.JOBS[job['id']]['_process'].pid
 os.kill(pid,signal.SIGSTOP)
 Path({str(marker)!r}).write_text(json.dumps(dict(pid=pid,job=job['id'])))
 return job
service.start_job=start
batch=studies.launch({plan['id']!r});Path({str(self.path/'batch-id')!r}).write_text(batch['id'])
while True:time.sleep(.1)
''')
        with (self.path/'launcher.log').open('w') as log:
            process=subprocess.Popen([interpreter(),str(script)],stdout=log,stderr=log)
            pid=None
            try:
                deadline=time.monotonic()+15
                while not marker.exists() and time.monotonic()<deadline:
                    if process.poll() is not None:self.fail((self.path/'launcher.log').read_text())
                    time.sleep(.01)
                self.assertTrue(marker.exists());data=json.loads(marker.read_text());pid=data['pid'];bid=(self.path/'batch-id').read_text()
                # Wait for the saved stage record before killing only the server.
                while not read_stage(studies.batch_folder(plan['id'],bid)).get('job') and time.monotonic()<deadline:time.sleep(.01)
                process.kill();process.wait(timeout=5);service.JOBS={};live=studies.batch_state(plan['id'],bid)
                self.assertTrue(live['live']);self.assertEqual(live['status'],'running');self.assertEqual(service.job_state(data['job'])['status'],'running')
                self.assertEqual(studies.launch(plan['id'],bid)['id'],bid);self.assertEqual(len(service.list_jobs()),1)
                with self.assertRaises(ValueError):service.start_job(dict(name='CompGeom',revision=service.REVISION,inputs=[]))
                os.kill(pid,signal.SIGCONT)
                deadline=time.monotonic()+30
                while studies.batch_state(plan['id'],bid)['live'] and time.monotonic()<deadline:time.sleep(.03)
                interrupted=studies.batch_state(plan['id'],bid);self.assertEqual(interrupted['status'],'interrupted');self.assertEqual(interrupted['cases'][0]['status'],'complete')
                resumed=studies.launch(plan['id'],bid);resumed=self.wait(plan['id'],bid);self.assertEqual(resumed['status'],'complete',resumed);self.assertEqual(resumed['cases'][0]['stages'][0]['job'],data['job']);self.assertEqual(len(service.list_jobs()),2)
            finally:
                if process.poll() is None:process.kill();process.wait(timeout=5)
                if pid:
                    try:os.kill(pid,signal.SIGCONT)
                    except ProcessLookupError:pass

    def test_saved_definition_edit_is_versioned_and_preserves_older_execution(self):
        span=self.v.FindParm(self.gid,'TotalSpan','WingGeom');plan=self.save([dict(kind='parameter',id=span,values=[12.])]);batch=studies.launch(plan['id']);old=self.wait(plan['id'],batch['id'])
        self.v.SetParmValUpdate(span,30.);self.v.WriteVSPFile(str(self.model),self.v.SET_ALL)
        request=dict(id=plan['id'],definitionVersion=plan['version'],name='Edited saved study',revision=service.REVISION,baseline='saved',axes=[dict(kind='parameter',id=span,values=[18.])],stages=plan['stages'])
        edited=studies.save_study(request);self.assertEqual(edited['sourceHash'],plan['sourceHash']);self.assertNotEqual(edited['version'],plan['version'])
        self.assertEqual(studies.batch_state(plan['id'],old['id'])['plan'],plan)
        with self.assertRaisesRegex(ValueError,'another window'):studies.save_study(request)
        request.update(definitionVersion=edited['version'],baseline='current');current=studies.save_study(request);self.assertNotEqual(current['sourceHash'],plan['sourceHash'])
        self.assertEqual(studies.batch_state(plan['id'],old['id'])['plan'],plan)

    def test_cancel_native_execution_and_resume_preserves_completed_steps(self):
        plan=self.save([dict(kind='input',stage=0,name='AngleOfAttackDegrees',values=list(range(12)))],stages=[dict(name='HersheyBarTheory',inputs=[dict(name='NumPoints',values=[16])])])
        batch=studies.launch(plan['id']);deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            batch=studies.batch_state(plan['id'],batch['id'])
            if batch['completed'] and any(s['status']=='running' for c in batch['cases'] for s in c['stages']):break
            time.sleep(.01)
        self.assertGreater(batch['completed'],0);completed={c['index']:c['stages'][0]['job'] for c in batch['cases'] if c['status']=='complete'}
        studies.cancel(plan['id'],batch['id']);cancelled=self.wait(plan['id'],batch['id']);self.assertEqual(cancelled['status'],'cancelled');self.assertLess(cancelled['completed'],12)
        self.assertFalse(service.lock_is_held(service.WORK/'run.lock'))
        # Resume the original cases and retain every successful native run.
        resumed=studies.launch(plan['id'],batch['id']);resumed=self.wait(plan['id'],batch['id']);self.assertEqual(resumed['status'],'complete')
        for i,jid in completed.items():self.assertEqual(resumed['cases'][i]['stages'][0]['job'],jid)
        self.assertTrue(any(j['status']=='cancelled' for j in service.list_jobs()))

    def test_aerodynamic_study_passes_each_native_database_to_its_slicer(self):
        inputs={'AlphaStart':4.,'AlphaEnd':4.,'AlphaNpts':1,'NCPU':1,'MachStart':.1,'MachEnd':.1,'MachNpts':1}
        plan=self.save([dict(kind='input',stage=1,name='YSlicePosVec',values=[1.,2.])],stages=[dict(name='VSPAEROSweep',inputs=[dict(name=n,values=[x]) for n,x in inputs.items()]),dict(name='CpSlicer',sourceStage=0,inputs=[dict(name='YSlicePosVec',values=[1.])])])
        batch=studies.launch(plan['id']);batch=self.wait(plan['id'],batch['id']);self.assertEqual(batch['status'],'complete',batch)
        from aero_io import read_adb
        for case in batch['cases']:
            source,step=case['stages'];source_folder=service.job_folder(source['job']);step_folder=service.job_folder(step['job'])
            self.assertEqual((source_folder/'aircraft.adb').read_bytes(),(step_folder/'aircraft.adb').read_bytes())
            req=json.loads((step_folder/'request.json').read_text());self.assertEqual(req['sourceRun'],source['job'])
            data=service.job_state(step['job'])['result'];slices=[r for r in data['results'] if r['name']=='CpSlicer_Case'];self.assertTrue(slices)
            entries={e['name']:e['values'] for e in slices[0]['entries']};self.assertTrue(entries['Cp']);self.assertTrue(all(y==case['values'][0] for y in entries['Y_Loc']))
        field=next(f for f in studies.result_fields(plan['id'],batch['id']) if f['result']=='CpSlicer_Case' and f['field']=='Cp')
        table=studies.comparison(plan['id'],batch['id'],field['key']);self.assertEqual([r['effective'] for r in table['rows']],[[1.],[2.]])

    def test_invalid_study_limits_references_and_path_access_are_rejected(self):
        span=self.v.FindParm(self.gid,'TotalSpan','WingGeom');before=self.model.read_bytes()
        for axes,stages in [([dict(kind='parameter',id='missing',values=[1.])],None),([dict(kind='parameter',id=span,values=[-1.])],None),([dict(kind='parameter',id=span,values=[float('nan')])],None),([dict(kind='parameter',id=span,values=list(range(1,1001))),dict(kind='input',stage=0,name='Set',values=[0,1])],None),([dict(kind='input',stage=0,name='Set',values=[.5])],None),([], [dict(name='MissingAnalysis')]),([], [dict(name='CpSlicer')])]:
            with self.subTest(axes=axes,stages=stages),self.assertRaises(ValueError):self.save(axes,stages)
        self.assertEqual(self.model.read_bytes(),before)
        for sid in ['../','a'*31,'/tmp']:
            with self.assertRaises(ValueError):studies.definition(sid)
        plan=self.save([])
        with self.assertRaises(ValueError):studies.bundle(plan['id'],'../')


def read_stage(folder):return studies.read_json(folder/'batch.json')['cases'][0]['stages'][0]


if __name__=='__main__':unittest.main()
