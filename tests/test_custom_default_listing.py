"""Default native folder discovery matches direct scripts and survives packaging."""
import base64,os,shutil,unittest
import test_custom_file_reads,test_custom_filesystem,test_native
from native_custom_scripts import import_script


class CustomDefaultListing(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    template=test_custom_file_reads.CustomFileReads.template
    script=test_custom_file_reads.CustomFileReads.script
    imported=test_custom_file_reads.CustomFileReads.imported
    length=test_custom_file_reads.CustomFileReads.length
    check=test_custom_file_reads.CustomFileReads.check
    package=test_custom_filesystem.CustomFilesystem.package
    original=test_custom_filesystem.CustomFilesystem.original

    def files(self,script):
        return {'part/Main.vsppart':script,'part/length.txt':'12\n',
                'part/other.txt':'17\n','part/data/nested.txt':'19\n','part/empty/':None}

    def test_default_listing_finds_bundled_entry_files_without_worker_files(self):
        self.check(self.script('filesystem directory;array<string>@ names=directory.getFiles();double length=5;if(names.length()==3 && names.find("Main.vsppart")>=0 && names.find("length.txt")>=0 && names.find("other.txt")>=0)length=12;SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);'),12)

    def test_default_listing_reads_bare_and_current_path_filenames_without_changing_directory(self):
        prefix='filesystem directory;string before=directory.getCurrentPath();array<string>@ names=directory.getFiles();double length=0;for(uint i=0;i<names.length();i++){if(names[i]!="length.txt" && names[i]!="other.txt")continue;file reader;string path=names[i]=="length.txt"?names[i]:directory.getCurrentPath()+"/"+names[i];if(reader.open(path,"r")==0){length+=parseFloat(reader.readLine());reader.close();}}if(directory.getCurrentPath()!=before)length=5;SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);'
        self.check(self.script(prefix),29)

    def test_default_directory_discovery_and_native_navigation(self):
        prefix='filesystem directory;string before=directory.getCurrentPath();array<string>@ names=directory.getDirs();double length=5;if(names.length()==2 && names.find("data")>=0 && names.find("empty")>=0 && directory.getCurrentPath()==before && directory.changeCurrentPath("data")){array<string>@ files=directory.getFiles();if(files.length()==1){file reader;if(reader.open(directory.getCurrentPath()+"/"+files[0],"r")==0){length=parseFloat(reader.readLine());reader.close();}}}SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);'
        self.check(self.script(prefix),19)

    def test_native_write_list_and_read_preserve_overrides_and_new_files(self):
        prefix='filesystem directory;directory.makeDir("created-dir");file writer;writer.open("length.txt","w");writer.writeString("23\\n");writer.close();writer.open(directory.getCurrentPath()+"/created.txt","w");writer.writeString("31\\n");writer.close();array<string>@ names=directory.getFiles();array<string>@ dirs=directory.getDirs();double length=0;if(names.length()==4 && names.find("length.txt")>=0 && names.find("created.txt")>=0 && dirs.length()==3 && dirs.find("created-dir")>=0){file reader;for(uint i=0;i<names.length();i++){if(names[i]!="length.txt" && names[i]!="created.txt")continue;if(reader.open(directory.getCurrentPath()+"/"+names[i],"r")==0){length+=parseFloat(reader.readLine());reader.close();}}}else length=5;SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);'
        self.check(self.script(prefix),54)

    def test_packaged_worker_basename_is_readable_and_explicit_writes_take_precedence(self):
        original_files=self.files
        self.files=lambda script:{**original_files(script),'part/request.json':'12\n'}
        prefix='filesystem directory;WRITEarray<string>@ names=directory.getFiles();double length=5;if(names.length()==4 && names.find("request.json")>=0){file reader;if(reader.open(PATH,"r")==0){length=parseFloat(reader.readLine());reader.close();}}SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);'
        for path in ['"request.json"','directory.getCurrentPath()+"/request.json"']:
            for write,expected in [('',12),('file writer;writer.open("request.json","w");writer.writeString("23\\n");writer.close();',23)]:
                with self.subTest(path=path,written=bool(write)):
                    self.check(self.script(prefix.replace('WRITE',write).replace('PATH',path)),expected)

    def test_included_reader_uses_entry_working_directory(self):
        original_files=self.files
        extra='double ReadEntry(){filesystem directory;array<string>@ names=directory.getFiles();if(names.find("length.txt")<0)return 5;file reader;if(reader.open(directory.getCurrentPath()+"/length.txt","r")!=0)return 6;double value=parseFloat(reader.readLine());reader.close();return value;}\n'
        self.files=lambda script:{**original_files(script),'part/helpers/read.as':extra,'part/helpers/length.txt':'99\n'}
        script='#include "helpers/read.as"\n'+self.script('SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),ReadEntry());')
        self.check(script,12)

    def test_main_calls_native_factories_declared_in_an_include(self):
        original_files=self.files
        extra='filesystem directory;file@ reader=file();filesystem@ NativeDirectory(){return directory;}file@ NativeReader(){return reader;}\n'
        self.files=lambda script:{**original_files(script),'part/helpers/factories.as':extra}
        prefix='array<string>@ names=NativeDirectory().getFiles();double length=5;int index=names.find("length.txt");if(index>=0 && NativeReader().open(NativeDirectory().getCurrentPath()+"/"+names[index],"r")==0){length=parseFloat(NativeReader().readLine());NativeReader().close();}SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);'
        self.check('#include "helpers/factories.as"\n'+self.script(prefix),12)

    def test_native_receivers_evaluate_once_and_shadow_methods_are_unchanged(self):
        extra='\nint calls=0;filesystem directory;filesystem@ GetDirectory(){calls++;return directory;}namespace Other{class filesystem{array<string>@ getFiles(){array<string> names={"sentinel"};return names;}array<string>@ getDirs(){array<string> names={"sentinel-dir"};return names;}}}\n'
        prefix='calls=0;array<string>@ names=GetDirectory().getFiles();Other::filesystem other;double length=5;if(names.find("length.txt")>=0 && calls==1 && other.getFiles().length()==1 && other.getFiles()[0]=="sentinel" && other.getDirs()[0]=="sentinel-dir")length=12;SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);'
        self.check(self.script(prefix,extra),12)

    def test_legacy_default_reader_upgrades_and_cold_load_is_idempotent(self):
        from native_custom_assets import save,prepare
        script=self.script('filesystem directory;array<string>@ names=directory.getFiles();double length=5;if(names.find("length.txt")>=0){file reader;if(reader.open(directory.getCurrentPath()+"/length.txt","r")==0){length=parseFloat(reader.readLine());reader.close();}}SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);')
        expected,surfaces=self.original(script);gid=self.original_gid
        save(self.v,gid,self.package(script));self.v.WriteVSPFile(str(self.model),self.v.SET_ALL);before=self.model.read_bytes()
        state,path=self.worker(dict(action='state'));c=next(c for c in state['components'] if c['id']==gid)
        self.assertEqual(self.length(c),expected);self.assertEqual([s['points'] for s in c['surfaces']],surfaces)
        self.assertEqual(self.model.read_bytes(),before);self.assertEqual(path.read_bytes(),before)
        width=next(p['id'] for p in c['params'] if p['name']=='Width' and p['rawGroup']=='Design')
        state,path=self.worker(dict(action='mutate',operation='parameter',id=width,value=9),path)
        saved=next(c for c in state['components'] if c['id']==gid);self.assertEqual(self.length(saved),expected)
        shutil.rmtree(path.parent/'.studio-custom-assets',ignore_errors=True)
        state,last=self.worker(dict(action='state'),path);self.assertEqual(next(c for c in state['components'] if c['id']==gid)['surfaces'],saved['surfaces'])
        self.assertEqual(prepare(self.v,last),last,'New generated listing helpers must not be wrapped again.')

    def test_legacy_generated_file_helper_accepts_default_discovered_absolute_names(self):
        from native_custom_assets import stage,save,prepare,choice_cases
        prefix='filesystem directory;array<string>@ names=directory.getFiles();int choice=GetIntParmVal(GetParm(GetCurrCustomGeom(),"DataChoice","Design"));string path=choice==0?"length.txt":directory.getCurrentPath()+"/length.txt";double length=5;if(choice==0 || names.find("length.txt")>=0){file reader;if(reader.open(path,"r")==0){length=parseFloat(reader.readLine());reader.close();}}SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);'
        script=self.script(prefix).replace('void Init()\n{','void Init()\n{string choice=AddParm(PARM_INT_TYPE,"DataChoice","Design");SetParmVal(choice,0);')
        expected,surfaces=self.original(script);raw=self.package(script)
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(self.model));folder,entry,_=stage(raw)
        helper='StudioPackageProfile_0123456789abcdef'
        # Exact original generated file receiver shape from before listing
        # support; the saved source's original per-source alias table matters.
        generated='\nstring '+helper+'_filePath(const string &in filename){string normalized=filename;while(normalized.length()>=2 && normalized.substr(0,2)=="./")normalized=normalized.substr(2);'+choice_cases(entry,folder,folder)+'return filename;}\n'
        generated+='\nint '+helper+'_open(file@ target,const string &in filename,const string &in mode){int status=target.open(filename,mode);if(status!=0 && (mode=="r" || mode=="rb")){string path='+helper+'_filePath(filename);if(path!=filename)return target.open(path,mode);}return status;}\n'
        legacy=self.path/'legacy.vsppart';legacy.write_text(script.replace('reader.open(path,"r")',helper+'_open(@reader,path,"r")')+generated)
        gid=import_script(v,legacy,'Legacy generated reader');save(v,gid,raw);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        shutil.rmtree(folder.parent)
        state,path=self.worker(dict(action='state'));c=next(c for c in state['components'] if c['id']==gid)
        self.assertEqual(self.length(c),expected);self.assertEqual(path.read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)
        pid=next(p['id'] for p in c['params'] if p['name']=='DataChoice')
        state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=1),path);c=next(c for c in state['components'] if c['id']==gid)
        self.assertEqual(self.length(c),expected);self.assertEqual([s['points'] for s in c['surfaces']],surfaces)
        cold,last=self.worker(dict(action='state'),path);self.assertEqual(next(c for c in cold['components'] if c['id']==gid)['surfaces'],c['surfaces'])
        self.assertEqual(prepare(v,last),last)

    def test_multiple_packages_do_not_list_each_others_companions(self):
        original_files=self.files
        prefix='filesystem directory;array<string>@ names=directory.getFiles();double length=5;if(names.find("TOKEN")>=0 && names.find("OTHER")<0)length=EXPECTED;SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);'
        path=self.model;ids=[]
        for filename,other,expected in [('first-only.txt','second-only.txt',12),('second-only.txt','first-only.txt',17)]:
            script=self.script(prefix.replace('TOKEN',filename).replace('OTHER',other).replace('EXPECTED',str(expected)))
            self.files=lambda script,filename=filename:{**original_files(script),'part/'+filename:'present\n'}
            original,surfaces=self.original(script);self.assertEqual(original,expected)
            state,path=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_PACKAGE',name=filename,content=base64.b64encode(self.package(script)).decode()),path)
            component=next(c for c in state['components'] if c['name']==filename);ids.append((component['id'],expected))
            self.assertEqual([s['points'] for s in component['surfaces']],surfaces)
            for gid,value in ids:self.assertEqual(self.length(next(c for c in state['components'] if c['id']==gid)),value)
        shutil.rmtree(path.parent/'.studio-custom-assets',ignore_errors=True)
        cold,_=self.worker(dict(action='state'),path)
        for gid,value in ids:self.assertEqual(self.length(next(c for c in cold['components'] if c['id']==gid)),value)

    def test_direct_restore_and_prepare_initialize_listing_before_native_load(self):
        from native_custom_assets import restore,prepare
        from native_worker import errors
        script=self.script('filesystem directory;array<string>@ names=directory.getFiles();double length=5;if(names.length()==3 && names.find("Main.vsppart")>=0 && names.find("length.txt")>=0 && names.find("other.txt")>=0){file reader;if(reader.open(directory.getCurrentPath()+"/length.txt","r")==0){length=parseFloat(reader.readLine());reader.close();}}SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);')
        expected,surfaces=self.original(script);self.assertEqual(expected,12)
        _,saved,component=self.imported(script);gid=component['id'];v=self.v
        for operation in ('restore','prepare'):
            with self.subTest(operation=operation):
                folder=self.path/('direct-'+operation);folder.mkdir()
                model=folder/'aircraft.vsp3';shutil.copy2(saved,model);before=model.read_bytes()
                # Native load paths outside native_worker.run also have their
                # own surrounding files. They must not enter script listings.
                for name in ('request.json','engine.log','.engine-owner.json','unrelated.txt'):(folder/name).write_text('worker data\n')
                previous=os.getcwd();v.ClearVSPModel();os.chdir(folder)
                try:
                    if operation=='restore':restore(model);load_path=model
                    else:load_path=prepare(v,model)
                    v.ReadVSPFile(str(load_path));v.Update();errors(v)
                    self.assertEqual(v.GetParmVal(gid,'Length','Design'),expected)
                    actual=[]
                    for index in range(v.GetTotalNumSurfs(gid)):
                        u,w=v.GetUWTess01(gid,index%v.GetNumMainSurfs(gid))
                        actual.append([[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(gid,index,[a for a in u for _ in w],[b for _ in u for b in w])])
                    self.assertEqual(actual,surfaces);self.assertEqual(model.read_bytes(),before)
                finally:os.chdir(previous)


if __name__=='__main__':unittest.main()
