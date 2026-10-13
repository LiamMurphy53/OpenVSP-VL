"""Native structural references, spar stations, array expansion and regions."""
import sys
import unittest
import test_native
from vsp_runtime import load


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class StructuralWorkflows(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def structure(self):
        state,path=self.worker(dict(action='mutate',operation='structure-add',geom=self.gid,name='Native wing'))
        return state['tools']['structures'][0]['id'],path

    def test_rib_reference_order_and_trim_flags_survive_reopen(self):
        sid,path=self.structure();parts={}
        for typ,label in [('FEA_RIB','Normal rib'),('FEA_SPAR','Reference spar'),('FEA_TRIM','Trim')]:
            state,path=self.worker(dict(action='mutate',operation='part-add',structure=sid,type=typ,name=label),path)
            parts[typ]=next(p for p in state['tools']['structures'][0]['parts'] if p['name']==label)
        rib,spar,trim=[parts[t]['id'] for t in ['FEA_RIB','FEA_SPAR','FEA_TRIM']]
        state,path=self.worker(dict(action='mutate',operation='part-perpendicular-spar',structure=sid,id=rib,spar=spar),path)
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        self.assertEqual(v.GetFeaPartPerpendicularSparID(rib),spar)
        self.assertEqual(v.GetParmVal(v.FindParm(rib,'PerpendicularEdgeType','FeaRib')),v.SPAR_NORMAL)
        state,path=self.worker(dict(action='mutate',operation='part-trim-add',structure=sid,id=trim,target=spar),path)
        part=next(p for p in state['tools']['structures'][0]['parts'] if p['id']==trim)
        flag=next(p for p in part['params'] if p['name']=='FlipFlag_0')
        state,path=self.worker(dict(action='mutate',operation='parameter',id=flag['id'],value=1),path)
        state,path=self.worker(dict(action='mutate',operation='part-reorder',structure=sid,id=rib,direction='REORDER_MOVE_TOP'),path)
        self.assertEqual(state['tools']['structures'][0]['parts'][0]['id'],rib)
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        self.assertEqual(list(v.GetFeaTrimPartIDVec(trim)),[spar]);self.assertEqual(v.GetParmVal(flag['id']),1)
        for target in [trim,next(p['id'] for p in state['tools']['structures'][0]['parts'] if p['id'] not in (rib,spar,trim))]:
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='part-trim-add',structure=sid,id=trim,target=target),path)
        state,path=self.worker(dict(action='mutate',operation='part-trim-delete',structure=sid,id=trim,target=spar),path)
        self.assertEqual(next(p for p in state['tools']['structures'][0]['parts'] if p['id']==trim)['trimTargets'],[])

    def test_polyline_spar_point_edits_match_direct_native_mesh(self):
        from mesh_io import read_gmsh
        sid,path=self.structure()
        state,path=self.worker(dict(action='mutate',operation='part-add',structure=sid,type='FEA_POLY_SPAR',name='Curved spar'),path)
        part=next(p for p in state['tools']['structures'][0]['parts'] if p['name']=='Curved spar');pid=part['id']
        state,path=self.worker(dict(action='mutate',operation='part-point-insert',structure=sid,id=pid,point=part['points'][1]['id']),path)
        part=next(p for p in state['tools']['structures'][0]['parts'] if p['id']==pid)
        self.assertEqual(len(part['points']),3)
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        entries=[]
        for pt,eta,xoc in zip(part['points'],[.1,.5,.9],[.2,.5,.3]):
            for key,value in [('Eta',eta),('XoC',xoc)]:
                parm=next(p['id'] for p in pt['params'] if p['name']==key)
                v.SetParmValUpdate(parm,value);entries.append((parm,value))
        expected=self.path/'expected.vsp3';v.WriteVSPFile(str(expected),v.SET_ALL)
        for parm,value in entries:state,path=self.worker(dict(action='mutate',operation='parameter',id=parm,value=value),path)
        part=next(p for p in state['tools']['structures'][0]['parts'] if p['id']==pid)
        request=dict(action='analysis',name='FeaMeshAnalysis',structure=sid,formats=['GMSH'],inputs=[dict(name=n,values=[x]) for n,x in [('BaseLen',1.),('MinLen',.2),('MaxGap',.03)]])
        _,a=self.worker(request,path);_,b=self.worker(request,expected)
        ma=read_gmsh(a.parent/'structure.msh');mb=read_gmsh(b.parent/'structure.msh')
        self.assertEqual(ma['nodes'],mb['nodes']);self.assertEqual(ma['elements'],mb['elements'])
        point=part['points'][1]['id']
        state,path=self.worker(dict(action='mutate',operation='part-point-rename',structure=sid,id=pid,point=point,name='Mid span'),path)
        state,path=self.worker(dict(action='mutate',operation='part-point-reorder',structure=sid,id=pid,point=point,direction='REORDER_MOVE_TOP'),path)
        part=next(p for p in state['tools']['structures'][0]['parts'] if p['id']==pid)
        self.assertEqual((part['points'][0]['id'],part['points'][0]['name']),(point,'Mid span'))
        state,path=self.worker(dict(action='mutate',operation='part-point-delete',structure=sid,id=pid,point=point),path)
        remaining=next(p for p in state['tools']['structures'][0]['parts'] if p['id']==pid)['points']
        self.assertEqual(len(remaining),2)
        with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='part-point-delete',structure=sid,id=pid,point=remaining[0]['id']),path)

    def test_array_expansion_uses_native_parts_and_preserves_dimensions(self):
        sid,path=self.structure()
        state,path=self.worker(dict(action='mutate',operation='part-add',structure=sid,type='FEA_RIB_ARRAY',name='Ribs'),path)
        array=next(p for p in state['tools']['structures'][0]['parts'] if p['name']=='Ribs')
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        v.ExportFile(str(self.path/'direct-structure.igs'),v.SET_ALL,v.EXPORT_IGES_STRUCTURE)
        v.IndividualizeFeaPart(self.gid,v.GetFeaStructIndex(sid),array['id']);v.Update()
        expected=[[(v.GetParmName(p),v.GetParmVal(p)) for p in v.FindContainerParmIDs(part) if v.GetParmName(p) in ('RelCenterLocation','Theta','FeaPropertyIndex')] for part in v.GetFeaPartIDVec(sid)]
        state,path=self.worker(dict(action='mutate',operation='part-individualize',structure=sid,id=array['id']),path)
        parts=state['tools']['structures'][0]['parts']
        self.assertNotIn(array['id'],[p['id'] for p in parts]);self.assertGreater(len(parts),2)
        actual=[[(p['name'],p['value']) for p in part['params'] if p['name'] in ('RelCenterLocation','Theta','FeaPropertyIndex')] for part in parts]
        self.assertEqual(actual,expected)

    def test_native_surface_regions_and_intersection_persist(self):
        v=self.v;v.ClearVSPModel();g=v.AddGeom('POD');other=v.AddGeom('POD');v.SetParmVal(other,'X_Rel_Location','XForm',4);v.SetParmVal(other,'Z_Rel_Rotation','XForm',60);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,path=self.worker(dict(action='mutate',operation='subsurface-add',geom=g,type='SS_RECTANGLE',name='Patch'))
        rect=state['tools']['controls'][0]['id']
        state,path=self.worker(dict(action='mutate',operation='subsurface-add',geom=g,type='SS_INTERSECT',name='Join'),path)
        region=next(p for p in state['tools']['controls'] if p['name']=='Join')['id']
        state,path=self.worker(dict(action='mutate',operation='subsurface-intersect',geom=g,id=region,target=other),path)
        self.assertEqual(next(p for p in state['tools']['controls'] if p['id']==region)['intersectionTarget'],other)
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();self.assertEqual(v.GetIntersectSubSurfGeomID(region),other)
        state,path=self.worker(dict(action='mutate',operation='subsurface-reorder',geom=g,id=region,direction='REORDER_MOVE_TOP'),path)
        self.assertEqual([p['id'] for p in state['tools']['controls']],[region,rect])
        with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='subsurface-intersect',geom=g,id=region,target=g),path)

    def test_structural_cad_export_selects_requested_structure(self):
        v=self.v;v.ClearVSPModel();structures=[]
        for x in [0.,100.]:
            g=v.AddGeom('POD');v.SetParmVal(g,'X_Rel_Location','XForm',x)
            i=v.AddFeaStruct(g);structures.append(v.GetFeaStructID(g,i))
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        for fmt,group,suffix in [('IGES_STRUCTURE','IGESSettings','igs'),('STEP_STRUCTURE','STEPSettings','stp')]:
            with self.subTest(format=fmt):
                def geometry(text):
                    if suffix=='igs':return '\n'.join(line for line in text.splitlines() if line[72:73]=='P')
                    return text.split('DATA;',1)[1].split('ENDSEC;',1)[0]
                v.SetParmVal(v.FindParm(v.GetVehicleID(),'StructureExportIndex',group),0)
                wrong=self.path/('wrong.'+suffix);v.ExportFile(str(wrong),v.SET_ALL,getattr(v,'EXPORT_'+fmt))
                v.SetParmVal(v.FindParm(v.GetVehicleID(),'StructureExportIndex',group),1)
                direct=self.path/('direct.'+suffix);v.ExportFile(str(direct),v.SET_ALL,getattr(v,'EXPORT_'+fmt))
                self.assertNotEqual(geometry(wrong.read_text()),geometry(direct.read_text()))
                result,out=self.worker(dict(action='export-geometry',format=fmt,set=0,structure=structures[1]))
                actual=geometry((out.parent/result['filename']).read_text())
                self.assertEqual(actual,geometry(direct.read_text()))
                self.assertEqual(out.read_bytes(),self.model.read_bytes())


if __name__=='__main__':unittest.main()
