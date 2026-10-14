"""Whole-wing AR driving edits use native span and area updates."""
import math
import sys
import unittest
import test_native
from native_design_assist import metadata

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class WingAspectRatio(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_area_retained_with_multisection_dihedral_and_symmetry(self):
        v=self.v;g=self.gid
        for symmetric in (True,False):
            with self.subTest(symmetric=symmetric):
                if symmetric:v.InsertXSec(g,1,v.XS_FOUR_SERIES)
                v.SetParmValUpdate(g,'Sym_Planar_Flag','Sym',v.SYM_XZ if symmetric else 0)
                surf=v.GetXSecSurf(g,0)
                for i in range(1,v.GetNumXSec(surf)):
                    v.SetParmValUpdate(v.GetXSecParm(v.GetXSec(surf,i),'Dihedral'),12*i)
                v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
                area=v.GetParmVal(g,'TotalArea','WingGeom');ar=v.GetParmVal(g,'TotalAR','WingGeom');span=v.GetParmVal(g,'TotalProjectedSpan','WingGeom')
                target=ar*1.7
                result,saved=self.worker({'action':'mutate','operation':'design-assist','geom':g,'control':'wing-aspect-ratio','value':target})
                self.assertAlmostEqual(result['components'][0]['designAssist']['aspectRatio'],target)
                reopened,_=self.worker({'action':'state'},saved)
                self.assertEqual(result['components'][0]['surfaces'],reopened['components'][0]['surfaces'])
                v.ClearVSPModel();v.ReadVSPFile(str(saved));v.Update()
                self.assertAlmostEqual(v.GetParmVal(g,'TotalArea','WingGeom'),area)
                self.assertAlmostEqual(v.GetParmVal(g,'TotalProjectedSpan','WingGeom'),span*math.sqrt(1.7))
                self.assertAlmostEqual(metadata(v,g)['aspectRatio'],target)

    def test_invalid_target_leaves_saved_model_unchanged(self):
        for value in (0,-1,1e20):
            before=self.model.read_bytes()
            with self.assertRaises(ValueError):self.worker({'action':'mutate','operation':'design-assist','geom':self.gid,'control':'wing-aspect-ratio','value':value})
            self.assertEqual(self.model.read_bytes(),before)

if __name__=='__main__':unittest.main()
