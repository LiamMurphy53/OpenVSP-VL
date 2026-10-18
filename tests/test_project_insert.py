"""Geometry-only project insertion retains native identities and Studio meshes."""
import base64
import json
import sys
import unittest
import xml.etree.ElementTree as ET
import native_ngon
import native_project_insert
import test_native


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativeProjectInsert(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    @staticmethod
    def payloads(path,tag):
        return {g.findtext('ParmContainer/ID'):json.loads(g.findtext(tag)) for g in ET.parse(path).findall('./Vehicle/Geom') if g.find(tag) is not None}

    def test_colliding_projects_meshes_regions_parent_and_cold_recovery(self):
        v=self.v;wing=self.gid;region=v.AddSubSurf(wing,v.SS_RECTANGLE,0);v.Update()
        collection=v.GetChildCollection(wing)
        v.AddAttributeString(collection,'Imported note','Keep Unicode λ and user text unchanged')
        v.AddAttributeParm(collection,'Imported span reference',v.FindParm(wing,'TotalSpan','WingGeom'))
        mesh=v.ComputeCompGeom(v.SET_ALL,False,0);native_ngon.capture_mesh(v,mesh)
        polygon=native_ngon.convert(v,mesh,levels=1);v.SetParmValUpdate(polygon,'ActiveMesh','RefMesh',1)
        v.SetGeomParent(mesh,wing);v.SetGeomParent(polygon,wing);v.Update()
        source=self.path/'insert.vsp3';native_ngon.write(v,source);source_bytes=source.read_bytes()
        parent=v.AddGeom('BLANK');v.SetGeomName(parent,'Insertion parent');v.Update();native_ngon.write(v,self.model);before=self.model.read_bytes();original=set(v.FindGeoms())
        polygons=self.payloads(self.model,'StudioPolygonSnapshot');triangles=self.payloads(self.model,'StudioTriangleMetadata')
        state,path=self.worker(dict(action='mutate',operation='geometry-import',format='VSP3',parent=parent,content=base64.b64encode(source_bytes).decode()))
        added=[c for c in state['components'] if c['id'] not in original];self.assertEqual(len(added),3)
        by_type={c['type'].upper():c for c in added};new_wing=by_type['WING']['id'];new_mesh=by_type['MESH']['id'];new_polygon=by_type['NGONMESH']['id']
        self.assertEqual(by_type['WING']['parent'],parent)
        self.assertEqual(by_type['MESH']['parent'],new_wing);self.assertEqual(by_type['NGONMESH']['parent'],new_wing)
        original_wing=next(c for c in state['components'] if c['id']==wing)
        self.assertEqual(by_type['WING']['surfaces'],original_wing['surfaces'])
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();native_ngon.restore_file(v,path)
        new_region=list(v.GetSubSurfIDVec(new_wing))[0];self.assertNotEqual(region,new_region)
        mapping={wing:new_wing,mesh:new_mesh,polygon:new_polygon,region:new_region}
        pg=self.payloads(path,'StudioPolygonSnapshot');tm=self.payloads(path,'StudioTriangleMetadata')
        self.assertEqual(pg[polygon],polygons[polygon]);self.assertEqual(tm[mesh],triangles[mesh])
        self.assertEqual(pg[new_polygon],native_project_insert.remap_mesh(polygons[polygon],mapping))
        self.assertEqual(tm[new_mesh],native_project_insert.remap_mesh(triangles[mesh],mapping,True))
        # Check actual reference targets, independently of the remapping helper.
        self.assertTrue(any(new_wing in value for _,value in pg[new_polygon]['tagIDs']))
        self.assertFalse(any(wing in value for _,value in pg[new_polygon]['tagIDs']))
        self.assertEqual(tm[new_mesh]['meshes'][0]['origin'],new_wing)
        self.assertFalse(any(v.GetAttributeName(a).startswith('Studio.InsertMapping.') for a in v.FindAllAttributes()))
        self.assertNotIn(b'Studio.InsertMapping.',path.read_bytes())
        attributes={v.GetAttributeName(a):a for a in v.FindAttributesInCollection(v.GetChildCollection(new_wing))}
        self.assertEqual(list(v.GetAttributeStringVal(attributes['Imported note'])),['Keep Unicode λ and user text unchanged'])
        self.assertEqual(list(v.GetAttributeParmID(attributes['Imported span reference'])),[v.FindParm(new_wing,'TotalSpan','WingGeom')])
        reopened,_=self.worker(dict(action='state'),path)
        self.assertEqual([c['id'] for c in reopened['components']],[c['id'] for c in state['components']])
        repeated,again=self.worker(dict(action='mutate',operation='geometry-import',format='VSP3',parent=parent,content=base64.b64encode(source_bytes).decode()),path)
        self.assertEqual(len(repeated['components']),len(state['components'])+3)
        for gid,data in pg.items():self.assertEqual(self.payloads(again,'StudioPolygonSnapshot')[gid],data)
        for gid,data in tm.items():self.assertEqual(self.payloads(again,'StudioTriangleMetadata')[gid],data)
        self.assertNotIn(b'Studio.InsertMapping.',again.read_bytes())
        self.assertEqual(self.model.read_bytes(),before);self.assertEqual(source.read_bytes(),source_bytes)

    def test_malformed_or_corrupt_project_rejects_without_changes(self):
        before=self.model.read_bytes()
        for raw in [b'not XML',b'<Other/>',b'<Vsp_Geometry><Vehicle/></Vsp_Geometry>']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='geometry-import',format='VSP3',content=base64.b64encode(raw).decode()))
            self.assertEqual(self.model.read_bytes(),before)
        v=self.v;mesh=v.ComputeCompGeom(v.SET_ALL,False,0);native_ngon.capture_mesh(v,mesh)
        polygon=native_ngon.convert(v,mesh);source=self.path/'corrupt.vsp3';native_ngon.write(v,source)
        tree=ET.parse(source);tree.find('./Vehicle/Geom/StudioPolygonSnapshot').set('sha256','0'*64)
        with self.assertRaisesRegex(ValueError,'corrupt'):self.worker(dict(action='mutate',operation='geometry-import',format='VSP3',content=base64.b64encode(ET.tostring(tree.getroot())).decode()))
        self.assertEqual(self.model.read_bytes(),before)
