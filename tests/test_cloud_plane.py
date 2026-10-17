"""Cloud plane inspection preserves original FitPlane and native vector results."""
import unittest
import test_native,native_cloud

class CloudPlane(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    def xyz(self,p):return [p.x(),p.y(),p.z()]
    def fixture(self,points,transformed=False):
        v=self.v;g=v.CreatePtCloudGeomFromPts([v.vec3d(*p) for p in points],'Plane inspection cloud')
        if transformed:
            parent=v.AddGeom('POD');v.SetGeomParent(g,parent);v.SetParmValUpdate(parent,'Z_Rel_Rotation','XForm',31)
            for name,value in [('Trans_Attach_Flag',v.ATTACH_TRANS_COMP),('Rots_Attach_Flag',v.ATTACH_ROT_COMP),('Scale',1.7),('X_Rel_Location',3.1),('Y_Rel_Location',-1.3),('Z_Rel_Rotation',17),('Y_Rel_Rotation',23)]:v.SetParmValUpdate(g,name,'Attach' if 'Attach' in name else 'XForm',value)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);return g
    def check(self,g):
        v=self.v;points=native_cloud.world_points(v,g);center=v.vec3d();normal=v.vec3d();v.FitPlane(v.Vec3dVec(points),center,normal)
        before=self.model.read_bytes();data,path=self.worker(dict(action='query',operation='cloud-fit-plane',geom=g))
        self.assertEqual(data['center'],self.xyz(center));self.assertEqual(data['normal'],self.xyz(normal));self.assertEqual(data['points'],[self.xyz(p) for p in points]);self.assertEqual(data['signedOffsets'],[v.dot(p-center,normal) for p in points])
        self.assertEqual(data['pointCount'],len(points));self.assertEqual(self.model.read_bytes(),before);self.assertEqual(path.read_bytes(),before)
        return data
    def test_planar_reference_has_exact_native_center_normal_and_zero_offsets(self):
        g=self.fixture([(0,0,2),(1,0,2),(0,1,2),(1,1,2)]);data=self.check(g)
        self.assertEqual(data['center'],[.5,.5,2]);self.assertEqual(abs(data['normal'][2]),1);self.assertEqual(data['signedOffsets'],[0]*4);self.assertEqual(data['pointSpread'],'noncollinear')
    def test_transformed_and_noisy_clouds_retain_complete_native_fit_and_offsets(self):
        for transformed in [False,True]:
            with self.subTest(transformed=transformed):self.check(self.fixture([(0,0,1),(1,0,1.1),(0,1,.9),(1,1,1.02),(.3,.7,1.07)],transformed))
    def test_collinear_cloud_preserves_native_normal_and_marks_ambiguity(self):
        data=self.check(self.fixture([(0,0,0),(1,0,0),(2,0,0)]));self.assertEqual(data['pointSpread'],'collinear');self.assertEqual(data['signedOffsets'],[0]*3)
    def test_short_and_noncloud_inputs_reject_without_changing_aircraft(self):
        v=self.v;g=self.fixture([(0,0,0),(1,0,0)])
        for geom,message in [(g,'three'),(self.gid,'point cloud'),('missing','point cloud')]:
            before=self.model.read_bytes();existing=set(self.path.glob('*/aircraft.vsp3'))
            with self.assertRaisesRegex(ValueError,message):self.worker(dict(action='query',operation='cloud-fit-plane',geom=geom))
            candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)
