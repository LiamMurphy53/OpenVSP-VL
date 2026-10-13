"""Blade-element guidance retains native geometry samples and BEM bytes."""
import sys,unittest
import test_native
import native_worker
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native runtime.')
class BladeElements(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;g=v.AddGeom('PROP');v.SetGeomName(g,'Selected propeller');v.SetParmValUpdate(g,'Diameter','Design',6);v.SetParmValUpdate(g,'Beta34','Design',25);v.SetParmValUpdate(g,'Y_Rel_Location','XForm',8);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);return g

    def test_selector_and_invalid_reference_recovery(self):
        g=self.fixture();state,_=self.worker(dict(action='schema',name='BladeElement'))
        p=next(e for e in state['inputs'] if e['name']=='PropID');self.assertEqual([x['value'] for x in p['choices']],['',g]);self.assertIn('geometry',state['guide']['note'])
        before=self.model.read_bytes()
        for prop in ('',self.gid,'missing-native-propeller'):
            with self.subTest(prop=prop),self.assertRaisesRegex(ValueError,'existing native propeller'):
                self.worker(dict(action='analysis',name='BladeElement',inputs=[dict(name='PropID',values=[prop])]))
        self.assertEqual(self.model.read_bytes(),before)

    def test_complete_samples_and_export_match_independent_native(self):
        g=self.fixture();before=self.model.read_bytes();state,case=self.worker(dict(action='analysis',name='BladeElement',inputs=[dict(name='PropID',values=[g]),dict(name='ExportBEMFlag',values=[1]),dict(name='BEMFileName',values=['/prior/workspace/selected.bem'])]))
        self.assertTrue((case.parent/'selected.bem').is_file());v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();v.SetAnalysisInputDefaults('BladeElement');v.SetStringAnalysisInput('BladeElement','PropID',[g]);v.SetIntAnalysisInput('BladeElement','ExportBEMFlag',[1]);v.SetStringAnalysisInput('BladeElement','BEMFileName',[str(self.path/'direct.bem')]);v.ExecAnalysis('BladeElement');expected=native_worker.collect_results(v)
        actual=next(r for r in state['results'] if r['name']=='PropBEM');direct=next(r for r in expected if r['name']=='PropBEM')
        for e in direct['entries']:
            if e['name']=='Analysis_Duration_Sec':continue
            self.assertEqual(next(x['values'] for x in actual['entries'] if (x['name'],x['index'])==(e['name'],e['index'])),e['values'])
        self.assertEqual((case.parent/'selected.bem').read_bytes(),(self.path/'direct.bem').read_bytes());self.assertEqual(self.model.read_bytes(),before)

    def test_filename_rejection_and_results_only(self):
        g=self.fixture();before=self.model.read_bytes()
        for filename in ('','..','invalid\\path.bem'):
            with self.subTest(filename=filename),self.assertRaisesRegex(ValueError,'BEM filename'):
                self.worker(dict(action='analysis',name='BladeElement',inputs=[dict(name='PropID',values=[g]),dict(name='ExportBEMFlag',values=[1]),dict(name='BEMFileName',values=[filename])]))
        state,case=self.worker(dict(action='analysis',name='BladeElement',inputs=[dict(name='PropID',values=[g])]))
        self.assertTrue(any(r['name']=='PropBEM' for r in state['results']));self.assertFalse(list(case.parent.glob('*.bem')));self.assertEqual(self.model.read_bytes(),before)
