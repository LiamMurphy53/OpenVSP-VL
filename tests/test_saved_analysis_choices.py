"""Saved engineering enums retain original codes, owners and native analysis math."""
import unittest,math
import test_native
import native_saved_analysis_controls as controls
from native_worker import parameter,collect_results,errors,analysis_schema
from vsp_runtime import load
class SavedAnalysisChoices(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    def test_all_native_codes_and_same_name_user_fields(self):
        v=self.v
        for (group,name),(label,items) in controls.FIELDS.items():
            pid=v.FindParm(v.GetVehicleID(),name,group);self.assertTrue(v.ValidParm(pid));p=parameter(v,pid)
            expected=[getattr(v,key) for key,text in items];self.assertEqual([c['value'] for c in p['choices']],expected);self.assertEqual(p['label'],label)
            for value in expected:
                v.SetParmValUpdate(pid,value);self.assertEqual(v.GetParmVal(pid),value);self.assertEqual(parameter(v,pid)['value'],value)
                binding={('MassProperties','MassSliceDir'):('MassProp','MassSliceDir'),('DegenGeom','DegenGeomMeshType'):('DegenGeomMesh','DegenGeomMeshType')}.get((group,name))
                if binding:
                    analysis,field=binding;v.SetAnalysisInputDefaults(analysis);self.assertEqual(list(v.GetIntAnalysisInput(analysis,field)),[value])
                if (group,name)==('PSlice','PlanarAxisType'):
                    v.SetAnalysisInputDefaults('PlanarSlice');normal=v.GetVec3dAnalysisInput('PlanarSlice','Norm')[0];self.assertEqual([normal.x(),normal.y(),normal.z()],[float(axis==value) for axis in range(3)])
            if group=='Projection':
                saved={e['name']:e['values'] for e in controls.projection_options(v)};self.assertEqual(saved[name],[expected[-1]])
            user=v.AddUserParm(v.PARM_INT_TYPE,name,group);field=parameter(v,user);self.assertNotIn('choices',field);self.assertNotEqual(field.get('label'),label)
        for analysis,group,name in [('MassProp','MassProperties','MassSliceDir'),('DegenGeomMesh','DegenGeom','DegenGeomMeshType')]:
            field=next(e for e in analysis_schema(v,analysis)['inputs'] if e['name']==name);self.assertEqual(field['nativeParameter'],v.FindParm(v.GetVehicleID(),name,group))
        import native_study_worker
        schema=native_study_worker.schema(v,parameter);pid=v.FindParm(v.GetVehicleID(),'MassSliceDir','MassProperties');item=next(p for p in schema['parameters'] if p['id']==pid);self.assertEqual([c['value'] for c in item['choices']],[v.X_DIR,v.Y_DIR,v.Z_DIR])
        v.WriteVSPFile(str(self.model),v.SET_ALL);v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        for group,name in controls.FIELDS:self.assertTrue(parameter(v,v.FindParm(v.GetVehicleID(),name,group)).get('choices'))
    def test_saved_mass_axes_match_original_defaults_and_numeric_results(self):
        v=self.v;v.SetParmValUpdate(self.gid,'Density','Mass_Props',1.)
        for axis in [v.X_DIR,v.Y_DIR,v.Z_DIR]:
            pid=v.FindParm(v.GetVehicleID(),'MassSliceDir','MassProperties');v.SetParmValUpdate(pid,axis);v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
            data,out=self.worker(dict(action='analysis',name='MassProp',inputs=[]));self.assertEqual(next(e['values'] for e in data['inputs'] if e['name']=='MassSliceDir'),[axis]);self.assertEqual(out.read_bytes(),before)
            v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();v.SetVSP3FileName(str(self.path/('original-'+str(axis)+'.vsp3')));v.SetAnalysisInputDefaults('MassProp');self.assertEqual(list(v.GetIntAnalysisInput('MassProp','MassSliceDir')),[axis]);v.ExecAnalysis('MassProp');errors(v)
            def clean(x):
                if isinstance(x,float) and not math.isfinite(x):return None
                return [clean(y) for y in x] if isinstance(x,list) else x
            def fields(results):return {(r['name'],r['index'],e['name'],e['index']):clean(e['values']) for r in results for e in r['entries'] if e['type'] in (v.INT_DATA,v.DOUBLE_DATA,v.VEC3D_DATA,v.DOUBLE_MATRIX_DATA) and e['name'] not in ('Analysis_Duration_Sec','WallTime')}
            self.assertEqual(fields(data['results']),fields(collect_results(v)));self.assertEqual(self.model.read_bytes(),before)
            v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
