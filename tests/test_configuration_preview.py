"""Native preset/mode preview uses ordinary isolated transactions without committing."""
import unittest
import test_studies
import native_service as service

class ConfigurationPreview(unittest.TestCase):
    setUpClass=classmethod(test_studies.NativeStudies.setUpClass.__func__)
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown

    def fixture(self):
        v=self.v;self.pod=v.AddGeom('POD');self.length=v.FindParm(self.pod,'Length','Design');self.target=v.FindParm(self.gid,'X_Rel_Location','XForm')
        v.AddParmLink(self.length,self.target)
        self.group=v.AddVarPresetGroup('Preview dimensions');v.AddVarPresetParm(self.group,self.length)
        self.setting=v.AddVarPresetSetting(self.group,'Long');v.SetVarPresetParmVal(self.group,self.setting,self.length,12.)
        self.mode=v.CreateAndAddMode('Preview mode',v.SET_ALL,-1);v.ModeAddGroupSetting(self.mode,self.group,self.setting)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)

    def test_preset_and_mode_show_direct_and_linked_native_changes_without_commit(self):
        self.fixture();v=self.v;before=self.model.read_bytes();revision=service.REVISION;history=list(service.HISTORY)
        original_before={pid:v.GetParmVal(pid) for pid in [self.length,self.target]}
        v.ApplyVarPresetSetting(self.group,self.setting);v.Update()
        original_after={pid:v.GetParmVal(pid) for pid in [self.length,self.target]}
        for fields in [dict(configuration='preset',group=self.group,setting=self.setting),dict(configuration='mode',id=self.mode)]:
            with self.subTest(kind=fields['configuration']):
                result=service.query(dict(operation='configuration-preview',revision=revision,**fields))
                changes={p['idAfter']:p for p in result['changes']}
                for pid in [self.length,self.target]:
                    self.assertEqual(changes[pid]['after'],original_after[pid]);self.assertEqual(changes[pid]['before'],original_before[pid])
                self.assertEqual(self.model.read_bytes(),before);self.assertEqual(service.REVISION,revision);self.assertEqual(service.HISTORY,history)
                self.assertFalse(result['saved'])
                self.assertEqual(result['changes'][0]['idAfter'],self.length)
                self.assertTrue(changes[self.length]['selected']);self.assertFalse(changes[self.target]['selected'])
                self.assertEqual(changes[self.length]['unit'],'model length units')
        v.ApplyVarPresetSetting(self.group,self.setting);v.Update()
        for pid in [self.length,self.target]:self.assertEqual(changes[pid]['after'],v.GetParmVal(pid))

    def test_conflicting_lock_and_invalid_references_preserve_model_and_history(self):
        self.fixture();service.mutation(dict(operation='property-lock',parameters=[self.length],locked=True,revision=service.REVISION))
        before=self.model.read_bytes();history=list(service.HISTORY);revision=service.REVISION
        for fields,message in [(dict(configuration='preset',group=self.group,setting=self.setting),'locked'),(dict(configuration='mode',id=self.mode),'locked'),(dict(configuration='preset',group=self.group,setting='missing'),'no longer exists'),(dict(configuration='bad'),'preset or mode')]:
            with self.subTest(fields=fields):
                with self.assertRaisesRegex(ValueError,message):service.query(dict(operation='configuration-preview',revision=revision,**fields))
                self.assertEqual(self.model.read_bytes(),before);self.assertEqual(service.HISTORY,history);self.assertEqual(service.REVISION,revision)

    def test_unchanged_native_configuration_has_no_false_parameter_changes(self):
        self.fixture();v=self.v;v.SetVarPresetParmVal(self.group,self.setting,self.length,v.GetParmVal(self.length));v.WriteVSPFile(str(self.model),v.SET_ALL)
        before=self.model.read_bytes()
        result=service.query(dict(operation='configuration-preview',configuration='preset',group=self.group,setting=self.setting,revision=service.REVISION))
        self.assertEqual(result['changes'],[])
        self.assertEqual(self.model.read_bytes(),before)
