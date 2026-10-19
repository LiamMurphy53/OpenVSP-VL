"""Edit stored native configurations without applying them to the aircraft."""
import sys,unittest
import test_native

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class PresetValues(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;v.ClearVSPModel();self.geom=v.AddGeom('POD');self.length=v.FindParm(self.geom,'Length','Design');self.ratio=v.FindParm(self.geom,'FineRatio','Design')
        self.group=v.AddVarPresetGroup('Flight');v.AddVarPresetParm(self.group,self.length);v.AddVarPresetParm(self.group,self.ratio)
        self.setting=v.AddVarPresetSetting(self.group,'Cruise');v.SaveVarPresetParmVals(self.group,self.setting)
        self.other=v.AddVarPresetSetting(self.group,'Other');v.SaveVarPresetParmVals(self.group,self.other)
        self.mode=v.CreateAndAddMode('Flight mode',v.SET_ALL,-1);v.ModeAddGroupSetting(self.mode,self.group,self.setting)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)

    def surfaces(self):
        v=self.v;out=[]
        for i in range(v.GetTotalNumSurfs(self.geom)):
            u,w=v.GetUWTess01(self.geom,i%v.GetNumMainSurfs(self.geom));out.append([[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(self.geom,i,[x for x in u for _ in w],[y for _ in u for y in w])])
        return out

    def test_stored_edit_and_native_mode_application(self):
        self.fixture();v=self.v;before=self.model.read_bytes();original=self.surfaces();other=list(v.GetVarPresetParmVals(self.other))
        entries=[dict(parameter=self.length,value=12.),dict(parameter=self.ratio,value=9.)]
        for e in entries:v.SetVarPresetParmVal(self.group,self.setting,e['parameter'],e['value'])
        expected=list(v.GetVarPresetParmVals(self.setting));v.Update();self.assertEqual(self.surfaces(),original)
        state,path=self.worker(dict(action='mutate',operation='preset-setting-values',group=self.group,setting=self.setting,entries=entries))
        preset=next(p for p in state['tools']['presets'] if p['id']==self.group)
        self.assertEqual(preset['parameters'],[self.length,self.ratio]);self.assertEqual(next(s['values'] for s in preset['settings'] if s['id']==self.setting),expected);self.assertEqual(next(s['values'] for s in preset['settings'] if s['id']==self.other),other)
        self.assertEqual([s['points'] for s in state['components'][0]['surfaces']],original)
        cold,_=self.worker(dict(action='state'),path);self.assertEqual(cold['tools']['presets'],state['tools']['presets']);self.assertEqual(cold['components'][0]['surfaces'],state['components'][0]['surfaces'])
        v.ApplyModeSettings(self.mode);v.Update();geometry=self.surfaces()
        for operation,fields in [('preset-apply',dict(group=self.group,setting=self.setting)),('mode-apply',dict(id=self.mode))]:
            changed,_=self.worker(dict(action='mutate',operation=operation,**fields),path)
            self.assertEqual([s['points'] for s in changed['components'][0]['surfaces']],geometry)
            self.assertEqual(next(p['value'] for p in changed['components'][0]['params'] if p['id']==self.length),12.)
        self.assertEqual(self.model.read_bytes(),before)

    def test_invalid_requests_preserve_stored_values(self):
        self.fixture();before=self.model.read_bytes();valid=dict(parameter=self.length,value=12.)
        for entries in [[],{},[valid,valid],[valid,dict(parameter='missing',value=3.)],[valid,dict(parameter=self.ratio,value=True)],[valid,dict(parameter=self.ratio,value=float('inf'))],[None]]:
            with self.subTest(entries=entries),self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='preset-setting-values',group=self.group,setting=self.setting,entries=entries))
        v=self.v;other=v.AddVarPresetGroup('Unrelated');v.AddVarPresetParm(other,self.length);wrong=v.AddVarPresetSetting(other,'Wrong');v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='preset-setting-values',group=self.group,setting=wrong,entries=[valid]))
        self.assertEqual(self.model.read_bytes(),before)

    def test_locked_aircraft_can_store_but_cannot_apply_conflicting_configuration(self):
        self.fixture();_,path=self.worker(dict(action='mutate',operation='property-lock',parameters=[self.length],locked=True))
        state,path=self.worker(dict(action='mutate',operation='preset-setting-values',group=self.group,setting=self.setting,entries=[dict(parameter=self.length,value=12.)]),path);before=path.read_bytes()
        self.assertEqual(next(s['values'][0] for p in state['tools']['presets'] for s in p['settings'] if s['id']==self.setting),12.)
        for op,fields in [('preset-apply',dict(group=self.group,setting=self.setting)),('mode-apply',dict(id=self.mode))]:
            with self.assertRaisesRegex(ValueError,'locked'):self.worker(dict(action='mutate',operation=op,**fields),path)
            self.assertEqual(path.read_bytes(),before)

if __name__=='__main__':unittest.main()
