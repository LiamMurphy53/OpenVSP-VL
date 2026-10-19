"""Native preset deletion otherwise leaves dangling mode setting IDs."""
import unittest
import test_preset_values

class PresetReferences(unittest.TestCase):
    setUpClass=test_preset_values.PresetValues.__dict__['setUpClass']
    setUp=test_preset_values.PresetValues.setUp
    tearDown=test_preset_values.PresetValues.tearDown
    worker=test_preset_values.PresetValues.worker
    fixture=test_preset_values.PresetValues.fixture
    surfaces=test_preset_values.PresetValues.surfaces
    def test_native_deletion_leaves_mode_reference_and_studio_rejects_it(self):
        for kind in ['setting','group']:
            with self.subTest(kind=kind):
                self.fixture();v=self.v;before=self.model.read_bytes()
                # Confirm the actual installed SDK does not clean this reference.
                if kind=='setting':v.DeleteVarPresetSetting(self.group,self.setting)
                else:v.DeleteVarPresetGroup(self.group)
                self.assertEqual(list(v.ModeGetAllGroups(self.mode)),[self.group]);self.assertEqual(list(v.ModeGetAllSettings(self.mode)),[self.setting])
                fields=dict(operation='preset-setting-delete',group=self.group,setting=self.setting) if kind=='setting' else dict(operation='preset-delete',id=self.group)
                with self.assertRaisesRegex(ValueError,'Flight mode.*Remove the included setting'):self.worker(dict(action='mutate',**fields))
                cold,_=self.worker(dict(action='state'));self.assertEqual(self.model.read_bytes(),before)
                self.assertTrue(any(p['id']==self.group and any(s['id']==self.setting for s in p['settings']) for p in cold['tools']['presets']))

    def test_unreferenced_sibling_can_be_deleted_and_detaching_allows_deletion(self):
        self.fixture();v=self.v
        state,path=self.worker(dict(action='mutate',operation='preset-setting-delete',group=self.group,setting=self.other))
        self.assertEqual([s['id'] for p in state['tools']['presets'] for s in p['settings']],[self.setting])
        before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'Flight mode'):self.worker(dict(action='mutate',operation='preset-delete',id=self.group),path)
        self.assertEqual(path.read_bytes(),before)
        state,path=self.worker(dict(action='mutate',operation='mode-preset-remove',id=self.mode,index=0),path)
        state,path=self.worker(dict(action='mutate',operation='preset-setting-delete',group=self.group,setting=self.setting),path)
        state,path=self.worker(dict(action='mutate',operation='preset-delete',id=self.group),path)
        self.assertEqual(state['tools']['presets'],[]);self.assertEqual(state['tools']['modes'][0]['groups'],[])
        v.RemoveGroupSetting(self.mode,0);v.DeleteVarPresetSetting(self.group,self.other);v.DeleteVarPresetSetting(self.group,self.setting);v.DeleteVarPresetGroup(self.group);v.ApplyModeSettings(self.mode);v.Update();expected=self.surfaces()
        state,path=self.worker(dict(action='mutate',operation='mode-apply',id=self.mode),path)
        self.assertEqual([s['points'] for s in state['components'][0]['surfaces']],expected)
        cold,_=self.worker(dict(action='state'),path);self.assertEqual(cold['tools']['presets'],[]);self.assertEqual(cold['tools']['modes'][0]['groups'],[])

    def test_all_referencing_modes_are_named(self):
        self.fixture();v=self.v;second=v.CreateAndAddMode('Landing mode',v.SET_ALL,-1);v.ModeAddGroupSetting(second,self.group,self.setting);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        with self.assertRaisesRegex(ValueError,'Flight mode, Landing mode'):self.worker(dict(action='mutate',operation='preset-setting-delete',group=self.group,setting=self.setting))

if __name__=='__main__':unittest.main()
