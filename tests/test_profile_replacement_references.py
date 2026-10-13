"""Native profile replacement preserves referenced IDs or rejects atomically."""
import sys
import unittest
import test_native


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class ProfileReferences(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;g=v.AddGeom('STACK');surf=v.GetXSecSurf(g,0);x=v.GetXSec(surf,1)
        pid=v.GetXSecParm(x,'Theta');v.AddAttributeParm(v.GetChildCollection(v.GetVehicleID()),'Profile orientation reference',pid)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return g,pid,v.GetXSecShape(x)

    def test_referenced_profile_rejects_shape_import_and_conversion(self):
        g,pid,shape=self.fixture();before=self.model.read_bytes()
        requests=[dict(operation='shape',shape=self.v.XS_ROUNDED_RECTANGLE),dict(operation='curve-convert'),dict(operation='airfoil-import',content='Airfoil\n1 0\n.5 .1\n0 0\n.5 -.1\n1 0\n'),dict(operation='section-profile-import',content='OPENVSP_XSEC_FILE_V1\n1 0\n0 -1\n-1 0\n0 1\n1 0\n')]
        for extra in requests:
            existing=set(self.path.glob('*/aircraft.vsp3'))
            with self.assertRaisesRegex(ValueError,'profile parameter IDs used by parameter reference'):
                self.worker(dict(action='mutate',geom=g,surface=0,index=1,**extra))
            candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before)

    def test_same_profile_family_keeps_saved_reference(self):
        g,pid,shape=self.fixture()
        _,path=self.worker(dict(action='mutate',operation='shape',geom=g,surface=0,index=1,shape=shape))
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        self.assertTrue(v.ValidParm(pid))
        attr=next(a for a in v.FindAllAttributes() if v.GetAttributeName(a)=='Profile orientation reference')
        self.assertEqual(list(v.GetAttributeParmID(attr)),[pid])


    def test_cst_fit_rejects_referenced_original_airfoil(self):
        v=self.v;x=v.GetXSec(v.GetXSecSurf(self.gid,0),1);pid=v.GetXSecParm(x,'Theta')
        v.AddAttributeParm(v.GetChildCollection(v.GetVehicleID()),'Airfoil reference',pid);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'profile parameter IDs used by parameter reference'):
            self.worker(dict(action='mutate',operation='cst-fit',geom=self.gid,surface=0,index=1,degree=8))
        self.assertEqual(next(self.path.glob('*/aircraft.vsp3')).read_bytes(),before)


if __name__=='__main__':unittest.main()
