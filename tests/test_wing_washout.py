"""Distributed washout is verified against direct native wing edits."""
import sys
import unittest
import test_native
from native_design_assist import metadata


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class WingWashout(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_multi_section_relative_twist_matches_saved_native_reference(self):
        v=self.v;g=self.gid
        v.InsertXSec(g,1,v.XS_FOUR_SERIES)
        v.SetParmValUpdate(g,'RelativeTwistFlag','WingGeom',1)
        v.SetParmValUpdate(g,'Z_Rel_Rotation','XForm',19)
        s=v.GetXSecSurf(g,0)
        for i,twist in enumerate([3,2,-1]):
            x=v.GetXSec(s,i)
            v.SetParmValUpdate(v.GetXSecParm(x,'Twist'),twist)
            v.SetParmValUpdate(v.GetXSecParm(x,'Twist_Location'),.4)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        self.assertIsNone(metadata(v,g)['washout'])
        # Original spans are 9 and 1; a six-degree root-to-tip difference
        # gives absolute twists 3, -2.4, -3 about quarter chord.
        v.SetParmValUpdate(g,'RelativeTwistFlag','WingGeom',0)
        for i,twist in enumerate([3,3-6*.9,-3]):
            x=v.GetXSec(s,i)
            v.SetParmValUpdate(v.GetXSecParm(x,'Twist'),twist)
            v.SetParmValUpdate(v.GetXSecParm(x,'Twist_Location'),.25)
        v.Update();reference=self.path/'reference.vsp3';v.WriteVSPFile(str(reference),v.SET_ALL)
        expected,_=self.worker({'action':'state'},reference)
        actual,saved=self.worker({'action':'mutate','operation':'design-assist','geom':g,'control':'wing-washout','value':6})
        self.assertEqual(actual['components'][0]['surfaces'],expected['components'][0]['surfaces'])
        reopened,_=self.worker({'action':'state'},saved)
        self.assertEqual(reopened['components'][0]['surfaces'],expected['components'][0]['surfaces'])
        v.ClearVSPModel();v.ReadVSPFile(str(saved));v.Update()
        self.assertAlmostEqual(metadata(v,g)['washout'],6)
        self.assertEqual(v.GetParmVal(g,'Z_Rel_Rotation','XForm'),19)
        self.assertEqual(v.GetParmVal(g,'RelativeTwistFlag','WingGeom'),0)
        s=v.GetXSecSurf(g,0)
        for i,twist in enumerate([3,3-6*.9,-3]):self.assertAlmostEqual(v.GetParmVal(v.GetXSecParm(v.GetXSec(s,i),'Twist')),twist)

    def test_negative_washout_and_rejection_preserve_native_file(self):
        state,path=self.worker({'action':'mutate','operation':'design-assist','geom':self.gid,'control':'wing-washout','value':-4})
        self.assertAlmostEqual(state['components'][0]['designAssist']['washout'],-4)
        before=path.read_bytes();existing=set(self.path.glob('*/aircraft.vsp3'))
        with self.assertRaisesRegex(ValueError,'twist limit'):
            self.worker({'action':'mutate','operation':'design-assist','geom':self.gid,'control':'wing-washout','value':1000},path)
        candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing))
        self.assertEqual(candidate.read_bytes(),before)


if __name__=='__main__':unittest.main()
