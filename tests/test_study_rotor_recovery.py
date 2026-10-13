"""Explicit saved-study rotor matching preserves frozen baselines and values."""
import shutil,sys,unittest
import test_studies,native_service as service,native_studies as studies,native_worker
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class StudyRotorRecovery(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    worker=test_studies.NativeStudies.worker
    save=test_studies.NativeStudies.save
    wait=test_studies.NativeStudies.wait

    def fixture(self,disk=False):
        v=self.v;self.prop=v.AddGeom('PROP');v.SetGeomName(self.prop,'Recovery rotor')
        v.SetParmValUpdate(self.prop,'PropMode','Design',v.PROP_DISK if disk else v.PROP_BLADES);v.Update()
        v.WriteVSPFile(str(self.model),v.SET_ALL)
        schema=studies.study_schema()
        p=next(p for p in schema['parameters'] if p.get('rotorBinding',{}).get('field')==('RotorCT' if disk else 'RPM'))
        return self.save([dict(kind='parameter',id=p['id'],values=[.25,.35] if disk else [1350.,1750.])])

    def mode(self,value):
        return service.mutation(dict(operation='parameter',id=self.v.FindParm(self.prop,'PropMode','Design'),value=value,revision=service.REVISION))

    def review(self,plan,**extra):
        return studies.rebind_current_aircraft(dict(id=plan['id'],definitionVersion=plan['version'],axes=plan['axes'],stages=plan['stages'],revision=service.REVISION,**extra))

    def test_recreated_rotating_axis_keeps_values_and_native_cases(self):
        plan=self.fixture();folder=studies.study_folder(plan['id']);original=(folder/'aircraft.vsp3').read_bytes();definition=(folder/'definition.json').read_bytes()
        old_batch=studies.launch(plan['id']);old_batch=self.wait(plan['id'],old_batch['id']);self.assertEqual(old_batch['status'],'complete')
        batch_folder=studies.batch_folder(plan['id'],old_batch['id']);frozen=(batch_folder/'aircraft.vsp3').read_bytes()
        self.mode(self.v.PROP_DISK)
        with self.assertRaisesRegex(ValueError,'same component and native surface'):self.review(plan)
        self.mode(self.v.PROP_BLADES);before=self.model.read_bytes();review=self.review(plan)
        self.assertNotEqual(review['axes'][0]['id'],plan['axes'][0]['id']);self.assertEqual(review['axes'][0]['values'],[1350.,1750.])
        self.assertTrue(review['matches'][0]['changed']);self.assertEqual(self.model.read_bytes(),before)
        self.assertEqual((folder/'aircraft.vsp3').read_bytes(),original);self.assertEqual((folder/'definition.json').read_bytes(),definition)
        next_plan=self.save(review['axes'],review['stages'],id=plan['id'],definitionVersion=plan['version'],baseline='current')
        batch=studies.launch(plan['id']);batch=self.wait(plan['id'],batch['id']);self.assertEqual(batch['status'],'complete',batch)
        for case in batch['cases']:
            self.assertEqual(case['prepared']['parameters'][0]['effective'],case['values'][0])
            self.assertEqual(case['prepared']['parameters'][0]['id'],next_plan['axes'][0]['id'])
            v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(folder/'aircraft.vsp3'));v.Update()
            v.SetParmValUpdate(next_plan['axes'][0]['id'],case['values'][0]);v.SetAnalysisInputDefaults('CompGeom');v.ExecAnalysis('CompGeom')
            expected=native_worker.collect_results(v);actual=service.job_state(case['stages'][0]['job'])['result']['results']
            for result in expected:
                target=next(r for r in actual if r['name']==result['name'] and r['index']==result['index'])
                for e in result['entries']:
                    if e['name']!='Analysis_Duration_Sec' and e['type'] in (v.INT_DATA,v.DOUBLE_DATA,v.VEC3D_DATA,v.DOUBLE_MATRIX_DATA):
                        self.assertEqual(next(x['values'] for x in target['entries'] if x['name']==e['name'] and x['index']==e['index']),e['values'])
        self.assertEqual((batch_folder/'aircraft.vsp3').read_bytes(),frozen);self.assertEqual(self.model.read_bytes(),before)

    def test_disk_recovery_rejects_new_calculated_field_and_stale_review(self):
        plan=self.fixture(disk=True);self.mode(self.v.PROP_BLADES);self.mode(self.v.PROP_DISK)
        state=service.state();cid=state['tools']['disks'][0]['id']
        service.mutation(dict(operation='rotor-disk-drivers',id=cid,choices=[0,3,6],revision=service.REVISION))
        before=self.model.read_bytes();folder=studies.study_folder(plan['id']);saved=(folder/'definition.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'editable current driver'):self.review(plan)
        self.assertEqual(self.model.read_bytes(),before);self.assertEqual((folder/'definition.json').read_bytes(),saved)
        with self.assertRaisesRegex(ValueError,'changed in another window'):
            studies.rebind_current_aircraft(dict(id=plan['id'],definitionVersion=plan['version'],revision='old'))

    def test_same_name_replacement_is_not_the_original_rotor(self):
        plan=self.fixture();v=self.v
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();v.DeleteGeom(self.prop)
        replacement=v.AddGeom('PROP');v.SetGeomName(replacement,'Recovery rotor')
        v.SetParmValUpdate(replacement,'PropMode','Design',v.PROP_BLADES);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'same component and native surface'):self.review(plan)
        self.assertEqual(self.model.read_bytes(),before)

if __name__=='__main__':unittest.main()
