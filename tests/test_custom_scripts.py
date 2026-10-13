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
