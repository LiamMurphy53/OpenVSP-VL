"""Packaged native advanced-link code survives relocation and cold script reads."""
import base64
import io
import os
from pathlib import Path
import shutil
import sys
import unittest
import zipfile
import test_native
import test_custom_scripts
from native_custom_scripts import import_script
from native_custom_assets import restore

CODE='body_y = body_length * 0.25;\n'

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use native Python 3.11.')
class CustomCodeAssets(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    template=test_custom_scripts.CustomScripts.template
    rejected_file_is_unchanged=test_custom_scripts.CustomScripts.rejected_file_is_unchanged

    def fixture(self):
        v=self.v;v.ClearVSPModel();parent=v.AddGeom('POD');v.SetGeomName(parent,'Linked body')
        source=v.FindParm(parent,'Length','Design');target=v.FindParm(parent,'Y_Rel_Location','XForm')
        v.AddAdvLink('Package equation');index=v.GetLinkIndex('Package equation')
        v.AddAdvLinkInput(index,source,'body_length');v.AddAdvLinkOutput(index,target,'body_y')
        v.SetAdvLinkCode(index,'body_y = 0;');self.assertTrue(v.BuildAdvLinkScript(index));v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return parent,source,target

    def script(self,computed):
        script=self.template()
        prefix='array<string>@ link_names=GetAdvLinkNames();int code_index=-1;for(uint li=0;li<link_names.length();li++){if(link_names[li]=="Package equation")code_index=int(li);}if(code_index>=0){'
        if computed:
            script=script.replace('void Init()\n{','void Init()\n{string option=AddParm(PARM_BOOL_TYPE,"MissingCode","Design");SetParmVal(option,0);')
            prefix+='string filename=GetBoolParmVal(GetParm(GetCurrCustomGeom(),"MissingCode","Design"))?"missing.as":"./equation.as";'
        argument='filename' if computed else '"equation.as"'
        prefix+='ReadAdvLinkCodeFile(GetLinkIndex("Package equation"),'+argument+');BuildAdvLinkScript(code_index);}'
        return script.replace('void UpdateSurf()\n{','void UpdateSurf()\n{'+prefix)

    def package(self,script):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as archive:
            archive.writestr('part/Main.vsppart',script);archive.writestr('part/equation.as',CODE)
        return data.getvalue()

    def verify_case(self,computed):
        parent,source,target=self.fixture();script=self.script(computed);v=self.v
        original=self.path/'original';original.mkdir();entry=original/'Main.vsppart';entry.write_text(script);(original/'equation.as').write_text(CODE)
        old=os.getcwd()
        try:
            os.chdir(original);gid=import_script(v,entry,'Original code reader',parent=parent)
            v.SetParmValUpdate(source,18);v.Update();expected=v.GetParmVal(target)
            self.assertEqual(expected,4.5)
            expected_surfaces=[]
            for i in range(v.GetTotalNumSurfs(parent)):
                u,w=v.GetUWTess01(parent,i%v.GetNumMainSurfs(parent))
                points=[[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(parent,i,[a for a in u for _ in w],[b for _ in u for b in w])]
                expected_surfaces.append(dict(index=i,rows=len(u),cols=len(w),points=points))
        finally:os.chdir(old)
        shutil.rmtree(original)
        state,path=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_PACKAGE',name='Packaged code reader',parent=parent,content=base64.b64encode(self.package(script)).decode()))
        link=next(x for x in state['tools']['advancedLinks'] if x['name']=='Package equation');self.assertEqual(link['code'],CODE)
        state,path=self.worker(dict(action='mutate',operation='parameter',id=source,value=18),path)
        body=next(c for c in state['components'] if c['id']==parent);self.assertEqual(next(p['value'] for p in body['params'] if p['id']==target),expected)
        self.assertEqual(body['surfaces'],expected_surfaces)
        shutil.rmtree(path.parent/'.studio-custom-assets',ignore_errors=True)
        cold,cold_path=self.worker(dict(action='state'),path)
        self.assertEqual({c['id']:c['surfaces'] for c in cold['components']},{c['id']:c['surfaces'] for c in state['components']})
        child=next(c for c in cold['components'] if c['name']=='Packaged code reader')
        width=next(p['id'] for p in child['params'] if p['rawGroup']=='Design' and p['name']=='Width')
        # Replace the serialized link code first. Re-reading the companion
        # must restore it; a previously compiled/saved expression cannot pass.
        restore(cold_path);v.ClearVSPModel();v.ReadVSPFile(str(cold_path));v.Update()
        index=v.GetLinkIndex('Package equation');v.SetAdvLinkCode(index,'body_y = -1;')
        altered=self.path/'altered-link.vsp3';v.WriteVSPFile(str(altered),v.SET_ALL)
        self.assertEqual(v.GetAdvLinkCode(index),'body_y = -1;')
        shutil.rmtree(self.path/'.studio-custom-assets',ignore_errors=True)
        cold,cold_path=self.worker(dict(action='mutate',operation='parameter',id=width,value=9),altered)
        self.assertEqual(next(x for x in cold['tools']['advancedLinks'] if x['name']=='Package equation')['code'],CODE)
        cold,cold_path=self.worker(dict(action='mutate',operation='parameter',id=source,value=20),cold_path)
        self.assertEqual(next(p['value'] for p in next(c for c in cold['components'] if c['id']==parent)['params'] if p['id']==target),5)
        if computed:
            missing=next(p['id'] for p in child['params'] if p['name']=='MissingCode')
            self.rejected_file_is_unchanged(dict(action='mutate',operation='parameter',id=missing,value=1),cold_path)

    def test_literal_code_companion_uses_native_expression_after_source_removal(self):
        self.verify_case(False)

    def test_computed_code_companion_reloads_and_missing_filename_rejects(self):
        self.verify_case(True)

    def test_unavailable_literal_code_files_reject_without_changing_aircraft(self):
        self.fixture()
        for filename in ('missing.as','../outside.as'):
            with self.subTest(filename=filename):
                script=self.script(False).replace('"equation.as"','"'+filename+'"')
                request=dict(action='mutate',operation='geometry-import',format='CUSTOM_PACKAGE',name='Unavailable code reader',content=base64.b64encode(self.package(script)).decode())
                before=self.model.read_bytes();folders=set(self.path.glob('*/aircraft.vsp3'))
                with self.assertRaisesRegex(ValueError,'in-package code file'):self.worker(request)
                self.assertEqual(self.model.read_bytes(),before)
                self.assertTrue(all(p.read_bytes()==before for p in set(self.path.glob('*/aircraft.vsp3'))-folders))
