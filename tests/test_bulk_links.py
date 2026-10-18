"""Compare bulk relationships to original native matching and evaluation."""
import sys,unittest
import test_native

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class BulkLinks(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self,kind='POD'):
        v=self.v;self.a=v.AddGeom(kind);self.b=v.AddGeom(kind)
        name,group=('TotalSpan','WingGeom') if kind=='WING' else ('Length','Design');self.pa=v.FindParm(self.a,name,group);self.pb=v.FindParm(self.b,name,group)
        v.SetParmVal(self.pa,5.);v.SetParmValUpdate(self.pb,2.);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)

    def links(self,state):
        return sorted((x['source'],x['target'],sorted((p['name'],p['value']) for p in x['params'])) for x in state['tools']['links'])

    def test_group_and_component_match_original_links_and_geometry(self):
        for kind,scope in [('POD','group'),('POD','component'),('WING','group'),('WING','component')]:
            with self.subTest(kind=kind,scope=scope):
                v=self.v;v.ClearVSPModel();self.fixture(kind)
                self.assertTrue((v.LinkAllGroup if scope=='group' else v.LinkAllComp)(self.pa,self.pb));expected=[]
                for i in range(v.GetNumParmLinks()):
                    lid=v.GetParmLinkID(i);expected.append((v.GetParmLinkAParm(lid),v.GetParmLinkBParm(lid),sorted((v.GetParmName(p),v.GetParmVal(p)) for p in v.FindContainerParmIDs(lid))))
                expected.sort();self.assertGreater(len(expected),1);v.SetParmValUpdate(self.pa,7.);expected_length=v.GetParmVal(self.pb);surfaces=[]
                for i in range(v.GetTotalNumSurfs(self.b)):
                    u,w=v.GetUWTess01(self.b,i%v.GetNumMainSurfs(self.b));surfaces.append([[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(self.b,i,[x for x in u for _ in w],[y for _ in u for y in w])])
                state,path=self.worker(dict(action='mutate',operation='link-bulk',source=self.pa,target=self.pb,scope=scope));self.assertEqual(self.links(state),expected)
                state,path=self.worker(dict(action='mutate',operation='parameter',id=self.pa,value=7.),path);target=next(c for c in state['components'] if c['id']==self.b)
                self.assertEqual(next(p['value'] for p in target['params'] if p['id']==self.pb),expected_length);self.assertEqual([s['points'] for s in target['surfaces']],surfaces)
                before=path.read_bytes();cold,_=self.worker(dict(action='state'),path);self.assertEqual(self.links(cold),expected);self.assertEqual(next(c for c in cold['components'] if c['id']==self.b)['surfaces'],target['surfaces'])
                with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='link-bulk',source=self.pa,target=self.pb,scope=scope),path)
                self.assertEqual(path.read_bytes(),before)

    def test_native_offsets_preserve_locked_target_then_reject_conflicting_edit(self):
        self.fixture();state,path=self.worker(dict(action='mutate',operation='property-lock',parameters=[self.pb],locked=True))
        state,path=self.worker(dict(action='mutate',operation='link-bulk',source=self.pa,target=self.pb,scope='group'),path)
        before=path.read_bytes();links=self.links(state);self.assertEqual(len(links),2)
        with self.assertRaisesRegex(ValueError,'locked'):self.worker(dict(action='mutate',operation='parameter',id=self.pa,value=7.),path)
        cold,_=self.worker(dict(action='state'),path);self.assertEqual(self.links(cold),links);self.assertEqual(path.read_bytes(),before)

    def test_invalid_scope_missing_or_identical_parameters_preserve_file(self):
        self.fixture();before=self.model.read_bytes()
        for fields in [dict(scope='bad'),dict(source='missing'),dict(target=self.pa)]:
            with self.subTest(fields=fields),self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='link-bulk',**(dict(source=self.pa,target=self.pb,scope='group')|fields)))
        self.assertEqual(self.model.read_bytes(),before)

    def test_existing_expression_drivers_and_cycles_cannot_be_saved(self):
        for reverse in (False,True):
            with self.subTest(reverse=reverse):
                self.v.ClearVSPModel();self.fixture()
                a,b=(self.pb,self.pa) if reverse else (self.pa,self.pb)
                state,path=self.worker(dict(action='mutate',operation='advanced-link-save',name='Existing expression',inputs=[dict(name='a',parameter=a)],outputs=[dict(name='b',parameter=b)],code='b = a;'))
                before=path.read_bytes()
                try:state,_=self.worker(dict(action='mutate',operation='link-bulk',source=self.pa,target=self.pb,scope='group'),path)
                except ValueError as error:self.assertRegex(str(error),'driver|cycle|matching')
                else:
                    # The engine may skip the conflicting pair. Any accepted
                    # native subset must still have one driver and no cycle.
                    outputs={p['parameter'] for link in state['tools']['advancedLinks'] for p in link['outputs']}
                    self.assertTrue(outputs.isdisjoint(l['target'] for l in state['tools']['links']))
                    edges={a:[b]}
                    for link in state['tools']['links']:edges.setdefault(link['source'],[]).append(link['target'])
                    for source in edges:
                        stack=list(edges[source]);seen=set()
                        while stack:
                            target=stack.pop();self.assertNotEqual(target,source)
                            if target not in seen:seen.add(target);stack.extend(edges.get(target,[]))
                self.assertEqual(path.read_bytes(),before)
