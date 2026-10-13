"""Native boundary coordinates, symmetry, identity and read-only query checks."""
import sys
import unittest
import test_native
import native_worker
from vsp_runtime import load


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativeOverlays(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def save(self):
        self.v.Update();self.v.WriteVSPFile(str(self.model),self.v.SET_ALL)

    def add(self,geom,typ,name=None):
        s=self.v.AddSubSurf(geom,getattr(self.v,typ));self.v.SetSubSurfName(s,name or s);return s

    def direct(self,model=None):
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(model or self.model));v.Update()
        v.SetAnalysisInputDefaults('DegenGeom')
        for key,value in [('Set',v.SET_ALL),('UseModeFlag',0),('WriteCSVFlag',0),('WriteMFileFlag',0)]:v.SetIntAnalysisInput('DegenGeom',key,[value])
        rid=v.ExecAnalysis('DegenGeom');native_worker.errors(v);self.assertTrue(rid)
        rows={}
        for parent in v.GetStringResults(rid,'Degen_DegenGeoms'):
            g=v.GetStringResults(parent,'geom_id')[0];surface=v.GetIntResults(parent,'surf_index')[0]
            main=v.GetIntResults(parent,'main_surf_index')[0];copy=v.GetIntResults(parent,'sym_copy_index')[0]
            for child in v.GetStringResults(parent,'subsurfs'):
                name=v.GetStringResults(child,'name')[0]
                rows.setdefault((g,name),[]).append(dict(surface=surface,mainSurface=main,symmetryCopy=copy,
                    points=[[p.x(),p.y(),p.z()] for p in v.GetVec3dResults(child,'x')],
                    u=list(v.GetDoubleResults(child,'u')),w=list(v.GetDoubleResults(child,'w')),
                    typeName=v.GetStringResults(child,'typeName')[0],testType=v.GetIntResults(child,'testType')[0]))
        return rows

    def compare(self,model=None):
        expected=self.direct(model);data,path=self.worker(dict(action='query',operation='region-boundaries'),model)
        self.assertEqual(path.read_bytes(),(model or self.model).read_bytes())
        for region in data['regions']:
            actual=[{k:x[k] for k in ['surface','mainSurface','symmetryCopy','points','u','w','typeName','testType']} for x in region['paths']]
            self.assertEqual(actual,expected.get((region['geom'],region['name']),[]))
        return data,path

    def test_all_seven_native_region_families_match_direct_native_polygons(self):
        v=self.v
        ids=[self.add(self.gid,t) for t in ['SS_LINE','SS_RECTANGLE','SS_ELLIPSE','SS_CONTROL','SS_FINITE_LINE','SS_XSEC_CURVE']]
        g=v.AddGeom('POD');other=v.AddGeom('POD');v.SetParmVal(v.FindParm(other,'X_Rel_Location','XForm'),4);v.SetParmValUpdate(v.FindParm(other,'Z_Rel_Rotation','XForm'),60)
        sid=self.add(g,'SS_INTERSECT');ids.append(sid);v.SetIntersectSubSurfGeomID(sid,other);v.IntersectSubSurf(sid);native_worker.errors(v);self.save()
        data,_=self.compare();self.assertEqual({r['id'] for r in data['regions']},set(ids));self.assertTrue(all(r['paths'] for r in data['regions']))
        self.assertFalse(data['warnings']);self.assertTrue(all(p['valid'] for r in data['regions'] for p in r['paths']))

    def test_transformed_capped_geometry_and_propeller_symmetry_match_native(self):
        v=self.v;prop=v.AddGeom('PROP');sid=self.add(prop,'SS_RECTANGLE')
        main=next(p for p in v.GetSubSurfParmIDs(sid) if v.GetParmName(p)=='MainSurfIndx');v.SetParmValUpdate(main,-1)
        self.add(self.gid,'SS_CONTROL')
        for key,value in [('X_Rel_Location',7.),('Y_Rel_Location',2.),('Z_Rel_Location',-3.),('Z_Rel_Rotation',23.)]:v.SetParmVal(v.FindParm(self.gid,key,'XForm'),value)
        v.SetParmValUpdate(v.FindParm(self.gid,'CapUMinOption','EndCap'),2);self.save()
        data,_=self.compare();wing=next(r for r in data['regions'] if r['geom']==self.gid)
        self.assertEqual({p['symmetryCopy'] for p in wing['paths']},{0,1})
        self.assertGreater(len({p['surface'] for r in data['regions'] if r['geom']==prop for p in r['paths']}),1)

    def test_duplicate_names_keep_native_ids_and_geometry_associations(self):
        v=self.v;a=self.add(self.gid,'SS_RECTANGLE','Repeated name');b=self.add(self.gid,'SS_ELLIPSE','Repeated name');other=v.AddGeom('POD');c=self.add(other,'SS_RECTANGLE','Repeated name');self.save()
        data,path=self.worker(dict(action='query',operation='region-boundaries'))
        self.assertEqual(path.read_bytes(),self.model.read_bytes());self.assertEqual({r['id'] for r in data['regions']},{a,b,c})
        self.assertTrue(all(r['name']=='Repeated name' and r['paths'] for r in data['regions']))
        self.assertNotEqual(next(r for r in data['regions'] if r['id']==a)['paths'][0]['points'],next(r for r in data['regions'] if r['id']==b)['paths'][0]['points'])
        self.assertEqual(next(r for r in data['regions'] if r['id']==c)['geom'],other)
        v.ClearVSPModel();v.ReadVSPFile(str(path));self.assertEqual([v.GetSubSurfName(s) for s in [a,b,c]],['Repeated name']*3)

    def test_region_edits_refresh_boundaries_and_native_saved_file_stays_unchanged_by_query(self):
        v=self.v;sid=self.add(self.gid,'SS_RECTANGLE');self.save();before,_=self.compare()
        pid=v.FindParm(sid,'Center_U','SS_Rectangle');self.assertTrue(pid)
        _,edited=self.worker(dict(action='mutate',operation='parameter',id=pid,value=.7))
        after,_=self.compare(edited)
        self.assertNotEqual(before['regions'][0]['paths'][0]['points'],after['regions'][0]['paths'][0]['points'])
        again,_=self.compare();self.assertEqual(before['regions'][0]['paths'][0]['points'],again['regions'][0]['paths'][0]['points'])

    def test_empty_queries_and_component_filter_validation(self):
        data,path=self.worker(dict(action='query',operation='region-boundaries'))
        self.assertEqual(data['regions'],[]);self.assertEqual(data['warnings'],[]);self.assertEqual(path.read_bytes(),self.model.read_bytes())
        self.add(self.gid,'SS_RECTANGLE');g=self.v.AddGeom('POD');self.add(g,'SS_ELLIPSE');self.save()
        data,path=self.worker(dict(action='query',operation='region-boundaries',geom=g));self.assertEqual({r['geom'] for r in data['regions']},{g})
        with self.assertRaises(ValueError):self.worker(dict(action='query',operation='region-boundaries',geom='missing'))

if __name__=='__main__':unittest.main()
