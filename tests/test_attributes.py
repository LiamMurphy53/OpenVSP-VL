"""Native metadata lists, recursive copying and transactional preservation."""
import sys
import unittest
import test_native
import native_attributes
import native_service as service
from vsp_runtime import load


def vectors(points):return [[p.x(),p.y(),p.z()] for p in points]


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativeAttributes(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_imported_vector_list_edit_retains_all_rows_and_native_geometry(self):
        v=self.v;points=[[1.25,-2.,3.],[4.,5.5,6.],[0.,8.,-9.]]
        a=v.AddAttributeVec3d(v.GetChildCollection(self.gid),'Reference stations',[v.vec3d(*p) for p in points]);v.SetAttributeDoc(a,'Imported native vector list')
        expected=v.CompPnt01(self.gid,0,.36,.47);v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,path=self.worker(dict(action='state'));attr=next(a for a in state['tools']['attributes'] if a['name']=='Reference stations')
        self.assertEqual(attr['values'],points)
        points[1]=[40.,55.,60.];points.append([10.,11.,12.])
        state,path=self.worker(dict(action='mutate',operation='attribute-save',id=a,name='Edited stations',kind='Vector',value=points,doc='All rows retained'),path)
        edited=next(x for x in state['tools']['attributes'] if x['id']==a);self.assertEqual(edited['values'],points);self.assertEqual(edited['doc'],'All rows retained')
        v.ClearVSPModel();v.ReadVSPFile(str(path));self.assertEqual(vectors(v.GetAttributeVec3dVal(a)),points)
        actual=v.CompPnt01(self.gid,0,.36,.47);self.assertEqual(vectors([actual]),vectors([expected]))
        # Existing single-vector API clients retain their original shorthand.
        state,path=self.worker(dict(action='mutate',operation='attribute-save',id=a,name='One station',kind='Vector',value=[1.,2.,3.]),path)
        self.assertEqual(next(x for x in state['tools']['attributes'] if x['id']==a)['values'],[[1.,2.,3.]])

    def test_group_copy_matches_direct_native_copy_and_keeps_external_parameter_reference(self):
        v=self.v;source=v.GetChildCollection(self.gid);group=v.AddAttributeGroup(source,'Design record');v.SetAttributeDoc(group,'Nested assumptions')
        nested=v.AddAttributeGroup(v.GetChildCollection(group),'Measurements');nc=v.GetChildCollection(nested)
        v.AddAttributeVec3d(nc,'Stations',[v.vec3d(1,2,3),v.vec3d(4,5,6)])
        v.AddAttributeDoubleMatrix(nc,'Weights',[[.1,.2],[.3,.4]])
        parm=v.FindParm(self.gid,'TotalSpan','WingGeom');v.AddAttributeParm(nc,'Span reference',parm)
        v.AddAttributeString(nc,'Note','Line one\nUnicode λ & <text>')
        target=v.GetChildCollection(v.GetVehicleID());v.WriteVSPFile(str(self.model),v.SET_ALL)
        self.assertEqual(v.CopyAttribute(group),0);expected_id=list(v.PasteAttribute(target))[0]
        def record(a):
            kind=v.GetAttributeType(a);base=dict(name=v.GetAttributeName(a),doc=v.GetAttributeDoc(a),kind=kind)
            if kind==v.ATTR_COLLECTION_DATA:base['children']=sorted([record(c) for c in v.FindAttributesInCollection(v.GetChildCollection(a))],key=lambda r:r['name'])
            elif kind==v.VEC3D_DATA:base['values']=vectors(v.GetAttributeVec3dVal(a))
            elif kind==v.DOUBLE_MATRIX_DATA:base['values']=[list(row) for row in v.GetAttributeDoubleMatrixVal(a)]
            elif kind==v.PARM_REFERENCE_DATA:base['values']=list(v.GetAttributeParmID(a))
            elif kind==v.STRING_DATA:base['values']=list(v.GetAttributeStringVal(a))
            return base
        expected=record(expected_id)
        state,path=self.worker(dict(action='mutate',operation='attribute-copy',id=group,collection=target))
        copies=[a for a in state['tools']['attributes'] if a['name']=='Design record' and a['collection']==target];self.assertEqual(len(copies),1);copy=copies[0]['id'];self.assertNotEqual(copy,group)
        v.ClearVSPModel();v.ReadVSPFile(str(path));self.assertEqual(record(copy),expected);self.assertEqual(record(group),expected)
        refs=[a for a in state['tools']['attributes'] if a['name']=='Span reference'];self.assertEqual(len(refs),2);self.assertTrue(all(a['values']==[parm] for a in refs))
        # Removing the original group leaves the independent native copy intact.
        state,path=self.worker(dict(action='mutate',operation='attribute-delete',id=group),path)
        v.ClearVSPModel();v.ReadVSPFile(str(path));self.assertEqual(record(copy),expected);self.assertNotIn(group,v.FindAllAttributes())

    def test_matrix_shape_and_all_cells_persist_with_native_integer_and_double_types(self):
        path=self.model
        for kind,getter,values in [('Integer matrix','GetAttributeIntMatrixVal',[[1,-2,3],[4,5,6],[7,8,9]]),('Number matrix','GetAttributeDoubleMatrixVal',[[.1,-2.25],[3.5,4.75]])]:
            state,path=self.worker(dict(action='mutate',operation='attribute-save',owner=self.gid,name=kind,kind=kind,value=values),path)
            a=next(a for a in state['tools']['attributes'] if a['name']==kind);self.assertEqual(a['values'],values)
            values=values[1:]+[[x+10 for x in values[0]]]
            state,path=self.worker(dict(action='mutate',operation='attribute-save',id=a['id'],name=kind,kind=kind,value=values),path)
            self.v.ClearVSPModel();self.v.ReadVSPFile(str(path));self.assertEqual([list(row) for row in getattr(self.v,getter)(a['id'])],values)

    def test_empty_native_owner_collections_include_sections_settings_structures_and_parameters(self):
        v=self.v;idx=v.AddFeaStruct(self.gid);structure=v.GetFeaStructID(self.gid,idx)
        part=v.AddFeaPart(self.gid,idx,v.FEA_RIB);mode=v.CreateAndAddMode('Cruise',v.SET_ALL,v.SET_NONE)
        preset=v.AddVarPresetGroup('Configuration');setting=v.AddVarPresetSetting(preset,'Baseline')
        section=v.GetXSec(v.GetXSecSurf(self.gid,0),1);parameter=v.FindParm(part,'RelCenterLocation','FeaPart')
        self.assertTrue(v.ValidParm(parameter))
        owners=[section,structure,part,parameter,mode,v.FindContainer('CFDMeshSettings',0)]
        v.WriteVSPFile(str(self.model),v.SET_ALL);state,path=self.worker(dict(action='state'))
        collections={c['object']:c for c in state['tools']['attributeCollections']}
        self.assertTrue(set(owners)<=set(collections),set(owners)-set(collections))
        # 3.52.2 exposes preset objects, but no native attribute collection for them.
        self.assertEqual(v.GetChildCollection(preset),'ID ERROR');self.assertEqual(v.GetChildCollection(setting),'ID ERROR')
        self.assertNotIn(preset,collections);self.assertNotIn(setting,collections)
        self.assertNotIn('ID ERROR',[c['id'] for c in collections.values()]);self.assertIn('RelCenterLocation',collections[parameter]['name'])
        for i,owner in enumerate(owners):
            state,path=self.worker(dict(action='mutate',operation='attribute-save',owner=owner,name=f'Owner note {i}',kind='Text',value=f'Native owner {i}'),path)
        v.ClearVSPModel();v.ReadVSPFile(str(path))
        for i,owner in enumerate(owners):
            a=next(a for a in v.FindAttributesInCollection(v.GetChildCollection(owner)) if v.GetAttributeName(a)==f'Owner note {i}')
            self.assertEqual(list(v.GetAttributeStringVal(a)),[f'Native owner {i}'])

    def test_empty_native_vector_lists_and_matrices_remain_empty(self):
        v=self.v;path=self.model
        for kind,getter in [('Vector','GetAttributeVec3dVal'),('Integer matrix','GetAttributeIntMatrixVal'),('Number matrix','GetAttributeDoubleMatrixVal')]:
            state,path=self.worker(dict(action='mutate',operation='attribute-save',owner=self.gid,name=f'Empty {kind}',kind=kind,value=[]),path)
            a=next(a for a in state['tools']['attributes'] if a['name']==f'Empty {kind}');self.assertEqual(a['values'],[])
            v.ClearVSPModel();v.ReadVSPFile(str(path));self.assertEqual(list(getattr(v,getter)(a['id'])),[])
            state,path=self.worker(dict(action='mutate',operation='attribute-save',id=a['id'],name=a['name'],kind=kind,value=[]),path)
            self.assertEqual(next(x for x in state['tools']['attributes'] if x['id']==a['id'])['values'],[])

    def test_invalid_lists_destinations_and_managed_group_contents_are_rejected(self):
        v=self.v;g=v.AddAttributeGroup(v.GetChildCollection(self.gid),'Outer');n=v.AddAttributeGroup(v.GetChildCollection(g),'Inner')
        managed=v.AddAttributeString(v.GetChildCollection(n),'Studio.FitReport','Managed');v.WriteVSPFile(str(self.model),v.SET_ALL)
        for operation in ['attribute-copy','attribute-delete']:
            with self.assertRaisesRegex(ValueError,'managed metadata'):self.worker(dict(action='mutate',operation=operation,id=g,owner=self.gid))
            with self.assertRaisesRegex(ValueError,'Choose an attribute'):self.worker(dict(action='mutate',operation=operation,owner=self.gid))
        v.DeleteAttribute(managed);v.WriteVSPFile(str(self.model),v.SET_ALL)
        for owner in [g,n,'missing-owner']:
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='attribute-copy',id=g,owner=owner))
        for kind,values in [('Vector',None),('Vector',[[1,2,3],[4,5]]),('Vector',[[1,2,float('inf')]]),('Vector',[True,2,3]),('Integer matrix',[[1,2.5]]),('Number matrix',[[1,2],[3]]),('Integer',1.5)]:
            with self.subTest(kind=kind,values=values),self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='attribute-save',owner=self.gid,name='Invalid',kind=kind,value=values))

    def test_list_edit_copy_undo_redo_and_failed_transaction_preserve_the_model(self):
        old=(service.WORK,service.MODEL,service.HISTORY,service.FUTURE,service.REVISION)
        service.WORK=self.path;service.MODEL=self.model;service.HISTORY=[];service.FUTURE=[];service.REVISION='attribute-verification'
        try:
            def mutate(**request):return service.mutation(dict(revision=service.REVISION,**request))
            state=mutate(operation='attribute-save',owner=self.gid,name='Stations',kind='Vector',value=[[1,2,3],[4,5,6]])
            a=next(a for a in state['tools']['attributes'] if a['name']=='Stations');before=self.model.read_bytes();history=len(service.HISTORY)
            with self.assertRaises(ValueError):mutate(operation='attribute-save',id=a['id'],name='Stations',kind='Vector',value=[[1,2]])
            self.assertEqual(self.model.read_bytes(),before);self.assertEqual(len(service.HISTORY),history)
            values=[[10,20,30],[40,50,60],[70,80,90]];state=mutate(operation='attribute-save',id=a['id'],name='Stations',kind='Vector',value=values)
            self.assertEqual(next(x for x in state['tools']['attributes'] if x['id']==a['id'])['values'],values)
            undo=service.undo(revision=service.REVISION);self.assertEqual(next(x for x in undo['tools']['attributes'] if x['id']==a['id'])['values'],[[1,2,3],[4,5,6]])
            redo=service.undo(redo=True,revision=service.REVISION);self.assertEqual(next(x for x in redo['tools']['attributes'] if x['id']==a['id'])['values'],values)
            owner=next(c['object'] for c in redo['tools']['attributeCollections'] if c['type']=='Vehicle');state=mutate(operation='attribute-copy',id=a['id'],owner=owner)
            self.assertEqual(len([x for x in service.state()['tools']['attributes'] if x['name']=='Stations']),2)
            state=service.undo(revision=service.REVISION);self.assertEqual(len([x for x in state['tools']['attributes'] if x['name']=='Stations']),1)
            state=service.undo(redo=True,revision=service.REVISION);self.assertEqual([x['values'] for x in state['tools']['attributes'] if x['name']=='Stations'],[values,values])
        finally:service.WORK,service.MODEL,service.HISTORY,service.FUTURE,service.REVISION=old


if __name__=='__main__':unittest.main()
