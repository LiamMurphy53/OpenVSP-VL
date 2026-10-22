"""One native parameter may have several independently bound custom widgets."""
import unittest
import test_native
import test_custom_scripts

class OwnCustomControls(unittest.TestCase):
    setUpClass=classmethod(test_custom_scripts.CustomScripts.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    template=test_custom_scripts.CustomScripts.template
    import_component=test_custom_scripts.CustomScripts.import_component
    fields=test_custom_scripts.CustomScripts.fields
    rejected_file_is_unchanged=test_custom_scripts.CustomScripts.rejected_file_is_unchanged

    def script(self):
        text=self.template().replace('int LengthSlider;','int FineLength;\nint LengthSlider;')
        text=text.replace('void Init()\n{','void Init()\n{\n string sw=AddParm(PARM_BOOL_TYPE,"SelectWidth","Design");SetParmVal(sw,0);')
        text=text.replace('void InitGui()\n{','void InitGui()\n{\n')
        text=text.replace('SquareButton = AddGui','AddGui(GDEV_SCROLL_TAB,"Fine adjustments");AddGui(GDEV_DIVIDER_BOX,"Fine dimensions");FineLength=AddGui(GDEV_SLIDER_ADJ_RANGE_INPUT,"Fine dimension","","",.1);AddGui(GDEV_TOGGLE_BUTTON,"Fine edits width","SelectWidth","Design");\n SquareButton = AddGui')
        text=text.replace('void UpdateGui()\n{','void UpdateGui()\n{\n string owner=GetCurrCustomGeom();if(GetBoolParmVal(GetParm(owner,"SelectWidth","Design")))UpdateGui(FineLength,GetParm(owner,"Width","Design"));else UpdateGui(FineLength,GetParm(owner,"Length","Design"));')
        return text

    def test_duplicate_own_widgets_keep_independent_labels_tabs_ranges_and_ids(self):
        _,path,c=self.import_component(self.script());gid=c['id'];fields=self.fields(c);length=fields['Length']['id']
        controls=[r for r in c['customOwnControls'] if r['parameter']['id']==length]
        self.assertEqual(len(controls),2);self.assertTrue(all(r['owned'] for r in controls));self.assertFalse(c['customExternalControls'])
        self.assertEqual([r['parameter']['label'] for r in controls],['Length','Fine dimension'])
        self.assertEqual([r['tab'] for r in controls],['Design','Fine adjustments'])
        self.assertEqual([r['parameter']['customSlider']['range'] for r in controls],[10,.1])
        self.assertNotEqual(controls[0]['index'],controls[1]['index']);self.assertNotEqual(controls[0]['parameter']['customSlider']['key'],controls[1]['parameter']['customSlider']['key'])
        self.assertEqual(sum(p['id']==length for p in c['params']),1)
        for row,value in zip(controls,[6.,6.1]):
            state,path=self.worker(dict(action='mutate',operation='custom-control-parameter',geom=gid,index=row['index'],id=length,value=value),path)
        actual=next(c for c in state['components'] if c['id']==gid);self.assertEqual([r['parameter']['value'] for r in actual['customOwnControls'] if r['parameter']['id']==length],[6.1,6.1])
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();reference=v.AddGeom('Box');v.SetParmValUpdate(v.FindParm(reference,'Length','Design'),6.1);v.Update()
        for s in actual['surfaces']:
            u,w=v.GetUWTess01(reference,s['index']%v.GetNumMainSurfs(reference));points=[[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(reference,s['index'],[a for a in u for _ in w],[b for _ in u for b in w])];self.assertEqual(s['points'],points)
        cold,_=self.worker(dict(action='state'),path);self.assertEqual(next(c for c in cold['components'] if c['id']==gid)['customOwnControls'],actual['customOwnControls'])

    def test_rebound_own_widget_rejects_stale_target_and_exposes_current_target(self):
        _,path,c=self.import_component(self.script());gid=c['id'];fields=self.fields(c);old=next(r for r in c['customOwnControls'] if r['parameter']['label']=='Fine dimension')
        state,path=self.worker(dict(action='mutate',operation='parameter',id=fields['SelectWidth']['id'],value=1),path)
        changed=next(c for c in state['components'] if c['id']==gid);row=next(r for r in changed['customOwnControls'] if r['index']==old['index'])
        self.assertEqual(row['parameter']['id'],fields['Width']['id']);self.assertEqual(row['parameter']['customSlider']['range'],.1)
        self.rejected_file_is_unchanged(dict(action='mutate',operation='custom-control-parameter',geom=gid,index=old['index'],id=old['parameter']['id'],value=8),path)
        state,path=self.worker(dict(action='mutate',operation='custom-control-parameter',geom=gid,index=row['index'],id=row['parameter']['id'],value=8),path)
        actual=next(c for c in state['components'] if c['id']==gid);self.assertEqual(self.fields(actual)['Width']['value'],8);self.assertEqual(self.fields(actual)['Length']['value'],5)
        cold,_=self.worker(dict(action='state'),path);self.assertEqual(next(c for c in cold['components'] if c['id']==gid)['customOwnControls'],actual['customOwnControls'])

    def test_disconnected_own_controls_remain_visible_and_read_only(self):
        _,path,c=self.import_component(self.template());gid=c['id'];fields=self.fields(c);old={r['parameter']['id']:r for r in c['customOwnControls']}
        state,path=self.worker(dict(action='mutate',operation='parameter',id=fields['SquareFlag']['id'],value=1),path)
        actual=next(c for c in state['components'] if c['id']==gid)
        for name in ('Width','Height'):
            pid=fields[name]['id'];row=next(r for r in actual['customOwnControls'] if r['parameter']['id']==pid)
            self.assertEqual(row['index'],old[pid]['index']);self.assertTrue(row['parameter']['displayReadOnly'])
            self.rejected_file_is_unchanged(dict(action='mutate',operation='custom-control-parameter',geom=gid,index=row['index'],id=pid,value=8),path)


    def test_input_and_output_views_of_one_parameter_keep_separate_editability(self):
        text=self.template().replace('int LengthSlider;','int LengthOutput;\nint LengthSlider;')
        text=text.replace('void InitGui()\n{','void InitGui()\n{\n LengthOutput=AddGui(GDEV_OUTPUT,"Length readout");')
        text=text.replace('void UpdateGui()\n{','void UpdateGui()\n{\n UpdateGui(LengthOutput,GetParm(GetCurrCustomGeom(),"Length","Design"));')
        _,path,c=self.import_component(text);gid=c['id'];rows={r['parameter']['label']:r for r in c['customOwnControls']}
        self.assertTrue(rows['Length readout']['parameter']['displayReadOnly']);self.assertFalse(rows['Length']['parameter'].get('displayReadOnly',False))
        self.rejected_file_is_unchanged(dict(action='mutate',operation='custom-control-parameter',geom=gid,index=rows['Length readout']['index'],id=rows['Length readout']['parameter']['id'],value=7),path)
        state,path=self.worker(dict(action='mutate',operation='custom-control-parameter',geom=gid,index=rows['Length']['index'],id=rows['Length']['parameter']['id'],value=7),path)
        self.assertEqual(self.fields(next(c for c in state['components'] if c['id']==gid))['Length']['value'],7)

    def profile_fixture(self):
        text=self.template().replace('int LengthSlider;','int ProfileRadius;\nint LengthSlider;')
        text=text.replace('LengthSlider = AddGui','ProfileRadius=AddGui(GDEV_SLIDER_INPUT,"First profile radius","","",.1);\n LengthSlider = AddGui')
        text=text.replace('void UpdateGui()\n{','void UpdateGui()\n{\n UpdateGui(ProfileRadius,GetXSecParm(GetXSec(GetXSecSurf(GetCurrCustomGeom(),0),1),"RoundRectXSec_Radius"));')
        text=text.replace('SetParmVal( GetXSecParm( xsec1, "RoundRectXSec_Radius" ), 0.0 );','')
        _,path,c=self.import_component(text);gid=c['id'];row=next(r for r in c['customExternalControls'] if r['parameter']['label']=='First profile radius');pid=row['parameter']['id']
        return path,c,row

    def test_generated_profile_control_is_read_only_without_saved_component_input(self):
        path,c,row=self.profile_fixture()
        self.assertTrue(row['parameter']['displayReadOnly'])
        # This native script regenerates its profile on load: an apparent live
        # edit must not be offered as a persistent component input.
        v=self.v;gid=c['id'];v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        radius=lambda:v.GetXSecParm(v.GetXSec(v.GetXSecSurf(gid,0),1),'RoundRectXSec_Radius')
        initial=v.GetParmVal(radius());v.SetParmValUpdate(radius(),.25);v.Update();self.assertEqual(v.GetParmVal(radius()),.25)
        from pathlib import Path
        probe=Path(path).with_name('original-profile-probe.vsp3');v.WriteVSPFile(str(probe),v.SET_ALL)
        v.ClearVSPModel();v.ReadVSPFile(str(probe));v.Update();self.assertEqual(v.GetParmVal(radius()),initial)
        self.rejected_file_is_unchanged(dict(action='mutate',operation='custom-control-parameter',geom=c['id'],index=row['index'],id=row['parameter']['id'],value=.25),path)

import test_studies
import native_service as service

class OwnCustomHistory(unittest.TestCase):
    setUpClass=classmethod(test_studies.NativeStudies.setUpClass.__func__)
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    worker=test_native.NativeIntegration.worker
    template=test_custom_scripts.CustomScripts.template
    import_component=test_custom_scripts.CustomScripts.import_component
    script=OwnCustomControls.script

    def fixture(self):
        _,path,self.component=self.import_component(self.script());self.model.write_bytes(path.read_bytes())
        return [r for r in self.component['customOwnControls'] if r['parameter']['name']=='Length']

    def edit(self,row,value):
        return service.mutation(dict(operation='custom-control-parameter',geom=self.component['id'],index=row['index'],id=row['parameter']['id'],value=value,editGesture='a'*32,revision=service.REVISION))

    def test_repeated_own_widgets_keep_separate_undo_steps_for_same_parameter(self):
        coarse,fine=self.fixture();before=self.model.read_bytes()
        self.edit(coarse,6.);coarse_bytes=self.model.read_bytes();self.assertEqual(len(service.HISTORY),1)
        self.edit(fine,6.1);self.edit(fine,6.2);self.assertEqual(len(service.HISTORY),2);final=self.model.read_bytes()
        service.undo(revision=service.REVISION);self.assertEqual(self.model.read_bytes(),coarse_bytes)
        service.undo(revision=service.REVISION);self.assertEqual(self.model.read_bytes(),before)
        service.undo(redo=True,revision=service.REVISION);service.undo(redo=True,revision=service.REVISION);self.assertEqual(self.model.read_bytes(),final)

    def test_shared_native_lock_is_reflected_in_every_widget_and_rejects_edits(self):
        coarse,fine=self.fixture();pid=coarse['parameter']['id'];state=service.mutation(dict(operation='property-lock',parameters=[pid],locked=True,revision=service.REVISION))
        before=self.model.read_bytes();history=list(service.HISTORY);c=next(c for c in state['components'] if c['id']==self.component['id'])
        self.assertTrue(all(r['parameter']['userLocked'] for r in c['customOwnControls'] if r['parameter']['id']==pid))
        for row in (coarse,fine):
            with self.assertRaisesRegex(ValueError,'locked'):self.edit(row,8.)
        self.assertEqual(self.model.read_bytes(),before);self.assertEqual(service.HISTORY,history)
