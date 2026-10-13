"""Guided component analysis preserves official results and trimmed mesh."""
import json,sys,unittest
import test_native
import test_guides
import native_worker
from mesh_io import read_gmsh
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativeComponentGuides(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    fixture=test_guides.NativeGuides.fixture
    direct=test_guides.NativeGuides.direct
    assertNative=test_guides.NativeGuides.assertNative

    def test_selection_half_regions_and_mode_presets_match_native_results_and_mesh(self):
        self.fixture();v=self.v
        region=v.AddSubSurf(self.gid,v.SS_RECTANGLE,0);v.SetSubSurfName(region,'Measured wing panel')
        slot=v.GetNumSets()-1;v.SetSetName(slot,'Preserved export selection');v.SetSetFlag(self.gid,slot,True)
        mode=v.CreateAndAddMode('Body mode',4,-1)
        thin_mode=v.CreateAndAddMode('Thin wing',-1,3);mixed_mode=v.CreateAndAddMode('Body and thin wing',4,3)
        group=v.AddVarPresetGroup('Body position');pid=v.FindParm(self.pod,'Y_Rel_Location','XForm');v.AddVarPresetParm(group,pid)
        setting=v.AddVarPresetSetting(group,'Offset body');v.SetVarPresetParmVal(group,setting,pid,2.)
        v.ModeAddGroupSetting(mode,group,setting);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        cases=[dict(Set=[0],SubSurfFlag=[1],WriteTXTFlag=[1],WriteCSVFlag=[1]),
               dict(Set=[3],HalfMeshFlag=[1],SubSurfFlag=[1],WriteTXTFlag=[0],WriteCSVFlag=[0]),
               dict(Set=[3],SubSurfFlag=[0]),dict(UseModeFlag=[1],ModeID=[thin_mode]),
               dict(UseModeFlag=[1],ModeID=[mixed_mode]),dict(UseModeFlag=[1],ModeID=[mode],Set=[-1],DegenSet=[-1])]
        baseline=self.model.read_bytes()
        for values in cases:
            with self.subTest(inputs=values):
                expected=self.direct('CompGeom',values)
                result=next(r for r in expected if r['name']=='Comp_Geom')
                ids=next(e['values'] for e in result['entries'] if e['name']=='Mesh_GeomID')
                flags={g:v.GetSetFlag(g,slot) for g in v.FindGeoms()}
                for g in flags:v.SetSetFlag(g,slot,g in ids)
                direct_file=self.path/'direct-component.msh';v.ExportFile(str(direct_file),slot,v.EXPORT_GMSH,1);native_worker.errors(v)
                direct_mesh=read_gmsh(direct_file)
                for g,flag in flags.items():v.SetSetFlag(g,slot,flag)
                request=dict(action='analysis',name='CompGeom',inputs=[dict(name=n,index=0,values=x) for n,x in values.items()])
                actual,path=self.worker(request);self.assertNative(expected,actual['results'])
                mesh=read_gmsh(path.parent/actual['meshFile'])
                for key in ('nodes','nodeIDs','elements','groups','higherOrder','unsupportedElements'):
                    self.assertEqual(mesh[key],direct_mesh[key],key)
                self.assertEqual(actual['meshSummary']['nodes'],len(direct_mesh['nodes']))
                self.assertEqual(self.model.read_bytes(),baseline);self.assertEqual(path.read_bytes(),baseline)
                if values.get('WriteCSVFlag')==[1]:self.assertTrue(list(path.parent.glob('*CompGeom.csv')))
                if values.get('WriteTXTFlag')==[1]:self.assertTrue(list(path.parent.glob('*CompGeom.txt')))
                if values.get('WriteCSVFlag')==[0]:self.assertFalse(list(path.parent.glob('*CompGeom.csv')))
                if values.get('WriteTXTFlag')==[0]:self.assertFalse(list(path.parent.glob('*CompGeom.txt')))

    def test_invalid_selection_rejects_before_native_execution_and_preserves_source(self):
        self.fixture();baseline=self.model.read_bytes()
        for inputs in [dict(Set=[-1],DegenSet=[-1]),dict(Set=[20],DegenSet=[-1]),dict(Set=[999]),dict(Set=[4],DegenSet=[3]),dict(UseModeFlag=[1],ModeID=['missing']),dict(HalfMeshFlag=[2]),dict(SubSurfFlag=[2]),dict(WriteCSVFlag=[2]),dict(WriteTXTFlag=[2])]:
            with self.subTest(inputs=inputs),self.assertRaises(ValueError):
                self.worker(dict(action='analysis',name='CompGeom',inputs=[dict(name=n,values=x) for n,x in inputs.items()]))
            self.assertEqual(self.model.read_bytes(),baseline)

    def test_temporary_mesh_export_selection_is_restored_in_native_memory(self):
        self.fixture();v=self.v;slot=v.GetNumSets()-1;v.SetSetName(slot,'Keep this slot');v.SetSetFlag(self.gid,slot,True);v.SetSetFlag(self.pod,slot,False)
        original={g:v.GetSetFlag(g,slot) for g in v.FindGeoms()}
        v.SetVSP3FileName(str(self.path/'direct.vsp3'))
        import os
        previous=os.getcwd()
        try:
            os.chdir(self.path)
            data=native_worker.execute_analysis(v,dict(name='CompGeom',inputs=[]))
        finally:os.chdir(previous)
        for g,flag in original.items():self.assertEqual(v.GetSetFlag(g,slot),flag)
        self.assertEqual(v.GetSetName(slot),'Keep this slot');self.assertTrue((self.path/data['meshFile']).is_file())
