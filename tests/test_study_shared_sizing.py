"""Shared assembly controllers preserve separate sizing and original native meshes."""
import unittest
import test_studies,test_assembly_mesh
import native_studies as studies,native_service as service,native_mesh
from native_worker import errors
from mesh_io import read_gmsh

class StudySharedSizing(unittest.TestCase):
    setUpClass=classmethod(test_studies.NativeStudies.setUpClass.__func__)
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    save=test_studies.NativeStudies.save
    wait=test_studies.NativeStudies.wait

    def test_shared_basis_sweep_applies_to_separate_member_settings_and_matches_native(self):
        test_assembly_mesh.AssemblyMesh.fixture(self);v=self.v;before=self.model.read_bytes()
        settings=[dict(BaseAbsRel=v.ABS,BaseLen=1.+i,BaseLenFrac=.25+.10*i,MinLen=.2,MaxGap=.03) for i in range(2)]
        stage=dict(name='FeaAssemblyMesh',structure=self.aid,formats=['GMSH'],inputs=[],memberInputs=[dict(id=sid,inputs=[dict(name=n,index=0,values=[x]) for n,x in row.items()]) for sid,row in zip(self.members,settings)])
        plan=self.save([dict(kind='input',stage=0,name='BaseAbsRel',values=[v.ABS,v.REL])],[stage])
        frozen=studies.study_folder(plan['id'])/'aircraft.vsp3';frozen_bytes=frozen.read_bytes()
        batch=self.wait(plan['id'],studies.launch(plan['id'])['id']);self.assertEqual(batch['status'],'complete')
        effective=[]
        for case in batch['cases']:
            basis=case['values'][0];job=service.job_state(case['stages'][0]['job']);self.assertEqual(job['status'],'complete');actual=read_gmsh(service.job_folder(job['id'])/'assembly.msh')
            effective.append([m['values']['BaseLen'] for m in job['result']['generatedMemberSizing']])
            for member,row in zip(job['result']['memberSizing'],settings):
                self.assertEqual(member['values']['BaseAbsRel'],basis)
                driving='BaseLen' if basis==v.ABS else 'BaseLenFrac';self.assertEqual(member['values'][driving],row[driving])
            v.ClearVSPModel();v.ReadVSPFile(str(frozen));v.Update();direct=self.path/('original-basis-'+str(basis));direct.mkdir()
            for sid,row in zip(self.members,settings):
                gid=v.GetFeaStructParentGeomID(sid);index=v.GetFeaStructIndex(sid);p=native_mesh.sizing_parameters(v,sid)
                v.SetParmVal(p['BaseAbsRel'],basis)
                for n in ['BaseLen' if basis==v.ABS else 'BaseLenFrac','MinLen','MaxGap']:v.SetParmVal(p[n],row[n])
                v.Update();v.SetFeaMeshFileName(gid,index,v.FEA_GMSH_FILE_NAME,str(direct/(sid+'.msh')));v.ComputeFeaMesh(sid,v.FEA_GMSH_FILE_NAME);errors(v)
            for pid in v.FindContainerParmIDs(self.aid):
                if v.GetParmGroupName(pid)=='ExportFEA' and v.GetParmName(pid).endswith('_Export'):v.SetParmVal(pid,int(v.GetParmName(pid)=='GMSH_Export'))
            v.SetFeaAssemblyFileName(self.aid,v.FEA_GMSH_FILE_NAME,str(direct/'assembly.msh'));v.ComputeFeaAssemblyMesh(self.aid);errors(v)
            self.assertEqual(job['result']['generatedMemberSizing'],native_mesh.assembly_schema(v,self.aid)['guide']['memberSizing'])
            expected=read_gmsh(direct/'assembly.msh')
            for key in ['nodeIDs','nodes','elements','groups']:self.assertEqual(actual[key],expected[key],(basis,key))
        self.assertNotEqual(effective[0],effective[1]);self.assertEqual(self.model.read_bytes(),before);self.assertEqual(frozen.read_bytes(),frozen_bytes)
