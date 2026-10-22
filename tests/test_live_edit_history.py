"""A native slider gesture is one undo step, without crossing other edits."""
import unittest
import test_studies
import native_service as service

class LiveHistory(unittest.TestCase):
    setUpClass=classmethod(test_studies.NativeStudies.setUpClass.__func__)
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    def change(self,pid,value,token=None):
        req=dict(operation='parameter',id=pid,value=value,revision=service.REVISION)
        if token is not None:req['editGesture']=token
        return service.mutation(req)
    def test_drag_undo_redo_and_intervening_edits(self):
        pid=self.v.FindParm(self.gid,'TotalSpan','WingGeom');before=self.model.read_bytes();token='a'*32
        self.change(pid,19,token);self.change(pid,20,token)
        self.assertEqual(len(service.HISTORY),1);final=self.model.read_bytes()
        service.undo(revision=service.REVISION);self.assertEqual(self.model.read_bytes(),before)
        service.undo(redo=True,revision=service.REVISION);self.assertEqual(self.model.read_bytes(),final)
        self.change(pid,21,token);self.assertEqual(len(service.HISTORY),2,'Undo/redo breaks grouping')
        self.change(pid,22);self.change(pid,23,token);self.assertEqual(len(service.HISTORY),4,'An ordinary edit breaks grouping')
    def test_failure_and_stale_edit_preserve_last_valid_gesture(self):
        pid=self.v.FindParm(self.gid,'TotalSpan','WingGeom');before=self.model.read_bytes();token='b'*32
        self.change(pid,19,token);valid=self.model.read_bytes();history=list(service.HISTORY)
        with self.assertRaises(ValueError):service.mutation(dict(operation='parameter',id=pid,value=20,editGesture=token,revision='stale'))
        with self.assertRaises(ValueError):self.change(pid,20,'bad')
        with self.assertRaises(ValueError):self.change(pid,float('nan'),token)
        self.assertEqual(self.model.read_bytes(),valid);self.assertEqual(service.HISTORY,history)
        service.undo(revision=service.REVISION);self.assertEqual(self.model.read_bytes(),before)

    def test_same_token_cannot_combine_different_controls(self):
        span=self.v.FindParm(self.gid,'TotalSpan','WingGeom');area=self.v.FindParm(self.gid,'TotalArea','WingGeom');token='c'*32
        self.change(span,19,token);self.change(area,60,token)
        self.assertEqual(len(service.HISTORY),2)

    def test_cst_drag_is_one_native_undo_step(self):
        service.mutation(dict(operation='cst-fit',geom=self.gid,index=1,degree=3,revision=service.REVISION))
        baseline=len(service.HISTORY);before=self.model.read_bytes()
        for value in (.15,.25,.35):
            service.mutation(dict(operation='cst-coefficients',geom=self.gid,surface=0,index=1,
                upper=[value,.2,.2,.1],lower=[-.1,-.2,-.2,-.1],editGesture='d'*32,revision=service.REVISION))
        self.assertEqual(len(service.HISTORY),baseline+1)
        final=self.model.read_bytes()
        service.undo(revision=service.REVISION);self.assertEqual(self.model.read_bytes(),before)
        service.undo(redo=True,revision=service.REVISION);self.assertEqual(self.model.read_bytes(),final)

    def test_prop_curve_drag_is_one_native_undo_step(self):
        self.v.ClearVSPModel();gid=self.v.AddGeom('PROP');self.v.Update();self.v.WriteVSPFile(str(self.model),self.v.SET_ALL)
        data=service.state();prop=data['tools']['propellers'][0];curve=prop['curves'][0]
        before=self.model.read_bytes();baseline=len(service.HISTORY)
        for scale in (1.05,1.1):
            service.mutation(dict(operation='prop-curve-set',geom=gid,curve=curve['name'],stations=curve['stations'],
                values=[v*scale for v in curve['values']],editGesture='e'*32,revision=service.REVISION))
        self.assertEqual(len(service.HISTORY),baseline+1)
        final=self.model.read_bytes()
        service.undo(revision=service.REVISION);self.assertEqual(self.model.read_bytes(),before)
        service.undo(redo=True,revision=service.REVISION);self.assertEqual(self.model.read_bytes(),final)
