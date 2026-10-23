"""Packaged filesystem sequences preserve the installed native engine's behavior."""
import unittest
import test_custom_default_listing,test_native


class CustomFilesystemSequences(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    template=test_custom_default_listing.CustomDefaultListing.template
    script=test_custom_default_listing.CustomDefaultListing.script
    package=test_custom_default_listing.CustomDefaultListing.package
    files=test_custom_default_listing.CustomDefaultListing.files
    original=test_custom_default_listing.CustomDefaultListing.original
    imported=test_custom_default_listing.CustomDefaultListing.imported

    def compare(self,body,expected):
        # Run each operation once during native initialization. Repeating an
        # append/delete in UpdateSurf would obscure its original return value.
        declarations=''.join('double '+name+'=0;' for name in expected)
        record=''.join('string diagnostic'+name+'=AddParm(PARM_DOUBLE_TYPE,"'+name+'","Diagnostics");SetParmValLimits(diagnostic'+name+','+name+',-1000000,1000000);' for name in expected)
        script=self.script('SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),12);')
        script=script.replace('void Init()\n{','void Init()\n{'+declarations+body+record)
        _,surfaces=self.original(script)
        original={name:self.v.GetParmVal(self.original_gid,name,'Diagnostics') for name in expected}
        self.assertEqual(original,expected,'The installed engine must establish the expected native behavior.')
        _,_,component=self.imported(script)
        actual={p['name']:p['value'] for p in component['params'] if p['rawGroup']=='Diagnostics'}
        self.assertEqual(actual,original)
        self.assertEqual([surface['points'] for surface in component['surfaces']],surfaces)

    def test_append_preserves_the_existing_bundled_file(self):
        self.compare('filesystem directory;array<string>@ names=directory.getFiles();file writer;OpenStatus=writer.open("length.txt","a");if(OpenStatus==0){writer.writeString("MORE");writer.close();}Size=directory.getSize("length.txt");ReadStatus=writer.open("length.txt","r");if(ReadStatus==0){Content=writer.readString(7)=="12\\nMORE"?1:0;writer.close();}',
                     dict(OpenStatus=0,Size=7,ReadStatus=0,Content=1))

    def test_nested_write_uses_the_existing_bundled_directory(self):
        self.compare('filesystem directory;array<string>@ names=directory.getDirs();file writer;OpenStatus=writer.open("data/new.txt","w");if(OpenStatus==0){writer.writeString("NEW");writer.close();}Size=directory.getSize("data/new.txt");Moved=directory.changeCurrentPath("data")?1:0;Found=directory.getFiles().find("new.txt")>=0?1:0;Companion=directory.getFiles().find("nested.txt")>=0?1:0;',
                     dict(OpenStatus=0,Size=3,Moved=1,Found=1,Companion=1))

    def test_dot_navigation_preserves_the_native_path_and_file_view(self):
        self.compare('filesystem directory;string before=directory.getCurrentPath();Moved=directory.changeCurrentPath(".")?1:0;Path=directory.getCurrentPath()==before+"/."?1:0;Found=directory.getFiles().find("length.txt")>=0?1:0;Size=directory.getSize("length.txt");',
                     dict(Moved=1,Path=1,Found=1,Size=3))

    def test_parent_directory_lists_only_the_complete_package_contents(self):
        original_files=self.files
        self.files=lambda script:{**original_files(script),'sibling/root.txt':'21\n','root-file.txt':'31\n'}
        self.compare('filesystem directory;Moved=directory.changeCurrentPath("..")?1:0;array<string>@ directories=directory.getDirs();array<string>@ files=directory.getFiles();DirectoryCount=directories.length();FileCount=files.length();Entry=directories.find("part")>=0?1:0;Sibling=directories.find("sibling")>=0?1:0;RootFile=files.find("root-file.txt")>=0?1:0;',
                     dict(Moved=1,DirectoryCount=2,FileCount=1,Entry=1,Sibling=1,RootFile=1))

    def test_failed_write_over_a_directory_closes_the_previous_file_handle(self):
        self.compare('filesystem directory;array<string>@ names=directory.getDirs();file reader;Opened=reader.open("length.txt","r");Rejected=reader.open("data","w");Size=reader.getSize();Closed=reader.close();IsDirectory=directory.isDir("data")?1:0;IsFile=directory.getFiles().find("data")>=0?1:0;',
                     dict(Opened=0,Rejected=-1,Size=-1,Closed=-1,IsDirectory=1,IsFile=0))

    def test_const_filesystem_handles_keep_native_read_only_methods(self):
        self.compare('filesystem original;const filesystem@ directory=original;Found=directory.getFiles().find("length.txt")>=0?1:0;Size=directory.getSize("length.txt");IsDirectory=directory.isDir("data")?1:0;Directories=directory.getDirs().length();',
                     dict(Found=1,Size=3,IsDirectory=1,Directories=2))

    def test_native_copy_delete_move_and_remove_share_the_same_file_view(self):
        self.compare('filesystem directory;array<string>@ names=directory.getFiles();Copied=directory.copyFile("length.txt","created.txt");CopySize=directory.getSize("created.txt");Deleted=directory.deleteFile("length.txt");OriginalVisible=directory.getFiles().find("length.txt")>=0?1:0;Moved=directory.move("created.txt","renamed.txt");OldVisible=directory.getFiles().find("created.txt")>=0?1:0;NewSize=directory.getSize("renamed.txt");Removed=directory.removeDir("empty");DirectoryVisible=directory.getDirs().find("empty")>=0?1:0;',
                     dict(Copied=0,CopySize=3,Deleted=0,OriginalVisible=0,Moved=0,OldVisible=0,NewSize=3,Removed=0,DirectoryVisible=0))


if __name__=='__main__':unittest.main()
