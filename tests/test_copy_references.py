"""Native clipboard operations cannot persist dangling parameter references."""
import sys,unittest
import test_native

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class CopyReferences(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        import native_references,native_auxiliary_controls as auxiliary
        v=self.v;source=v.AddGeom('STACK');ss=v.GetXSecSurf(source,0);v.ChangeXSecShape(ss,1,v.XS_ROUNDED_RECTANGLE)
        body=v.AddGeom('STACK');x=v.GetXSec(v.GetXSecSurf(body,0),1)
        bor=v.AddGeom('BODYOFREVOLUTION');region=v.AddSubSurf(self.gid,v.SS_XSEC_CURVE)
        index=v.AddFeaStruct(self.gid);sid=v.GetFeaStructID(self.gid,index);structural=v.AddFeaSubSurf(self.gid,index,v.SS_XSEC_CURVE)
        aux=v.AddGeom('AUXILIARY');v.SetParmValUpdate(aux,'AuxiliaryGeomType','Design',v.AUX_GEOM_SUPER_CONE)
        v.Update();refs=native_references.references(v)
        cases=[(dict(operation='section-copy-from',geom=body,surface=0,index=1,curveOnly=True),v.GetXSecParm(x,'Theta')),(dict(operation='bor-profile-copy',geom=bor),v.FindParm(bor,'Theta','XSecCurve'))]
        for owner,rid in [(dict(geom=self.gid),region),(dict(structure=sid),structural)]:
            cid=refs[rid]['curveID'];pid=next(p for p in v.FindContainerParmIDs(cid) if v.GetParmName(p)=='Theta');cases.append((dict(operation='region-curve-copy-from',id=rid,**owner),pid))
        cid=auxiliary.curve_container(v,aux);cases.append((dict(operation='auxiliary-profile-copy',geom=aux),next(p for p in v.FindContainerParmIDs(cid) if v.GetParmName(p)=='Theta')))
        for i,(_,pid) in enumerate(cases):v.AddAttributeParm(v.GetChildCollection(v.GetVehicleID()),'Copy target '+str(i),pid)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return dict(kind='section',geom=source,surface=0,index=1),cases

    def test_five_copy_targets_reject_deleted_referenced_parameters_atomically(self):
        source,cases=self.fixture();before=self.model.read_bytes()
        for request,pid in cases:
            with self.subTest(operation=request['operation'],id=request.get('id')):
                existing=set(self.path.glob('*/aircraft.vsp3'))
                with self.assertRaisesRegex(ValueError,'copy replaces native parameter IDs used by parameter reference'):
                    self.worker(dict(action='mutate',source=source,**request))
                candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before)

    def test_same_family_copy_obeys_each_native_owner_identity_behavior(self):
        source,cases=self.fixture();v=self.v
        ss=v.GetXSecSurf(source['geom'],0)
        for request,pid in cases:
            # Surface/structural regions default to Circle; other targets to Ellipse.
            shape=v.XS_CIRCLE if request['operation']=='region-curve-copy-from' else v.XS_ELLIPSE
            v.ChangeXSecShape(ss,1,shape);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
            before=self.model.read_bytes();existing=set(self.path.glob('*/aircraft.vsp3'))
            if request['operation']=='region-curve-copy-from':
                state,path=self.worker(dict(action='mutate',source=source,**request))
                cold,_=self.worker(dict(action='state'),path)
                key='structuralSubsurfaces' if 'structure' in request else 'controls'
                for result in (state,cold):
                    row=next(r for r in result['tools'][key] if r['id']==request['id'])
                    self.assertIn(pid,{p['id'] for p in row['sectionCurve']['params']})
                    self.assertTrue(any(a['values']==[pid] for a in result['tools']['attributes']))
            else:
                with self.assertRaisesRegex(ValueError,'copy replaces native parameter IDs used by parameter reference'):
                    self.worker(dict(action='mutate',source=source,**request))
                candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before)

    def test_same_family_copy_preserves_unrelated_references_and_native_geometry(self):
        source,cases=self.fixture();v=self.v
        attr=next(a for a in v.FindAllAttributes() if v.GetAttributeName(a)=='Copy target 0');v.DeleteAttribute(attr)
        ss=v.GetXSecSurf(source['geom'],0);v.ChangeXSecShape(ss,1,v.XS_ELLIPSE);x=v.GetXSec(ss,1);v.SetXSecWidth(x,7);v.SetXSecHeight(x,4);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        request,pid=cases[0];v.CopyXSecCurve(source['geom'],1);v.PasteXSecCurve(request['geom'],1);v.Update();reference=self.path/'reference.vsp3';v.WriteVSPFile(str(reference),v.SET_ALL)
        expected,_=self.worker(dict(action='state'),reference)
        state,path=self.worker(dict(action='mutate',source=source,**request))
        reopened,_=self.worker(dict(action='state'),path)
        for result in (state,reopened):
            component=next(c for c in result['components'] if c['id']==request['geom']);native=next(c for c in expected['components'] if c['id']==request['geom'])
            self.assertEqual(component['surfaces'],native['surfaces'])
            for i,(_,other_pid) in enumerate(cases[1:],1):self.assertEqual(next(a['values'] for a in result['tools']['attributes'] if a['name']=='Copy target '+str(i)),[other_pid])

    def test_copy_guards_links_presets_expressions_and_design_variables(self):
        source,cases=self.fixture();v=self.v;request,pid=cases[0]
        attr=next(a for a in v.FindAllAttributes() if v.GetAttributeName(a)=='Copy target 0');v.DeleteAttribute(attr)
        for kind in ('parameter link','preset','expression','design variable'):
            if kind=='parameter link':v.AddParmLink(pid,v.FindParm(self.gid,'X_Rel_Location','XForm'))
            elif kind=='preset':
                group=v.AddVarPresetGroup('Copy reference');v.AddVarPresetParm(group,pid);setting=v.AddVarPresetSetting(group,'Original');v.SaveVarPresetParmVals(group,setting)
            elif kind=='expression':
                v.AddAdvLink('Copy expression');index=v.GetLinkIndex('Copy expression');v.AddAdvLinkInput(index,pid,'profile_theta');v.AddAdvLinkOutput(index,v.FindParm(self.gid,'Y_Rel_Location','XForm'),'position_y');v.SetAdvLinkCode(index,'position_y = profile_theta;');v.BuildAdvLinkScript(index)
            else:
                import native_files
                v.AddDesignVar(pid,v.XDDM_VAR);native_files.save_design(v)
            v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes();existing=set(self.path.glob('*/aircraft.vsp3'))
            with self.assertRaisesRegex(ValueError,kind):self.worker(dict(action='mutate',source=source,**request))
            candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before)

    def test_whole_section_copy_routes_preserve_referenced_destination(self):
        source,cases=self.fixture();request,pid=cases[0];before=self.model.read_bytes()
        routes=[dict(**{**request,'curveOnly':False},source=source),dict(operation='section-copy-from',geom=request['geom'],surface=0,index=1,sourceGeom=source['geom'],sourceSurface=0,sourceIndex=1)]
        for route in routes:
            existing=set(self.path.glob('*/aircraft.vsp3'))
            with self.assertRaisesRegex(ValueError,'copy replaces native parameter IDs used by parameter reference'):
                self.worker(dict(action='mutate',**route))
            candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before)

if __name__=='__main__':unittest.main()
