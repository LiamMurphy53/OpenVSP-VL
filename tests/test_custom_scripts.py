"""Custom component workflows use original scripts, compiler, and geometry."""
import base64
import io
import shutil
import sys
import unittest
import zipfile
import test_native
from vsp_runtime import distribution,load


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class CustomScripts(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def template(self,name='Box'):
        return (distribution()/'CustomScripts'/(name+'.vsppart')).read_text()

    def import_component(self,text,model=None,fmt='CUSTOM_SCRIPT'):
        raw=text.encode() if isinstance(text,str) else text
        state,path=self.worker(dict(action='mutate',operation='geometry-import',format=fmt,
                                    name='Custom test',content=base64.b64encode(raw).decode()),model)
        return state,path,next(c for c in state['components'] if c['name']=='Custom test')

    def fields(self,component):
        return {p['name']:p for p in component['params'] if p['rawGroup']=='Design'}

    def rejected_file_is_unchanged(self,request,model):
        before=model.read_bytes();existing=set(self.path.glob('*/aircraft.vsp3'))
        with self.assertRaises(ValueError):self.worker(request,model)
        candidates=set(self.path.glob('*/aircraft.vsp3'))-existing
        self.assertEqual(len(candidates),1)
        self.assertEqual(next(iter(candidates)).read_bytes(),before)
        self.assertEqual(model.read_bytes(),before)

    def compare_box(self,component,model,length):
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(model));v.Update()
        gid=component['id'];self.assertEqual(v.GetParmVal(v.FindParm(gid,'Length','Design')),length)
        reference=v.AddGeom('Box');v.SetParmValUpdate(v.FindParm(reference,'Length','Design'),length)
        def points(g,i):
            u,w=v.GetUWTess01(g,i%v.GetNumMainSurfs(g))
            return [[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(g,i,[a for a in u for _ in w],[b for _ in u for b in w])]
        self.assertEqual(v.GetTotalNumSurfs(gid),v.GetTotalNumSurfs(reference))
        for surface in component['surfaces']:
            i=surface['index'];self.assertEqual(surface['points'],points(gid,i));self.assertEqual(points(gid,i),points(reference,i))

    def archive(self,entries):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as package:
            for name,text in entries:package.writestr(name,text)
        return data.getvalue()

    def test_nested_package_is_embedded_and_matches_original_geometry(self):
        main=self.template().replace('length, 5.0','length, StudioTestLength()')
        raw=self.archive([('part/Main.vsppart','#include "helpers/shape.as"\n'+main),
                          ('part/helpers/shape.as','#include "dimensions.as"\n'),
                          ('part/helpers/dimensions.as','double StudioTestLength(){return 13.0;}\n')])
        _,path,component=self.import_component(raw,fmt='CUSTOM_PACKAGE')
        shutil.rmtree(path.parent/'component-package')
        self.compare_box(component,path,13)
        state,reopened=self.worker(dict(action='state'),path)
        self.compare_box(next(c for c in state['components'] if c['id']==component['id']),reopened,13)

    def test_dynamic_bindings_and_real_gui_errors_preserve_files(self):
        text=self.template().replace('SquareFlag','CubeSwitch')
        _,path,c=self.import_component(text);gid=c['id'];fields=self.fields(c)
        self.assertFalse(fields['Width'].get('displayReadOnly',False))
        state,path=self.worker(dict(action='mutate',operation='parameter',id=fields['CubeSwitch']['id'],value=1),path)
        c=next(c for c in state['components'] if c['id']==gid);fields=self.fields(c)
        self.assertTrue(fields['Width']['displayReadOnly']);self.assertTrue(fields['Height']['displayReadOnly'])
        self.rejected_file_is_unchanged(dict(action='mutate',operation='parameter',id=fields['Width']['id'],value=8),path)
        bad=text.replace('void UpdateGui()\n{','void UpdateGui()\n{\n GetParm(GetCurrCustomGeom(), "MissingSetting", "Design");')
        self.assertNotEqual(bad,text)
        self.rejected_file_is_unchanged(dict(action='mutate',operation='geometry-import',format='CUSTOM_SCRIPT',
                                            content=base64.b64encode(bad.encode()).decode()),path)

    def test_parameterless_events_are_once_per_click_and_survive_reopening(self):
        text=self.template().replace('int LengthSlider;','int TestAction;\nint LengthSlider;')
        text=text.replace('void InitGui()\n{','void InitGui()\n{\n TestAction=AddGui(GDEV_TRIGGER_BUTTON,"Double length");')
        text=text.replace('void UpdateGui()\n{','void UpdateGui()\n{\n if(CheckClearTriggerEvent(TestAction)){string g=GetCurrCustomGeom();string p=GetParm(g,"Length","Design");SetParmVal(p,2*GetParmVal(p));}')
        _,path,c=self.import_component(text);gid=c['id']
        self.assertEqual(c['customActions'],[dict(index=0,label='Double length')])
        for length in (10,20):
            state,path=self.worker(dict(action='mutate',operation='custom-trigger',geom=gid,index=0),path)
            self.compare_box(next(c for c in state['components'] if c['id']==gid),path,length)
        self.rejected_file_is_unchanged(dict(action='mutate',operation='custom-trigger',geom=gid,index=500),path)

    def test_script_defined_choices_and_parameter_trigger_match_native_array(self):
        text=self.template('BoxGroup').replace('BoxLayout','ArrangementMethod').replace('LayoutTrigger','PresetApply')
        text=text.replace('"Layouts:"','"Arrangement:"').replace('"Go", "PresetApply"','"Build array", "PresetApply"')
        _,path,c=self.import_component(text);gid=c['id'];fields=self.fields(c)
        self.assertEqual(fields['ArrangementMethod']['choices'],[[0,'2 by 2'],[1,'2 by 4'],[2,'4 by 2']])
        self.assertEqual(fields['ArrangementMethod']['label'],'Arrangement')
        self.assertTrue(fields['PresetApply']['trigger'])
        self.assertEqual(fields['PresetApply']['triggerLabel'],'Build array')
        _,path=self.worker(dict(action='mutate',operation='parameter',id=fields['ArrangementMethod']['id'],value=1),path)
        state,path=self.worker(dict(action='mutate',operation='parameter',id=fields['PresetApply']['id'],value=1),path)
        c=next(c for c in state['components'] if c['id']==gid)
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        self.assertEqual(v.GetParmVal(v.FindParm(gid,'PresetApply','Design')),0)
        reference=v.AddGeom('BoxGroup')
        v.SetParmValUpdate(v.FindParm(reference,'NumRow','Design'),2)
        v.SetParmValUpdate(v.FindParm(reference,'NumCol','Design'),4)
        self.assertEqual(v.GetTotalNumSurfs(gid),8)
        for surface in c['surfaces']:
            i=surface['index'];u,w=v.GetUWTess01(reference,i%v.GetNumMainSurfs(reference))
            expected=[[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(reference,i,[a for a in u for _ in w],[b for _ in u for b in w])]
            self.assertEqual(surface['points'],expected)

    def test_script_controls_in_custom_groups_remain_editable_after_reload(self):
        text=self.template().replace('"Design"','"Dimensions"')
        _,path,c=self.import_component(text);gid=c['id']
        fields={p['name']:p for p in c['params'] if p['rawGroup']=='Dimensions'}
        for name in ('Length','Width','Height','SquareFlag'):self.assertTrue(fields[name]['customControl'])
        state,saved=self.worker(dict(action='mutate',operation='parameter',id=fields['Length']['id'],value=11),path)
        c=next(c for c in state['components'] if c['id']==gid)
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(saved));v.Update()
        reference=v.AddGeom('Box');v.SetParmValUpdate(reference,'Length','Design',11);v.Update()
        for surface in c['surfaces']:
            i=surface['index'];u,w=v.GetUWTess01(reference,i%v.GetNumMainSurfs(reference))
            expected=[[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(reference,i,[a for a in u for _ in w],[b for _ in u for b in w])]
            self.assertEqual(surface['points'],expected)
        reopened,_=self.worker(dict(action='state'),saved)
        fields={p['name']:p for p in next(c for c in reopened['components'] if c['id']==gid)['params'] if p['rawGroup']=='Dimensions'}
        self.assertTrue(fields['Length']['customControl']);self.assertEqual(fields['Length']['value'],11)
        state,_=self.worker(dict(action='mutate',operation='parameter',id=fields['SquareFlag']['id'],value=1),saved)
        fields={p['name']:p for p in next(c for c in state['components'] if c['id']==gid)['params'] if p['rawGroup']=='Dimensions'}
        for name in ('Width','Height'):
            self.assertTrue(fields[name]['customControl']);self.assertTrue(fields[name]['displayReadOnly']);self.assertEqual(fields[name]['dimension'],'length')

    def test_empty_native_surface_rejects_without_saving(self):
        text='void Init(){string s=AddXSecSurf();AppendCustomXSec(s,XS_ELLIPSE);} void InitGui(){} void UpdateGui(){} void UpdateSurf(){SkinXSecSurf();}'
        before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'did not produce a valid native surface'):
            self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_SCRIPT',content=base64.b64encode(text.encode()).decode()))
        self.assertEqual(next(self.path.glob('*/aircraft.vsp3')).read_bytes(),before)
        _,_,empty=self.import_component('void Init(){} void InitGui(){} void UpdateGui(){} void UpdateSurf(){SkinXSecSurf();}')
        self.assertEqual(empty['surfaces'],[])

    def test_bad_package_graphs_reject_before_writing(self):
        main=self.template()
        cases=[ [('Main.vsppart',main),('../escape.as','bad')],
                [('Main.vsppart','#include "missing.as"\n'+main)],
                [('Main.vsppart','#include "helper.as"\n'+main),('helper.as','#include "Main.vsppart"\n')],
                [('Main.vsppart',main),('Other.vsppart',main)] ]
        for entries in cases:
            with self.subTest(entries=[n for n,_ in entries]):
                self.rejected_file_is_unchanged(dict(action='mutate',operation='geometry-import',format='CUSTOM_PACKAGE',
                                                    content=base64.b64encode(self.archive(entries)).decode()),self.model)

    def test_native_counter_and_index_selector_bindings_preserve_complete_geometry(self):
        from native_custom_scripts import gui_definitions
        for device in ('GDEV_COUNTER','GDEV_INDEX_SELECTOR'):
            with self.subTest(device=device):
                text=self.template().replace('GDEV_SLIDER_ADJ_RANGE_INPUT, "Length"','%s, "Length"'%device)
                self.assertNotEqual(text,self.template())
                state,path,c=self.import_component(text);gid=c['id'];field=self.fields(c)['Length']
                self.assertTrue(field['customControl']);self.assertFalse(field.get('displayReadOnly',False))
                value=7 if device=='GDEV_INDEX_SELECTOR' else 7.5
                state,path=self.worker(dict(action='mutate',operation='parameter',id=field['id'],value=value),path)
                c=next(c for c in state['components'] if c['id']==gid);self.compare_box(c,path,value)
                definitions=gui_definitions(self.v,gid)
                self.assertTrue(any(d['type']==getattr(self.v,device) and d['label']=='Length' for d in definitions))
                reopened,saved=self.worker(dict(action='state'),path);cold=next(c for c in reopened['components'] if c['id']==gid)
                self.assertEqual(self.fields(cold)['Length']['id'],field['id']);self.compare_box(cold,saved,value)
                self.rejected_file_is_unchanged(dict(action='mutate',operation='parameter',id=field['id'],value=field['max']+1),path)

    def test_parameter_button_and_native_link_drive_custom_geometry(self):
        text=self.template().replace('void InitGui()\n{','void InitGui()\n{\n AddGui(GDEV_PARM_BUTTON,"Length","Length","Design");')
        self.assertNotEqual(text,self.template());_,path,c=self.import_component(text);gid=c['id'];source=self.fields(c)['Length']
        self.assertTrue(source['customParmButton']);self.assertEqual(source['id'],self.fields(c)['Length']['id'])
        state,path=self.worker(dict(action='mutate',operation='link-add',source=source['id'],target=self.fields(c)['Width']['id'],scale=.5,offset=1),path)
        state,path=self.worker(dict(action='mutate',operation='parameter',id=source['id'],value=12),path)
        actual=next(c for c in state['components'] if c['id']==gid);self.assertEqual(self.fields(actual)['Width']['value'],7)
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();reference=v.AddGeom('Box')
        v.SetParmValUpdate(v.FindParm(reference,'Length','Design'),12);v.SetParmValUpdate(v.FindParm(reference,'Width','Design'),7)
        for surface in actual['surfaces']:
            i=surface['index'];u,w=v.GetUWTess01(reference,i%v.GetNumMainSurfs(reference))
            expected=[[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(reference,i,[a for a in u for _ in w],[b for _ in u for b in w])]
            self.assertEqual(surface['points'],expected)
        cold,_=self.worker(dict(action='state'),path);reopened=next(c for c in cold['components'] if c['id']==gid)
        self.assertEqual(reopened['surfaces'],actual['surfaces']);self.assertTrue(self.fields(reopened)['Length']['customParmButton'])
        self.assertTrue(any(l['source']==source['id'] and l['target']==self.fields(c)['Width']['id'] for l in cold['tools']['links']))

    def test_index_steps_clamp_and_match_original_native_array_geometry(self):
        text=self.template('BoxGroup').replace('GDEV_COUNTER, "Num Row"','GDEV_INDEX_SELECTOR, "Num Row"')
        self.assertNotEqual(text,self.template('BoxGroup'));_,path,c=self.import_component(text);gid=c['id'];index=self.fields(c)['NumRow']['customIndexSelector']
        for delta,rows in [(1,2),(10,10),(-1,9),(-10,1)]:
            state,path=self.worker(dict(action='mutate',operation='custom-index-step',geom=gid,index=index,delta=delta),path)
            c=next(c for c in state['components'] if c['id']==gid);self.assertEqual(self.fields(c)['NumRow']['value'],rows)
            v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();reference=v.AddGeom('BoxGroup');v.SetParmValUpdate(v.FindParm(reference,'NumRow','Design'),rows)
            self.assertEqual(v.GetTotalNumSurfs(gid),v.GetTotalNumSurfs(reference))
            for surface in c['surfaces']:
                i=surface['index'];u,w=v.GetUWTess01(reference,i%v.GetNumMainSurfs(reference))
                expected=[[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(reference,i,[a for a in u for _ in w],[b for _ in u for b in w])]
                self.assertEqual(surface['points'],expected)
            cold,_=self.worker(dict(action='state'),path);reopened=next(c for c in cold['components'] if c['id']==gid)
            self.assertEqual(reopened['surfaces'],c['surfaces']);self.assertEqual(self.fields(reopened)['NumRow']['customIndexSelector'],index)
        for extra in [dict(delta=True),dict(delta=1.5),dict(delta=2),dict(index=False),dict(index=500)]:
            request=dict(action='mutate',operation='custom-index-step',geom=gid,index=index,delta=1);request.update(extra);self.rejected_file_is_unchanged(request,path)

    def test_disconnected_index_selector_does_not_edit_saved_parameter(self):
        text=self.template('BoxGroup').replace('int LengthSlider;','int TestSelector;\nint LengthSlider;')
        text=text.replace('AddGui( GDEV_COUNTER, "Num Row"','TestSelector=AddGui( GDEV_INDEX_SELECTOR, "Num Row"')
        text=text.replace('void UpdateGui()\n{','void UpdateGui()\n{\n UpdateGui(TestSelector,GetParm(GetCurrCustomGeom(),"","Design"));')
        self.assertNotEqual(text,self.template('BoxGroup'));_,path,c=self.import_component(text)
        from native_custom_scripts import gui_definitions
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();index=next(d['index'] for d in gui_definitions(v,c['id']) if d['type']==v.GDEV_INDEX_SELECTOR)
        self.rejected_file_is_unchanged(dict(action='mutate',operation='custom-index-step',geom=c['id'],index=index,delta=1),path)
