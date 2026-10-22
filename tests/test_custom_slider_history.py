"""Live external custom controls retain script binding identity and native history."""
import base64
import unittest
import test_studies
import test_custom_bindings
import test_custom_scripts
import test_native
import native_service as service

class CustomSliderHistory(unittest.TestCase):
    setUpClass=classmethod(test_studies.NativeStudies.setUpClass.__func__)
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    worker=test_native.NativeIntegration.worker
    template=test_custom_scripts.CustomScripts.template

    def fixture(self,variant=None):
        parent,child,state,path,text=test_custom_bindings.ExternalCustomBindings.fixture(self)
        if variant=='rebind':
            text=text.replace('UpdateGui(ParentLength,GetParm(parent_owner,"Length","Design"));','if(GetParmVal(GetParm(parent_owner,"Length","Design"))>=6)UpdateGui(ParentLength,GetParm(parent_owner,"Width","Design"));else UpdateGui(ParentLength,GetParm(parent_owner,"Length","Design"));')
        if variant=='output':text=text.replace('GDEV_SLIDER_INPUT,"Parent length"','GDEV_OUTPUT,"Parent length"')
        if variant=='duplicate':
            text=text.replace('int ParentSelector;','int ParentOther;int ParentSelector;')
            text=text.replace('void InitGui()\n{','void InitGui()\n{\n ParentOther=AddGui(GDEV_SLIDER_INPUT,"Parent alternate length");')
            text=text.replace('void UpdateGui()\n{','void UpdateGui()\n{\n UpdateGui(ParentOther,GetParm(GetGeomParent(GetCurrCustomGeom()),"Length","Design"));')
        if variant:
            state,path=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_SCRIPT',name='Bound slider',parent=parent,content=base64.b64encode(text.encode()).decode()))
            child=next(c for c in state['components'] if c['name']=='Bound slider')
        self.model.write_bytes(path.read_bytes());self.parent=parent;self.child=child
        return next(x for x in child['customExternalControls'] if x['parameter']['label']=='Parent length')

    def change(self,control,value,token='a'*32):
        return service.mutation(dict(operation='custom-control-parameter',geom=self.child['id'],index=control['index'],id=control['parameter']['id'],value=value,editGesture=token,revision=service.REVISION))

    def capture(self):
        v=self.v;out=[]
        for g in v.FindGeoms():
            fields=sorted((v.GetParmDisplayGroupName(p),v.GetParmName(p),v.GetParmVal(p)) for p in v.GetGeomParmIDs(g));surfaces=[]
            for i in range(v.GetTotalNumSurfs(g)):
                u,w=v.GetUWTess01(g,i%v.GetNumMainSurfs(g));surfaces.append([[q.x(),q.y(),q.z()] for q in v.CompVecPnt01(g,i,[a for a in u for _ in w],[b for _ in u for b in w])])
            out.append((g,fields,surfaces))
        return out

    def test_live_external_slider_matches_original_and_is_one_undo_step(self):
        control=self.fixture();v=self.v;before=self.model.read_bytes();reference=self.path/'original-source.vsp3';reference.write_bytes(before)
        for value in (4.,5.,6.):state=self.change(control,value)
        self.assertEqual(len(service.HISTORY),1);final=self.model.read_bytes()
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();actual=self.capture()
        v.ClearVSPModel();v.ReadVSPFile(str(reference));v.Update()
        for value in (4.,5.,6.):v.SetParmValUpdate(control['parameter']['id'],value);v.Update()
        native=self.path/'original-final.vsp3';v.WriteVSPFile(str(native),v.SET_ALL);v.ClearVSPModel();v.ReadVSPFile(str(native));v.Update();self.assertEqual(actual,self.capture())
        service.undo(revision=service.REVISION);self.assertEqual(self.model.read_bytes(),before)
        service.undo(redo=True,revision=service.REVISION);self.assertEqual(self.model.read_bytes(),final)
        cold=service.state();self.assertEqual(next(c for c in cold['components'] if c['id']==self.child['id'])['customExternalControls'],next(c for c in state['components'] if c['id']==self.child['id'])['customExternalControls'])

    def test_script_rebinding_rejects_next_frame_without_changing_valid_state(self):
        control=self.fixture('rebind');self.change(control,6.);valid=self.model.read_bytes();history=list(service.HISTORY)
        with self.assertRaisesRegex(ValueError,'another parameter'):self.change(control,7.)
        self.assertEqual(self.model.read_bytes(),valid);self.assertEqual(service.HISTORY,history)
        current=next(x for x in next(c for c in service.state()['components'] if c['id']==self.child['id'])['customExternalControls'] if x['index']==control['index'])
        self.assertNotEqual(current['parameter']['id'],control['parameter']['id'])
        self.change(current,4.,'b'*32);self.assertEqual(len(service.HISTORY),2)
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();self.assertEqual(v.GetParmVal(self.parent,'Length','Design'),6.);self.assertEqual(v.GetParmVal(self.parent,'Width','Design'),4.)

    def test_same_token_cannot_merge_distinct_custom_controls_for_same_parameter(self):
        control=self.fixture('duplicate');other=next(x for x in self.child['customExternalControls'] if x['parameter']['label']=='Parent alternate length')
        self.assertEqual(other['parameter']['id'],control['parameter']['id'])
        self.change(control,4.);self.change(other,5.);self.assertEqual(len(service.HISTORY),2)

    def test_saved_property_lock_rejects_live_edits(self):
        control=self.fixture();service.mutation(dict(operation='property-lock',parameters=[control['parameter']['id']],locked=True,revision=service.REVISION));before=self.model.read_bytes();history=list(service.HISTORY)
        with self.assertRaisesRegex(ValueError,'locked'):self.change(control,7.)
        self.assertEqual(self.model.read_bytes(),before);self.assertEqual(service.HISTORY,history)

    def test_native_output_rejects_live_edits(self):
        control=self.fixture('output');before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'calculated output'):self.change(control,7.)
        self.assertEqual(self.model.read_bytes(),before);self.assertFalse(service.HISTORY)
