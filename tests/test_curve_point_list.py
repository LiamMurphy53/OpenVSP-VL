"""Bulk curve points remain original native geometry and atomic transactions."""
import sys
import unittest
import test_native

ROWS=[[0,.5,.5,0,0],[.25,.5,-.5,0,.02],[.5,-.5,-.5,0,.03],[.75,-.5,.5,0,.01],[1,.5,.5,0,0]]

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class CurvePointLists(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self,kind='STACK'):
        v=self.v;v.ClearVSPModel();g=v.AddGeom(kind);s=v.GetXSecSurf(g,0);v.ChangeXSecShape(s,1,v.XS_EDIT_CURVE);x=v.GetXSec(s,1)
        v.SetParmValUpdate(v.GetXSecParm(x,'SymType'),v.SYM_NONE);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return g,x

    def test_native_point_lists_and_rounding_match_on_four_families(self):
        v=self.v
        for kind in ('WING','FUSELAGE','STACK','PROP'):
            for typ in ('LINEAR','PCHIP','CEDIT'):
                with self.subTest(kind=kind,type=typ):
                    rows=ROWS if typ!='CEDIT' else [[0,.5,0,0,0],[1/3,0,.5,0,0],[2/3,-.5,0,0,0],[1,.5,0,0,0]]
                    g,x=self.fixture(kind);v.EditXSecConvertTo(x,getattr(v,typ));v.SetEditXSecPnts(x,[r[0] for r in rows],[v.vec3d(*r[1:4]) for r in rows],[r[4] for r in rows]);v.Update()
                    reference=self.path/'reference.vsp3';v.WriteVSPFile(str(reference),v.SET_ALL)
                    expected,_=self.worker(dict(action='state'),reference)
                    state,path=self.worker(dict(action='mutate',operation='curve-replace-points',geom=g,surface=0,index=1,type=typ,rows=rows))
                    self.assertEqual(state['components'][0]['surfaces'],expected['components'][0]['surfaces'])
                    section=state['components'][0]['sections'][1]
                    self.assertEqual(section['controlPoints'],expected['components'][0]['sections'][1]['controlPoints']);self.assertEqual(section['rounding'],expected['components'][0]['sections'][1]['rounding'])
                    if typ=='LINEAR':self.assertEqual(section['rounding'],[r[4] for r in rows])
                    if typ=='PCHIP':self.assertEqual(section['rounding'],[0]*len(rows))
                    reopened,_=self.worker(dict(action='state'),path)
                    self.assertEqual(reopened['components'][0]['surfaces'],expected['components'][0]['surfaces'])

    def test_bad_rows_and_referenced_points_preserve_candidate(self):
        g,x=self.fixture();v=self.v
        cases=[('LINEAR',[[0,0,0,0,0],[0,1,1,0,0]]),('CEDIT',ROWS),('LINEAR',[[0,0,0,0,-1],[1,1,1,0,0]]),('LINEAR',[[0,0,0],[1,1,1]])]
        for typ,rows in cases:
            before=self.model.read_bytes();existing=set(self.path.glob('*/aircraft.vsp3'))
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='curve-replace-points',geom=g,index=1,type=typ,rows=rows))
            candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before)
        pid=v.GetXSecParm(x,'X_3');v.AddAttributeParm(v.GetChildCollection(v.GetVehicleID()),'Curve point reference',pid);v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes();existing=set(self.path.glob('*/aircraft.vsp3'))
        with self.assertRaisesRegex(ValueError,'point IDs used by parameter reference'):
            self.worker(dict(action='mutate',operation='curve-replace-points',geom=g,index=1,type='LINEAR',rows=ROWS))
        candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before)

if __name__=='__main__':unittest.main()
