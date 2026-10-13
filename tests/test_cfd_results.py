"""Saved native CFD intersection/diagnostic artifacts and direct-engine equality."""
import ctypes,json,os,sys,tempfile,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
import test_native
from vsp_runtime import load,ROOT,distribution
import native_cfd_results

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class CfdResults(unittest.TestCase):
 setUp=test_native.NativeIntegration.setUp
 tearDown=test_native.NativeIntegration.tearDown
 worker=test_native.NativeIntegration.worker
 @classmethod
 def setUpClass(cls):
  cls.v=load();cls.tempref=tempfile.TemporaryDirectory();target=Path(cls.tempref.name)/'reference.dylib'
  subprocess.run(['/usr/bin/clang++','-std=c++17','-O2','-dynamiclib','-I',str(ROOT/'native_bridge/vendor/openvsp-3.52.2'),str(ROOT/'tests/cfd_native_reference.cpp'),'-o',str(target)],capture_output=True,check=True)
  cls.library=ctypes.CDLL(str(target));cls.reference=cls.library.native_cfd_result_reference;cls.reference.argtypes=[ctypes.c_char_p];cls.reference.restype=ctypes.c_char_p
  cls.intersection=cls.library.native_intersection_reference;cls.intersection.argtypes=[ctypes.c_char_p];cls.intersection.restype=ctypes.c_char_p
 @classmethod
 def tearDownClass(cls):cls.tempref.cleanup()
 @staticmethod
 def drawings(objects):return sorted(json.dumps(dict(nativeType=o['nativeType'],points=o['points'])) for o in objects)
 def inputs(self):return [dict(name=n,index=0,type=self.v.DOUBLE_DATA,values=[x]) for n,x in dict(BaseLen=1,MinLen=.2,MaxGap=.02).items()]
 def test_every_saved_drawing_matches_independent_native_closed_wing_mesh(self):
  v=self.v;before=self.model.read_bytes();result,path=self.worker(dict(action='analysis',name='CfdMeshAnalysis',inputs=self.inputs()))
  checks=result['cfdChecks'];self.assertTrue(checks['available']);data=json.loads((path.parent/checks['drawingFile']).read_text())
  v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();v.SetAnalysisInputDefaults('CfdMeshAnalysis')
  for e in self.inputs():v.SetDoubleAnalysisInput('CfdMeshAnalysis',e['name'],e['values'])
  v.SetIntAnalysisInput('CfdMeshAnalysis','GMSHFileFlag',[1]);v.SetStringAnalysisInput('CfdMeshAnalysis','GMSHFileName',[str(self.path/'direct.msh')]);v.ExecAnalysis('CfdMeshAnalysis')
  expected=json.loads(self.reference(str(distribution()/'python/openvsp/openvsp/_vsp.so').encode()))
  self.assertEqual(self.drawings([o for p in data['parts'] for o in p['objects']]),self.drawings(expected))
  self.assertEqual([checks['counts'][k] for k in ['BADEDGE','BADTRI','BADQUAD']],[0,0,0]);self.assertGreater(checks['counts']['BORDERCURVE'],0)
  self.assertTrue(any('does not establish' in w for w in checks['warnings']));self.assertEqual(self.model.read_bytes(),before);self.assertEqual(path.read_bytes(),before)
  # Repeated observations do not append problem collections or modify geometry.
  first=native_cfd_results.save(v);again=native_cfd_results.save(v);self.assertEqual(first,again)
  for key in ['rawCurvesFile','adaptedCurvesFile']:
   self.assertEqual((path.parent/checks[key]).read_bytes(),(self.path/again[key]).read_bytes())
 def test_open_native_wing_returns_engine_classified_problem_edges(self):
  v=self.v
  for p in v.GetGeomParmIDs(self.gid):
   if v.GetParmName(p) in ['CapUMinOption','CapUMaxOption']:v.SetParmVal(p,v.NO_END_CAP)
  v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
  result,path=self.worker(dict(action='analysis',name='CfdMeshAnalysis',inputs=self.inputs()));checks=result['cfdChecks'];self.assertTrue(checks['available'])
  self.assertGreater(checks['counts']['BADEDGE'],0);self.assertTrue(any('classified problem' in w for w in checks['warnings']))
  data=json.loads((path.parent/checks['drawingFile']).read_text());part=next(p for p in data['parts'] if p['id']=='BADEDGE');self.assertEqual(sum(len(o['points']) for o in part['objects']),checks['counts']['BADEDGE']*2)
  v.SetAnalysisInputDefaults('CfdMeshAnalysis')
  for e in self.inputs():v.SetDoubleAnalysisInput('CfdMeshAnalysis',e['name'],e['values'])
  v.SetIntAnalysisInput('CfdMeshAnalysis','GMSHFileFlag',[1]);v.SetStringAnalysisInput('CfdMeshAnalysis','GMSHFileName',[str(self.path/'open-direct.msh')]);v.ExecAnalysis('CfdMeshAnalysis')
  expected=json.loads(self.reference(str(distribution()/'python/openvsp/openvsp/_vsp.so').encode()))
  self.assertEqual(self.drawings([o for p in data['parts'] for o in p['objects']]),self.drawings(expected))
  first=native_cfd_results.save(v);again=native_cfd_results.save(v);self.assertEqual(first,again);self.assertEqual(first['counts'],checks['counts'])
 def test_unavailable_adapter_keeps_mesh_results_without_claiming_checks(self):
  with patch('native_cfd_results.adapter',side_effect=ValueError('Unsupported platform')):
   result=native_cfd_results.save(self.v)
  self.assertFalse(result['available']);self.assertIn('Unsupported platform',result['reason']);self.assertNotIn('counts',result)

 def test_standalone_intersections_export_and_match_every_native_curve_point(self):
  v=self.v;v.AddGeom('POD');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
  inputs=[dict(name=n,index=0,type=v.INT_DATA,values=[0]) for n in ['IGESFileFlag','STEPFileFlag']]
  result,path=self.worker(dict(action='analysis',name='SurfaceIntersection',inputs=inputs));checks=result['cfdChecks']
  self.assertEqual(result['resultID'],'');self.assertTrue(checks['available']);self.assertEqual(checks['kind'],'surface-intersections');self.assertNotIn('meshFile',result)
  self.assertNotIn('BADEDGE',checks['counts']);self.assertGreater(checks['counts']['ISECTCURVE'],0)
  v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();v.SetAnalysisInputDefaults('SurfaceIntersection')
  for e in inputs:v.SetIntAnalysisInput('SurfaceIntersection',e['name'],e['values'])
  for n in v.GetAnalysisInputNames('SurfaceIntersection'):
   if n.endswith('FileName'):v.SetStringAnalysisInput('SurfaceIntersection',n,[str(self.path/('direct-'+n+Path(v.GetStringAnalysisInput('SurfaceIntersection',n)[0]).suffix))])
  self.assertEqual(v.ExecAnalysis('SurfaceIntersection'),'')
  expected=json.loads(self.intersection(str(distribution()/'python/openvsp/openvsp/_vsp.so').encode()));data=json.loads((path.parent/checks['drawingFile']).read_text())
  self.assertEqual(self.drawings([o for p in data['parts'] for o in p['objects']]),self.drawings(expected));self.assertIn('not a mesh',data['displayNote'])
  direct=native_cfd_results.save(v,meshed=False)
  for key in ['rawCurvesFile','adaptedCurvesFile']:self.assertEqual((path.parent/checks[key]).read_bytes(),(self.path/direct[key]).read_bytes())
  for e in result['inputs']:
   if e['name'].endswith('FileName'):self.assertEqual(Path(e['values'][0]).parent.resolve(),path.parent.resolve())
  for suffix in ['.srf','.curv','.p3d']:self.assertTrue(list(path.parent.glob('*'+suffix)))
  self.assertEqual(path.read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)
 def test_empty_standalone_intersections_report_no_curves_without_mesh_quality_claims(self):
  v=self.v;inputs=[dict(name=n,index=0,type=v.INT_DATA,values=[0]) for n in ['IGESFileFlag','STEPFileFlag']]+[dict(name='SelectedSetIndex',index=0,type=v.INT_DATA,values=[3])]
  result,path=self.worker(dict(action='analysis',name='SurfaceIntersection',inputs=inputs));checks=result['cfdChecks']
  self.assertTrue(checks['available']);self.assertTrue(all(n==0 for n in checks['counts'].values()));self.assertTrue(any('no intersection or border curves' in w for w in checks['warnings']));self.assertNotIn('BADEDGE',checks['counts']);self.assertNotIn('meshFile',result)
