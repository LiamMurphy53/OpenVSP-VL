// Independent drawing route through the official CFD mesh manager, not Studio's
// per-component source-vector accessor. No geometry calculations in this test.
#include "DrawObj.h"
#include <dlfcn.h>
#include <iomanip>
#include <sstream>
#include <stdexcept>
template<class T> T lookup(void* library,const char* name){auto p=dlsym(library,name);if(!p)throw std::runtime_error(name);return reinterpret_cast<T>(p);}
extern "C" const char* native_cfd_manager_drawings(const char* engine){
 static thread_local std::string output;
 void* library=dlopen(engine,RTLD_NOW);
 try{
  if(!library)throw std::runtime_error("engine unavailable");
  void* manager=lookup<void*>(library,"_ZZN19CfdMeshMgrSingleton11getInstanceEvE8instance");
  lookup<void(*)(void*)>(library,"_ZN19CfdMeshMgrSingleton20TransferMeshSettingsEv")(manager);
  lookup<void(*)(void*)>(library,"_ZN19CfdMeshMgrSingleton21UpdateSourcesAndWakesEv")(manager);
  std::vector<DrawObj*> objects;
  lookup<void(*)(void*,std::vector<DrawObj*>&)>(library,"_ZN19CfdMeshMgrSingleton12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE")(manager,objects);
  std::ostringstream s;s << std::setprecision(17) << '[';bool first=true;
  for(auto o:objects){
   if(!o->m_Visible||o->m_PntVec.empty())continue;
   if(!first)s << ',';first=false;s << "{\"nativeType\":" << int(o->m_Type) << ",\"points\":[";
   for(size_t i=0;i<o->m_PntVec.size();++i){if(i)s << ',';auto p=o->m_PntVec[i];s << '[' << p.v[0] << ',' << p.v[1] << ',' << p.v[2] << ']';}
   s << "]}";
  }
  s << ']';output=s.str();
 }catch(const std::exception&){output="{\"error\":\"Independent native CFD drawings unavailable\"}";}
 if(library)dlclose(library);return output.c_str();
}

// Independent post-mesh observation without Studio's serializer or classification.
static const char* result_reference(const char* engine,bool meshed){
 static thread_local std::string output;void* library=dlopen(engine,RTLD_NOW);
 try{
  if(!library)throw std::runtime_error("engine unavailable");
  void* manager=lookup<void*>(library,meshed?"_ZZN19CfdMeshMgrSingleton11getInstanceEvE8instance":"_ZZN28SurfaceIntersectionSingleton11getInstanceEvE8instance");
  std::vector<DrawObj*> objects;
  lookup<void(*)(void*,std::vector<DrawObj*>&)>(library,meshed?"_ZN19CfdMeshMgrSingleton12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE":"_ZN28SurfaceIntersectionSingleton12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE")(manager,objects);
  std::ostringstream s;s << std::setprecision(17) << '[';bool first=true;
  for(auto o:objects){
   // Mesh diagnostics and the base intersection manager's curve drawings.
   const bool wanted=o->m_GeomID.find("CURVE")!=std::string::npos||o->m_GeomID.find("BADEDGE")!=std::string::npos||o->m_GeomID.find("BADTRI")!=std::string::npos||o->m_GeomID.find("BADQUAD")!=std::string::npos;
   if(!wanted)continue;
   if(!first)s << ',';first=false;s << "{\"nativeType\":" << int(o->m_Type) << ",\"points\":[";
   for(size_t i=0;i<o->m_PntVec.size();++i){if(i)s << ',';auto p=o->m_PntVec[i];s << '[' << p.v[0] << ',' << p.v[1] << ',' << p.v[2] << ']';}
   s << "]}";
  }
  s << ']';output=s.str();
 }catch(const std::exception&){output="{\"error\":\"Native result reference unavailable\"}";}
 if(library)dlclose(library);return output.c_str();
}

extern "C" const char* native_cfd_result_reference(const char* engine){return result_reference(engine,true);}
extern "C" const char* native_intersection_reference(const char* engine){return result_reference(engine,false);}
