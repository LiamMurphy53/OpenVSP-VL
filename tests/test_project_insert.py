"""Geometry-only project insertion retains native identities and Studio meshes."""
import base64
import shutil
import json
import sys
import unittest
import xml.etree.ElementTree as ET
import native_ngon
import native_project_insert
import test_native
import test_custom_assets


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

    def test_packaged_custom_profile_insert_is_independently_editable_after_relocation(self):
        script=test_custom_assets.SCRIPT.replace('void Init(){','void Init(){string p=AddParm(PARM_DOUBLE_TYPE,"Length","Design");SetParmVal(p,8);')
        script=script.replace('vec3d(8,0,0)','vec3d(GetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design")),0,0)')
        raw=test_custom_assets.CustomAssets.package(self,script)
        initial,source=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_PACKAGE',name='Packaged body',content=base64.b64encode(raw).decode()))
        original=next(c for c in initial['components'] if c['name']=='Packaged body');source_bytes=source.read_bytes();before=set(c['id'] for c in initial['components'])
        for folder in ['component-package','.studio-custom-assets']:shutil.rmtree(source.parent/folder,ignore_errors=True)
        state,path=self.worker(dict(action='mutate',operation='geometry-import',format='VSP3',content=base64.b64encode(source_bytes).decode()),source)
        clone=next(c for c in state['components'] if c['id'] not in before and c['name']=='Packaged body')
        self.assertEqual(clone['surfaces'],original['surfaces'])
        pid=next(p['id'] for p in clone['params'] if p['name']=='Length' and p['rawGroup']=='Design')
        edited,output=self.worker(dict(action='mutate',operation='parameter',id=pid,value=12.),path)
        expected=next(c for c in edited['components'] if c['id']==clone['id'])['surfaces']
        self.assertNotEqual(expected,clone['surfaces'])
        self.assertEqual(next(c for c in edited['components'] if c['id']==original['id'])['surfaces'],original['surfaces'])
        for folder in [path.parent,output.parent]:shutil.rmtree(folder/'.studio-custom-assets',ignore_errors=True)
        reopened,_=self.worker(dict(action='state'),output)
        self.assertEqual(next(c for c in reopened['components'] if c['id']==clone['id'])['surfaces'],expected)
        # Independent original compiler and literal file reader, without the
        # Studio insertion or companion-path wrappers, provide the math oracle.
        from native_custom_scripts import import_script
        reference=self.path/'reference.vsppart';reference.write_text(script);(self.path/'profile.dat').write_text(test_custom_assets.PROFILE)
        v=self.v;v.ClearVSPModel();gid=import_script(v,reference,'OriginalInsertProfileReference');v.SetParmValUpdate(gid,'Length','Design',12.);v.Update()
        actual=[]
        for i in range(v.GetTotalNumSurfs(gid)):
            u,w=v.GetUWTess01(gid,i%v.GetNumMainSurfs(gid))
            points=[[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(gid,i,[a for a in u for _ in w],[b for _ in u for b in w])]
            actual.append(dict(index=i,rows=len(u),cols=len(w),points=points))
        self.assertEqual(actual,expected);self.assertEqual(source.read_bytes(),source_bytes)
        self.assertNotIn(b'Studio.InsertMapping.',output.read_bytes())

    def test_structural_and_link_references_follow_inserted_objects(self):
        v=self.v
        state,path=self.worker(dict(action='mutate',operation='structure-add',geom=self.gid,name='Inserted wing structure'))
        sid=state['tools']['structures'][0]['id'];parts={}
        for typ,label in [('FEA_RIB','Insert rib'),('FEA_SPAR','Insert spar'),('FEA_TRIM','Insert trim')]:
            state,path=self.worker(dict(action='mutate',operation='part-add',structure=sid,type=typ,name=label),path)
            parts[typ]=next(p['id'] for p in state['tools']['structures'][0]['parts'] if p['name']==label)
        rib,spar,trim=[parts[t] for t in ['FEA_RIB','FEA_SPAR','FEA_TRIM']]
        state,path=self.worker(dict(action='mutate',operation='part-perpendicular-spar',structure=sid,id=rib,spar=spar),path)
        state,path=self.worker(dict(action='mutate',operation='part-trim-add',structure=sid,id=trim,target=spar),path)
        source=v.FindParm(self.gid,'TotalSpan','WingGeom');target=v.FindParm(self.gid,'X_Rel_Location','XForm')
        state,path=self.worker(dict(action='mutate',operation='link-add',source=source,target=target,scale=.5,offset=0),path)
        raw=path.read_bytes();before=raw
        inserted,output=self.worker(dict(action='mutate',operation='geometry-import',format='VSP3',content=base64.b64encode(raw).decode()),path)
        clone=next(c for c in inserted['components'] if c['id']!=self.gid)
        structure=next(s for s in inserted['tools']['structures'] if s['geom']==clone['id'])
        new_parts={p['name']:p for p in structure['parts']}
        self.assertEqual(new_parts['Insert rib']['perpendicularSpar'],new_parts['Insert spar']['id'])
        self.assertEqual(new_parts['Insert trim']['trimTargets'],[new_parts['Insert spar']['id']])
        self.assertNotEqual(structure['id'],sid)
        props={p['id'] for p in inserted['tools']['properties']}
        for part in structure['parts']:
            for prop in part['propertyReferences'].values():
                if prop:self.assertIn(prop,props)
        fields={p['name']:p for p in clone['params'] if p['rawGroup'] in ('WingGeom','XForm')}
        link=next(l for l in inserted['tools']['links'] if l['source']==fields['TotalSpan']['id'])
        self.assertEqual(link['target'],fields['X_Rel_Location']['id']);self.assertEqual(len(inserted['tools']['links']),2)
        edited,edited_path=self.worker(dict(action='mutate',operation='parameter',id=fields['TotalSpan']['id'],value=22.),output)
        changed=next(c for c in edited['components'] if c['id']==clone['id']);original=next(c for c in edited['components'] if c['id']==self.gid)
        self.assertEqual(next(p['value'] for p in changed['params'] if p['id']==fields['X_Rel_Location']['id']),11.)
        self.assertEqual(next(p['value'] for p in original['params'] if p['id']==target),9.)
        reopened,_=self.worker(dict(action='state'),edited_path)
        self.assertEqual(next(s for s in reopened['tools']['structures'] if s['id']==structure['id']),next(s for s in edited['tools']['structures'] if s['id']==structure['id']))
        self.assertEqual(path.read_bytes(),before)
