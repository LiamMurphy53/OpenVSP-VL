"""Only the original selected absolute/relative sizing input can drive a case."""
import unittest
import test_studies,test_assembly_mesh
import native_mesh,native_service as service,native_studies as studies
class SizingSweepDrivers(unittest.TestCase):
    setUpClass=classmethod(test_studies.NativeStudies.setUpClass.__func__)
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    save=test_studies.NativeStudies.save
    wait=test_studies.NativeStudies.wait
    def test_all_native_basis_pairs_and_member_scopes_without_mutation(self):
        test_assembly_mesh.AssemblyMesh.fixture(self);v=self.v;before=self.model.read_bytes()
        for controller,(absolute,relative) in native_mesh.FEA_PAIRS.items():
            for mode,driver,follower in [(v.ABS,absolute,relative),(v.REL,relative,absolute)]:
                for assembly in [False,True]:
                    with self.subTest(controller=controller,mode=mode,assembly=assembly):
                        req=dict(name='FeaAssemblyMesh' if assembly else 'FeaMeshAnalysis',structure=self.aid if assembly else self.members[0],inputs=[dict(name=controller,values=[mode])],inputSweeps=[dict(kind='input',name=follower,**({'member':self.members[1]} if assembly else {}))])
                        with self.assertRaisesRegex(ValueError,'is calculated in this case'):native_mesh.validate_swept_sizing(v,req)
                        req['inputSweeps'][0]['name']=driver;native_mesh.validate_swept_sizing(v,req)
        self.assertEqual(self.model.read_bytes(),before)
    def test_single_structure_worker_rejects_calculated_input_before_meshing(self):
        test_assembly_mesh.AssemblyMesh.fixture(self);before=self.model.read_bytes()
        req=dict(action='analysis',name='FeaMeshAnalysis',structure=self.members[0],inputs=[dict(name='BaseAbsRel',values=[self.v.REL]),dict(name='BaseLenFrac',values=[.1])],inputSweeps=[dict(kind='input',name='BaseLen',value=1.)])
        with self.assertRaisesRegex(ValueError,'is calculated in this case'):test_studies.NativeStudies.worker(self,req)
        self.assertEqual(self.model.read_bytes(),before)
    def test_actual_case_stops_noop_sweep_and_recovers_with_fraction_driver(self):
        test_assembly_mesh.AssemblyMesh.fixture(self);v=self.v;before=self.model.read_bytes();sid=self.members[0]
        stage=dict(name='FeaAssemblyMesh',structure=self.aid,inputs=[],memberInputs=[dict(id=sid,inputs=[dict(name='BaseAbsRel',values=[v.REL]),dict(name='BaseLenFrac',values=[.1])])])
        plan=self.save([dict(kind='input',stage=0,member=sid,name='BaseLen',values=[1.])],[stage]);batch=self.wait(plan['id'],studies.launch(plan['id'])['id']);self.assertEqual(batch['status'],'failed',batch)
        job=service.job_state(batch['cases'][0]['stages'][0]['job']);self.assertIn('is calculated in this case',job.get('error',''));self.assertFalse((service.job_folder(job['id'])/'assembly.msh').exists())
        fixed=self.save([dict(kind='input',stage=0,member=sid,name='BaseLenFrac',values=[.08,.12])],[stage]);result=self.wait(fixed['id'],studies.launch(fixed['id'])['id']);self.assertEqual(result['status'],'complete',result)
        values=[service.job_state(c['stages'][0]['job'])['result']['generatedMemberSizing'][0]['values']['BaseLen'] for c in result['cases']];self.assertNotEqual(*values);self.assertEqual(self.model.read_bytes(),before)
