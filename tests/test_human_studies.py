"""Native Human controller sweeps, conditional failures and exact replay."""
import sys,unittest
import test_studies,native_files,native_worker
import native_service as service,native_studies as studies
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class HumanStudies(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    worker=test_studies.NativeStudies.worker
    save=test_studies.NativeStudies.save
    wait=test_studies.NativeStudies.wait

    def fixture(self):
        v=self.v;self.hid=v.AddGeom('HUMAN');v.SetGeomName(self.hid,'Study occupant');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        self.ids={v.GetParmName(p):p for p in v.GetGeomParmIDs(self.hid)}

    def capture(self):
        v=self.v
        return dict(parameters={p:(v.GetParmVal(p),v.GetParmLowerLimit(p),v.GetParmUpperLimit(p)) for p in v.GetGeomParmIDs(self.hid)},mesh=native_files.solid_preview(v,self.hid))

    def original(self,edits,source=None):
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(source or self.model));v.Update()
        for n,x in edits:v.SetParmValUpdate(self.ids[n],x)
        v.Update();path=self.path/'human-sdk-prepared.vsp3';v.WriteVSPFile(str(path),v.SET_ALL)
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        return self.capture()

    def assert_prepared(self,path,edits,source=None):
        expected=self.original(edits,source);v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();self.assertEqual(self.capture(),expected)

    def test_units_and_body_model_apply_before_stature_in_both_axis_orders(self):
        self.fixture();before=self.model.read_bytes()
        edits=[('GenderFlag',self.v.FEMALE),('LenUnit',self.v.LEN_CM),('Stature',165.)]
        for ordered in (edits,list(reversed(edits))):
            with self.subTest(order=ordered):
                params=[dict(id=self.ids[n],value=x) for n,x in ordered]
                result,path=self.worker(dict(action='study-model',parameters=params))
                self.assertEqual([p['effective'] for p in result['parameters']],[x for n,x in ordered])
                self.assert_prepared(path,edits)
        schema,_=self.worker(dict(action='study-schema'))
        fields={p['id']:p for p in schema['parameters']}
        self.assertEqual(fields[self.ids['LenUnit']]['choices'][self.v.LEN_CM]['label'],'cm')
        self.assertEqual(fields[self.ids['Stature']]['humanStudy']['limitControllers'],[self.ids['LenUnit']])
        self.assertEqual(self.model.read_bytes(),before)

    def test_left_pose_and_density_unlock_before_values_and_keep_native_guards(self):
        self.fixture();before=self.model.read_bytes()
        for controller,dependent,x in [('RLSym','KneeLt',45.),('AutoDensity','Density',20.)]:
            edits=[(controller,0),(dependent,x)]
            for ordered in (edits,list(reversed(edits))):
                with self.subTest(controller=controller,order=ordered):
                    result,path=self.worker(dict(action='study-model',parameters=[dict(id=self.ids[n],value=value) for n,value in ordered]))
                    self.assert_prepared(path,edits)
            with self.assertRaises(ValueError):self.save([dict(kind='parameter',id=self.ids[dependent],values=[x])])
            with self.assertRaises(ValueError):self.save([dict(kind='parameter',id=self.ids[controller],values=[1]),dict(kind='parameter',id=self.ids[dependent],values=[x])])
        with self.assertRaises(ValueError):self.worker(dict(action='study-model',parameters=[dict(id=self.ids['Stature'],value=165.),dict(id=self.ids['LenUnit'],value=self.v.LEN_IN)]))
        for name in ('Volume','PresetPose'):
            with self.assertRaises(ValueError):self.save([dict(kind='parameter',id=self.ids['RLSym'],values=[0]),dict(kind='parameter',id=self.ids[name],values=[1])])
        self.assertEqual(self.model.read_bytes(),before)

    def test_saved_unit_cases_match_all_native_geometry_and_engineering_results(self):
        self.fixture();v=self.v;before=self.model.read_bytes()
        plan=self.save([dict(kind='parameter',id=self.ids[n],values=xs) for n,xs in [('Stature',[160.,170.]),('LenUnit',[v.LEN_CM]),('GenderFlag',[v.FEMALE])]])
        batch=studies.launch(plan['id']);batch=self.wait(plan['id'],batch['id']);self.assertEqual(batch['status'],'complete',batch)
        for case in batch['cases']:
            source=studies.study_folder(plan['id'])/'aircraft.vsp3';path=studies.batch_folder(plan['id'],batch['id'])/'cases'/str(case['index'])/'aircraft.vsp3'
            self.assert_prepared(path,[('GenderFlag',v.FEMALE),('LenUnit',v.LEN_CM),('Stature',case['values'][0])],source)
            self.original([('GenderFlag',v.FEMALE),('LenUnit',v.LEN_CM),('Stature',case['values'][0])],source)
            v.SetAnalysisInputDefaults('CompGeom');v.ExecAnalysis('CompGeom');native_worker.errors(v)
            expected=native_worker.collect_results(v);actual=service.job_state(case['stages'][0]['job'])['result']['results']
            for r in expected:
                target=next(t for t in actual if t['name']==r['name'] and t['index']==r['index'])
                for e in r['entries']:
                    if e['name']!='Analysis_Duration_Sec' and e['type'] in (v.INT_DATA,v.DOUBLE_DATA,v.VEC3D_DATA,v.DOUBLE_MATRIX_DATA):
                        self.assertEqual(next(t['values'] for t in target['entries'] if t['name']==e['name'] and t['index']==e['index']),e['values'])
        self.assertEqual(self.model.read_bytes(),before)

    def test_mixed_pose_controller_cases_stop_before_analysis_and_preserve_good_cases(self):
        self.fixture();before=self.model.read_bytes()
        plan=self.save([dict(kind='parameter',id=self.ids['KneeLt'],values=[30.,45.]),dict(kind='parameter',id=self.ids['RLSym'],values=[0,1])])
        batch=studies.launch(plan['id']);batch=self.wait(plan['id'],batch['id']);self.assertEqual(batch['status'],'partial',batch)
        self.assertEqual([c['status'] for c in batch['cases']],['complete','failed','complete','failed'])
        for case in batch['cases']:
            if case['values'][1]:
                self.assertIn('Left pose follows',case['error']);self.assertTrue(all(s['status']=='not-run' and not s.get('job') for s in case['stages']))
            else:
                path=studies.batch_folder(plan['id'],batch['id'])/'cases'/str(case['index'])/'aircraft.vsp3'
                self.assert_prepared(path,[('RLSym',0),('KneeLt',case['values'][0])],studies.study_folder(plan['id'])/'aircraft.vsp3')
        self.assertEqual(self.model.read_bytes(),before)

if __name__=='__main__':unittest.main()
