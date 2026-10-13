"""Exact native structural intersection curves and rejected-edit preservation."""
import sys
import unittest
import xml.etree.ElementTree as ET
import test_native
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class StructuralIntersections(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;v.ClearVSPModel();self.gid=v.AddGeom('POD');self.other=v.AddGeom('POD')
        v.SetParmVal(self.other,'X_Rel_Location','XForm',4);v.SetParmVal(self.other,'Z_Rel_Rotation','XForm',60)
        self.index=v.AddFeaStruct(self.gid);self.sid=v.GetFeaStructID(self.gid,self.index)
        self.region=v.AddFeaSubSurf(self.gid,self.index,v.SS_INTERSECT);v.SetFeaSubSurfName(self.region,'Native join')
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return self.model

    def request(self,**kw):return dict(action='mutate',operation='structural-subsurface-intersect',structure=self.sid,id=self.region,target=self.other,curve=0,**kw)

    def test_structural_curve_matches_independent_native_geometry_intersection(self):
        self.fixture();v=self.v;ordinary=v.AddSubSurf(self.gid,v.SS_INTERSECT);v.SetIntersectSubSurfGeomID(ordinary,self.other);v.Update();v.IntersectSubSurf(ordinary);v.Update()
        direct=self.path/'direct.vsp3';v.WriteVSPFile(str(direct),v.SET_ALL)
        native=next(n for n in ET.parse(direct).findall('.//SubSurface') if n.findtext('ParmContainer/ID')==ordinary)
        state,path=self.worker(self.request());region=next(p for p in state['tools']['structuralSubsurfaces'] if p['id']==self.region)
        self.assertEqual(region['intersectionTarget'],self.other);self.assertEqual(region['type'],v.SS_INTERSECT)
        computed=next(n for n in ET.parse(path).findall('.//FeaSubSurface') if n.findtext('ParmContainer/ID')==self.region)
        def payload(node):
            return (node.tag,{k:v for k,v in node.attrib.items() if k!='ID'},(node.text or '').strip(),[payload(n) for n in node if n.tag not in ('ID','Name')])
        self.assertEqual(payload(computed.find('XSecCurve')),payload(native.find('XSecCurve')))
        for name in ('NCurves','ICurve','Center_U','Center_W'):
            actual=next(p['value'] for p in region['params'] if p['name']==name)
            expected=next(float(n.attrib['Value']) for n in native.iter() if n.tag==name and 'Value' in n.attrib)
            self.assertEqual(actual,expected)
        self.assertGreater(next(p['value'] for p in region['params'] if p['name']=='NCurves'),0)
        # The temporary geometry-region bridge never becomes user geometry.
        self.assertEqual(state['tools']['controls'],[])
        self.assertEqual(computed.findtext('ParmContainer/Name'),'Native join')
        from mesh_io import read_gmsh
        import copy
        independent=ET.parse(self.model);owner=next(n for n in independent.findall('.//FeaStructureInfo') if n.findtext('ParmContainer/ID')==self.sid)
        old=owner.find('FeaSubSurface');slot=list(owner).index(old);owner.remove(old)
        expected=copy.deepcopy(native);expected.tag='FeaSubSurface';expected.find('ParmContainer/ID').text=self.region;expected.find('ParmContainer/Name').text='Native join';owner.insert(slot,expected)
        expected_file=self.path/'independent-structural.vsp3';independent.write(expected_file,encoding='utf-8',xml_declaration=True)
        req=dict(action='analysis',name='FeaMeshAnalysis',structure=self.sid,formats=['GMSH'],inputs=[dict(name=n,values=[x]) for n,x in [('BaseLen',1.),('MinLen',.2),('MaxGap',.03)]])
        _,a=self.worker(req,path);_,b=self.worker(req,expected_file);ma=read_gmsh(a.parent/'structure.msh');mb=read_gmsh(b.parent/'structure.msh')
        self.assertEqual(ma['nodes'],mb['nodes']);self.assertEqual(ma['elements'],mb['elements']);self.assertEqual(ma['groups'],mb['groups'])


    def test_no_intersection_invalid_curve_and_foreign_target_preserve_saved_model(self):
        self.fixture();state,path=self.worker(self.request());before=path.read_bytes()
        for changes in ({'target':self.gid},{'target':'MISSING'},{'curve':True},{'curve':-1},{'curve':100},{'curve':.5}):
            request=self.request();request.update(changes)
            with self.assertRaises(ValueError):self.worker(request,path)
            self.assertEqual(path.read_bytes(),before)
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.SetParmValUpdate(self.other,'X_Rel_Location','XForm',100);far=self.path/'far.vsp3';v.WriteVSPFile(str(far),v.SET_ALL)
        far_before=far.read_bytes()
        with self.assertRaisesRegex(ValueError,'no intersection curves'):self.worker(self.request(),far)
        self.assertEqual(far.read_bytes(),far_before)

    def test_native_owner_properties_constraints_and_target_delete_guard(self):
        self.fixture();state,path=self.worker(dict(action='mutate',operation='boundary-add',structure=self.sid,type='FEA_BC_SUBSURF',name='Join constraint'))
        bc=state['tools']['boundaryConditions'][0]['id'];state,path=self.worker(dict(action='mutate',operation='boundary-target',structure=self.sid,id=bc,target=self.region),path)
        before_ids={p['id']:p['rawGroup']+'/'+p['name'] for p in state['tools']['structuralSubsurfaces'][0]['params'] if p['rawGroup'] in ('SubSurface','FeaSubSurface','SS_Intersect','SS_XsecCurve','ParasiteDragProps')};surfaces={c['id']:c['surfaces'] for c in state['components']};refs=state['tools']['boundaryConditions'][0]['references']
        original_node=next(n for n in ET.parse(path).findall('.//FeaSubSurface') if n.findtext('ParmContainer/ID')==self.region)
        properties={key:original_node.findtext(key) for key in ('FeaPropertyID','CapFeaPropertyID')}
        state,path=self.worker(self.request(),path)
        region=state['tools']['structuralSubsurfaces'][0]
        self.assertFalse({pid:name for pid,name in before_ids.items() if pid not in {p['id'] for p in region['params']}})
        self.assertEqual(state['tools']['boundaryConditions'][0]['references'],refs)
        computed=next(n for n in ET.parse(path).findall('.//FeaSubSurface') if n.findtext('ParmContainer/ID')==self.region)
        self.assertEqual({key:computed.findtext(key) for key in properties},properties)
        self.assertEqual({c['id']:c['surfaces'] for c in state['components']},surfaces)
        with self.assertRaisesRegex(ValueError,'Native join'):self.worker(dict(action='mutate',operation='delete',geom=self.other),path)
        state,_=self.worker(dict(action='mutate',operation='delete',geom=self.gid),path)
        self.assertEqual(state['tools']['structuralSubsurfaces'],[])
