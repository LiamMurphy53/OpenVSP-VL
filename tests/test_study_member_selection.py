"""Saved assembly studies reject orphan member settings without replacing a plan."""
import copy,unittest
import test_studies
import test_assembly_mesh
import native_studies as studies,native_service as service
class StudyMemberSelection(unittest.TestCase):
    setUpClass=classmethod(test_studies.NativeStudies.setUpClass.__func__)
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    save=test_studies.NativeStudies.save
    def test_rejected_member_and_sweep_preserve_saved_plan_then_matching_member_recovers(self):
        test_assembly_mesh.AssemblyMesh.fixture(self);v=self.v;other=v.AddFeaAssembly();v.AddFeaAssemblyStructure(other,self.members[0]);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        stage=dict(name='FeaAssemblyMesh',structure=self.aid,inputs=[],memberInputs=[dict(id=sid,inputs=[dict(name='BaseLen',values=[value])]) for sid,value in zip(self.members,[1.,1.6])])
        plan=self.save([dict(kind='input',stage=0,member=self.members[0],name='BaseLen',values=[1.,1.2])],[stage]);saved=studies.definition(plan['id'])
        def update(candidate,axes):return studies.save_study(dict(id=plan['id'],definitionVersion=saved['version'],name=saved['name'],baseline='saved',revision=service.REVISION,stages=[candidate],axes=axes))
        replacement=copy.deepcopy(stage);replacement['structure']=other
        with self.assertRaises(ValueError):update(replacement,saved['axes'])
        self.assertEqual(studies.definition(plan['id']),saved)
        replacement.pop('memberInputs');replacement['inputs']=[dict(name='BaseLen',values=[1.])]
        wrong=copy.deepcopy(saved['axes']);wrong[0]['member']=self.members[1]
        with self.assertRaises(ValueError):update(replacement,wrong)
        self.assertEqual(studies.definition(plan['id']),saved)
        recovered=update(replacement,saved['axes']);self.assertEqual(recovered['stages'][0]['structure'],other);self.assertEqual(recovered['axes'][0]['member'],self.members[0]);self.assertEqual(self.model.read_bytes(),before)
