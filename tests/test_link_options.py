"""Native link flags update immediately and persist without local equations."""
import sys,unittest
import test_native

OPTIONS=('Scale','Offset','LowerLimit','UpperLimit')

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class LinkOptions(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self,value=5.):
        v=self.v;v.ClearVSPModel();self.a=v.AddGeom('POD');self.b=v.AddGeom('POD');self.source=v.FindParm(self.a,'Length','Design');self.target=v.FindParm(self.b,'Length','Design');v.SetParmValUpdate(self.source,value)
        self.lid=v.AddParmLink(self.source,self.target)
        v.SetParmLinkScaleFlag(self.lid,True);v.SetParmLinkOffsetFlag(self.lid,True)
        for key,x in [('Scale',2.),('Offset',1.),('LowerLimit',8.),('UpperLimit',10.)]:v.SetParmValUpdate(v.FindParm(self.lid,key,'Link'),x)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)

    def geometry(self):
        v=self.v;out=[]
        for i in range(v.GetTotalNumSurfs(self.b)):
            u,w=v.GetUWTess01(self.b,i%v.GetNumMainSurfs(self.b));out.append([[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(self.b,i,[x for x in u for _ in w],[y for _ in u for y in w])])
        return out

    def test_all_switches_match_original_evaluation_and_cold_geometry(self):
        cases=[({'Scale':False},5.),({'Offset':False},5.),({'LowerLimit':True},2.),({'UpperLimit':True},5.),(dict.fromkeys(OPTIONS,False),5.),(dict.fromkeys(OPTIONS,True),5.),(dict(Scale=False,Offset=False,LowerLimit=True,UpperLimit=True),12.)]
        for changes,value in cases:
            with self.subTest(changes=changes,value=value):
                self.fixture(value);v=self.v;before=self.model.read_bytes()
                # Independent original SDK reference: a real source edit makes
                # the original manager evaluate the configured relationship.
                v.SetParmValUpdate(self.source,value-1.)
                for key,on in changes.items():getattr(v,'SetParmLink'+key+'Flag')(self.lid,on)
                v.SetParmValUpdate(self.source,value);v.Update()
                expected_flags={key:bool(getattr(v,'GetParmLink'+key+'Flag')(self.lid)) for key in OPTIONS};expected_value=v.GetParmVal(self.target);expected_geometry=self.geometry()
                state,path=self.worker(dict(action='mutate',operation='link-options',id=self.lid,flags=changes))
                link=next(l for l in state['tools']['links'] if l['id']==self.lid);target=next(c for c in state['components'] if c['id']==self.b)
                self.assertEqual(link['flags'],expected_flags);self.assertEqual(next(p['value'] for p in target['params'] if p['id']==self.target),expected_value)
                self.assertEqual([s['points'] for s in target['surfaces']],expected_geometry)
                self.assertEqual(next(p['value'] for c in state['components'] if c['id']==self.a for p in c['params'] if p['id']==self.source),value)
                cold,_=self.worker(dict(action='state'),path);self.assertEqual(next(l for l in cold['tools']['links'] if l['id']==self.lid)['flags'],expected_flags)
                v.SetParmValUpdate(self.source,6.);v.Update();expected_value=v.GetParmVal(self.target);expected_geometry=self.geometry()
                changed,_=self.worker(dict(action='mutate',operation='parameter',id=self.source,value=6.),path);target=next(c for c in changed['components'] if c['id']==self.b)
                self.assertEqual(next(p['value'] for p in target['params'] if p['id']==self.target),expected_value);self.assertEqual([s['points'] for s in target['surfaces']],expected_geometry)
                self.assertEqual(self.model.read_bytes(),before)

    def test_locked_target_rejects_switch_and_preserves_original_flags(self):
        self.fixture();state,path=self.worker(dict(action='mutate',operation='property-lock',parameters=[self.target],locked=True));before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'locked'):self.worker(dict(action='mutate',operation='link-options',id=self.lid,flags={'Offset':False}),path)
        cold,_=self.worker(dict(action='state'),path);self.assertTrue(cold['tools']['links'][0]['flags']['Offset']);self.assertEqual(path.read_bytes(),before)

    def test_invalid_switch_requests_preserve_model(self):
        self.fixture();before=self.model.read_bytes()
        for flags in [{},{'Scale':1},{'Other':True},{'Scale':False,'Offset':'no'},[]]:
            with self.subTest(flags=flags),self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='link-options',id=self.lid,flags=flags))
        with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='link-options',id='missing',flags={'Scale':False}))
        self.assertEqual(self.model.read_bytes(),before)
