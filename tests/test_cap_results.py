"""Read native cap flags without changing geometry; preserve ABI guard failures."""
import ctypes
import json
import sys
import tempfile
import unittest
from vsp_runtime import load
import native_preview


@unittest.skipUnless(sys.version_info[:2] == (3,11), 'Use native Python 3.11.')
class CapResults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v=load()

    def tearDown(self):
        self.v.ClearVSPModel()

    def test_native_end_results_and_read_only_inspection(self):
        v=self.v
        for kind in ('WING','POD','FUSELAGE','STACK','PROP','ELLIPSOID'):
            with self.subTest(kind=kind):
                v.ClearVSPModel();g=v.AddGeom(kind);v.Update()
                before={p:v.GetParmVal(p) for p in v.GetGeomParmIDs(g)}
                expected=kind in ('WING','PROP')
                self.assertEqual(native_preview.cap_results(v,g),[[expected]*v.GetNumMainSurfs(g)]*2)
                self.assertEqual(before,{p:v.GetParmVal(p) for p in v.GetGeomParmIDs(g)})

    def test_open_body_caps_and_none(self):
        v=self.v;g=v.AddGeom('STACK');surf=v.GetXSecSurf(g,0)
        for i in (0,v.GetNumXSec(surf)-1):
            v.ChangeXSecShape(surf,i,v.XS_ELLIPSE)
            v.SetXSecWidthHeight(v.GetXSec(surf,i),2,1.5)
        for mode,expected in ((v.FLAT_END_CAP,True),(v.NO_END_CAP,False),(v.ROUND_END_CAP,True)):
            for name in ('CapUMinOption','CapUMaxOption'):
                v.SetParmVal(g,name,'EndCap',mode)
            v.Update()
            self.assertEqual(native_preview.cap_results(v,g),[[expected],[expected]])

    def test_reject_mismatched_parameter_addresses(self):
        v=self.v;g=v.AddGeom('WING');v.Update()
        _,engine,bridge=native_preview.adapter(v)
        function=bridge.studio_cap_results
        function.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.POINTER(ctypes.c_char_p),ctypes.c_int]
        function.restype=ctypes.c_char_p
        wrong=v.FindParm(g,'Tess_U','Shape').encode()
        result=json.loads(function(engine,g.encode(),(ctypes.c_char_p*5)(*([wrong]*5)),1))
        self.assertIn('layout does not match',result['error'])
        self.assertEqual(native_preview.cap_results(v,g),[[True],[True]])

    def test_reject_unknown_component(self):
        with self.assertRaisesRegex(ValueError,'existing component'):
            native_preview.cap_results(self.v,'missing')

    def test_reject_other_engine_build_before_reading_layout(self):
        with tempfile.NamedTemporaryFile() as file:
            file.write(b'Unverified engine build');file.flush()
            with self.assertRaisesRegex(ValueError,'verified OpenVSP'):
                native_preview._verified_private_layout(file.name,23,0)
