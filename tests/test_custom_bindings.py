"""External custom controls retain original owners and current native bindings."""
import base64,sys,unittest
import test_native,test_custom_scripts

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class ExternalCustomBindings(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    template=test_custom_scripts.CustomScripts.template
    rejected_file_is_unchanged=test_custom_scripts.CustomScripts.rejected_file_is_unchanged

    def fixture(self,variant=None):
        v=self.v;v.ClearVSPModel();parent=v.AddGeom('BoxGroup');v.SetGeomName(parent,'Parent array');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        text=self.template().replace('int LengthSlider;','int ParentSelector;int ParentLength;\nint LengthSlider;')
        text=text.replace('void Init()\n{','void Init()\n{\n string mode=AddParm(PARM_BOOL_TYPE,"SelectColumns","Design");SetParmVal(mode,0);')
        text=text.replace('void InitGui()\n{','void InitGui()\n{\n ParentSelector=AddGui(GDEV_INDEX_SELECTOR,"Parent count");ParentLength=AddGui(GDEV_SLIDER_INPUT,"Parent length");AddGui(GDEV_TOGGLE_BUTTON,"Use columns","SelectColumns","Design");')
        text=text.replace('void UpdateGui()\n{','void UpdateGui()\n{\n string parent_owner=GetGeomParent(GetCurrCustomGeom());\n if(GetBoolParmVal(GetParm(GetCurrCustomGeom(),"SelectColumns","Design")))UpdateGui(ParentSelector,GetParm(parent_owner,"NumCol","Design"));\n else UpdateGui(ParentSelector,GetParm(parent_owner,"NumRow","Design"));\n UpdateGui(ParentLength,GetParm(parent_owner,"Length","Design"));')
        if variant=='output':text=text.replace('GDEV_SLIDER_INPUT,"Parent length"','GDEV_OUTPUT,"Parent length"')
        if variant=='choice':text=text.replace('ParentSelector=AddGui(GDEV_INDEX_SELECTOR,"Parent count");','ParentSelector=AddGui(GDEV_CHOICE,"Parent count");AddGui(GDEV_ADD_CHOICE_ITEM,"Zero");AddGui(GDEV_ADD_CHOICE_ITEM,"One");AddGui(GDEV_ADD_CHOICE_ITEM,"Two");')
        state,path=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_SCRIPT',name='External controls',parent=parent,content=base64.b64encode(text.encode()).decode()))
        child=next(c for c in state['components'] if c['name']=='External controls')
        return parent,child,state,path,text

    def test_external_controls_edit_native_parent_and_reopen_with_exact_geometry(self):
        parent,child,state,path,text=self.fixture();gid=child['id'];controls={r['parameter']['label']:r for r in child['customExternalControls']}
        self.assertEqual(set(controls),{'Parent count','Parent length'});row=controls['Parent count'];length=controls['Parent length']
        self.assertEqual(row['owner'],'Parent array');self.assertNotIn(row['parameter']['id'],{p['id'] for p in child['params']})
        state,path=self.worker(dict(action='mutate',operation='custom-index-step',geom=gid,index=row['index'],delta=1),path)
        state,path=self.worker(dict(action='mutate',operation='custom-control-parameter',geom=gid,index=length['index'],id=length['parameter']['id'],value=9),path)
        actual=next(c for c in state['components'] if c['id']==parent);v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        reference=v.AddGeom('BoxGroup');v.SetParmValUpdate(v.FindParm(reference,'NumRow','Design'),2);v.SetParmValUpdate(v.FindParm(reference,'Length','Design'),9)
        for surface in actual['surfaces']:
            i=surface['index'];u,w=v.GetUWTess01(reference,i%v.GetNumMainSurfs(reference))
            expected=[[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(reference,i,[a for a in u for _ in w],[b for _ in u for b in w])]
            self.assertEqual(surface['points'],expected)
        cold,_=self.worker(dict(action='state'),path)
        self.assertEqual({c['id']:c['surfaces'] for c in state['components']},{c['id']:c['surfaces'] for c in cold['components']})
        self.assertEqual(next(c for c in cold['components'] if c['id']==gid)['customExternalControls'],next(c for c in state['components'] if c['id']==gid)['customExternalControls'])

    def test_external_rebinding_rejects_stale_parameter_without_saving(self):
        parent,child,state,path,text=self.fixture();gid=child['id'];row=next(r for r in child['customExternalControls'] if r['parameter']['label']=='Parent count')
        switch=next(p['id'] for p in child['params'] if p['name']=='SelectColumns')
        state,path=self.worker(dict(action='mutate',operation='parameter',id=switch,value=1),path)
        cold,path=self.worker(dict(action='state'),path);child=next(c for c in cold['components'] if c['id']==gid);current=next(r for r in child['customExternalControls'] if r['index']==row['index'])
        self.assertNotEqual(current['parameter']['id'],row['parameter']['id'])
        self.rejected_file_is_unchanged(dict(action='mutate',operation='custom-control-parameter',geom=gid,index=row['index'],id=row['parameter']['id'],value=5),path)
        state,path=self.worker(dict(action='mutate',operation='custom-control-parameter',geom=gid,index=current['index'],id=current['parameter']['id'],value=3),path)
        fields={p['name']:p['value'] for p in next(c for c in state['components'] if c['id']==parent)['params'] if p['rawGroup']=='Design'}
        self.assertEqual((fields['NumRow'],fields['NumCol']),(1,3))

    def test_external_choice_labels_and_output_protection_survive_reopening(self):
        for variant in ('choice','output'):
            parent,child,state,path,text=self.fixture(variant);gid=child['id']
            controls={r['parameter']['label']:r for r in child['customExternalControls']}
            if variant=='choice':
                row=controls['Parent count'];self.assertEqual(row['parameter']['choices'],[[0,'Zero'],[1,'One'],[2,'Two']])
                state,path=self.worker(dict(action='mutate',operation='custom-control-parameter',geom=gid,index=row['index'],id=row['parameter']['id'],value=2),path)
                self.assertEqual(next(p['value'] for p in next(c for c in state['components'] if c['id']==parent)['params'] if p['name']=='NumRow'),2)
            else:
                row=controls['Parent length'];self.assertTrue(row['parameter']['displayReadOnly'])
                self.rejected_file_is_unchanged(dict(action='mutate',operation='custom-control-parameter',geom=gid,index=row['index'],id=row['parameter']['id'],value=8),path)
            cold,_=self.worker(dict(action='state'),path)
            self.assertEqual(next(c for c in cold['components'] if c['id']==gid)['customExternalControls'],next(c for c in state['components'] if c['id']==gid)['customExternalControls'])

if __name__=='__main__':unittest.main()
