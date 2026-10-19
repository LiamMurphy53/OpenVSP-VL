"""Saved link endpoint edits use the original manager and preserve link identity."""
import unittest
import test_link_options
OPTIONS=test_link_options.OPTIONS

class LinkEndpoints(unittest.TestCase):
    setUpClass=test_link_options.LinkOptions.__dict__['setUpClass']
    setUp=test_link_options.LinkOptions.setUp
    tearDown=test_link_options.LinkOptions.tearDown
    worker=test_link_options.LinkOptions.worker
    geometry=test_link_options.LinkOptions.geometry
    def fixture(self,value=5.):
        test_link_options.LinkOptions.fixture(self,value)
        v=self.v;self.c=v.AddGeom('POD');self.d=v.AddGeom('POD')
        self.pc=v.FindParm(self.c,'Length','Design');self.pd=v.FindParm(self.d,'Length','Design')
        v.SetParmValUpdate(self.pc,7.);v.SetParmValUpdate(self.pd,3.);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)

    def test_rewire_matches_original_and_future_edits(self):
        for mode in ['source','target','both','swap']:
            with self.subTest(mode=mode):
                self.fixture();v=self.v
                a,b={'source':(self.pc,self.target),'target':(self.source,self.pd),'both':(self.pc,self.pd),'swap':(self.target,self.source)}[mode]
                before=self.model.read_bytes();value=v.GetParmVal(a)
                v.SetParmLinkAParm(self.lid,a);v.SetParmLinkBParm(self.lid,b)
                v.SetParmValUpdate(a,value-1.);v.SetParmValUpdate(a,value);v.Update()
                expected={p:v.GetParmVal(p) for p in [self.source,self.target,self.pc,self.pd]}
                original_b=self.b;self.b=v.GetParmContainer(b);geometry=self.geometry();self.b=original_b
                settings={k:v.GetParmVal(v.FindParm(self.lid,k,'Link')) for k in OPTIONS};flags={k:bool(getattr(v,'GetParmLink'+k+'Flag')(self.lid)) for k in OPTIONS}
                state,path=self.worker(dict(action='mutate',operation='link-endpoints',id=self.lid,source=a,target=b))
                link=next(l for l in state['tools']['links'] if l['id']==self.lid)
                self.assertEqual((link['source'],link['target']),(a,b));self.assertEqual(link['flags'],flags)
                self.assertEqual({p['name']:p['value'] for p in link['params'] if p['name'] in OPTIONS},settings)
                for component in state['components']:
                    for p in component['params']:
                        if p['id'] in expected:self.assertEqual(p['value'],expected[p['id']])
                    if component['id']==v.GetParmContainer(b):self.assertEqual([s['points'] for s in component['surfaces']],geometry)
                cold,_=self.worker(dict(action='state'),path);self.assertEqual(next(l for l in cold['tools']['links'] if l['id']==self.lid)['source'],a)
                self.assertEqual([c['surfaces'] for c in cold['components']],[c['surfaces'] for c in state['components']])
                changed,_=self.worker(dict(action='mutate',operation='parameter',id=a,value=6.),path)
                self.assertEqual(next(p['value'] for c in changed['components'] for p in c['params'] if p['id']==b),13.)
                self.assertEqual(self.model.read_bytes(),before)

    def test_expression_driver_and_cycle_rejections(self):
        for source,target in [('pc','pd'),('pd','pc')]:
            self.fixture()
            _,path=self.worker(dict(action='mutate',operation='advanced-link-save',name='Existing expression',inputs=[dict(name='a',parameter=self.pc)],outputs=[dict(name='b',parameter=self.pd)],code='b = a;'))
            before=path.read_bytes()
            with self.assertRaisesRegex(ValueError,'driver|cycle'):self.worker(dict(action='mutate',operation='link-endpoints',id=self.lid,source=getattr(self,source),target=getattr(self,target)),path)
            self.assertEqual(path.read_bytes(),before)

    def test_invalid_endpoints_and_locked_target(self):
        self.fixture();v=self.v;v.AddParmLink(self.pc,self.pd);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        for a,b in [(self.pc,self.pd),(self.source,self.source),(self.pd,self.pc),('missing',self.target)]:
            with self.subTest(source=a,target=b),self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='link-endpoints',id=self.lid,source=a,target=b))
        self.assertEqual(self.model.read_bytes(),before)
        _,path=self.worker(dict(action='mutate',operation='property-lock',parameters=[self.target],locked=True));before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'locked'):self.worker(dict(action='mutate',operation='link-endpoints',id=self.lid,source=self.pc,target=self.target),path)
        self.assertEqual(path.read_bytes(),before)

if __name__=='__main__':unittest.main()
