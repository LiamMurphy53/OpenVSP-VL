"""Native intersection setup, mode/thin surfaces, file controls and CAD parity."""
import json,re,sys,unittest
from pathlib import Path
import test_native
import test_cfd_results as cfd_results
from vsp_runtime import distribution
from native_worker import analysis_schema

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class IntersectionGuides(unittest.TestCase):
    setUpClass=classmethod(cfd_results.CfdResults.setUpClass.__func__)
    tearDownClass=classmethod(cfd_results.CfdResults.tearDownClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    drawings=staticmethod(cfd_results.CfdResults.drawings)

    def fixture(self):
        v=self.v;self.pod=v.AddGeom('POD');v.SetGeomName(self.pod,'Body')
        self.region=v.AddSubSurf(self.gid,v.SS_RECTANGLE,0);v.SetSubSurfName(self.region,'Wing patch')
        v.SetSetName(3,'Wing and body');v.SetSetFlag(self.gid,3,True);v.SetSetFlag(self.pod,3,True)
        v.SetSetName(4,'Thin wing');v.SetSetFlag(self.gid,4,True)
        v.SetSetName(5,'Body only');v.SetSetFlag(self.pod,5,True)
        self.mode=v.CreateAndAddMode('Trim configuration',3,v.SET_NONE)
        group=v.AddVarPresetGroup('Wing position');p=v.FindParm(self.gid,'X_Rel_Location','XForm')
        v.AddVarPresetParm(group,p);setting=v.AddVarPresetSetting(group,'Aft');v.SetVarPresetParmVal(group,setting,p,3)
        v.ModeAddGroupSetting(self.mode,group,setting);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)

    def direct(self,values):
        v=self.v;folder=self.path/'direct';folder.mkdir(exist_ok=True)
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();v.SetAnalysisInputDefaults('SurfaceIntersection')
        setters={v.INT_DATA:v.SetIntAnalysisInput,v.DOUBLE_DATA:v.SetDoubleAnalysisInput,v.STRING_DATA:v.SetStringAnalysisInput}
        for key,value in values.items():setters[v.GetAnalysisInputType('SurfaceIntersection',key)]('SurfaceIntersection',key,value)
        for key in v.GetAnalysisInputNames('SurfaceIntersection'):
            if key.endswith('FileName'):v.SetStringAnalysisInput('SurfaceIntersection',key,[str(folder/Path(v.GetStringAnalysisInput('SurfaceIntersection',key)[0]).name)])
        self.assertEqual(v.ExecAnalysis('SurfaceIntersection'),'')
        expected=json.loads(self.intersection(str(distribution()/'python/openvsp/openvsp/_vsp.so').encode()))
        return folder,expected

    def run_case(self,values):
        before=self.model.read_bytes()
        result,path=self.worker(dict(action='analysis',name='SurfaceIntersection',inputs=[dict(name=k,values=x) for k,x in values.items()]))
        actual=json.loads((path.parent/result['cfdChecks']['drawingFile']).read_text())
        folder,expected=self.direct(values)
        self.assertEqual(self.drawings([o for p in actual['parts'] for o in p['objects']]),self.drawings(expected))
        self.assertEqual(self.model.read_bytes(),before);self.assertEqual(path.read_bytes(),before)
        return result,path,folder

    def test_guidance_retains_every_native_input_default_and_native_enum_limits(self):
        self.fixture();v=self.v;v.SetAnalysisInputDefaults('SurfaceIntersection')
        raw={key:(v.GetAnalysisInputType('SurfaceIntersection',key),list(({v.INT_DATA:v.GetIntAnalysisInput,v.DOUBLE_DATA:v.GetDoubleAnalysisInput,v.STRING_DATA:v.GetStringAnalysisInput}[v.GetAnalysisInputType('SurfaceIntersection',key)])('SurfaceIntersection',key))) for key in v.GetAnalysisInputNames('SurfaceIntersection')}
        s=analysis_schema(v,'SurfaceIntersection');fields={e['name']:e for e in s['inputs']}
        self.assertEqual({key:(e['type'],e['values']) for key,e in fields.items()},raw)
        self.assertEqual(set(fields),{key for g in s['guide']['sections'] for key in g['inputs']})
        self.assertIn(dict(value=self.mode,label='Trim configuration'),fields['ModeID']['choices'])
        self.assertEqual([c['value'] for c in fields['STEPRepresentation']['choices']],[v.STEP_SHELL,v.STEP_BREP])
        self.assertNotIn(v.LEN_UNITLESS,[c['value'] for c in fields['CADLenUnit']['choices']])
        cid=v.FindContainer('SurfaceIntersectSettings',0)
        for key in ['RelCurveTol','STEPTol','CADLenUnit','CADLabelDelim']:
            p=next(p for p in v.FindContainerParmIDs(cid) if v.GetParmName(p)==key)
            self.assertEqual((fields[key]['min'],fields[key]['max']),(v.GetParmLowerLimit(p),v.GetParmUpperLimit(p)))
        self.assertEqual(fields['ModeID']['applicableWhen'],dict(input='UseMode',values=[1]))
        self.assertEqual(fields['STEPTol']['applicableWhen'],dict(input='STEPFileFlag',values=[1]))

    def test_native_mode_presets_and_thin_geometry_match_every_curve_and_export_samples(self):
        self.fixture();v=self.v
        for index,geometry in enumerate([dict(UseMode=[1],ModeID=[self.mode]),dict(UseMode=[0],SelectedSetIndex=[5],SelectedDegenSetIndex=[4])]):
            with self.subTest(case=index):
                values=dict(geometry,RelCurveTol=[.01],ExportRawFlag=[index],IntersectSubSurfs=[index],IGESFileFlag=[0],STEPFileFlag=[0],P3DFileFlag=[0],SRFFileFlag=[0],CURVFileName=[f'case-{index}.curv'])
                result,path,direct=self.run_case(values);self.assertGreater(result['cfdChecks']['counts']['BORDERCURVE'],0)
                exported=path.parent/f'case-{index}.curv';self.assertEqual(exported.read_bytes(),(direct/exported.name).read_bytes())
                native_samples=path.parent/result['cfdChecks']['rawCurvesFile' if index else 'adaptedCurvesFile']
                self.assertEqual(exported.read_bytes(),native_samples.read_bytes())
                for suffix in ['.srf','.p3d','.igs','.stp']:self.assertFalse(list(path.parent.glob('*'+suffix)))
                self.assertEqual(next(e['values'] for e in result['inputs'] if e['name']=='RelCurveTol'),[.01])

    def test_cad_shell_and_brep_units_labels_and_file_records_equal_native(self):
        self.fixture();v=self.v
        for representation in [v.STEP_SHELL,v.STEP_BREP]:
            with self.subTest(representation=representation):
                values=dict(SelectedSetIndex=[5],SelectedDegenSetIndex=[-1],STEPRepresentation=[representation],STEPTol=[2e-5],CADLenUnit=[v.LEN_MM],CADLabelDelim=[v.DELIM_USCORE],CADLabelID=[0],CADLabelSplitNo=[0],STEPFileName=[f'body-{representation}.stp'],IGESFileName=[f'body-{representation}.igs'])
                result,path,direct=self.run_case(values)
                step=(path.parent/f'body-{representation}.stp').read_text();expected=(direct/f'body-{representation}.stp').read_text()
                # Compare every native record/metadata field except the header's
                # execution timestamp. Original files are never normalized.
                step_records=lambda text:re.sub(r"(?m)^(FILE_NAME\('[^']*',')[^']*('.*)$",r'\1<NATIVE_TIMESTAMP>\2',text)
                self.assertEqual(step_records(step),step_records(expected))
                entity='SHELL_BASED_SURFACE_MODEL' if representation==v.STEP_SHELL else 'MANIFOLD_SOLID_BREP'
                self.assertIn(entity,step);self.assertIn('SI_UNIT(.MILLI.,.METRE.)',step)
                iges=(path.parent/f'body-{representation}.igs').read_text();native_iges=(direct/f'body-{representation}.igs').read_text()
                records=lambda text:[line for line in text.splitlines() if len(line)>72 and line[72] in 'SDPT']
                self.assertEqual(records(iges),records(native_iges));self.assertTrue(records(iges))
                global_records=lambda text:re.sub(r'15H\d{8}\.\d{6}','15H00000000.000000',''.join(line[:72] for line in text.splitlines() if len(line)>72 and line[72]=='G').rstrip())
                self.assertEqual(global_records(iges),global_records(native_iges))
                self.assertIn(',1.0,2,2HMM,',global_records(iges))
                for e in result['inputs']:
                    if e['name'].endswith('FileName'):self.assertEqual(Path(e['values'][0]).parent.resolve(),path.parent.resolve())

    def test_surface_region_inclusion_changes_native_exports_and_matches_sdk(self):
        self.fixture();runs=[]
        for enabled in [0,1]:
            values=dict(UseMode=[0],SelectedSetIndex=[3],SelectedDegenSetIndex=[-1],IntersectSubSurfs=[enabled],IGESFileFlag=[0],STEPFileFlag=[0],P3DFileFlag=[1],P3DFileName=[f'regions-{enabled}.p3d'],CURVFileName=[f'regions-{enabled}.curv'],SRFFileName=[f'regions-{enabled}.srf'])
            result,path,direct=self.run_case(values)
            exports=[]
            for suffix in ['curv','srf','p3d']:
                name=f'regions-{enabled}.{suffix}';data=(path.parent/name).read_bytes()
                self.assertEqual(data,(direct/name).read_bytes());exports.append(data)
            runs.append(exports)
        self.assertNotEqual(runs[0],runs[1])

    def test_invalid_native_choices_references_limits_and_output_collisions_preserve_model(self):
        self.fixture();v=self.v;before=self.model.read_bytes()
        cases=[dict(UseMode=[1],ModeID=['MISSING']),dict(SelectedSetIndex=[999]),dict(SelectedDegenSetIndex=[999]),dict(RelCurveTol=[0]),dict(STEPTol=[0]),dict(STEPRepresentation=[2]),dict(CADLenUnit=[v.LEN_UNITLESS]),dict(CADLabelDelim=[v.DELIM_NUM_TYPES]),dict(IntersectSubSurfs=[2]),dict(CURVFileName=['request.json']),dict(STEPFileName=['../aircraft.vsp3']),dict(CURVFileName=['same.curv'],SRFFileName=['SAME.CURV']),dict(CURVFileName=['']),dict(CURVFileName=['bad\nname.curv']),dict(RelCurveTol=[])]
        for values in cases:
            with self.subTest(values=values),self.assertRaises(ValueError):
                self.worker(dict(action='analysis',name='SurfaceIntersection',inputs=[dict(name=k,values=x) for k,x in values.items()]))
            self.assertEqual(self.model.read_bytes(),before)
        outside=self.path/'outside.curv';outside.write_bytes(b'Existing native file')
        result,path,_=self.run_case(dict(IGESFileFlag=[0],STEPFileFlag=[0],CURVFileName=[str(outside)]))
        self.assertEqual(outside.read_bytes(),b'Existing native file');self.assertTrue((path.parent/'outside.curv').is_file())
