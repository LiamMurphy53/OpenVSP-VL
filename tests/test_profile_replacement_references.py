"""Native profile replacement preserves referenced IDs or rejects atomically."""
import sys
import unittest
import test_native


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class ProfileReferences(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;g=v.AddGeom('STACK');surf=v.GetXSecSurf(g,0);x=v.GetXSec(surf,1)
        pid=v.GetXSecParm(x,'Theta');v.AddAttributeParm(v.GetChildCollection(v.GetVehicleID()),'Profile orientation reference',pid)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return g,pid,v.GetXSecShape(x)

    def test_referenced_profile_rejects_shape_import_and_conversion(self):
        g,pid,shape=self.fixture();before=self.model.read_bytes()
        requests=[dict(operation='shape',shape=self.v.XS_ROUNDED_RECTANGLE),dict(operation='curve-convert'),dict(operation='airfoil-import',content='Airfoil\n1 0\n.5 .1\n0 0\n.5 -.1\n1 0\n'),dict(operation='section-profile-import',content='OPENVSP_XSEC_FILE_V1\n1 0\n0 -1\n-1 0\n0 1\n1 0\n')]
        for extra in requests:
            existing=set(self.path.glob('*/aircraft.vsp3'))
            with self.assertRaisesRegex(ValueError,'profile parameter IDs used by parameter reference'):
                self.worker(dict(action='mutate',geom=g,surface=0,index=1,**extra))
            candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before)

    def test_same_profile_family_keeps_saved_reference(self):
        g,pid,shape=self.fixture()
        _,path=self.worker(dict(action='mutate',operation='shape',geom=g,surface=0,index=1,shape=shape))
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        self.assertTrue(v.ValidParm(pid))
        attr=next(a for a in v.FindAllAttributes() if v.GetAttributeName(a)=='Profile orientation reference')
        self.assertEqual(list(v.GetAttributeParmID(attr)),[pid])


    def test_cst_fit_rejects_referenced_original_airfoil(self):
        v=self.v;x=v.GetXSec(v.GetXSecSurf(self.gid,0),1);pid=v.GetXSecParm(x,'Theta')
        v.AddAttributeParm(v.GetChildCollection(v.GetVehicleID()),'Airfoil reference',pid);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'profile parameter IDs used by parameter reference'):
            self.worker(dict(action='mutate',operation='cst-fit',geom=self.gid,surface=0,index=1,degree=8))
        self.assertEqual(next(self.path.glob('*/aircraft.vsp3')).read_bytes(),before)


    def test_revolution_replacements_preserve_referenced_profile(self):
        v=self.v;g=v.AddGeom('BODYOFREVOLUTION');v.ChangeBORXSecShape(g,v.XS_FOUR_SERIES)
        pid=v.FindParm(g,'Theta','XSecCurve');v.AddAttributeParm(v.GetChildCollection(v.GetVehicleID()),'Revolution profile reference',pid)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        requests=[dict(operation='bor-shape',shape='XS_ELLIPSE'),dict(operation='bor-curve-convert'),dict(operation='bor-cst-fit',degree=8),dict(operation='bor-airfoil',content='Airfoil\n1 0\n.5 .1\n0 0\n.5 -.1\n1 0\n'),dict(operation='bor-profile',content='OPENVSP_XSEC_FILE_V1\n1 0\n0 -1\n-1 0\n0 1\n1 0\n')]
        for extra in requests:
            existing=set(self.path.glob('*/aircraft.vsp3'))
            with self.assertRaisesRegex(ValueError,'profile parameter IDs used by parameter reference'):
                self.worker(dict(action='mutate',geom=g,**extra))
            candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before)
        baseline,_=self.worker(dict(action='state'))
        before_ref=next(a for a in baseline['tools']['attributes'] if a['name']=='Revolution profile reference')['values']
        state,path=self.worker(dict(action='mutate',operation='bor-shape',geom=g,shape='XS_FOUR_SERIES'))
        after_ref=next(a for a in state['tools']['attributes'] if a['name']=='Revolution profile reference')['values']
        reopened,_=self.worker(dict(action='state'),path)
        reopened_ref=next(a for a in reopened['tools']['attributes'] if a['name']=='Revolution profile reference')['values']
        self.assertEqual(after_ref,before_ref);self.assertEqual(reopened_ref,before_ref)
        curve=next(c for c in reopened['components'] if c['id']==g)
        self.assertIn(before_ref[0],{p['id'] for p in curve['params'] if p['name']=='Theta' and p['rawGroup']=='XSecCurve'})

    def test_region_and_auxiliary_profile_replacement_guards(self):
        import native_references
        import native_auxiliary_controls as auxiliary
        v=self.v
        region=v.AddSubSurf(self.gid,v.SS_XSEC_CURVE)
        index=v.AddFeaStruct(self.gid);sid=v.GetFeaStructID(self.gid,index)
        structural=v.AddFeaSubSurf(self.gid,index,v.SS_XSEC_CURVE)
        aux=v.AddGeom('AUXILIARY');v.SetParmValUpdate(aux,'AuxiliaryGeomType','Design',v.AUX_GEOM_SUPER_CONE)
        v.Update();refs=native_references.references(v)
        cases=[('region-curve-',dict(geom=self.gid,id=region),refs[region]['curveID'],refs[region]['curveType']),('region-curve-',dict(structure=sid,id=structural),refs[structural]['curveID'],refs[structural]['curveType']),('auxiliary-profile-',dict(geom=aux),auxiliary.curve_container(v,aux),auxiliary.curve(v,aux)['type'])]
        for prefix,owner,cid,current in cases:
            pid=next(p for p in v.FindContainerParmIDs(cid) if v.GetParmName(p)=='Theta')
            v.AddAttributeParm(v.GetChildCollection(v.GetVehicleID()),prefix+cid,pid)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        for prefix,owner,cid,current in cases:
            requests=[dict(operation=prefix+'shape',shape='XS_ELLIPSE' if current!=v.XS_ELLIPSE else 'XS_CIRCLE'),dict(operation=prefix+'convert'),dict(operation=prefix+'import',format='section',content='OPENVSP_XSEC_FILE_V1\n1 0\n0 -1\n-1 0\n0 1\n1 0\n'),dict(operation=prefix+'import',format='airfoil',content='Airfoil\n1 0\n.5 .1\n0 0\n.5 -.1\n1 0\n')]
            for request in requests:
                existing=set(self.path.glob('*/aircraft.vsp3'))
                with self.assertRaisesRegex(ValueError,'profile parameter IDs used by parameter reference'):
                    self.worker(dict(action='mutate',**owner,**request))
                candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before)
            from native_special import SHAPES
            shape=next(name for name in SHAPES if getattr(v,name)==current)
            baseline,_=self.worker(dict(action='state'))
            state,path=self.worker(dict(action='mutate',operation=prefix+'shape',shape=shape,**owner))
            cold,_=self.worker(dict(action='state'),path)
            def reference(data):return next(a['values'] for a in data['tools']['attributes'] if a['name']==prefix+cid)
            self.assertEqual(reference(state),reference(baseline));self.assertEqual(reference(cold),reference(baseline))

    def test_unrelated_expression_does_not_change_reference_error_label(self):
        g,pid,shape=self.fixture();v=self.v
        v.AddAdvLink('Unrelated expression');index=v.GetLinkIndex('Unrelated expression')
        v.AddAdvLinkInput(index,v.FindParm(self.gid,'X_Rel_Location','XForm'),'source_x')
        v.AddAdvLinkOutput(index,v.FindParm(g,'X_Rel_Location','XForm'),'target_x')
        v.SetAdvLinkCode(index,'target_x = source_x;');v.BuildAdvLinkScript(index)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        with self.assertRaisesRegex(ValueError,'native profile parameter IDs used by parameter reference'):
            self.worker(dict(action='mutate',operation='shape',geom=g,surface=0,index=1,shape=v.XS_ROUNDED_RECTANGLE))


if __name__=='__main__':unittest.main()
