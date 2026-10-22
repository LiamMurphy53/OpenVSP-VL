"""Geometry-owned extension references follow set moves and prevent stale slots."""
import unittest
import test_native
import native_components


class EngineSetReferences(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;g=v.AddGeom('FUSELAGE');v.SetGeomName(g,'Flowpath reference owner')
        pid=v.FindParm(g,'AutoExtensionSet','EngineModel')
        v.SetParmValUpdate(native_components.count_parameter(v),22)
        v.SetParmValUpdate(pid,24)
        group=v.AddVarPresetGroup('Extension references');v.AddVarPresetParm(group,pid)
        setting=v.AddVarPresetSetting(group,'Saved extension')
        v.SaveVarPresetParmVals(group,setting);v.SetVarPresetParmVal(group,setting,pid,23)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return g,pid,group,setting

    def test_shrink_requires_both_geometry_and_preset_reassignment(self):
        v=self.v;g,pid,group,setting=self.fixture();before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'Flowpath extension reference set'):
            self.worker(dict(action='mutate',operation='set-count',count=20))
        self.assertEqual(self.model.read_bytes(),before)
        refs=[r for r in native_components.references(v) if r['id']==pid]
        self.assertEqual(len(refs),2)
        replacements={r['key']:3 if 'group' not in r else 4 for r in refs}
        state,path=self.worker(dict(action='mutate',operation='set-count',count=20,replacements=replacements))
        cold,_=self.worker(dict(action='state'),path)
        for result in (state,cold):
            actual={r['key']:r['value'] for r in result['tools']['setConfig']['references'] if r['id']==pid}
            self.assertEqual(actual,replacements)

    def test_reorder_keeps_extension_target_and_preset_contents(self):
        v=self.v;g,pid,group,setting=self.fixture()
        v.SetSetName(24,'Extension envelope');v.SetSetName(23,'Saved envelope')
        v.SetSetFlag(g,24,True);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        order=list(range(3,v.GetNumSets()));order[0],order[-1]=order[-1],order[0]
        state,path=self.worker(dict(action='mutate',operation='set-reorder',order=order))
        refs=[r for r in state['tools']['setConfig']['references'] if r['id']==pid]
        self.assertEqual({r['value'] for r in refs},{3,23})
        self.assertEqual(state['tools']['sets'][3]['name'],'Extension envelope')
        self.assertIn(g,state['tools']['sets'][3]['members'])
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        self.assertEqual(v.GetParmVal(pid),3)
        self.assertEqual(list(v.GetVarPresetParmVals(setting)),[23])
