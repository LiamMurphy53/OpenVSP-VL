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
