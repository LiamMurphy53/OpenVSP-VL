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
        original,surfaces=self.original(script)
        if expected is not None:self.assertEqual(original,expected)
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

    def test_auto_file_handle_reads_original_data(self):
        self.check(self.script('auto reader=file();if(reader.open("length.txt","r")==0){double length=parseFloat(reader.readLine());reader.close();SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);}'),12)

    def test_member_and_indexed_file_handles_read_original_data(self):
        for expression,prefix,extra in [
            ('holder.reader','Holder holder;','\nclass Holder{file@ reader=file();}\n'),
            ('readers[1]','array<file@> readers={file(),file()};',''),
            ('holder.reader','auto holder=Holder();','\nclass Holder{file@ reader=file();}\n'),
            ('holder.getReader()','Holder holder;','\nclass Holder{file@ reader=file();file@ getReader(){return reader;}}\n')
        ]:
            with self.subTest(expression=expression):
                self.check(self.script(prefix+'if('+expression+'.open("length.txt","r")==0){double length=parseFloat('+expression+'.readLine());'+expression+'.close();SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);}',extra),12)

    def test_factory_receiver_and_mode_evaluate_once_in_original_order(self):
        extra='\nint calls=0;file@ shared=file();file@ MakeReader(){calls=calls*10+1;return shared;}string ReadMode(){calls=calls*10+2;return "r";}\n'
        script=self.script('calls=0;if(MakeReader().open("length.txt",ReadMode())==0){double length=parseFloat(shared.readLine())+calls/100.0;shared.close();SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);}',extra)
        _,component=self.check(script,None);self.assertIn(self.length(component),(12.12,12.21))

    def test_nonfile_members_and_factories_remain_original_calls(self):
        extra='\nclass Other{int open(const string &in filename,const string &in mode){return filename=="length.txt"?99:0;}}\nclass Holder{Other reader;Other@ getReader(){return reader;}}\nOther@ NotAFile(){Other value;return value;}\n'
        prefix='auto holder=Holder();auto nonfile=NotAFile();file reader;double length=1;if(reader.open("length.txt","r")==0){length=parseFloat(reader.readLine());reader.close();}if(holder.reader.open("length.txt","r")!=99 || holder.getReader().open("length.txt","r")!=99 || nonfile.open("length.txt","r")!=99)length=2;SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);'
        self.check(self.script(prefix,extra),12)

    def test_multiple_handle_declarations_and_array_constructor(self):
        for prefix,reader in [('file first,second;','second'),('array<file@> readers(2);@readers[1]=file();','readers[1]')]:
            with self.subTest(prefix=prefix):
                self.check(self.script(prefix+'if('+reader+'.open("length.txt","r")==0){double length=parseFloat('+reader+'.readLine());'+reader+'.close();SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);}'),12)

    def test_inherited_file_members_and_methods_keep_native_data(self):
        extra='\nclass ReaderBase{file@ reader=file();file@ getReader(){return reader;}}\nclass ReaderMiddle:ReaderBase{}\nclass ReaderLeaf:ReaderMiddle{}\n'
        for expression in ['holder.reader','holder.getReader()']:
            with self.subTest(expression=expression):
                prefix='ReaderLeaf holder;double length=5;if('+expression+'.open("length.txt","r")==0){length=parseFloat('+expression+'.readLine());'+expression+'.close();}SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);'
                self.check(self.script(prefix,extra),12)

    def test_inherited_nonfile_member_and_method_are_not_relocated(self):
        extra='\nclass Other{int open(const string &in filename,const string &in mode){return filename=="length.txt"?99:0;}}\nclass OtherBase{Other reader;Other@ getReader(){return reader;}}\nclass OtherLeaf:OtherBase{}\n'
        prefix='OtherLeaf holder;file reader;double length=5;if(reader.open("length.txt","r")==0){length=parseFloat(reader.readLine());reader.close();}if(holder.reader.open("length.txt","r")!=99 || holder.getReader().open("length.txt","r")!=99)length=2;SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);'
        self.check(self.script(prefix,extra),12)

    def test_inherited_receivers_inside_methods_and_local_shadows(self):
        extra='\nclass Other{int open(const string &in filename,const string &in mode){return 99;}}\nclass ReaderBase{file@ reader=file();file@ getReader(){return reader;}}\nclass ReaderLeaf:ReaderBase{double value(){double result=5;if(this.reader.open("length.txt","r")==0){result=parseFloat(reader.readLine());reader.close();}Other reader;if(reader.open("length.txt","r")!=99)return 2;return result;}double fromGetter(){if(getReader().open("length.txt","r")!=0)return 5;double result=parseFloat(getReader().readLine());getReader().close();return result;}}\n'
        self.check(self.script('ReaderLeaf holder;SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),(holder.value()+holder.fromGetter())/2);',extra),12)

    def test_namespaced_native_file_members_and_factories(self):
        extra='\nnamespace Data{file@ shared=file();file@ MakeReader(){return shared;}class Holder{file@ reader=file();file@ getReader(){return reader;}}}\n'
        for prefix,expression in [('Data::Holder holder;','holder.reader'),('auto holder=Data::Holder();','holder.getReader()'),('','Data::MakeReader()')]:
            with self.subTest(expression=expression):
                value='Data::shared' if expression=='Data::MakeReader()' else expression
                self.check(self.script(prefix+'double length=5;if('+expression+'.open("length.txt","r")==0){length=parseFloat('+value+'.readLine());'+value+'.close();}SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);',extra),12)

    def test_namespace_type_and_function_names_do_not_collide(self):
        extra='\nnamespace Data{class Holder{file@ reader=file();file@ getReader(){return reader;}}file@ MakeReader(){return file();}}\nnamespace Other{class Value{int open(const string &in filename,const string &in mode){return 99;}}class Holder{Value reader;Value@ getReader(){return reader;}}Value@ MakeReader(){return Value();}}\n'
        prefix='auto holder=Data::Holder();Other::Holder other;double length=5;if(holder.getReader().open("length.txt","r")==0){length=parseFloat(holder.reader.readLine());holder.reader.close();}if(other.reader.open("length.txt","r")!=99 || other.getReader().open("length.txt","r")!=99 || Other::MakeReader().open("length.txt","r")!=99)length=2;SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);'
        self.check(self.script(prefix,extra),12)

    def test_nested_namespace_readers_and_qualified_inheritance(self):
        extra='\nnamespace Data{class Base{file@ reader=file();file@ getReader(){return reader;}}namespace Nested{class Holder:Data::Base{}file@ shared=file();file@ MakeReader(){return shared;}double Read(){Holder holder;double length=5;if(holder.reader.open("length.txt","r")==0){length=parseFloat(holder.reader.readLine());holder.reader.close();}if(MakeReader().open("other.txt","r")==0){length+=parseFloat(shared.readLine());shared.close();}return length;}}}\n'
        self.check(self.script('SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),Data::Nested::Read());',extra),29)

    def test_namespace_forward_globals_and_absolute_lookup(self):
        extra='\nfile@ shared=file();namespace Data{double Read(){double length=5;if(shared.open("length.txt","r")==0){length=parseFloat(shared.readLine());shared.close();}if(::shared.open("other.txt","r")==0){length+=parseFloat(::shared.readLine());::shared.close();}return length;}file@ shared=file();}\n'
        self.check(self.script('SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),Data::Read());',extra),29)

    def test_qualified_parameter_types_keep_their_namespace_identity(self):
        extra='\nnamespace Data{class Holder{file@ reader=file();}}namespace Other{class Value{int open(const string &in filename,const string &in mode){return 99;}}class Holder{Value reader;}}namespace Data{int Probe(Other::Holder@ holder){return holder.reader.open("length.txt","r");}double Read(Data::Holder@ holder){double length=5;if(holder.reader.open("length.txt","r")==0){length=parseFloat(holder.reader.readLine());holder.reader.close();}return length;}}\n'
        self.check(self.script('Data::Holder holder;Other::Holder other;double length=Data::Read(@holder);if(Data::Probe(@other)!=99)length=2;SetParmVal(GetParm(GetCurrCustomGeom(),"Length","Design"),length);',extra),12)
