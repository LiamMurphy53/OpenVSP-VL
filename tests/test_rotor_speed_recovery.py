"""Native RPM recovery follows original component/surface membership, not IDs."""
import json,sys,unittest
import test_native
import native_rotor_speeds as recovery
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class RotorSpeedRecovery(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;self.props=[]
        for y in (-8,8):
            g=v.AddGeom('PROP');self.props.append(g)
            v.SetParmValUpdate(g,'PropMode','Design',v.PROP_BLADES)
            v.SetParmValUpdate(g,'Y_Rel_Location','XForm',y)
        v.SetParmVal(recovery.linked_parameter(v),0)
        for g,rpm in zip(recovery.groups(v),(1200.,1700.)):v.SetParmVal(g['parameter'],rpm)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)

    def test_native_regeneration_restores_independent_speeds_and_cold_saved_record(self):
        self.fixture();v=self.v;before=self.model.read_bytes()
        state,saved=self.worker(dict(action='mutate',operation='rotor-speeds-save'))
        backup=state['tools']['rotorSpeedBackup'];self.assertTrue(backup['restoreReady'])
        self.assertEqual([g['rpm'] for g in backup['groups']],[1200.,1700.])
        original_ids={g['parameter'] for g in recovery.groups(v)}
        for prop in self.props:
            state,saved=self.worker(dict(action='mutate',operation='parameter',id=v.FindParm(prop,'PropMode','Design'),value=v.PROP_DISK),saved)
        self.assertFalse(state['tools']['rotorSpeedBackup']['restoreReady'])
        for prop in self.props:
            state,saved=self.worker(dict(action='mutate',operation='parameter',id=v.FindParm(prop,'PropMode','Design'),value=v.PROP_BLADES),saved)
        state,saved=self.worker(dict(action='mutate',operation='parameter',id=recovery.linked_parameter(v),value=1),saved)
        v.ClearVSPModel();v.ReadVSPFile(str(saved));v.Update()
        current=recovery.groups(v);self.assertTrue(original_ids.isdisjoint({g['parameter'] for g in current}))
        # Independent official SDK replay supplies every expected parameter
        # and complete surface; production restore must reach the same state.
        v.SetParmVal(recovery.linked_parameter(v),backup['linked'])
        bykey={json.dumps(g['key']):g for g in current}
        for g in backup['groups']:v.SetParmVal(bykey[json.dumps(g['key'])]['parameter'],g['rpm'])
        v.Update();direct=self.path/'direct.vsp3';v.WriteVSPFile(str(direct),v.SET_ALL)
        expected,_=self.worker(dict(action='state'),direct)
        actual,restored=self.worker(dict(action='mutate',operation='rotor-speeds-restore'),saved)
        self.assertEqual(actual['components'],expected['components'])
        self.assertEqual(actual['tools']['rotatingGroups'],expected['tools']['rotatingGroups'])
        cold,_=self.worker(dict(action='state'),restored)
        self.assertEqual(cold['tools']['rotorSpeedBackup'],backup)
        self.assertEqual(cold['tools']['rotatingGroups'],actual['tools']['rotatingGroups'])
        self.assertEqual(self.model.read_bytes(),before)

    def test_linked_speed_setting_restores_original_native_coupling(self):
        self.fixture();v=self.v
        for g in recovery.groups(v):v.SetParmVal(g['parameter'],2300.)
        v.SetParmVal(recovery.linked_parameter(v),1)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,saved=self.worker(dict(action='mutate',operation='rotor-speeds-save'))
        backup=state['tools']['rotorSpeedBackup']
        self.assertEqual(backup['linked'],1);self.assertEqual({g['rpm'] for g in backup['groups']},{2300.})
        state,saved=self.worker(dict(action='mutate',operation='parameter',id=recovery.linked_parameter(v),value=0),saved)
        state,saved=self.worker(dict(action='mutate',operation='parameter',id=recovery.groups(v)[0]['parameter'],value=3100.),saved)
        state,restored=self.worker(dict(action='mutate',operation='rotor-speeds-restore'),saved)
        v.ClearVSPModel();v.ReadVSPFile(str(restored));v.Update()
        self.assertEqual(v.GetParmVal(recovery.linked_parameter(v)),1.)
        self.assertEqual({g['rpm'] for g in recovery.groups(v)},{2300.})

    def test_membership_mismatch_rejected_before_any_aircraft_change(self):
        self.fixture();state,saved=self.worker(dict(action='mutate',operation='rotor-speeds-save'))
        pid=self.v.FindParm(self.props[0],'PropMode','Design')
        state,saved=self.worker(dict(action='mutate',operation='parameter',id=pid,value=self.v.PROP_DISK),saved)
        before=saved.read_bytes()
        with self.assertRaisesRegex(ValueError,'surface copies do not match'):
            self.worker(dict(action='mutate',operation='rotor-speeds-restore'),saved)
        self.assertEqual(saved.read_bytes(),before)

    def test_invalid_saved_metadata_and_no_rotors_are_recoverable(self):
        v=self.v
        with self.assertRaisesRegex(ValueError,'rotating propeller blades'):recovery.mutate(v,'rotor-speeds-save')
        v.AddAttributeString(v.GetChildCollection(v.GetVehicleID()),recovery.ATTRIBUTE,'{"version":1,"linked":0,"groups":[]}')
        self.assertFalse(recovery.configuration(v)['restoreReady'])
        with self.assertRaisesRegex(ValueError,'record is invalid'):recovery.mutate(v,'rotor-speeds-restore')
        self.fixture();recovery.mutate(v,'rotor-speeds-save')
        self.assertTrue(recovery.configuration(v)['restoreReady'])

if __name__=='__main__':unittest.main()
