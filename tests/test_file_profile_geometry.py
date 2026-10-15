"""Stored-coordinate edits retain complete original SDK geometry after saving."""
import unittest
import test_native
from native_bor_points import coordinates

class FileProfileGeometry(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def check(self,kind,shape,side=None):
        v=self.v;v.ClearVSPModel();g=v.AddGeom(kind)
        surf=v.GetXSecSurf(g,0);v.ChangeXSecShape(surf,1,shape);x=v.GetXSec(surf,1)
        v.SetParmValUpdate(g,'Y_Rel_Rotation','XForm',13)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        request=dict(action='mutate',geom=g,surface=0,index=1)
        if side is None:
            rows=[[1,0,0],[.6,-.7,0],[0,-1,0],[-.6,-.7,0],[-1,0,0],[-.6,.9,0],[0,1.2,0],[.6,.9,0],[1,0,0]]
            v.SetXSecPnts(x,[v.vec3d(*p) for p in rows]);request.update(operation='section-file-section-points',points=rows)
        else:
            upper=[[0,0,0],[.2,.09,0],[.6,.07,0],[1,0,0]]
            lower=[[0,0,0],[.3,-.04,0],[.7,-.025,0],[1,0,0]]
            old_upper=coordinates(v.GetAirfoilUpperPnts(x));old_lower=coordinates(v.GetAirfoilLowerPnts(x))
            request.update(operation='section-file-airfoil-points',side=side)
            if side=='both':v.SetAirfoilPnts(x,[v.vec3d(*p) for p in upper],[v.vec3d(*p) for p in lower]);request.update(upper=upper,lower=lower)
            else:
                rows=upper if side=='upper' else lower
                getattr(v,'SetAirfoil'+side.title()+'Pnts')(x,[v.vec3d(*p) for p in rows]);request['points']=rows
        v.Update();reference=self.path/'direct.vsp3';v.WriteVSPFile(str(reference),v.SET_ALL)
        expected,_=self.worker(dict(action='state'),reference)
        actual,saved=self.worker(request)
        cold,_=self.worker(dict(action='state'),saved)
        # Whole component includes every surface coordinate and sampled profile,
        # original parameter IDs/values, native point vectors and transforms.
        self.assertEqual(actual['components'],expected['components'])
        self.assertEqual(cold['components'],expected['components'])
        if side in ('upper','lower'):
            profile=actual['components'][0]['sections'][1]['filePoints']
            self.assertEqual(profile['lower' if side=='upper' else 'upper'],old_lower if side=='upper' else old_upper)

    def test_native_section_coordinates_all_four_owners(self):
        for kind in ('WING','PROP','FUSELAGE','STACK'):
            with self.subTest(kind=kind):self.check(kind,self.v.XS_FILE_FUSE)

    def test_native_airfoil_sides_all_four_owners(self):
        for kind in ('WING','PROP','FUSELAGE','STACK'):
            for side in ('upper','lower','both'):
                with self.subTest(kind=kind,side=side):self.check(kind,self.v.XS_FILE_AIRFOIL,side)

if __name__=='__main__':unittest.main()
