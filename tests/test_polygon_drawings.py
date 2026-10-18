"""Polygon diagnostics use the original native drawing objects and visibility."""
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import unittest
import native_ngon
import test_native
import test_ngon_snapshot
from vsp_runtime import distribution


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativePolygonDrawings(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    generate=test_ngon_snapshot.NativePolygonSnapshot.generate

    def test_native_objects_open_boundary_transforms_visibility_and_reopen(self):
        headers=Path(native_ngon.__file__).parent/'native_bridge/vendor/openvsp-3.52.2'
        source=self.path/'drawing-reference.cpp';library=self.path/'drawing-reference.dylib'
        source.write_text(r'''#include "DrawObj.h"
#include "PGMesh.h"
#include "NGonLayout.h"
#include <dlfcn.h>
#include <sstream>
#include <iomanip>
extern "C" const char* drawings(const char* engine,const char* gid,int hole){
 static std::string result;void* h=dlopen(engine,RTLD_NOW);
 auto find=reinterpret_cast<void*(*)(const std::string&,const std::string&)>(dlsym(h,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_"));
 auto c=static_cast<char*>(find(gid,"Independent polygon drawing reference"));
 if(hole){auto& m=*reinterpret_cast<PGMulti*>(c+studio_ngon_layout::m_PGMulti);auto p=m.m_MeshVec[m.m_ActiveMesh];
 reinterpret_cast<void(*)(PGMesh*,PGFace*)>(dlsym(h,"_ZN6PGMesh10RemoveFaceEP6PGFace"))(p,p->m_FaceList.front());
 reinterpret_cast<void(*)(PGMesh*)>(dlsym(h,"_ZN6PGMesh11DumpGarbageEv"))(p);}
 reinterpret_cast<void(*)(void*)>(dlsym(h,"_ZN12NGonMeshGeom13UpdateDrawObjEv"))(c);
 std::vector<DrawObj*> objects;reinterpret_cast<void(*)(void*,std::vector<DrawObj*>&)>(dlsym(h,"_ZN12NGonMeshGeom12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE"))(c,objects);
 std::ostringstream s;s<<std::setprecision(17)<<'[';bool first=true;
 for(auto o:objects){bool lines=o->m_Type==DrawObj::VSP_LINES,points=o->m_Type==DrawObj::VSP_POINTS;if((!lines&&!points)||o->m_GeomID.rfind(gid,0)!=0)continue;
 if(!first)s<<',';first=false;auto color=lines?o->m_LineColor:o->m_PointColor;
 s<<"{\"nativeID\":\""<<o->m_GeomID<<"\",\"kind\":\""<<(lines?"lines":"points")<<"\",\"visible\":"<<(o->m_Visible?"true":"false")<<",\"lineWidth\":"<<o->m_LineWidth<<",\"pointSize\":"<<o->m_PointSize<<",\"color\":["<<color.x()<<','<<color.y()<<','<<color.z()<<"],\"points\":[";
 for(size_t i=0;i<o->m_PntVec.size();++i){if(i)s<<',';auto p=o->m_PntVec[i];s<<'['<<p.x()<<','<<p.y()<<','<<p.z()<<']';}s<<"]}";}
 s<<']';result=s.str();dlclose(h);return result.c_str();}
''')
        subprocess.run(['clang++','-std=c++17','-dynamiclib','-I'+str(headers),str(source),'-o',str(library)],check=True,capture_output=True)
        direct=ctypes.CDLL(str(library)).drawings;direct.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];direct.restype=ctypes.c_char_p
        v=self.v;gid=self.generate(('WING',));engine=str(distribution()/'python/openvsp/openvsp/_vsp.so').encode()
        direct(engine,gid.encode(),1)
        for name,value in [('X_Rel_Location',3.125),('Z_Rel_Rotation',31),('Scale',1.7)]:v.SetParmValUpdate(gid,name,'XForm',value)
        for enabled in (0,1):
            v.SetParmValUpdate(gid,'ShowNonManifoldEdges','Draw',enabled)
            expected=json.loads(direct(engine,gid.encode(),0));self.assertEqual(native_ngon.drawings(v,gid),expected)
            boundary=next(o for o in expected if o['nativeID']==gid+'Bad_Edges_Few')
            self.assertTrue(boundary['points']);self.assertEqual(boundary['visible'],bool(enabled));self.assertEqual(boundary['color'],[0,0,1])
            native_ngon.write(v,self.model);before=self.model.read_bytes()
            state,path=self.worker(dict(action='state'))
            actual=next(c for c in state['components'] if c['id']==gid)['referenceDrawings']
            self.assertEqual(actual,[dict(o,selectionOnly=False) for o in expected if o['visible']])
            self.assertEqual(self.model.read_bytes(),before)
            reopened,_=self.worker(dict(action='state'),path)
            self.assertEqual(next(c for c in reopened['components'] if c['id']==gid)['referenceDrawings'],actual)
