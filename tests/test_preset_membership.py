"""Original preset membership preserves settings, mode bindings and geometry."""
import unittest
import test_preset_values

class PresetMembership(unittest.TestCase):
    setUpClass=test_preset_values.PresetValues.__dict__['setUpClass']
    setUp=test_preset_values.PresetValues.setUp
    tearDown=test_preset_values.PresetValues.tearDown
    worker=test_preset_values.PresetValues.worker
    fixture=test_preset_values.PresetValues.fixture
    surfaces=test_preset_values.PresetValues.surfaces

    def test_native_membership_preserves_values_and_modes(self):
        self.fixture();v=self.v;position=v.FindParm(self.geom,'X_Rel_Location','XForm');v.SetParmValUpdate(position,3.)
        v.SetVarPresetParmVal(self.group,self.setting,self.length,12.);v.SetVarPresetParmVal(self.group,self.other,self.length,8.);v.WriteVSPFile(str(self.model),v.SET_ALL);original=self.surfaces();path=self.model
        for parameter,member in [(position,True),(self.ratio,False),(position,True),(self.length,False),(position,False)]:
            with self.subTest(parameter=parameter,member=member):
                current=list(v.GetVarPresetParmIDs(self.group))
                if member and parameter not in current:v.AddVarPresetParm(self.group,parameter)
                elif not member:v.DeleteVarPresetParm(self.group,parameter)
                expected=list(v.GetVarPresetParmIDs(self.group));values={s:list(v.GetVarPresetParmVals(s)) for s in [self.setting,self.other]}
                state,path=self.worker(dict(action='mutate',operation='preset-parameter',group=self.group,parameter=parameter,member=member),path)
                preset=next(p for p in state['tools']['presets'] if p['id']==self.group);self.assertEqual(preset['parameters'],expected);self.assertEqual({s['id']:s['values'] for s in preset['settings']},values)
                mode=next(m for m in state['tools']['modes'] if m['id']==self.mode);self.assertEqual(mode['groups'],[self.group]);self.assertEqual(mode['settings'],[self.setting]);self.assertEqual([s['points'] for s in state['components'][0]['surfaces']],original)
                cold,_=self.worker(dict(action='state'),path);self.assertEqual(cold['tools']['presets'],state['tools']['presets'])
                v.ApplyModeSettings(self.mode);v.Update();geometry=self.surfaces()
                applied,_=self.worker(dict(action='mutate',operation='mode-apply',id=self.mode),path);self.assertEqual([s['points'] for s in applied['components'][0]['surfaces']],geometry)
                # Restore reference current dimensions for next membership edit.
                v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()

    def test_invalid_membership_preserves_model(self):
        self.fixture();before=self.model.read_bytes()
        for fields in [dict(parameter='missing',member=True),dict(parameter='missing',member=False),dict(parameter=self.length,member=1),dict(group='missing',parameter=self.length,member=True)]:
            with self.subTest(fields=fields),self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='preset-parameter',**(dict(group=self.group)|fields)))
        self.assertEqual(self.model.read_bytes(),before)

if __name__=='__main__':unittest.main()
