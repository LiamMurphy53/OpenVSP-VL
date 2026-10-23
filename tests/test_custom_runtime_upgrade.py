"""Saved first-generation filesystem helpers acquire current native semantics."""
import json,re,shutil,unittest
from pathlib import Path
import test_custom_default_listing


class CustomRuntimeUpgrade(unittest.TestCase):
    base=test_custom_default_listing.CustomDefaultListing
    setUpClass=classmethod(base.setUpClass.__func__)
    setUp=base.setUp
    tearDown=base.tearDown
    worker=base.worker
    template=base.template
    script=base.script
    files=base.files
    package=base.package
    original=base.original
    length=base.length

    def legacy(self,script):
        from native_custom_assets import stage,save,choice_cases,listing_context
        from native_custom_file_reads import replacements
        from native_custom_scripts import import_script
        raw=self.package(script);folder,entry,_=stage(raw)
        owner='StudioPackageProfile_0123456789abcdef'
        tokens=[m for m in re.finditer(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|[A-Za-z_]\w*|[^\s]',script,re.S) if not m[0].startswith(('//','/*'))]
        old_prefixes=tuple(owner+'_'+method+'(' for method in ('open','changeCurrentPath','getFiles','getDirs'))
        for start,end,replacement in sorted(replacements(script,tokens,owner),reverse=True):
            if replacement.startswith(old_prefixes):script=script[:start]+replacement+script[end:]
        context=listing_context(entry,folder,folder)
        generated=(Path(__file__).parent/'fixtures/custom_filesystem_v1.as').read_text()
        values={'OWNER':owner,'RUNTIME_FILE_CASES':context['file_cases'],'RUNTIME_DIRECTORY_CASES':context['directory_cases'],
                'FILE_CASES':choice_cases(entry,folder,folder),'DIRECTORY_CASES':choice_cases(entry,folder,folder,directories=True),
                'ROOT_LITERAL':json.dumps(context['root'])}
        for key,value in values.items():generated=generated.replace(key,value)
        legacy=self.path/'legacy.vsppart';legacy.write_text(script+generated)
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(self.model))
        gid=import_script(v,legacy,'Saved first-generation runtime');save(v,gid,raw)
        v.WriteVSPFile(str(self.model),v.SET_ALL)
        return gid

    def test_saved_navigation_helpers_upgrade_without_unwrapped_filesystem_calls(self):
        from native_custom_assets import prepare
        original_files=self.files
        self.files=lambda script:{**original_files(script),'sibling/root.txt':'21\n'}
        script=self.script('filesystem directory;array<string>@ initial=directory.getFiles();double length=5;if(initial.find("length.txt")>=0 && directory.changeCurrentPath("..")){array<string>@ dirs=directory.getDirs();if(dirs.find("sibling")>=0)length=21;}SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);')
        expected,surfaces=self.original(script);self.assertEqual(expected,21)
        gid=self.legacy(script);before=self.model.read_bytes()
        state,path=self.worker(dict(action='state'))
        component=next(c for c in state['components'] if c['id']==gid)
        self.assertEqual(self.length(component),expected)
        self.assertEqual([s['points'] for s in component['surfaces']],surfaces)
        self.assertEqual(path.read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)
        width=next(p['id'] for p in component['params'] if p['name']=='Width' and p['rawGroup']=='Design')
        state,path=self.worker(dict(action='mutate',operation='parameter',id=width,value=9),path)
        saved=next(c for c in state['components'] if c['id']==gid)
        self.assertEqual(self.length(saved),expected)
        shutil.rmtree(path.parent/'.studio-custom-assets',ignore_errors=True)
        cold,last=self.worker(dict(action='state'),path)
        self.assertEqual(next(c for c in cold['components'] if c['id']==gid)['surfaces'],saved['surfaces'])
        self.assertEqual(prepare(self.v,last),last,'Current helpers must not be regenerated on every load.')

    def test_only_complete_unchanged_previous_generated_groups_are_migrated(self):
        from native_custom_assets import generated_functions
        from native_custom_runtime_upgrade import edits
        source=(Path(__file__).parent/'fixtures/custom_filesystem_v1.as').read_text()
        owner='StudioPackageProfile_0123456789abcdef'
        for key,value in {'OWNER':owner,'RUNTIME_FILE_CASES':'','RUNTIME_DIRECTORY_CASES':'','FILE_CASES':'','DIRECTORY_CASES':'','ROOT_LITERAL':'"package"'}.items():source=source.replace(key,value)
        def functions(text):
            tokens=[m for m in re.finditer(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|[A-Za-z_]\w*|[^\s]',text,re.S) if not m[0].startswith(('//','/*'))]
            return generated_functions(text,tokens)
        context=dict(root='package',file_cases='',directory_cases='')
        changes,owners=edits(functions(source),context)
        self.assertEqual(owners,{owner});self.assertEqual(len(changes),13)
        self.assertEqual(edits(functions(source.replace('return false;','return true;',1)),context),([],set()))
        self.assertEqual(edits(functions(source.replace('const string &in filename,const string &in mode','const string &in mode,const string &in filename')),context),([],set()))
        self.assertEqual(edits(functions(source.replace('const string &in mode)','const string &in mode="r")')),context),([],set()))
        trim='while(normalized.length()>1 && normalized.substr(normalized.length()-1)=="/")normalized=normalized.substr(0,normalized.length()-1);'
        moved_case='if(normalized=="data/")return "custom-directory";\n'
        self.assertEqual(edits(functions(source.replace(trim,moved_case+trim,1)),context),([],set()))
        self.assertEqual(edits(functions(source)[:-1],context),([],set()))


if __name__=='__main__':unittest.main()
