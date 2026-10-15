"""Saved value constraints must reject direct, dependent and study edits atomically."""
import unittest
import test_native
from native_property_locks import records

class PropertyLocks(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_direct_and_dependent_constraints_reload_and_unlock(self):
        v=self.v;g=self.gid;area=v.FindParm(g,'TotalArea','WingGeom');span=v.FindParm(g,'TotalSpan','WingGeom')
        state,path=self.worker(dict(action='mutate',operation='property-lock',parameters=[area],locked=True))
        self.assertTrue(next(p for p in state['components'][0]['params'] if p['id']==area)['userLocked'])
        reopened,path=self.worker(dict(action='state'),path)
        self.assertTrue(next(p for p in reopened['components'][0]['params'] if p['id']==area)['userLocked'])
        for pid in (area,span):
            before=path.read_bytes()
            with self.assertRaisesRegex(ValueError,'locked'):
                self.worker(dict(action='mutate',operation='parameter',id=pid,value=100),path)
            self.assertEqual(path.read_bytes(),before)
        # Compound AR resize retains area, so this edit is permitted.
        state,path=self.worker(dict(action='mutate',operation='design-assist',geom=g,control='wing-aspect-ratio',value=12),path)
        self.assertAlmostEqual(next(p['value'] for p in state['components'][0]['params'] if p['id']==area),v.GetParmVal(area))
        state,path=self.worker(dict(action='mutate',operation='property-lock',parameters=[area],locked=False),path)
        state,path=self.worker(dict(action='mutate',operation='parameter',id=area,value=100),path)
        self.assertAlmostEqual(next(p['value'] for p in state['components'][0]['params'] if p['id']==area),100)

    def test_computed_ar_blocks_linked_resize_and_component_removal(self):
        v=self.v;g=self.gid;ar=v.FindParm(g,'TotalAR','WingGeom')
        state,path=self.worker(dict(action='mutate',operation='property-lock',parameters=[ar],locked=True))
        for edit in (dict(operation='design-assist',geom=g,control='wing-aspect-ratio',value=20),dict(operation='delete',geom=g)):
            before=path.read_bytes()
            with self.assertRaisesRegex(ValueError,'locked'):self.worker(dict(action='mutate',**edit),path)
            self.assertEqual(path.read_bytes(),before)

    def test_native_parameter_link_cannot_change_locked_target(self):
        v=self.v;g=self.gid;pod=v.AddGeom('POD');v.Update()
        source=v.FindParm(pod,'Length','Design')
        target=v.GetXSecParm(v.GetXSec(v.GetXSecSurf(g,0),1),'Root_Chord')
        scale=v.GetParmVal(target)/v.GetParmVal(source)
        v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,path=self.worker(dict(action='mutate',operation='link-add',source=source,target=target,scale=scale))
        state,path=self.worker(dict(action='mutate',operation='property-lock',parameters=[target],locked=True),path)
        before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'locked'):self.worker(dict(action='mutate',operation='parameter',id=source,value=30),path)
        self.assertEqual(path.read_bytes(),before)

    def test_external_deletion_can_release_stale_lock(self):
        v=self.v;g=self.gid;pid=v.FindParm(g,'TotalSpan','WingGeom')
        from native_property_locks import set_locked
        set_locked(v,[pid],True)
        v.DeleteGeom(g);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,path=self.worker(dict(action='state'))
        lock=state['tools']['propertyLocks'][0]
        self.assertFalse(lock['available']);self.assertTrue(lock['conflict'])
        self.assertTrue(state['warnings'])
        state,path=self.worker(dict(action='mutate',operation='property-lock',parameters=[pid],locked=False),path)
        self.assertEqual(state['tools']['propertyLocks'],[])

    def test_fit_optimizer_cannot_change_locked_variable(self):
        v=self.v;v.ClearVSPModel();g=v.AddGeom('POD');pid=v.FindParm(g,'Length','Design')
        v.SetParmValUpdate(pid,12);p=v.CompPnt01(g,0,.7,.25)
        point=[p.x(),p.y(),p.z()]
        v.SetParmValUpdate(pid,8);v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,path=self.worker(dict(action='mutate',operation='fit-targets-add',geom=g,surface=0,points=[point],fixedU=True,fixedW=True,u=.7,w=.25))
        state,path=self.worker(dict(action='mutate',operation='fit-variables',parameters=[pid]),path)
        state,path=self.worker(dict(action='mutate',operation='property-lock',parameters=[pid],locked=True),path)
        before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'locked'):self.worker(dict(action='mutate',operation='fit-optimize'),path)
        self.assertEqual(path.read_bytes(),before)

    def test_reloaded_reference_edit_enforces_lock_and_preserves_transaction(self):
        import uuid
        import native_service as service
        from native_property_locks import set_locked
        v=self.v;pid=v.FindParm(self.gid,'TotalSpan','WingGeom')
        prop=v.AddFeaProperty(v.FEA_SHELL);material=v.AddFeaMaterial()
        set_locked(v,[pid],True)
        # Simulate a native-app change while the saved Studio constraint remains.
        v.SetParmValUpdate(pid,24);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        old=service.WORK,service.MODEL,service.HISTORY,service.FUTURE,service.REVISION,service.SESSION_WARNING
        try:
            service.WORK=self.path;service.MODEL=self.model;service.HISTORY=[];service.FUTURE=[];service.REVISION=uuid.uuid4().hex;service.SESSION_WARNING=None
            before=self.model.read_bytes();revision=service.REVISION
            with self.assertRaisesRegex(ValueError,'locked'):
                service.mutation(dict(operation='property-material',id=prop,material=material,revision=revision))
            self.assertEqual(self.model.read_bytes(),before)
            self.assertEqual(service.REVISION,revision);self.assertEqual(service.HISTORY,[])
            service.mutation(dict(operation='property-lock',parameters=[pid],locked=False,revision=revision))
            state=service.mutation(dict(operation='property-material',id=prop,material=material,revision=service.REVISION))
            self.assertEqual(state['tools']['propertyLocks'],[])
            v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
            from native_references import references
            self.assertEqual(references(v)[prop]['FeaMaterialID'],material)
            self.assertEqual(v.GetParmVal(pid),24)
        finally:service.WORK,service.MODEL,service.HISTORY,service.FUTURE,service.REVISION,service.SESSION_WARNING=old

    def test_study_constraints_checked_before_writing(self):
        v=self.v;g=self.gid;pid=v.FindParm(g,'TotalSpan','WingGeom')
        from native_property_locks import set_locked
        from native_study_worker import prepare
        from native_worker import errors
        set_locked(v,[pid],True)
        candidate=self.path/'locked-study.vsp3'
        with self.assertRaisesRegex(ValueError,'locked'):prepare(v,dict(parameters=[dict(id=pid,value=50)]),candidate,errors)
        self.assertFalse(candidate.exists())

if __name__=='__main__':unittest.main()
