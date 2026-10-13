"""Native categorical, vector and array studies, including saved provenance."""
import csv
import io
import json
import math
from pathlib import Path
import shutil
import sys
import unittest
import test_studies
import native_service as service
import native_studies as studies
import native_worker
from vsp_runtime import load


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativeStudyValues(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    worker=test_studies.NativeStudies.worker
    save=test_studies.NativeStudies.save
    wait=test_studies.NativeStudies.wait

    def run_plan(self,plan):
        batch=studies.launch(plan['id']);batch=self.wait(plan['id'],batch['id'])
        self.assertEqual(batch['status'],'complete',[dict(case=c['index'],error=c.get('error')) for c in batch['cases']])
        return batch

    def field(self,plan,batch,name,result=None,stage=None):
        field=next(f for f in studies.result_fields(plan['id'],batch['id']) if f['field']==name and (result is None or f['result']==result) and (stage is None or f['stage']==stage))
        return studies.comparison(plan['id'],batch['id'],field['key'])

    def direct(self,model,job):
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(model));v.Update()
        native_worker.analysis_schema(v,job['name']);native_worker.set_inputs(v,job['name'],job['result']['inputs'])
        v.ExecAnalysis(job['name']);native_worker.errors(v)
        for result in native_worker.collect_results(v):
            actual=next(r for r in job['result']['results'] if r['name']==result['name'] and r['index']==result['index'])
            for e in result['entries']:
                if e['name']!='Analysis_Duration_Sec' and e['type'] in (v.INT_DATA,v.DOUBLE_DATA,v.VEC3D_DATA,v.DOUBLE_MATRIX_DATA):
                    self.assertEqual(next(x['values'] for x in actual['entries'] if x['name']==e['name'] and x['index']==e['index']),e['values'],e['name'])

    def test_categorical_geometry_references_and_native_options_match_direct_projection(self):
        v=self.v;pod=v.AddGeom('POD');v.SetGeomName(pod,'Reference body');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);original=self.model.read_bytes()
        plan=self.save([dict(kind='input',stage=0,name='TargetGeomID',values=[self.gid,pod]),dict(kind='input',stage=0,name='DirectionType',values=[v.X_PROJ,v.Y_PROJ,v.Z_PROJ])],stages=[dict(name='Projection',inputs=[dict(name='TargetType',values=[v.GEOM_TARGET])])])
        self.assertEqual(plan['caseCount'],6);self.assertTrue(plan['axes'][0]['choices']);self.assertTrue(plan['axes'][1]['choices'])
        batch=self.run_plan(plan)
        for case in batch['cases']:
            model=studies.batch_folder(plan['id'],batch['id'])/'cases'/str(case['index'])/'aircraft.vsp3'
            self.direct(model,service.job_state(case['stages'][0]['job']))
        table=self.field(plan,batch,'Area');self.assertEqual([r['requested'] for r in table['rows']],[r['effective'] for r in table['rows']])
        self.assertEqual(self.model.read_bytes(),original)

    def test_entire_vectors_and_vector_arrays_preserve_exact_native_flow_samples(self):
        plan=self.save([dict(kind='input',stage=0,name='Center',values=[[0.,0.,0.],[4.,-2.,1.]]),dict(kind='input',stage=0,name='FreestreamVelocity',valueMode='array',values=[[[100.,0.,0.]],[[100.,50.,25.]]])],stages=[dict(name='EllipsoidFlowTheory',inputs=[dict(name='NumPointsU',values=[20]),dict(name='NumPointsW',values=[20])])])
        batch=self.run_plan(plan);v=self.v
        local=v.GetEllipsoidSurfPnts(v.vec3d(0,0,0),v.vec3d(1,2,3),20,20)
        for case in batch['cases']:
            center,velocity=case['values'];result=service.job_state(case['stages'][0]['job'])['result'];entries={e['name']:e['values'] for e in result['results'][0]['entries']}
            points=v.GetEllipsoidSurfPnts(v.vec3d(*center),v.vec3d(1,2,3),20,20)
            self.assertEqual(entries['X_Loc'],[p.x() for p in points]);self.assertEqual(entries['Y_Loc'],[p.y() for p in points]);self.assertEqual(entries['Z_Loc'],[p.z() for p in points])
            self.assertEqual(entries['Cp'],list(v.GetEllipsoidCpDist(local,v.vec3d(1,2,3),v.vec3d(*velocity[0]))))
        table=self.field(plan,batch,'Cp');self.assertEqual([r['requested'] for r in table['rows']],[r['effective'] for r in table['rows']]);self.assertEqual(len(table['rows'][0]['values']),400)

    def test_string_arrays_including_empty_native_flow_regions_match_wave_drag(self):
        v=self.v;region=v.AddSubSurf(self.gid,v.SS_RECTANGLE);v.SetSubSurfName(region,'Native flow region')
        settings=v.FindContainer('WaveDragSettings',0);v.SetParmVal(v.FindParm(settings,'Sref','WaveDrag'),45);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        plan=self.save([dict(kind='input',stage=0,name='SSFlow_vec',valueMode='array',values=[[],[region]])],stages=[dict(name='WaveDrag',inputs=[dict(name='Mach',values=[1.8]),dict(name='NumSlices',values=[15]),dict(name='NumRotSects',values=[5])])])
        batch=self.run_plan(plan)
        for case in batch['cases']:
            self.direct(studies.batch_folder(plan['id'],batch['id'])/'cases'/str(case['index'])/'aircraft.vsp3',service.job_state(case['stages'][0]['job']))
        table=self.field(plan,batch,'CDWave');self.assertEqual([r['effective'] for r in table['rows']],[[[]],[[region]]])
        rows=list(csv.DictReader(io.StringIO(studies.csv_comparison(plan['id'],batch['id'],table['field']['key']).decode())))
        key=plan['axes'][0]['label']+' native';self.assertEqual([json.loads(r[key]) for r in rows],[[],[region]])

    def test_disjoint_vector_coordinates_merge_without_losing_saved_values(self):
        plan=self.save([dict(kind='input',stage=0,name='Center',component=0,values=[3.,5.]),dict(kind='input',stage=0,name='Center',component=2,values=[-1.,2.])],stages=[dict(name='EllipsoidFlowTheory',inputs=[dict(name='Center',values=[[1.,7.,9.]]),dict(name='NumPointsU',values=[20]),dict(name='NumPointsW',values=[20])])])
        batch=self.run_plan(plan)
        for case in batch['cases']:
            result=service.job_state(case['stages'][0]['job'])['result'];center=next(e['values'] for e in result['inputs'] if e['name']=='Center')[0]
            self.assertEqual(center,[case['values'][0],7.,case['values'][1]])
        table=self.field(plan,batch,'X_Loc');self.assertEqual([r['requested'] for r in table['rows']],[r['effective'] for r in table['rows']])

    def slicer(self,axis):
        flight={'AlphaStart':4.,'AlphaEnd':4.,'AlphaNpts':1,'NCPU':1,'MachStart':.1,'MachEnd':.1,'MachNpts':1}
        return self.save(axis,stages=[dict(name='VSPAEROSweep',inputs=[dict(name=n,values=[x]) for n,x in flight.items()]),dict(name='CpSlicer',sourceStage=0,inputs=[dict(name='YSlicePosVec',values=[1.,2.,3.])])])

    def verify_slices(self,plan,batch):
        v=self.v
        for case in batch['cases']:
            job=service.job_state(case['stages'][1]['job']);positions=next(e['values'] for e in job['result']['inputs'] if e['name']=='YSlicePosVec')
            # Copy the official database companions for an independent direct run.
            directory=self.path/f'direct-slicer-{case["index"]}';directory.mkdir()
            for path in service.job_folder(case['stages'][0]['job']).glob('aircraft.*'):
                if path.is_file():shutil.copy2(path,directory/path.name)
            model=studies.batch_folder(plan['id'],batch['id'])/'cases'/str(case['index'])/'aircraft.vsp3'
            v.ClearVSPModel();v.ReadVSPFile(str(model));v.Update();v.SetAnalysisInputDefaults('CpSlicer')
            v.SetVSP3FileName(str(directory/'aircraft.vsp3'));v.SetAnalysisInputDefaults('CpSlicer');v.SetDoubleAnalysisInput('CpSlicer','YSlicePosVec',positions)
            v.ExecAnalysis('CpSlicer');native_worker.errors(v)
            actual=[r for r in job['result']['results'] if r['name']=='CpSlicer_Case'];expected=[r for r in native_worker.collect_results(v) if r['name']=='CpSlicer_Case']
            self.assertEqual(len(actual),len(positions));self.assertEqual(len(actual),len(expected))
            for a,e in zip(actual,expected):
                self.assertEqual([(x['name'],x['index'],x['values']) for x in a['entries']],[(x['name'],x['index'],x['values']) for x in e['entries']])

    def test_numeric_arrays_have_variable_lengths_and_exact_native_slicer_outputs(self):
        plan=self.slicer([dict(kind='input',stage=1,name='YSlicePosVec',valueMode='array',values=[[1.,2.],[-2.,0.,2.]])]);batch=self.run_plan(plan);self.verify_slices(plan,batch)
        table=self.field(plan,batch,'Cp');self.assertEqual([r['requested'] for r in table['rows']],[r['effective'] for r in table['rows']])
        service.JOBS={};studies.RUNNERS={};cold=studies.definition(plan['id']);self.assertEqual(cold['axes'],plan['axes']);self.assertEqual(studies.comparison(plan['id'],batch['id'],table['field']['key']),table)

    def test_supplied_area_array_studies_match_native_integration_and_preserve_invalid_definition(self):
        original=self.model.read_bytes()
        stages=[dict(name='EmintonLord',inputs=[dict(name='X_vec',values=[0.,1.,2.,3.]),dict(name='Area_vec',values=[0.,2.,3.,0.])])]
        axis=dict(kind='input',stage=0,name='Area_vec',valueMode='array',values=[[0.,2.,3.,0.],[0.,1.,4.,0.]])
        plan=self.save([axis],stages=stages);batch=self.run_plan(plan)
        for case in batch['cases']:
            model=studies.batch_folder(plan['id'],batch['id'])/'cases'/str(case['index'])/'aircraft.vsp3'
            self.direct(model,service.job_state(case['stages'][0]['job']))
        table=self.field(plan,batch,'Donq');self.assertEqual([r['requested'] for r in table['rows']],[r['effective'] for r in table['rows']])
        before=studies.definition(plan['id']);source=(studies.study_folder(plan['id'])/'aircraft.vsp3').read_bytes()
        invalid={**axis,'values':[[0.,2.,0.]]}
        with self.assertRaisesRegex(ValueError,'matching station and area lists'):
            studies.save_study(dict(id=plan['id'],definitionVersion=plan['version'],baseline='saved',name=plan['name'],revision=service.REVISION,stages=stages,axes=[invalid]))
        self.assertEqual(studies.definition(plan['id']),before);self.assertEqual((studies.study_folder(plan['id'])/'aircraft.vsp3').read_bytes(),source);self.assertEqual(self.model.read_bytes(),original)
        service.JOBS={};studies.RUNNERS={};self.assertEqual(studies.comparison(plan['id'],batch['id'],table['field']['key']),table)

    def test_array_elements_merge_and_preserve_other_native_slice_positions(self):
        plan=self.slicer([dict(kind='input',stage=1,name='YSlicePosVec',element=0,values=[-.5,.5]),dict(kind='input',stage=1,name='YSlicePosVec',element=1,values=[1.,2.])]);batch=self.run_plan(plan);self.verify_slices(plan,batch)
        for case in batch['cases']:
            result=service.job_state(case['stages'][1]['job'])['result'];positions=next(e['values'] for e in result['inputs'] if e['name']=='YSlicePosVec')
            self.assertEqual(positions,[*case['values'],3.])
        table=self.field(plan,batch,'Cp');self.assertEqual([r['requested'] for r in table['rows']],[r['effective'] for r in table['rows']])

    def test_partial_array_sweep_keeps_case_native_defaults_and_explicit_freeze(self):
        v=self.v;v.DeleteAllCpSlices();v.AddCpSlice(v.Y_DIR,1.);second=v.AddCpSlice(v.Y_DIR,2.);pid=v.FindParm(second,'CutPosition','CpSlice')
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        axes=[dict(kind='parameter',id=pid,values=[2.,4.]),dict(kind='input',stage=1,name='YSlicePosVec',element=0,values=[-.5,.5])]
        plan=self.slicer(axes);plan['stages'][1]['inputs']=[]
        plan=self.save(axes,stages=plan['stages']);batch=self.run_plan(plan);self.verify_slices(plan,batch)
        for case in batch['cases']:
            result=service.job_state(case['stages'][1]['job'])['result'];positions=next(e['values'] for e in result['inputs'] if e['name']=='YSlicePosVec')
            self.assertEqual(positions,[case['values'][1],case['values'][0]])
            record=result['studyParameters'][0];self.assertEqual(record['value'],case['values'][0]);self.assertFalse(record['availableAfterAnalysis']);self.assertIsNone(record['valueAfterAnalysis']);self.assertTrue(result['studyParameterWarnings'])
        table=self.field(plan,batch,'Cp','CpSlicer_Case',1);self.assertEqual([r['requested'] for r in table['rows']],[r['effective'] for r in table['rows']]);self.assertTrue(all(r['warnings'] for r in table['rows']))
        rows=list(csv.DictReader(io.StringIO(studies.csv_comparison(plan['id'],batch['id'],table['field']['key']).decode())))
        self.assertTrue(all('before replacement' in r['native_setting_notes'] for r in rows))
        frozen=self.save(axes[:1],stages=[*plan['stages'][:1],dict(name='CpSlicer',sourceStage=0,freezeInputs=True,inputs=[dict(name='YSlicePosVec',values=[1.,2.])])])
        fixed=self.run_plan(frozen)
        for case in fixed['cases']:
            values=next(e['values'] for e in service.job_state(case['stages'][1]['job'])['result']['inputs'] if e['name']=='YSlicePosVec')
            self.assertEqual(values,[1.,2.])

    def test_invalid_shapes_choices_overlaps_and_saved_definition_are_guarded(self):
        plan=self.save([],stages=[dict(name='Projection',inputs=[])]);before=studies.definition(plan['id']);source=(studies.study_folder(plan['id'])/'aircraft.vsp3').read_bytes();current=self.model.read_bytes()
        axes=[dict(kind='input',stage=0,name='DirectionType',values=[999]),dict(kind='input',stage=0,name='TargetGeomID',values=[123]),dict(kind='input',stage=0,name='Direction',values=[[1.,2.]]),dict(kind='input',stage=0,name='Direction',valueMode='array',values=[[[1.,0.,0.],[0.,1.,0.]]]),dict(kind='input',stage=0,name='Direction',component=4,values=[1.]),dict(kind='input',stage=0,name='Direction',element=True,values=[[1.,0.,0.]]),dict(kind='input',stage=0,name='Direction',index=False,values=[[1.,0.,0.]]),dict(kind='input',stage=0,name='Direction',valueMode='unknown',values=[[1.,0.,0.]]),dict(kind='input',stage=0,name='Direction',element=2,values=[[1.,0.,0.]]),dict(kind='input',stage=0,name='Direction',component=1,values=[float('nan')])]
        for axis in axes:
            with self.subTest(axis=axis),self.assertRaises(ValueError):studies.save_study(dict(id=plan['id'],definitionVersion=plan['version'],baseline='saved',name=plan['name'],revision=service.REVISION,stages=plan['stages'],axes=[axis]))
        whole=dict(kind='input',stage=0,name='Direction',valueMode='array',values=[[[1.,0.,0.]]]);vector=dict(kind='input',stage=0,name='Direction',values=[[1.,0.,0.]]);coordinate=dict(kind='input',stage=0,name='Direction',component=0,values=[1.])
        for pair in ([whole,coordinate],[coordinate,whole],[vector,coordinate],[coordinate,vector],[coordinate,coordinate]):
            with self.subTest(pair=pair),self.assertRaisesRegex(ValueError,'overwrite'):self.save(pair,stages=plan['stages'])
        self.assertEqual(studies.definition(plan['id']),before);self.assertEqual((studies.study_folder(plan['id'])/'aircraft.vsp3').read_bytes(),source);self.assertEqual(self.model.read_bytes(),current)


if __name__=='__main__':unittest.main()
