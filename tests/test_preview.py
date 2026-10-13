"""Read-only native structural drawing adapter and SDK position checks."""
import sys
import unittest
import test_native
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class StructuralPreview(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;i=v.AddFeaStruct(self.gid);self.sid=v.GetFeaStructID(self.gid,i)
        self.parts={}
        for name in ('RIB','SPAR','SLICE','FIX_POINT','DOME','RIB_ARRAY','SLICE_ARRAY','TRIM','POLY_SPAR'):
            self.parts[name]=v.AddFeaPart(self.gid,i,getattr(v,'FEA_'+name))
        for n,x in [('FixedPointType',v.FEA_FIX_PT_GLOBAL_XYZ),('AbsX',3),('AbsY',1.5),('AbsZ',2)]:v.SetParmVal(v.FindParm(self.parts['FIX_POINT'],n,'FeaFixPoint'),x)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)

    def test_native_drawing_contains_every_part_and_exact_fixed_point_without_file_edits(self):
        self.fixture();before=self.model.read_bytes()
        data,path=self.worker(dict(action='query',operation='structural-preview',structure=self.sid))
        self.assertEqual(path.read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)
        self.assertEqual(data['engineOperation'],'FeaStructure::Update / FeaPart::LoadDrawObjs / SubSurface::LoadDrawObjs')
        actual={p['id']:p for p in data['parts']};self.assertTrue(set(self.parts.values()).issubset(actual))
        self.assertEqual([p['type'] for p in data['parts'] if p['isSkin']],[self.v.FEA_SKIN])
        for name in ('RIB','SPAR','SLICE','DOME','RIB_ARRAY','SLICE_ARRAY','POLY_SPAR'):
            self.assertTrue(any(o['kind']=='quads' and len(o['points'])>=4 for o in actual[self.parts[name]]['objects']),name)
        point=actual[self.parts['FIX_POINT']]
        for obj in point['objects']:
            self.assertEqual(obj['kind'],'points');self.assertTrue(all(p==[3,1.5,2] for p in obj['points']))
        self.assertTrue(any('Skin' in w for w in data['warnings']))
        for part in data['parts']:
            for obj in part['objects']:
                if obj['kind']=='quads':self.assertEqual(len(obj['points'])%4,0)
                if obj['kind']=='triangles':self.assertEqual(len(obj['points'])%3,0)
        self.assertEqual(list(path.parent.glob('*.msh')),[])

    def test_native_edit_changes_preview_and_invalid_structure_is_rejected(self):
        self.fixture();a,path=self.worker(dict(action='query',operation='structural-preview',structure=self.sid))
        pid=self.v.FindParm(self.parts['RIB'],'RelCenterLocation','FeaPart')
        if not pid:
            pid=next(p for p in self.v.FindContainerParmIDs(self.parts['RIB']) if self.v.GetParmName(p)=='RelCenterLocation')
        state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=.3),path)
        b,path=self.worker(dict(action='query',operation='structural-preview',structure=self.sid),path)
        def rib(x):return next(p['objects'] for p in x['parts'] if p['id']==self.parts['RIB'])
        self.assertNotEqual(rib(a),rib(b))
        before=path.read_bytes()
        with self.assertRaises(ValueError):self.worker(dict(action='query',operation='structural-preview',structure='UNKNOWN'),path)
        self.assertEqual(path.read_bytes(),before)

    def test_structural_region_drawing_matches_independent_native_polygon_corners(self):
        import xml.etree.ElementTree as ET
        self.fixture();v=self.v;index=v.GetFeaStructIndex(self.sid)
        region_ids=[]
        for name in ('SS_LINE','SS_RECTANGLE','SS_ELLIPSE','SS_CONTROL','SS_LINE_ARRAY','SS_FINITE_LINE'):
            pid=v.AddFeaSubSurf(self.gid,index,getattr(v,name));v.SetFeaSubSurfName(pid,name)
            region_ids.append(pid)
        for name,value in [('X_Rel_Location',2),('Y_Rel_Location',1),('Z_Rel_Rotation',23)]:
            v.SetParmVal(self.gid,name,'XForm',value)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        data,path=self.worker(dict(action='query',operation='structural-preview',structure=self.sid))
        self.assertEqual(path.read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)
        self.assertEqual([r['id'] for r in data['regions']],region_ids)
        for region in data['regions']:
            self.assertTrue(region['isRegion']);self.assertFalse(region['isSkin'])
            self.assertTrue(region['objects'],region['name'])
            self.assertTrue(all(o['kind']=='lines' and len(o['points'])%2==0 for o in region['objects']))
        # Move complete native region definitions into a separate ordinary
        # subsurface model; compare independent native DegenGeom corner output.
        tree=ET.parse(self.model)
        owner=next(n for n in tree.findall('.//FeaStructureInfo') if n.findtext('ParmContainer/ID')==self.sid)
        geom=next(n for n in tree.findall('.//Geom') if n.findtext('ParmContainer/ID')==self.gid)
        target=geom.find('Geom/SubSurfaces')
        for node in owner.findall('FeaSubSurface'):
            owner.remove(node);node.tag='SubSurface';target.append(node)
        independent=self.path/'independent-regions.vsp3';tree.write(independent,encoding='utf-8',xml_declaration=True)
        polygons,_=self.worker(dict(action='query',operation='region-boundaries',geom=self.gid),independent)
        by_id={r['id']:r for r in polygons['regions']}
        for region in data['regions']:
            # Ellipse/control polygons can use different native tessellation;
            # the line and rectangle corner records are exact common samples.
            if region['name'] not in ('SS_LINE','SS_RECTANGLE','SS_FINITE_LINE'):continue
            drawing=[p for o in region['objects'] for p in o['points']]
            expected=[p for path in by_id[region['id']]['paths'] for p in path['points']]
            self.assertTrue(expected,region['name'])
            for p in expected:
                self.assertLessEqual(min(max(abs(a-b) for a,b in zip(p,q)) for q in drawing),1e-10,region['name'])
        self.assertEqual(self.model.read_bytes(),before)
