// Independent original vehicle drawing observer for point-cloud coordinates.
#include "DrawObj.h"
#include <dlfcn.h>
#include <iomanip>
#include <sstream>
#include <stdexcept>
template<class T> static T lookup(void* lib,const char* name){auto p=dlsym(lib,name);if(!p)throw std::runtime_error(name);return reinterpret_cast<T>(p);}
extern "C" const char* native_cloud_reference(const char* engine,const char* geom){
 static thread_local std::string output;void* lib=dlopen(engine,RTLD_NOW);
 try{
  if(!lib)throw std::runtime_error("engine unavailable");
  auto vehicle=lookup<void*(*)()>(lib,"_ZN3vsp10GetVehicleEv")();
  std::vector<DrawObj*> objects;
  lookup<void(*)(void*,std::vector<DrawObj*>&)>(lib,"_ZN7Vehicle12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE")(vehicle,objects);
  const DrawObj* cloud=nullptr;
  for(auto o:objects)if(o->m_GeomID==geom && o->m_Type==DrawObj::VSP_POINTS){if(cloud)throw std::runtime_error("duplicate cloud drawing");cloud=o;}
  if(!cloud)throw std::runtime_error("missing cloud drawing");
  std::ostringstream s;s << std::setprecision(17) << '[';bool first=true;
  for(const auto& p:cloud->m_PntVec){if(!first)s << ',';first=false;s << '[' << p.v[0] << ',' << p.v[1] << ',' << p.v[2] << ']';}
  s << ']';output=s.str();
 }catch(const std::exception& e){output="null";}
 if(lib)dlclose(lib);return output.c_str();
}
