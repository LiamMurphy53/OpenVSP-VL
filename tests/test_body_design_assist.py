"""Compound station controls compared with saved, direct native geometry."""
import sys
import unittest
import test_native
from native_design_assist import metadata


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class BodyDesignAssist(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    def test_end_lengths_match_native_saved_geometry(self):
        v=self.v
        v.ClearVSPModel();gid=v.AddGeom('FUSELAGE');v.Update()
        v.WriteVSPFile(str(self.model),v.SET_ALL)
        surf=v.GetXSecSurf(gid,0)
        dimensions=[(v.GetXSecWidth(v.GetXSec(surf,i)),v.GetXSecHeight(v.GetXSec(surf,i))) for i in range(5)]
        # Independent native setters: nose 3/30, center halfway to fixed 3/4.
        for i,pos in [(1,.1),(2,.425),(3,.75)]:
            v.SetParmValUpdate(v.GetXSecParm(v.GetXSec(surf,i),'XLocPercent'),pos)
        v.Update();reference=self.path/'reference.vsp3';v.WriteVSPFile(str(reference),v.SET_ALL)
        reference_state,_=self.worker({'action':'state'},reference)
        state,saved=self.worker({'action':'mutate','operation':'design-assist','geom':gid,'control':'body-nose','value':3})
        self.assertEqual(len(state['components'][0]['surfaces']),len(reference_state['components'][0]['surfaces']))
        for actual,expected in zip(state['components'][0]['surfaces'],reference_state['components'][0]['surfaces']):
            self.assertEqual((actual['rows'],actual['cols']),(expected['rows'],expected['cols']))
            self.assertEqual(len(actual['points']),len(expected['points']))
            for p,q in zip(actual['points'],expected['points']):
                for a,b in zip(p,q):self.assertAlmostEqual(a,b,places=10)
        v.ClearVSPModel();v.ReadVSPFile(str(saved));surf=v.GetXSecSurf(gid,0)
        self.assertAlmostEqual(metadata(v,gid)['noseLength'],3)
        self.assertEqual(dimensions,[(v.GetXSecWidth(v.GetXSec(surf,i)),v.GetXSecHeight(v.GetXSec(surf,i))) for i in range(5)])
        _,tail=self.worker({'action':'mutate','operation':'design-assist','geom':gid,'control':'body-tail','value':12},saved)
        v.ClearVSPModel();v.ReadVSPFile(str(tail));surf=v.GetXSecSurf(gid,0)
        for i,pos in enumerate([0,.1,.35,.6,1]):self.assertAlmostEqual(v.GetParmVal(v.GetXSecParm(v.GetXSec(surf,i),'XLocPercent')),pos)
        self.assertAlmostEqual(metadata(v,gid)['tailLength'],12)

    def test_forward_station_moves_preserve_native_order(self):
        v=self.v;v.ClearVSPModel();gid=v.AddGeom('FUSELAGE');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        saved=self.model
        for control,value,positions in [('body-nose',15,[0,.5,.625,.75,1]),('body-tail',3,[0,.5,.7,.9,1])]:
            _,saved=self.worker({'action':'mutate','operation':'design-assist','geom':gid,'control':control,'value':value},saved)
            v.ClearVSPModel();v.ReadVSPFile(str(saved));surf=v.GetXSecSurf(gid,0)
            for i,pos in enumerate(positions):self.assertAlmostEqual(v.GetParmVal(v.GetXSecParm(v.GetXSec(surf,i),'XLocPercent')),pos)

    def test_crossing_station_edit_is_rejected(self):
        v=self.v;v.ClearVSPModel();gid=v.AddGeom('FUSELAGE');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'leave space'):
            self.worker({'action':'mutate','operation':'design-assist','geom':gid,'control':'body-nose','value':24})
        candidates=list(self.path.glob('*/aircraft.vsp3'))
        self.assertEqual(len(candidates),1)
        self.assertEqual(candidates[0].read_bytes(),before)


if __name__=='__main__':unittest.main()
