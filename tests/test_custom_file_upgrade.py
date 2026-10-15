"""Older embedded custom code is upgraded only in an isolated native-load copy."""
import base64,os,shutil,unittest
from pathlib import Path
import test_custom_file_reads,test_native
from native_custom_scripts import import_script
from native_custom_assets import save

class CustomFileUpgrade(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    template=test_custom_file_reads.CustomFileReads.template
    script=test_custom_file_reads.CustomFileReads.script
    package=test_custom_file_reads.CustomFileReads.package
    length=test_custom_file_reads.CustomFileReads.length
    def legacy(self,compound=False,generated=False,check_filename=False):
        script=self.script(('auto reader=file();' if compound else 'file reader;')+'double length=5;if(reader.open("length.txt","r")==0){length=parseFloat(reader.readLine());reader.close();}SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);')
        if check_filename:script=script.replace('SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);','if(GetVSPFileName().findFirst("studio-custom-readable")>=0)length=2;SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);')
        if generated:script='int StudioPackageProfile_0123456789abcdef_open(file@ target,const string &in name,const string &in mode){return target.open(name,mode); }\n'+script
        original=self.path/'original';original.mkdir();(original/'Main.vsppart').write_text(script);(original/'length.txt').write_text('12\n');old=os.getcwd();os.chdir(original)
        try:
            gid=import_script(self.v,original/'Main.vsppart','Legacy data reader');self.v.Update();save(self.v,gid,self.package(script));self.v.WriteVSPFile(str(self.model),self.v.SET_ALL)
            expected=[]
            for i in range(self.v.GetTotalNumSurfs(gid)):
                u,w=self.v.GetUWTess01(gid,i%self.v.GetNumMainSurfs(gid));expected.append([[p.x(),p.y(),p.z()] for p in self.v.CompVecPnt01(gid,i,[a for a in u for _ in w],[b for _ in u for b in w])])
        finally:os.chdir(old)
        shutil.rmtree(original);return gid,expected

    def test_legacy_plain_and_compound_code_load_correctly_without_rewriting_original(self):
        for compound in [False,True]:
            with self.subTest(compound=compound):
                # Each fixture starts with a clean native model and no staged data.
                self.v.ClearVSPModel();self.gid=self.v.AddGeom('WING');self.v.Update();self.v.WriteVSPFile(str(self.model),self.v.SET_ALL)
                gid,expected=self.legacy(compound);before=self.model.read_bytes()
                state,path=self.worker(dict(action='state'));c=next(c for c in state['components'] if c['id']==gid)
                self.assertEqual(self.length(c),12);self.assertEqual([s['points'] for s in c['surfaces']],expected)
                self.assertEqual(self.model.read_bytes(),before);self.assertEqual(path.read_bytes(),before)
                self.assertFalse(list((path.parent/'.studio-custom-assets').glob('.studio-custom-readable-*.vsp3')))
                width=next(p['id'] for p in c['params'] if p['name']=='Width' and p['rawGroup']=='Design')
                changed,saved=self.worker(dict(action='mutate',operation='parameter',id=width,value=9),path)
                self.assertEqual(self.length(next(c for c in changed['components'] if c['id']==gid)),12)
                self.assertIn(b'StudioPackageUpgrade_',saved.read_bytes())
                cold,last=self.worker(dict(action='state'),saved);self.assertEqual(next(c for c in cold['components'] if c['id']==gid)['surfaces'],next(c for c in changed['components'] if c['id']==gid)['surfaces'])
                from native_custom_assets import prepare
                self.assertEqual(prepare(self.v,last),last,'The saved upgrade must be idempotent.')

    def test_existing_generated_file_helpers_are_not_wrapped_recursively(self):
        gid,expected=self.legacy(generated=True);before=self.model.read_bytes()
        result,path=self.worker(dict(action='state'));c=next(c for c in result['components'] if c['id']==gid)
        self.assertEqual(self.length(c),12);self.assertEqual([s['points'] for s in c['surfaces']],expected);self.assertEqual(path.read_bytes(),before)

    def test_ambiguous_package_metadata_rejects_without_changing_aircraft(self):
        import copy,xml.etree.ElementTree as ET
        self.legacy();tree=ET.parse(self.model)
        for geom in tree.iter('Geom'):
            collection=geom.find('ParmContainer/AttributeCollection')
            if collection is None:continue
            record=next((a for a in collection.findall('Attribute') if a.get('Name')=='Studio.CustomAssets'),None)
            if record is not None:collection.append(copy.deepcopy(record));break
        tree.write(self.model,encoding='utf-8',xml_declaration=True);before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'ambiguous embedded package'):self.worker(dict(action='state'))
        self.assertEqual(self.model.read_bytes(),before)

    def test_native_callbacks_keep_the_original_aircraft_filename(self):
        gid,expected=self.legacy(check_filename=True)
        state,_=self.worker(dict(action='state'));c=next(c for c in state['components'] if c['id']==gid)
        self.assertEqual(self.length(c),12);self.assertEqual([s['points'] for s in c['surfaces']],expected)
