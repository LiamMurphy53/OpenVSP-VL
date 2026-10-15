"""Native Accept/Reset scale actions preserve official geometry and transactions."""
import unittest
import test_native

class ScaleActions(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    def fixture(self,kind):
        v=self.v;v.ClearVSPModel()
        if kind=='PTCLOUD':g=v.CreatePtCloudGeomFromPts([v.vec3d(0,0,0),v.vec3d(1,2,3),v.vec3d(-1,.3,2)],'Scaled cloud')
        elif kind=='WIREFRAME':
            from test_wire_geometry import plot3d
            file=self.path/'wire.p3d';file.write_bytes(plot3d());v.ImportFile(str(file),v.IMPORT_P3D_WIRE,'');g=v.FindGeoms()[0]
        else:g=v.AddGeom(kind)
        v.SetParmValUpdate(g,'Scale','XForm',2);v.SetParmValUpdate(g,'Z_Rel_Rotation','XForm',17);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);return g
    def geometry(self,state):
        return {c['id']:{key:c.get(key) for key in ['surfaces','mesh','paths','points']} for c in state['components']}
    def test_actions_match_original_sdk_across_native_geometry_and_reopening(self):
        import native_cloud
        v=self.v
        for kind in ['POD','WING','STACK','PTCLOUD','WIREFRAME']:
            for action in ['accept','reset']:
                with self.subTest(kind=kind,action=action):
                    g=self.fixture(kind)
                    # Match the actual load/update lifecycle before the independent SDK action.
                    v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();native_cloud.refresh(v)
                    (v.AcceptGeomScale if action=='accept' else v.ResetGeomScale)(g);v.Update()
                    reference=self.path/'reference.vsp3';v.WriteVSPFile(str(reference),v.SET_ALL)
                    expected,_=self.worker(dict(action='state'),reference)
                    state,path=self.worker(dict(action='mutate',operation='scale-'+action,geom=g));cold,_=self.worker(dict(action='state'),path)
                    self.assertEqual(self.geometry(cold),self.geometry(expected))
                    for result in [state,cold]:
                        c=next(c for c in result['components'] if c['id']==g);self.assertEqual(next(p['value'] for p in c['params'] if p['name']=='Scale' and p['rawGroup']=='XForm'),1)
                    actual={p['id']:p['value'] for c in cold['components'] for p in c['params']}
                    self.assertEqual(actual,{p['id']:p['value'] for c in expected['components'] for p in c['params']})
    def test_reset_after_accept_uses_the_accepted_size(self):
        v=self.v;g=self.fixture('POD')
        accepted,path=self.worker(dict(action='mutate',operation='scale-accept',geom=g))
        scale=next(p['id'] for p in accepted['components'][0]['params'] if p['name']=='Scale' and p['rawGroup']=='XForm')
        resized,path=self.worker(dict(action='mutate',operation='parameter',id=scale,value=1.5),path)
        reset,path=self.worker(dict(action='mutate',operation='scale-reset',geom=g),path)
        self.assertEqual(self.geometry(reset),self.geometry(accepted));self.assertNotEqual(self.geometry(resized),self.geometry(accepted))
    def test_locked_scale_and_dimensions_reject_without_changing_candidate(self):
        v=self.v;g=self.fixture('POD')
        for action,name,group in [('accept','Scale','XForm'),('reset','Length','Design')]:
            pid=v.FindParm(g,name,group);_,path=self.worker(dict(action='mutate',operation='property-lock',parameters=[pid],locked=True))
            before=path.read_bytes();existing=set(self.path.glob('*/aircraft.vsp3'))
            with self.assertRaisesRegex(ValueError,'locked'):self.worker(dict(action='mutate',operation='scale-'+action,geom=g),path)
            candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before);self.assertEqual(path.read_bytes(),before)
    def test_missing_component_rejects_without_changing_candidate(self):
        before=self.model.read_bytes();existing=set(self.path.glob('*/aircraft.vsp3'))
        with self.assertRaisesRegex(ValueError,'component'):self.worker(dict(action='mutate',operation='scale-reset',geom='missing'))
        candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before)
