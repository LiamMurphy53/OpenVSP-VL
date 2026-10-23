"""Packaged native directory discovery survives relocation and cold loading."""
import io,os,shutil,unittest,zipfile
import test_custom_file_reads,test_native
from native_custom_scripts import import_script


class CustomFilesystem(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    template=test_custom_file_reads.CustomFileReads.template
    script=test_custom_file_reads.CustomFileReads.script
    imported=test_custom_file_reads.CustomFileReads.imported
    length=test_custom_file_reads.CustomFileReads.length
    check=test_custom_file_reads.CustomFileReads.check

    def files(self,script):
        return {'part/Main.vsppart':script,'part/data/one.txt':'12\n','part/data/nested/two.txt':'17\n','part/empty/':None}

    def package(self,script):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as archive:
            for name,content in self.files(script).items():archive.writestr(name,content or '')
        return data.getvalue()

    def original(self,script):
        v=self.v;folder=self.path/'original';folder.mkdir()
        for name,content in self.files(script).items():
            target=folder/name
            if content is None:target.mkdir(parents=True,exist_ok=True)
            else:target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content)
        old=os.getcwd();os.chdir(folder/'part')
        try:
            gid=import_script(v,folder/'part/Main.vsppart','Original directory reader');v.Update();self.original_gid=gid
            length=v.GetParmVal(gid,'Length','Design');surfaces=[]
            for i in range(v.GetTotalNumSurfs(gid)):
                u,w=v.GetUWTess01(gid,i%v.GetNumMainSurfs(gid));surfaces.append([[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(gid,i,[a for a in u for _ in w],[b for _ in u for b in w])])
        finally:os.chdir(old)
        shutil.rmtree(folder);return length,surfaces

    def directory_script(self,receiver='directory',prefix='filesystem directory;',extra='',path='"data"'):
        return self.script(prefix+'double length=5;if('+receiver+'.changeCurrentPath('+path+')){length=0;array<string>@ names='+receiver+'.getFiles();for(uint i=0;i<names.length();i++){file reader;if(reader.open('+receiver+'.getCurrentPath()+"/"+names[i],"r")==0){length+=parseFloat(reader.readLine());reader.close();}}}SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);',extra)

    def test_native_directory_listing_reads_embedded_data(self):
        self.check(self.directory_script(),12)

    def test_trailing_slash_and_package_root_paths_find_the_same_native_directory(self):
        self.check(self.directory_script(path='"./data/"'),12)
        script=self.directory_script(path='"part/data"')
        original,surfaces=self.original(self.directory_script())
        _,_,c=self.imported(script);self.assertEqual(self.length(c),original);self.assertEqual([s['points'] for s in c['surfaces']],surfaces)

    def test_default_directory_discovery_uses_entry_folder_before_package_aliases(self):
        original_files=self.files
        self.files=lambda script:{**original_files(script),'data/wrong.txt':'99\n'}
        original,surfaces=self.original(self.directory_script());self.assertEqual(original,12)
        _,path,c=self.imported(self.directory_script());self.assertEqual(self.length(c),original)
        self.assertEqual([s['points'] for s in c['surfaces']],surfaces)
        state,_=self.worker(dict(action='state'),path);self.assertEqual(self.length(next(item for item in state['components'] if item['id']==c['id'])),original)

    def test_nested_and_empty_directories_keep_native_navigation_and_status(self):
        prefix='filesystem directory;double length=5;if(directory.changeCurrentPath("./data")){length=0;array<string>@ dirs=directory.getDirs();if(dirs.find("nested")<0)length=100;file reader;if(reader.open(directory.getCurrentPath()+"/one.txt","r")==0){length+=parseFloat(reader.readLine());reader.close();}if(directory.changeCurrentPath("nested")){if(reader.open(directory.getCurrentPath()+"/two.txt","r")==0){length+=parseFloat(reader.readLine());reader.close();}string before=directory.getCurrentPath();if(directory.changeCurrentPath("data") || directory.getCurrentPath()!=before)length=200;directory.changeCurrentPath("../..");if(!directory.changeCurrentPath("empty") || directory.getFiles().length()!=0)length=300;before=directory.getCurrentPath();if(directory.changeCurrentPath("missing") || directory.getCurrentPath()!=before)length=400;}}SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);'
        self.check(self.script(prefix),29)

    def test_existing_native_directory_and_written_files_take_precedence(self):
        prefix='filesystem directory;directory.makeDir("data");file writer;writer.open("data/one.txt","w");writer.writeString("23\\n");writer.close();'
        self.check(self.directory_script(prefix=prefix),23)

    def test_computed_directory_tracks_native_parameter_changes(self):
        script=self.directory_script(path='GetIntParmVal(GetParm(GetCurrCustomGeom(),"DataChoice","Design"))==0?"data":GetIntParmVal(GetParm(GetCurrCustomGeom(),"DataChoice","Design"))==1?"data/nested":"optional"')
        script=script.replace('void Init()\n{','void Init()\n{string choice=AddParm(PARM_INT_TYPE,"DataChoice","Design");SetParmVal(choice,0);')
        path,c=self.check(script,12);pid=next(p['id'] for p in c['params'] if p['name']=='DataChoice')
        for value,expected in [(1,17),(2,5),(0,12)]:
            state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value),path)
            c=next(item for item in state['components'] if item['id']==c['id']);self.assertEqual(self.length(c),expected)

    def test_typed_members_factories_arrays_and_parameters_use_original_filesystem(self):
        for prefix,receiver,extra in [
            ('auto directory=filesystem();','directory',''),
            ('filesystem first,directory;','directory',''),
            ('array<filesystem@> directories(2);@directories[1]=filesystem();','directories[1]',''),
            ('Data::Leaf holder;','holder.directory','\nnamespace Data{class Base{filesystem directory;}class Leaf:Base{}}\n'),
            ('auto holder=Data::Holder();','holder.getDirectory()','\nnamespace Data{class Holder{filesystem directory;filesystem@ getDirectory(){return directory;}}}\n'),
            ('','Data::GetDirectory()','\nnamespace Data{filesystem directory;filesystem@ GetDirectory(){return directory;}}\n')
        ]:
            with self.subTest(receiver=receiver):self.check(self.directory_script(receiver,prefix,extra),12)
        extra='\nbool Navigate(filesystem@ target,const string &in path){return target.changeCurrentPath(path);}\n'
        self.check(self.directory_script(extra=extra).replace('directory.changeCurrentPath("data")','Navigate(@directory,"data")'),12)

    def test_native_receiver_and_path_expressions_evaluate_once_in_original_order(self):
        extra='\nint calls=0;filesystem directory;filesystem@ GetDirectory(){calls=calls*10+1;return directory;}string DataPath(){calls=calls*10+2;return "data";}\n'
        script=self.directory_script(prefix='calls=0;',extra=extra).replace('directory.changeCurrentPath("data")','GetDirectory().changeCurrentPath(DataPath())').replace('"Design"),length);','"Design"),length+calls/100.0);')
        _,c=self.check(script,None);self.assertIn(self.length(c),(12.12,12.21))

    def test_nonfilesystem_methods_keep_their_original_arguments(self):
        extra='\nnamespace Other{class filesystem{bool changeCurrentPath(const string &in path){return path=="data";}}class Holder{filesystem directory;}filesystem@ Make(){return filesystem();}}\n'
        script=self.directory_script(extra=extra).replace('"Design"),length);','"Design"),length);Other::Holder holder;if(!holder.directory.changeCurrentPath("data") || !Other::Make().changeCurrentPath("data"))SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),2);')
        self.check(script,12)

    def test_legacy_embedded_directory_reader_upgrades_without_rewriting_read_only_files(self):
        from native_custom_assets import save,prepare
        script=self.directory_script();expected,surfaces=self.original(script)
        gid=self.original_gid
        save(self.v,gid,self.package(script));self.v.WriteVSPFile(str(self.model),self.v.SET_ALL);before=self.model.read_bytes()
        state,path=self.worker(dict(action='state'));c=next(c for c in state['components'] if c['id']==gid)
        self.assertEqual(self.length(c),expected);self.assertEqual([s['points'] for s in c['surfaces']],surfaces)
        self.assertEqual(self.model.read_bytes(),before);self.assertEqual(path.read_bytes(),before)
        width=next(p['id'] for p in c['params'] if p['name']=='Width' and p['rawGroup']=='Design')
        state,path=self.worker(dict(action='mutate',operation='parameter',id=width,value=9),path)
        saved=next(c for c in state['components'] if c['id']==gid);self.assertEqual(self.length(saved),expected)
        shutil.rmtree(path.parent/'.studio-custom-assets',ignore_errors=True)
        state,last=self.worker(dict(action='state'),path);self.assertEqual(next(c for c in state['components'] if c['id']==gid)['surfaces'],saved['surfaces'])
        self.assertEqual(prepare(self.v,last),last,'Generated directory helpers must not be wrapped again.')


if __name__=='__main__':unittest.main()
