"""Stack coordinate-basis controls must follow the original engine transforms."""
import unittest
import test_body_controls
import test_native
import native_worker
import native_stack_positions as positions

class StackPositions(unittest.TestCase):
    setUpClass=classmethod(test_body_controls.BodyControls.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    body=test_body_controls.BodyControls.body
    compare=test_body_controls.BodyControls.compare

    def fixture(self):
        v=self.v;self.body('STACK');surf=v.GetXSecSurf(self.gid,0)
        prior=v.GetXSec(surf,1);v.SetParmValUpdate(v.GetXSecParm(prior,'ZRotate'),15.);v.SetParmValUpdate(v.GetXSecParm(prior,'YRotate'),6.)
        v.SetParmValUpdate(v.FindParm(self.gid,'Z_Rotation','XForm'),11.);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return v.GetXSec(surf,2)

    def test_each_basis_exposes_actual_driver_ids_and_matches_native_edits(self):
        v=self.v;x=self.fixture();before=self.model.read_bytes()
        for basis,names in [(v.REL,positions.RELATIVE),(v.ABS,positions.ABSOLUTE)]:
            v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
            pid=v.GetXSecParm(x,'XSAbsRelFlag');v.SetParmValUpdate(pid,basis);v.Update()
            state,saved=self.worker(dict(action='mutate',operation='parameter',id=pid,value=basis));self.compare(state)
            c=state['components'][0];section=c['sections'][2];params={p['id']:p for p in c['params']}
            self.assertEqual([params[p['parameter']]['name'] for p in section['bodyPositionControls']],['XSAbsRelFlag',*names])
            self.assertEqual(params[pid]['choices'],[[v.REL,'Relative to previous section'],[v.ABS,'Absolute in component axes']])
            for name,value in zip(names,[3.,.8,.4,10.,-5.,12.]):
                with self.subTest(basis=basis,name=name):
                    target=v.GetXSecParm(x,name);v.SetParmValUpdate(target,value);v.Update()
                    state,saved=self.worker(dict(action='mutate',operation='parameter',id=target,value=value),saved);self.compare(state)
                    self.assertEqual(next(p['dimension'] for p in state['components'][0]['params'] if p['id']==target),'angle' if 'Rotate' in name else 'length')
            reopened,_=self.worker(dict(action='state'),saved);self.compare(reopened)
        self.assertEqual(self.model.read_bytes(),before)

    def test_other_representation_and_fixed_endpoint_edits_are_rejected(self):
        v=self.v;x=self.fixture();before=self.model.read_bytes()
        for name in positions.ABSOLUTE:
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'coordinate basis'):
                self.worker(dict(action='mutate',operation='parameter',id=v.GetXSecParm(x,name),value=1.))
        root=v.GetXSec(v.GetXSecSurf(self.gid,0),0)
        with self.assertRaisesRegex(ValueError,'first stack profile'):self.worker(dict(action='mutate',operation='parameter',id=v.GetXSecParm(root,'XSAbsRelFlag'),value=v.ABS))
        order=v.FindParm(self.gid,'OrderPolicy','Design');_,saved=self.worker(dict(action='mutate',operation='parameter',id=order,value=1))
        last=v.GetXSec(v.GetXSecSurf(self.gid,0),v.GetNumXSec(v.GetXSecSurf(self.gid,0))-1)
        for name in positions.NAMES:
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'closes the stack loop'):
                self.worker(dict(action='mutate',operation='parameter',id=v.GetXSecParm(last,name),value=0.),saved)
        self.assertEqual(self.model.read_bytes(),before)
