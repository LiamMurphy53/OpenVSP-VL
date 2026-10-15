"""Only the native Scale driver is editable; bookkeeping must remain calculated."""
import unittest
import test_native

class ScaleControls(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    def fixture(self):
        v=self.v;g=v.CreatePtCloudGeomFromPts([v.vec3d(0,0,0),v.vec3d(1,2,3)],'Scale test cloud');v.SetParmValUpdate(g,'Scale','XForm',2);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return g,[v.FindParm(g,n,'XForm') for n in ['Last_Scale','Scale_From_Original']]
    def test_bookkeeping_rejected_atomically_by_direct_edits(self):
        g,ids=self.fixture();ids.append(self.v.FindParm(self.gid,'Last_Scale','XForm'))
        for pid in ids:
            with self.subTest(parameter=self.v.GetParmName(pid)):
                before=self.model.read_bytes();existing=set(self.path.glob('*/aircraft.vsp3'))
                with self.assertRaisesRegex(ValueError,'Scale'):self.worker(dict(action='mutate',operation='parameter',id=pid,value=1.7))
                candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)
    def test_properties_studies_and_fitting_agree_on_calculated_values(self):
        g,ids=self.fixture();state,_=self.worker(dict(action='state'));fields={p['id']:p for c in state['components'] for p in c['params']}
        schema,_=self.worker(dict(action='study-schema'));study={p['id']:p for p in schema['parameters']}
        for pid in ids:
            self.assertTrue(fields[pid].get('displayReadOnly'));self.assertFalse(study[pid]['editable'])
            with self.assertRaisesRegex(ValueError,'Scale'):self.worker(dict(action='mutate',operation='fit-variables',parameters=[pid]))
    def test_stale_study_cases_cannot_assign_scale_bookkeeping(self):
        from native_study_worker import prepare
        from native_worker import errors
        g,ids=self.fixture()
        for pid in ids:
            candidate=self.path/'invalid-study.vsp3'
            with self.assertRaisesRegex(ValueError,'Scale'):prepare(self.v,dict(parameters=[dict(id=pid,value=1.7)]),candidate,errors)
            self.assertFalse(candidate.exists())
    def test_scale_driver_matches_original_native_cloud_points_and_reopening(self):
        import native_cloud
        v=self.v;g,_=self.fixture();scale=v.FindParm(g,'Scale','XForm');v.SetParmValUpdate(scale,3.1);v.Update()
        expected=[[p.x(),p.y(),p.z()] for p in native_cloud.world_points(v,g)]
        state,path=self.worker(dict(action='mutate',operation='parameter',id=scale,value=3.1))
        for data in [state,self.worker(dict(action='state'),path)[0]]:
            c=next(c for c in data['components'] if c['id']==g);self.assertEqual(c['points'],expected)
            self.assertFalse(next(p for p in c['params'] if p['id']==scale).get('displayReadOnly',False))
    def test_user_parameters_with_matching_names_remain_editable(self):
        v=self.v;pid=v.AddUserParm(v.PARM_DOUBLE_TYPE,'Last_Scale','XForm');v.SetParmValUpdate(pid,1.2);v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=1.7))
        p=next(p for p in state['tools']['userParameters'] if p['id']==pid);self.assertEqual(p['value'],1.7);self.assertFalse(p.get('displayReadOnly',False))
        schema,_=self.worker(dict(action='study-schema'),path);self.assertIsNot(next(p for p in schema['parameters'] if p['id']==pid).get('editable'),False)
