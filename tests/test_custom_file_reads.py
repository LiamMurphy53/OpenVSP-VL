"""Native file-handle data reads retain geometry after package relocation."""
import base64,io,os,shutil,struct,unittest,zipfile
import test_native,test_custom_scripts
from native_custom_scripts import import_script

class CustomFileReads(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    template=test_custom_scripts.CustomScripts.template

    def script(self,prefix,extra=''):
        return self.template().replace('void UpdateSurf()\n{','void UpdateSurf()\n{'+prefix)+extra

    def package(self,script):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:
            z.writestr('part/Main.vsppart',script);z.writestr('part/length.txt','12\n');z.writestr('part/other.txt','17\n');z.writestr('part/binary.bin',struct.pack('<d',12.25))
        return data.getvalue()

    def original(self,script):
        v=self.v;folder=self.path/'original';folder.mkdir();entry=folder/'Main.vsppart';entry.write_text(script);(folder/'length.txt').write_text('12\n');(folder/'other.txt').write_text('17\n');(folder/'binary.bin').write_bytes(struct.pack('<d',12.25))
        old=os.getcwd();os.chdir(folder)
        try:
            gid=import_script(v,entry,'Original data reader');v.Update();length=v.GetParmVal(gid,'Length','Design');surfaces=[]
            for i in range(v.GetTotalNumSurfs(gid)):
                u,w=v.GetUWTess01(gid,i%v.GetNumMainSurfs(gid));surfaces.append([[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(gid,i,[a for a in u for _ in w],[b for _ in u for b in w])])
        finally:os.chdir(old)
        shutil.rmtree(folder);return length,surfaces

    def imported(self,script):
        state,path=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_PACKAGE',name='Relocated native reader',content=base64.b64encode(self.package(script)).decode()))
        return state,path,next(c for c in state['components'] if c['name']=='Relocated native reader')

    def length(self,c):return next(p['value'] for p in c['params'] if p['name']=='Length' and p['rawGroup']=='Design')

    def check(self,script,expected):
        original,surfaces=self.original(script);self.assertEqual(original,expected)
        _,path,c=self.imported(script);self.assertEqual(self.length(c),original);self.assertEqual([s['points'] for s in c['surfaces']],surfaces)
        shutil.rmtree(path.parent/'.studio-custom-assets',ignore_errors=True)
        state,_=self.worker(dict(action='state'),path);cold=next(x for x in state['components'] if x['id']==c['id']);self.assertEqual(self.length(cold),original);self.assertEqual(cold['surfaces'],c['surfaces'])
        return path,c

    def test_literal_native_reads_preserve_complete_geometry_without_original_files(self):
        self.check(self.script('file reader;if(reader.open("length.txt","r")==0){string line=reader.readLine();reader.close();SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),parseFloat(line));}'),12)

    def test_computed_filenames_and_optional_missing_reads_keep_native_status(self):
        script=self.script('file reader;int choice=GetIntParmVal(GetParm(GetCurrCustomGeom(),"DataChoice","Design"));string filename=choice==0?"./length.txt":choice==1?"other.txt":"optional.txt";double length=7;if(reader.open(filename,"r")==0){length=parseFloat(reader.readLine());reader.close();}SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);')
        script=script.replace('void Init()\n{','void Init()\n{string choice=AddParm(PARM_INT_TYPE,"DataChoice","Design");SetParmVal(choice,0);')
        path,c=self.check(script,12);pid=next(p['id'] for p in c['params'] if p['name']=='DataChoice')
        for choice,expected in [(1,17),(2,7),(0,12)]:
            state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=choice),path);c=next(x for x in state['components'] if x['id']==c['id']);self.assertEqual(self.length(c),expected)

    def test_native_writes_and_read_after_write_take_precedence_over_companions(self):
        self.check(self.script('file writer;writer.open("length.txt","w");writer.writeString("23\\n");writer.close();file reader;if(reader.open("length.txt","r")==0){string line=reader.readLine();reader.close();SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),parseFloat(line));}'),23)

    def test_typed_function_parameters_and_nonfile_shadow_methods(self):
        extra='\nclass Other{int open(const string &in filename,const string &in mode){return 99;}}\nint Probe(){Other reader;return reader.open("length.txt","r");}\ndouble ReadValue(file@ reader,const string &in filename){if(reader.open(filename,"r")!=0)return 5;string line=reader.readLine();reader.close();return parseFloat(line);}\n'
        self.check(self.script('file reader;double length=ReadValue(@reader,"length.txt");if(Probe()!=99)length=1;SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);',extra),12)

    def test_binary_reads_use_original_native_file_decoder(self):
        self.check(self.script('file reader;if(reader.open("binary.bin","r")==0){double length=reader.readDouble();reader.close();SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);}'),12.25)
