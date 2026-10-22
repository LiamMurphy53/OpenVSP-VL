"""Original wing blend modes, endpoint policy and complete native geometry."""
import sys
import unittest
import test_native
import test_wing_controls
import native_worker
import native_wing_blending as blend

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class WingBlending(unittest.TestCase):
    setUpClass=classmethod(test_wing_controls.WingControls.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    assert_geometry_matches=test_wing_controls.WingControls.assert_geometry_matches

    def fixture(self):
        v=self.v
        v.InsertXSec(self.gid,1,v.XS_FOUR_SERIES);v.Update()
        x=v.GetXSec(v.GetXSecSurf(self.gid,0),1)
        for edge,_ in blend.EDGES:v.SetParmVal(v.GetXSecParm(x,edge+'Mode'),v.BLEND_ANGLES)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        native_worker.errors(v)
        return x

    def test_every_available_interior_mode_matches_original_sdk_and_reopens(self):
        v=self.v;x=self.fixture();source=self.model.read_bytes();count=0
        state,_=self.worker(dict(action='state'))
        for edge,_ in blend.EDGES:
            pid=v.GetXSecParm(x,edge+'Mode');p=next(p for p in state['components'][0]['params'] if p['id']==pid)
            self.assertNotIn('displayReadOnly',p)
            for value,label in p['choices']:
                with self.subTest(edge=edge,mode=label):
                    v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
                    v.SetParmValUpdate(pid,value);v.Update();native_worker.errors(v)
                    actual,saved=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value))
                    self.assert_geometry_matches(actual)
                    reopened,_=self.worker(dict(action='state'),saved)
                    self.assertEqual(next(p['value'] for p in reopened['components'][0]['params'] if p['id']==pid),v.GetParmVal(pid));count+=1
        self.assertEqual(count,28)
        self.assertEqual(self.model.read_bytes(),source)

    def test_native_angles_strength_and_endpoint_eligibility(self):
        v=self.v;x=self.fixture()
        for name,value in [('InLESweep',23.),('InLEDihedral',12.),('OutTEStrength',.4)]:
            pid=v.GetXSecParm(x,name);v.SetParmValUpdate(pid,value);v.Update()
            actual,_=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value));self.assert_geometry_matches(actual)
            v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        state,_=self.worker(dict(action='state'));params={p['id']:p for p in state['components'][0]['params']}
        surf=v.GetXSecSurf(self.gid,0)
        for index,edge in [(0,'InLE'),(0,'InTE'),(v.GetNumXSec(surf)-1,'OutLE'),(v.GetNumXSec(surf)-1,'OutTE')]:
            pid=v.GetXSecParm(v.GetXSec(surf,index),edge+'Mode')
            self.assertTrue(params[pid]['displayReadOnly'])
            with self.assertRaisesRegex(ValueError,'neighbor'):self.worker(dict(action='mutate',operation='parameter',id=pid,value=1))
        self.assertEqual(params[v.GetXSecParm(x,'InLESweep')]['dimension'],'angle')

    def test_matching_angle_dependencies_and_automatic_outputs_reject_edits(self):
        v=self.v;x=self.fixture();pid=v.GetXSecParm(x,'InLEMode')
        actual,saved=self.worker(dict(action='mutate',operation='parameter',id=pid,value=v.BLEND_FREE))
        params={p['name']:p for p in actual['components'][0]['params'] if p['group']=='XSec_1'}
        self.assertNotIn(v.BLEND_MATCH_IN_ANGLES,[choice[0] for choice in params['OutLEMode']['choices']])
        self.assertNotIn(v.BLEND_MATCH_LE_ANGLES,[choice[0] for choice in params['InTEMode']['choices']])
        original=saved.read_bytes()
        for name,value in [('InLESweep',5),('InLEStrength',.5),('OutLEMode',v.BLEND_MATCH_IN_ANGLES),('InLEMode',7)]:
            with self.subTest(name=name),self.assertRaises(ValueError):
                self.worker(dict(action='mutate',operation='parameter',id=params[name]['id'],value=value),saved)
        self.assertEqual(saved.read_bytes(),original)
