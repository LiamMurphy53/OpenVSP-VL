"""Native reference drawing coordinates survive transient GUI selection."""
import ctypes,json,sys,unittest
import test_native
from native_preview import adapter

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class BlankReferences(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_selection_policy_preserves_exact_native_drawing_data(self):
        v=self.v;g=v.AddGeom('BLANK');v.SetParmValUpdate(g,'X_Rel_Location','XForm',4);v.SetParmValUpdate(g,'PointMass','Mass_Props',2);v.Update()
        _,engine,bridge=adapter(v);fn=bridge.studio_blank_drawings
        fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p];fn.restype=ctypes.c_char_p
        original=json.loads(fn(engine,g.encode()))
        v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,path=self.worker(dict(action='state'));c=next(c for c in state['components'] if c['id']==g)
        normalize=lambda rows:[{k:value for k,value in row.items() if k not in ('visible','selectionOnly')} for row in rows]
        self.assertEqual(normalize(c['referenceDrawings']),normalize(original))
        for row in c['referenceDrawings']:
            self.assertEqual(row['selectionOnly'],not row['nativeID'].startswith(g+'_Feature_'))
        state,path=self.worker(dict(action='mutate',operation='add',type='POD'),path)
        changed=next(c for c in state['components'] if c['id']==g)
        self.assertEqual(changed['referenceDrawings'],c['referenceDrawings'])
        cold,_=self.worker(dict(action='state'),path)
        self.assertEqual(next(c for c in cold['components'] if c['id']==g)['referenceDrawings'],c['referenceDrawings'])
