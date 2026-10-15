"""Copying a shorter editable profile must replace the entire point list."""
import unittest
import test_native
from test_curve_point_list import ROWS

class SectionCopyPoints(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_shorter_profile_replaces_points_on_all_section_families(self):
        v=self.v
        for kind in ('STACK','FUSELAGE','WING','PROP'):
            with self.subTest(kind=kind):
                v.ClearVSPModel();source=v.AddGeom('STACK');target=v.AddGeom(kind)
                xs=[]
                for g,rows in ((source,ROWS),(target,[[i/24,*ROWS[i%4][1:4],0] for i in range(25)])):
                    surf=v.GetXSecSurf(g,0);v.ChangeXSecShape(surf,1,v.XS_EDIT_CURVE);x=v.GetXSec(surf,1);xs.append(x)
                    v.SetParmValUpdate(v.GetXSecParm(x,'SymType'),v.SYM_NONE);v.EditXSecConvertTo(x,v.LINEAR)
                    v.SetEditXSecPnts(x,[r[0] for r in rows],[v.vec3d(*r[1:4]) for r in rows],[r[4] for r in rows])
                v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
                v.CopyXSec(source,1);v.PasteXSec(target,1);v.Update()
                reference=self.path/'direct.vsp3';v.WriteVSPFile(str(reference),v.SET_ALL)
                expected,_=self.worker(dict(action='state'),reference)
                state,path=self.worker(dict(action='mutate',operation='section-copy-from',geom=target,surface=0,index=1,sourceGeom=source,sourceSurface=0,sourceIndex=1))
                c=next(c for c in state['components'] if c['id']==target);section=c['sections'][1]
                self.assertEqual(section['controlPoints'],[r[1:4] for r in ROWS])
                self.assertEqual(section['rounding'],[r[4] for r in ROWS])
                ref=next(c for c in expected['components'] if c['id']==target)
                self.assertEqual(c['surfaces'],ref['surfaces'])
                values=lambda component:sorted((p['rawGroup'],p['group'],p['name'],p['value'],p['min'],p['max'],p['type']) for p in component['params'])
                self.assertEqual(values(c),values(ref))
                self.assertEqual(section['profile'],ref['sections'][1]['profile'])
                cold,_=self.worker(dict(action='state'),path)
                self.assertEqual(next(c['surfaces'] for c in cold['components'] if c['id']==target),c['surfaces'])

if __name__=='__main__':unittest.main()
