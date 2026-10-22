"""Saved geometry checks and their presets follow native set-content lifetimes."""
import unittest
import sys
import test_native
import test_geometry_cases
import native_components


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class CaseSetReferences(unittest.TestCase):
    setUpClass=classmethod(test_geometry_cases.NativeGeometryCases.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    fixture=test_geometry_cases.NativeGeometryCases.fixture
    case=test_geometry_cases.NativeGeometryCases.case
    direct=test_geometry_cases.NativeGeometryCases.direct
    canonical=test_geometry_cases.NativeGeometryCases.canonical
    assertResults=test_geometry_cases.NativeGeometryCases.assertResults

    def setup_case(self):
        self.fixture();v=self.v;cid=self.case('EXTERNAL_INTERFERENCE')
        primary=v.FindParm(cid,'PrimarySet','InterferenceCase');secondary=v.FindParm(cid,'SecondarySet','InterferenceCase')
        group=v.AddVarPresetGroup('Saved check targets');v.AddVarPresetParm(group,primary);v.AddVarPresetParm(group,secondary)
        setting=v.AddVarPresetSetting(group,'Reverse targets');v.SaveVarPresetParmVals(group,setting)
        v.SetVarPresetParmVal(group,setting,primary,4);v.SetVarPresetParmVal(group,setting,secondary,3)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return cid,primary,secondary,group,setting

    def test_reorder_preserves_case_geometry_results_and_preset_targets(self):
        v=self.v;cid,primary,secondary,group,setting=self.setup_case()
        expected=self.direct('GeometryAnalysis',{'CaseID':[cid]})
        order=[4,5,3,*range(6,v.GetNumSets())]
        state,path=self.worker(dict(action='mutate',operation='set-reorder',order=order))
        cold,_=self.worker(dict(action='state'),path)
        for result in (state,cold):
            refs=[r for r in result['tools']['setConfig']['references'] if r['id'] in (primary,secondary)]
            self.assertEqual(len(refs),4)
            self.assertEqual({r['id']:r['value'] for r in refs if 'group' not in r},{primary:5,secondary:3})
            self.assertEqual({r['id']:r['value'] for r in refs if 'group' in r},{primary:3,secondary:5})
            case=next(c for c in result['tools']['geometryCases'] if c['id']==cid)
            self.assertEqual({p['name']:p['value'] for p in case['params'] if p['name'] in ('PrimarySet','SecondarySet')},{'PrimarySet':5,'SecondarySet':3})
            self.assertIn(self.gid,result['tools']['sets'][5]['members']);self.assertIn(self.pod,result['tools']['sets'][3]['members'])
        data,_=self.worker(dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=[cid])]),path)
        self.assertResults(expected,data['results'])
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();self.assertEqual(list(v.GetVarPresetParmVals(setting)),[3,5])

    def test_shrink_requires_case_and_preset_replacement_before_saving(self):
        v=self.v;cid,primary,secondary,group,setting=self.setup_case()
        v.SetParmValUpdate(native_components.count_parameter(v),22)
        v.SetParmValUpdate(primary,24);v.SetParmValUpdate(secondary,23)
        v.SetVarPresetParmVal(group,setting,primary,23);v.SetVarPresetParmVal(group,setting,secondary,24)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'replacement sets'):
            self.worker(dict(action='mutate',operation='set-count',count=20))
        self.assertEqual(self.model.read_bytes(),before)
        refs=[r for r in native_components.references(v) if r['id'] in (primary,secondary)]
        self.assertEqual(len(refs),4)
        replacements={r['key']:(3 if r['id']==primary else 4) for r in refs}
        partial=dict(replacements);partial.pop(next(k for k in partial if k.startswith('preset:')))
        with self.assertRaisesRegex(ValueError,'replacement sets'):
            self.worker(dict(action='mutate',operation='set-count',count=20,replacements=partial))
        self.assertEqual(self.model.read_bytes(),before)
        state,path=self.worker(dict(action='mutate',operation='set-count',count=20,replacements=replacements))
        cold,_=self.worker(dict(action='state'),path)
        for result in (state,cold):
            got={r['key']:r['value'] for r in result['tools']['setConfig']['references'] if r['id'] in (primary,secondary)}
            self.assertEqual(got,replacements)
