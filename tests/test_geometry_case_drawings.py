"""Saved geometry-check drawings match independent original C++ DrawObj reads."""
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import unittest
import test_native
import test_geometry_cases
import native_geometry_cases
import native_worker
from vsp_runtime import distribution


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class GeometryCaseDrawings(unittest.TestCase):
    setUpClass=classmethod(test_geometry_cases.NativeGeometryCases.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    fixture=test_geometry_cases.NativeGeometryCases.fixture
    case=test_geometry_cases.NativeGeometryCases.case
    direct=test_geometry_cases.NativeGeometryCases.direct
    canonical=test_geometry_cases.NativeGeometryCases.canonical
    assertResults=test_geometry_cases.NativeGeometryCases.assertResults

    def reader(self):
        headers=Path(native_worker.__file__).parent/'native_bridge/vendor/openvsp-3.52.2'
        source=Path(__file__).with_name('case_drawing_reference.cpp');lib=self.path/'case-drawings.dylib'
        subprocess.run(['clang++','-std=c++17','-dynamiclib','-I'+str(headers),str(source),'-o',str(lib)],check=True,capture_output=True)
        fn=ctypes.CDLL(str(lib)).case_drawings;fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p];fn.restype=ctypes.c_char_p
        engine=str(distribution()/'python/openvsp/openvsp/_vsp.so').encode()
        def read(cid):
            raw=fn(engine,cid.encode());self.assertIsNotNone(raw,'Original case drawing reader must resolve its native symbols')
            return json.loads(raw)
        return read

    def check_drawing(self,data,path,cid,expected):
        summary=next(c for c in data['geometryCaseDrawings'] if c['id']==cid)
        drawing=json.loads((path.parent/summary['file']).read_text())
        self.assertEqual(drawing['nativeObjects'],expected)
        self.assertEqual(drawing['case']['id'],cid);self.assertEqual(drawing['coordinateFrame'],'Native world XYZ')
        self.assertEqual(summary['points'],sum(len(o['points']) for o in expected))
        self.assertEqual(summary['objects'],len(expected))
        displayed=[p['objects'][0] for p in drawing['parts']]
        valid=[o for o in expected if o['points'] and o['kind'] in ('points','lines','triangles') and all(all(x is not None for x in p) for p in o['points'])]
        self.assertEqual(displayed,valid);self.assertEqual(summary['displayable'],bool(valid))
        return drawing

    def test_five_calculation_families_preserve_original_drawings_and_aircraft(self):
        self.fixture();read=self.reader();v=self.v;seen=set()
        for typ in ('COMP_GEOM','PLANAR_SLICE','PROJ_AREA','MASS_PROP','EXTERNAL_INTERFERENCE'):
            with self.subTest(calculation=typ):
                cid=self.case(typ);before=self.model.read_bytes()
                # Refresh derived headless case state through the original manager.
                v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();native_geometry_cases.update(v)
                v.SetAnalysisInputDefaults('GeometryAnalysis');v.SetStringAnalysisInput('GeometryAnalysis','CaseID',[cid]);v.ExecAnalysis('GeometryAnalysis');native_worker.errors(v)
                expected=read(cid);self.assertTrue(any(o['points'] for o in expected),typ)
                results=native_worker.collect_results(v)
                data,path=self.worker(dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=[cid])]))
                self.assertResults(results,data['results']);self.assertEqual(path.read_bytes(),before)
                self.assertEqual(len(data['geometryCaseDrawings']),1)
                self.check_drawing(data,path,cid,expected);seen.update(o['kind'] for o in expected if o['points'])
        self.assertTrue({'lines','triangles'}<=seen)

    def test_all_cases_keep_individual_drawings_without_last_case_overwrite(self):
        self.fixture();read=self.reader();v=self.v
        ids=[self.case(t) for t in ('COMP_GEOM','PLANAR_SLICE','PROJ_AREA','MASS_PROP','EXTERNAL_INTERFERENCE')];before=self.model.read_bytes()
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();native_geometry_cases.update(v)
        v.SetAnalysisInputDefaults('GeometryAnalysis');v.SetStringAnalysisInput('GeometryAnalysis','CaseID',['ALL']);v.ExecAnalysis('GeometryAnalysis');native_worker.errors(v)
        expected={cid:read(cid) for cid in ids};self.assertTrue(all(any(o['points'] for o in rows) for rows in expected.values()))
        data,path=self.worker(dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=['ALL'])]))
        self.assertEqual(path.read_bytes(),before);self.assertEqual([c['id'] for c in data['geometryCaseDrawings']],ids)
        self.assertEqual(len({c['file'] for c in data['geometryCaseDrawings']}),len(ids))
        for cid in ids:self.check_drawing(data,path,cid,expected[cid])
