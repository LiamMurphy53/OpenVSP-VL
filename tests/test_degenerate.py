"""Native degenerate guides preserve every result, sample and mesh."""
import json,sys,unittest
import test_native,test_guides
import native_worker,native_degenerate
from mesh_io import read_gmsh
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativeDegenerate(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    fixture=test_guides.NativeGuides.fixture
    direct=test_guides.NativeGuides.direct

    def canonical(self,results,value):
        refs={r['id']:(r['name'],r['index']) for r in results}
        def convert(x):
            if isinstance(x,str):return refs.get(x,x)
            if isinstance(x,list):return [convert(t) for t in x]
            if isinstance(x,dict):return {k:convert(t) for k,t in x.items()}
            return x
        return convert(value)

    def assertResults(self,expected,actual):
        def entries(rows):return {(r['name'],r['index']):[(e['name'],e['index'],e['type'],self.canonical(rows,e['values'])) for e in r['entries'] if e['name'] not in ('Analysis_Duration_Sec','Mesh_GeomID')] for r in rows}
        self.assertEqual(entries(expected),entries(actual))

    def test_native_grids_sticks_point_properties_modes_and_files_match(self):
        self.fixture();v=self.v
        prop=v.AddGeom('PROP');v.SetGeomName(prop,'Native propeller');v.SetParmValUpdate(v.FindParm(prop,'Y_Rel_Location','XForm'),5.)
        v.SetSetName(5,'Propeller only');v.SetSetFlag(prop,5,True)
        mode=v.CreateAndAddMode('Wing preset',3,-1);group=v.AddVarPresetGroup('Wing offset');pid=v.FindParm(self.gid,'Z_Rel_Location','XForm');v.AddVarPresetParm(group,pid);setting=v.AddVarPresetSetting(group,'Raised');v.SetVarPresetParmVal(group,setting,pid,2.);v.ModeAddGroupSetting(mode,group,setting)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);baseline=self.model.read_bytes()
        cases=[dict(Set=[0],WriteCSVFlag=[1],WriteMFileFlag=[1]),dict(Set=[4],WriteCSVFlag=[0],WriteMFileFlag=[0]),dict(Set=[5],WriteCSVFlag=[1],WriteMFileFlag=[0]),dict(UseModeFlag=[1],ModeID=[mode],WriteCSVFlag=[0],WriteMFileFlag=[1])]
        for inputs in cases:
            with self.subTest(inputs=inputs):
                expected=self.direct('DegenGeom',inputs);drawing=native_degenerate.geometry(expected)
                direct_files={ext:(self.path/('direct_DegenGeom.'+ext)).read_bytes() for ext,flag in [('csv',inputs['WriteCSVFlag'][0]),('m',inputs['WriteMFileFlag'][0])] if flag}
                data,path=self.worker(dict(action='analysis',name='DegenGeom',inputs=[dict(name=n,values=x) for n,x in inputs.items()]))
                self.assertResults(expected,data['results']);actual=json.loads((path.parent/data['guideFile']).read_text())
                self.assertEqual(self.canonical(expected,drawing),self.canonical(data['results'],actual));self.assertTrue(actual['nodes']);self.assertTrue(actual['elements'])
                for ext,raw in direct_files.items():self.assertEqual((path.parent/('aircraft_DegenGeom.'+ext)).read_bytes(),raw)
                for ext,flag in [('csv',inputs['WriteCSVFlag'][0]),('m',inputs['WriteMFileFlag'][0])]:self.assertEqual((path.parent/('aircraft_DegenGeom.'+ext)).exists(),bool(flag))
                for r in expected:
                    if r['name'] in ('Degen_surf','Degen_plate'):
                        actual_id=next(a['id'] for a in data['results'] if (a['name'],a['index'])==(r['name'],r['index']))
                        for group in [g for g in actual['groups'] if g['nativeResultID']==actual_id]:
                            keys=['xCamberx','xCambery','xCamberz'] if ' · camber ' in group['name'] else ['x','y','z']
                            axes=[list(v.GetDoubleMatResults(r['id'],k)) for k in keys]
                            expected_points=[list(p) for rows in zip(*axes) for p in zip(*rows)]
                            cells=[e for e in actual['elements'] if e['group']==group['id']]
                            indices=[n for e in cells for n in e['nodes']];start=min(indices)
                            self.assertEqual(actual['nodes'][start:max(indices)+1],expected_points)
                            self.assertEqual(group['rows'],len(axes[0]));self.assertEqual(group['columns'],len(axes[0][0]))
                            if r['name']=='Degen_surf':self.assertEqual(cells[0]['nativeNormal'],[v.GetDoubleMatResults(r['id'],k)[0][0] for k in ['nx','ny','nz']])
                self.assertEqual(path.read_bytes(),baseline);self.assertEqual(self.model.read_bytes(),baseline)

    def test_all_mesh_settings_match_direct_export_and_preserve_generated_native_type(self):
        self.fixture();v=self.v;slot=v.GetNumSets()-1;v.SetSetFlag(self.gid,slot,True);v.SetSetName(slot,'Existing members');v.WriteVSPFile(str(self.model),v.SET_ALL);baseline=self.model.read_bytes()
        meshes=[]
        for typ in (v.TRI_MESH_TYPE,v.QUAD_MESH_TYPE,v.NGON_MESH_TYPE):
            with self.subTest(meshType=typ):
                expected=self.direct('DegenGeomMesh',dict(Set=[0],DegenGeomMeshType=[typ]));r=next(r for r in expected if r['name']=='DegenGeomMesh');gid=next(e['values'][0] for e in r['entries'] if e['name']=='Mesh_GeomID');kind=v.GetGeomTypeName(gid);before=set(v.FindGeoms());flags={g:(v.GetSetFlag(g,slot),v.GetSetFlag(g,v.SET_SHOWN)) for g in before}
                for g in before:v.SetSetFlag(g,slot,g==gid)
                filename=self.path/'direct-degenerate.msh';v.ExportFile(str(filename),slot,v.EXPORT_GMSH,1);native_worker.errors(v);mesh=read_gmsh(filename)
                for g in set(v.FindGeoms())-before:v.DeleteGeom(g)
                for g,(member,shown) in flags.items():v.SetSetFlag(g,slot,member);v.SetSetFlag(g,v.SET_SHOWN,shown)
                polygon_bytes=None;polygon_companions={}
                if typ==v.NGON_MESH_TYPE:
                    selected=set(v.FindGeoms());saved_flags={g:(v.GetSetFlag(g,slot),v.GetSetFlag(g,v.SET_SHOWN)) for g in selected}
                    for g in selected:v.SetSetFlag(g,slot,g==gid)
                    existing_files=set(self.path.iterdir())
                    direct_polygon=self.path/'direct-polygons.vspgeom';v.ExportFile(str(direct_polygon),slot,v.EXPORT_VSPGEOM,1);native_worker.errors(v);polygon_bytes=direct_polygon.read_bytes()
                    polygon_companions={p.name.replace('direct-polygons','degenerate-polygons'):p.read_bytes() for p in set(self.path.iterdir())-existing_files if p.is_file()}
                    for g in set(v.FindGeoms())-selected:v.DeleteGeom(g)
                    for g,(member,shown) in saved_flags.items():v.SetSetFlag(g,slot,member);v.SetSetFlag(g,v.SET_SHOWN,shown)
                data,path=self.worker(dict(action='analysis',name='DegenGeomMesh',inputs=[dict(name='Set',values=[0]),dict(name='DegenGeomMeshType',values=[typ])]))
                self.assertResults(expected,data['results']);actual=read_gmsh(path.parent/data['meshFile'])
                for key in ('nodes','nodeIDs','elements','groups','higherOrder','unsupportedElements'):self.assertEqual(actual[key],mesh[key])
                self.assertEqual(data['degenerateMesh']['nativeGeomType'],kind)
                self.assertEqual(data['degenerateMesh']['modelGeometrySaved'],typ!=v.NGON_MESH_TYPE)
                if polygon_bytes is not None:
                    meta=data['degenerateMesh'];self.assertEqual((path.parent/meta['polygonFile']).read_bytes(),polygon_bytes)
                    self.assertIn(meta['polygonFile'],meta['polygonFiles']);self.assertEqual(set(meta['polygonFiles']),set(polygon_companions))
                    for filename,raw in polygon_companions.items():self.assertEqual((path.parent/filename).read_bytes(),raw.replace(str(self.path/'direct-polygons').encode(),str((path.parent/'degenerate-polygons').resolve()).encode()).replace(b'direct-polygons',b'degenerate-polygons'))
                    self.assertTrue(all((path.parent/name).is_file() for name in meta['polygonFiles']))

                v.ClearVSPModel();v.ReadVSPFile(str(path.parent/data['degenerateMesh']['modelFile']));v.Update();native_worker.errors(v)
                self.assertEqual(set(v.FindGeoms()),{self.gid,self.pod,data['degenerateMesh']['nativeGeomID']});self.assertEqual(v.GetGeomTypeName(data['degenerateMesh']['nativeGeomID']),kind)
                if typ==v.NGON_MESH_TYPE:
                    # The original engine retains the type/parameters but loses
                    # polygon data in VSP3. Do not treat type identity as geometry.
                    for g in v.FindGeoms():v.SetSetFlag(g,slot,g==data['degenerateMesh']['nativeGeomID'])
                    cold_mesh=self.path/'cold-polygons.msh';v.ExportFile(str(cold_mesh),slot,v.EXPORT_GMSH,1);native_worker.errors(v)
                    with self.assertRaisesRegex(ValueError,'no displayable mesh'):read_gmsh(cold_mesh)
                    v.SetSetFlag(self.gid,slot,True);v.SetSetFlag(self.pod,slot,False)
                self.assertTrue(v.GetSetFlag(self.gid,slot));self.assertFalse(v.GetSetFlag(self.pod,slot));self.assertEqual(v.GetSetName(slot),'Existing members')
                self.assertEqual(path.read_bytes(),baseline);self.assertEqual(self.model.read_bytes(),baseline);meshes.append(actual)
        self.assertEqual(meshes[0]['nodes'],meshes[1]['nodes']);self.assertEqual(meshes[0]['elements'],meshes[1]['elements'])

    def test_blank_points_and_empty_normal_mode_remain_valid_native_results(self):
        self.fixture();v=self.v;blank=v.AddGeom('BLANK');v.SetGeomName(blank,'Saved blank mass');v.SetParmValUpdate(v.FindParm(blank,'PointMass','Mass_Props'),2.);v.SetParmValUpdate(v.FindParm(blank,'X_Rel_Location','XForm'),7.);v.SetSetFlag(blank,5,True);mode=v.CreateAndAddMode('Thin-only mode',-1,3);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        for inputs,has_points in [(dict(Set=[5]),True),(dict(UseModeFlag=[1],ModeID=[mode]),False)]:
            expected=self.direct('DegenGeom',inputs);data,path=self.worker(dict(action='analysis',name='DegenGeom',inputs=[dict(name=n,values=x) for n,x in inputs.items()]));self.assertResults(expected,data['results']);drawing=json.loads((path.parent/data['guideFile']).read_text());self.assertEqual(bool(drawing['nodes']),has_points)
            if has_points:self.assertEqual(drawing['nodes'],[[7.,0.,0.]]);self.assertEqual(drawing['elements'][0]['nativeMass'],2.)
            else:self.assertTrue(drawing['warnings'])
        with self.assertRaises(ValueError):self.worker(dict(action='analysis',name='DegenGeomMesh',inputs=[dict(name='Set',values=[5])]))

    def test_invalid_guided_selections_reject_before_execution(self):
        self.fixture();baseline=self.model.read_bytes()
        for name,inputs in [('DegenGeom',dict(Set=[-1])),('DegenGeom',dict(Set=[20])),('DegenGeom',dict(UseModeFlag=[1],ModeID=['missing'])),('DegenGeom',dict(WriteCSVFlag=[2])),('DegenGeom',dict(WriteMFileFlag=[2])),('DegenGeomMesh',dict(Set=[999])),('DegenGeomMesh',dict(DegenGeomMeshType=[99]))]:
            with self.subTest(name=name,inputs=inputs),self.assertRaises(ValueError):self.worker(dict(action='analysis',name=name,inputs=[dict(name=n,values=x) for n,x in inputs.items()]))
            self.assertEqual(self.model.read_bytes(),baseline)
