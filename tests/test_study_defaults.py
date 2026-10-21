"""Per-field inheritance fixes a real frozen-input override without math changes."""
import copy,json,unittest
import test_studies
import native_service as service,native_studies as studies,native_managers

class StudyDefaults(unittest.TestCase):
    setUpClass=classmethod(test_studies.NativeStudies.setUpClass.__func__)
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    save=test_studies.NativeStudies.save
    wait=test_studies.NativeStudies.wait

    def fixture(self):
        v=self.v;v.ClearVSPModel();v.AddGeom('POD');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        pid=v.FindParm(native_managers.manager(v,'SurfaceIntersectSettings'),'CADLenUnit','ExportIntersect')
        schema=studies.analysis_schema(None,'SurfaceIntersection');entries=[dict(name=e['name'],index=e['index'],values=copy.deepcopy(e['values'])) for e in schema['inputs']]
        changes=dict(CADLenUnit=v.LEN_FT,SRFFileFlag=0,CURVFileFlag=0,P3DFileFlag=0,IGESFileFlag=0,STEPFileFlag=1,STEPFileName='native.stp',CADLabelName=0)
        for e in entries:
            if e['name'] in changes:e['values']=[changes[e['name']]]
        return pid,dict(name='SurfaceIntersection',freezeInputs=True,inputs=entries)

    def test_frozen_other_settings_remain_explicit_and_units_follow_each_native_case(self):
        v=self.v;pid,stage=self.fixture();before=self.model.read_bytes();axis=[dict(kind='parameter',id=pid,values=[v.LEN_CM,v.LEN_FT])]
        fixed=self.save(axis,[stage]);batch=self.wait(fixed['id'],studies.launch(fixed['id'])['id']);self.assertEqual(batch['status'],'complete')
        for case in batch['cases']:
            job=service.job_state(case['stages'][0]['job']);self.assertIn("CONVERSION_BASED_UNIT('FOOT',",(service.job_folder(job['id'])/'native.stp').read_text())
        followed=copy.deepcopy(stage);followed['followDefaults']=[dict(scope='inputs',name='CADLenUnit',index=0)]
        plan=self.save(axis,[followed]);self.assertTrue(plan['stages'][0]['freezeInputs'])
        self.assertEqual(plan['stages'][0]['inputs'],[e for e in stage['inputs'] if e['name']!='CADLenUnit'])
        result=self.wait(plan['id'],studies.launch(plan['id'])['id']);self.assertEqual(result['status'],'complete')
        for case in result['cases']:
            job=service.job_state(case['stages'][0]['job']);unit=case['values'][0];inputs={e['name']:e['values'] for e in job['result']['inputs']};self.assertEqual(inputs['CADLenUnit'],[unit]);self.assertEqual(inputs['CADLabelName'],[0])
            text=(service.job_folder(job['id'])/'native.stp').read_text();self.assertIn('SI_UNIT(.CENTI.,.METRE.)' if unit==v.LEN_CM else "CONVERSION_BASED_UNIT('FOOT',",text)
        self.assertEqual(self.model.read_bytes(),before)

    def test_invalid_inherited_fields_preserve_saved_definition(self):
        pid,stage=self.fixture();plan=self.save([dict(kind='parameter',id=pid,values=[1,4])],[stage]);folder=studies.study_folder(plan['id']);before=(folder/'definition.json').read_bytes()
        for follows in [[dict(scope='inputs',name='Missing',index=0)],[dict(scope='inputs',name='CADLenUnit',index=0)]*2,[dict(scope='geometryInputs',name='CADLenUnit',index=0)]]:
            invalid=copy.deepcopy(stage);invalid['followDefaults']=follows
            with self.assertRaises(ValueError):self.save(plan['axes'],[invalid],id=plan['id'],definitionVersion=plan['version'],baseline='saved')
            self.assertEqual((folder/'definition.json').read_bytes(),before)
