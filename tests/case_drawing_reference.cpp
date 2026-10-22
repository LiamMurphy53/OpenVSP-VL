// Test-only reader of the original evaluated case DrawObj records.
#include "DrawObj.h"
#include <dlfcn.h>
#include <sstream>
#include <iomanip>
#include <cmath>
#include <stdexcept>
extern "C" const char* case_drawings(const char* engine,const char* id){
 static std::string output;
 void* library=dlopen(engine,RTLD_NOW);
 if(!library)return nullptr;
 auto manager=dlsym(library,"_ZZN28GeometryAnalysisMgrSingleton11getInstanceEvE8instance");
 auto find=reinterpret_cast<void*(*)(void*,const std::string&)>(dlsym(library,"_ZNK28GeometryAnalysisMgrSingleton19GetGeometryAnalysisERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE"));
 auto load=reinterpret_cast<void(*)(void*,std::vector<DrawObj*>&)>(dlsym(library,"_ZN20GeometryAnalysisCase12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE"));
 if(!manager||!find||!load){dlclose(library);return nullptr;}
 void* item=find(manager,std::string(id));if(!item){dlclose(library);return nullptr;}
 std::vector<DrawObj*> objects;load(item,objects);
 std::ostringstream out;out<<std::setprecision(17)<<'[';bool first=true;
 for(auto object:objects){
  if(object->m_GeomID.rfind(id,0)!=0)continue;
  if(!first)out<<',';first=false;
  const char* kind=object->m_Type==DrawObj::VSP_LINES?"lines":object->m_Type==DrawObj::VSP_POINTS?"points":object->m_Type==DrawObj::VSP_WIRE_SHADED_TRIS?"triangles":"unsupported";
  out<<"{\"nativeID\":\""<<object->m_GeomID<<"\",\"nativeType\":"<<int(object->m_Type)<<",\"kind\":\""<<kind<<"\",\"visible\":"<<(object->m_Visible?"true":"false")<<",\"points\":[";
  for(size_t i=0;i<object->m_PntVec.size();++i){
   if(i)out<<',';auto p=object->m_PntVec[i];out<<'[';double values[]={p.x(),p.y(),p.z()};
   for(int j=0;j<3;++j){if(j)out<<',';if(std::isfinite(values[j]))out<<values[j];else out<<"null";}out<<']';
  }out<<"]}";
 }
 out<<']';output=out.str();dlclose(library);return output.c_str();
}
