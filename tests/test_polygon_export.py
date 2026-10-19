"""Selected polygon export matches the original component screen writer."""
import ctypes
from pathlib import Path
import subprocess
import sys
import unittest
import native_ngon
import test_native
from vsp_runtime import distribution


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python runtime.')
class NativePolygonExport(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_selected_multilevel_export_matches_original_writer_without_other_components(self):
        source=self.path/'export.cpp';library=self.path/'export.dylib'
        source.write_text(r'''#include <dlfcn.h>
#include <string>
#include <vector>
extern "C" void write(const char* engine,const char* id,const char* filename){
 void* h=dlopen(engine,RTLD_NOW);
 auto find=reinterpret_cast<void*(*)(const std::string&,const std::string&)>(dlsym(h,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_"));
 auto action=reinterpret_cast<void(*)(void*,std::string,std::vector<std::string>&)>(dlsym(h,"_ZN12NGonMeshGeom12WriteVSPGEOMENSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEERNS0_6vectorIS6_NS4_IS6_EEEE"));
 std::vector<std::string> files;action(find(id,"Independent polygon export"),filename,files);dlclose(h);
}
''')
        subprocess.run(['clang++','-std=c++17','-dynamiclib',str(source),'-o',str(library)],check=True,capture_output=True)
        write=ctypes.CDLL(str(library)).write;write.argtypes=[ctypes.c_char_p]*3;write.restype=None
        v=self.v;mesh=v.ComputeCompGeom(v.SET_ALL,False,0);native_ngon.capture_mesh(v,mesh)
        gid=native_ngon.convert(v,mesh,levels=2)
        for name,value in [('Scale',1.7),('X_Rel_Location',3.125),('Z_Rel_Rotation',17)]:v.SetParmValUpdate(gid,name,'XForm',value)
        other=v.AddGeom('POD');v.SetParmValUpdate(other,'X_Rel_Location','XForm',100)
        for level in (0,2):
            v.SetParmValUpdate(gid,'ActiveMesh','RefMesh',level);native_ngon.write(v,self.model);before=self.model.read_bytes()
            # Compare after the same cold-load lifecycle, without Studio export.
            v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();native_ngon.restore_file(v,self.model)
            result,path=self.worker(dict(action='export-geometry',kind='polygon-mesh',geom=gid))
            actual={Path(n).name:(path.parent/n).read_bytes() for n in result['files']}
            self.assertTrue(actual)
            # Native key files include the absolute output pathname. Use the
            # exact same destination rather than normalize any file contents.
            folder=(path.parent/'output').resolve()
            for p in folder.iterdir():p.unlink()
            write(str(distribution()/'python/openvsp/openvsp/_vsp.so').encode(),gid.encode(),str(folder/'polygon.vspgeom').encode())
            expected={p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()}
            self.assertEqual(actual,expected)
            self.assertEqual(self.model.read_bytes(),before)

    def test_nonpolygon_and_missing_component_reject_without_changing_project(self):
        before=self.model.read_bytes()
        for gid in (self.gid,'missing'):
            with self.subTest(gid=gid),self.assertRaises(ValueError):
                self.worker(dict(action='export-geometry',kind='polygon-mesh',geom=gid))
            self.assertEqual(self.model.read_bytes(),before)

    def test_service_packages_native_companions_without_format_field(self):
        import io,zipfile
        import native_service as service
        v=self.v;mesh=v.ComputeCompGeom(v.SET_ALL,False,0);native_ngon.capture_mesh(v,mesh)
        gid=native_ngon.convert(v,mesh);native_ngon.write(v,self.model);before=self.model.read_bytes()
        prior=service.WORK,service.MODEL
        try:
            service.WORK=self.path;service.MODEL=self.model
            filename,raw=service.export_geometry(dict(kind='polygon-mesh',geom=gid,revision=service.REVISION))
        finally:service.WORK,service.MODEL=prior
        self.assertEqual(filename,'openvsp-polygon-vspgeom.zip')
        with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
            self.assertIn('polygon.vspgeom',bundle.namelist())
            self.assertGreater(len(bundle.namelist()),1)
            self.assertTrue(all(bundle.read(n) for n in bundle.namelist()))
        self.assertEqual(self.model.read_bytes(),before)
