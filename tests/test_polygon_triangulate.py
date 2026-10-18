"""Modern triangulation compared with the original geometry-screen method."""
import ctypes
import json
import os
import tempfile
from pathlib import Path
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
import native_ngon
import test_native
import test_ngon_snapshot
from vsp_runtime import distribution
import test_triangle_project


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativePolygonTriangulate(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    generate=test_ngon_snapshot.NativePolygonSnapshot.generate

    def test_worker_matches_original_method_and_persists_complete_graph(self):
        source=self.path/'reference.cpp';library=self.path/'reference.dylib'
        source.write_text('''#include <dlfcn.h>
#include <string>
extern "C" void triangulate(const char* engine,const char* id,int report){
 void* h=dlopen(engine,RTLD_NOW);
 auto find=reinterpret_cast<void*(*)(const std::string&,const std::string&)>(dlsym(h,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_"));
 auto action=reinterpret_cast<void(*)(void*)>(dlsym(h,report?"_ZN12NGonMeshGeom6ReportEv":"_ZN12NGonMeshGeom11TriangulateEv"));
 action(find(id,"Independent native triangulation reference"));dlclose(h);
}
''')
        subprocess.run(['clang++','-std=c++17','-dynamiclib',str(source),'-o',str(library)],check=True,capture_output=True)
        direct=ctypes.CDLL(str(library)).triangulate;direct.argtypes=[ctypes.c_char_p]*2+[ctypes.c_int]
        for kinds in [('POD',),('WING',),('POD','WING')]:
            with self.subTest(kinds=kinds):
                gid=self.generate(kinds);native_ngon.write(self.v,self.model);before=self.model.read_bytes()
                # Match a fresh original-engine load, as used by the query worker.
                self.v.ClearVSPModel();self.v.ReadVSPFile(str(self.model));self.v.Update();native_ngon.restore_file(self.v,self.model)
                flush=ctypes.CDLL(None).fflush;flush(None)
                with tempfile.TemporaryFile() as captured:
                    previous=os.dup(1)
                    try:
                        os.dup2(captured.fileno(),1)
                        direct(str(distribution()/'python/openvsp/openvsp/_vsp.so').encode(),gid.encode(),1)
                    finally:flush(None);os.dup2(previous,1);os.close(previous)
                    captured.seek(0);expected_report=captured.read().decode()
                report,_=self.worker(dict(action='query',operation='polygon-report',geom=gid))
                self.assertEqual(report['text'],expected_report)
                self.assertIn('Non-manifold edges',report['text']);self.assertTrue(report['text'].endswith('Done\n'))
                self.assertEqual(self.model.read_bytes(),before)
                # Report renumbers native scratch point IDs; triangulation's
                # independent reference starts from the untouched saved project.
                self.v.ClearVSPModel();self.v.ReadVSPFile(str(self.model));self.v.Update();native_ngon.restore_file(self.v,self.model)
                direct(str(distribution()/'python/openvsp/openvsp/_vsp.so').encode(),gid.encode(),0)
                self.v.Update();expected=native_ngon.snapshot(self.v,gid)
                self.assertTrue(any(f['triNodes'] for f in expected['faces']))
                result,path=self.worker(dict(action='mutate',operation='polygon-triangulate',geom=gid))
                self.assertEqual(result['changed'],gid)
                actual=json.loads(ET.parse(path).findtext('./Vehicle/Geom/StudioPolygonSnapshot'))
                self.assertEqual(test_triangle_project.NativeTriangleProject.canonical(actual),test_triangle_project.NativeTriangleProject.canonical(expected))
                self.worker(dict(action='state'),path)
                self.assertEqual(self.model.read_bytes(),before)

    def test_wrong_geometry_rejects_without_changing_project(self):
        before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'polygon mesh'):self.worker(dict(action='mutate',operation='polygon-triangulate',geom=self.gid))
        with self.assertRaisesRegex(ValueError,'polygon mesh'):self.worker(dict(action='query',operation='polygon-report',geom=self.gid))
        self.assertEqual(self.model.read_bytes(),before)
