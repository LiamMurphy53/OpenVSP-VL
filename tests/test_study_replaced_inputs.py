"""Complete input sweeps supply omitted starting inputs through original analysis."""
import json,unittest,csv,io
import test_studies
import native_studies as studies,native_service as service,native_worker

class StudyReplacedInputs(unittest.TestCase):
    setUpClass=classmethod(test_studies.NativeStudies.setUpClass.__func__)
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    save=test_studies.NativeStudies.save
    wait=test_studies.NativeStudies.wait

    def test_slice_start_sweep_supplies_omitted_manual_start_and_matches_original(self):
        v=self.v;source=self.model.read_bytes()
        inputs=[dict(name=n,index=0,values=[value]) for n,value in [('AutoBoundFlag',0),('EndVal',6.),('NumSlices',5),('Set',0)]]
        inputs.append(dict(name='Norm',index=0,values=[[1.,0.,0.]]))
        plan=self.save([dict(kind='input',stage=0,name='StartVal',values=[1.,3.])],[dict(name='PlanarSlice',inputs=inputs)])
        self.assertFalse(any(e['name']=='StartVal' for e in plan['stages'][0]['inputs']))
        baseline=studies.study_folder(plan['id'])/'aircraft.vsp3';frozen=baseline.read_bytes();batch=self.wait(plan['id'],studies.launch(plan['id'])['id']);self.assertEqual(batch['status'],'complete');areas=[]
        def numeric(results):return sorted((r['name'],e['name'],e['index'],json.dumps(e['values'])) for r in results for e in r['entries'] if e['type'] in (1,2,4) and e['name']!='Analysis_Duration_Sec')
        for case in batch['cases']:
            start=case['values'][0];job=service.job_state(case['stages'][0]['job']);self.assertEqual(job['status'],'complete');result=job['result'];self.assertEqual(next(e['values'] for e in result['inputs'] if e['name']=='StartVal'),[start])
            areas.append(next(e['values'] for r in result['results'] for e in r['entries'] if e['name']=='Slice_Area'))
            v.ClearVSPModel();v.ReadVSPFile(str(baseline));v.Update();v.DeleteAllResults();v.SetVSP3FileName(str(self.path/('original-start-'+str(start)+'.vsp3')));v.SetAnalysisInputDefaults('PlanarSlice')
            for e in inputs+[dict(name='StartVal',values=[start])]:
                kind=v.GetAnalysisInputType('PlanarSlice',e['name'])
                if kind==v.VEC3D_DATA:v.SetVec3dAnalysisInput('PlanarSlice',e['name'],[v.vec3d(*p) for p in e['values']])
                else:
                    setter=v.SetDoubleAnalysisInput if kind==v.DOUBLE_DATA else v.SetIntAnalysisInput;setter('PlanarSlice',e['name'],e['values'])
            self.assertTrue(v.ExecAnalysis('PlanarSlice'));native_worker.errors(v);self.assertEqual(numeric(result['results']),numeric(native_worker.collect_results(v)))
        field=next(f for f in studies.result_fields(plan['id'],batch['id']) if f['field']=='Slice_Area');self.assertEqual(field['unit'],'model length²')
        rows=list(csv.DictReader(io.StringIO(studies.csv_comparison(plan['id'],batch['id'],field['key']).decode())))
        self.assertEqual([float(row['value']) for row in rows],[value for values in areas for value in values]);self.assertTrue(all(row['value_units']=='model length²' for row in rows))
        self.assertNotEqual(*areas);self.assertEqual(self.model.read_bytes(),source);self.assertEqual(baseline.read_bytes(),frozen)
