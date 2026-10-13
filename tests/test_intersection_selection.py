"""Native selection validation and documented ModeID reload semantics."""
import sys,unittest
import test_native
import native_intersection_selection as selection
from native_references import ReloadRequired

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class IntersectionSelection(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_saved_named_mode_is_native_default_and_active_reference_is_guarded(self):
        v=self.v;mode=v.CreateAndAddMode('Intersection configuration',0,-1);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        with self.assertRaises(ReloadRequired):selection.mutate(v,dict(values={'UseMode':1},mode=mode))
        schema,_=self.worker(dict(action='schema',name='SurfaceIntersection'))
        fields={e['name']:e['values'] for e in schema['inputs']}
        self.assertEqual(fields['ModeID'],[mode]);self.assertEqual(fields['UseMode'],[1])
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        self.assertEqual(selection.configuration(v)['mode'],mode)
        with self.assertRaisesRegex(ValueError,'selected for surface intersections'):selection.guard_mode_delete(v,mode)
        selection.mutate(v,dict(values={'UseMode':0,'Set':0,'DegenSet':-1}))
        selection.guard_mode_delete(v,mode)
        with self.assertRaises(ReloadRequired):selection.mutate(v,dict(values={},mode=''))
        schema,_=self.worker(dict(action='schema',name='SurfaceIntersection'))
        self.assertEqual(next(e['values'] for e in schema['inputs'] if e['name']=='ModeID'),[''])

    def test_invalid_requests_preserve_all_native_values_and_file(self):
        before=selection.configuration(self.v);file=self.model.read_bytes()
        for request in [dict(values={'UseMode':1}),dict(values={'UseMode':1},mode='missing'),dict(values={'Set':self.v.GetNumSets()}),dict(values={'Set':.5}),dict(values={'DegenSet':-2}),dict(values={'UseMode':True}),dict(values={'Set':0},mode=42),dict(values={'NoSuchSetting':1}),dict(values=[]),dict(values={})]:
            with self.subTest(request=request),self.assertRaises(ValueError):selection.mutate(self.v,request)
            self.assertEqual(selection.configuration(self.v),before);self.assertEqual(self.model.read_bytes(),file)

    def test_integrated_worker_selection_snapshot_and_mode_deletion_guard(self):
        v=self.v;mode=v.CreateAndAddMode('Intersection configuration',0,-1)
        other=v.CreateAndAddMode('Other configuration',1,-1);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        original=self.model.read_bytes()
        state,path=self.worker(dict(action='mutate',operation='intersection-selection',values={'UseMode':1},mode=mode))
        config=next(g['selection'] for g in state['tools']['globalSettings'] if g['name']=='SurfaceIntersectSettings')
        self.assertEqual(config['mode'],mode);self.assertEqual(next(p['value'] for p in config['params'] if p['name']=='UseMode'),1)
        frozen=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'selected for surface intersections'):self.worker(dict(action='mutate',operation='mode-delete',id=mode),path)
        self.assertEqual(path.read_bytes(),frozen)
        state,reassigned=self.worker(dict(action='mutate',operation='intersection-selection',values={'UseMode':1},mode=other),path)
        state,deleted=self.worker(dict(action='mutate',operation='mode-delete',id=mode),reassigned)
        self.assertNotIn(mode,[m['id'] for m in state['tools']['modes']])
        self.assertEqual(next(g['selection']['mode'] for g in state['tools']['globalSettings'] if g['name']=='SurfaceIntersectSettings'),other)
        state,sets=self.worker(dict(action='mutate',operation='intersection-selection',values={'UseMode':0,'Set':0,'DegenSet':-1}),deleted)
        self.assertEqual({p['name']:p['value'] for p in next(g['selection'] for g in state['tools']['globalSettings'] if g['name']=='SurfaceIntersectSettings')['params']},{'UseMode':0,'Set':0,'DegenSet':-1})
        self.assertEqual(self.model.read_bytes(),original)
