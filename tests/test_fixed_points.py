"""Fixed-point references, placements and meshes use the official native engine."""
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET
import test_native
import test_session
import native_service as service
from vsp_runtime import load
from mesh_io import read_gmsh

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class FixedPoints(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_session.NativeSession.setUp
    tearDown=test_session.NativeSession.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;i=v.AddFeaStruct(self.gid);self.sid=v.GetFeaStructID(self.gid,i)
        self.skin=v.GetFeaPartIDVec(self.sid)[0];self.spar=v.AddFeaPart(self.gid,i,v.FEA_SPAR);v.SetFeaPartName(self.spar,'Attachment spar')
        self.point=v.AddFeaPart(self.gid,i,v.FEA_FIX_POINT);v.SetFeaPartName(self.point,'Reference point')
        self.other=v.AddGeom('POD');v.SetGeomName(self.other,'Reference body');v.SetParmVal(self.other,'X_Rel_Location','XForm',12);v.SetParmVal(self.other,'Z_Rel_Rotation','XForm',35)
        for n,x in [('CGx',.75),('CGy',.2),('CGz',-.1)]:v.SetParmVal(self.other,n,'Mass_Props',x)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return self.model

    def request(self,mode,parent=None,reference=None):
        return dict(action='mutate',operation='part-fixed-point',structure=self.sid,id=self.point,mode=mode,parent=parent or self.spar,reference=reference or self.other,values=dict(PosU=.35,PosW=.4,AbsX=3.,AbsY=1.5,AbsZ=2.,DeltaX=.2,DeltaY=.1,DeltaZ=.3,DeltaU=.1,DeltaV=.2,DeltaN=.3,FixPointMassFlag=1,FixPointMass=2.,MassUnit=self.v.MASS_UNIT_KG))

    def direct(self,request):
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        for n,x in request['values'].items():v.SetParmVal(v.FindParm(self.point,n,'FeaFixPoint'),x)
        v.SetParmVal(v.FindParm(self.point,'FixedPointType','FeaFixPoint'),request['mode']);v.Update()
        path=self.path/'independent-native.vsp3';v.WriteVSPFile(str(path),v.SET_ALL)
        tree=ET.parse(path);node=next(n for n in tree.findall('.//FeaPartInfo') if n.findtext('ParmContainer/ID')==self.point).find('ParmContainer')
        # These are the exact keys in official FeaFixPoint::EncodeXml/DecodeXml;
        # the 3.52.2 Python API has no parent-part or reference-geometry setter.
        mode=request['mode']
        if mode in (v.FEA_FIX_PT_ON_BODY,v.FEA_FIX_PT_DELTA_XYZ,v.FEA_FIX_PT_DELTA_UVN):node.find('ParentFeaPartID').text=request['parent']
        if mode in (v.FEA_FIX_PT_GEOM_ORIGIN,v.FEA_FIX_PT_GEOM_CG):node.find('OtherGeomID').text=request['reference']
        tree.write(path,encoding='utf-8',xml_declaration=True)
        return path

    def test_all_six_placements_reopen_with_native_references_and_parameter_ids(self):
        self.fixture();source=self.model.read_bytes();v=self.v;ids=set(v.FindContainerParmIDs(self.point))
        for mode in range(v.FEA_NUM_FIX_PT_TYPES):
            with self.subTest(mode=mode):
                request=self.request(mode);state,path=self.worker(request)
                part=next(p for p in state['tools']['structures'][0]['parts'] if p['id']==self.point)
                self.assertEqual(set(p['id'] for p in part['params']),ids)
                for n,x in request['values'].items():self.assertEqual(next(p['value'] for p in part['params'] if p['name']==n),x)
                self.assertEqual(next(p['value'] for p in part['params'] if p['name']=='FixedPointType'),mode)
                expected=self.direct(request);native,_=self.worker(dict(action='state'),expected)
                direct=next(p for p in native['tools']['structures'][0]['parts'] if p['id']==self.point)
                self.assertEqual(part['fixedPoint'],direct['fixedPoint'])
                reopened,_=self.worker(dict(action='state'),path);self.assertEqual(next(p for p in reopened['tools']['structures'][0]['parts'] if p['id']==self.point),part)
        self.assertEqual(self.model.read_bytes(),source)

    def test_all_six_native_meshes_match_independent_engine_configuration(self):
        self.fixture();v=self.v
        for mode in range(v.FEA_NUM_FIX_PT_TYPES):
            with self.subTest(mode=mode):
                request=self.request(mode,parent=self.skin if mode==v.FEA_FIX_PT_ON_BODY else self.spar)
                _,path=self.worker(request);direct=self.direct(request)
                mesh_request=dict(action='analysis',name='FeaMeshAnalysis',structure=self.sid,formats=['GMSH','CALCULIX','MASS'],inputs=[dict(name=n,values=[x]) for n,x in [('BaseLen',1.),('MinLen',.2),('MaxGap',.03)]])
                before=path.read_bytes();_,a=self.worker(mesh_request,path);_,b=self.worker(mesh_request,direct)
                ma=read_gmsh(a.parent/'structure.msh',a.parent/'structure.bdf');mb=read_gmsh(b.parent/'structure.msh',b.parent/'structure.bdf')
                self.assertEqual(len(ma['nodes']),len(mb['nodes']))
                # Native driver updates can move the last printed Gmsh decimal
                # across a rounding boundary on an independent file round-trip.
                for x,y in zip(ma['nodes'],mb['nodes']):
                    for a_value,b_value in zip(x,y):self.assertLessEqual(abs(a_value-b_value),1.000001e-6)
                self.assertEqual(ma['elements'],mb['elements']);self.assertEqual(ma['groups'],mb['groups']);self.assertEqual(len(ma['nativePointMasses']),len(mb['nativePointMasses']))
                self.assertEqual((a.parent/'structure.txt').read_text(),(b.parent/'structure.txt').read_text())
                self.assertEqual(path.read_bytes(),before)
                if mode==v.FEA_FIX_PT_GLOBAL_XYZ:self.assertIn([3.,1.5,2.],ma['nodes'])

    def test_invalid_references_modes_values_and_parent_deletion_preserve_aircraft(self):
        self.fixture();v=self.v
        other_index=v.AddFeaStruct(self.other);foreign=v.GetFeaPartIDVec(v.GetFeaStructID(self.other,other_index))[0]
        cloud=v.CreatePtCloudGeomFromPts([v.vec3d(1,2,3)],'Excluded cloud');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        bad=[dict(mode=True),dict(mode=99),dict(parent=self.point),dict(parent=foreign),dict(parent='missing'),dict(mode=v.FEA_FIX_PT_GEOM_ORIGIN,reference=cloud),dict(mode=v.FEA_FIX_PT_GEOM_CG,reference='missing'),dict(values={'PosU':1.1}),dict(values={'FixPointMassFlag':.5}),dict(values={'MassUnit':1.2}),dict(values={'DeltaX':float('inf')}),dict(values={'Unexpected':1}),dict(id=self.spar)]
        service.save_session();before=self.model.read_bytes();revision=service.REVISION
        for changes in bad:
            request=self.request(v.FEA_FIX_PT_ON_BODY);request.update(changes);request.pop('action');request['revision']=revision
            with self.subTest(changes=changes),self.assertRaises(ValueError):service.mutation(request)
            self.assertEqual(self.model.read_bytes(),before);self.assertEqual(service.REVISION,revision);self.assertFalse(service.HISTORY)
        req=self.request(v.FEA_FIX_PT_DELTA_XYZ);req.pop('action');req['revision']=service.REVISION;service.mutation(req);saved=self.model.read_bytes();revision=service.REVISION
        with self.assertRaisesRegex(ValueError,'another parent part'):service.mutation(dict(operation='part-delete',structure=self.sid,id=self.spar,revision=revision))
        self.assertEqual(self.model.read_bytes(),saved);self.assertEqual(service.REVISION,revision)
        req=self.request(v.FEA_FIX_PT_GEOM_ORIGIN);req.pop('action');req['revision']=service.REVISION;service.mutation(req);saved=self.model.read_bytes();revision=service.REVISION
        with self.assertRaisesRegex(ValueError,'another reference component'):service.mutation(dict(operation='delete',geom=self.other,revision=revision))
        self.assertEqual(self.model.read_bytes(),saved);self.assertEqual(service.REVISION,revision)

    def test_native_point_mass_companion_does_not_accept_arbitrary_truncation(self):
        self.fixture();_,path=self.worker(self.request(self.v.FEA_FIX_PT_GLOBAL_XYZ))
        _,out=self.worker(dict(action='analysis',name='FeaMeshAnalysis',structure=self.sid,formats=['GMSH']),path)
        msh=out.parent/'structure.msh';bdf=out.parent/'structure.bdf';mesh=read_gmsh(msh,bdf)
        self.assertEqual(len(mesh['nativePointMasses']),1);self.assertIn('CONM2',bdf.read_text());self.assertTrue((out.parent/'structure.dat').exists())
        self.assertEqual(len(mesh['elements']),mesh['totalElements']);self.assertTrue(mesh['warnings'])
        with self.assertRaisesRegex(ValueError,'incomplete'):read_gmsh(msh)
        cut=self.path/'truncated.msh';cut.write_text('\n'.join(msh.read_text().splitlines()[:-1])+'\n')
        with self.assertRaisesRegex(ValueError,'incomplete'):read_gmsh(cut,bdf)
        bad=self.path/'missing-node.bdf';bad.write_text('CONM2   ,1,999999999, ,2.0\n')
        with self.assertRaisesRegex(ValueError,'missing mesh node'):read_gmsh(msh,bad)

    def test_assembly_point_masses_retain_native_bulk_deck_and_preview(self):
        self.fixture();_,path=self.worker(self.request(self.v.FEA_FIX_PT_GLOBAL_XYZ))
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();i=v.AddFeaStruct(self.other);sid2=v.GetFeaStructID(self.other,i)
        p=v.AddFeaPart(self.other,i,v.FEA_FIX_POINT)
        for n,x in [('FixedPointType',v.FEA_FIX_PT_GLOBAL_XYZ),('AbsX',15.),('AbsY',2.),('AbsZ',3.),('FixPointMassFlag',1),('FixPointMass',3.)]:v.SetParmVal(v.FindParm(p,n,'FeaFixPoint'),x)
        aid=v.AddFeaAssembly();v.AddFeaAssemblyStructure(aid,self.sid);v.AddFeaAssemblyStructure(aid,sid2);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        result,out=self.worker(dict(action='analysis',name='FeaAssemblyMesh',structure=aid,formats=['GMSH'],inputs=[dict(name=n,values=[x]) for n,x in [('BaseLen',1.),('MinLen',.2),('MaxGap',.03)]]))
        self.assertIn('NASTRAN',result['formats']);m=read_gmsh(out.parent/'assembly.msh',out.parent/'assembly.bdf')
        self.assertEqual(len(m['nativePointMasses']),2);self.assertIn([3.,1.5,2.],m['nodes']);self.assertIn([15.,2.,3.],m['nodes']);self.assertEqual(len(m['elements']),m['totalElements'])

    def test_atomic_placement_undo_redo_and_cold_history_restore(self):
        self.fixture();service.save_session();original=self.model.read_bytes()
        req=self.request(self.v.FEA_FIX_PT_GEOM_CG);req.pop('action');req['revision']=service.REVISION;state=service.mutation(req)
        placed=self.model.read_bytes();point=next(p for p in state['tools']['structures'][0]['parts'] if p['id']==self.point)
        self.assertEqual(point['fixedPoint']['OtherGeomID'],self.other)
        service.undo(revision=service.REVISION);self.assertEqual(self.model.read_bytes(),original)
        service.HISTORY=[];service.FUTURE=[];self.assertTrue(service.restore_session())
        service.undo(redo=True,revision=service.REVISION);self.assertEqual(self.model.read_bytes(),placed)
        state=service.state();self.assertEqual(next(p for p in state['tools']['structures'][0]['parts'] if p['id']==self.point)['fixedPoint']['OtherGeomID'],self.other)

if __name__=='__main__':unittest.main()
