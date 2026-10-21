"""Named CAD parameter sweeps retain original native choices and exported files."""
import json,re,unittest
from pathlib import Path
import test_studies
import native_service as service,native_studies as studies,native_managers
from native_worker import parameter,errors

class CADSettingStudies(unittest.TestCase):
    setUpClass=classmethod(test_studies.NativeStudies.setUpClass.__func__)
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    save=test_studies.NativeStudies.save
    wait=test_studies.NativeStudies.wait

    def test_schema_choices_belong_only_to_original_cad_manager(self):
        v=self.v;cid=native_managers.manager(v,'SurfaceIntersectSettings');schema=studies.study_schema();fields={p['id']:p for p in schema['parameters']}
        for name in ['CADLenUnit','CADLabelDelim','STEPRepresentation','ExportRawFlag']:
            p=v.FindParm(cid,name,'ExportIntersect');field=parameter(v,p)
            self.assertTrue(field['choices']);self.assertEqual(fields[p]['choices'],field['choices']);self.assertTrue(fields[p]['label'].startswith('Surface intersections / Saved defaults / '))
            fake=v.AddUserParm(v.PARM_INT_TYPE,name,'ExportIntersect');self.assertNotIn('choices',parameter(v,fake));self.assertNotIn('label',parameter(v,fake))

    def test_unit_and_representation_cases_match_original_step_and_iges_records(self):
        v=self.v;v.ClearVSPModel();g=v.AddGeom('POD');v.SetGeomName(g,'CAD body');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);source=self.model.read_bytes()
        cid=native_managers.manager(v,'SurfaceIntersectSettings');units=v.FindParm(cid,'CADLenUnit','ExportIntersect');representation=v.FindParm(cid,'STEPRepresentation','ExportIntersect')
        inputs=[dict(name=k,values=[x]) for k,x in dict(SelectedSetIndex=0,SelectedDegenSetIndex=-1,SRFFileFlag=0,CURVFileFlag=0,P3DFileFlag=0,IGESFileFlag=1,STEPFileFlag=1,IGESFileName='native.igs',STEPFileName='native.stp').items()]
        plan=self.save([dict(kind='parameter',id=units,values=[v.LEN_CM,v.LEN_FT]),dict(kind='parameter',id=representation,values=[v.STEP_SHELL,v.STEP_BREP])],[dict(name='SurfaceIntersection',inputs=inputs)])
        batch=self.wait(plan['id'],studies.launch(plan['id'])['id']);self.assertEqual(batch['status'],'complete',batch)
        normalize=lambda text:re.sub(r"(?m)^(FILE_NAME\('[^']*',')[^']*('.*)$",r'\1<NATIVE_TIMESTAMP>\2',text)
        records=lambda text:[line for line in text.splitlines() if len(line)>72 and line[72] in 'SDPT']
        globals=lambda text:re.sub(r'15H\d{8}\.\d{6}','15H00000000.000000',''.join(line[:72] for line in text.splitlines() if len(line)>72 and line[72]=='G').rstrip())
        for case in batch['cases']:
            job=service.job_state(case['stages'][0]['job']);folder=service.job_folder(job['id']);data=job['result'];unit,rep=case['values'];direct=self.path/('direct-'+str(case['index']));direct.mkdir()
            v.ClearVSPModel();v.ReadVSPFile(str(folder/'aircraft.vsp3'));v.Update();v.SetVSP3FileName(str(direct/'aircraft.vsp3'));v.SetAnalysisInputDefaults('SurfaceIntersection')
            for entry in data['inputs']:
                values=entry['values']
                if entry['type']==v.STRING_DATA and entry['name'].endswith('FileName'):values=[str(direct/Path(x).name) for x in values]
                {v.INT_DATA:v.SetIntAnalysisInput,v.DOUBLE_DATA:v.SetDoubleAnalysisInput,v.STRING_DATA:v.SetStringAnalysisInput}[entry['type']]('SurfaceIntersection',entry['name'],values,entry['index'])
            v.ExecAnalysis('SurfaceIntersection');errors(v)
            step=(folder/'native.stp').read_text();self.assertEqual(normalize(step),normalize((direct/'native.stp').read_text()))
            self.assertIn('SHELL_BASED_SURFACE_MODEL' if rep==v.STEP_SHELL else 'MANIFOLD_SOLID_BREP',step)
            self.assertIn('SI_UNIT(.CENTI.,.METRE.)' if unit==v.LEN_CM else "CONVERSION_BASED_UNIT('FOOT',",step)
            iges=(folder/'native.igs').read_text();native=(direct/'native.igs').read_text();self.assertEqual(records(iges),records(native));self.assertEqual(globals(iges),globals(native))
        self.assertEqual(self.model.read_bytes(),source)
