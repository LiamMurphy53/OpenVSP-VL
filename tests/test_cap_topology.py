"""Native cap-result slots may differ from split main surface counts."""
import sys,unittest
import test_native

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class CapTopology(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_flowthrough_stack_preset_matches_original_geometry_and_reopens(self):
        v=self.v;gid=v.AddGeom('STACK');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        v.InitStackPreset(gid,v.STACK_PRESET_FLOWTHRU_MID_ORIG);v.Update()
        def points():
            out=[]
            for i in range(v.GetTotalNumSurfs(gid)):
                u,w=v.GetUWTess01(gid,i%v.GetNumMainSurfs(gid));out.append([[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(gid,i,[x for x in u for _ in w],[y for _ in u for y in w])])
            return out
        expected=points();self.assertEqual(len(expected),2)
        state,path=self.worker(dict(action='mutate',operation='stack-preset',geom=gid,preset='STACK_PRESET_FLOWTHRU_MID_ORIG'))
        for request in [None,dict(action='state')]:
            if request:state,_=self.worker(request,path)
            c=next(c for c in state['components'] if c['id']==gid)
            self.assertEqual([s['points'] for s in c['surfaces']],expected);self.assertEqual(len(c['sections']),7)
            self.assertEqual(c['mainSurfaceCount'],2)
            self.assertEqual([x['results'] for x in c['endCaps']['ends']],[[False],[False]])
            self.assertEqual([len(x['results']) for x in c['endCaps']['ends']],[1,1])
        for name in ('CapUMinOption','CapUMaxOption'):v.SetParmVal(gid,name,'EndCap',v.FLAT_END_CAP)
        v.Update();capped=points()
        for name in ('CapUMinOption','CapUMaxOption'):
            state,path=self.worker(dict(action='mutate',operation='parameter',id=v.FindParm(gid,name,'EndCap'),value=v.FLAT_END_CAP),path)
        cold,_=self.worker(dict(action='state'),path);component=next(c for c in cold['components'] if c['id']==gid)
        self.assertEqual([s['points'] for s in component['surfaces']],capped)
        self.assertEqual([x['results'] for x in component['endCaps']['ends']],[[True],[True]])
        self.assertEqual(self.model.read_bytes(),before)
