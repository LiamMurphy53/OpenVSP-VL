"""Directory-discovered profile paths still use the original native readers."""
import base64,io,os,shutil,unittest,zipfile
from pathlib import Path
import test_native,test_custom_assets
from native_custom_scripts import import_script


class DiscoveredProfiles(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def script(self,airfoil=False):
        shape='XS_FILE_AIRFOIL' if airfoil else 'XS_FILE_FUSE';reader='ReadFileAirfoil' if airfoil else 'ReadFileXSec'
        return '''void Init(){string p=AddParm(PARM_INT_TYPE,"ProfileChoice","Design");SetParmValLimits(p,0,0,1);string s=AddXSecSurf();AppendCustomXSec(s,SHAPE);AppendCustomXSec(s,SHAPE);}
int profileControl;
void InitGui(){AddGui(GDEV_TAB,"Profiles");profileControl=AddGui(GDEV_SLIDER_ADJ_RANGE_INPUT,"Profile choice");}
void UpdateGui(){UpdateGui(profileControl,GetParm(GetCurrCustomGeom(),"ProfileChoice","Design"));}
void UpdateSurf(){filesystem directory;if(!directory.changeCurrentPath("profiles"))return;array<string>@ files=directory.getFiles();files.sortAsc();string filename=directory.getCurrentPath()+"/"+files[GetIntParmVal(GetParm(GetCurrCustomGeom(),"ProfileChoice","Design"))];string s=GetXSecSurf(GetCurrCustomGeom(),0);READER(GetXSec(s,0),filename);READER(GetXSec(s,1),filename);SetCustomXSecLoc(GetXSec(s,1),vec3d(8,0,0));SkinXSecSurf();}
'''.replace('SHAPE',shape).replace('READER',reader)

    def files(self,script,airfoil=False):
        profile='Airfoil\n1 0\n.5 .1\n0 0\n.5 -.1\n1 0\n' if airfoil else test_custom_assets.PROFILE
        alternate=profile.replace('.1','.2') if airfoil else profile.replace('1 0','2 0').replace('-1 0','-2 0')
        return {'part/Main.vsppart':script,'part/profiles/first.dat':profile,'part/profiles/second.dat':alternate}

    def package(self,files):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as archive:
            for name,content in files.items():archive.writestr(name,content)
        return data.getvalue()

    def original(self,files):
        folder=self.path/'original';folder.mkdir()
        for name,content in files.items():
            path=folder/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
        old=os.getcwd();os.chdir(folder/'part')
        try:
            gid=import_script(self.v,folder/'part/Main.vsppart','Original discovered profile');self.v.Update()
            expected={}
            for value in [0,1]:
                self.v.SetParmValUpdate(gid,'ProfileChoice','Design',value);self.v.Update();surfaces=[]
                for i in range(self.v.GetTotalNumSurfs(gid)):
                    u,w=self.v.GetUWTess01(gid,i%self.v.GetNumMainSurfs(gid));surfaces.append([[p.x(),p.y(),p.z()] for p in self.v.CompVecPnt01(gid,i,[a for a in u for _ in w],[b for _ in u for b in w])])
                expected[value]=surfaces
        finally:os.chdir(old)
        shutil.rmtree(folder);return expected

    def check(self,airfoil=False):
        files=self.files(self.script(airfoil),airfoil);expected=self.original(files)
        state,path=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_PACKAGE',name='Discovered profile',content=base64.b64encode(self.package(files)).decode()))
        c=next(c for c in state['components'] if c['name']=='Discovered profile');pid=next(p['id'] for p in c['params'] if p['name']=='ProfileChoice')
        self.assertEqual([s['points'] for s in c['surfaces']],expected[0]);self.assertNotEqual(expected[0],expected[1])
        state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=1),path)
        c=next(c for c in state['components'] if c['name']=='Discovered profile');self.assertEqual([s['points'] for s in c['surfaces']],expected[1])
        shutil.rmtree(path.parent/'.studio-custom-assets',ignore_errors=True)
        cold,_=self.worker(dict(action='state'),path);self.assertEqual(next(item for item in cold['components'] if item['id']==c['id'])['surfaces'],c['surfaces'])

    def test_discovered_body_profile_matches_original_after_switch_and_reopen(self):self.check()
    def test_discovered_airfoil_matches_original_after_switch_and_reopen(self):self.check(True)

    def test_saved_old_resolver_upgrades_preserving_native_geometry_and_read_only_bytes(self):
        from unittest.mock import patch
        from native_custom_assets import stage,save,prepare
        script=self.script()
        script=script.replace('string s=GetXSecSurf(GetCurrCustomGeom(),0);ReadFileXSec','if(GetIntParmVal(GetParm(GetCurrCustomGeom(),"ProfileChoice","Design"))==0)filename="profiles/first.dat";string s=GetXSecSurf(GetCurrCustomGeom(),0);ReadFileXSec')
        files=self.files(script);expected=self.original(files);raw=self.package(files)
        self.v.ClearVSPModel();self.v.ReadVSPFile(str(self.model));folder,entry,_=stage(raw)
        # Recreate the preceding release's generated resolver, where only
        # relative aliases were accepted. Initial choice 0 was valid there.
        with patch('native_custom_assets.discovered_profile_cases',return_value=''):
            gid=import_script(self.v,entry,'Legacy discovered profile',package_root=folder,asset_root=folder)
        save(self.v,gid,raw);self.v.WriteVSPFile(str(self.model),self.v.SET_ALL);before=self.model.read_bytes()
        shutil.rmtree(folder.parent)
        state,path=self.worker(dict(action='state'));c=next(c for c in state['components'] if c['id']==gid)
        self.assertEqual([s['points'] for s in c['surfaces']],expected[0]);self.assertEqual(path.read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)
        pid=next(p['id'] for p in c['params'] if p['name']=='ProfileChoice')
        state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=1),path);c=next(c for c in state['components'] if c['id']==gid)
        self.assertEqual([s['points'] for s in c['surfaces']],expected[1]);self.assertIn(b'studioProfileRootPath',path.read_bytes())
        cold,last=self.worker(dict(action='state'),path);self.assertEqual(next(c for c in cold['components'] if c['id']==gid)['surfaces'],c['surfaces'])
        self.assertEqual(prepare(self.v,last),last)

    def test_unknown_or_outside_absolute_profiles_do_not_gain_package_access(self):
        for path in ['directory.getCurrentPath()+"/missing.dat"','filesystem().getCurrentPath()+"/profiles/first.dat"']:
            with self.subTest(path=path):
                script=self.script().replace('string s=GetXSecSurf(GetCurrCustomGeom(),0);ReadFileXSec','filename='+path+';string s=GetXSecSurf(GetCurrCustomGeom(),0);ReadFileXSec')
                before=self.model.read_bytes();existing=set(self.path.glob('*/aircraft.vsp3'))
                with self.assertRaisesRegex(ValueError,'Missing or ambiguous custom package file'):
                    self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_PACKAGE',name='Unresolved discovered profile',content=base64.b64encode(self.package(self.files(script))).decode()))
                candidates=set(self.path.glob('*/aircraft.vsp3'))-existing
                self.assertEqual(len(candidates),1);self.assertEqual(next(iter(candidates)).read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)

    def test_discovered_design_files_keep_native_application_and_parameter_validation(self):
        for reader,writer,suffix in [('ReadApplyDESFile','WriteDESFile','des'),('ReadApplyXDDMFile','WriteXDDMFile','xddm')]:
            with self.subTest(reader=reader):
                v=self.v;v.ClearVSPModel();parent=v.AddGeom('POD');pid=v.FindParm(parent,'Length','Design');v.AddDesignVar(pid,v.XDDM_VAR)
                v.SetParmValUpdate(pid,18);data=self.path/('dimensions.'+suffix);getattr(v,writer)(str(data));payload=data.read_text();data.unlink();expected=[]
                for i in range(v.GetTotalNumSurfs(parent)):
                    u,w=v.GetUWTess01(parent,i%v.GetNumMainSurfs(parent));expected.append([[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(parent,i,[a for a in u for _ in w],[b for _ in u for b in w])])
                v.SetParmValUpdate(pid,10);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
                script=test_custom_assets.SCRIPT.replace('AppendCustomXSec(s,XS_FILE_FUSE);}', 'AppendCustomXSec(s,XS_FILE_FUSE);filesystem directory;if(directory.changeCurrentPath("data")){array<string>@ files=directory.getFiles();'+reader+'(directory.getCurrentPath()+"/"+files[0]);}}')
                files={'part/Main.vsppart':script,'part/profile.dat':test_custom_assets.PROFILE,'part/data/dimensions.'+suffix:payload}
                state,path=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_PACKAGE',parent=parent,name='Discovered design',content=base64.b64encode(self.package(files)).decode()))
                self.assertEqual(next(p['value'] for c in state['components'] for p in c['params'] if p['id']==pid),18)
                self.assertEqual([s['points'] for c in state['components'] if c['id']==parent for s in c['surfaces']],expected)
                cold,_=self.worker(dict(action='state'),path);self.assertEqual(next(p['value'] for c in cold['components'] for p in c['params'] if p['id']==pid),18)
                self.assertEqual([s['points'] for c in cold['components'] if c['id']==parent for s in c['surfaces']],expected)
                files['part/data/dimensions.'+suffix]=payload.replace(pid,'NOTAPARM')
                before=self.model.read_bytes()
                with self.assertRaisesRegex(ValueError,'Malformed custom design file or unavailable parameter'):
                    self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_PACKAGE',parent=parent,name='Invalid discovered design',content=base64.b64encode(self.package(files)).decode()))
                self.assertEqual(self.model.read_bytes(),before)


if __name__=='__main__':unittest.main()
