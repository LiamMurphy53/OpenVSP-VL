"""Saved expression-code downloads use the original native file writer."""
import unittest
import test_native

class ExpressionFiles(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;source=v.FindParm(self.gid,'TotalSpan','WingGeom');target=v.FindParm(self.gid,'Y_Rel_Location','XForm')
        v.AddAdvLink('Span placement');index=v.GetLinkIndex('Span placement')
        v.AddAdvLinkInput(index,source,'span');v.AddAdvLinkOutput(index,target,'position')
        code='// Native code file\nposition = span * 0.25;\n'
        original=self.path/'original.as';original.write_text(code)
        v.ReadAdvLinkCodeFile(index,str(original));self.assertTrue(v.BuildAdvLinkScript(index));v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return index,source,target

    def test_download_matches_native_writer_and_reimports_with_original_compiler(self):
        v=self.v;index,source,target=self.fixture();reference=self.path/'reference.as';v.WriteAdvLinkCodeFile(index,str(reference))
        before=self.model.read_bytes()
        result,work=self.worker(dict(action='export-geometry',kind='advanced-link-code',index=index,expectedName='Span placement'))
        exported=work.parent/result['filename'];self.assertEqual(exported.read_bytes(),reference.read_bytes());self.assertEqual(self.model.read_bytes(),before)
        definition=dict(action='mutate',operation='advanced-link-save',index=index,expectedName='Span placement',name='Span placement',inputs=[dict(name='span',parameter=source)],outputs=[dict(name='position',parameter=target)],code=exported.read_text())
        state,saved=self.worker(definition)
        state,saved=self.worker(dict(action='mutate',operation='parameter',id=source,value=24),saved)
        component=state['components'][0];self.assertEqual(next(p['value'] for p in component['params'] if p['id']==target),6)
        reopened,_=self.worker(dict(action='state'),saved);self.assertEqual(reopened['components'][0]['surfaces'],component['surfaces'])
        self.assertEqual(reopened['tools']['advancedLinks'][0]['code'],v.GetAdvLinkCode(index))

    def test_stale_missing_and_noninteger_expression_references_reject(self):
        index,_,_=self.fixture();before=self.model.read_bytes()
        for idx,title in [(index,'Renamed'),(-1,'Span placement'),(99,'Span placement'),(True,'Span placement'),('0','Span placement')]:
            with self.subTest(index=idx,name=title):
                with self.assertRaises(ValueError):self.worker(dict(action='export-geometry',kind='advanced-link-code',index=idx,expectedName=title))
                self.assertEqual(self.model.read_bytes(),before)
