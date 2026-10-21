"""Saved native case editing and execution, independent of interface formatting."""
import json
import sys
import unittest
import xml.etree.ElementTree as ET
import test_native, test_guides, test_degenerate
import native_worker, native_geometry_cases
from vsp_runtime import load


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativeGeometryCases(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    fixture=test_guides.NativeGuides.fixture
    direct=test_guides.NativeGuides.direct
    canonical=test_degenerate.NativeDegenerate.canonical
    assertResults=test_degenerate.NativeDegenerate.assertResults

    def case(self,typ):
        v=self.v;cid=v.AddGeometryAnalysis();v.SetContainerName(cid,'Saved '+typ)
        for key,val in [('IntererenceCheckType',getattr(v,typ)),('PrimarySet',3),('SecondarySet',4),('NumSlices',7),('DispX',1)]:v.SetParmVal(v.FindParm(cid,key,'InterferenceCase'),val)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return cid

    def test_saved_cases_and_all_case_execution_match_native(self):
        self.fixture();v=self.v;cases=[]
        for typ in ['COMP_GEOM','PLANAR_SLICE','PROJ_AREA','MASS_PROP','EXTERNAL_INTERFERENCE']:
            cid=self.case(typ);cases.append(cid);baseline=self.model.read_bytes()
            expected=self.direct('GeometryAnalysis',{'CaseID':[cid]})
            data,path=self.worker(dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=[cid])]))
            self.assertResults(expected,data['results']);self.assertEqual(path.read_bytes(),baseline)
            saved=next(c for c in data['geometryCases'] if c['id']==cid)
            self.assertEqual(saved['name'],'Saved '+typ)
            self.assertEqual(next(p['value'] for p in saved['params'] if p['name']=='IntererenceCheckType'),getattr(v,typ))
        baseline=self.model.read_bytes();expected=self.direct('GeometryAnalysis',{'CaseID':['ALL']})
        data,path=self.worker(dict(action='analysis',name='GeometryAnalysis',inputs=[]))
        self.assertResults(expected,data['results']);self.assertEqual(path.read_bytes(),baseline)
        self.assertEqual([c['id'] for c in data['geometryCases']],cases)

    def test_create_references_directions_cutouts_and_delete_persist(self):
        self.fixture();v=self.v;sid=v.AddSubSurf(self.gid,v.SS_RECTANGLE);mode=v.CreateAndAddMode('Check mode',3,-1);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,path=self.worker(dict(action='mutate',operation='geometry-case-add',name='Visibility check',type=v.VISIBLE_FROM_POINT_ANALYSIS))
        c=state['tools']['geometryCases'][0];cid=c['id'];self.assertEqual(len(state['tools']['geometryCaseTypes']),20)
        for key,value in [('PrimaryGeomID',self.gid),('SecondaryGeomID',self.pod),('DirectionGeomID',self.gid),('PrimaryModeID',mode)]:
            state,path=self.worker(dict(action='mutate',operation='geometry-case-reference',id=cid,key=key,value=value),path)
            self.assertEqual(state['tools']['geometryCases'][0]['references'][key],value)
            node=next(n for n in ET.parse(path).findall('.//GeometryAnalysis') if n.findtext('ParmContainer/ID')==cid)
            self.assertEqual(node.findtext(key),value)
        state,path=self.worker(dict(action='mutate',operation='geometry-case-cutouts',id=cid,values=[sid]),path)
        self.assertEqual(state['tools']['geometryCases'][0]['cutouts'],[sid])
        for az,el in [(15,25),(-170,-80)]:state,path=self.worker(dict(action='mutate',operation='geometry-case-direction-add',id=cid,azimuth=az,elevation=el),path)
        self.assertEqual([(d['azimuth']['value'],d['elevation']['value']) for d in state['tools']['geometryCases'][0]['directions']],[(15,25),(-170,-80)])
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        self.assertEqual(v.GetNumGeometryAnalysisAzEl(cid),2)
        self.assertEqual(v.GetParmVal(v.GetGeometryAnalysisAzimuthParm(cid,1)),-170)
        state,path=self.worker(dict(action='mutate',operation='geometry-case-direction-delete',id=cid,index=0),path)
        self.assertEqual(len(state['tools']['geometryCases'][0]['directions']),1)
        state,path=self.worker(dict(action='mutate',operation='geometry-case-rename',id=cid,name='Renamed check'),path)
        self.assertEqual(state['tools']['geometryCases'][0]['name'],'Renamed check')
        state,path=self.worker(dict(action='mutate',operation='geometry-case-delete',id=cid),path)
        self.assertEqual(state['tools']['geometryCases'],[])

    def test_missing_cases_and_invalid_references_are_actionable(self):
        baseline=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'Create a named case'):self.worker(dict(action='analysis',name='GeometryAnalysis',inputs=[]))
        self.assertEqual(self.model.read_bytes(),baseline)
        self.fixture();cid=self.case('COMP_GEOM');baseline=self.model.read_bytes()
        for request in [dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=['MISSING'])]),dict(action='mutate',operation='geometry-case-reference',id=cid,key='PrimaryGeomID',value='MISSING'),dict(action='mutate',operation='geometry-case-direction-add',id=cid,azimuth=181,elevation=0)]:
            with self.assertRaises(ValueError):self.worker(request)
            self.assertEqual(self.model.read_bytes(),baseline)

    def test_headless_case_projection_uses_native_derived_direction(self):
        self.fixture();v=self.v;cid=self.case('PROJ_AREA')
        for key,val in [('DirectionType',v.Z_PROJ),('DispX',0),('DispY',0),('DispZ',0)]:v.SetParmVal(v.FindParm(cid,key,'InterferenceCase'),val)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);baseline=self.model.read_bytes()
        # The separate official Projection analysis computes its own direction.
        expected=self.direct('Projection',dict(TargetType=[v.SET_TARGET],TargetSet=[3],DirectionType=[v.Z_PROJ]))
        area=next(e['values'] for r in expected if r['name']=='Projection' for e in r['entries'] if e['name']=='Area')
        data,path=self.worker(dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=[cid])]))
        actual=next(r for r in data['results'] if r['name']=='Projected_Area')
        self.assertEqual(next(e['values'] for e in actual['entries'] if e['name']=='Area'),area)
        self.assertGreater(area[0],0)
        self.assertEqual(next(e['values'] for e in actual['entries'] if e['name']=='Direction'),[[0,0,1]])
        self.assertEqual(path.read_bytes(),baseline)

    def test_case_specific_choices_do_not_leak_between_saved_cases(self):
        self.fixture();v=self.v
        types=['VISIBLE_FROM_POINT_ANALYSIS','EXTERNAL_INTERFERENCE','VISIBLE_FROM_POINT_ANALYSIS','PACKAGING_INTERFERENCE']
        ids=[self.case(typ) for typ in types]
        state,path=self.worker({'action':'state'})
        cases={c['id']:c for c in state['tools']['geometryCases']}
        ordinary={v.SET_TARGET,v.GEOM_TARGET}
        for cid,typ in zip(ids,types):
            choices=next(p['choices'] for p in cases[cid]['params'] if p['name']=='SecondaryType')
            expected=ordinary|({v.XYZ_TARGET} if typ=='VISIBLE_FROM_POINT_ANALYSIS' else set())
            self.assertEqual({c['value'] for c in choices},expected,typ)
            self.assertEqual(len(choices),len(expected),'No repeated options from earlier cases')
        reopened,_=self.worker({'action':'state'},path)
        self.assertEqual([next(p['choices'] for p in c['params'] if p['name']=='SecondaryType') for c in reopened['tools']['geometryCases']],
                         [next(p['choices'] for p in c['params'] if p['name']=='SecondaryType') for c in state['tools']['geometryCases']])

    def test_observation_point_recovery_preserves_coordinates_and_native_results(self):
        self.fixture();v=self.v;cid=self.case('VISIBLE_FROM_POINT_ANALYSIS')
        for name,value in [('SecondaryType',v.XYZ_TARGET),('SecondaryX',12.),('SecondaryY',4.),('SecondaryZ',3.)]:v.SetParmVal(v.FindParm(cid,name,'InterferenceCase'),value)
        v.AddGeometryAnalysisAzEl(cid,15.,10.);v.AddGeometryAnalysisAzEl(cid,-20.,-5.);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);original=self.model.read_bytes()
        for request in [dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=[cid])]),dict(action='mutate',operation='geometry-case-result-mesh',id=cid)]:
            with self.assertRaisesRegex(ValueError,'Create observation-point component'):self.worker(request)
        state,path=self.worker(dict(action='mutate',operation='geometry-case-observation-point',id=cid))
        self.assertEqual(self.model.read_bytes(),original)
        saved=next(c for c in state['tools']['geometryCases'] if c['id']==cid);point=saved['references']['SecondaryGeomID'];blank=next(g for g in state['components'] if g['id']==point)
        self.assertEqual(blank['type'].upper(),'BLANK');self.assertEqual(len(state['components']),3)
        for axis,coordinate in zip('XYZ',[12.,4.,3.]):self.assertEqual(next(p['value'] for p in blank['params'] if p['rawGroup']=='XForm' and p['name']==axis+'_Rel_Location'),coordinate)
        self.assertFalse(saved['editorGuide']['observationPoint'])
        for discrete,polygon in [(0,0),(0,1),(1,0),(1,1)]:
            with self.subTest(discrete=discrete,polygon=polygon):
                v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
                for name,value in [('DiscreteVisibilityFlag',discrete),('PolyVisibleFlag',polygon)]:v.SetParmVal(v.FindParm(cid,name,'InterferenceCase'),value)
                v.Update();v.WriteVSPFile(str(path),v.SET_ALL);before=path.read_bytes()
                expected=self.direct('GeometryAnalysis',{'CaseID':[cid]},model=path)
                data,result_path=self.worker(dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=[cid])]),path)
                self.assertResults(expected,data['results']);self.assertEqual(result_path.read_bytes(),before)
                result=next(r for r in data['results'] if r['name']=='Point_Visibility');self.assertEqual(next(e['values'] for e in result['entries'] if e['name']=='Center'),[[12.,4.,3.]])

    def test_observation_point_recovery_rejects_other_case_types(self):
        self.fixture();cid=self.case('COMP_GEOM');before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'point-visibility case'):
            self.worker(dict(action='mutate',operation='geometry-case-observation-point',id=cid))
        self.assertEqual(self.model.read_bytes(),before)

    def test_observation_point_recovery_is_one_undoable_edit_and_preserves_geometry_locks(self):
        from unittest.mock import patch
        import native_service as service
        self.fixture();v=self.v;cid=self.case('VISIBLE_FROM_POINT_ANALYSIS');pid=v.FindParm(cid,'SecondaryType','InterferenceCase');v.SetParmVal(pid,v.XYZ_TARGET);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);original=self.model.read_bytes()
        with patch.multiple(service,WORK=self.path,MODEL=self.model,REVISION='original',HISTORY=[],FUTURE=[],LAST_EDIT_GROUP=None):
            service.mutation(dict(operation='geometry-case-observation-point',id=cid,revision=service.REVISION));adapted=self.model.read_bytes();self.assertEqual(len(service.HISTORY),1)
            service.undo(revision=service.REVISION);self.assertEqual(self.model.read_bytes(),original)
            service.undo(redo=True,revision=service.REVISION);self.assertEqual(self.model.read_bytes(),adapted)
        self.model.write_bytes(original)
        # Saved locks apply to geometry properties, not case enum parameters.
        span=v.FindParm(self.gid,'TotalSpan','WingGeom')
        state,locked=self.worker(dict(action='mutate',operation='property-lock',parameters=[span],locked=True));before=locked.read_bytes()
        original_span=next(p['value'] for c in state['components'] for p in c['params'] if p['id']==span)
        recovered,_=self.worker(dict(action='mutate',operation='geometry-case-observation-point',id=cid),locked)
        after=next(p for c in recovered['components'] for p in c['params'] if p['id']==span)
        self.assertEqual(after['value'],original_span);self.assertTrue(after['userLocked']);self.assertEqual(locked.read_bytes(),before)

    def visibility_mode(self,secondary):
        v=self.v;cid=self.case('VISIBLE_FROM_POINT_ANALYSIS');pid=v.FindParm(cid,'SecondaryType','InterferenceCase')
        group=v.AddVarPresetGroup('Visibility target');v.AddVarPresetParm(group,pid);setting=v.AddVarPresetSetting(group,'Target');v.SetVarPresetParmVal(group,setting,pid,secondary)
        mode=v.CreateAndAddMode('Visibility mode',3,-1);v.ModeAddGroupSetting(mode,group,setting)
        v.SetParmVal(v.FindParm(cid,'PrimaryType','InterferenceCase'),v.MODE_TARGET);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        _,path=self.worker(dict(action='mutate',operation='geometry-case-reference',id=cid,key='PrimaryModeID',value=mode))
        return cid,pid,path

    def test_visibility_mode_cannot_reintroduce_crashing_xyz_target(self):
        self.fixture();v=self.v;cid,pid,path=self.visibility_mode(v.XYZ_TARGET);before=path.read_bytes()
        for request in [dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=[cid])]),dict(action='mutate',operation='geometry-case-result-mesh',id=cid)]:
            with self.assertRaisesRegex(ValueError,'mode.*preset'):self.worker(request,path)
        self.assertEqual(path.read_bytes(),before)

    def test_visibility_mode_can_replace_baseline_xyz_with_valid_component(self):
        self.fixture();v=self.v;cid,pid,path=self.visibility_mode(v.GEOM_TARGET)
        _,path=self.worker(dict(action='mutate',operation='geometry-case-reference',id=cid,key='SecondaryGeomID',value=self.pod),path)
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();v.SetParmVal(pid,v.XYZ_TARGET);v.Update();v.WriteVSPFile(str(path),v.SET_ALL);before=path.read_bytes()
        expected=self.direct('GeometryAnalysis',{'CaseID':[cid]},model=path)
        data,result=self.worker(dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=[cid])]),path)
        self.assertResults(expected,data['results']);self.assertEqual(path.read_bytes(),before);self.assertEqual(result.read_bytes(),before)

    def test_run_all_checks_mode_effects_on_later_visibility_case(self):
        self.fixture();v=self.v;first=self.case('COMP_GEOM');later=self.case('VISIBLE_FROM_POINT_ANALYSIS')
        pid=v.FindParm(later,'SecondaryType','InterferenceCase');v.SetParmVal(pid,v.GEOM_TARGET)
        group=v.AddVarPresetGroup('Later target');v.AddVarPresetParm(group,pid);setting=v.AddVarPresetSetting(group,'XYZ target');v.SetVarPresetParmVal(group,setting,pid,v.XYZ_TARGET)
        mode=v.CreateAndAddMode('Earlier mode',3,-1);v.ModeAddGroupSetting(mode,group,setting);v.SetParmVal(v.FindParm(first,'PrimaryType','InterferenceCase'),v.MODE_TARGET);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        _,path=self.worker(dict(action='mutate',operation='geometry-case-reference',id=first,key='PrimaryModeID',value=mode))
        _,path=self.worker(dict(action='mutate',operation='geometry-case-reference',id=later,key='SecondaryGeomID',value=self.pod),path);before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'mode.*preset'):
            self.worker(dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=['ALL'])]),path)
        self.assertEqual(path.read_bytes(),before)
