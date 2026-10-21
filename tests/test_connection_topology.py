"""Saved assembly endpoints follow the original fixed-point copy topology."""
import sys,unittest
import test_native,test_assembly_mesh
import native_connection_controls as controls
import native_mesh

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class ConnectionTopology(unittest.TestCase):
    setUpClass=classmethod(test_assembly_mesh.AssemblyMesh.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    fixture=test_assembly_mesh.AssemblyMesh.fixture

    def test_symmetry_removed_copy_is_identified_and_repaired_atomically(self):
        self.fixture();v=self.v
        cid=v.GetFeaAssemblyConnectionID(self.aid,0)
        pid=v.FindParm(cid,'StartFixPtSurfIndex','Connection')
        catalog=controls.catalog(v,self.aid)
        self.assertEqual(len(catalog[0]['copies']),2)
        v.SetParmValUpdate(pid,1)
        self.assertEqual(controls.connection_issues(v,self.aid),[])
        owner=v.GetFeaStructParentGeomID(self.members[0])
        v.SetParmValUpdate(owner,'Sym_Planar_Flag','Sym',0)
        self.assertEqual(v.GetParmVal(pid),1,'Native connection retains the removed copy index')
        baseline={p:v.GetParmVal(p) for s in self.members+[self.aid] for p in v.FindContainerParmIDs(s)}
        v.SetFeaAssemblyFileName(self.aid,v.FEA_GMSH_FILE_NAME,str(self.path/'custom-destination.msh'))
        destination=v.GetFeaAssemblyFileName(self.aid,v.FEA_GMSH_FILE_NAME)
        issues=controls.inspect_assembly(v,self.aid)
        self.assertEqual(v.GetFeaAssemblyFileName(self.aid,v.FEA_GMSH_FILE_NAME),destination)
        self.assertEqual({p:v.GetParmVal(p) for s in self.members+[self.aid] for p in v.FindContainerParmIDs(s)},baseline,'Preflight must not refresh native meshing state in the caller')
        self.assertEqual(controls.connection_issues(v,self.aid),issues)
        self.assertEqual(len(controls.catalog(v,self.aid)[0]['copies']),1)
        self.assertEqual(len(issues),1)
        self.assertEqual((issues[0]['connection'],issues[0]['side']),(cid,'start'))
        self.assertIn('copy 1 is unavailable',issues[0]['message'])
        self.assertEqual(native_mesh.assembly_schema(v,self.aid)['guide']['connectionIssues'],issues)
        before={p:v.GetParmVal(p) for s in self.members+[self.aid] for p in v.FindContainerParmIDs(s)}
        with self.assertRaisesRegex(ValueError,'Repair the endpoints'):
            native_mesh.run_assembly(v,dict(structure=self.aid,formats=['GMSH'],inputs=[dict(name='BaseLen',values=[.7])]))
        self.assertEqual({p:v.GetParmVal(p) for s in self.members+[self.aid] for p in v.FindContainerParmIDs(s)},before)
        v.WriteVSPFile(str(self.model),v.SET_ALL);original=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'copy 1 is unavailable'):
            self.worker(dict(action='analysis',name='FeaAssemblyMesh',structure=self.aid,formats=['GMSH']))
        self.assertEqual(self.model.read_bytes(),original)
        first,second=controls.catalog(v,self.aid)
        request=dict(action='mutate',operation='assembly-connection-edit',assembly=self.aid,id=cid,
                     startStructure=first['structure'],startPoint=first['id'],startIndex=0,
                     endStructure=second['structure'],endPoint=second['id'],endIndex=1)
        state,path=self.worker(request)
        connection=state['tools']['assemblies'][0]['connections'][0]
        self.assertEqual(next(p['value'] for p in connection['params'] if p['id']==pid),0)
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        self.assertEqual(controls.connection_issues(v,self.aid),[])
        reopened,_=self.worker(dict(action='state'),path)
        self.assertEqual(reopened['tools']['assemblies'][0]['connections'],state['tools']['assemblies'][0]['connections'])

        # Repair leads to an actual native mesh, with exact original export parity.
        from mesh_io import read_gmsh
        saved=path.read_bytes()
        result,out=self.worker(dict(action='analysis',name='FeaAssemblyMesh',structure=self.aid,formats=['GMSH']),path)
        self.assertEqual(result['assemblyComputations'],1)
        self.assertEqual(path.read_bytes(),saved)
        self.assertEqual(out.read_bytes(),saved)
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        for p in v.FindContainerParmIDs(self.aid):
            if v.GetParmGroupName(p)=='ExportFEA' and v.GetParmName(p).endswith('_Export'):
                v.SetParmVal(p,int(v.GetParmName(p)=='GMSH_Export'))
        direct=self.path/'direct-repaired.msh'
        v.SetFeaAssemblyFileName(self.aid,v.FEA_GMSH_FILE_NAME,str(direct))
        v.ComputeFeaAssemblyMesh(self.aid)
        actual=read_gmsh(out.parent/'assembly.msh');expected=read_gmsh(direct)
        for key in ['nodeIDs','nodes','elements','groups']:self.assertEqual(actual[key],expected[key],key)
