"""Native engineering edits, persistence, and solver-ready structural exports."""
import sys
import unittest
import test_native
from vsp_runtime import load


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class AdvancedNative(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_blade_curves_match_direct_native_surfaces_and_persist(self):
        v=self.v;gid=v.AddGeom('PROP');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        v.PCurveConvertTo(gid,v.PROP_CHORD,v.PCHIP)
        stations=[.2,.45,.7,1.];values=[.08,.19,.15,.04]
        v.SetPCurve(gid,v.PROP_CHORD,stations,values,v.PCHIP);v.Update()
        expected=v.CompVecPnt01(gid,0,[.1,.3,.5,.8],[.2,.4,.6,.8])
        state,path=self.worker({'action':'mutate','operation':'prop-curve-type','geom':gid,'curve':'PROP_CHORD','type':'PCHIP'})
        state,path=self.worker({'action':'mutate','operation':'prop-curve-set','geom':gid,'curve':'PROP_CHORD','stations':stations,'values':values},path)
        curve=next(p for p in state['tools']['propellers'][0]['curves'] if p['name']=='PROP_CHORD')
        self.assertEqual(curve['stations'],stations);self.assertEqual(curve['values'],values)
        v.ClearVSPModel();v.ReadVSPFile(str(path));actual=v.CompVecPnt01(gid,0,[.1,.3,.5,.8],[.2,.4,.6,.8])
        for p,q in zip(expected,actual):
            for a,b in zip([p.x(),p.y(),p.z()],[q.x(),q.y(),q.z()]):self.assertAlmostEqual(a,b,places=10)
        state,path=self.worker({'action':'mutate','operation':'prop-curve-split','geom':gid,'curve':'PROP_CHORD','station':.6},path)
        curve=next(p for p in state['tools']['propellers'][0]['curves'] if p['name']=='PROP_CHORD');self.assertIn(.6,curve['stations'])
        with self.assertRaises(ValueError):self.worker({'action':'mutate','operation':'prop-curve-set','geom':gid,'curve':'PROP_CHORD','stations':[.5,.2],'values':[1.,1.]},path)

    def test_boundary_target_survives_native_save_and_is_exported(self):
        state,path=self.worker({'action':'mutate','operation':'structure-add','geom':self.gid,'name':'Wing structure'})
        s=state['tools']['structures'][0];sid=s['id'];skin=s['parts'][0]['id']
        state,path=self.worker({'action':'mutate','operation':'boundary-add','structure':sid,'type':'FEA_BC_PART','name':'Skin clamp'},path)
        b=state['tools']['boundaryConditions'][0]
        state,path=self.worker({'action':'mutate','operation':'boundary-target','structure':sid,'id':b['id'],'target':skin},path)
        self.assertEqual(state['tools']['boundaryConditions'][0]['references']['PartID'],skin)
        con=next(p['id'] for p in b['params'] if p['name']=='ConMode')
        state,path=self.worker({'action':'mutate','operation':'parameter','id':con,'value':self.v.FEA_BCM_ALL},path)
        b=state['tools']['boundaryConditions'][0]
        self.assertEqual(next(p['value'] for p in b['params'] if p['name']=='ConMode'),self.v.FEA_BCM_ALL)
        before=path.read_bytes()
        result,out=self.worker({'action':'analysis','name':'FeaMeshAnalysis','structure':sid,'formats':['CALCULIX','NASTRAN','MASS'],'inputs':[{'name':n,'values':[x]} for n,x in [('BaseLen',1.),('MinLen',.2),('MaxGap',.03)]]},path)
        self.assertEqual(out.read_bytes(),before)
        calculix=(out.parent/'structure.inp').read_text()
        self.assertIn('*BOUNDARY',calculix.upper())
        boundary_block=calculix.upper().split('*BOUNDARY',1)[1].split('\n*',1)[0]
        directions={int(line.split(',')[1]) for line in boundary_block.splitlines() if line and line[0].isdigit() and ',' in line}
        self.assertEqual(directions,{1,2,3,4,5,6})
        self.assertGreater((out.parent/'structure.bdf').stat().st_size,100)
        self.assertGreater((out.parent/'structure.txt').stat().st_size,50)
        self.assertGreater(result['meshSummary']['nodes'],10)

    def test_laminate_native_layer_math_and_material_references_persist(self):
        state,path=self.worker({'action':'mutate','operation':'material-add','name':'Laminate'})
        m=next(m for m in state['tools']['materials'] if m['name']=='Laminate')
        pid=next(p['id'] for p in m['params'] if p['name']=='FeaMaterialType')
        state,path=self.worker({'action':'mutate','operation':'parameter','id':pid,'value':self.v.FEA_LAMINATE},path)
        l=next(l for l in state['tools']['layers'] if l['material']==m['id'])
        lamina=next(x for x in state['tools']['materials'] if x['id'].startswith('_') and 'ALUMINUM' in x['name'].upper())
        state,path=self.worker({'action':'mutate','operation':'layer-material','material':m['id'],'id':l['id'],'lamina':lamina['id']},path)
        thickness=next(p['id'] for p in l['params'] if p['name']=='Thickness')
        state,path=self.worker({'action':'mutate','operation':'parameter','id':thickness,'value':.04},path)
        state,path=self.worker({'action':'mutate','operation':'layer-add','material':m['id']},path)
        self.v.ClearVSPModel();self.v.ReadVSPFile(str(path));self.v.Update()
        material=next(x for x in state['tools']['materials'] if x['id']==m['id'])
        for p in material['params']:
            if p['name'].endswith('_FEM'):self.assertAlmostEqual(p['value'],self.v.GetParmVal(p['id']),places=8)
        self.assertGreater(next(p['value'] for p in material['params'] if p['name']=='E1_FEM'),0)
        layer=next(x for x in state['tools']['layers'] if x['id']==l['id'])
        self.assertAlmostEqual(next(p['value'] for p in layer['params'] if p['name']=='Thickness'),.04)
        self.assertEqual(len([l for l in state['tools']['layers'] if l['material']==m['id']]),2)
        with self.assertRaises(ValueError):self.worker({'action':'mutate','operation':'layer-material','material':m['id'],'id':layer['id'],'lamina':m['id']},path)

    def test_assembly_exports_native_member_mesh_and_connections(self):
        v=self.v;v.ClearVSPModel();members=[];points=[]
        for offset in [0.,3.]:
            g=v.AddGeom('POD');v.SetParmVal(g,'X_Rel_Location','XForm',offset);i=v.AddFeaStruct(g);sid=v.GetFeaStructID(g,i)
            p=v.AddFeaPart(g,i,v.FEA_FIX_POINT);members.append(sid);points.append(p)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,path=self.worker({'action':'mutate','operation':'assembly-add','name':'Joined pods'})
        aid=state['tools']['assemblies'][0]['id']
        for sid in members:state,path=self.worker({'action':'mutate','operation':'assembly-member','id':aid,'structure':sid,'member':True},path)
        state,path=self.worker({'action':'mutate','operation':'assembly-connection-add','assembly':aid,'startStructure':members[0],'startPoint':points[0],'endStructure':members[1],'endPoint':points[1]},path)
        a=state['tools']['assemblies'][0];self.assertEqual(len(a['connections']),1)
        self.assertEqual(a['connections'][0]['references']['StartStructID'],members[0])
        before=path.read_bytes()
        result,out=self.worker({'action':'analysis','name':'FeaAssemblyMesh','structure':aid,'formats':['CALCULIX','NASTRAN','MASS'],'inputs':[{'name':n,'values':[x]} for n,x in [('BaseLen',1.),('MinLen',.2),('MaxGap',.03)]]},path)
        self.assertEqual(out.read_bytes(),before);self.assertEqual(result['members'],members)
        self.assertGreater(result['meshSummary']['nodes'],100)
        deck=(out.parent/'assembly.inp').read_text().upper()
        self.assertIn('*EQUATION',deck)
        self.assertGreater((out.parent/'assembly.bdf').stat().st_size,100)
        self.assertTrue(all(any(s in g['name'] for g in result['meshSummary']['groups']) for s in ['Skin']))

    def test_native_expressions_drive_outputs_and_reject_cycles_and_bad_syntax(self):
        state,path=self.worker({'action':'mutate','operation':'user-add','name':'Expression input','value':8})
        source=next(p['id'] for p in state['tools']['userParameters'] if p['name']=='Expression input')
        target=next(p['id'] for p in state['components'][0]['params'] if p['name']=='X_Rel_Location')
        definition=dict(operation='advanced-link-save',name='Location expression',inputs=[dict(name='length',parameter=source)],outputs=[dict(name='position',parameter=target)],code='position = 10.0 - length;')
        state,path=self.worker(dict(action='mutate',**definition),path)
        link=state['tools']['advancedLinks'][0]
        state,path=self.worker({'action':'mutate','operation':'parameter','id':source,'value':6},path)
        self.assertAlmostEqual(next(p['value'] for p in state['components'][0]['params'] if p['id']==target),4)
        with self.assertRaises(ValueError):self.worker(dict(action='mutate',**(definition|dict(index=link['index'],expectedName=link['name'],code='position = nonsense;'))),path)
        with self.assertRaises(ValueError):self.worker(dict(action='mutate',**(definition|dict(name='Cycle',inputs=[dict(name='position',parameter=target)],outputs=[dict(name='length',parameter=source)]))),path)
        state,path=self.worker({'action':'mutate','operation':'advanced-link-delete','index':link['index'],'expectedName':link['name']},path)
        state,path=self.worker({'action':'mutate','operation':'parameter','id':source,'value':7},path)
        self.assertAlmostEqual(next(p['value'] for p in state['components'][0]['params'] if p['id']==target),4)

    def test_variable_bounds_and_multiple_preset_settings_are_native(self):
        state,path=self.worker({'action':'mutate','operation':'user-add','name':'Bounded variable','value':8})
        pid=next(p['id'] for p in state['tools']['userParameters'] if p['name']=='Bounded variable')
        state,path=self.worker({'action':'mutate','operation':'user-limits','id':pid,'min':3,'max':7},path)
        p=next(p for p in state['tools']['userParameters'] if p['id']==pid)
        self.assertEqual((p['min'],p['max'],p['value']),(3,7,7))
        state,path=self.worker({'action':'mutate','operation':'preset-save','name':'Variable configurations','parameters':[pid]},path)
        preset=state['tools']['presets'][0]
        state,path=self.worker({'action':'mutate','operation':'parameter','id':pid,'value':4},path)
        state,path=self.worker({'action':'mutate','operation':'preset-setting-add','group':preset['id'],'name':'Reduced'},path)
        preset=state['tools']['presets'][0];self.assertEqual([s['values'] for s in preset['settings']],[[7.],[4.]])
        state,path=self.worker({'action':'mutate','operation':'preset-apply','group':preset['id'],'setting':preset['settings'][0]['id']},path)
        self.assertEqual(next(p['value'] for p in state['tools']['userParameters'] if p['id']==pid),7)
        state,path=self.worker({'action':'mutate','operation':'design-variables','entries':[dict(parameter=pid,type=self.v.XDDM_VAR)]},path)
        self.assertEqual(state['tools']['designVariables'],[dict(parameter=pid,type=self.v.XDDM_VAR)])
        state,path=self.worker({'action':'state'},path)
        self.assertEqual(state['tools']['designVariables'],[dict(parameter=pid,type=self.v.XDDM_VAR)])

    def test_native_mesh_import_preview_uses_transformed_engine_triangles(self):
        import base64
        stl='solid test\nfacet normal 0 0 1\n outer loop\n vertex 0 0 0\n vertex 1 0 0\n vertex 0 1 0\n endloop\nendfacet\nendsolid test\n'
        state,path=self.worker({'action':'mutate','operation':'geometry-import','format':'STL','content':base64.b64encode(stl.encode()).decode(),'name':'Imported triangle'})
        g=next(c for c in state['components'] if c['name']=='Imported triangle');self.assertEqual(g['type'],'Mesh')
        self.assertEqual(g['mesh']['triangles'],[[0,1,2]])
        x=next(p['id'] for p in g['params'] if p['name']=='X_Rel_Location')
        state,path=self.worker({'action':'mutate','operation':'parameter','id':x,'value':3},path)
        g=next(c for c in state['components'] if c['id']==g['id'])
        self.assertEqual(g['mesh']['points'],[[3.,0.,0.],[4.,0.,0.],[3.,1.,0.]])
        self.v.ClearVSPModel();self.v.ReadVSPFile(str(path));rid=self.v.CreateGeomResults(g['id'],'Direct')
        points=[[p.x(),p.y(),p.z()] for p in self.v.GetVec3dResults(rid,'Tri_Pnts')]
        self.assertEqual(g['mesh']['points'],points)
        with self.assertRaises(ValueError):self.worker({'action':'mutate','operation':'geometry-import','format':'STL','content':'invalid base64'},path)

    def test_geometry_formats_design_files_and_companion_exports_are_native(self):
        v=self.v;p=v.AddGeom('PROP');i=v.AddFeaStruct(self.gid);sid=v.GetFeaStructID(self.gid,i);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        for fmt in ['DXF','CART3D','VSPGEOM','PLOT3D','NASCART','BEM','SELIG_AIRFOILS','BEZIER_AIRFOILS','STEP_STRUCTURE','IGES_STRUCTURE','XSEC','POVRAY','X3D','FACET','PMARC']:
            with self.subTest(format=fmt):
                data,path=self.worker({'action':'export-geometry','format':fmt,'set':0,'geom':p,'structure':sid})
                self.assertTrue(data['files'],fmt)
                self.assertTrue(all((path.parent/f).stat().st_size for f in data['files']),fmt)
                self.assertEqual(path.read_bytes(),self.model.read_bytes())
        span=v.FindParm(self.gid,'TotalSpan','WingGeom');v.AddDesignVar(span,v.XDDM_VAR)
        import native_files
        native_files.save_design(v);v.WriteVSPFile(str(self.model),v.SET_ALL)
        result,path=self.worker({'action':'export-geometry','kind':'design-variables','format':'DES'})
        design=(path.parent/result['filename']).read_text()
        state,path=self.worker({'action':'mutate','operation':'parameter','id':span,'value':25})
        state,path=self.worker({'action':'mutate','operation':'design-file-apply','format':'DES','content':design},path)
        self.assertAlmostEqual(next(p['value'] for p in state['components'][0]['params'] if p['id']==span),v.GetParmVal(span))
        result,path=self.worker({'action':'export-geometry','kind':'design-variables','format':'XDDM'},path)
        self.assertIn('Variable',(path.parent/result['filename']).read_text())

    def test_thick_body_pressure_matches_official_slicer(self):
        from aero_io import read_adb
        from native_service import invoke
        v=self.v;v.ClearVSPModel();v.AddGeom('POD');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        inputs={n:x for n,x in [('AlphaStart',2.),('AlphaEnd',2.),('AlphaNpts',1),('MachStart',.1),('MachEnd',.1),('NCPU',1),('GeomSet',0),('ThinGeomSet',-1)]}
        geometry=[dict(name='GeomSet',values=[0]),dict(name='ThinGeomSet',values=[-1])]
        result,path=self.worker({'action':'analysis','name':'VSPAEROSweep','inputs':[dict(name=n,values=[x]) for n,x in inputs.items()],'geometryInputs':geometry})
        mesh=read_adb(path.with_suffix('.adb'));self.assertEqual(mesh['modelType'],2);self.assertEqual(mesh['pressureLabel'],'Cp')
        sliced=invoke({'action':'analysis','name':'CpSlicer','inputs':[dict(name='YSlicePosVec',values=[0.])]},path,path.parent)
        entries={e['name']:e['values'] for r in sliced['results'] if r['name']=='CpSlicer_Case' for e in r['entries']}
        accum=[0.]*len(mesh['nodes']);area=[0.]*len(mesh['nodes']);edges=set()
        for e,cp in zip(mesh['elements'],mesh['fields'][0]['values']):
            for n in e['nodes']:accum[n]+=cp*e['area'];area[n]+=e['area']
            a,b,c=e['nodes'];edges.update(tuple(sorted(pair)) for pair in [(a,b),(b,c),(c,a)])
        cp=[a/w if w else 0 for a,w in zip(accum,area)];samples=[]
        for a,b in edges:
            pa,pb=mesh['nodes'][a],mesh['nodes'][b]
            if pa[1]*pb[1]>0 or abs(pb[1]-pa[1])<1e-12:continue
            t=-pa[1]/(pb[1]-pa[1]);samples.append(([pa[k]+t*(pb[k]-pa[k]) for k in range(3)],cp[a]+t*(cp[b]-cp[a])))
        self.assertGreater(len(entries['Cp']),20)
        for x,y,z,value in zip(entries['X_Loc'],entries['Y_Loc'],entries['Z_Loc'],entries['Cp']):
            candidates=[q for p,q in samples if max(abs(a-b) for a,b in zip(p,[x,y,z]))<.00015]
            self.assertTrue(candidates,'Native thick-body slice must lie on decoded triangle edges.')
            self.assertLess(min(abs(c-value) for c in candidates),.00015)

    def test_global_settings_and_modes_supply_native_analysis_defaults(self):
        state,path=self.worker({'action':'state'})
        settings=next(g for g in state['tools']['globalSettings'] if g['name']=='VSPAEROSettings')
        p=next(p for p in settings['params'] if p['name']=='AlphaStart')
        state,path=self.worker({'action':'mutate','operation':'parameter','id':p['id'],'value':7},path)
        schema,_=self.worker({'action':'schema','name':'VSPAEROSweep'},path)
        self.assertEqual(next(e['values'] for e in schema['inputs'] if e['name']=='AlphaStart'),[7.])
        span=next(p['id'] for p in state['components'][0]['params'] if p['name']=='TotalSpan')
        original=next(p['value'] for p in state['components'][0]['params'] if p['id']==span)
        state,path=self.worker({'action':'mutate','operation':'preset-save','name':'Flight','parameters':[span]},path)
        preset=state['tools']['presets'][0]
        state,path=self.worker({'action':'mutate','operation':'mode-add','name':'Cruise','set':0},path)
        mode=state['tools']['modes'][0]
        state,path=self.worker({'action':'mutate','operation':'mode-preset-add','id':mode['id'],'group':preset['id'],'setting':preset['settings'][0]['id']},path)
        state,path=self.worker({'action':'mutate','operation':'parameter','id':span,'value':original+2},path)
        state,path=self.worker({'action':'mutate','operation':'mode-apply','id':mode['id']},path)
        self.assertAlmostEqual(next(p['value'] for p in state['components'][0]['params'] if p['id']==span),original)
        self.assertEqual(state['tools']['modes'][0]['groups'],[preset['id']])
