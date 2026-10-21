"""Integration checks against the installed official OpenVSP API, not mocked math."""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from vsp_runtime import load,interpreter


@unittest.skipUnless(sys.version_info[:2]==(3,11), 'Run with the matching OpenVSP Python 3.11 runtime.')
class NativeIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v=load()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='openvsp-native-test-')
        self.path=Path(self.temp.name); self.old_cwd=os.getcwd();os.chdir(self.path)
        v=self.v;v.ClearVSPModel();self.gid=v.AddGeom('WING');v.SetGeomName(self.gid,'Reference wing')
        v.Update();self.model=self.path/'source.vsp3';v.WriteVSPFile(str(self.model),v.SET_ALL)

    def tearDown(self):
        os.chdir(self.old_cwd);self.temp.cleanup()

    def worker(self,request,model=None):
        folder=self.path/str(len(list(self.path.iterdir())));folder.mkdir()
        target=folder/'aircraft.vsp3';shutil.copy2(model or self.model,target)
        # Retain the exact pre-request file, not only a potentially changed candidate.
        shutil.copy2(target,folder/'input.vsp3')
        from native_service import invoke
        try:data=invoke(request,target,folder)
        except ValueError:raise  # Ordinary native validation is an expected test outcome.
        except Exception as error:
            import uuid
            evidence=ROOT/'.workspace/evidence/native-worker-failures'/uuid.uuid4().hex
            shutil.copytree(folder,evidence)
            raise RuntimeError(f'{error} Retained worker input and diagnostics: {evidence}') from error
        finally:
            if (folder/'engine.log').exists():shutil.copy2(folder/'engine.log',folder/'log.txt')
        return data,target

    def test_surface_coordinates_match_native_samples(self):
        state,_=self.worker({'action':'state'})
        self.assertEqual(len(state['components'][0]['surfaces']),self.v.GetTotalNumSurfs(self.gid))
        for si,surface in enumerate(state['components'][0]['surfaces']):
            u,w=self.v.GetUWTess01(self.gid,0)
            for i,j in [(0,0),(len(u)//2,len(w)//2),(len(u)-1,len(w)-1)]:
                expected=self.v.CompPnt01(self.gid,si,u[i],w[j])
                actual=surface['points'][i*len(w)+j]
                for a,b in zip(actual,[expected.x(),expected.y(),expected.z()]): self.assertAlmostEqual(a,b,places=11)

    def test_edit_and_dependent_values_match_direct_api(self):
        pid=self.v.FindParm(self.gid,'TotalSpan','WingGeom')
        self.v.SetParmValUpdate(pid,22.)
        expected={p:self.v.GetParmVal(p) for p in self.v.GetGeomParmIDs(self.gid)}
        state,path=self.worker({'action':'mutate','operation':'parameter','id':pid,'value':22.})
        for p in state['components'][0]['params']:
            self.assertAlmostEqual(p['value'],expected[p['id']],places=9,msg=p['name'])
        self.v.ClearVSPModel();self.v.ReadVSPFile(str(path))
        self.assertAlmostEqual(self.v.GetParmVal(pid),22.)

    def test_native_file_preserves_geometry_and_parameter_ids(self):
        state,_=self.worker({'action':'state'})
        self.assertEqual(state['components'][0]['id'],self.gid)
        self.assertEqual({p['id'] for p in state['components'][0]['params']},set(self.v.GetGeomParmIDs(self.gid)))

    def test_invalid_number_is_rejected(self):
        pid=self.v.FindParm(self.gid,'TotalSpan','WingGeom')
        for value in [float('nan'),float('inf'),-1]:
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.worker({'action':'mutate','operation':'parameter','id':pid,'value':value})

    def test_wing_drivers_and_section_insertion(self):
        before=self.v.GetNumXSec(self.v.GetXSecSurf(self.gid,0))
        state,_=self.worker({'action':'mutate','operation':'insert-section','geom':self.gid,'index':1,'surface':0,'shape':self.v.XS_FOUR_SERIES})
        self.assertEqual(len(state['components'][0]['sections']),before+1)
        drivers=[self.v.AR_WSECT_DRIVER,self.v.ROOTC_WSECT_DRIVER,self.v.TIPC_WSECT_DRIVER]
        state,_=self.worker({'action':'mutate','operation':'drivers','geom':self.gid,'index':1,'drivers':drivers})
        self.assertEqual(state['components'][0]['sections'][1]['drivers'],drivers)

    def test_compgeom_matches_direct_engine(self):
        v=self.v;v.SetVSP3FileName(str(self.path/'direct.vsp3'));v.SetAnalysisInputDefaults('CompGeom')
        rid=v.ExecAnalysis('CompGeom')
        names=['Total_Wet_Area','Total_Wet_Vol','Total_Theo_Area','Total_Theo_Vol']
        expected={n:list(v.GetDoubleResults(rid,n)) for n in names}
        data,_=self.worker({'action':'analysis','name':'CompGeom','inputs':[]})
        result=next(r for r in data['results'] if r['name']=='Comp_Geom')
        actual={e['name']:e['values'] for e in result['entries']}
        for n in names:self.assertEqual(actual[n],expected[n])

    def test_vspaero_matches_direct_engine(self):
        v=self.v;v.SetVSP3FileName(str(self.path/'direct-aero.vsp3'))
        v.SetAnalysisInputDefaults('VSPAEROComputeGeometry');v.ExecAnalysis('VSPAEROComputeGeometry')
        values={'AlphaStart':4.,'AlphaEnd':4.,'AlphaNpts':1,'NCPU':1,'MachStart':.1,'MachEnd':.1,'MachNpts':1,'Sref':45.,'bref':18.,'cref':2.5}
        v.SetAnalysisInputDefaults('VSPAEROSweep')
        for n,value in values.items():
            setter=v.SetIntAnalysisInput if v.GetAnalysisInputType('VSPAEROSweep',n)==v.INT_DATA else v.SetDoubleAnalysisInput
            setter('VSPAEROSweep',n,[value])
        v.ExecAnalysis('VSPAEROSweep');rid=v.FindLatestResultsID('VSPAERO_Polar')
        names=['CLtot','CDtot','CDi','CMytot']
        expected={n:list(v.GetDoubleResults(rid,n)) for n in names}
        self.assertTrue(all(expected.values()),'Native polar entries must exist.')
        data,_=self.worker({'action':'analysis','name':'VSPAEROSweep','inputs':[{'name':n,'values':[x]} for n,x in values.items()]})
        polar=next(r for r in data['results'] if r['name']=='VSPAERO_Polar')
        actual={e['name']:e['values'] for e in polar['entries']}
        for n in names:
            for a,b in zip(actual[n],expected[n]):self.assertAlmostEqual(a,b,places=9,msg=n)


    def test_pressure_database_matches_native_slicer_across_sweep_cases(self):
        from aero_io import read_adb
        inputs={'AlphaStart':0.,'AlphaEnd':6.,'AlphaNpts':3,'NCPU':1,'MachStart':.1,'MachEnd':.1,'MachNpts':1}
        result,path=self.worker({'action':'analysis','name':'VSPAEROSweep','inputs':[{'name':n,'values':[x]} for n,x in inputs.items()]})
        # Run the official slicer beside the saved solver files.
        from native_service import invoke
        sliced=invoke({'action':'analysis','name':'CpSlicer','inputs':[{'name':'YSlicePosVec','values':[2.]}]},path,path.parent)
        slices=[r for r in sliced['results'] if r['name']=='CpSlicer_Case']
        self.assertEqual(len(slices),3)
        for case in (1,2,3):
            mesh=read_adb(path.with_suffix('.adb'),case)
            self.assertAlmostEqual(mesh['conditions']['alpha'],(case-1)*3,places=5)
            self.assertTrue(mesh['wakes'])
            # The official slicer uses area-weighted node pressure and interpolates
            # it on intersected native edges. Compare those independent samples.
            accum=[0.]*len(mesh['nodes']);areas=[0.]*len(mesh['nodes'])
            cp=mesh['fields'][0]['values'];edges=set()
            for e,value in zip(mesh['elements'],cp):
                for n in e['nodes']:accum[n]+=value*e['area'];areas[n]+=e['area']
                a,b,c=e['nodes'];edges.update(tuple(sorted(pair)) for pair in ((a,b),(b,c),(c,a)))
            nodal=[a/w if w else 0 for a,w in zip(accum,areas)]
            crossings=[]
            for a,b in edges:
                pa,pb=mesh['nodes'][a],mesh['nodes'][b]
                if (pa[1]-2)*(pb[1]-2)>0 or abs(pb[1]-pa[1])<1e-12:continue
                t=(2-pa[1])/(pb[1]-pa[1])
                crossings.append((pa[0]+t*(pb[0]-pa[0]),nodal[a]+t*(nodal[b]-nodal[a])))
            entries={e['name']:e['values'] for e in slices[case-1]['entries']}
            self.assertGreater(len(entries['Cp']),10)
            for x,value in zip(entries['X_Loc'],entries['Cp']):
                candidates=[p for p in crossings if abs(p[0]-x)<.00015]
                self.assertTrue(candidates,'Native slice point must lie on decoded geometry.')
                self.assertLess(min(abs(p[1]-value) for p in candidates),.00015)

    def test_control_group_deflection_and_mirrored_gains_persist(self):
        state,path=self.worker({'action':'mutate','operation':'control-add','geom':self.gid,'name':'Flap','start':.15,'end':.75,'chord':.3})
        control=state['tools']['controls'][0]
        self.assertAlmostEqual(next(p['value'] for p in control['params'] if p['name']=='EtaStart'),.15)
        state,path=self.worker({'action':'mutate','operation':'control-groups-auto'},path)
        group=state['tools']['controlGroups'][0]
        gains=[p for p in group['params'] if p['name'].endswith('_Gain')]
        self.assertEqual(len(gains),2)
        pid=next(p['id'] for p in group['params'] if p['name']=='DeflectionAngle')
        state,path=self.worker({'action':'mutate','operation':'parameter','id':pid,'value':12},path)
        self.v.ClearVSPModel();self.v.ReadVSPFile(str(path))
        self.assertEqual(self.v.GetParmVal(pid),12)
        self.assertEqual(len(self.v.GetActiveCSNameVec(0)),2)
        state,path=self.worker({'action':'mutate','operation':'control-delete','geom':self.gid,'id':control['id']},path)
        self.assertFalse(state['tools']['controls'])

    def test_airfoil_reader_and_curve_edit_match_native(self):
        text='Test airfoil\n1.0 0.0\n0.75 0.04\n0.5 0.06\n0.25 0.05\n0.0 0.0\n0.25 -0.05\n0.5 -0.06\n0.75 -0.04\n1.0 0.0\n'
        state,path=self.worker({'action':'mutate','operation':'airfoil-import','geom':self.gid,'index':1,'content':text})
        v=self.v;surf=v.GetXSecSurf(self.gid,0);v.ChangeXSecShape(surf,1,v.XS_FILE_AIRFOIL)
        f=self.path/'direct.dat';f.write_text(text);xid=v.GetXSec(surf,1);v.ReadFileAirfoil(xid,str(f));v.Update()
        expected=[v.ComputeXSecPnt(xid,i/100) for i in range(101)]
        actual=state['components'][0]['sections'][1]['profile']
        for p,q in zip(actual,expected):
            for a,b in zip(p,[q.x(),q.y(),q.z()]):self.assertAlmostEqual(a,b,places=10)
        state,path=self.worker({'action':'mutate','operation':'curve-convert','geom':self.gid,'index':1},path)
        point=state['components'][0]['sections'][1]['controlPoints'][2];point[1]*=1.1
        state,path=self.worker({'action':'mutate','operation':'curve-point','geom':self.gid,'index':1,'point':2,'xyz':point},path)
        v.ClearVSPModel();v.ReadVSPFile(str(path));actual=v.GetEditXSecCtrlVec(v.GetXSec(v.GetXSecSurf(self.gid,0),1),True)[2]
        for a,b in zip(state['components'][0]['sections'][1]['controlPoints'][2],[actual.x(),actual.y(),actual.z()]):self.assertAlmostEqual(a,b,places=10)

    def test_sets_visibility_hierarchy_and_cycle_rejection(self):
        state,path=self.worker({'action':'mutate','operation':'set-name','index':3,'name':'Lifting surfaces'})
        state,path=self.worker({'action':'mutate','operation':'set-member','geom':self.gid,'index':3,'member':True},path)
        state,path=self.worker({'action':'mutate','operation':'visibility','geom':self.gid,'shown':False},path)
        self.assertFalse(state['components'][0]['shown'])
        self.assertIn(self.gid,state['tools']['sets'][3]['members'])
        state,path=self.worker({'action':'mutate','operation':'duplicate','geom':self.gid,'name':'Second wing'},path)
        second=state['changed'];self.assertNotEqual(second,self.gid)
        state,path=self.worker({'action':'mutate','operation':'reparent','geom':second,'parent':self.gid},path)
        self.assertEqual(next(c for c in state['components'] if c['id']==second)['parent'],self.gid)
        with self.assertRaises(ValueError):self.worker({'action':'mutate','operation':'reparent','geom':self.gid,'parent':second},path)
        state,path=self.worker({'action':'mutate','operation':'reparent','geom':second,'parent':''},path)
        self.assertEqual(next(c for c in state['components'] if c['id']==second)['parent'],'NONE')

    def test_links_drive_values_and_presets_restore_native_values(self):
        state,path=self.worker({'action':'mutate','operation':'user-add','name':'Span driver','value':10})
        source=next(p['id'] for p in state['tools']['userParameters'] if p['name']=='Span driver')
        target=self.v.FindParm(self.gid,'TotalSpan','WingGeom')
        state,path=self.worker({'action':'mutate','operation':'link-add','source':source,'target':target,'scale':2,'offset':1},path)
        state,path=self.worker({'action':'mutate','operation':'parameter','id':source,'value':12},path)
        span=next(p['value'] for p in state['components'][0]['params'] if p['id']==target)
        self.assertEqual(span,25)
        with self.assertRaises(ValueError):self.worker({'action':'mutate','operation':'link-add','source':target,'target':source},path)
        state,path=self.worker({'action':'mutate','operation':'preset-save','name':'Baseline','parameters':[source]},path)
        preset=state['tools']['presets'][0]
        state,path=self.worker({'action':'mutate','operation':'parameter','id':source,'value':14},path)
        state,path=self.worker({'action':'mutate','operation':'preset-apply','group':preset['id'],'setting':preset['settings'][0]['id']},path)
        self.assertEqual(next(p['value'] for p in state['tools']['userParameters'] if p['id']==source),12)
        self.assertEqual(next(p['value'] for p in state['components'][0]['params'] if p['id']==target),25)
        state,path=self.worker({'action':'mutate','operation':'preset-delete','id':preset['id']},path)
        lid=state['tools']['links'][0]['id']
        state,path=self.worker({'action':'mutate','operation':'link-delete','id':lid},path)
        self.assertFalse(state['tools']['presets']);self.assertFalse(state['tools']['links'])

    def test_mesh_sources_and_structural_parts_persist(self):
        state,path=self.worker({'action':'mutate','operation':'mesh-settings','values':{'CFD_MAX_EDGE_LEN':.8,'CFD_MIN_EDGE_LEN':.02}})
        state,path=self.worker({'action':'mutate','operation':'source-add','geom':self.gid,'type':'LINE_SOURCE','length':.1,'radius':.4},path)
        source=state['tools']['sources'][0]
        self.assertTrue(source['params'])
        state,path=self.worker({'action':'mutate','operation':'structure-add','geom':self.gid,'name':'Internal structure'},path)
        sid=state['tools']['structures'][0]['id']
        state,path=self.worker({'action':'mutate','operation':'part-add','structure':sid,'type':'FEA_RIB','name':'Midspan rib'},path)
        part=next(p for p in state['tools']['structures'][0]['parts'] if p['name']=='Midspan rib')
        pid=next(p['id'] for p in part['params'] if p['name']=='RelCenterLocation')
        state,path=self.worker({'action':'mutate','operation':'parameter','id':pid,'value':.6},path)
        state,path=self.worker({'action':'mutate','operation':'material-add','name':'Test material'},path)
        state,path=self.worker({'action':'mutate','operation':'property-add','name':'Shell property','type':0},path)
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path))
        self.assertAlmostEqual(v.GetParmVal(pid),.6)
        self.assertAlmostEqual(v.GetCFDMeshVal(v.CFD_MAX_EDGE_LEN),.8)
        self.assertEqual(v.GetNumCFDSources(self.gid),1)
        self.assertIn('Shell property',[v.GetContainerName(p) for p in v.GetFeaPropertyIDVec()])
        self.assertIn('Test material',[v.GetContainerName(p) for p in v.GetFeaMaterialIDVec()])
        state,path=self.worker({'action':'mutate','operation':'source-delete','geom':self.gid,'index':0},path)
        state,path=self.worker({'action':'mutate','operation':'part-delete','structure':sid,'id':part['id']},path)
        self.assertEqual(len(state['tools']['structures'][0]['parts']),1)
        state,path=self.worker({'action':'mutate','operation':'structure-delete','structure':sid},path)
        self.assertFalse(state['tools']['structures']);self.assertFalse(state['tools']['sources'])

    def test_geometry_export_produces_real_files_without_changing_model(self):
        original=self.model.read_bytes()
        for fmt,marker in [('STL',b'solid'),('OBJ',b'v '),('STEP',b'ISO-10303'),('IGES',None),('GMSH',b'$Nodes'),('SVG',b'<svg')]:
            data,path=self.worker({'action':'export-geometry','format':fmt,'set':0})
            content=(path.parent/data['filename']).read_bytes()
            self.assertGreater(len(content),100)
            if marker:self.assertIn(marker,content)
            self.assertEqual(path.read_bytes(),original)


    def test_cfd_mesh_run_returns_native_export_and_preserves_design(self):
        from mesh_io import read_gmsh
        req={'action':'analysis','name':'CfdMeshAnalysis','inputs':[{'name':n,'values':[x]} for n,x in [('BaseLen',1.),('MinLen',.2),('MaxGap',.03)]]}
        state,path=self.worker(req)
        self.assertEqual(path.read_bytes(),self.model.read_bytes())
        mesh=read_gmsh(path.parent/state['meshFile'])
        self.assertGreater(len(mesh['elements']),100)
        self.assertEqual(state['meshSummary']['nodes'],len(mesh['nodes']))
        self.assertFalse(state['resultID'])  # Native mesh analyses legitimately return no result ID.
        rows=(path.parent/state['meshFile']).read_text().splitlines();i=rows.index('$Nodes')
        self.assertEqual(mesh['nodes'][0],list(map(float,rows[i+2].split()[1:4])))

    def test_fea_mesh_contains_native_skin_and_rib_groups(self):
        from mesh_io import read_gmsh
        v=self.v;i=v.AddFeaStruct(self.gid,True,0);part=v.AddFeaPart(self.gid,i,v.FEA_RIB);v.SetFeaPartName(part,'Test rib');v.Update()
        sid=v.GetFeaStructID(self.gid,i);v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,path=self.worker({'action':'analysis','name':'FeaMeshAnalysis','structure':sid,'inputs':[{'name':n,'values':[x]} for n,x in [('BaseLen',1.),('MinLen',.2),('MaxGap',.03)]]})
        mesh=read_gmsh(path.parent/state['meshFile'])
        self.assertEqual(state['engineOperation'],'ComputeFeaMesh')
        self.assertTrue(any('Test rib' in g['name'] for g in mesh['groups']))
        self.assertTrue(any('Skin' in g['name'] for g in mesh['groups']))
        self.assertGreater(len(mesh['elements']),10)
        self.assertEqual(path.read_bytes(),self.model.read_bytes())
        with self.assertRaises(ValueError):self.worker({'action':'analysis','name':'FeaMeshAnalysis','structure':'invalid'})


    def test_cst_fit_and_coefficients_match_direct_native_engine(self):
        v=self.v;surf=v.GetXSecSurf(self.gid,0);v.FitCSTAirfoil(surf,1,8);v.Update();x=v.GetXSec(surf,1)
        expected=list(v.GetUpperCSTCoefs(x))
        state,path=self.worker({'action':'mutate','operation':'cst-fit','geom':self.gid,'index':1,'degree':8})
        sec=state['components'][0]['sections'][1];self.assertEqual(sec['cst']['upper'],expected)
        upper=sec['cst']['upper'];lower=sec['cst']['lower'];upper[2]*=1.1
        v.SetUpperCST(x,8,upper);v.SetLowerCST(x,8,lower);v.Update()
        state,path=self.worker({'action':'mutate','operation':'cst-coefficients','geom':self.gid,'index':1,'upper':upper,'lower':lower},path)
        for i,p in enumerate(state['components'][0]['sections'][1]['profile']):
            q=v.ComputeXSecPnt(x,i/100)
            for a,b in zip(p,[q.x(),q.y(),q.z()]):self.assertAlmostEqual(a,b,places=10)
        state,path=self.worker({'action':'mutate','operation':'cst-degree','geom':self.gid,'index':1,'side':'upper','direction':'promote'},path)
        self.assertEqual(state['components'][0]['sections'][1]['cst']['upperDegree'],9)
        state,path=self.worker({'action':'mutate','operation':'cst-degree','geom':self.gid,'index':1,'side':'upper','direction':'demote'},path)
        v.ClearVSPModel();v.ReadVSPFile(str(path));self.assertEqual(v.GetUpperCSTDegree(v.GetXSec(v.GetXSecSurf(self.gid,0),1)),8)
        with self.assertRaises(ValueError):self.worker({'action':'mutate','operation':'cst-coefficients','geom':self.gid,'index':1,'upper':[float('nan')],'lower':lower},path)

    def test_curve_interpolation_split_delete_and_constraints_persist(self):
        state,path=self.worker({'action':'mutate','operation':'curve-convert','geom':self.gid,'index':1})
        state,path=self.worker({'action':'mutate','operation':'curve-type','geom':self.gid,'index':1,'type':'LINEAR'},path)
        section=state['components'][0]['sections'][1];self.assertEqual(section['curveType'],self.v.LINEAR)
        before=len(section['controlPoints']);u=(section['curveU'][0]+section['curveU'][1])/2
        state,path=self.worker({'action':'mutate','operation':'curve-split','geom':self.gid,'index':1,'u':u},path)
        section=state['components'][0]['sections'][1];self.assertGreater(len(section['controlPoints']),before)
        point=section['curveU'].index(u)
        state,path=self.worker({'action':'mutate','operation':'curve-fixed','geom':self.gid,'index':1,'point':point,'fixed':True},path)
        self.assertTrue(state['components'][0]['sections'][1]['fixedU'][point])
        state,path=self.worker({'action':'mutate','operation':'curve-delete','geom':self.gid,'index':1,'point':point},path)
        self.assertEqual(len(state['components'][0]['sections'][1]['controlPoints']),before)
        with self.assertRaises(ValueError):self.worker({'action':'mutate','operation':'curve-delete','geom':self.gid,'index':1,'point':0},path)
        state,path=self.worker({'action':'mutate','operation':'curve-type','geom':self.gid,'index':1,'type':'PCHIP'},path)
        self.assertEqual(state['components'][0]['sections'][1]['curveType'],self.v.PCHIP)

    def test_custom_control_group_membership_gains_and_rename(self):
        state,path=self.worker({'action':'mutate','operation':'control-add','geom':self.gid,'name':'Aileron'})
        state,path=self.worker({'action':'mutate','operation':'control-group-create','name':'Roll'},path)
        group=state['tools']['controlGroups'][0];gid=group['id'];self.assertEqual(len(group['available']),2)
        for _ in range(2):
            group=state['tools']['controlGroups'][0]
            state,path=self.worker({'action':'mutate','operation':'control-group-member','group':gid,'member':1,'expectedName':group['available'][0],'add':True},path)
        group=state['tools']['controlGroups'][0];self.assertEqual(len(group['members']),2)
        gains=[p for p in group['params'] if p['name'].endswith('_Gain')]
        state,path=self.worker({'action':'mutate','operation':'parameter','id':gains[1]['id'],'value':-1},path)
        state,path=self.worker({'action':'mutate','operation':'control-group-rename','group':gid,'name':'Differential ailerons'},path)
        self.assertEqual(state['tools']['controlGroups'][0]['name'],'Differential ailerons')
        self.v.ClearVSPModel();self.v.ReadVSPFile(str(path));self.assertEqual(self.v.GetParmVal(gains[1]['id']),-1)
        group=state['tools']['controlGroups'][0]
        with self.assertRaises(ValueError):self.worker({'action':'mutate','operation':'control-group-member','group':gid,'member':1,'expectedName':'wrong','add':False},path)
        state,path=self.worker({'action':'mutate','operation':'control-group-member','group':gid,'member':1,'expectedName':group['members'][0],'add':False},path)
        self.assertEqual(len(state['tools']['controlGroups'][0]['members']),1)
        state,path=self.worker({'action':'mutate','operation':'control-group-delete','group':gid},path);self.assertFalse(state['tools']['controlGroups'])

    def test_native_airfoil_exports_preserve_model_and_coordinates(self):
        state,path=self.worker({'action':'export-geometry','kind':'airfoil','geom':self.gid,'format':'selig','u':.5})
        coords=[list(map(float,line.split())) for line in (path.parent/state['filename']).read_text().splitlines()[1:] if line.strip()]
        expected=self.v.GetAirfoilCoordinates(self.gid,.5);self.assertEqual(len(coords),len(expected))
        for p,q in zip(coords,expected):
            self.assertAlmostEqual(p[0],q.x(),places=6);self.assertAlmostEqual(p[1],q.y(),places=6)
        self.assertEqual(path.read_bytes(),self.model.read_bytes())
        state,path=self.worker({'action':'export-geometry','kind':'airfoil','geom':self.gid,'format':'bezier','u':.5})
        self.assertGreater((path.parent/state['filename']).stat().st_size,100)


@unittest.skipUnless(sys.version_info[:2]==(3,11), 'Run with OpenVSP Python 3.11.')
class NativeTransactions(unittest.TestCase):
    def setUp(self):
        import native_service as service
        self.s=service;self.temp=tempfile.TemporaryDirectory(prefix='vsp-transaction-test-')
        self.original=(service.WORK,service.MODEL,service.HISTORY,service.FUTURE,service.REVISION)
        service.WORK=Path(self.temp.name);service.MODEL=service.WORK/'model.vsp3';service.HISTORY=[];service.FUTURE=[];service.REVISION='test'
        self.state=service.state()

    def tearDown(self):
        self.s.WORK,self.s.MODEL,self.s.HISTORY,self.s.FUTURE,self.s.REVISION=self.original
        self.temp.cleanup()

    def test_noop_section_error_preserves_original_file(self):
        before=self.s.MODEL.read_bytes()
        with self.assertRaises(ValueError):
            self.s.mutation({'revision':self.state['revision'],'operation':'insert-section','geom':self.state['components'][0]['id'],'index':0,'surface':0,'shape':7})
        self.assertEqual(before,self.s.MODEL.read_bytes())
        self.assertFalse(self.s.HISTORY)

    def test_stale_edit_and_undo_are_rejected(self):
        with self.assertRaises(ValueError):self.s.mutation({'revision':'stale','operation':'add','type':'POD'})
        with self.assertRaises(ValueError):self.s.undo(revision='stale')

    def test_undo_redo_preserves_native_model(self):
        original=self.s.MODEL.read_bytes()
        result=self.s.mutation({'revision':self.state['revision'],'operation':'add','type':'FUSELAGE'})
        self.assertEqual(len(result['components']),2)
        undo=self.s.undo(revision=result['revision'])
        self.assertEqual(self.s.MODEL.read_bytes(),original)
        redo=self.s.undo(True,revision=undo['revision'])
        self.assertEqual(len(redo['components']),2)


if __name__=='__main__':unittest.main()
