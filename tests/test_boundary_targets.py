"""Active scoped boundary conditions require a current native target."""
import sys,unittest,subprocess
from pathlib import Path
import test_native,vsp_runtime,native_boundary_controls,native_mesh

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class BoundaryTargets(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self,scope=None):
        v=self.v;self.index=v.AddFeaStruct(self.gid);self.sid=v.GetFeaStructID(self.gid,self.index)
        self.region=v.AddFeaSubSurf(self.gid,self.index,v.SS_RECTANGLE);v.SetFeaSubSurfName(self.region,'Root patch')
        self.bid=v.AddFeaBC(self.sid,v.FEA_BC_SUBSURF if scope is None else scope);v.SetContainerName(self.bid,'Patch support')
        v.SetParmVal(v.FindParm(self.bid,'ConMode','FeaBC'),v.FEA_BCM_PIN)
        for key,value in [('CFD_MAX_EDGE_LEN',1.),('CFD_MIN_EDGE_LEN',.2),('CFD_MAX_GAP',.03)]:v.SetFeaMeshVal(self.gid,self.index,getattr(v,key),value)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)

    def original(self,model):
        direct=self.path/'original.inp'
        script="import sys;sys.path.insert(0,"+repr(str(Path(vsp_runtime.__file__).parent))+");from vsp_runtime import load;v=load();v.ClearVSPModel();v.ReadVSPFile(sys.argv[1]);v.Update();v.SetFeaMeshFileName(sys.argv[2],int(sys.argv[3]),v.FEA_CALCULIX_FILE_NAME,sys.argv[4]);v.ComputeFeaMesh(sys.argv[2],int(sys.argv[3]),v.FEA_CALCULIX_FILE_NAME)"
        result=subprocess.run([vsp_runtime.interpreter(),'-c',script,str(model),self.gid,str(self.index),str(direct)],capture_output=True,text=True,timeout=120)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        return direct

    def test_missing_region_is_rejected_then_picker_repair_matches_original_export(self):
        self.fixture();v=self.v;saved=self.model.read_bytes()
        # The unmodified engine assigns nodes even though SubSurfID is empty.
        from native_boundary_results import read
        original_missing=read(self.original(self.model));self.assertGreater(original_missing['nodeCount'],0)
        with self.assertRaisesRegex(ValueError,'Patch support.*structural region'):
            self.worker(dict(action='analysis',name='FeaMeshAnalysis',structure=self.sid,formats=['CALCULIX']))
        self.assertEqual(self.model.read_bytes(),saved)
        state,path=self.worker(dict(action='mutate',operation='boundary-target',structure=self.sid,id=self.bid,target=self.region))
        b=next(b for b in state['tools']['boundaryConditions'] if b['id']==self.bid)
        self.assertEqual(b['references']['SubSurfID'],self.region)
        cold,_=self.worker(dict(action='state'),path)
        self.assertEqual(cold['tools']['boundaryConditions'],state['tools']['boundaryConditions'])
        before=path.read_bytes();result,out=self.worker(dict(action='analysis',name='FeaMeshAnalysis',structure=self.sid,formats=['CALCULIX']),path)
        self.assertEqual(out.read_bytes(),before);self.assertEqual(path.read_bytes(),before)
        self.assertEqual((out.parent/'structure.inp').read_bytes(),self.original(path).read_bytes())
        self.assertGreater(result['boundaryReport']['nodeCount'],0)
        self.assertLess(result['boundaryReport']['nodeCount'],original_missing['nodeCount'])

    def test_validation_preserves_parameters_paths_and_disabled_custom_conditions(self):
        self.fixture(self.v.FEA_BC_PART);v=self.v
        params={p:v.GetParmVal(p) for c in [self.sid,self.bid,self.gid,v.GetVehicleID()] for p in v.FindContainerParmIDs(c)}
        destination=str(self.path/'keep-custom.inp');v.SetFeaMeshFileName(self.gid,self.index,v.FEA_CALCULIX_FILE_NAME,destination)
        filename=v.GetVSPFileName()
        with self.assertRaisesRegex(ValueError,'structural part'):native_boundary_controls.validate_targets(v,[self.sid])
        self.assertEqual({p:v.GetParmVal(p) for p in params},params)
        self.assertEqual(v.GetFeaMeshFileName(self.gid,self.index,v.FEA_CALCULIX_FILE_NAME),destination)
        self.assertEqual(v.GetVSPFileName(),filename)
        v.SetParmVal(v.FindParm(self.bid,'ConMode','FeaBC'),v.FEA_BCM_USER);v.SetParmVal(v.FindParm(self.bid,'Constraints','FeaBC'),0)
        native_boundary_controls.validate_targets(v,[self.sid])
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        result,out=self.worker(dict(action='analysis',name='FeaMeshAnalysis',structure=self.sid,formats=['CALCULIX']))
        self.assertEqual(result['boundaryReport']['nodeCount'],0)
        v.SetParmVal(v.FindParm(self.bid,'Constraints','FeaBC'),1)
        with self.assertRaisesRegex(ValueError,'structural part'):native_boundary_controls.validate_targets(v,[self.sid])

    def test_later_assembly_member_missing_target_is_rejected_before_sizing(self):
        from test_assembly_mesh import AssemblyMesh
        AssemblyMesh.fixture(self);v=self.v
        sid=self.members[1];bid=v.AddFeaBC(sid,v.FEA_BC_SUBSURF);v.SetContainerName(bid,'Rear patch support');v.SetParmVal(v.FindParm(bid,'ConMode','FeaBC'),v.FEA_BCM_ALL)
        before={p:v.GetParmVal(p) for s in self.members+[self.aid,bid] for p in v.FindContainerParmIDs(s)}
        with self.assertRaisesRegex(ValueError,'Rear patch support'):
            native_mesh.run_assembly(v,dict(structure=self.aid,formats=['GMSH'],inputs=[dict(name='BaseLen',values=[.7])]))
        self.assertEqual({p:v.GetParmVal(p) for p in before},before)

    def test_foreign_region_is_rejected_and_local_region_repair_preserves_other_owner(self):
        import xml.etree.ElementTree as ET
        self.fixture();v=self.v
        other=v.AddGeom('WING');index=v.AddFeaStruct(other);sid=v.GetFeaStructID(other,index)
        foreign=v.AddFeaSubSurf(other,index,v.SS_RECTANGLE);v.SetFeaSubSurfName(foreign,'Root patch')
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        tree=ET.parse(self.model)
        node=next(n for n in tree.findall('.//FeaBCInfo') if n.findtext('ParmContainer/ID')==self.bid)
        node.find('ParmContainer/SubSurfID').text=foreign
        tree.write(self.model,encoding='utf-8',xml_declaration=True)
        saved=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'Patch support.*structural region'):
            self.worker(dict(action='analysis',name='FeaMeshAnalysis',structure=self.sid,formats=['CALCULIX']))
        self.assertEqual(self.model.read_bytes(),saved)
        state,path=self.worker(dict(action='mutate',operation='boundary-target',structure=self.sid,id=self.bid,target=self.region))
        self.assertEqual(next(b for b in state['tools']['boundaryConditions'] if b['id']==self.bid)['references']['SubSurfID'],self.region)
        self.assertTrue(any(r['id']==foreign and r['structure']==sid for r in state['tools']['structuralSubsurfaces']))
