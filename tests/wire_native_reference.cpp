// Observe the official vehicle-level drawing list, independently of Studio's
// per-WireGeom adapter. The engine evaluates all points and connectivity.
#include "DrawObj.h"
#include <dlfcn.h>
#include <iomanip>
#include <sstream>
#include <stdexcept>
template<class T> static T lookup(void* library,const char* name){auto p=dlsym(library,name);if(!p)throw std::runtime_error(name);return reinterpret_cast<T>(p);}
extern "C" const char* native_wire_reference(const char* engine,const char* geom){
 static thread_local std::string output;void* library=dlopen(engine,RTLD_NOW);
 try{
  if(!library)throw std::runtime_error("engine unavailable");
  auto vehicle=lookup<void*(*)()>(library,"_ZN3vsp10GetVehicleEv")();
  std::vector<DrawObj*> objects;
  lookup<void(*)(void*,std::vector<DrawObj*>&)>(library,"_ZN7Vehicle12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE")(vehicle,objects);
  std::ostringstream s;s << std::setprecision(17) << "{\"surfaces\":[";bool first=true;
  for(const auto o:objects){
   if(o->m_GeomID.rfind(std::string(geom)+"_",0)!=0)continue;
   for(size_t k=0;k<o->m_PntMesh.size();++k){const auto& grid=o->m_PntMesh[k];
    if(grid.empty()||grid[0].empty())continue;
    if(!first)s << ',';first=false;
    s << "{\"rows\":" << grid.size() << ",\"cols\":" << grid[0].size() << ",\"points\":[";bool pointFirst=true;
    for(const auto& row:grid)for(const auto& p:row){if(!pointFirst)s << ',';pointFirst=false;s << '[' << p.v[0] << ',' << p.v[1] << ',' << p.v[2] << ']';}
    s << "],\"normals\":[";pointFirst=true;
    for(const auto& row:o->m_NormMesh.at(k))for(const auto& p:row){if(!pointFirst)s << ',';pointFirst=false;s << '[' << p.v[0] << ',' << p.v[1] << ',' << p.v[2] << ']';}
    s << "]}";
   }
  }
  s << "],\"paths\":[";first=true;
  for(const auto o:objects){
   if(o->m_GeomID!=std::string(geom)+"Line")continue;
   if(o->m_PntVec.size()%2)throw std::runtime_error("invalid native line pairs");
   for(size_t i=0;i<o->m_PntVec.size();i+=2){if(!first)s << ',';first=false;s << '[';
    for(size_t j=0;j<2;++j){if(j)s << ',';const auto& p=o->m_PntVec[i+j];s << '[' << p.v[0] << ',' << p.v[1] << ',' << p.v[2] << ']';}s << ']';}
  }
  s << "]}";output=s.str();
 }catch(const std::exception&){output="{\"error\":\"Independent native wire drawings unavailable\"}";}
 if(library)dlclose(library);return output.c_str();
}
