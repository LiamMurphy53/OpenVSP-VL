"""Cloud filtering calls native selectors and preserves original local points."""
import unittest
import test_native
import native_cloud

class CloudFilters(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    def fixture(self):
        v=self.v;target=v.AddGeom('POD');points=[[-1,-2,-3],[0,0,0],[.1,.2,.3],[1,2,3],[2,-1,.5],[4,2,-2]]
        g=v.CreatePtCloudGeomFromPts([v.vec3d(*p) for p in points],'Native filter cloud');v.SetGeomParent(g,target)
        for name,value in [('Scale',1.7),('X_Rel_Location',1.3),('Y_Rel_Location',-.2),('Z_Rel_Rotation',23),('Y_Rel_Rotation',17),('Trans_Attach_Flag',v.ATTACH_TRANS_COMP),('Rots_Attach_Flag',v.ATTACH_ROT_COMP)]:v.SetParmValUpdate(g,name,'Attach' if 'Attach' in name else 'XForm',value)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);return g,target
    def xyz(self,points):return [[p.x(),p.y(),p.z()] for p in points]
    def test_all_ten_filters_match_original_native_selection_with_transforms_and_reload(self):
        v=self.v;g,target=self.fixture();local=list(v.GetPtCloudPnts(g));world=native_cloud.world_points(v,g);origin=world[1]
        cases=[('KeepPtsInBBox',dict(minimum=[-1,-1,-1],maximum=[4,4,4]),[v.vec3d(-1,-1,-1),v.vec3d(4,4,4)]),('RemovePtsInBBox',dict(minimum=[-1,-1,-1],maximum=[4,4,4]),[v.vec3d(-1,-1,-1),v.vec3d(4,4,4)]),('KeepPtsInRange',dict(axis=v.X_DIR,low=0,high=4),[v.X_DIR,0,4]),('RemovePtsInRange',dict(axis=v.X_DIR,low=0,high=4),[v.X_DIR,0,4]),('KeepPtsAbove',dict(axis=v.Y_DIR,value=0),[v.Y_DIR,0]),('KeepPtsBelow',dict(axis=v.Z_DIR,value=0),[v.Z_DIR,0]),('KeepPtsNearPt',dict(center=self.xyz([origin])[0],radius=3),[origin,3]),('RemovePtsNearPt',dict(center=self.xyz([origin])[0],radius=3),[origin,3]),('KeepPtsNearGeom',dict(target=target,surface=0,tolerance=.5),[target,0,.5]),('RemovePtsNearGeom',dict(target=target,surface=0,tolerance=.5),[target,0,.5])]
        before=self.model.read_bytes();index={(p.x(),p.y(),p.z()):i for i,p in enumerate(world)}
        for method,request,args in cases:
            with self.subTest(method=method):
                kept=list(getattr(v,method)(world,*args));expected=[self.xyz([local[index[(p.x(),p.y(),p.z())]]])[0] for p in kept]
                state,path=self.worker(dict(action='mutate',operation='point-cloud-filter',geom=g,method=method,**request));cold,_=self.worker(dict(action='state'),path)
                for result in [state,cold]:
                    cloud=next(c for c in result['tools']['pointClouds'] if c['id']==g);self.assertEqual(cloud['points'],expected)
                    self.assertEqual(cloud['worldPoints'],self.xyz(kept));c=next(c for c in result['components'] if c['id']==g);self.assertEqual(c['parent'],target)
                self.assertEqual(self.model.read_bytes(),before);self.assertFalse(list(path.parent.glob('.native-rollback-*.vsp3')))
    def test_empty_results_preserve_component_identity_and_transform(self):
        v=self.v;g,target=self.fixture();state,path=self.worker(dict(action='mutate',operation='point-cloud-filter',geom=g,method='KeepPtsAbove',axis=v.X_DIR,value=1e6))
        for data in [state,self.worker(dict(action='state'),path)[0]]:
            c=next(c for c in data['components'] if c['id']==g);self.assertEqual(c['points'],[]);self.assertEqual(c['parent'],target)
            self.assertEqual(next(p['value'] for p in c['params'] if p['name']=='Scale_From_Original'),1.7)
    def test_invalid_filters_preserve_original_and_candidate(self):
        v=self.v;g,target=self.fixture();cases=[dict(method='bad'),dict(method='KeepPtsInBBox',minimum=[1,0,0],maximum=[0,1,1]),dict(method='KeepPtsInRange',axis=0,low=2,high=1),dict(method='KeepPtsAbove',axis=99,value=0),dict(method='KeepPtsAbove',axis=True,value=0),dict(method='KeepPtsNearPt',center=[0,0,0],radius=-1),dict(method='KeepPtsNearGeom',target=target,surface=99,tolerance=.1),dict(method='KeepPtsNearGeom',target='missing',surface=0,tolerance=.1)]
        for request in cases:
            before=self.model.read_bytes();existing=set(self.path.glob('*/aircraft.vsp3'))
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='point-cloud-filter',geom=g,**request))
            candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)
    def test_locked_bounds_reject_filter_without_saving(self):
        v=self.v;g,target=self.fixture();pid=v.FindParm(g,'X_Len','BBox');_,path=self.worker(dict(action='mutate',operation='property-lock',parameters=[pid],locked=True));before=path.read_bytes();existing=set(self.path.glob('*/aircraft.vsp3'))
        with self.assertRaisesRegex(ValueError,'locked'):self.worker(dict(action='mutate',operation='point-cloud-filter',geom=g,method='KeepPtsAbove',axis=v.X_DIR,value=1e6),path)
        candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before);self.assertEqual(path.read_bytes(),before);self.assertFalse(list(candidate.parent.glob('.native-rollback-*.vsp3')))
    def test_surface_filter_uses_selected_mirrored_surface(self):
        v=self.v;target=self.gid;v.Update();points=[v.CompPnt01(target,i,.5,.25) for i in [0,1]];g=v.CreatePtCloudGeomFromPts(points,'Mirrored surface filter');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        expected=self.xyz(v.KeepPtsNearGeom(points,target,1,.01));self.assertEqual(len(expected),1)
        state,path=self.worker(dict(action='mutate',operation='point-cloud-filter',geom=g,method='KeepPtsNearGeom',target=target,surface=1,tolerance=.01))
        self.assertEqual(next(c['worldPoints'] for c in state['tools']['pointClouds'] if c['id']==g),expected)
        cold,_=self.worker(dict(action='state'),path);self.assertEqual(next(c['worldPoints'] for c in cold['tools']['pointClouds'] if c['id']==g),expected)
