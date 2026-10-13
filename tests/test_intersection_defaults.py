"""Saved native CAD defaults and whole-request validation."""
import sys,unittest,re
import test_native
import test_cfd_results as cfd_results
import test_intersection_guides as guides
import native_intersection_defaults as defaults

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class IntersectionDefaults(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_saved_defaults_become_official_sdk_analysis_defaults_after_cold_reload(self):
        v=self.v;values=dict(IntersectSubSurfs=0,RelCurveTol=.012,ExportRawFlag=1,SRF_Export=0,CURV_Export=1,PLOT3D_Export=0,IGES_Export=1,STEP_Export=1,CADLenUnit=v.LEN_CM,CADLabelDelim=v.DELIM_SPACE,CADLabelID=0,CADLabelName=1,CADLabelSurfNo=0,CADLabelSplitNo=0,STEPRepresentation=v.STEP_SHELL,STEPTol=2e-5)
        config=defaults.configuration(v);c=config['id'];ids={v.GetParmName(p):p for p in v.FindContainerParmIDs(c)}
        for p in config['params']:
            self.assertEqual((p['min'],p['max']),(v.GetParmLowerLimit(ids[p['name']]),v.GetParmUpperLimit(ids[p['name']])))
        self.assertNotIn(v.LEN_UNITLESS,[x['value'] for x in next(p['choices'] for p in config['params'] if p['name']=='CADLenUnit')])
        original=self.model.read_bytes()
        defaults.mutate(v,dict(values=values));expected=defaults.configuration(v)
        state,path=self.worker(dict(action='mutate',operation='intersection-defaults',values=values))
        self.assertEqual(next(g['exportDefaults'] for g in state['tools']['globalSettings'] if g['name']=='SurfaceIntersectSettings'),expected)
        schema,_=self.worker(dict(action='schema',name='SurfaceIntersection'),path)
        fields={e['name']:e['values'] for e in schema['inputs']}
        for name,value in values.items():self.assertEqual(fields[defaults.INPUT_NAMES.get(name,name)],[value])
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        self.assertEqual({p['name']:p['value'] for p in defaults.configuration(v)['params']},values)
        self.assertEqual(self.model.read_bytes(),original)

    def test_invalid_defaults_preserve_every_native_parameter_and_model_bytes(self):
        before=defaults.configuration(self.v);file=self.model.read_bytes()
        for bad in [dict(CADLenUnit=self.v.LEN_UNITLESS),dict(CADLabelDelim=99),dict(STEPRepresentation=-1),dict(STEPTol=0),dict(RelCurveTol=.000001),dict(IGES_Export=.5),dict(CURV_Export=True),dict(CADLabelName=float('nan')),dict(SRF_XYZIntCurve=1),dict(Unknown=1),{},[],None]:
            values=dict(CADLabelID=0,**bad) if isinstance(bad,dict) and bad else bad
            with self.subTest(values=values),self.assertRaises(ValueError):defaults.mutate(self.v,dict(values=values))
            self.assertEqual(defaults.configuration(self.v),before);self.assertEqual(self.model.read_bytes(),file)

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class DefaultCADExports(unittest.TestCase):
    setUpClass=classmethod(cfd_results.CfdResults.setUpClass.__func__)
    tearDownClass=classmethod(cfd_results.CfdResults.tearDownClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    drawings=staticmethod(cfd_results.CfdResults.drawings)
    direct=guides.IntersectionGuides.direct
    run_case=guides.IntersectionGuides.run_case

    def test_saved_units_labels_representation_and_flags_match_native_cad_records(self):
        v=self.v
        for unit,representation,unitMetadata,stepMetadata in [(v.LEN_CM,v.STEP_SHELL,',1.0,10,2HCM,','SI_UNIT(.CENTI.,.METRE.)'),(v.LEN_FT,v.STEP_BREP,',1.0,4,2HFT,',"CONVERSION_BASED_UNIT('FOOT',")]:
            with self.subTest(unit=unit):
                v.ClearVSPModel();v.AddGeom('POD');v.SetGeomName(v.FindGeoms()[0],'CAD body')
                values=dict(CADLenUnit=unit,CADLabelDelim=v.DELIM_SPACE,CADLabelID=0,CADLabelName=1,CADLabelSurfNo=1,CADLabelSplitNo=1,STEPRepresentation=representation,STEPTol=2e-5,SRF_Export=0,CURV_Export=0,PLOT3D_Export=0,IGES_Export=1,STEP_Export=1)
                v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
                _,saved=self.worker(dict(action='mutate',operation='intersection-defaults',values=values));self.model=saved
                result,path,direct=self.run_case(dict(IGESFileName=['native.igs'],STEPFileName=['native.stp']))
                inputs={e['name']:e['values'][0] for e in result['inputs']}
                for name,value in values.items():self.assertEqual(inputs[defaults.INPUT_NAMES.get(name,name)],value)
                step=(path.parent/'native.stp').read_text();expected=(direct/'native.stp').read_text()
                normalize=lambda text:re.sub(r"(?m)^(FILE_NAME\('[^']*',')[^']*('.*)$",r'\1<NATIVE_TIMESTAMP>\2',text)
                self.assertEqual(normalize(step),normalize(expected));self.assertIn(stepMetadata,step);self.assertIn('Surf_CAD body 0 0',step)
                self.assertIn('SHELL_BASED_SURFACE_MODEL' if representation==v.STEP_SHELL else 'MANIFOLD_SOLID_BREP',step)
                records=lambda text:[line for line in text.splitlines() if len(line)>72 and line[72] in 'SDPT']
                globalRecords=lambda text:re.sub(r'15H\d{8}\.\d{6}','15H00000000.000000',''.join(line[:72] for line in text.splitlines() if len(line)>72 and line[72]=='G').rstrip())
                iges=(path.parent/'native.igs').read_text();native=(direct/'native.igs').read_text()
                self.assertEqual(records(iges),records(native));self.assertTrue(records(iges));self.assertEqual(globalRecords(iges),globalRecords(native));self.assertIn(unitMetadata,globalRecords(iges))
                for prefix in ['SRF','CURV','P3D']:self.assertFalse((path.parent/inputs[prefix+'FileName'].split('/')[-1]).exists())
