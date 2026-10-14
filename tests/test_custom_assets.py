"""Packaged native profile files survive job/source relocation."""
import base64
import io
import os
import shutil
import sys
import unittest
import zipfile
import test_native
from native_custom_scripts import import_script
from native_custom_assets import restore

SCRIPT='''void Init(){string s=AddXSecSurf();AppendCustomXSec(s,XS_FILE_FUSE);AppendCustomXSec(s,XS_FILE_FUSE);}
void InitGui(){}
void UpdateGui(){}
void UpdateSurf(){string s=GetXSecSurf(GetCurrCustomGeom(),0);ReadFileXSec(GetXSec(s,0),"profile.dat");ReadFileXSec(GetXSec(s,1),"profile.dat");SetCustomXSecLoc(GetXSec(s,1),vec3d(8,0,0));SkinXSecSurf();}
'''
PROFILE='OPENVSP_XSEC_FILE_V1\n1 0\n0 -1\n-1 0\n0 1\n1 0\n'


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class CustomAssets(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def package(self,script=SCRIPT):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as archive:
            archive.writestr('part/Main.vsppart',script);archive.writestr('part/profile.dat',PROFILE)
        return data.getvalue()

    def test_bor_companion_readers_survive_source_removal_and_cold_load(self):
        airfoil='Independent airfoil\n1 0\n.5 .1\n0 0\n.5 -.1\n1 0\n'
        for reader,shape,profile,computed in [(r,s,p,c) for r,s,p in [('ReadBORFileXSec',self.v.XS_FILE_FUSE,PROFILE),('ReadBORFileAirfoil',self.v.XS_FILE_AIRFOIL,airfoil)] for c in (False,True)]:
            with self.subTest(reader=reader,computed=computed):
                v=self.v;v.ClearVSPModel();parent=v.AddGeom('BODYOFREVOLUTION');v.ChangeBORXSecShape(parent,shape);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
                script='''void Init(){string s=AddXSecSurf();AppendCustomXSec(s,XS_POINT);AppendCustomXSec(s,XS_CIRCLE);AppendCustomXSec(s,XS_POINT);}
void InitGui(){} void UpdateGui(){}
void UpdateSurf(){string parent=GetGeomParent(GetCurrCustomGeom());if(parent!="NONE" && parent!="")READER(parent,"profile.dat");string s=GetXSecSurf(GetCurrCustomGeom(),0);SetCustomXSecLoc(GetXSec(s,1),vec3d(1,0,0));SetCustomXSecLoc(GetXSec(s,2),vec3d(2,0,0));SkinXSecSurf();}'''.replace('READER',reader)
                if computed:script=script.replace('void UpdateSurf(){','void UpdateSurf(){string filename=\"./profile.dat\";').replace('parent,\"profile.dat\"','parent,filename')
                # Original compiler and reader, with no package relocation.
                source=self.path/'bor-reader.vsppart';source.write_text(script);data=self.path/'profile.dat';data.write_text(profile)
                import_script(v,source,'Original BOR reader',parent=parent);v.Update()
                expected=[[p.x(),p.y(),p.z()] for p in (v.ComputeBORXSecPnt(parent,i/100) for i in range(101))]
                source.unlink();data.unlink()
                raw=io.BytesIO()
                with zipfile.ZipFile(raw,'w') as archive:
                    archive.writestr('part/Main.vsppart',script);archive.writestr('part/profile.dat',profile)
                state,saved=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_PACKAGE',name='BOR reader',parent=parent,content=base64.b64encode(raw.getvalue()).decode()))
                bor=next(b for b in state['tools']['bodiesOfRevolution'] if b['id']==parent)
                self.assertEqual(bor['profile'],expected)
                shutil.rmtree(saved.parent/'component-package');shutil.rmtree(saved.parent/'.studio-custom-assets')
                cold,_=self.worker(dict(action='state'),saved)
                self.assertEqual(next(b for b in cold['tools']['bodiesOfRevolution'] if b['id']==parent)['profile'],expected)
                self.assertEqual({c['id']:c['surfaces'] for c in cold['components']},{c['id']:c['surfaces'] for c in state['components']})

    def test_profile_package_reopens_without_original_files(self):
        # Direct original compiler/reader reference with the file in native cwd.
        script=SCRIPT.replace('AppendCustomXSec(s,XS_FILE_FUSE);AppendCustomXSec(s,XS_FILE_FUSE);','AppendCustomXSec(s,XS_POINT);AppendCustomXSec(s,XS_FILE_FUSE);AppendCustomXSec(s,XS_FILE_FUSE);AppendCustomXSec(s,XS_POINT);').replace('ReadFileXSec(GetXSec(s,0)','ReadFileXSec(GetXSec(s,2)').replace('SetCustomXSecLoc(GetXSec(s,1),vec3d(8,0,0));','SetCustomXSecLoc(GetXSec(s,2),vec3d(8,0,0));SetCustomXSecLoc(GetXSec(s,3),vec3d(8,0,0));')
        v=self.v;source=self.path/'direct.vsppart';source.write_text(script);(self.path/'profile.dat').write_text(PROFILE)
        direct=import_script(v,source,'DirectProfileReference');v.Update()
        expected=[]
        for i in range(v.GetTotalNumSurfs(direct)):
            u,w=v.GetUWTess01(direct,i%v.GetNumMainSurfs(direct))
            points=[[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(direct,i,[a for a in u for _ in w],[b for _ in u for b in w])]
            expected.append(dict(index=i,rows=len(u),cols=len(w),points=points))
        source.unlink();(self.path/'profile.dat').unlink()
        state,saved=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_PACKAGE',name='File body',content=base64.b64encode(self.package(script)).decode()))
        c=next(c for c in state['components'] if c['name']=='File body')
        self.assertEqual(c['surfaces'],expected)
        self.assertFalse(any(a['name']=='Studio.CustomAssets' for a in state['tools']['attributes']))
        shutil.rmtree(saved.parent/'component-package');shutil.rmtree(saved.parent/'.studio-custom-assets')
        reopened,path=self.worker(dict(action='state'),saved)
        self.assertEqual(next(c for c in reopened['components'] if c['name']=='File body')['surfaces'],expected)
        self.assertTrue((path.parent/'.studio-custom-assets').is_dir())
        restore(path);v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        self.assertEqual(v.GetXSecShape(v.GetXSec(v.GetXSecSurf(c['id'],0),1)),v.XS_FILE_FUSE)

    def test_computed_profile_switch_matches_native_points_after_reopen(self):
        script=SCRIPT.replace('void Init(){','void Init(){string p=AddParm(PARM_BOOL_TYPE,"AlternateProfile","Design");SetParmVal(p,0);')
        script=script.replace('void UpdateSurf(){','void UpdateSurf(){string filename=GetParmVal(GetCurrCustomGeom(),"AlternateProfile","Design")>0?"alternate.dat":"profile.dat";')
        script=script.replace('"profile.dat");','filename);')
        alternate=PROFILE.replace('1 0','2 0').replace('-1 0','-2 0')
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,'w') as archive:
            archive.writestr('part/Main.vsppart',script);archive.writestr('part/profile.dat',PROFILE);archive.writestr('part/alternate.dat',alternate)
        state,path=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_PACKAGE',name='Switching profile',content=base64.b64encode(raw.getvalue()).decode()))
        c=next(c for c in state['components'] if c['name']=='Switching profile');gid=c['id']
        pid=next(p['id'] for p in c['params'] if p['name']=='AlternateProfile')
        shutil.rmtree(path.parent/'component-package');shutil.rmtree(path.parent/'.studio-custom-assets')
        state,saved=self.worker(dict(action='mutate',operation='parameter',id=pid,value=1),path)
        c=next(c for c in state['components'] if c['id']==gid)
        # Direct original compiler/reader with the computed filename unchanged.
        (self.path/'profile.dat').write_text(PROFILE);(self.path/'alternate.dat').write_text(alternate)
        source=self.path/'switch.vsppart';source.write_text(script)
        v=self.v;reference=import_script(v,source,'OriginalComputedProfile')
        v.SetParmValUpdate(reference,'AlternateProfile','Design',1);v.Update()
        for surface in c['surfaces']:
            i=surface['index'];u,w=v.GetUWTess01(reference,i%v.GetNumMainSurfs(reference))
            points=[[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(reference,i,[a for a in u for _ in w],[b for _ in u for b in w])]
            self.assertEqual(surface['points'],points)
        (self.path/'profile.dat').unlink();(self.path/'alternate.dat').unlink();source.unlink()
        reopened,_=self.worker(dict(action='state'),saved)
        self.assertEqual(next(c for c in reopened['components'] if c['id']==gid)['surfaces'],c['surfaces'])

    def test_helper_selected_airfoil_files_match_original_after_reopen(self):
        airfoil="Independent airfoil\n1 0\n.5 .1\n0 0\n.5 -.1\n1 0\n"
        alternate=airfoil.replace('.1','.2')
        main=SCRIPT.replace('XS_FILE_FUSE','XS_FILE_AIRFOIL')
        main=main.replace('void Init(){','void Init(){string p=AddParm(PARM_BOOL_TYPE,"AlternateProfile","Design");SetParmVal(p,0);')
        main=main.replace('ReadFileXSec(GetXSec(s,0),"profile.dat");ReadFileXSec(GetXSec(s,1),"profile.dat");','LoadProfiles(s,GetParmVal(GetCurrCustomGeom(),"AlternateProfile","Design")>0?"alternate.dat":"profile.dat");')
        helper='void LoadProfiles(const string &in s,const string &in filename){ReadFileAirfoil(GetXSec(s,0),"././../profiles/"+filename);ReadFileAirfoil(GetXSec(s,1),"././../profiles/"+filename);}'
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,'w') as archive:
            archive.writestr('part/Main.vsppart','#include "helpers/read.as"\n'+main)
            archive.writestr('part/helpers/read.as',helper)
            archive.writestr('part/profiles/profile.dat',airfoil);archive.writestr('part/profiles/alternate.dat',alternate)
        state,path=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_PACKAGE',name='Helper airfoil',content=base64.b64encode(raw.getvalue()).decode()))
        c=next(c for c in state['components'] if c['name']=='Helper airfoil');gid=c['id']
        pid=next(p['id'] for p in c['params'] if p['name']=='AlternateProfile')
        shutil.rmtree(path.parent/'component-package');shutil.rmtree(path.parent/'.studio-custom-assets')
        state,saved=self.worker(dict(action='mutate',operation='parameter',id=pid,value=1),path)
        c=next(c for c in state['components'] if c['id']==gid)
        profiles=self.path/'profiles';profiles.mkdir();(profiles/'profile.dat').write_text(airfoil);(profiles/'alternate.dat').write_text(alternate)
        direct=self.path/'helpers';direct.mkdir();source=direct/'direct.vsppart';source.write_text(helper+'\n'+main)
        previous=os.getcwd()
        try:
            os.chdir(direct);v=self.v;reference=import_script(v,source,'OriginalHelperAirfoil')
            v.SetParmValUpdate(reference,'AlternateProfile','Design',1);v.Update()
            for surface in c['surfaces']:
                i=surface['index'];u,w=v.GetUWTess01(reference,i%v.GetNumMainSurfs(reference))
                points=[[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(reference,i,[a for a in u for _ in w],[b for _ in u for b in w])]
                self.assertEqual(surface['points'],points)
        finally:os.chdir(previous)
        shutil.rmtree(profiles);shutil.rmtree(direct)
        reopened,_=self.worker(dict(action='state'),saved)
        self.assertEqual(next(c for c in reopened['components'] if c['id']==gid)['surfaces'],c['surfaces'])

    def test_unknown_computed_filename_rejects_before_save(self):
        script=SCRIPT.replace('void UpdateSurf(){','void UpdateSurf(){string filename="../outside.dat";').replace('"profile.dat");','filename);')
        before=self.model.read_bytes()
        with self.assertRaises(ValueError):
            self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_PACKAGE',content=base64.b64encode(self.package(script)).decode()))
        self.assertEqual(next(self.path.glob('*/aircraft.vsp3')).read_bytes(),before)

    def test_unsafe_section_order_is_rejected_without_saving(self):
        unsafe=PROFILE.replace('0 -1','0 TEMP').replace('0 1','0 -1').replace('0 TEMP','0 1')
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,'w') as archive:
            archive.writestr('Main.vsppart',SCRIPT);archive.writestr('profile.dat',unsafe)
        before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'point order'):
            self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_PACKAGE',content=base64.b64encode(raw.getvalue()).decode()))
        self.assertEqual(next(self.path.glob('*/aircraft.vsp3')).read_bytes(),before)

    def test_missing_profile_rejects_without_saving(self):
        before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'in-package profile'):
            self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_PACKAGE',content=base64.b64encode(self.package(SCRIPT.replace('profile.dat','missing.dat'))).decode()))
        self.assertEqual(next(self.path.glob('*/aircraft.vsp3')).read_bytes(),before)


if __name__=='__main__':unittest.main()
