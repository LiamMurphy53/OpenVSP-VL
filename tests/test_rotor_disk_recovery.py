"""Regenerated disks restore original native drivers and values atomically."""
import sys,unittest
import test_native,native_rotor_disks as recovery,native_references
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class RotorDiskRecovery(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self,manual=True):
        v=self.v;self.prop=v.AddGeom('PROP');v.SetParmValUpdate(self.prop,'PropMode','Design',v.PROP_DISK);v.Update()
        cid=v.FindActuatorDisk(0);p={v.GetParmName(x):x for x in v.FindContainerParmIDs(cid)}
        v.SetParmVal(p['RotorRPM'],1400.);v.SetParmVal(p['RotorCT'],.3);v.SetParmVal(p['RotorCP'],.45)
        v.SetParmVal(p['AutoHubDiaFlag'],0 if manual else 1)
        if manual:v.SetParmVal(p['RotorHubDiameter'],.75)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)

    def test_regenerated_identity_and_changed_drivers_restore_native_inputs_and_full_geometry(self):
        self.fixture();v=self.v;before=self.model.read_bytes();original=v.FindActuatorDisk(0)
        state,saved=self.worker(dict(action='mutate',operation='rotor-disks-save'))
        backup=state['tools']['rotorDiskBackup'];self.assertTrue(backup['restoreReady'])
        mode=v.FindParm(self.prop,'PropMode','Design')
        state,saved=self.worker(dict(action='mutate',operation='parameter',id=mode,value=v.PROP_BLADES),saved)
        self.assertFalse(state['tools']['rotorDiskBackup']['restoreReady'])
        state,saved=self.worker(dict(action='mutate',operation='parameter',id=mode,value=v.PROP_DISK),saved)
        current=state['tools']['disks'][0]['id'];self.assertNotEqual(original,current)
        state,saved=self.worker(dict(action='mutate',operation='rotor-disk-drivers',id=current,choices=[0,3,6]),saved)
        pre=saved.read_bytes()
        actual,restored=self.worker(dict(action='mutate',operation='rotor-disks-restore'),saved)
        self.assertEqual(saved.read_bytes(),pre)
        d=actual['tools']['disks'][0];self.assertEqual(d['driverChoices'],[0,1,2])
        p={p['name']:p['value'] for p in d['params']}
        self.assertEqual((p['RotorRPM'],p['RotorCT'],p['RotorCP'],p['AutoHubDiaFlag'],p['RotorHubDiameter']),(1400.,.3,.45,0.,.75))
        # Independent matching native XML choice write, followed by original
        # SDK parameter assignment and original engine geometry evaluation.
        v.ClearVSPModel();v.ReadVSPFile(str(saved));v.Update();v.SetVSP3FileName(str(self.path/'direct.vsp3'))
        try:native_references.set_references(v,current,'Rotor',{'DriverGroup/ChoiceVec':'0, 1, 2, '})
        except native_references.ReloadRequired:pass
        v.ClearVSPModel();v.ReadVSPFile(str(self.path/'direct.vsp3'));v.Update()
        p={v.GetParmName(x):x for x in v.FindContainerParmIDs(v.FindActuatorDisk(0))}
        for name,x in [('AutoHubDiaFlag',0),('RotorHubDiameter',.75),('RotorRPM',1400.),('RotorCT',.3),('RotorCP',.45)]:v.SetParmVal(p[name],x)
        v.Update();v.WriteVSPFile(str(self.path/'direct.vsp3'),v.SET_ALL)
        expected,_=self.worker(dict(action='state'),self.path/'direct.vsp3')
        self.assertEqual(actual['components'],expected['components']);self.assertEqual(actual['tools']['disks'],expected['tools']['disks'])
        cold,_=self.worker(dict(action='state'),restored);self.assertEqual(cold['tools']['rotorDiskBackup'],backup)
        self.assertEqual(self.model.read_bytes(),before)

    def test_missing_disk_and_smaller_diameter_reject_without_source_changes(self):
        self.fixture();v=self.v;_,saved=self.worker(dict(action='mutate',operation='rotor-disks-save'))
        for name,group,x,message in [('Diameter','Design',.5,'manual hub exceeds'),('PropMode','Design',v.PROP_BLADES,'native surface copies do not match')]:
            state,path=self.worker(dict(action='mutate',operation='parameter',id=v.FindParm(self.prop,name,group),value=x),saved)
            before=path.read_bytes();self.assertFalse(state['tools']['rotorDiskBackup']['restoreReady'])
            with self.assertRaisesRegex(ValueError,message):self.worker(dict(action='mutate',operation='rotor-disks-restore'),path)
            self.assertEqual(path.read_bytes(),before)

    def test_automatic_hub_uses_current_native_geometry(self):
        self.fixture(manual=False);v=self.v;_,saved=self.worker(dict(action='mutate',operation='rotor-disks-save'))
        _,saved=self.worker(dict(action='mutate',operation='parameter',id=v.FindParm(self.prop,'Diameter','Design'),value=12.),saved)
        actual,restored=self.worker(dict(action='mutate',operation='rotor-disks-restore'),saved)
        p={p['name']:p['value'] for p in actual['tools']['disks'][0]['params']}
        self.assertEqual(p['RotorDiameter'],12.);self.assertEqual(p['AutoHubDiaFlag'],1.)
        v.ClearVSPModel();v.ReadVSPFile(str(restored));v.Update();cid=v.FindActuatorDisk(0)
        native={v.GetParmName(x):v.GetParmVal(x) for x in v.FindContainerParmIDs(cid)}
        self.assertEqual(p,native)

if __name__=='__main__':unittest.main()
