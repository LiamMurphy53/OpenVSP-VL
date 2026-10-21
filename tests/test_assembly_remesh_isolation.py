"""Repeated Studio assembly runs match explicitly regenerated native member meshes."""
import unittest,json
import test_native,test_assembly_mesh
import native_mesh
from mesh_io import read_gmsh
from vsp_runtime import load
from native_worker import errors

class AssemblyRemeshIsolation(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    def test_fine_coarse_fine_uses_fresh_workers_and_matches_original_regeneration(self):
        test_assembly_mesh.AssemblyMesh.fixture(self);v=self.v;before=self.model.read_bytes();meshes=[];processes=[]
        for index,fraction in enumerate([.08,.12,.08]):
            req=dict(action='analysis',name='FeaAssemblyMesh',structure=self.aid,formats=['GMSH','CALCULIX'],inputs=[],memberInputs=[dict(id=self.members[0],inputs=[dict(name=n,values=[x]) for n,x in dict(BaseAbsRel=v.REL,BaseLenFrac=fraction,MinAbsRel=v.REL,MinFrac=.2,MaxGapAbsRel=v.REL,MaxGapFrac=.02).items()]),dict(id=self.members[1],inputs=[dict(name='BaseLen',values=[1.6]),dict(name='MinLen',values=[.25])])])
            result,out=self.worker(req);actual=read_gmsh(out.parent/'assembly.msh');meshes.append(actual);processes.append(json.loads((out.parent/'worker-exit.json').read_text())['processID'])
            direct=self.path/('regenerated-'+str(index));direct.mkdir();v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
            for member in result['memberSizing']:
                sid=member['id'];values=member['values'];parameters=list(v.FindContainerParmIDs(sid));followers={pair[1] if values[controller]==v.ABS else pair[0] for controller,pair in native_mesh.FEA_PAIRS.items()}
                for name,value in values.items():
                    if name in followers:continue
                    native_name,group=native_mesh.FEA_PARAMETERS[name];pid=next(p for p in parameters if v.GetParmName(p)==native_name and v.GetParmGroupName(p)==group);v.SetParmVal(pid,value)
            v.Update()
            # The original assembly API skips already-meshed structures in a warm
            # process. Explicit original ComputeFeaMesh regenerates every member.
            for sid in self.members:
                gid=v.GetFeaStructParentGeomID(sid);i=v.GetFeaStructIndex(sid)
                v.SetFeaMeshFileName(gid,i,v.FEA_GMSH_FILE_NAME,str(direct/(sid+'.msh')));v.ComputeFeaMesh(sid,v.FEA_GMSH_FILE_NAME);errors(v)
            for pid in v.FindContainerParmIDs(self.aid):
                if v.GetParmGroupName(pid)=='ExportFEA' and v.GetParmName(pid).endswith('_Export'):v.SetParmVal(pid,int(v.GetParmName(pid) in ['GMSH_Export','CALCULIX_Export']))
            v.SetFeaAssemblyFileName(self.aid,v.FEA_GMSH_FILE_NAME,str(direct/'assembly.msh'));v.SetFeaAssemblyFileName(self.aid,v.FEA_CALCULIX_FILE_NAME,str(direct/'assembly.inp'));v.ComputeFeaAssemblyMesh(self.aid);errors(v)
            expected=read_gmsh(direct/'assembly.msh')
            for key in ['nodeIDs','nodes','elements','groups']:self.assertEqual(actual[key],expected[key],(index,key))
            self.assertEqual((out.parent/'assembly.inp').read_bytes(),(direct/'assembly.inp').read_bytes())
            self.assertEqual(out.read_bytes(),before)
        self.assertEqual(len(set(processes)),3)
        self.assertNotEqual(meshes[0]['nodes'],meshes[1]['nodes'])
        for key in ['nodeIDs','nodes','elements','groups']:self.assertEqual(meshes[0][key],meshes[2][key])
        self.assertEqual(self.model.read_bytes(),before)
