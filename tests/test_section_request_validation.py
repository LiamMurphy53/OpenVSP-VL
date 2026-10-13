"""Main section transactions must not truncate indices or native shape codes."""
import sys
import unittest
import test_native


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class SectionRequests(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def reject(self,request,message):
        before=self.model.read_bytes();existing=set(self.path.glob('*/aircraft.vsp3'))
        with self.assertRaisesRegex(ValueError,message):self.worker(dict(action='mutate',geom=self.gid,**request))
        candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing))
        self.assertEqual(candidate.read_bytes(),before)

    def test_fractional_and_boolean_indices_are_rejected_for_every_operation(self):
        for operation in ('shape','insert-section','cut-section','split-section','drivers'):
            common=dict(operation=operation,shape=self.v.XS_ELLIPSE,drivers=[self.v.SPAN_WSECT_DRIVER,self.v.ROOTC_WSECT_DRIVER,self.v.TIPC_WSECT_DRIVER])
            for extra in [dict(index=1.9),dict(index=True),dict(index=1,surface=.5),dict(index=1,surface=False)]:
                self.reject(dict(**common,**extra),'whole-number')

    def test_invalid_shape_codes_are_rejected_without_saving(self):
        for operation in ('shape','insert-section'):
            for shape in (2.5,True,-1,100000):self.reject(dict(operation=operation,index=1,shape=shape),'supported native profile')


    def test_curve_constraint_and_delete_indices_are_strict(self):
        v=self.v;surf=v.GetXSecSurf(self.gid,0);v.ChangeXSecShape(surf,1,v.XS_EDIT_CURVE);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        for operation in ('curve-delete','curve-fixed'):
            for point in (True,False,3.0,3.5,'3'):
                self.reject(dict(operation=operation,index=1,point=point,fixed=True),'native curve point index')


if __name__=='__main__':unittest.main()
