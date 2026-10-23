"""Native filesystem metadata, navigation and creation agree with bundled reads."""
import shutil,unittest
import test_custom_default_listing,test_native


class CustomFilesystemMetadata(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    template=test_custom_default_listing.CustomDefaultListing.template
    script=test_custom_default_listing.CustomDefaultListing.script
    package=test_custom_default_listing.CustomDefaultListing.package
    imported=test_custom_default_listing.CustomDefaultListing.imported
    original=test_custom_default_listing.CustomDefaultListing.original

    def files(self,script):
        return {**test_custom_default_listing.CustomDefaultListing.files(self,script),
                'sibling/root.txt':'21\n','part/request.json':'12\n'}

    def check(self,prefix,expected=None):
        names=('Observed','Second','Status')
        suffix=''.join('SetParmVal(GetParm(GetCurrCustomGeom(),"'+name+'","Diagnostics"),'+name.lower()+');' for name in names)
        # Metadata drives a real original custom surface as well as separately
        # inspectable diagnostics. Negative native failure statuses stay valid.
        suffix+='SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),10+observed+second+status);'
        init=''.join('string diagnostic'+name+'=AddParm(PARM_DOUBLE_TYPE,"'+name+'","Diagnostics");SetParmValLimits(diagnostic'+name+',0,-1000000,1000000);' for name in names)
        script=self.script(prefix+suffix).replace('void Init()\n{','void Init()\n{'+init)
        _,surfaces=self.original(script)
        original={name:self.v.GetParmVal(self.original_gid,name,'Diagnostics') for name in names}
        if expected is not None:self.assertEqual(original,dict(zip(names,expected)))
        _,path,component=self.imported(script)
        observed=lambda c:{p['name']:p['value'] for p in c['params'] if p['rawGroup']=='Diagnostics'}
        self.assertEqual(observed(component),original)
        self.assertEqual([s['points'] for s in component['surfaces']],surfaces)
        shutil.rmtree(path.parent/'.studio-custom-assets',ignore_errors=True)
        cold,_=self.worker(dict(action='state'),path)
        reopened=next(c for c in cold['components'] if c['id']==component['id'])
        self.assertEqual(observed(reopened),original);self.assertEqual(reopened['surfaces'],component['surfaces'])

    def test_default_file_metadata_agrees_with_discovery(self):
        for filename in ['"length.txt"','"./length.txt"','d.getCurrentPath()+"/length.txt"']:
            with self.subTest(filename=filename):
                self.check('filesystem d;array<string>@ files=d.getFiles();double observed=d.getSize('+filename+');double second=files.find("length.txt")>=0?1:0;double status=d.isDir('+filename+')?1:0;', (3,1,0))

    def test_default_directory_metadata_agrees_with_discovery(self):
        for filename in ['"data"','"./data/"','d.getCurrentPath()+"/data"']:
            with self.subTest(filename=filename):
                self.check('filesystem d;array<string>@ dirs=d.getDirs();double observed=d.isDir('+filename+')?1:0;double second=dirs.find("data")>=0?1:0;double status=d.isDir("length.txt")?1:0;', (1,1,0))

    def test_metadata_inside_explicit_folder_and_parent_queries(self):
        for filename in ['"nested.txt"','d.getCurrentPath()+"/nested.txt"']:
            with self.subTest(filename=filename):
                self.check('filesystem d;bool moved=d.changeCurrentPath("data");array<string>@ files=d.getFiles();double observed=d.getSize('+filename+');double second=moved && files.find("nested.txt")>=0?1:0;double status=d.isDir("../empty")?1:0;', (3,1,1))

    def test_parent_navigation_finds_siblings_then_returns_to_same_entry_path(self):
        self.check('filesystem d;string before=d.getCurrentPath();array<string>@ initial=d.getFiles();bool moved=d.changeCurrentPath("..");array<string>@ dirs=d.getDirs();double observed=moved && dirs.find("sibling")>=0 && dirs.find("part")>=0?1:0;double status=0;file reader;if(reader.open(d.getCurrentPath()+"/sibling/root.txt","r")==0){status=parseFloat(reader.readLine());reader.close();}bool returned=d.changeCurrentPath("part");array<string>@ files=d.getFiles();double second=returned && files.length()==initial.length() && d.getSize("length.txt")==3 && d.changeCurrentPath(before) && d.getCurrentPath()==before?1:0;', (1,1,21))

    def test_native_file_writes_cannot_replace_a_packaged_directory(self):
        for filename in ['"data"','d.getCurrentPath()+"/data"']:
            for mode in ['w','a']:
                with self.subTest(filename=filename,mode=mode):
                    self.check('filesystem d;file writer;double status=writer.open('+filename+',"'+mode+'");if(status==0){writer.writeString("created");writer.close();}array<string>@ files=d.getFiles();array<string>@ dirs=d.getDirs();double observed=files.find("data")>=0?1:0;double second=dirs.find("data")>=0 && d.isDir("data")?1:0;', (0,1,-1))

    def test_native_directory_creation_cannot_replace_a_packaged_file(self):
        for filename in ['"length.txt"','d.getCurrentPath()+"/length.txt"']:
            with self.subTest(filename=filename):
                self.check('filesystem d;double status=d.makeDir('+filename+');array<string>@ files=d.getFiles();array<string>@ dirs=d.getDirs();double observed=files.find("length.txt")>=0 && d.getSize("length.txt")==3?1:0;double second=dirs.find("length.txt")>=0 || d.isDir("length.txt")?1:0;', (1,0,-1))

    def test_worker_basename_metadata_uses_companion_until_a_native_write(self):
        for filename in ['"request.json"','d.getCurrentPath()+"/request.json"']:
            for write,size in [('',3),('file writer;writer.open("request.json","w");writer.writeString("12345");writer.close();',5)]:
                with self.subTest(filename=filename,written=bool(write)):
                    self.check('filesystem d;'+write+'array<string>@ files=d.getFiles();double observed=d.getSize('+filename+');double second=files.find("request.json")>=0?1:0;double status=d.isDir('+filename+')?1:0;', (size,1,0))

    def test_native_created_files_and_directories_have_consistent_metadata(self):
        self.check('filesystem d;int made=0;if(!d.isDir("runtime"))made=d.makeDir("runtime");file writer;int opened=writer.open("runtime/value.txt","w");if(opened==0){writer.writeString("12345");writer.close();}array<string>@ dirs=d.getDirs();double observed=dirs.find("runtime")>=0 && d.isDir("runtime")?1:0;double second=d.getSize("runtime/value.txt");bool moved=d.changeCurrentPath("runtime");array<string>@ files=d.getFiles();double status=made==0 && opened==0 && moved && files.find("value.txt")>=0 && d.getSize("value.txt")==5 && !d.isDir("value.txt")?1:0;', (1,5,1))

    def test_metadata_only_script_does_not_require_a_listing_call(self):
        self.check('filesystem d;double observed=d.getSize("length.txt");double second=d.isDir("data")?1:0;double status=d.getSize(d.getCurrentPath()+"/request.json");', (3,1,3))

    def test_navigation_only_script_does_not_require_a_listing_call(self):
        self.check('filesystem d;string before=d.getCurrentPath();bool up=d.changeCurrentPath("..");bool sibling=d.changeCurrentPath("sibling");bool back=d.changeCurrentPath("../part");double observed=up?1:0;double second=sibling?1:0;double status=back && d.changeCurrentPath(before) && d.getCurrentPath()==before?1:0;', (1,1,1))


if __name__=='__main__':unittest.main()
