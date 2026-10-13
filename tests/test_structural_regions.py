"""Structural array expansion and native region identity/reference preservation."""
import sys
import unittest
import test_native
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class StructuralRegions(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;i=v.AddFeaStruct(self.gid);self.sid=v.GetFeaStructID(self.gid,i);self.index=i
        self.array=v.AddFeaSubSurf(self.gid,i,v.SS_LINE_ARRAY);v.SetFeaSubSurfName(self.array,'Stiffeners')
        self.rect=v.AddFeaSubSurf(self.gid,i,v.SS_RECTANGLE);v.SetFeaSubSurfName(self.rect,'Patch')
        for n,x in [('ConstLineType',v.CONST_U),('StartLocation',.2),('EndLocation',.8),('Spacing',.2),('CreateBeamElements',1)]:v.SetParmVal(v.FindParm(self.array,n,'SS_LineArray' if n in ('ConstLineType','StartLocation','EndLocation','Spacing') else 'SubSurface'),x)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return self.model

    def test_array_expansion_matches_direct_native_lines_properties_and_mesh(self):
        from mesh_io import read_gmsh
        self.fixture();v=self.v
        v.ExportFile(str(self.path/'direct-structure.igs'),v.SET_ALL,v.EXPORT_IGES_STRUCTURE)
        v.IndividualizeFeaPart(self.gid,self.index,self.array);v.Update()
        keys=('Const_Line_Value','Const_Line_Type','Value_01','MainSurfIndx','FeaPropertyIndex','CapFeaPropertyIndex','CreateBeamElements','KeepDelShellElements')
        def values(p):return {v.GetParmName(x):v.GetParmVal(x) for x in v.FindContainerParmIDs(p) if v.GetParmName(x) in keys}
        expected=[(v.GetFeaSubSurfName(p),values(p)) for p in v.GetFeaSubSurfIDVec(self.sid)]
        native=self.path/'direct.vsp3';v.WriteVSPFile(str(native),v.SET_ALL)
        state,path=self.worker(dict(action='mutate',operation='structural-subsurface-individualize',structure=self.sid,id=self.array))
        actual=[(p['name'],{x['name']:x['value'] for x in p['params'] if x['name'] in keys}) for p in state['tools']['structuralSubsurfaces']]
        self.assertEqual(actual,expected);self.assertNotIn(self.array,[p['id'] for p in state['tools']['structuralSubsurfaces']]);self.assertGreater(len(actual),2)
        self.assertTrue(all(p['type']==v.SS_LINE for p in state['tools']['structuralSubsurfaces'] if p['id']!=self.rect))
        req=dict(action='analysis',name='FeaMeshAnalysis',structure=self.sid,formats=['GMSH'],inputs=[dict(name=n,values=[x]) for n,x in [('BaseLen',1.),('MinLen',.2),('MaxGap',.03)]])
        _,a=self.worker(req,path);_,b=self.worker(req,native);ma=read_gmsh(a.parent/'structure.msh');mb=read_gmsh(b.parent/'structure.msh')
        self.assertEqual(ma['nodes'],mb['nodes']);self.assertEqual(ma['elements'],mb['elements']);self.assertEqual(ma['groups'],mb['groups'])

    def test_native_region_reorder_rename_preserve_ids_and_other_owners(self):
        self.fixture();baseline,_=self.worker(dict(action='state'))
        original={p['id']:{x['id']:x['value'] for x in p['params']} for p in baseline['tools']['structuralSubsurfaces']}
        state,path=self.worker(dict(action='mutate',operation='structural-subsurface-reorder',structure=self.sid,id=self.rect,direction='REORDER_MOVE_TOP'))
        self.assertEqual([p['id'] for p in state['tools']['structuralSubsurfaces']],[self.rect,self.array])
        self.assertEqual(original,{p['id']:{x['id']:x['value'] for x in p['params']} for p in state['tools']['structuralSubsurfaces']})
        before_ids={p['id']:{x['id'] for x in p['params']} for p in state['tools']['structuralSubsurfaces']}
        state,path=self.worker(dict(action='mutate',operation='structural-subsurface-rename',structure=self.sid,id=self.rect,name='Load patch'),path)
        self.assertEqual(state['tools']['structuralSubsurfaces'][0]['name'],'Load patch')
        self.assertEqual(before_ids,{p['id']:{x['id'] for x in p['params']} for p in state['tools']['structuralSubsurfaces']})
        for direction,expected in [('REORDER_MOVE_BOTTOM',[self.array,self.rect]),('REORDER_MOVE_UP',[self.rect,self.array]),('REORDER_MOVE_DOWN',[self.array,self.rect])]:
            state,path=self.worker(dict(action='mutate',operation='structural-subsurface-reorder',structure=self.sid,id=self.rect,direction=direction),path)
            self.assertEqual([p['id'] for p in state['tools']['structuralSubsurfaces']],expected)
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();self.assertEqual(v.GetFeaSubSurfName(self.rect),'Load patch');self.assertEqual(list(v.GetFeaSubSurfIDVec(self.sid)),[self.array,self.rect])

    def test_active_constraint_guards_expansion_and_delete_and_rejects_foreign_region(self):
        self.fixture();state,path=self.worker(dict(action='mutate',operation='boundary-add',structure=self.sid,type='FEA_BC_SUBSURF',name='Array constraint'))
        bc=state['tools']['boundaryConditions'][0]['id'];state,path=self.worker(dict(action='mutate',operation='boundary-target',structure=self.sid,id=bc,target=self.array),path)
        before=path.read_bytes()
        for op in ('structural-subsurface-delete','structural-subsurface-individualize'):
            with self.assertRaisesRegex(ValueError,'Array constraint'):self.worker(dict(action='mutate',operation=op,structure=self.sid,id=self.array),path)
            self.assertEqual(path.read_bytes(),before)
        for req in [dict(operation='structural-subsurface-individualize',id=self.rect),dict(operation='structural-subsurface-reorder',id=self.rect,direction='BAD'),dict(operation='structural-subsurface-rename',id='FOREIGN',name='Bad')]:
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',structure=self.sid,**req),path)
        state,path=self.worker(dict(action='mutate',operation='boundary-target',structure=self.sid,id=bc,target=self.rect),path)
        state,path=self.worker(dict(action='mutate',operation='structural-subsurface-individualize',structure=self.sid,id=self.array),path)
        self.assertEqual(state['tools']['boundaryConditions'][0]['references']['SubSurfID'],self.rect)
