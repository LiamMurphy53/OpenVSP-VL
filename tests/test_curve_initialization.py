"""Native editable-profile initialization and saved geometry equivalence."""
import sys
import unittest
import test_native


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class CurveInitialization(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_three_presets_match_direct_native_geometry_on_four_families(self):
        v=self.v
        for kind in ('WING','FUSELAGE','STACK','PROP'):
            for shape in ('EDIT_XSEC_CIRCLE','EDIT_XSEC_ELLIPSE','EDIT_XSEC_RECTANGLE'):
                with self.subTest(kind=kind,shape=shape):
                    v.ClearVSPModel();gid=v.AddGeom(kind);surf=v.GetXSecSurf(gid,0);v.ChangeXSecShape(surf,1,v.XS_EDIT_CURVE);x=v.GetXSec(surf,1)
                    v.EditXSecConvertTo(x,v.LINEAR);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
                    v.SetParmVal(v.GetXSecParm(x,'ShapeType'),getattr(v,shape));v.EditXSecInitShape(x);v.Update()
                    reference=self.path/'reference.vsp3';v.WriteVSPFile(str(reference),v.SET_ALL)
                    expected,_=self.worker(dict(action='state'),reference)
                    actual,saved=self.worker(dict(action='mutate',operation='curve-init',geom=gid,surface=0,index=1,shape=shape))
                    expected=expected['components'][0]
                    self.assertEqual(actual['components'][0]['sections'][1]['initShape'],shape)
                    self.assertEqual(actual['components'][0]['surfaces'],expected['surfaces'])
                    self.assertEqual(actual['components'][0]['sections'][1]['controlPoints'],expected['sections'][1]['controlPoints'])
                    reopened,_=self.worker(dict(action='state'),saved)
                    self.assertEqual(reopened['components'][0]['sections'][1]['initShape'],shape)
                    self.assertEqual(reopened['components'][0]['surfaces'],expected['surfaces'])


    def test_revolution_and_both_region_editors_use_native_rectangle(self):
        v=self.v;bor=v.AddGeom('BODYOFREVOLUTION');region=v.AddSubSurf(self.gid,v.SS_XSEC_CURVE)
        index=v.AddFeaStruct(self.gid);sid=v.GetFeaStructID(self.gid,index);fea=v.AddFeaSubSurf(self.gid,index,v.SS_XSEC_CURVE)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        scratch=v.AddGeom('STACK');surf=v.GetXSecSurf(scratch,0);v.ChangeXSecShape(surf,1,v.XS_EDIT_CURVE);x=v.GetXSec(surf,1)
        v.SetParmVal(v.GetXSecParm(x,'ShapeType'),v.EDIT_XSEC_RECTANGLE);v.EditXSecInitShape(x);v.Update()
        expected=[[p.x(),p.y(),p.z()] for p in v.GetEditXSecCtrlVec(x,True)]
        cases=[(dict(operation='bor-curve-convert',geom=bor),dict(operation='bor-curve-init',geom=bor),'bor'),(dict(operation='region-curve-convert',geom=self.gid,id=region),dict(operation='region-curve-init',geom=self.gid,id=region),'controls'),(dict(operation='region-curve-convert',structure=sid,id=fea),dict(operation='region-curve-init',structure=sid,id=fea),'structuralSubsurfaces')]
        for convert,initialize,key in cases:
            _,path=self.worker(dict(action='mutate',**convert))
            state,saved=self.worker(dict(action='mutate',shape='EDIT_XSEC_RECTANGLE',**initialize),path)
            if key=='bor':curve=next(c for c in state['tools']['bodiesOfRevolution'] if c['id']==bor)['editable']
            else:curve=next(c for c in state['tools'][key] if c['id']==initialize['id'])['sectionCurve']
            self.assertEqual(curve['initShape'],'EDIT_XSEC_RECTANGLE')
            self.assertEqual(curve['controlPoints'],expected)
            reopened,_=self.worker(dict(action='state'),saved)
            self.assertEqual({c['id']:c['surfaces'] for c in reopened['components']},{c['id']:c['surfaces'] for c in state['components']})


    def test_auxiliary_cone_preset_matches_native_editable_rectangle(self):
        import test_auxiliary_controls
        test_auxiliary_controls.NativeAuxiliaryControls.fixture(self)
        v=self.v;v.SetParmValUpdate(self.aux,'AuxiliaryGeomType','Design',v.AUX_GEOM_SUPER_CONE);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        _,path=self.worker(dict(action='mutate',operation='auxiliary-profile-shape',geom=self.aux,shape='XS_EDIT_CURVE'))
        state,saved=self.worker(dict(action='mutate',operation='auxiliary-profile-edit-init',geom=self.aux,shape='EDIT_XSEC_RECTANGLE'),path)
        scratch=v.AddGeom('STACK');surf=v.GetXSecSurf(scratch,0);v.ChangeXSecShape(surf,1,v.XS_EDIT_CURVE);x=v.GetXSec(surf,1)
        v.SetParmVal(v.GetXSecParm(x,'ShapeType'),v.EDIT_XSEC_RECTANGLE);v.EditXSecInitShape(x);v.Update()
        expected=[[p.x(),p.y(),p.z()] for p in v.GetEditXSecCtrlVec(x,True)]
        profile=next(a for a in state['tools']['auxiliary'] if a['id']==self.aux)['controls']['profile']
        self.assertEqual(profile['initShape'],'EDIT_XSEC_RECTANGLE')
        self.assertEqual(profile['controlPoints'],expected)
        reopened,_=self.worker(dict(action='state'),saved)
        self.assertEqual({c['id']:c['surfaces'] for c in reopened['components']},{c['id']:c['surfaces'] for c in state['components']})


if __name__=='__main__':unittest.main()
