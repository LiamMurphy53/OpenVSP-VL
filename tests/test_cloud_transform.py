"""Point-cloud world coordinates match independent native drawing points exactly."""
import ctypes,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import test_native
from vsp_runtime import ROOT,distribution,load
import native_cloud

class CloudTransform(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v=load();cls.reference_dir=tempfile.TemporaryDirectory(prefix='openvsp-cloud-reference-')
        library=Path(cls.reference_dir.name)/'reference.dylib'
        subprocess.run(['/usr/bin/clang++','-std=c++17','-O2','-dynamiclib','-I',str(ROOT/'native_bridge/vendor/openvsp-3.52.2'),str(ROOT/'tests/cloud_native_reference.cpp'),'-o',str(library)],capture_output=True,check=True)
        cls.library=ctypes.CDLL(str(library));cls.reference=cls.library.native_cloud_reference
        cls.reference.argtypes=[ctypes.c_char_p,ctypes.c_char_p];cls.reference.restype=ctypes.c_char_p
    @classmethod
    def tearDownClass(cls):cls.reference_dir.cleanup()
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    def assert_points(self,actual,expected):
        self.assertEqual(len(actual),len(expected))
        for i,(a,b) in enumerate(zip(actual,expected)):self.assertEqual(a,b,'Native point '+str(i))
    def native_points(self,g):
        result=json.loads(self.reference(str(distribution()/'python/openvsp/openvsp/_vsp.so').encode(),g.encode()))
        self.assertIsInstance(result,list);return result
    def fixture(self,large=False):
        v=self.v;parent=v.AddGeom('POD');cloud=v.CreatePtCloudGeomFromPts([v.vec3d(i*.013,(i%17)*.029,(i%11)*.041) for i in range(10000 if large else 31)],'Native drawing cloud');v.SetGeomParent(cloud,parent)
        for g,values in [(parent,{'X_Rel_Location':7.37,'Y_Rel_Location':-2.14,'X_Rel_Rotation':19.31,'Y_Rel_Rotation':31.17,'Z_Rel_Rotation':-42.73}),(cloud,{'Trans_Attach_Flag':v.ATTACH_TRANS_COMP,'Rots_Attach_Flag':v.ATTACH_ROT_COMP,'X_Rel_Location':3.13,'Y_Rel_Location':-1.27,'Z_Rel_Location':2.61,'X_Rel_Rotation':7.11,'Y_Rel_Rotation':19.17,'Z_Rel_Rotation':31.13,'Scale':2.37})]:
            for name,value in values.items():v.SetParmValUpdate(g,name,'Attach' if 'Attach' in name else 'XForm',value)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);return cloud
    def test_every_world_point_matches_original_drawings_without_temporary_geometry(self):
        v=self.v;g=self.fixture();expected=self.native_points(g);ids=list(v.FindGeoms());before=self.model.read_bytes()
        with patch.object(v,'AddGeom',side_effect=AssertionError('Point transforms must not create geometry')):
            actual=[[p.x(),p.y(),p.z()] for p in native_cloud.world_points(v,g)]
        self.assertEqual(actual,expected);self.assertEqual(list(v.FindGeoms()),ids);self.assertEqual(self.model.read_bytes(),before)
        state,path=self.worker(dict(action='state'));self.assert_points(next(c for c in state['components'] if c['id']==g)['points'],expected);self.assertEqual(path.read_bytes(),before)
    def test_large_cloud_keeps_every_original_native_point(self):
        g=self.fixture(large=True);expected=self.native_points(g);self.assertEqual(len(expected),10000)
        state,path=self.worker(dict(action='state'));self.assert_points(next(c for c in state['components'] if c['id']==g)['points'],expected)
    def test_wrong_component_rejected_before_native_cloud_call(self):
        with self.assertRaisesRegex(ValueError,'native point cloud'):native_cloud.transform_points(self.v,self.gid,[self.v.vec3d(0,0,0)])

    def test_transformed_projection_matches_original_native_operation(self):
        v=self.v;pod=v.AddGeom('POD');g=v.CreatePtCloudGeomFromPts([v.vec3d(x,.02,1) for x in [1,2,3]],'Transformed projection')
        for name,value in [('Scale',1.3),('X_Rel_Location',1.1),('Y_Rel_Rotation',7.3)]:v.SetParmValUpdate(g,name,'XForm',value)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        for point in native_cloud.world_points(v,g):self.assertGreaterEqual(v.AxisProjPnt01(pod,0,v.Z_DIR,point)[0],0)
        v.ProjectPtCloudPts(g,pod,0,v.Z_DIR);v.Update();expected=[[p.x(),p.y(),p.z()] for p in v.GetPtCloudPnts(g)]
        state,path=self.worker(dict(action='mutate',operation='point-cloud-project',geom=g,target=pod,surface=0,direction=v.Z_DIR))
        actual=next(c for c in state['tools']['pointClouds'] if c['id']==g)['points'];self.assert_points(actual,expected)
        cold,_=self.worker(dict(action='state'),path);self.assert_points(next(c for c in cold['tools']['pointClouds'] if c['id']==g)['points'],expected)
    def test_scale_refresh_preserves_all_saved_parameters_and_is_idempotent(self):
        v=self.v;g=self.fixture();expected=self.native_points(g)
        before={p:v.GetParmVal(p) for geom in v.FindGeoms() for p in v.GetGeomParmIDs(geom)};filename=v.GetVSPFileName()
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        for _ in range(2):
            native_cloud.refresh(v);self.assert_points(self.native_points(g),expected)
            self.assertEqual({p:v.GetParmVal(p) for geom in v.FindGeoms() for p in v.GetGeomParmIDs(geom)},before)
            self.assertEqual(v.GetVSPFileName(),filename)
