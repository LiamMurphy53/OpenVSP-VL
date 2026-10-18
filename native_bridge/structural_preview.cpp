// Serialize drawing points produced by the installed, unmodified OpenVSP engine.
// Native layouts come from the exact OpenVSP_3.52.2 headers; no geometry math.
#include "DrawObj.h"
#include "Parm.h"
#include "GridDensity.h"
#include "PropDriverGroup.h"
#include "WingDriverGroup.h"
#include "XSecCurveDriverGroup.h"
#include "Matrix4d.h"
#include "APIDefines.h"
#include "GeomCapLayout.h"
#include "WaveDragMgr.h"
#include "PGMesh.h"
#include "NGonLayout.h"
#include "MeshTagLayout.h"
#include "TMesh.h"
#define protected public
#include "SubSurfaceMgr.h"
#undef protected

#include "SubSurfaceTagLayout.h"
static_assert(sizeof(SubSurfaceMgrSingleton)==studio_tag_layout::size,"Native tag manager size mismatch.");
static_assert(__builtin_offsetof(SubSurfaceMgrSingleton,m_TagCombos)==studio_tag_layout::m_TagCombos,"Native tag manager field mismatch: m_TagCombos");
static_assert(__builtin_offsetof(SubSurfaceMgrSingleton,m_TagNames)==studio_tag_layout::m_TagNames,"Native tag manager field mismatch: m_TagNames");
static_assert(__builtin_offsetof(SubSurfaceMgrSingleton,m_TagIDs)==studio_tag_layout::m_TagIDs,"Native tag manager field mismatch: m_TagIDs");
static_assert(__builtin_offsetof(SubSurfaceMgrSingleton,m_CompNames)==studio_tag_layout::m_CompNames,"Native tag manager field mismatch: m_CompNames");
static_assert(__builtin_offsetof(SubSurfaceMgrSingleton,m_CompIDs)==studio_tag_layout::m_CompIDs,"Native tag manager field mismatch: m_CompIDs");
static_assert(__builtin_offsetof(SubSurfaceMgrSingleton,m_CompTypes)==studio_tag_layout::m_CompTypes,"Native tag manager field mismatch: m_CompTypes");
static_assert(__builtin_offsetof(SubSurfaceMgrSingleton,m_CompPlate)==studio_tag_layout::m_CompPlate,"Native tag manager field mismatch: m_CompPlate");
static_assert(__builtin_offsetof(SubSurfaceMgrSingleton,m_CompCopyIndex)==studio_tag_layout::m_CompCopyIndex,"Native tag manager field mismatch: m_CompCopyIndex");
static_assert(__builtin_offsetof(SubSurfaceMgrSingleton,m_CompWmin)==studio_tag_layout::m_CompWmin,"Native tag manager field mismatch: m_CompWmin");
static_assert(__builtin_offsetof(SubSurfaceMgrSingleton,m_CompUscale)==studio_tag_layout::m_CompUscale,"Native tag manager field mismatch: m_CompUscale");
static_assert(__builtin_offsetof(SubSurfaceMgrSingleton,m_CompWscale)==studio_tag_layout::m_CompWscale,"Native tag manager field mismatch: m_CompWscale");
static_assert(__builtin_offsetof(SubSurfaceMgrSingleton,m_CompThick)==studio_tag_layout::m_CompThick,"Native tag manager field mismatch: m_CompThick");
static_assert(__builtin_offsetof(SubSurfaceMgrSingleton,m_CurrSurfInd)==studio_tag_layout::m_CurrSurfInd,"Native tag manager field mismatch: m_CurrSurfInd");
static_assert(__builtin_offsetof(SubSurfaceMgrSingleton,m_TagKeys)==studio_tag_layout::m_TagKeys,"Native tag manager field mismatch: m_TagKeys");
static_assert(__builtin_offsetof(SubSurfaceMgrSingleton,m_SingleTagMap)==studio_tag_layout::m_SingleTagMap,"Native tag manager field mismatch: m_SingleTagMap");
static_assert(__builtin_offsetof(SubSurfaceMgrSingleton,m_GeomIDs)==studio_tag_layout::m_GeomIDs,"Native tag manager field mismatch: m_GeomIDs");
static_assert(__builtin_offsetof(SubSurfaceMgrSingleton,m_GeomCopySet)==studio_tag_layout::m_GeomCopySet,"Native tag manager field mismatch: m_GeomCopySet");
#include <dlfcn.h>
#include <fstream>
#include <mach-o/dyld.h>
#include <mach-o/nlist.h>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <cmath>
#include <algorithm>
#include <limits>
#include <libxml/tree.h>

// Declaration below; the implementation uses the exact named native destructor.
extern "C" const char* studio_prop_driver_combinations(const char* engine);

// Invoke the original HumanGeom preset; serialize original design-eye points.
extern "C" const char* studio_human(const char* engine,const char* geom,bool apply);

static std::string quote(const std::string& value) {
    std::ostringstream s; s << '"';
    for (unsigned char c : value) {
        if (c=='"' || c=='\\') s << '\\' << c;
        else if (c<32) s << "\\u" << std::hex << std::setw(4) << std::setfill('0') << int(c) << std::dec;
        else s << c;
    }
    s << '"'; return s.str();
}
template<class T> static T symbol(void* library, const char* name) {
    void* value=dlsym(library,name);
    if (!value) throw std::runtime_error(std::string("Native preview symbol unavailable: ")+name);
    return reinterpret_cast<T>(value);
}

namespace studio_ngon {
template<class T> void value(std::ostream& s,const T& x){s<<x;}
inline void value(std::ostream& s,const std::string& x){s<<quote(x);}
inline void value(std::ostream& s,const double& x){if(!std::isfinite(x))throw std::runtime_error("Undefined native polygon coordinate.");if(x==0 && std::signbit(x))s<<"-0.0";else s<<x;}
template<class T> void array(std::ostream& s,const T& xs){s<<'[';bool first=true;for(const auto& x:xs){if(!first)s<<',';first=false;value(s,x);}s<<']';}
template<class T> void value(std::ostream& s,const std::vector<T>& xs){array(s,xs);}
template<class T> struct Index {
    std::map<const T*,int> ids;
    std::vector<const T*> items;
    void add(const T* p){if(!p || ids.count(p))throw std::runtime_error("Invalid native polygon ownership.");ids[p]=items.size();items.push_back(p);}
    int at(const T* p)const{if(!p)return -1;auto it=ids.find(p);if(it==ids.end())throw std::runtime_error("Native polygon reference is outside live graph.");return it->second;}
    template<class C> void refs(std::ostream& s,const C& xs)const{s<<'[';bool first=true;for(auto x:xs){if(!first)s<<',';first=false;s<<at(x);}s<<']';}
    template<class C> void loops(std::ostream& s,const C& xs)const{s<<'[';bool first=true;for(const auto& x:xs){if(!first)s<<',';first=false;refs(s,x);}s<<']';}
};
template<class T> void stringMap(std::ostream& s,const T& xs){std::map<int,std::string> ordered(xs.begin(),xs.end());s<<'[';bool first=true;for(const auto& x:ordered){if(!first)s<<',';first=false;s<<'['<<x.first<<','<<quote(x.second)<<']';}s<<']';}
static std::string snapshot(const PGMulti& multi){
    Index<PGPoint> points;Index<PGNode> nodes;Index<PGEdge> edges;Index<PGFace> faces;
    for(auto p:multi.m_PointList)points.add(p);
    for(auto m:multi.m_MeshVec){if(!m)throw std::runtime_error("Missing native polygon mesh level.");for(auto p:m->m_NodeList)nodes.add(p);for(auto p:m->m_EdgeList)edges.add(p);for(auto p:m->m_FaceList)faces.add(p);}
    std::ostringstream s;s<<std::setprecision(17)<<std::boolalpha<<"{\"format\":1,\"activeMesh\":"<<multi.m_ActiveMesh<<",\"points\":[";bool first=true;
    for(auto p:points.items){if(!first)s<<',';first=false;s<<"{\"xyz\":";array(s,p->m_Pnt.v);s<<",\"id\":"<<p->m_ID<<",\"deleted\":"<<p->m_DeleteMeFlag<<",\"nodes\":";nodes.refs(s,p->m_NodeVec);s<<'}';}
    s<<"],\"nodes\":[";first=true;
    for(auto n:nodes.items){if(!first)s<<',';first=false;s<<"{\"point\":"<<points.at(n->m_Pt)<<",\"deleted\":"<<n->m_DeleteMeFlag<<",\"edges\":";edges.refs(s,n->m_EdgeVec);s<<",\"tagUW\":[";std::map<int,vec2d> ordered(n->m_TagUWMap.begin(),n->m_TagUWMap.end());bool t=true;for(const auto& pair:ordered){if(!t)s<<',';t=false;s<<'['<<pair.first<<',';array(s,pair.second.v);s<<']';}s<<"]}";}
    s<<"],\"edges\":[";first=true;
    for(auto e:edges.items){if(!first)s<<',';first=false;s<<"{\"nodes\":["<<nodes.at(e->m_N0)<<','<<nodes.at(e->m_N1)<<"],\"id\":"<<e->m_ID<<",\"deleted\":"<<e->m_DeleteMeFlag<<",\"inLoop\":"<<e->m_InLoopFlag<<",\"inCurrentLoop\":"<<e->m_InCurrentLoopFlag<<",\"faces\":";faces.refs(s,e->m_FaceVec);s<<'}';}
    s<<"],\"faces\":[";first=true;
    for(auto f:faces.items){if(!first)s<<',';first=false;s<<"{\"normal\":";array(s,f->m_Nvec.v);s<<",\"id\":"<<f->m_ID<<",\"quad\":"<<f->m_iQuad<<",\"tag\":"<<f->m_Tag<<",\"jref\":"<<f->m_jref<<",\"kref\":"<<f->m_kref<<",\"region\":"<<f->m_Region<<",\"deleted\":"<<f->m_DeleteMeFlag<<",\"parent\":"<<faces.at(f->m_Parent)<<",\"edges\":";edges.refs(s,f->m_EdgeVec);s<<",\"triNodes\":";nodes.refs(s,f->m_TriNodeVec);s<<",\"children\":";faces.refs(s,f->m_ChildVec);s<<'}';}
    s<<"],\"meshes\":[";first=true;
    for(auto m:multi.m_MeshVec){if(!first)s<<',';first=false;s<<"{\"deleted\":"<<m->m_DeleteMeFlag<<",\"nodes\":";nodes.refs(s,m->m_NodeList);s<<",\"edges\":";edges.refs(s,m->m_EdgeList);s<<",\"faces\":";faces.refs(s,m->m_FaceList);
        s<<",\"doubleBackNodes\":";nodes.refs(s,m->m_DoubleBackNode);s<<",\"edgeLoops\":";edges.loops(s,m->m_EdgeLoopVec);s<<",\"wingWakes\":";edges.loops(s,m->m_WingWakeVec);s<<",\"wingWakeParts\":";array(s,m->m_WingWakePartVec);s<<",\"bodyWakes\":";edges.loops(s,m->m_BodyWakeVec);s<<",\"bodyWakeParts\":";array(s,m->m_BodyWakePartVec);s<<",\"bodyWakeNodes\":";nodes.refs(s,m->m_BodyNodeWakeVec);s<<",\"bodyWakeNodeParts\":";array(s,m->m_BodyNodeWakePartVec);s<<",\"regions\":";faces.refs(s,m->m_Regions);s<<'}';}
    s<<"],\"tagNames\":";stringMap(s,multi.m_TagNames);s<<",\"tagIDs\":";stringMap(s,multi.m_TagIDs);
    s<<",\"thick\":";array(s,multi.m_ThickVec);s<<",\"type\":";array(s,multi.m_TypeVec);s<<",\"plate\":";array(s,multi.m_PlateVec);s<<",\"copyIndex\":";array(s,multi.m_CopyIndxVec);s<<",\"wmin\":";array(s,multi.m_WminVec);s<<",\"uscale\":";array(s,multi.m_UscaleVec);s<<",\"wscale\":";array(s,multi.m_WscaleVec);
    s<<",\"tagKeys\": [";first=true;for(const auto& xs:multi.m_TagKeys){if(!first)s<<',';first=false;array(s,xs);}s<<"],\"singleTagMap\":[";first=true;for(const auto& pair:multi.m_SingleTagMap){if(!first)s<<',';first=false;s<<'[';array(s,pair.first);s<<','<<pair.second<<']';}s<<"]}";return s.str();
}
}

extern "C" const char* studio_ngon_snapshot(const char* engine,const char* geom,const char* scaleGuard){
    static thread_local std::string output;void* library=nullptr;
    try{
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        const char* component=static_cast<const char*>(find(geom,"Studio polygon snapshot"));if(!component)throw std::runtime_error("Native polygon component unavailable.");
        void* manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");
        auto parm=symbol<Parm*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton8FindParmERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE");
        if(!scaleGuard || !*scaleGuard || reinterpret_cast<const char*>(parm(manager,std::string(scaleGuard)))!=component+studio_ngon_layout::m_ScaleFromOrig)throw std::runtime_error("Native polygon layout does not match the pinned engine.");
        output=studio_ngon::snapshot(*reinterpret_cast<const PGMulti*>(component+studio_ngon_layout::m_PGMulti));
        double matrix[16];symbol<void(*)(const void*,double*)>(library,"_ZNK8Matrix4d6getMatEPd")(component+studio_ngon_layout::m_ScaleMatrix,matrix);
        std::ostringstream extra;extra<<std::setprecision(17)<<",\"scaleMatrix\":";studio_ngon::array(extra,matrix);extra<<'}';output.pop_back();output+=extra.str();
    }catch(const std::exception& e){output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_mesh_prepare_polygon(const char* engine,const char* geom,const char* scaleGuard){
    static thread_local std::string output;void* library=nullptr;
    try{
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        char* component=static_cast<char*>(find(geom,"Studio polygon conversion setup"));if(!component)throw std::runtime_error("Native triangle mesh unavailable.");
        auto manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");auto parm=symbol<Parm*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton8FindParmERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE");
        if(!scaleGuard || !*scaleGuard || reinterpret_cast<char*>(parm(manager,std::string(scaleGuard)))!=component+studio_mesh_layout::m_ScaleFromOrig)throw std::runtime_error("Native triangle mesh layout does not match the pinned engine.");
        auto& meshes=*reinterpret_cast<std::vector<TMesh*>*>(component+studio_mesh_layout::m_TMeshVec);
        if(meshes.empty())throw std::runtime_error("Choose a triangle mesh with geometry.");
        const std::vector<std::string> surfaces;
        symbol<void(*)(bool,std::vector<TMesh*>&,const std::vector<std::string>&)>(library,"_Z10SubTagTrisbRNSt3__16vectorIP5TMeshNS_9allocatorIS2_EEEERKNS0_INS_12basic_stringIcNS_11char_traitsIcEENS3_IcEEEENS3_ISB_EEEE")(true,meshes,surfaces);
        output="{\"prepared\":true}";
    }catch(const std::exception& e){output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

namespace studio_ngon {
static SubSurfaceMgrSingleton* tagManager(void* library){
    auto guard=symbol<unsigned char*>(library,"_ZGVZN22SubSurfaceMgrSingleton11GetInstanceEvE8instance");if(!(*guard&1))throw std::runtime_error("Native tag manager is not initialized.");
    return symbol<SubSurfaceMgrSingleton*>(library,"_ZZN22SubSurfaceMgrSingleton11GetInstanceEvE8instance");
}
static void tagData(std::ostream& s,const SubSurfaceMgrSingleton& m){
    s<<"{\"names\":";stringMap(s,m.m_TagNames);s<<",\"ids\":";stringMap(s,m.m_TagIDs);s<<",\"componentNames\":";array(s,m.m_CompNames);s<<",\"componentIDs\":";array(s,m.m_CompIDs);s<<",\"types\":";array(s,m.m_CompTypes);s<<",\"plates\":";array(s,m.m_CompPlate);s<<",\"copies\":";array(s,m.m_CompCopyIndex);s<<",\"wmin\":";array(s,m.m_CompWmin);s<<",\"uscale\":";array(s,m.m_CompUscale);s<<",\"wscale\":";array(s,m.m_CompWscale);s<<",\"thick\":";array(s,m.m_CompThick);s<<",\"currentSurface\":"<<m.m_CurrSurfInd;
    s<<",\"combinations\":[";bool first=true;for(const auto& v:m.m_TagCombos){if(!first)s<<',';first=false;array(s,v);}s<<"],\"keys\":[";first=true;for(const auto& v:m.m_TagKeys){if(!first)s<<',';first=false;array(s,v);}s<<"],\"single\":[";first=true;for(const auto& p:m.m_SingleTagMap){if(!first)s<<',';first=false;s<<'[';array(s,p.first);s<<','<<p.second<<']';}
    s<<"],\"geometryIDs\":";array(s,m.m_GeomIDs);s<<",\"geometryCopies\":[";first=true;for(const auto& p:m.m_GeomCopySet){if(!first)s<<',';first=false;s<<'['<<quote(p.first)<<','<<p.second<<']';}s<<"]}";
}
static void triangleMetadata(std::ostream& s,const TTri* t,int depth,size_t& count){
    if(!t || depth>64 || ++count>10000000)throw std::runtime_error("Invalid native triangle hierarchy.");
    const TNode* corners[]={t->m_N0,t->m_N1,t->m_N2};for(auto n:corners)if(!n)throw std::runtime_error("Missing native triangle corner.");
    s<<"{\"quad\":"<<t->m_iQuad<<",\"jref\":"<<t->m_jref<<",\"kref\":"<<t->m_kref<<",\"id\":"<<t->m_ID<<",\"ignore\":"<<t->m_IgnoreTriFlag<<",\"invalid\":"<<t->m_InvalidFlag<<",\"geomID\":"<<quote(t->m_GeomID)<<",\"density\":";value(s,t->m_Density);
    s<<",\"tags\":";array(s,t->m_Tags);s<<",\"inside\":";array(s,t->m_insideSurf);s<<",\"normal\":";array(s,t->m_Norm.v);
    s<<",\"corners\":[";for(int i=0;i<3;++i){if(i)s<<',';auto n=corners[i];s<<"{\"xyz\":";array(s,n->m_Pnt.v);s<<",\"uw\":";array(s,n->m_UWPnt.v);s<<",\"xyzFlag\":"<<n->GetXYZFlag()<<",\"coordInfo\":"<<n->GetCoordInfo()<<",\"intersection\":"<<n->m_IsectFlag<<",\"id\":"<<n->m_ID<<'}';}
    s<<"],\"split\":[";bool first=true;for(auto child:t->m_SplitVec){if(!first)s<<',';first=false;triangleMetadata(s,child,depth+1,count);}s<<"]}";
}
static void grid(std::ostream& s,const std::vector<std::vector<vec3d>>& rows){s<<'[';bool first=true;for(const auto& row:rows){if(!first)s<<',';first=false;s<<'[';bool next=true;for(const auto& v:row){if(!next)s<<',';next=false;array(s,v.v);}s<<']';}s<<']';}
static std::string meshMetadata(const std::vector<TMesh*>& meshes){
    std::ostringstream s;s<<std::setprecision(17)<<std::boolalpha<<"{\"format\":2,\"meshes\":[";bool first=true;size_t triangles=0;
    for(auto m:meshes){if(!m)throw std::runtime_error("Missing native triangle mesh.");if(!first)s<<',';first=false;
        s<<"{\"origin\":"<<quote(m->m_OriginGeomID)<<",\"name\":"<<quote(m->m_NameStr)<<",\"surface\":"<<m->m_SurfNum<<",\"plate\":"<<m->m_PlateNum<<",\"copy\":"<<m->m_CopyIndex<<",\"material\":"<<m->m_MaterialID<<",\"cfdType\":"<<m->m_SurfCfdType<<",\"surfaceType\":"<<m->m_SurfType<<",\"thick\":"<<m->m_ThickSurf<<",\"flatPatch\":"<<m->m_FlatPatch<<",\"massPriority\":"<<m->m_MassPrior<<",\"density\":";value(s,m->m_Density);s<<",\"shellAreaDensity\":";value(s,m->m_ShellMassArea);s<<",\"shell\":"<<m->m_ShellFlag;
        s<<",\"wmin\":";value(s,m->m_Wmin);s<<",\"uscale\":";value(s,m->m_Uscale);s<<",\"wscale\":";value(s,m->m_Wscale);s<<",\"groups\":";array(s,m->m_InGroup);s<<",\"uwGrid\":";grid(s,m->m_UWPnts);s<<",\"xyzGrid\":";grid(s,m->m_XYZPnts);
        s<<",\"triangles\":[";bool next=true;for(auto t:m->m_TVec){if(!next)s<<',';next=false;triangleMetadata(s,t,0,triangles);}s<<"]}";
    }
    s<<"]}";return s.str();
}
}

extern "C" const char* studio_mesh_metadata(const char* engine,const char* geom,const char* scaleGuard){
    static thread_local std::string output;void* library=nullptr;
    try{
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");auto component=static_cast<const char*>(find(geom,"Studio triangle metadata"));if(!component)throw std::runtime_error("Native triangle mesh unavailable.");
        auto manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");auto parm=symbol<Parm*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton8FindParmERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE");
        if(!scaleGuard || !*scaleGuard || reinterpret_cast<const char*>(parm(manager,std::string(scaleGuard)))!=component+studio_mesh_layout::m_ScaleFromOrig)throw std::runtime_error("Native triangle mesh layout does not match the pinned engine.");
        output=studio_ngon::meshMetadata(*reinterpret_cast<const std::vector<TMesh*>*>(component+studio_mesh_layout::m_TMeshVec));double matrix[16];symbol<void(*)(const void*,double*)>(library,"_ZNK8Matrix4d6getMatEPd")(component+studio_mesh_layout::m_ScaleMatrix,matrix);std::ostringstream extra;extra<<std::setprecision(17)<<",\"scaleMatrix\":";studio_ngon::array(extra,matrix);extra<<",\"tagData\":";studio_ngon::tagData(extra,*studio_ngon::tagManager(library));extra<<'}';output.pop_back();output+=extra.str();
    }catch(const std::exception& e){output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

namespace studio_ngon {
static xmlNodePtr field(xmlNodePtr p,const char* name){xmlNodePtr result=nullptr;for(auto n=p->children;n;n=n->next)if(n->type==XML_ELEMENT_NODE && xmlStrEqual(n->name,BAD_CAST name)){if(result)throw std::runtime_error("Duplicate polygon snapshot field.");result=n;}if(!result)throw std::runtime_error(std::string("Missing polygon snapshot field: ")+name);return result;}
static std::vector<xmlNodePtr> items(xmlNodePtr p){std::vector<xmlNodePtr> out;for(auto n=p->children;n;n=n->next)if(n->type==XML_ELEMENT_NODE){if(!xmlStrEqual(n->name,BAD_CAST "item"))throw std::runtime_error("Invalid polygon snapshot list.");out.push_back(n);}return out;}
static std::string text(xmlNodePtr p){xmlChar* raw=xmlNodeGetContent(p);if(!raw)throw std::runtime_error("Missing polygon snapshot value.");std::string result(reinterpret_cast<const char*>(raw));xmlFree(raw);return result;}
static int integer(xmlNodePtr p){auto raw=text(p);size_t used=0;long long n=std::stoll(raw,&used);if(used!=raw.size() || n<std::numeric_limits<int>::min() || n>std::numeric_limits<int>::max())throw std::runtime_error("Invalid polygon snapshot integer.");return int(n);}
static double real(xmlNodePtr p){auto raw=text(p);char* end=nullptr;double n=std::strtod(raw.c_str(),&end);if(raw.empty() || end!=raw.c_str()+raw.size() || !std::isfinite(n))throw std::runtime_error("Invalid polygon snapshot number.");return n;}
static bool flag(xmlNodePtr p){int n=integer(p);if(n!=0 && n!=1)throw std::runtime_error("Invalid polygon snapshot flag.");return n;}
static std::string unhex(xmlNodePtr p){auto raw=text(p);if(raw.size()%2)throw std::runtime_error("Invalid polygon snapshot string.");std::string out;for(size_t i=0;i<raw.size();i+=2){auto digit=[](char c){if(c>='0' && c<='9')return c-'0';if(c>='a' && c<='f')return c-'a'+10;throw std::runtime_error("Invalid polygon snapshot string.");};out.push_back(char(16*digit(raw[i])+digit(raw[i+1])));}return out;}
static std::vector<int> ints(xmlNodePtr p){std::vector<int> out;for(auto n:items(p))out.push_back(integer(n));return out;}
static std::vector<double> reals(xmlNodePtr p){std::vector<double> out;for(auto n:items(p))out.push_back(real(n));return out;}
template<class T> static T* ref(int i,const std::vector<T*>& objects,bool nullable=false){if(nullable && i==-1)return nullptr;if(i<0 || size_t(i)>=objects.size() || !objects[i])throw std::runtime_error("Invalid polygon snapshot reference.");return objects[i];}
template<class T> static std::vector<T*> references(xmlNodePtr p,const std::vector<T*>& objects){std::vector<T*> out;for(int i:ints(p))out.push_back(ref(i,objects));return out;}
template<class T> static std::vector<std::vector<T*>> loops(xmlNodePtr p,const std::vector<T*>& objects){std::vector<std::vector<T*>> out;for(auto n:items(p))out.push_back(references(n,objects));return out;}
struct Stage {
    void(*destroy)(PGMulti*);PGMulti* multi;
    explicit Stage(void* library):destroy(symbol<void(*)(PGMulti*)>(library,"_ZN7PGMultiD1Ev")),multi(static_cast<PGMulti*>(::operator new(sizeof(PGMulti)))){
        try{symbol<void(*)(PGMulti*)>(library,"_ZN7PGMultiC1Ev")(multi);}catch(...){::operator delete(multi);throw;}
    }
    ~Stage(){destroy(multi);::operator delete(multi);}
};
static void restore(void* library,char* component,xmlNodePtr root){
    if(integer(field(root,"format"))!=1)throw std::runtime_error("Unsupported polygon snapshot format.");
    auto ps=items(field(root,"points")),ns=items(field(root,"nodes")),es=items(field(root,"edges")),fs=items(field(root,"faces")),ms=items(field(root,"meshes"));
    if(ps.size()+ns.size()+es.size()+fs.size()+ms.size()>10000000)throw std::runtime_error("Polygon snapshot is too large.");
    Stage stage(library);auto& multi=*stage.multi;symbol<void(*)(PGMulti*)>(library,"_ZN7PGMulti5ClearEv")(&multi);
    auto addPoint=symbol<PGPoint*(*)(PGMulti*,const vec3d&)>(library,"_ZN7PGMulti8AddPointERK5vec3d");auto addMesh=symbol<PGMesh*(*)(PGMulti*)>(library,"_ZN7PGMulti7AddMeshEv");
    auto addNode=symbol<PGNode*(*)(PGMesh*,PGPoint*)>(library,"_ZN6PGMesh7AddNodeEP7PGPoint");auto addEdge=symbol<PGEdge*(*)(PGMesh*,PGNode*,PGNode*)>(library,"_ZN6PGMesh7AddEdgeEP6PGNodeS1_");auto addFace=symbol<PGFace*(*)(PGMesh*)>(library,"_ZN6PGMesh7AddFaceEv");
    auto xyz=symbol<void(*)(void*,double,double,double)>(library,"_ZN5vec3dC1Eddd");auto uv=symbol<void(*)(void*,double,double)>(library,"_ZN5vec2dC1Edd");
    std::vector<PGPoint*> points;std::vector<PGNode*> nodes(ns.size(),nullptr);std::vector<PGEdge*> edges(es.size(),nullptr);std::vector<PGFace*> faces(fs.size(),nullptr);std::set<PGEdge*> allocatedEdges;
    for(auto p:ps){auto coords=reals(field(p,"xyz"));if(coords.size()!=3)throw std::runtime_error("Invalid polygon point.");alignas(vec3d) unsigned char storage[sizeof(vec3d)];xyz(storage,coords[0],coords[1],coords[2]);auto point=addPoint(&multi,*reinterpret_cast<vec3d*>(storage));point->m_ID=integer(field(p,"id"));point->m_DeleteMeFlag=flag(field(p,"deleted"));points.push_back(point);}
    for(auto m:ms){auto mesh=addMesh(&multi);mesh->m_DeleteMeFlag=flag(field(m,"deleted"));
        for(int i:ints(field(m,"nodes"))){if(i<0 || size_t(i)>=ns.size() || nodes[i])throw std::runtime_error("Duplicate polygon node ownership.");auto n=ns[i];nodes[i]=addNode(mesh,ref(integer(field(n,"point")),points));nodes[i]->m_DeleteMeFlag=flag(field(n,"deleted"));for(auto pair:items(field(n,"tagUW"))){auto values=items(pair);if(values.size()!=2)throw std::runtime_error("Invalid polygon UV map.");auto coords=reals(values[1]);if(coords.size()!=2)throw std::runtime_error("Invalid polygon UV coordinates.");alignas(vec2d) unsigned char storage[sizeof(vec2d)];uv(storage,coords[0],coords[1]);if(!nodes[i]->m_TagUWMap.emplace(integer(values[0]),*reinterpret_cast<vec2d*>(storage)).second)throw std::runtime_error("Duplicate polygon UV tag.");}}
        for(int i:ints(field(m,"edges"))){if(i<0 || size_t(i)>=es.size() || edges[i])throw std::runtime_error("Duplicate polygon edge ownership.");auto e=es[i];auto endpoints=ints(field(e,"nodes"));if(endpoints.size()!=2)throw std::runtime_error("Invalid polygon edge.");auto edge=addEdge(mesh,ref(endpoints[0],nodes),ref(endpoints[1],nodes));if(!allocatedEdges.insert(edge).second)throw std::runtime_error("Duplicate native polygon edge.");edges[i]=edge;edge->m_ID=integer(field(e,"id"));edge->m_DeleteMeFlag=flag(field(e,"deleted"));edge->m_InLoopFlag=flag(field(e,"inLoop"));edge->m_InCurrentLoopFlag=flag(field(e,"inCurrentLoop"));}
        for(int i:ints(field(m,"faces"))){if(i<0 || size_t(i)>=fs.size() || faces[i])throw std::runtime_error("Duplicate polygon face ownership.");faces[i]=addFace(mesh);}
    }
    for(size_t i=0;i<ps.size();++i)points[i]->m_NodeVec=references(field(ps[i],"nodes"),nodes);
    for(size_t i=0;i<ns.size();++i)ref(int(i),nodes)->m_EdgeVec=references(field(ns[i],"edges"),edges);
    for(size_t i=0;i<es.size();++i)ref(int(i),edges)->m_FaceVec=references(field(es[i],"faces"),faces);
    for(size_t i=0;i<fs.size();++i){auto f=ref(int(i),faces);auto x=fs[i];auto normal=reals(field(x,"normal"));if(normal.size()!=3)throw std::runtime_error("Invalid polygon face normal.");for(int k=0;k<3;++k)f->m_Nvec.v[k]=normal[k];
        f->m_ID=integer(field(x,"id"));f->m_iQuad=integer(field(x,"quad"));f->m_Tag=integer(field(x,"tag"));f->m_jref=integer(field(x,"jref"));f->m_kref=integer(field(x,"kref"));f->m_Region=integer(field(x,"region"));f->m_DeleteMeFlag=flag(field(x,"deleted"));f->m_Parent=ref(integer(field(x,"parent")),faces,true);f->m_EdgeVec=references(field(x,"edges"),edges);f->m_TriNodeVec=references(field(x,"triNodes"),nodes);f->m_ChildVec=references(field(x,"children"),faces);
    }
    for(size_t i=0;i<ms.size();++i){auto m=multi.m_MeshVec[i];auto x=ms[i];m->m_DoubleBackNode=references(field(x,"doubleBackNodes"),nodes);m->m_EdgeLoopVec=loops(field(x,"edgeLoops"),edges);m->m_WingWakeVec=loops(field(x,"wingWakes"),edges);m->m_WingWakePartVec=ints(field(x,"wingWakeParts"));m->m_BodyWakeVec=loops(field(x,"bodyWakes"),edges);m->m_BodyWakePartVec=ints(field(x,"bodyWakeParts"));m->m_BodyNodeWakeVec=references(field(x,"bodyWakeNodes"),nodes);m->m_BodyNodeWakePartVec=ints(field(x,"bodyWakeNodeParts"));m->m_Regions=references(field(x,"regions"),faces);}
    multi.m_ActiveMesh=integer(field(root,"activeMesh"));if(multi.m_ActiveMesh<0 || size_t(multi.m_ActiveMesh)>=ms.size())throw std::runtime_error("Invalid active polygon mesh.");
    for(auto pair:items(field(root,"tagNames"))){auto values=items(pair);if(values.size()!=2)throw std::runtime_error("Invalid polygon tag name.");multi.m_TagNames.emplace(integer(values[0]),unhex(values[1]));}
    for(auto pair:items(field(root,"tagIDs"))){auto values=items(pair);if(values.size()!=2)throw std::runtime_error("Invalid polygon tag ID.");multi.m_TagIDs.emplace(integer(values[0]),unhex(values[1]));}
    multi.m_ThickVec=ints(field(root,"thick"));multi.m_TypeVec=ints(field(root,"type"));multi.m_PlateVec=ints(field(root,"plate"));multi.m_CopyIndxVec=ints(field(root,"copyIndex"));multi.m_WminVec=reals(field(root,"wmin"));multi.m_UscaleVec=reals(field(root,"uscale"));multi.m_WscaleVec=reals(field(root,"wscale"));
    for(auto n:items(field(root,"tagKeys")))multi.m_TagKeys.push_back(ints(n));for(auto pair:items(field(root,"singleTagMap"))){auto values=items(pair);if(values.size()!=2)throw std::runtime_error("Invalid polygon tag map.");multi.m_SingleTagMap.emplace(ints(values[0]),integer(values[1]));}
    auto matrix=reals(field(root,"scaleMatrix"));if(matrix.size()!=16)throw std::runtime_error("Invalid polygon scale matrix.");
    // Resolve all native functions and validate the staged graph before replacing live ownership.
    auto check=symbol<bool(*)(PGMulti*)>(library,"_ZN7PGMulti5CheckEv");auto garbage=symbol<void(*)(PGMulti*)>(library,"_ZN7PGMulti11DumpGarbageEv");auto init=symbol<void(*)(void*,const double*)>(library,"_ZN8Matrix4d7initMatEPKd");
    if(!check(&multi))throw std::runtime_error("Native polygon graph validation failed.");auto meshCheck=symbol<bool(*)(PGMesh*)>(library,"_ZN6PGMesh5CheckEv");for(auto m:multi.m_MeshVec)if(!meshCheck(m))throw std::runtime_error("Native polygon mesh validation failed.");snapshot(multi);
    auto& destination=*reinterpret_cast<PGMulti*>(component+studio_ngon_layout::m_PGMulti);garbage(&destination);
    using std::swap;swap(destination.m_MeshVec,multi.m_MeshVec);swap(destination.m_PointList,multi.m_PointList);swap(destination.m_ActiveMesh,multi.m_ActiveMesh);swap(destination.m_TagNames,multi.m_TagNames);swap(destination.m_TagIDs,multi.m_TagIDs);swap(destination.m_ThickVec,multi.m_ThickVec);swap(destination.m_TypeVec,multi.m_TypeVec);swap(destination.m_PlateVec,multi.m_PlateVec);swap(destination.m_CopyIndxVec,multi.m_CopyIndxVec);swap(destination.m_WminVec,multi.m_WminVec);swap(destination.m_UscaleVec,multi.m_UscaleVec);swap(destination.m_WscaleVec,multi.m_WscaleVec);swap(destination.m_TagKeys,multi.m_TagKeys);swap(destination.m_SingleTagMap,multi.m_SingleTagMap);
    for(auto m:destination.m_MeshVec)m->m_PGMulti=&destination;for(auto m:multi.m_MeshVec)m->m_PGMulti=&multi;
    init(component+studio_ngon_layout::m_ScaleMatrix,matrix.data());
}
}

extern "C" const char* studio_ngon_restore(const char* engine,const char* geom,const char* scaleGuard,const char* payload){
    static thread_local std::string output;void* library=nullptr;xmlDocPtr doc=nullptr;
    try{
        if(!payload || strlen(payload)>128*1024*1024)throw std::runtime_error("Invalid polygon restore payload.");
        doc=xmlReadMemory(payload,int(strlen(payload)),"polygon-snapshot.xml",nullptr,XML_PARSE_NONET|XML_PARSE_NOBLANKS);
        if(!doc || doc->intSubset || doc->extSubset)throw std::runtime_error("Invalid polygon restore document.");auto root=xmlDocGetRootElement(doc);if(!root || !xmlStrEqual(root->name,BAD_CAST "snapshot"))throw std::runtime_error("Invalid polygon snapshot root.");
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        char* component=static_cast<char*>(find(geom,"Studio polygon restore"));if(!component)throw std::runtime_error("Native polygon component unavailable.");auto manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");auto parm=symbol<Parm*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton8FindParmERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE");
        if(!scaleGuard || !*scaleGuard || reinterpret_cast<char*>(parm(manager,std::string(scaleGuard)))!=component+studio_ngon_layout::m_ScaleFromOrig)throw std::runtime_error("Native polygon layout does not match the pinned engine.");
        studio_ngon::restore(library,component,root);output="{\"restored\":true}";
    }catch(const std::exception& e){output="{\"error\":"+quote(e.what())+"}";}
    if(doc)xmlFreeDoc(doc);if(library)dlclose(library);return output.c_str();
}

namespace studio_ngon {
struct TagTables {
    std::set<std::vector<int>> combos;std::unordered_map<int,std::string> names,ids;std::vector<std::string> componentNames,componentIDs;
    std::vector<int> types,plates,copies,thick;std::vector<double> wmin,uscale,wscale;int current;
    std::vector<std::vector<int>> keys;std::map<std::vector<int>,int> single;std::set<std::string,std::greater<std::string>> geometryIDs;std::set<std::pair<std::string,int>,PairGreaterLess> geometryCopies;
};
static void restoreTagTables(void* library,xmlNodePtr root){
    auto target=tagManager(library);TagTables stage;
    auto strings=[](xmlNodePtr n){std::vector<std::string> out;for(auto x:items(n))out.push_back(unhex(x));return out;};
    for(auto p:items(field(root,"names"))){auto xs=items(p);if(xs.size()!=2 || !stage.names.emplace(integer(xs[0]),unhex(xs[1])).second)throw std::runtime_error("Invalid native tag name table.");}
    for(auto p:items(field(root,"ids"))){auto xs=items(p);if(xs.size()!=2 || !stage.ids.emplace(integer(xs[0]),unhex(xs[1])).second)throw std::runtime_error("Invalid native tag identity table.");}
    stage.componentNames=strings(field(root,"componentNames"));stage.componentIDs=strings(field(root,"componentIDs"));stage.types=ints(field(root,"types"));stage.plates=ints(field(root,"plates"));stage.copies=ints(field(root,"copies"));stage.thick=ints(field(root,"thick"));stage.wmin=reals(field(root,"wmin"));stage.uscale=reals(field(root,"uscale"));stage.wscale=reals(field(root,"wscale"));stage.current=integer(field(root,"currentSurface"));
    const size_t n=stage.componentNames.size();if(stage.componentIDs.size()!=n || stage.types.size()!=n || stage.plates.size()!=n || stage.copies.size()!=n || stage.thick.size()!=n || stage.wmin.size()!=n || stage.uscale.size()!=n || stage.wscale.size()!=n)throw std::runtime_error("Native tag component table sizes disagree.");
    for(auto x:items(field(root,"combinations")))if(!stage.combos.insert(ints(x)).second)throw std::runtime_error("Duplicate native tag combination.");
    for(auto x:items(field(root,"keys")))stage.keys.push_back(ints(x));
    for(auto x:items(field(root,"single"))){auto xs=items(x);if(xs.size()!=2 || !stage.single.emplace(ints(xs[0]),integer(xs[1])).second)throw std::runtime_error("Invalid native single-tag table.");}
    for(auto x:strings(field(root,"geometryIDs")))if(!stage.geometryIDs.insert(x).second)throw std::runtime_error("Duplicate native tag geometry.");
    for(auto x:items(field(root,"geometryCopies"))){auto xs=items(x);if(xs.size()!=2 || !stage.geometryCopies.emplace(unhex(xs[0]),integer(xs[1])).second)throw std::runtime_error("Invalid native tag symmetry table.");}
    // No allocation or parsing follows these swaps into original native tables.
    target->m_TagCombos.swap(stage.combos);target->m_TagNames.swap(stage.names);target->m_TagIDs.swap(stage.ids);target->m_CompNames.swap(stage.componentNames);target->m_CompIDs.swap(stage.componentIDs);target->m_CompTypes.swap(stage.types);target->m_CompPlate.swap(stage.plates);target->m_CompCopyIndex.swap(stage.copies);target->m_CompThick.swap(stage.thick);target->m_CompWmin.swap(stage.wmin);target->m_CompUscale.swap(stage.uscale);target->m_CompWscale.swap(stage.wscale);target->m_CurrSurfInd=stage.current;target->m_TagKeys.swap(stage.keys);target->m_SingleTagMap.swap(stage.single);target->m_GeomIDs.swap(stage.geometryIDs);target->m_GeomCopySet.swap(stage.geometryCopies);
}
struct TriangleStages {
    void(*destroy)(TMesh*);void(*construct)(TMesh*);void(*copy)(TMesh*,TMesh*);std::vector<TMesh*> values;
    TriangleStages(void* library,size_t count):destroy(symbol<void(*)(TMesh*)>(library,"_ZN5TMeshD1Ev")),construct(symbol<void(*)(TMesh*)>(library,"_ZN5TMeshC1Ev")),copy(symbol<void(*)(TMesh*,TMesh*)>(library,"_ZN5TMesh4copyEPS_")){values.reserve(count);}
    TMesh* add(TMesh* source,void(*operation)(TMesh*,TMesh*)=nullptr){auto p=static_cast<TMesh*>(::operator new(sizeof(TMesh)));try{construct(p);}catch(...){::operator delete(p);throw;}values.push_back(p);(operation?operation:copy)(p,source);return p;}
    ~TriangleStages(){for(auto p:values){destroy(p);::operator delete(p);}}
};
static bool sameDouble(double a,double b){return a==b && (a!=0 || std::signbit(a)==std::signbit(b));}
static void sameGeometry(const std::vector<double>& values,const double* actual){if(values.size()!=3)throw std::runtime_error("Invalid triangle metadata coordinate.");for(int k=0;k<3;++k)if(!sameDouble(values[k],actual[k]))throw std::runtime_error("Triangle metadata does not match native geometry.");}
static std::vector<std::vector<vec3d>> gridValues(void* library,xmlNodePtr node){
    auto construct=symbol<void(*)(void*,double,double,double)>(library,"_ZN5vec3dC1Eddd");std::vector<std::vector<vec3d>> out;
    for(auto row:items(node)){out.emplace_back();for(auto p:items(row)){auto coords=reals(p);if(coords.size()!=3)throw std::runtime_error("Invalid triangle interpolation grid.");alignas(vec3d) unsigned char storage[sizeof(vec3d)];construct(storage,coords[0],coords[1],coords[2]);out.back().push_back(*reinterpret_cast<vec3d*>(storage));}}
    return out;
}

extern "C" const char* studio_mesh_restore_tags(const char* engine,const char* geom,const char* scaleGuard,const char* payload){
    static thread_local std::string output;void* library=nullptr;xmlDocPtr doc=nullptr;
    try{
        if(!payload || strlen(payload)>128*1024*1024)throw std::runtime_error("Invalid native tag payload.");doc=xmlReadMemory(payload,int(strlen(payload)),"triangle-tags.xml",nullptr,XML_PARSE_NONET|XML_PARSE_NOBLANKS);if(!doc || doc->intSubset || doc->extSubset)throw std::runtime_error("Invalid native tag document.");auto root=xmlDocGetRootElement(doc);if(!root || !xmlStrEqual(root->name,BAD_CAST "snapshot"))throw std::runtime_error("Invalid native tag root.");
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");char* component=static_cast<char*>(find(geom,"Studio triangle tag restoration"));if(!component)throw std::runtime_error("Native triangle mesh unavailable.");auto manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");auto parm=symbol<Parm*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton8FindParmERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE");
        if(!scaleGuard || !*scaleGuard || reinterpret_cast<char*>(parm(manager,std::string(scaleGuard)))!=component+studio_mesh_layout::m_ScaleFromOrig)throw std::runtime_error("Native triangle mesh layout does not match the pinned engine.");studio_ngon::restoreTagTables(library,root);output="{\"prepared\":true,\"restoredTagData\":true}";
    }catch(const std::exception& e){output="{\"error\":"+quote(e.what())+"}";}
    if(doc)xmlFreeDoc(doc);if(library)dlclose(library);return output.c_str();
}
static void triangleFields(TTri* stage,const TTri* source,xmlNodePtr node){
    if(!items(field(node,"split")).empty() || !source->m_SplitVec.empty())throw std::runtime_error("Triangle split hierarchy must be flattened by the original engine before metadata restoration.");
    sameGeometry(reals(field(node,"normal")),source->m_Norm.v);auto corners=items(field(node,"corners"));if(corners.size()!=3)throw std::runtime_error("Invalid triangle metadata corners.");
    const TNode* original[]={source->m_N0,source->m_N1,source->m_N2};TNode* target[]={stage->m_N0,stage->m_N1,stage->m_N2};
    for(int i=0;i<3;++i){auto n=corners[i];if(!original[i] || !target[i])throw std::runtime_error("Missing native triangle corner.");sameGeometry(reals(field(n,"xyz")),original[i]->m_Pnt.v);auto uw=reals(field(n,"uw"));if(uw.size()!=3)throw std::runtime_error("Invalid triangle UV metadata.");for(int k=0;k<3;++k)target[i]->m_UWPnt.v[k]=uw[k];target[i]->SetXYZFlag(flag(field(n,"xyzFlag")));int info=integer(field(n,"coordInfo"));if(info<0 || info>3)throw std::runtime_error("Invalid native triangle coordinate flags.");target[i]->SetCoordInfo(info);target[i]->m_IsectFlag=integer(field(n,"intersection"));target[i]->m_ID=integer(field(n,"id"));}
    stage->m_iQuad=integer(field(node,"quad"));stage->m_jref=integer(field(node,"jref"));stage->m_kref=integer(field(node,"kref"));stage->m_ID=integer(field(node,"id"));stage->m_IgnoreTriFlag=flag(field(node,"ignore"));stage->m_InvalidFlag=flag(field(node,"invalid"));stage->m_GeomID=unhex(field(node,"geomID"));stage->m_Density=real(field(node,"density"));stage->m_Tags=ints(field(node,"tags"));stage->m_insideSurf.clear();for(auto n:items(field(node,"inside")))stage->m_insideSurf.push_back(flag(n));
}
static bool sameNodeMetadata(const TNode* a,const TNode* b){for(int k=0;k<3;++k)if(!sameDouble(a->m_UWPnt.v[k],b->m_UWPnt.v[k]))return false;return a->m_ID==b->m_ID && a->m_IsectFlag==b->m_IsectFlag && a->GetXYZFlag()==b->GetXYZFlag() && a->GetCoordInfo()==b->GetCoordInfo();}
static void commitNodeMetadata(TNode* to,const TNode* from){for(int k=0;k<3;++k)to->m_UWPnt.v[k]=from->m_UWPnt.v[k];to->m_ID=from->m_ID;to->m_IsectFlag=from->m_IsectFlag;to->SetXYZFlag(from->GetXYZFlag());to->SetCoordInfo(from->GetCoordInfo());}
static void restoreMeshMetadata(void* library,char* component,xmlNodePtr root){
    if(integer(field(root,"format"))!=2)throw std::runtime_error("Unsupported triangle metadata format.");auto records=items(field(root,"meshes"));auto& meshes=*reinterpret_cast<std::vector<TMesh*>*>(component+studio_mesh_layout::m_TMeshVec);
    if(records.size()!=meshes.size())throw std::runtime_error("Triangle metadata mesh count does not match native geometry.");
    auto matrix=reals(field(root,"scaleMatrix"));if(matrix.size()!=16)throw std::runtime_error("Invalid triangle scale matrix.");auto init=symbol<void(*)(void*,const double*)>(library,"_ZN8Matrix4d7initMatEPKd");TriangleStages stages(library,meshes.size());std::map<const TNode*,const TNode*> aliases;
    for(size_t i=0;i<meshes.size();++i){auto source=meshes[i];if(!source)throw std::runtime_error("Missing native triangle mesh.");auto record=records[i];auto tris=items(field(record,"triangles"));if(tris.size()!=source->m_TVec.size())throw std::runtime_error("Triangle metadata count does not match native geometry.");auto stage=stages.add(source);
        stage->m_OriginGeomID=unhex(field(record,"origin"));stage->m_NameStr=unhex(field(record,"name"));stage->m_SurfNum=integer(field(record,"surface"));stage->m_PlateNum=integer(field(record,"plate"));stage->m_CopyIndex=integer(field(record,"copy"));stage->m_MaterialID=integer(field(record,"material"));stage->m_SurfCfdType=integer(field(record,"cfdType"));stage->m_SurfType=integer(field(record,"surfaceType"));stage->m_ThickSurf=integer(field(record,"thick"));stage->m_FlatPatch=flag(field(record,"flatPatch"));stage->m_MassPrior=integer(field(record,"massPriority"));stage->m_Density=real(field(record,"density"));stage->m_ShellMassArea=real(field(record,"shellAreaDensity"));stage->m_ShellFlag=flag(field(record,"shell"));stage->m_Wmin=real(field(record,"wmin"));stage->m_Uscale=real(field(record,"uscale"));stage->m_Wscale=real(field(record,"wscale"));stage->m_InGroup=ints(field(record,"groups"));stage->m_UWPnts=gridValues(library,field(record,"uwGrid"));stage->m_XYZPnts=gridValues(library,field(record,"xyzGrid"));
        for(size_t j=0;j<tris.size();++j){triangleFields(stage->m_TVec[j],source->m_TVec[j],tris[j]);TNode* old[]={source->m_TVec[j]->m_N0,source->m_TVec[j]->m_N1,source->m_TVec[j]->m_N2};TNode* fresh[]={stage->m_TVec[j]->m_N0,stage->m_TVec[j]->m_N1,stage->m_TVec[j]->m_N2};for(int k=0;k<3;++k){auto found=aliases.emplace(old[k],fresh[k]);if(!found.second && !sameNodeMetadata(found.first->second,fresh[k]))throw std::runtime_error("Conflicting metadata for a shared native triangle corner.");}}
    }
    // Every parse, native clone allocation and geometry/alias check is complete.
    // Preserve native node/triangle ownership and all existing edge references.
    for(size_t i=0;i<meshes.size();++i){auto to=meshes[i];auto from=stages.values[i];to->m_OriginGeomID.swap(from->m_OriginGeomID);to->m_NameStr.swap(from->m_NameStr);to->m_SurfNum=from->m_SurfNum;to->m_PlateNum=from->m_PlateNum;to->m_CopyIndex=from->m_CopyIndex;to->m_MaterialID=from->m_MaterialID;to->m_SurfCfdType=from->m_SurfCfdType;to->m_SurfType=from->m_SurfType;to->m_ThickSurf=from->m_ThickSurf;to->m_FlatPatch=from->m_FlatPatch;to->m_MassPrior=from->m_MassPrior;to->m_Density=from->m_Density;to->m_ShellMassArea=from->m_ShellMassArea;to->m_ShellFlag=from->m_ShellFlag;to->m_Wmin=from->m_Wmin;to->m_Uscale=from->m_Uscale;to->m_Wscale=from->m_Wscale;to->m_InGroup.swap(from->m_InGroup);to->m_UWPnts.swap(from->m_UWPnts);to->m_XYZPnts.swap(from->m_XYZPnts);
        for(size_t j=0;j<to->m_TVec.size();++j){auto a=to->m_TVec[j];auto b=from->m_TVec[j];a->m_iQuad=b->m_iQuad;a->m_jref=b->m_jref;a->m_kref=b->m_kref;a->m_ID=b->m_ID;a->m_IgnoreTriFlag=b->m_IgnoreTriFlag;a->m_InvalidFlag=b->m_InvalidFlag;a->m_GeomID.swap(b->m_GeomID);a->m_Density=b->m_Density;a->m_Tags.swap(b->m_Tags);a->m_insideSurf.swap(b->m_insideSurf);}
    }
    for(const auto& pair:aliases)commitNodeMetadata(const_cast<TNode*>(pair.first),pair.second);
    init(component+studio_mesh_layout::m_ScaleMatrix,matrix.data());
}
}

extern "C" const char* studio_mesh_restore_metadata(const char* engine,const char* geom,const char* scaleGuard,const char* payload){
    static thread_local std::string output;void* library=nullptr;xmlDocPtr doc=nullptr;
    try{
        if(!payload || strlen(payload)>128*1024*1024)throw std::runtime_error("Invalid triangle metadata payload.");doc=xmlReadMemory(payload,int(strlen(payload)),"triangle-metadata.xml",nullptr,XML_PARSE_NONET|XML_PARSE_NOBLANKS);if(!doc || doc->intSubset || doc->extSubset)throw std::runtime_error("Invalid triangle metadata document.");auto root=xmlDocGetRootElement(doc);if(!root || !xmlStrEqual(root->name,BAD_CAST "snapshot"))throw std::runtime_error("Invalid triangle metadata root.");
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");char* component=static_cast<char*>(find(geom,"Studio triangle metadata restoration"));if(!component)throw std::runtime_error("Native triangle mesh unavailable.");auto manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");auto parm=symbol<Parm*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton8FindParmERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE");
        if(!scaleGuard || !*scaleGuard || reinterpret_cast<char*>(parm(manager,std::string(scaleGuard)))!=component+studio_mesh_layout::m_ScaleFromOrig)throw std::runtime_error("Native triangle mesh layout does not match the pinned engine.");studio_ngon::restoreMeshMetadata(library,component,root);output="{\"restored\":true}";
    }catch(const std::exception& e){output="{\"error\":"+quote(e.what())+"}";}
    if(doc)xmlFreeDoc(doc);if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_mesh_project_data(const char* engine,const char* geom,const char* scaleGuard){
    static thread_local std::string output;void* library=nullptr;xmlNodePtr root=nullptr;xmlBufferPtr buffer=nullptr;void(*freeNode)(xmlNodePtr)=nullptr;void(*freeBuffer)(xmlBufferPtr)=nullptr;
    try{
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");auto component=static_cast<const char*>(find(geom,"Studio canonical triangle project"));if(!component)throw std::runtime_error("Native triangle mesh unavailable.");auto manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");auto parm=symbol<Parm*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton8FindParmERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE");
        if(!scaleGuard || !*scaleGuard || reinterpret_cast<const char*>(parm(manager,std::string(scaleGuard)))!=component+studio_mesh_layout::m_ScaleFromOrig)throw std::runtime_error("Native triangle mesh layout does not match the pinned engine.");
        const auto& meshes=*reinterpret_cast<const std::vector<TMesh*>*>(component+studio_mesh_layout::m_TMeshVec);studio_ngon::TriangleStages stages(library,meshes.size());auto flatten=symbol<void(*)(TMesh*,TMesh*)>(library,"_ZN5TMesh11CopyFlattenEPS_");for(auto m:meshes){if(!m)throw std::runtime_error("Missing native triangle mesh.");stages.add(m,flatten);}
        // Use the installed engine's own XML implementation and allocator as
        // well as its TMesh encoder; no triangle serialization is reimplemented.
        auto create=symbol<xmlNodePtr(*)(xmlNsPtr,const xmlChar*)>(library,"xmlNewNode");auto child=symbol<xmlNodePtr(*)(xmlNodePtr,xmlNsPtr,const xmlChar*,const xmlChar*)>(library,"xmlNewTextChild");freeNode=symbol<void(*)(xmlNodePtr)>(library,"xmlFreeNode");freeBuffer=symbol<void(*)(xmlBufferPtr)>(library,"xmlBufferFree");auto makeBuffer=symbol<xmlBufferPtr(*)()>(library,"xmlBufferCreate");auto dump=symbol<int(*)(xmlBufferPtr,xmlDocPtr,xmlNodePtr,int,int)>(library,"xmlNodeDump");auto content=symbol<const xmlChar*(*)(const xmlBuffer*)>(library,"xmlBufferContent");auto length=symbol<int(*)(const xmlBuffer*)>(library,"xmlBufferLength");auto encode=symbol<xmlNodePtr(*)(TMesh*,xmlNodePtr&)>(library,"_ZN5TMesh9EncodeXmlERP8_xmlNode");
        root=create(nullptr,BAD_CAST "MeshGeom");if(!root)throw std::runtime_error("Could not allocate native mesh XML.");auto count=std::to_string(stages.values.size());if(!child(root,nullptr,BAD_CAST "Num_Meshes",BAD_CAST count.c_str()))throw std::runtime_error("Could not encode native mesh count.");for(auto m:stages.values)encode(m,root);buffer=makeBuffer();if(!buffer || dump(buffer,nullptr,root,0,1)<0)throw std::runtime_error("Could not encode native triangle project data.");std::string xml(reinterpret_cast<const char*>(content(buffer)),length(buffer));
        auto metadata=studio_ngon::meshMetadata(stages.values);double matrix[16];symbol<void(*)(const void*,double*)>(library,"_ZNK8Matrix4d6getMatEPd")(component+studio_mesh_layout::m_ScaleMatrix,matrix);std::ostringstream extra;extra<<std::setprecision(17)<<",\"scaleMatrix\":";studio_ngon::array(extra,matrix);extra<<'}';metadata.pop_back();metadata+=extra.str();output="{\"metadata\":"+metadata+",\"xml\":"+quote(xml)+"}";
    }catch(const std::exception& e){output="{\"error\":"+quote(e.what())+"}";}
    if(buffer && freeBuffer)freeBuffer(buffer);if(root && freeNode)freeNode(root);if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_ngon_action(const char* engine,const char* geom,const char* scaleGuard,const char* operation){
    static thread_local std::string output;void* library=nullptr;
    try{
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        auto component=static_cast<char*>(find(geom,"Studio polygon triangulation"));if(!component)throw std::runtime_error("Native polygon component unavailable.");
        auto manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");auto parm=symbol<Parm*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton8FindParmERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE");
        if(!scaleGuard || !*scaleGuard || reinterpret_cast<char*>(parm(manager,std::string(scaleGuard)))!=component+studio_ngon_layout::m_ScaleFromOrig)throw std::runtime_error("Native polygon layout does not match the pinned engine.");
        auto& multi=*reinterpret_cast<PGMulti*>(component+studio_ngon_layout::m_PGMulti);
        if(multi.m_ActiveMesh<0 || static_cast<size_t>(multi.m_ActiveMesh)>=multi.m_MeshVec.size() || !multi.m_MeshVec[multi.m_ActiveMesh])throw std::runtime_error("Choose an available polygon mesh level.");
        if(std::string(operation?operation:"")=="triangulate")symbol<void(*)(void*)>(library,"_ZN12NGonMeshGeom11TriangulateEv")(component);
        else if(std::string(operation?operation:"")=="report")symbol<void(*)(void*)>(library,"_ZN12NGonMeshGeom6ReportEv")(component);
        else if(std::string(operation?operation:"")=="drawings"){
            symbol<void(*)(void*)>(library,"_ZN12NGonMeshGeom13UpdateDrawObjEv")(component);
            std::vector<DrawObj*> objects;symbol<void(*)(void*,std::vector<DrawObj*>&)>(library,"_ZN12NGonMeshGeom12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE")(component,objects);
            std::ostringstream s;s<<std::setprecision(17)<<'[';bool first=true;
            for(auto object:objects){
                bool lines=object->m_Type==DrawObj::VSP_LINES,points=object->m_Type==DrawObj::VSP_POINTS;
                if((!lines&&!points)||object->m_GeomID.rfind(std::string(geom),0)!=0)continue;
                if(!first)s<<',';first=false;const auto& color=lines?object->m_LineColor:object->m_PointColor;
                s<<"{\"nativeID\":"<<quote(object->m_GeomID)<<",\"kind\":"<<quote(lines?"lines":"points")<<",\"visible\":"<<(object->m_Visible?"true":"false")<<",\"lineWidth\":"<<object->m_LineWidth<<",\"pointSize\":"<<object->m_PointSize<<",\"color\":["<<color.x()<<','<<color.y()<<','<<color.z()<<"],\"points\":[";
                for(size_t i=0;i<object->m_PntVec.size();++i){if(i)s<<',';const auto& p=object->m_PntVec[i];s<<'['<<p.x()<<','<<p.y()<<','<<p.z()<<']';}s<<"]}";
            }s<<']';output=s.str();
        }
        else throw std::runtime_error("Unknown native polygon action.");
        if(std::string(operation?operation:"")!="drawings")output="{\"complete\":true}";
    }catch(const std::exception& e){output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// Offsets are compiler-generated from the complete pinned Geom declaration.
// Check native Parm addresses before accessing either private result vector.
extern "C" const char* studio_cap_results(const char* engine,const char* geom,const char* const* guards,int count) {
    static thread_local std::string output;void* library=nullptr;
    try {
        if(count<0)throw std::runtime_error("Invalid native surface count.");
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        auto component=static_cast<const char*>(find(std::string(geom),"Studio end-cap results"));
        if(!component)throw std::runtime_error("Native component unavailable.");
        void* manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");
        auto parm=symbol<Parm*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton8FindParmERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE");
        using namespace studio_cap_layout;
        const std::size_t offsets[]={m_CapUMinOption,m_CapUMaxOption,m_CapUMinTess,m_TessU,m_TessW};
        for(int i=0;i<5;++i) {
            if(!guards[i] || !*guards[i] || reinterpret_cast<const char*>(parm(manager,std::string(guards[i])))!=component+offsets[i])
                throw std::runtime_error("Native end-cap layout does not match the pinned engine.");
        }
        std::ostringstream s;s<<'[';
        for(int end=0;end<2;++end){
            if(end)s<<',';
            const auto& flags=*reinterpret_cast<const std::vector<bool>*>(component+(end?m_CapUMaxSuccess:m_CapUMinSuccess));
            if(flags.empty()){s<<"null";continue;}
            if(flags.size()!=static_cast<std::size_t>(count))throw std::runtime_error("Native end-cap results do not match the surface count.");
            s<<'[';
            for(int i=0;i<count;++i){if(i)s<<',';s<<(flags[i]?"true":"false");}
            s<<']';
        }
        s<<']';output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);
    return output.c_str();
}

// The inline source getter has no emitted symbol. Read the reference through
// the original ConformalGeom XML encoder; no class layout offsets are used.
extern "C" const char* studio_conformal_source(const char* engine,const char* geom,const char* parent,bool apply) {
    static thread_local std::string output;void* library=nullptr;xmlNodePtr node=nullptr;
    void(*freeNode)(xmlNodePtr)=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* component=find(std::string(geom),"Studio conformal source");
        if(!component)throw std::runtime_error("Native conformal component unavailable.");
        if(apply)symbol<bool(*)(void*,const std::string&)>(library,"_ZN13ConformalGeom18SetConformalParentERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(component,std::string(parent));
        auto create=symbol<xmlNodePtr(*)(xmlNsPtr,const xmlChar*)>(library,"xmlNewNode");
        freeNode=symbol<void(*)(xmlNodePtr)>(library,"xmlFreeNode");
        node=create(nullptr,BAD_CAST "StudioConformalSource");
        if(!node)throw std::runtime_error("Could not allocate native source reference inspection.");
        auto encoded=symbol<xmlNodePtr(*)(void*,xmlNodePtr&)>(library,"_ZN13ConformalGeom9EncodeXmlERP8_xmlNode")(component,node);
        std::string source;bool found=false;
        if(encoded)for(auto child=encoded->children;child;child=child->next){
            if(child->type!=XML_ELEMENT_NODE || std::string(reinterpret_cast<const char*>(child->name))!="ConformalParentID")continue;
            auto content=symbol<xmlChar*(*)(const xmlNode*)>(library,"xmlNodeGetContent")(child);
            if(content){source=reinterpret_cast<const char*>(content);(*symbol<xmlFreeFunc*>(library,"xmlFree"))(content);}
            found=true;break;
        }
        if(!found)throw std::runtime_error("Original conformal encoder did not return its source reference.");
        output="{\"source\":"+quote(source)+"}";
    } catch(const std::exception& e) {output="{\"error\":"+quote(e.what())+"}";}
    if(node&&freeNode)freeNode(node);
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_hinge_drawings(const char* engine,const char* geom) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* component=find(std::string(geom),"Studio hinge drawing inspection");
        if(!component)throw std::runtime_error("Native hinge unavailable.");
        symbol<void(*)(void*)>(library,"_ZN9HingeGeom13UpdateDrawObjEv")(component);
        std::vector<DrawObj*> objects;
        symbol<void(*)(void*,std::vector<DrawObj*>&)>(library,"_ZN9HingeGeom12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE")(component,objects);
        std::ostringstream s;s<<std::setprecision(17)<<'[';bool first=true;
        for(const auto object:objects){
            const char* kind=object->m_Type==DrawObj::VSP_LINES?"lines":object->m_Type==DrawObj::VSP_POINTS?"points":object->m_Type==DrawObj::VSP_SHADED_TRIS?"triangles":nullptr;
            if(!kind || object->m_GeomID.rfind(std::string(geom),0)!=0)continue;
            if(!first)s<<',';first=false;
            const auto& color=object->m_Type==DrawObj::VSP_LINES?object->m_LineColor:object->m_PointColor;
            s<<"{\"nativeID\":"<<quote(object->m_GeomID)<<",\"nativeType\":"<<int(object->m_Type)<<",\"kind\":"<<quote(kind)<<",\"visible\":"<<(object->m_Visible?"true":"false")<<",\"color\":["<<(object->m_Type==DrawObj::VSP_SHADED_TRIS?object->m_MaterialInfo.Diffuse[0]:color.x())<<','<<(object->m_Type==DrawObj::VSP_SHADED_TRIS?object->m_MaterialInfo.Diffuse[1]:color.y())<<','<<(object->m_Type==DrawObj::VSP_SHADED_TRIS?object->m_MaterialInfo.Diffuse[2]:color.z())<<"],\"points\":[";
            for(size_t i=0;i<object->m_PntVec.size();++i){const auto& p=object->m_PntVec[i];if(i)s<<',';s<<'['<<p.x()<<','<<p.y()<<','<<p.z()<<']';}
            s<<"]}";
        }
        s<<']';output=s.str();
    } catch(const std::exception& e) {output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_human(const char* engine,const char* geom,bool apply) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* component=find(std::string(geom),"Studio human controls");
        if(!component)throw std::runtime_error("Native human unavailable.");
        if(apply)symbol<void(*)(void*)>(library,"_ZN9HumanGeom9SetPresetEv")(component);
        std::vector<vec3d> eyes;
        if(!apply)symbol<void(*)(void*,std::vector<vec3d>&)>(library,"_ZNK9HumanGeom15GetDesignEyeVecERNSt3__16vectorI5vec3dNS0_9allocatorIS2_EEEE")(component,eyes);
        std::ostringstream s;s<<std::setprecision(17)<<"{\"eyes\":[";
        for(size_t i=0;i<eyes.size();++i){if(i)s<<',';s<<'['<<eyes[i].x()<<','<<eyes[i].y()<<','<<eyes[i].z()<<']';}
        s<<"],\"skeleton\":[";
        if(!apply){
            symbol<void(*)(void*)>(library,"_ZN9HumanGeom13UpdateDrawObjEv")(component);
            std::vector<DrawObj*> objects;
            symbol<void(*)(void*,std::vector<DrawObj*>&)>(library,"_ZN9HumanGeom12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE")(component,objects);
            bool first=true;
            for(const auto object:objects){
                if(object->m_Type!=DrawObj::VSP_LINES || object->m_GeomID.rfind(std::string(geom)+"Feature_",0)!=0)continue;
                if(!first)s<<',';first=false;
                s<<"{\"nativeID\":"<<quote(object->m_GeomID)<<",\"nativeType\":"<<int(object->m_Type)<<",\"kind\":\"lines\",\"visible\":"<<(object->m_Visible?"true":"false")<<",\"points\":[";
                for(size_t i=0;i<object->m_PntVec.size();++i){const auto& p=object->m_PntVec[i];if(i)s<<',';s<<'['<<p.x()<<','<<p.y()<<','<<p.z()<<']';}
                s<<"]}";
            }
        }
        s<<"]}";output=s.str();
    } catch(const std::exception& e) {output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// Execute the original saved-database interrogation without regenerating the
// aerodynamic setup. Python changes only the saved cutting-plane records.
extern "C" const char* studio_flow_interrogate(const char* engine) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN19VSPAEROMgrSingleton11getInstanceEvE8instance");
        symbol<void(*)(void*)>(library,"_ZN19VSPAEROMgrSingleton15UpdateFilenamesEv")(manager);
        symbol<void(*)(void*,FILE*)>(library,"_ZN19VSPAEROMgrSingleton21ExecuteQuadTreeSlicerEP7__sFILE")(manager,stdout);
        output="{}";
    } catch(const std::exception& e) {output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// Vehicle Update does not update GeometryAnalysisMgr cases. Call the official
// update used by the native case editor for vectors, symmetry and activity.
extern "C" const char* studio_geometry_cases_update(const char* engine) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN28GeometryAnalysisMgrSingleton11getInstanceEvE8instance");
        symbol<void(*)(void*)>(library,"_ZN28GeometryAnalysisMgrSingleton6UpdateEv")(manager);
        output="{}";
    } catch(const std::exception& e) {output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// Execute the installed saved-case method or copy its evaluated native mesh.
// C++ string ABI matches the installed arm64 engine and this adapter's libc++.
extern "C" const char* studio_geometry_case_action(const char* engine,const char* caseid,int action) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN28GeometryAnalysisMgrSingleton11getInstanceEvE8instance");
        void* item=symbol<void*(*)(void*,const std::string&)>(library,"_ZNK28GeometryAnalysisMgrSingleton19GetGeometryAnalysisERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(manager,std::string(caseid));
        if(!item)throw std::runtime_error("Native geometry check unavailable.");
        if(action!=0&&action!=1)throw std::runtime_error("Unknown native case action.");
        auto method=symbol<std::string(*)(void*)>(library,action==0?"_ZN20GeometryAnalysisCase8EvaluateEv":"_ZN20GeometryAnalysisCase12MakeMeshGeomEv");
        output="{\"id\":"+quote(method(item))+"}";
    } catch(const std::exception& e) {output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// Retain the original case's already evaluated drawing coordinates.
extern "C" const char* studio_geometry_case_drawings(const char* engine,const char* caseid) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN28GeometryAnalysisMgrSingleton11getInstanceEvE8instance");
        void* item=symbol<void*(*)(void*,const std::string&)>(library,"_ZNK28GeometryAnalysisMgrSingleton19GetGeometryAnalysisERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(manager,std::string(caseid));
        if(!item)throw std::runtime_error("Native geometry check unavailable.");
        std::vector<DrawObj*> objects;
        symbol<void(*)(void*,std::vector<DrawObj*>&)>(library,"_ZN20GeometryAnalysisCase12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE")(item,objects);
        std::ostringstream s;s<<std::setprecision(17)<<'[';bool first=true;
        for(const auto object:objects){
            const char* kind=object->m_Type==DrawObj::VSP_LINES?"lines":object->m_Type==DrawObj::VSP_POINTS?"points":object->m_Type==DrawObj::VSP_WIRE_SHADED_TRIS?"triangles":"unsupported";
            if(object->m_GeomID.rfind(std::string(caseid),0)!=0)continue;
            if(!first)s<<',';first=false;
            s<<"{\"nativeID\":"<<quote(object->m_GeomID)<<",\"nativeType\":"<<int(object->m_Type)<<",\"kind\":"<<quote(kind)<<",\"visible\":"<<(object->m_Visible?"true":"false")<<",\"points\":[";
            for(size_t i=0;i<object->m_PntVec.size();++i){const auto& p=object->m_PntVec[i];if(i)s<<',';s<<'[';double xyz[]={p.x(),p.y(),p.z()};for(int j=0;j<3;++j){if(j)s<<',';if(std::isfinite(xyz[j]))s<<xyz[j];else s<<"null";}s<<']';}
            s<<"]}";
        }
        s<<']';output=s.str();
    } catch(const std::exception& e) {output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_fea_mesh_export(const char* engine,const char* structure) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN19FeaMeshMgrSingleton11getInstanceEvE8instance");
        std::string sid(structure);
        void* mesh=symbol<void*(*)(void*,const std::string&)>(library,"_ZN19FeaMeshMgrSingleton10GetMeshPtrERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(manager,sid);
        if(!mesh)throw std::runtime_error("Generate the native structural mesh before exporting it.");
        symbol<void(*)(void*,const std::string&)>(library,"_ZN19FeaMeshMgrSingleton13ExportFeaMeshERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(manager,sid);
        symbol<void(*)(void*)>(library,"_ZN19FeaMeshMgrSingleton14ExportCADFilesEv")(manager);
        output="{}";
    } catch(const std::exception& e) {output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// Routing has no API surfaces from which to infer the physical copy count.
// Call the installed native getter; never duplicate symmetry rules in Studio.
extern "C" const char* studio_symmetry_count(const char* engine,const char* geom) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* component=find(std::string(geom),"Studio physical symmetry copies");
        if(!component)throw std::runtime_error("Native component unavailable.");
        output=std::to_string(symbol<int(*)(const void*)>(library,"_ZNK4Geom16GetNumSymmCopiesEv")(component));
    } catch(const std::exception& e) {output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// WireGeom has no API VspSurf. Preserve its native grids and native line pairs;
// transformations, trimming, strides and patches have already run in OpenVSP.
extern "C" const char* studio_wire_drawings(const char* engine,const char* geom) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* wire=find(std::string(geom),"Studio wire geometry preview");
        if(!wire)throw std::runtime_error("Native wire geometry unavailable.");
        symbol<void(*)(void*)>(library,"_ZN8WireGeom13UpdateDrawObjEv")(wire);
        std::vector<DrawObj*> objects;
        symbol<void(*)(void*,std::vector<DrawObj*>&)>(library,"_ZN8WireGeom12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE")(wire,objects);
        std::ostringstream s;s << std::setprecision(17) << '[';bool first=true;size_t count=0;
        auto point=[&](const vec3d& p,bool position=true){if(position&&++count>1000000)throw std::runtime_error("Native wire geometry exceeds the one-million-point display limit.");s << '[' << p.v[0] << ',' << p.v[1] << ',' << p.v[2] << ']';};
        for(const auto object:objects){
            bool mesh=object->m_Type==DrawObj::VSP_WIRE_MESH||object->m_Type==DrawObj::VSP_WIRE_HIDDEN_MESH||object->m_Type==DrawObj::VSP_SHADED_MESH||object->m_Type==DrawObj::VSP_TEXTURED_MESH;
            bool line=object->m_Type==DrawObj::VSP_LINES&&object->m_GeomID==std::string(geom)+"Line";
            if((!mesh&&!line)||(mesh&&object->m_PntMesh.empty())||(line&&object->m_PntVec.empty()))continue;
            if(!first)s << ',';first=false;
            s << "{\"nativeID\":" << quote(object->m_GeomID) << ",\"nativeType\":" << int(object->m_Type) << ",\"kind\":" << quote(mesh?"grids":"lines") << ",\"flipNormals\":" << (object->m_FlipNormals?"true":"false") << ",\"points\":[";
            if(mesh){
                for(size_t k=0;k<object->m_PntMesh.size();++k){if(k)s << ',';s << '[';const auto& grid=object->m_PntMesh[k];
                    for(size_t i=0;i<grid.size();++i){if(i)s << ',';s << '[';for(size_t j=0;j<grid[i].size();++j){if(j)s << ',';point(grid[i][j]);}s << ']';}s << ']';}
            }else for(size_t i=0;i<object->m_PntVec.size();++i){if(i)s << ',';point(object->m_PntVec[i]);}
            s << ']';
            if(mesh){s << ",\"normals\":[";
                for(size_t k=0;k<object->m_NormMesh.size();++k){if(k)s << ',';s << '[';const auto& grid=object->m_NormMesh[k];
                    for(size_t i=0;i<grid.size();++i){if(i)s << ',';s << '[';for(size_t j=0;j<grid[i].size();++j){if(j)s << ',';point(grid[i][j],false);}s << ']';}s << ']';}s << ']';}
            s << '}';
        }
        s << ']';output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// Some official inline accessors are present as local named Mach-O functions.
// Resolve their actual symbol-table values with the loader's image slide. This
// does not infer an object layout, a vtable position, or a function offset.
template<class T> static T local_symbol(void* library,const char* engine,const char* name) {
    if(void* value=dlsym(library,name))return reinterpret_cast<T>(value);
    Dl_info info{};
    void* anchor=symbol<void*>(library,"_ZN4Geom13UpdateSourcesEv");
    if(!dladdr(anchor,&info))throw std::runtime_error("Native image unavailable.");
    intptr_t slide=0;bool found=false;
    for(uint32_t i=0;i<_dyld_image_count();++i){
        if(_dyld_get_image_header(i)==info.dli_fbase){slide=_dyld_get_image_vmaddr_slide(i);found=true;break;}
    }
    if(!found)throw std::runtime_error("Native image slide unavailable.");
    std::ifstream file(engine,std::ios::binary);
    file.seekg(0,std::ios::end);std::streamoff size=file.tellg();file.seekg(0);
    mach_header_64 header{};file.read(reinterpret_cast<char*>(&header),sizeof(header));
    if(!file || header.magic!=MH_MAGIC_64 || size<std::streamoff(sizeof(header)) || header.sizeofcmds>size-std::streamoff(sizeof(header)))throw std::runtime_error("Unsupported native symbol table.");
    symtab_command table{};
    for(uint32_t i=0;i<header.ncmds;++i){
        auto position=file.tellg();load_command command{};file.read(reinterpret_cast<char*>(&command),sizeof(command));
        if(!file || command.cmdsize<sizeof(command) || position+std::streamoff(command.cmdsize)>size)throw std::runtime_error("Invalid native load command.");
        if(command.cmd==LC_SYMTAB){file.seekg(position);file.read(reinterpret_cast<char*>(&table),sizeof(table));break;}
        file.seekg(position+std::streamoff(command.cmdsize));
    }
    if(!table.strsize || uint64_t(table.stroff)+table.strsize>uint64_t(size) || uint64_t(table.symoff)+uint64_t(table.nsyms)*sizeof(nlist_64)>uint64_t(size))throw std::runtime_error("Native named symbols unavailable.");
    std::string strings(table.strsize,'\0');file.seekg(table.stroff);file.read(strings.data(),strings.size());
    file.seekg(table.symoff);
    for(uint32_t i=0;i<table.nsyms;++i){
        nlist_64 entry{};file.read(reinterpret_cast<char*>(&entry),sizeof(entry));
        if(!file)throw std::runtime_error("Incomplete native symbol table.");
        auto index=entry.n_un.n_strx;const std::string native_name="_"+std::string(name);
        if(index<strings.size() && !(entry.n_type&N_STAB) && (entry.n_type&N_TYPE)==N_SECT && strings.find('\0',index)==index+native_name.size() && strings.compare(index,native_name.size(),native_name)==0)
            return reinterpret_cast<T>(entry.n_value+slide);
    }
    throw std::runtime_error(std::string("Native named accessor unavailable: ")+name);
}

extern "C" const char* studio_cfd_sources(const char* engine,const char* geom) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* parent=find(std::string(geom),"Studio CFD source preview");
        if(!parent)throw std::runtime_error("Native source parent unavailable.");
        symbol<void(*)(void*)>(library,"_ZN4Geom13UpdateSourcesEv")(parent);
        auto sources=local_symbol<std::vector<BaseSimpleSource*>(*)(void*)>(library,engine,"_ZN4Geom23GetCfdMeshSimpSourceVecEv")(parent);
        std::ostringstream s;s << std::setprecision(17) << "[";
        for(size_t i=0;i<sources.size();++i){
            BaseSimpleSource* source=sources[i];if(!source)throw std::runtime_error("Native source unavailable.");
            source->Show(true);std::vector<DrawObj*> objects;source->LoadDrawObjs(objects);
            if(i)s << ',';s << "{\"source\":" << quote(source->m_OrigSourceID) << ",\"surface\":" << source->m_SurfIndx << ",\"objects\":[";
            bool first=true;
            for(const DrawObj* object:objects){
                if(object->m_PntVec.empty())continue;
                std::string kind;
                switch(object->m_Type){
                    case DrawObj::VSP_POINTS:kind="points";break;
                    case DrawObj::VSP_LINES:kind="lines";break;
                    case DrawObj::VSP_LINE_LOOP:kind="loop";break;
                    case DrawObj::VSP_LINE_STRIP:kind="strip";break;
                    default:throw std::runtime_error("Unsupported native source drawing type.");
                }
                if(!first)s << ',';first=false;
                s << "{\"nativeID\":" << quote(object->m_GeomID) << ",\"nativeType\":" << int(object->m_Type) << ",\"kind\":" << quote(kind) << ",\"visible\":" << (object->m_Visible?"true":"false") << ",\"points\":[";
                for(size_t j=0;j<object->m_PntVec.size();++j){auto& p=object->m_PntVec[j];if(j)s << ',';s << '[' << p.v[0] << ',' << p.v[1] << ',' << p.v[2] << ']';}
                s << "]}";
            }
            s << "]}";
        }
        s << "]";output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_cfd_domain(const char* engine,const char* mode) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN19CfdMeshMgrSingleton11getInstanceEvE8instance");
        symbol<void(*)(void*)>(library,"_ZN19CfdMeshMgrSingleton20TransferMeshSettingsEv")(manager);
        // Match native FetchSurfs: freeze mesh settings, then apply the selected
        // mode's presets before updating wakes/domain from the resulting model.
        if(mode && *mode)symbol<void(*)(const std::string&)>(library,"_ZN3vsp17ApplyModeSettingsERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(std::string(mode));
        symbol<void(*)(void*)>(library,"_ZN19CfdMeshMgrSingleton21UpdateSourcesAndWakesEv")(manager);
        symbol<void(*)(void*)>(library,"_ZN19CfdMeshMgrSingleton12UpdateDomainEv")(manager);
        std::vector<DrawObj*> objects;
        symbol<void(*)(void*,std::vector<DrawObj*>&)>(library,"_ZN19CfdMeshMgrSingleton12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE")(manager,objects);
        std::ostringstream s;s << std::setprecision(17) << '[';bool first=true;
        for(const DrawObj* object:objects){
            const auto& id=object->m_GeomID;
            auto ends=[&](const char* suffix){std::string tail(suffix);return id.size()>=tail.size() && id.compare(id.size()-tail.size(),tail.size(),tail)==0;};
            // These identifiers are assigned by the official native domain/wake
            // drawing routines, not by Studio or inferred from point positions.
            std::string owner=id=="WAKE"?"wake":ends("BBOXLS1")||ends("BBOXL1")?"symmetry":ends("BBOXLS")||ends("BBOXL")?"domain":"";
            if(owner.empty()||object->m_PntVec.empty())continue;
            std::string kind=object->m_Type==DrawObj::VSP_LINES?"lines":object->m_Type==DrawObj::VSP_LINE_STRIP?"strip":"";
            if(kind.empty())throw std::runtime_error("Unsupported native domain drawing type.");
            if(!first)s << ',';first=false;
            s << "{\"owner\":" << quote(owner) << ",\"nativeID\":" << quote(id) << ",\"nativeType\":" << int(object->m_Type) << ",\"kind\":" << quote(kind) << ",\"visible\":" << (object->m_Visible?"true":"false") << ",\"points\":[";
            for(size_t j=0;j<object->m_PntVec.size();++j){auto& p=object->m_PntVec[j];if(j)s << ',';s << '[' << p.v[0] << ',' << p.v[1] << ',' << p.v[2] << ']';}
            s << "]}";
        }
        s << ']';output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// Bogie references have no public SDK string setters. Resolve the exact
// native Bogie through its owning GearGeom, then call its named methods.
// No Bogie or GearGeom object layout is reproduced here.
extern "C" const char* studio_bogie_retraction(const char* engine,const char* geom,const char* id,int action,const char* parent,bool drawings) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* gear=find(std::string(geom),"Studio gear retraction");
        if(!gear)throw std::runtime_error("Native gear unavailable.");
        void* bogie=symbol<void*(*)(const void*,const std::string&)>(library,"_ZNK8GearGeom8GetBogieERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(gear,std::string(id));
        if(!bogie)throw std::runtime_error("Native wheel group unavailable.");
        if(action==1||action==2){
            const char* setter=action==1?"_ZN5Bogie15SetStowParentIDERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE":"_ZN5Bogie15SetMechParentIDERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE";
            symbol<void(*)(void*,const std::string&)>(library,setter)(bogie,std::string(parent));
        }else if(action!=0&&action!=3)throw std::runtime_error("Unsupported native retraction operation.");
        auto stow=local_symbol<std::string(*)(void*)>(library,engine,"_ZN5Bogie15GetStowParentIDEv")(bogie);
        auto mechanism=local_symbol<std::string(*)(void*)>(library,engine,"_ZN5Bogie15GetMechParentIDEv")(bogie);
        if(action==3){
            // Decode can register a forward reference before its parent exists.
            // Native AddStepChildID deduplicates; restore the native dependency
            // and evaluate this gear after its references have been evaluated.
            symbol<void(*)(void*)>(library,"_ZN8GearGeom13UpdateParentsEv")(gear);
            const auto geoms=symbol<std::vector<std::string>(*)()>(library,"_ZN3vsp9FindGeomsEv")();
            for(const auto& ref:{stow,mechanism}){
                if(ref.empty()||std::find(geoms.begin(),geoms.end(),ref)==geoms.end())continue;
                void* target=find(ref,"Studio gear retraction refresh");
                if(target)symbol<void(*)(void*,const std::string&)>(library,"_ZN8GeomBase14AddStepChildIDERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(target,std::string(geom));
            }
            symbol<void(*)(void*,bool)>(library,"_ZN4Geom6UpdateEb")(gear,true);
        }
        bool sj=symbol<bool(*)(void*)>(library,"_ZN5Bogie17IsStowParentJointEv")(bogie),mj=symbol<bool(*)(void*)>(library,"_ZN5Bogie17IsMechParentJointEv")(bogie);
        std::ostringstream s;s << std::setprecision(17) << "{\"stowParent\":" << quote(stow) << ",\"mechanismParent\":" << quote(mechanism) << ",\"stowJoint\":" << (sj?"true":"false") << ",\"mechanismJoint\":" << (mj?"true":"false") << ",\"objects\":[";
        if(drawings){
            symbol<void(*)(void*)>(library,"_ZN8GearGeom13UpdateDrawObjEv")(gear);
            std::vector<DrawObj*> objects;
            symbol<void(*)(void*,std::vector<DrawObj*>&)>(library,"_ZN5Bogie12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE")(bogie,objects);
            bool first=true;size_t count=0;
            for(const auto object:objects){
                if(object->m_PntVec.empty())continue;
                std::string kind=object->m_Type==DrawObj::VSP_LINES?"lines":object->m_Type==DrawObj::VSP_POINTS?"points":object->m_Type==DrawObj::VSP_SHADED_TRIS?"triangles":"";
                if(kind.empty())throw std::runtime_error("Unsupported native retraction drawing type.");
                if(!first)s << ',';first=false;
                s << "{\"nativeID\":" << quote(object->m_GeomID) << ",\"nativeType\":" << int(object->m_Type) << ",\"kind\":" << quote(kind) << ",\"points\":[";
                for(size_t i=0;i<object->m_PntVec.size();++i){const auto& p=object->m_PntVec[i];
                    if(++count>1000000)throw std::runtime_error("Native retraction drawing exceeds the display limit.");
                    if(!std::isfinite(p.v[0])||!std::isfinite(p.v[1])||!std::isfinite(p.v[2]))throw std::runtime_error("Native retraction drawing contains undefined points.");
                    if(i)s << ',';s << '[' << p.v[0] << ',' << p.v[1] << ',' << p.v[2] << ']';}
                s << "]}";
            }
        }
        s << "]}";output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// BOR decoding can leave its curve evaluated with constructor defaults. Ask
// the actual native curve/parent to evaluate the already decoded parameters.
extern "C" const char* studio_refresh_profile(const char* engine,const char* container,const char* parameter,const char* geom) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");
        void* curve=symbol<void*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton17FindParmContainerERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(manager,std::string(container));
        Parm* parm=symbol<Parm*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton8FindParmERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(manager,std::string(parameter));
        if(!curve||!parm)throw std::runtime_error("Native profile parameter unavailable.");
        auto getparent=local_symbol<std::string(*)(void*)>(library,engine,"_ZNK13ParmContainer18GetParentContainerEv");
        std::string before=getparent(curve);
        if(before!=std::string(geom)){
            local_symbol<void(*)(void*,const std::string&)>(library,engine,"_ZN13ParmContainer18SetParentContainerERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(curve,std::string(geom));
            symbol<void(*)(void*,Parm*,int)>(library,"_ZN9XSecCurve11ParmChangedEP4Parmi")(curve,parm,Parm::SET_FROM_LINK);
        }
        output="{\"parentBefore\":"+quote(before)+",\"parentAfter\":"+quote(getparent(curve))+"}";
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_parameter_activity(const char* engine,const char* const* ids,int count) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);
        if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");
        auto find=symbol<Parm*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton8FindParmERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE");
        std::ostringstream s;s << "[";
        for(int i=0;i<count;++i){
            Parm* parm=find(manager,std::string(ids[i]));
            if(!parm)throw std::runtime_error("Native parameter unavailable.");
            if(i)s << ',';s << (parm->GetActiveFlag()?"true":"false");
        }
        s << "]";output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);
    return output.c_str();
}
extern "C" const char* studio_connection_preview(const char* engine,const char* connection) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");
        void* item=symbol<void*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton17FindParmContainerERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(manager,std::string(connection));
        if(!item)throw std::runtime_error("Native assembly connection unavailable.");
        symbol<void(*)(void*)>(library,"_ZN13FeaConnection6UpdateEv")(item);
        std::vector<DrawObj*> objects;
        symbol<void(*)(void*,std::vector<DrawObj*>&)>(library,"_ZN13FeaConnection12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE")(item,objects);
        std::ostringstream s;s<<std::setprecision(17)<<'[';bool first=true;
        for(const auto object:objects){
            if(object->m_PntVec.empty())continue;
            if(!first)s<<',';first=false;
            s<<"{\"nativeID\":"<<quote(object->m_GeomID)<<",\"nativeType\":"<<int(object->m_Type)<<",\"kind\":"<<quote(object->m_Type==DrawObj::VSP_LINES?"lines":object->m_Type==DrawObj::VSP_POINTS?"points":"unsupported")<<",\"visible\":"<<(object->m_Visible?"true":"false")<<",\"points\":[";
            for(size_t i=0;i<object->m_PntVec.size();++i){const auto& p=object->m_PntVec[i];if(i)s<<',';s<<'[';double xyz[]={p.x(),p.y(),p.z()};for(int j=0;j<3;++j){if(j)s<<',';if(std::isfinite(xyz[j]))s<<xyz[j];else s<<"null";}s<<']';}
            s<<"]}";
        }
        s<<']';output=s.str();
    }catch(const std::exception& e){output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_fixedpoint_copies(const char* engine,const char* point) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");
        void* item=symbol<void*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton17FindParmContainerERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(manager,std::string(point));
        if(!item)throw std::runtime_error("Native fixed point unavailable.");
        double scale=1.0;
        auto points=symbol<std::vector<vec3d>(*)(void*,const double&)>(library,"_ZN11FeaFixPoint9GetPntVecERKd")(item,scale);
        std::ostringstream s;s<<std::setprecision(17)<<'[';
        for(size_t i=0;i<points.size();++i){if(i)s<<',';s<<'[';double xyz[]={points[i].x(),points[i].y(),points[i].z()};for(int j=0;j<3;++j){if(j)s<<',';if(std::isfinite(xyz[j]))s<<xyz[j];else s<<"null";}s<<']';}s<<']';output=s.str();
    }catch(const std::exception& e){output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_boundary_update(const char* engine,const char* boundary) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");
        void* item=symbol<void*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton17FindParmContainerERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(manager,std::string(boundary));
        if(!item)throw std::runtime_error("Native structural boundary unavailable.");
        symbol<void(*)(void*)>(library,"_ZN5FeaBC6UpdateEv")(item);output="{}";
    }catch(const std::exception& e){output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_cfd_density_update(const char* engine,const char* density) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");
        void* item=symbol<void*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton17FindParmContainerERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(manager,std::string(density));
        if(!item)throw std::runtime_error("Native CFD density unavailable.");
        double scale=1.0;
        symbol<void(*)(void*,const double&)>(library,"_ZN11GridDensity6UpdateERKd")(item,scale);output="{}";
    }catch(const std::exception& e){output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_structure_update(const char* engine,const char* geom,int index) {
    static thread_local std::string output;
    void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);
        if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,int,const std::string&)>(library,"_ZN3vsp13FindFeaStructERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEEiS8_");
        void* structure=find(std::string(geom),index,"Studio structure update");
        if(!structure)throw std::runtime_error("Native structure unavailable.");
        symbol<void(*)(void*)>(library,"_ZN12FeaStructure6UpdateEv")(structure);
        output="{}";
    }catch(const std::exception& e){output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_structural_preview(const char* engine, const char* geom, int index, int count, int region_count) {
    static thread_local std::string output;
    try {
        void* library=dlopen(engine,RTLD_NOW);
        if (!library) throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,int,const std::string&)>(library,"_ZN3vsp13FindFeaStructERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEEiS8_");
        auto update=symbol<void(*)(void*)>(library,"_ZN12FeaStructure6UpdateEv");
        auto part=symbol<void*(*)(void*,int)>(library,"_ZN12FeaStructure10GetFeaPartEi");
        auto draw=symbol<void(*)(void*,std::vector<DrawObj*>&)>(library,"_ZN7FeaPart12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE");
        auto region=symbol<void*(*)(void*,int)>(library,"_ZN12FeaStructure13GetFeaSubSurfEi");
        auto region_draw=symbol<void(*)(void*,std::vector<DrawObj*>&)>(library,"_ZN10SubSurface12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE");
        void* structure=find(std::string(geom),index,"Studio structural preview");
        if (!structure) throw std::runtime_error("Native structure unavailable.");
        update(structure);
        std::ostringstream s;s << std::setprecision(17) << "{\"parts\":[";
        for (int i=0;i<count+region_count;++i) {
            bool is_region=i>=count;
            int native_index=is_region?i-count:i;
            void* owner=is_region?region(structure,native_index):part(structure,native_index);
            if (!owner) throw std::runtime_error("Native structural drawing owner unavailable.");
            std::vector<DrawObj*> objects;
            if(is_region)region_draw(owner,objects);else draw(owner,objects);
            if (i==count) s << "],\"regions\":[";
            else if (i) s << ',';
            s << "{\"index\":" << native_index << ",\"objects\":[";
            bool first=true;
            for (const DrawObj* object:objects) {
                if (object->m_PntVec.empty()) continue;
                std::string kind;
                switch (object->m_Type) {
                    case DrawObj::VSP_POINTS:kind="points";break;
                    case DrawObj::VSP_LINES:kind="lines";break;
                    case DrawObj::VSP_LINE_LOOP:kind="loop";break;
                    case DrawObj::VSP_LINE_STRIP:kind="strip";break;
                    case DrawObj::VSP_SHADED_QUADS:kind="quads";break;
                    case DrawObj::VSP_SHADED_TRIS:kind="triangles";break;
                    default:kind="unsupported";
                }
                if (!first) s << ',';first=false;
                s << "{\"nativeID\":" << quote(object->m_GeomID) << ",\"nativeType\":" << int(object->m_Type) << ",\"kind\":" << quote(kind) << ",\"visible\":" << (object->m_Visible?"true":"false") << ",\"points\":[";
                for (size_t j=0;j<object->m_PntVec.size();++j) {
                    const auto& p=object->m_PntVec[j];if(j)s << ',';
                    s << '[' << p.v[0] << ',' << p.v[1] << ',' << p.v[2] << ']';
                }
                s << "]}";
            }
            s << "]}";
        }
        if(!region_count)s << "],\"regions\":[";
        s << "]}";output=s.str();
        dlclose(library);
    } catch(const std::exception& error) {output="{\"error\":"+quote(error.what())+"}";}
    return output.c_str();
}

static void* region_owner(void* library,const char* geom,int structure_index,int region_index) {
    void* owner=nullptr;
    if(structure_index>=0){
        auto find=symbol<void*(*)(const std::string&,int,const std::string&)>(library,"_ZN3vsp13FindFeaStructERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEEiS8_");
        auto region=symbol<void*(*)(void*,int)>(library,"_ZN12FeaStructure13GetFeaSubSurfEi");
        void* structure=find(std::string(geom),structure_index,"Studio section curve");
        if(structure)owner=region(structure,region_index);
    }else{
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        auto region=symbol<void*(*)(void*,int)>(library,"_ZN4Geom10GetSubSurfEi");
        void* parent=find(std::string(geom),"Studio section curve");
        if(parent)owner=region(parent,region_index);
    }
    if(!owner)throw std::runtime_error("Native section-curve region unavailable.");
    return owner;
}
// Change the engine's own section-curve object; no generated curve math here.
extern "C" const char* studio_region_curve_shape(const char* engine,const char* geom,int structure_index,int region_index,int type) {
    static thread_local std::string output;
    void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);
        if(!library)throw std::runtime_error(dlerror());
        void* owner=region_owner(library,geom,structure_index,region_index);
        auto change=symbol<void(*)(void*,int)>(library,"_ZN11SSXSecCurve16SetXSecCurveTypeEi");
        change(owner,type);output="{}";
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);
    return output.c_str();
}

extern "C" const char* studio_region_curve_operation(const char* engine,const char* geom,int structure_index,int region_index,int operation) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);
        if(!library)throw std::runtime_error(dlerror());
        void* owner=region_owner(library,geom,structure_index,region_index);
        if(operation==1){
            auto convert=symbol<void*(*)(void*)>(library,"_ZN11SSXSecCurve13ConvertToEditEv");
            if(!convert(owner))throw std::runtime_error("OpenVSP could not convert this curve.");
        }else if(operation==2){
            symbol<void(*)(void*)>(library,"_ZN11SSXSecCurve13CopyXSecCurveEv")(owner);
        }else if(operation==3){
            symbol<void(*)(void*)>(library,"_ZN11SSXSecCurve14PasteXSecCurveEv")(owner);
        }else throw std::runtime_error("Unknown native curve operation.");
        output="{}";
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);
    return output.c_str();
}

// Caller validates XS_EDIT_CURVE before entry. ConvertToEdit then returns the
// existing curve pointer without changing its type, ownership or parameters.
extern "C" const char* studio_region_edit_curve(const char* engine,const char* geom,int structure_index,int region_index,int operation,int argument,double u) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);
        if(!library)throw std::runtime_error(dlerror());
        void* owner=region_owner(library,geom,structure_index,region_index);
        // Vehicle::Update does not eagerly evaluate structural region curves
        // after loading. Native Split01 needs their evaluated base curve.
        if(operation!=5)symbol<void(*)(void*)>(library,"_ZN11SSXSecCurve6UpdateEv")(owner);
        void* curve=symbol<void*(*)(void*)>(library,"_ZN11SSXSecCurve13ConvertToEditEv")(owner);
        if(!curve)throw std::runtime_error("Native editable region curve unavailable.");
        if(operation==1)symbol<void(*)(void*,int)>(library,"_ZN13EditCurveXSec9ConvertToEi")(curve,argument);
        else if(operation==2)symbol<int(*)(void*,double)>(library,"_ZN13EditCurveXSec7Split01Ed")(curve,u);
        else if(operation==3)symbol<void(*)(void*,int)>(library,"_ZN13EditCurveXSec8DeletePtEi")(curve,argument);
        else if(operation==4)symbol<void(*)(void*)>(library,"_ZN13EditCurveXSec28ReparameterizeEqualArcLengthEv")(curve);
        // Parm::SET_FROM_DEVICE is 2 in official OpenVSP_3.52.2 Parm.h.
        // Match MoveEditXSecPnt's final native update after setting X/Y/Z.
        else if(operation==5)symbol<void(*)(void*,void*,int)>(library,"_ZN13EditCurveXSec11ParmChangedEP4Parmi")(curve,nullptr,2);
        else if(operation==6)symbol<void(*)(void*,int)>(library,"_ZN13EditCurveXSec14SetSelectPntIDEi")(curve,argument);
        else if(operation==7)symbol<void(*)(void*)>(library,"_ZN13EditCurveXSec9InitShapeEv")(curve);
        else if(operation!=0)throw std::runtime_error("Unknown editable curve operation.");
        auto points=symbol<std::vector<vec3d>(*)(void*,bool,bool)>(library,"_ZN13EditCurveXSec13GetCtrlPntVecEbb")(curve,true,false);
        auto positions=symbol<std::vector<double>(*)(void*)>(library,"_ZN13EditCurveXSec7GetUVecEv")(curve);
        auto fixed=symbol<std::vector<bool>(*)(void*)>(library,"_ZN13EditCurveXSec12GetFixedUVecEv")(curve);
        auto smooth=symbol<std::vector<bool>(*)(void*)>(library,"_ZN13EditCurveXSec8GetG1VecEv")(curve);
        std::ostringstream s;s << std::setprecision(17) << "{\"controlPoints\":[";
        for(size_t i=0;i<points.size();++i){if(i)s << ',';s << '[' << points[i].v[0] << ',' << points[i].v[1] << ',' << points[i].v[2] << ']';}
        s << "],\"curveU\":[";
        for(size_t i=0;i<positions.size();++i){if(i)s << ',';s << positions[i];}
        s << "],\"fixedU\":[";
        for(size_t i=0;i<fixed.size();++i){if(i)s << ',';s << (fixed[i]?"true":"false");}
        s << "],\"smooth\":[";
        for(size_t i=0;i<smooth.size();++i){if(i)s << ',';s << (smooth[i]?"true":"false");}
        s << "]}";output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);
    return output.c_str();
}

// Read classifications already produced by GenerateMesh/CheckWaterTight.
// Do not rerun CheckWaterTight: it appends to the native diagnostic collections.
extern "C" const char* studio_cfd_results(const char* engine,const char* rawfile,const char* adaptedfile,bool meshed) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,meshed?"_ZZN19CfdMeshMgrSingleton11getInstanceEvE8instance":"_ZZN28SurfaceIntersectionSingleton11getInstanceEvE8instance");
        auto write=symbol<void(*)(void*,const std::string&,bool)>(library,"_ZN28SurfaceIntersectionSingleton21WriteGridToolCurvFileERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEEb");
        write(manager,std::string(rawfile),true);write(manager,std::string(adaptedfile),false);
        std::vector<DrawObj*> objects;
        symbol<void(*)(void*,std::vector<DrawObj*>&)>(library,meshed?"_ZN19CfdMeshMgrSingleton12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE":"_ZN28SurfaceIntersectionSingleton12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE")(manager,objects);
        std::ostringstream s;s << std::setprecision(17) << '[';bool first=true;
        for(const auto object:objects){
            std::string owner;
            for(const auto suffix:{"RAWISECTCURVE","RAWBORDERCURVE","ISECTCURVE","BORDERCURVE","BADEDGE","BADTRI","BADQUAD"}){
                const std::string tail(suffix);const auto& id=object->m_GeomID;
                if(id.size()>=tail.size()&&id.compare(id.size()-tail.size(),tail.size(),tail)==0){owner=tail;break;}
            }
            if(owner.empty())continue;
            std::string kind=object->m_Type==DrawObj::VSP_LINES?"lines":object->m_Type==DrawObj::VSP_CFD_HIDDEN_TRIS?"triangles":object->m_Type==DrawObj::VSP_CFD_HIDDEN_QUADS?"quads":"";
            if(kind.empty())throw std::runtime_error("Unsupported native CFD diagnostic drawing type.");
            if(!first)s << ',';first=false;
            s << "{\"owner\":" << quote(owner) << ",\"nativeID\":" << quote(object->m_GeomID) << ",\"nativeType\":" << int(object->m_Type) << ",\"kind\":" << quote(kind) << ",\"points\":[";
            for(size_t j=0;j<object->m_PntVec.size();++j){auto& p=object->m_PntVec[j];if(j)s << ',';s << '[' << p.v[0] << ',' << p.v[1] << ',' << p.v[2] << ']';}
            s << "]}";
        }
        s << ']';output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// Construct the exact official class in correctly sized/aligned storage. Native
// constructor, validator and destructor run in the installed engine; no formulas
// or driver-validation rules are copied into this presentation adapter.
extern "C" const char* studio_prop_driver_combinations(const char* engine) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto construct=symbol<void(*)(void*)>(library,"_ZN15PropDriverGroupC1Ev");
        auto destroy=local_symbol<void(*)(void*)>(library,engine,"_ZN15PropDriverGroupD1Ev");
        auto valid=symbol<bool(*)(void*,std::vector<int>)>(library,"_ZN15PropDriverGroup12ValidDriversENSt3__16vectorIiNS0_9allocatorIiEEEE");
        alignas(PropDriverGroup) unsigned char storage[sizeof(PropDriverGroup)];
        construct(storage);
        try {
            std::ostringstream s;s << '[';bool first=true;
            for(int a=0;a<vsp::NUM_PROP_DRIVER;++a)
                for(int b=a+1;b<vsp::NUM_PROP_DRIVER;++b)
                    for(int c=b+1;c<vsp::NUM_PROP_DRIVER;++c)
                        if(valid(storage,{a,b,c})){
                            if(!first)s << ',';first=false;
                            s << '[' << a << ',' << b << ',' << c << ']';
                        }
            s << ']';output=s.str();
        }catch(...){destroy(storage);throw;}
        destroy(storage);
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_wing_driver_combinations(const char* engine) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto construct=symbol<void(*)(void*)>(library,"_ZN15WingDriverGroupC1Ev");
        auto destroy=local_symbol<void(*)(void*)>(library,engine,"_ZN15WingDriverGroupD1Ev");
        auto valid=symbol<bool(*)(void*,std::vector<int>)>(library,"_ZN15WingDriverGroup12ValidDriversENSt3__16vectorIiNS0_9allocatorIiEEEE");
        alignas(WingDriverGroup) unsigned char storage[sizeof(WingDriverGroup)];
        construct(storage);
        try {
            std::ostringstream s;s << '[';bool first=true;
            for(int a=0;a<vsp::NUM_WSECT_DRIVER;++a)
                for(int b=a+1;b<vsp::NUM_WSECT_DRIVER;++b)
                    for(int c=b+1;c<vsp::NUM_WSECT_DRIVER;++c)
                        if(valid(storage,{a,b,c})){
                            if(!first)s << ',';first=false;
                            s << '[' << a << ',' << b << ',' << c << ']';
                        }
            s << ']';output=s.str();
        }catch(...){destroy(storage);throw;}
        destroy(storage);
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_wing_driver_parameters(const char* engine,const char* geom,int section) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* wing=find(std::string(geom),"Studio wing section controls");
        if(!wing)throw std::runtime_error("Native wing unavailable.");
        void* sect=symbol<void*(*)(void*,int)>(library,"_ZN8WingGeom11GetWingSectEi")(wing,section);
        if(!sect)throw std::runtime_error("Native wing section unavailable.");
        auto ids=symbol<std::vector<std::string>(*)(void*)>(library,"_ZN8WingSect14GetDriverParmsEv")(sect);
        std::ostringstream s;s << '[';
        for(size_t i=0;i<ids.size();++i){if(i)s << ',';s << quote(ids[i]);}s << ']';output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_body_driver_combinations(const char* engine,bool circle) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        const char* ctor=circle?"_ZN21DXSecCurveDriverGroupC1Ev":"_ZN22HWXSecCurveDriverGroupC1Ev";
        const char* dtor=circle?"_ZN21DXSecCurveDriverGroupD1Ev":"_ZN22HWXSecCurveDriverGroupD1Ev";
        const char* validator=circle?"_ZN21DXSecCurveDriverGroup12ValidDriversENSt3__16vectorIiNS0_9allocatorIiEEEE":"_ZN22HWXSecCurveDriverGroup12ValidDriversENSt3__16vectorIiNS0_9allocatorIiEEEE";
        alignas(HWXSecCurveDriverGroup) unsigned char storage[sizeof(HWXSecCurveDriverGroup)];
        static_assert(sizeof(HWXSecCurveDriverGroup)==sizeof(DXSecCurveDriverGroup),"Matching native driver storage required");
        auto destroy=local_symbol<void(*)(void*)>(library,engine,dtor);
        symbol<void(*)(void*)>(library,ctor)(storage);
        try {
            auto valid=symbol<bool(*)(void*,std::vector<int>)>(library,validator);
            std::ostringstream s;s << '[';bool first=true;
            const int count=circle?vsp::CIRCLE_NUM_XSEC_DRIVER:vsp::NUM_XSEC_DRIVER;
            for(int a=0;a<count;++a)for(int b=circle?count:a+1;b<=count;++b){
                if(!circle&&b==count)continue;
                std::vector<int> choices={a};if(!circle)choices.push_back(b);
                if(!valid(storage,choices))continue;
                if(!first)s << ',';first=false;s << '[' << a;if(!circle)s << ',' << b;s << ']';
            }
            s << ']';output=s.str();
        }catch(...){destroy(storage);throw;}
        destroy(storage);
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_body_driver_parameters(const char* engine,const char* container,bool circle) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");
        void* curve=symbol<void*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton17FindParmContainerERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(manager,std::string(container));
        if(!curve)throw std::runtime_error("Native section curve unavailable.");
        auto ids=symbol<std::vector<std::string>(*)(void*)>(library,circle?"_ZN10CircleXSec14GetDriverParmsEv":"_ZN9XSecCurve14GetDriverParmsEv")(curve);
        std::ostringstream s;s << '[';for(size_t i=0;i<ids.size();++i){if(i)s << ',';s << quote(ids[i]);}s << ']';output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_attachment_frame(const char* engine,const char* geom) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* component=find(std::string(geom),"Studio attachment frame");
        if(!component)throw std::runtime_error("Native component unavailable.");
        Matrix4d matrix=symbol<Matrix4d(*)(void*,int)>(library,"_ZN9GeomXForm23GetAncestorAttachMatrixEi")(component,0);
        auto transform=symbol<vec3d(*)(const Matrix4d*,const vec3d&)>(library,"_ZNK8Matrix4d5xformERK5vec3d");
        auto construct=symbol<void(*)(void*,double,double,double)>(library,"_ZN5vec3dC1Eddd");
        std::ostringstream s;s << std::setprecision(17) << "{\"matrix\":[";
        for(int i=0;i<16;++i){if(i)s << ',';s << matrix.const_data()[i];}
        s << "],\"points\":[";
        for(int i=0;i<4;++i){
            alignas(vec3d) unsigned char basisStorage[sizeof(vec3d)];
            construct(basisStorage,i==1?1.:0.,i==2?1.:0.,i==3?1.:0.);
            vec3d point=transform(&matrix,*reinterpret_cast<vec3d*>(basisStorage));
            if(i)s << ',';s << '[' << point.v[0] << ',' << point.v[1] << ',' << point.v[2] << ']';
        }
        s << "],\"pointOrder\":[\"Origin\",\"X\",\"Y\",\"Z\"],\"axisLength\":1}";output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_prop_curve_values(const char* engine,const char* geom,int curveid,const double* stations,int count) {
    static thread_local std::string output;void* library=nullptr;
    try {
        if(count<1||count>10000)throw std::runtime_error("Choose 1–10000 native curve samples.");
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* component=find(std::string(geom),"Studio propeller curve");
        if(!component)throw std::runtime_error("Native propeller unavailable.");
        void* curve=symbol<void*(*)(void*,int)>(library,"_ZN8PropGeom9GetPCurveEi")(component,curveid);
        if(!curve)throw std::runtime_error("Native blade curve unavailable.");
        auto comp=symbol<double(*)(void*,double)>(library,"_ZN6PCurve4CompEd");
        std::ostringstream s;s << std::setprecision(17) << '[';
        for(int i=0;i<count;++i){if(i)s << ',';s << comp(curve,stations[i]);}
        s << ']';output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// Auxiliary SuperCone uses an XSecCurve without an API XSecSurf. Call its
// original editor methods and sample its native curve through ParmMgr.
extern "C" const char* studio_auxiliary_curve(const char* engine,const char* geom,const char* container,int operation,int argument) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* component=find(std::string(geom),"Studio auxiliary profile");
        if(!component)throw std::runtime_error("Native auxiliary unavailable.");
        if(operation==1)symbol<void(*)(void*,int)>(library,"_ZN13AuxiliaryGeom16SetXSecCurveTypeEi")(component,argument);
        else if(operation==2)symbol<void(*)(void*)>(library,"_ZN13AuxiliaryGeom13CopyXSecCurveEv")(component);
        else if(operation==3)symbol<void(*)(void*)>(library,"_ZN13AuxiliaryGeom14PasteXSecCurveEv")(component);
        else if(operation==4)symbol<void*(*)(void*)>(library,"_ZN13AuxiliaryGeom13ConvertToEditEv")(component);
        else if(operation!=0)throw std::runtime_error("Unknown native auxiliary profile operation.");
        int type=symbol<int(*)(void*)>(library,"_ZN13AuxiliaryGeom16GetXSecCurveTypeEv")(component);
        if(operation==1 && type==vsp::XS_EDIT_CURVE){
            // An inherited zero
            // dimension can leave the constructor's point vectors empty.
            // Initialize through the original editor before saving any IDs.
            void* editable=symbol<void*(*)(void*)>(library,"_ZN13AuxiliaryGeom13ConvertToEditEv")(component);
            auto points=symbol<std::vector<vec3d>(*)(void*,bool,bool)>(library,"_ZN13EditCurveXSec13GetCtrlPntVecEbb")(editable,true,false);
            if(points.empty())symbol<void(*)(void*)>(library,"_ZN13EditCurveXSec9InitShapeEv")(editable);
        }
        std::ostringstream s;s << std::setprecision(17) << "{\"type\":" << type;
        if(operation==0){
            void* manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");
            void* curve=symbol<void*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton17FindParmContainerERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(manager,std::string(container));
            if(!curve)throw std::runtime_error("Native auxiliary profile unavailable.");
            void* profile=symbol<void*(*)(void*)>(library,"_ZN9XSecCurve8GetCurveEv")(curve);
            auto sample=symbol<vec3d(*)(const void*,double)>(library,"_ZNK8VspCurve9CompPnt01Ed");
            s << ",\"profile\":[";
            for(int i=0;i<=100;++i){vec3d p=sample(profile,i/100.);if(i)s << ',';
                for(double x:p.v)if(!std::isfinite(x))throw std::runtime_error("OpenVSP returned undefined auxiliary profile points.");
                s << '[' << p.v[0] << ',' << p.v[1] << ',' << p.v[2] << ']';}
            s << ']';
        }
        s << '}';output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// SuperCone has a standalone editable curve, with the same original editor
// operations as native sections and region curves. No layout is reimplemented.
static const char* studio_geometry_edit_curve(const char* engine,const char* geom,int operation,int argument,double u,bool bor) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* component=find(std::string(geom),"Studio editable auxiliary profile");
        if(!component)throw std::runtime_error("Native auxiliary unavailable.");
        void* curve=symbol<void*(*)(void*)>(library,bor?"_ZN7BORGeom13ConvertToEditEv":"_ZN13AuxiliaryGeom13ConvertToEditEv")(component);
        if(!curve)throw std::runtime_error("Native editable cone profile unavailable.");
        if(operation!=5)symbol<void*(*)(void*)>(library,"_ZN9XSecCurve8GetCurveEv")(curve);
        if(operation==1)symbol<void(*)(void*,int)>(library,"_ZN13EditCurveXSec9ConvertToEi")(curve,argument);
        else if(operation==2)symbol<int(*)(void*,double)>(library,"_ZN13EditCurveXSec7Split01Ed")(curve,u);
        else if(operation==3)symbol<void(*)(void*,int)>(library,"_ZN13EditCurveXSec8DeletePtEi")(curve,argument);
        else if(operation==4)symbol<void(*)(void*)>(library,"_ZN13EditCurveXSec28ReparameterizeEqualArcLengthEv")(curve);
        // Parm::SET_FROM_DEVICE is 2 in official OpenVSP_3.52.2 Parm.h.
        // Match MoveEditXSecPnt's final native update after setting X/Y/Z.
        else if(operation==5)symbol<void(*)(void*,void*,int)>(library,"_ZN13EditCurveXSec11ParmChangedEP4Parmi")(curve,nullptr,2);
        else if(operation==6)symbol<void(*)(void*,int)>(library,"_ZN13EditCurveXSec14SetSelectPntIDEi")(curve,argument);
        else if(operation==7)symbol<void(*)(void*)>(library,"_ZN13EditCurveXSec9InitShapeEv")(curve);
        else if(operation!=0)throw std::runtime_error("Unknown editable curve operation.");
        auto points=symbol<std::vector<vec3d>(*)(void*,bool,bool)>(library,"_ZN13EditCurveXSec13GetCtrlPntVecEbb")(curve,true,false);
        auto positions=symbol<std::vector<double>(*)(void*)>(library,"_ZN13EditCurveXSec7GetUVecEv")(curve);
        auto fixed=symbol<std::vector<bool>(*)(void*)>(library,"_ZN13EditCurveXSec12GetFixedUVecEv")(curve);
        auto smooth=symbol<std::vector<bool>(*)(void*)>(library,"_ZN13EditCurveXSec8GetG1VecEv")(curve);
        std::ostringstream s;s << std::setprecision(17) << "{\"controlPoints\":[";
        for(size_t i=0;i<points.size();++i){if(i)s << ',';s << '[' << points[i].v[0] << ',' << points[i].v[1] << ',' << points[i].v[2] << ']';}
        s << "],\"curveU\":[";
        for(size_t i=0;i<positions.size();++i){if(i)s << ',';s << positions[i];}
        s << "],\"fixedU\":[";
        for(size_t i=0;i<fixed.size();++i){if(i)s << ',';s << (fixed[i]?"true":"false");}
        s << "],\"smooth\":[";
        for(size_t i=0;i<smooth.size();++i){if(i)s << ',';s << (smooth[i]?"true":"false");}
        s << "]}";output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_auxiliary_edit_curve(const char* engine,const char* geom,int operation,int argument,double u) {
    return studio_geometry_edit_curve(engine,geom,operation,argument,u,false);
}
extern "C" const char* studio_bor_edit_curve(const char* engine,const char* geom,int operation,int argument,double u) {
    return studio_geometry_edit_curve(engine,geom,operation,argument,u,true);
}

// Mean contact locations used by the native three-contact ground/CCE basis.
extern "C" const char* studio_gear_contact_point(const char* engine,const char* geom,const char* id,int mirrored,int tire,int suspension) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* gear=find(std::string(geom),"Studio auxiliary contact");
        if(!gear)throw std::runtime_error("Native gear unavailable.");
        void* bogie=symbol<void*(*)(const void*,const std::string&)>(library,"_ZNK8GearGeom8GetBogieERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(gear,std::string(id));
        if(!bogie)throw std::runtime_error("Native wheel group unavailable.");
        vec3d p=symbol<vec3d(*)(const void*,int,int,int,double)>(library,"_ZNK5Bogie19GetMeanContactPointEiiid")(bogie,mirrored,tire,suspension,0.0);
        for(double x:p.v)if(!std::isfinite(x))throw std::runtime_error("OpenVSP returned undefined contact coordinates.");
        std::ostringstream s;s << std::setprecision(17) << '[' << p.v[0] << ',' << p.v[1] << ',' << p.v[2] << ']';output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_bor_profile_clipboard(const char* engine,const char* geom,int operation) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* component=find(std::string(geom),"Studio revolution profile clipboard");
        if(!component)throw std::runtime_error("Native revolution component unavailable.");
        if(operation==0)symbol<void(*)(void*)>(library,"_ZN7BORGeom13CopyXSecCurveEv")(component);
        else if(operation==1)symbol<void(*)(void*)>(library,"_ZN7BORGeom14PasteXSecCurveEv")(component);
        else throw std::runtime_error("Unknown revolution clipboard operation.");
        output="{\"ok\":true}";
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_profile_query(const char* engine,const char* container,double fraction) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");
        void* curve=symbol<void*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton17FindParmContainerERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(manager,std::string(container));
        if(!curve)throw std::runtime_error("Native profile container unavailable.");
        void* profile=symbol<void*(*)(void*)>(library,"_ZN9XSecCurve8GetCurveEv")(curve);
        vec3d point=symbol<vec3d(*)(const void*,double)>(library,"_ZNK8VspCurve9CompPnt01Ed")(profile,fraction);
        vec3d tangent=symbol<vec3d(*)(const void*,double)>(library,"_ZNK8VspCurve9CompTan01Ed")(profile,fraction);
        std::ostringstream s;s << std::setprecision(17) << "{\"point\":[";
        for(int i=0;i<3;++i){if(i)s << ',';if(std::isfinite(point.v[i]))s << point.v[i];else s << "null";}
        s << "],\"tangent\":[";
        for(int i=0;i<3;++i){if(i)s << ',';if(std::isfinite(tangent.v[i]))s << tangent.v[i];else s << "null";}
        s << "]}";output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_measurements_update(const char* engine) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN19MeasureMgrSingleton11getInstanceEvE8instance");
        symbol<void(*)(void*)>(library,"_ZN19MeasureMgrSingleton6UpdateEv")(manager);
        output="{\"ok\":true}";
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_measurement_drawing(const char* engine,const char* id,int kind) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN19MeasureMgrSingleton11getInstanceEvE8instance");
        symbol<void(*)(void*)>(library,"_ZN19MeasureMgrSingleton6UpdateEv")(manager);
        symbol<void(*)(void*)>(library,"_ZN19MeasureMgrSingleton14UpdateDrawObjsEv")(manager);
        const char* getters[]={"_ZN19MeasureMgrSingleton8GetRulerERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE","_ZN19MeasureMgrSingleton8GetProbeERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE","_ZN19MeasureMgrSingleton11GetRSTProbeERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE","_ZN19MeasureMgrSingleton13GetProtractorERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE"};
        const char* loaders[]={"_ZN5Ruler12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE","_ZN5Probe12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE","_ZN8RSTProbe12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE","_ZN10Protractor12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE"};
        if(kind<0||kind>3)throw std::runtime_error("Unknown native measurement kind.");
        void* measurement=symbol<void*(*)(void*,const std::string&)>(library,getters[kind])(manager,std::string(id));
        if(!measurement)throw std::runtime_error("Native saved measurement unavailable.");
        std::vector<DrawObj*> objects;symbol<void(*)(void*,std::vector<DrawObj*>&)>(library,loaders[kind])(measurement,objects);
        std::ostringstream s;s << std::setprecision(17) << '[';bool first=true;
        for(const auto object:objects){
            std::vector<vec3d> points;std::string topology,label;
            if(object->m_Type==DrawObj::VSP_RULER){points={object->m_Ruler.Start,object->m_Ruler.End};topology="strip";label=object->m_Ruler.Label;}
            else if(object->m_Type==DrawObj::VSP_PROBE){points={object->m_Probe.Pt};topology="points";label=object->m_Probe.Label;}
            else if(object->m_Type==DrawObj::VSP_PROTRACTOR){points={object->m_Protractor.Start,object->m_Protractor.Mid,object->m_Protractor.End};topology="strip";label=object->m_Protractor.Label;}
            else if(object->m_Type==DrawObj::VSP_LINE_STRIP){points=object->m_PntVec;topology="strip";}
            else throw std::runtime_error("Unsupported native measurement drawing type.");
            if(!first)s << ',';first=false;
            s << "{\"nativeID\":" << quote(object->m_GeomID) << ",\"nativeType\":" << int(object->m_Type) << ",\"kind\":" << quote(topology) << ",\"label\":" << quote(label) << ",\"visible\":" << (object->m_Visible?"true":"false") << ",\"points\":[";
            for(size_t i=0;i<points.size();++i){if(i)s << ',';s << '[';for(int j=0;j<3;++j){if(j)s << ',';if(!std::isfinite(points[i].v[j]))throw std::runtime_error("OpenVSP returned undefined measurement drawing coordinates.");s << points[i].v[j];}s << ']';}
            s << "]}";
        }
        s << ']';output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_parasite_units(const char* engine,int kind,int unit) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN24ParasiteDragMgrSingleton11getInstanceEvE8instance");
        const char* methods[]={"_ZN24ParasiteDragMgrSingleton10UpdateVinfEi","_ZN24ParasiteDragMgrSingleton9UpdateAltEi","_ZN24ParasiteDragMgrSingleton10UpdateTempEi","_ZN24ParasiteDragMgrSingleton10UpdatePresEi"};
        if(kind<0||kind>3)throw std::runtime_error("Unknown native parasite-drag unit control.");
        symbol<void(*)(void*,int)>(library,methods[kind])(manager,unit);
        output="{\"ok\":true}";
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_wave_update(const char* engine) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN17WaveDragSingleton11getInstanceEvE8instance");
        symbol<void(*)(void*)>(library,"_ZN17WaveDragSingleton6UpdateEv")(manager);
        output="{\"ok\":true}";
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_wave_drawings(const char* engine) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN17WaveDragSingleton11getInstanceEvE8instance");
        std::vector<DrawObj*> objects;
        symbol<void(*)(void*,std::vector<DrawObj*>&)>(library,"_ZN17WaveDragSingleton12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE")(manager,objects);
        std::ostringstream s;s<<std::setprecision(17)<<'[';bool first=true;
        for(const auto object:objects){
            const char* kind=object->m_Type==DrawObj::VSP_SHADED_TRIS?"triangles":object->m_Type==DrawObj::VSP_LINE_LOOP?"loop":"unsupported";
            if(!first)s<<',';first=false;
            s<<"{\"nativeID\":"<<quote(object->m_GeomID)<<",\"nativeType\":"<<int(object->m_Type)<<",\"kind\":"<<quote(kind)<<",\"visible\":"<<(object->m_Visible?"true":"false")<<",\"opacity\":"<<object->m_MaterialInfo.Diffuse[3]<<",\"points\":[";
            for(size_t i=0;i<object->m_PntVec.size();++i){const auto& p=object->m_PntVec[i];if(i)s<<',';s<<'[';double xyz[]={p.x(),p.y(),p.z()};for(int j=0;j<3;++j){if(j)s<<',';if(std::isfinite(xyz[j]))s<<xyz[j];else s<<"null";}s<<']';}
            s<<"]}";
        }
        s<<']';output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_wave_reference_curves(const char* engine,double volume,double length,double area) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN17WaveDragSingleton11getInstanceEvE8instance");
        std::vector<double> x(100),sh,vk,lh;for(size_t i=0;i<x.size();++i)x[i]=double(i)/double(x.size()-1);
        symbol<void(*)(void*,const std::vector<double>&,std::vector<double>&,double,double)>(library,"_ZNK17WaveDragSingleton10SearsHaackERKNSt3__16vectorIdNS0_9allocatorIdEEEERS4_dd")(manager,x,sh,volume,length);
        using Curve=void(*)(void*,const std::vector<double>&,std::vector<double>&,double);
        symbol<Curve>(library,"_ZNK17WaveDragSingleton9vonKarmanERKNSt3__16vectorIdNS0_9allocatorIdEEEERS4_d")(manager,x,vk,area);
        symbol<Curve>(library,"_ZNK17WaveDragSingleton9LighthillERKNSt3__16vectorIdNS0_9allocatorIdEEEERS4_d")(manager,x,lh,area);
        std::ostringstream s;s<<std::setprecision(17)<<"{\"xNormalized\":";
        auto values=[&](const std::vector<double>& a){s<<'[';for(size_t i=0;i<a.size();++i){if(i)s<<',';if(std::isfinite(a[i]))s<<a[i];else s<<"null";}s<<']';};
        values(x);s<<",\"searsHaack\":";values(sh);s<<",\"vonKarman\":";values(vk);s<<",\"lighthill\":";values(lh);s<<'}';output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_wave_plot_data(const char* engine,const char* machParm,const char* slicesParm) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto manager=symbol<WaveDragSingleton*>(library,"_ZZN17WaveDragSingleton11getInstanceEvE8instance");
        void* parms=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");
        auto find=symbol<Parm*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton8FindParmERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE");
        if(find(parms,std::string(machParm))!=&manager->m_MachNumber || find(parms,std::string(slicesParm))!=&manager->m_NumSlices)
            throw std::runtime_error("Native wave manager does not match the pinned declarations.");
        std::ostringstream s;s<<std::setprecision(17);
        auto scalar=[&](double value){if(std::isfinite(value))s<<value;else s<<"null";};
        auto vector=[&](const std::vector<double>& values){s<<'[';for(size_t i=0;i<values.size();++i){if(i)s<<',';scalar(values[i]);}s<<']';};
        auto matrix=[&](const std::vector<std::vector<double>>& values){s<<'[';for(size_t i=0;i<values.size();++i){if(i)s<<',';vector(values[i]);}s<<']';};
        s<<"{\"xNormalized\":";vector(manager->m_XNorm);s<<",\"xFitNormalized\":";vector(manager->m_XNormFit);
        s<<",\"componentIds\":[";for(size_t i=0;i<manager->m_CompIDVec.size();++i){if(i)s<<',';s<<quote(manager->m_CompIDVec[i]);}
        s<<"],\"inletArea\":";scalar(manager->m_InletArea);s<<",\"exitArea\":";scalar(manager->m_ExitArea);
        s<<",\"selectedCone\":"<<static_cast<const Parm&>(manager->m_ThetaIndex).Get()<<",\"selectedIdealBody\":"<<static_cast<const Parm&>(manager->m_IdealBodyType).Get()<<",\"selectedAreaMode\":"<<static_cast<const Parm&>(manager->m_AreaPlotType).Get()<<",\"showPoints\":"<<(manager->m_PointFlag()?"true":"false")<<",\"cones\":[";
        if(manager->m_NTheta<0 || manager->m_NTheta>10000)throw std::runtime_error("Invalid native wave cone count.");
        for(int i=0;i<manager->m_NTheta;++i){
            if(i)s<<',';s<<"{\"coneIndex\":"<<i+1;
            s<<",\"flowSlices\":";vector(manager->m_SliceAreaDistFlow.at(i));s<<",\"totalSlices\":";vector(manager->m_SliceAreaDist.at(i));
            s<<",\"flowFit\":";vector(manager->m_FitAreaDistFlow.at(i));s<<",\"totalFit\":";vector(manager->m_FitAreaDist.at(i));
            s<<",\"componentSlices\":";matrix(manager->m_CompSliceAreaDist.at(i));s<<",\"componentFit\":";matrix(manager->m_CompFitAreaDist.at(i));
            s<<",\"buildupSlices\":";matrix(manager->m_BuildupAreaDist.at(i));s<<",\"buildupFit\":";matrix(manager->m_BuildupFitAreaDist.at(i));s<<'}';
        }
        s<<"]}";output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_geom_features(const char* engine,const char* geom) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* component=find(std::string(geom),"Studio feature lines");if(!component)throw std::runtime_error("Component unavailable.");
        symbol<void(*)(void*)>(library,"_ZN4Geom13UpdateDrawObjEv")(component);
        std::vector<DrawObj*> objects;
        symbol<void(*)(void*,std::vector<DrawObj*>&)>(library,"_ZN4Geom12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE")(component,objects);
        std::ostringstream s;s<<std::setprecision(17)<<'[';bool first=true;
        for(const auto object:objects){
            if(object->m_Type!=DrawObj::VSP_LINES||object->m_GeomID.rfind(std::string(geom)+"Feature_",0)!=0)continue;
            if(object->m_PntVec.size()%2)throw std::runtime_error("Native feature line has incomplete connectivity.");
            if(!first)s<<',';first=false;s<<"{\"nativeID\":"<<quote(object->m_GeomID)<<",\"segments\":[";
            for(size_t i=0;i<object->m_PntVec.size();i+=2){if(i)s<<',';s<<'[';for(int j=0;j<2;++j){if(j)s<<',';const auto& p=object->m_PntVec[i+j];double xyz[]={p.x(),p.y(),p.z()};s<<'[';for(int k=0;k<3;++k){if(k)s<<',';if(!std::isfinite(xyz[k]))throw std::runtime_error("Native feature line contains undefined coordinates.");s<<xyz[k];}s<<']';}s<<']';}s<<"]}";
        }
        s<<']';output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_section_copy_surfaces(const char* engine,const char* source,const char* target,int sourceIndex,int targetIndex) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&)>(library,"_ZN3vsp12FindXSecSurfERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE");
        void* from=find(std::string(source));void* to=find(std::string(target));if(!from||!to)throw std::runtime_error("Choose existing section surfaces.");
        symbol<void(*)(void*,int)>(library,"_ZN8XSecSurf8CopyXSecEi")(from,sourceIndex);
        symbol<void(*)(void*,int)>(library,"_ZN8XSecSurf9PasteXSecEi")(to,targetIndex);
        output="{\"ok\":true}";
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_blank_drawings(const char* engine,const char* geom) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* component=find(std::string(geom),"Studio reference drawing");if(!component)throw std::runtime_error("Reference component unavailable.");
        symbol<void(*)(void*)>(library,"_ZN9BlankGeom13UpdateDrawObjEv")(component);
        std::vector<DrawObj*> objects;symbol<void(*)(void*,std::vector<DrawObj*>&)>(library,"_ZN9BlankGeom12LoadDrawObjsERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEE")(component,objects);
        std::ostringstream s;s<<std::setprecision(17)<<'[';bool first=true;
        for(const auto object:objects){
            const bool lines=object->m_Type==DrawObj::VSP_LINES,points=object->m_Type==DrawObj::VSP_POINTS;if(!lines&&!points)continue;
            if(!first)s<<',';first=false;const auto& color=lines?object->m_LineColor:object->m_PointColor;
            s<<"{\"nativeID\":"<<quote(object->m_GeomID)<<",\"kind\":"<<quote(lines?"lines":"points")<<",\"visible\":"<<(object->m_Visible?"true":"false")<<",\"color\":["<<color.x()<<','<<color.y()<<','<<color.z()<<"],\"points\":[";
            for(size_t i=0;i<object->m_PntVec.size();++i){if(i)s<<',';const auto& p=object->m_PntVec[i];double xyz[]={p.x(),p.y(),p.z()};s<<'[';for(int k=0;k<3;++k){if(k)s<<',';if(!std::isfinite(xyz[k]))throw std::runtime_error("Native reference drawing contains undefined coordinates.");s<<xyz[k];}s<<']';}s<<"]}";
        }s<<']';output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// Exact GeomType data members from matching 3.52.2 Geom.h. Construction and
// geometry creation run in the original library; no geometry is synthesized.
struct StudioCustomGeomType {
    int m_Type; std::string m_Name; bool m_FixedFlag; bool m_AdoptableFlag;
    std::string m_ModuleName; std::string m_DisplayName;
};
extern "C" const char* studio_custom_script_import(const char* engine,const char* path,const char* name,const char* parent) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* scripts=symbol<void*>(library,"_ZZN18ScriptMgrSingleton11getInstanceEvE8instance");
        std::string content=symbol<std::string(*)(const std::string&)>(library,"_ZN18ScriptMgrSingleton14ExtractContentERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(std::string(path));
        std::string filename(path);auto slash=filename.find_last_of('/');std::string directory=slash==std::string::npos?std::string():filename.substr(0,slash+1);
        content=symbol<std::string(*)(void*,const std::string&,const std::string&)>(library,"_ZN18ScriptMgrSingleton15ReplaceIncludesERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_")(scripts,content,directory);
        std::string module=symbol<std::string(*)(void*,const std::string&,const std::string&)>(library,"_ZN18ScriptMgrSingleton20ReadScriptFromMemoryERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_")(scripts,std::string(name),content);
        if(module.empty())throw std::runtime_error("OpenVSP could not compile the custom component script.");
        void* manager=symbol<void*(*)()>(library,"_ZN19VehicleMgrSingleton11getInstanceEv")();
        void* vehicle=symbol<void*(*)(void*)>(library,"_ZN19VehicleMgrSingleton10GetVehicleEv")(manager);
        if(parent && *parent)symbol<void(*)(void*,const std::string&)>(library,"_ZN7Vehicle13SetActiveGeomERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(vehicle,std::string(parent));
        alignas(StudioCustomGeomType) unsigned char storage[sizeof(StudioCustomGeomType)];
        auto type=reinterpret_cast<StudioCustomGeomType*>(storage);
        symbol<void(*)(void*,int,const std::string&,bool,const std::string&,const std::string&)>(library,"_ZN8GeomTypeC1EiRKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEEbS8_S8_")(type,9,module,false,module,std::string(name));
        std::string id=symbol<std::string(*)(void*,const StudioCustomGeomType&)>(library,"_ZN7Vehicle7AddGeomERK8GeomType")(vehicle,*type);
        type->~StudioCustomGeomType();
        if(id.empty())throw std::runtime_error("OpenVSP did not create the custom component.");
        output=quote(id);
    }catch(const std::exception& e){output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_custom_script_expand(const char* engine,const char* path) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* scripts=symbol<void*>(library,"_ZZN18ScriptMgrSingleton11getInstanceEvE8instance");
        std::string content=symbol<std::string(*)(const std::string&)>(library,"_ZN18ScriptMgrSingleton14ExtractContentERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(std::string(path));
        std::string filename(path);auto slash=filename.find_last_of('/');std::string directory=slash==std::string::npos?std::string():filename.substr(0,slash+1);
        content=symbol<std::string(*)(void*,const std::string&,const std::string&)>(library,"_ZN18ScriptMgrSingleton15ReplaceIncludesERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_")(scripts,content,directory);
        output=quote(content);
    }catch(const std::exception& e){output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

#include "GuiDeviceEnums.h"
extern "C" const char* studio_custom_gui_definitions(const char* engine,const char* geom) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN22CustomGeomMgrSingleton11getInstanceEvE8instance");
        auto definitions=symbol<std::vector<GuiDef>(*)(void*,const std::string&)>(library,"_ZN22CustomGeomMgrSingleton12GetGuiDefVecERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(manager,std::string(geom));
        std::ostringstream json;json<<'[';bool first=true;
        for(size_t i=0;i<definitions.size();++i){auto& d=definitions[i];if(!first)json<<',';first=false;json<<"{\"index\":"<<i<<",\"type\":"<<d.m_Type<<",\"label\":"<<quote(d.m_Label)<<",\"parameter\":"<<quote(d.m_ParmName)<<",\"group\":"<<quote(d.m_GroupName)<<",\"range\":";if(std::isfinite(d.m_Range))json<<std::setprecision(17)<<d.m_Range;else json<<"null";json<<'}';}
        json<<']';output=json.str();
    }catch(const std::exception& e){output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_custom_gui_updates(const char* engine,const char* geom) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN22CustomGeomMgrSingleton11getInstanceEvE8instance");
        symbol<std::vector<GuiDef>(*)(void*,const std::string&)>(library,"_ZN22CustomGeomMgrSingleton12GetGuiDefVecERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(manager,std::string(geom));
        auto updates=symbol<std::vector<GuiUpdate>(*)(void*)>(library,"_ZN22CustomGeomMgrSingleton15GetGuiUpdateVecEv")(manager);
        std::ostringstream json;json<<'[';bool first=true;
        for(auto& u:updates){if(!first)json<<',';first=false;json<<"{\"index\":"<<u.m_GuiID<<",\"parameterId\":"<<quote(u.m_ParmID)<<'}';}
        json<<']';output=json.str();
    }catch(const std::exception& e){output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_custom_gui_trigger(const char* engine,const char* geom,int index) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* component=find(std::string(geom),"Studio custom trigger");
        if(!component)throw std::runtime_error("Custom component unavailable.");
        symbol<void(*)(void*,int)>(library,"_ZN10CustomGeom18AddGuiTriggerEventEi")(component,index);
        output="true";
    }catch(const std::exception& e){output="{\"error\":"+quote(e.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_section_curve_clipboard(const char* engine,const char* surface,int index,int operation) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&)>(library,"_ZN3vsp12FindXSecSurfERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE");
        void* surf=find(std::string(surface));if(!surf)throw std::runtime_error("Choose an existing section surface.");
        const char* method=operation==0?"_ZN8XSecSurf13CopyXSecCurveEi":"_ZN8XSecSurf14PasteXSecCurveEi";
        symbol<void(*)(void*,int)>(library,method)(surf,index);output="{\"ok\":true}";
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// Matching GeomBase::SURF == 3. Native curve clipboard updates may leave the
// owner's surface cache clean; request original geometry evaluation explicitly.
extern "C" const char* studio_refresh_section_owner(const char* engine,const char* geom) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* owner=find(std::string(geom),"Studio section refresh");if(!owner)throw std::runtime_error("Section owner unavailable.");
        symbol<void(*)(void*,int)>(library,"_ZN8GeomBase12SetDirtyFlagEi")(owner,3);output="{\"ok\":true}";
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// Original native patch counts detect unsuccessful custom skinning before sampling.
extern "C" const char* studio_surface_topology(const char* engine,const char* geom,int count) {
    static thread_local std::string output;void* library=nullptr;
    try {
        if(count<0 || count>10000)throw std::runtime_error("Invalid native surface count.");
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* component=find(std::string(geom),"Studio native surface validation");
        if(!component)throw std::runtime_error("Native component unavailable.");
        auto get=symbol<const void*(*)(const void*,int)>(library,"_ZNK4Geom14GetMainSurfPtrEi");
        auto u=symbol<int(*)(const void*)>(library,"_ZNK7VspSurf11GetNumSectUEv");
        auto w=symbol<int(*)(const void*)>(library,"_ZNK7VspSurf11GetNumSectWEv");
        std::ostringstream s;s << '[';
        for(int i=0;i<count;++i){if(i)s << ',';const void* surface=get(component,i);if(!surface)throw std::runtime_error("Native surface unavailable.");s << "{\"index\":" << i << ",\"uPatches\":" << u(surface) << ",\"wPatches\":" << w(surface) << '}';}
        s << ']';output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// Python validates owner/type, row topology, native limits and references first.
// Match original SetEditXSecPnts: native SetPntVecs owns all curve evaluation.
extern "C" const char* studio_edit_curve_point_list(const char* engine,const char* container,int type,int count,const double* rows) {
    static thread_local std::string output;void* library=nullptr;
    try {
        if(count<2||count>10000||!rows)throw std::runtime_error("Invalid native point-list size.");
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");
        void* curve=symbol<void*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton17FindParmContainerERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(manager,std::string(container));
        if(!curve)throw std::runtime_error("Native editable profile unavailable.");
        std::vector<double> u,x,y,z,r;
        for(int i=0;i<count;++i){u.push_back(rows[5*i]);x.push_back(rows[5*i+1]);y.push_back(rows[5*i+2]);z.push_back(rows[5*i+3]);r.push_back(rows[5*i+4]);}
        symbol<void(*)(void*,int)>(library,"_ZN13EditCurveXSec9ConvertToEi")(curve,type);
        symbol<void(*)(void*,const std::vector<double>&,const std::vector<double>&,const std::vector<double>&,const std::vector<double>&,const std::vector<double>&,std::vector<bool>,std::vector<bool>,bool)>(library,"_ZN13EditCurveXSec10SetPntVecsERKNSt3__16vectorIdNS0_9allocatorIdEEEES6_S6_S6_S6_NS1_IbNS2_IbEEEES8_b")(curve,u,x,y,z,r,{}, {},true);
        output="{}";
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// Evaluate the original native equations before committing a driver choice.
extern "C" const char* studio_evaluate_wing_drivers(const char* engine,const char* geom,int section,const int* choices) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* wing=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_")(std::string(geom),"Studio wing driver evaluation");
        if(!wing)throw std::runtime_error("Native wing unavailable.");
        void* sect=symbol<void*(*)(void*,int)>(library,"_ZN8WingGeom11GetWingSectEi")(wing,section);
        if(!sect||!choices)throw std::runtime_error("Native wing section unavailable.");
        auto ids=symbol<std::vector<std::string>(*)(void*)>(library,"_ZN8WingSect14GetDriverParmsEv")(sect);
        alignas(WingDriverGroup) unsigned char storage[sizeof(WingDriverGroup)];
        auto destroy=local_symbol<void(*)(void*)>(library,engine,"_ZN15WingDriverGroupD1Ev");
        symbol<void(*)(void*)>(library,"_ZN15WingDriverGroupC1Ev")(storage);
        try {
            symbol<void(*)(void*,const std::vector<int>&)>(library,"_ZN11DriverGroup10SetChoicesERKNSt3__16vectorIiNS0_9allocatorIiEEEE")(storage,{choices[0],choices[1],choices[2]});
            symbol<void(*)(void*,std::vector<std::string>)>(library,"_ZN15WingDriverGroup11UpdateGroupENSt3__16vectorINS0_12basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEENS5_IS7_EEEE")(storage,ids);
        }catch(...){destroy(storage);throw;}
        destroy(storage);output="{}";
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

// CpSlice owns both plane and border DrawObjs. Geometry stays in its original
// CreateSurf/LoadDrawObj routines; only finite native drawing records are copied.
extern "C" const char* studio_cutting_plane_drawings(const char* engine,const char* id,int index) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        void* manager=symbol<void*>(library,"_ZZN16ParmMgrSingleton11getInstanceEvE8instance");
        void* plane=symbol<void*(*)(void*,const std::string&)>(library,"_ZN16ParmMgrSingleton17FindParmContainerERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE")(manager,std::string(id));
        if(!plane)throw std::runtime_error("Native cutting plane unavailable.");
        std::vector<DrawObj*> objects;
        symbol<void(*)(void*,std::vector<DrawObj*>&,int,bool)>(library,"_ZN7CpSlice11LoadDrawObjERNSt3__16vectorIP7DrawObjNS0_9allocatorIS3_EEEEib")(plane,objects,index,false);
        std::ostringstream s;s<<std::setprecision(17)<<'[';bool first=true;
        for(const auto object:objects){
            const bool face=object->m_Type==DrawObj::VSP_SHADED_QUADS,border=object->m_Type==DrawObj::VSP_LINE_LOOP;
            if(!face&&!border)throw std::runtime_error("Unsupported native cutting-plane drawing type.");
            if(object->m_PntVec.size()!=4)throw std::runtime_error("Unexpected native cutting-plane point count.");
            if(!first)s<<',';first=false;
            s<<"{\"nativeID\":"<<quote(object->m_GeomID)<<",\"nativeType\":"<<int(object->m_Type)<<",\"kind\":"<<quote(face?"quads":"loop")<<",\"visible\":"<<(object->m_Visible?"true":"false")<<",\"opacity\":"<<(face?object->m_MaterialInfo.Diffuse[3]:1)<<",\"points\":[";
            for(size_t i=0;i<object->m_PntVec.size();++i){if(i)s<<',';const auto& p=object->m_PntVec[i];s<<'[';for(int k=0;k<3;++k){if(k)s<<',';if(!std::isfinite(p.v[k]))throw std::runtime_error("Native cutting plane contains undefined coordinates.");s<<p.v[k];}s<<']';}s<<"]}";
        }s<<']';output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_script_xml_text(const char* engine,const char* text,bool decode) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        const char* name=decode?"_ZN7XmlUtil23ConvertFromXMLSafeCharsERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE":"_ZN7XmlUtil21ConvertToXMLSafeCharsERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE";
        output=quote(symbol<std::string(*)(const std::string&)>(library,name)(std::string(text)));
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_cloud_transform(const char* engine,const char* geom,const double* coordinates,int count,bool inverse) {
    static thread_local std::string output;void* library=nullptr;
    try {
        if(count<0 || count>10000000 || (count && !coordinates))throw std::runtime_error("Invalid native point list.");
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* component=find(std::string(geom),"Studio point-cloud transform");
        if(!component)throw std::runtime_error("Native point cloud unavailable.");
        Matrix4d matrix=symbol<Matrix4d(*)(const void*)>(library,"_ZNK11PtCloudGeom16GetTotalTransMatEv")(component);
        if(inverse)symbol<void(*)(Matrix4d*)>(library,"_ZN8Matrix4d13affineInverseEv")(&matrix);
        auto transform=symbol<vec3d(*)(const Matrix4d*,const vec3d&)>(library,"_ZNK8Matrix4d5xformERK5vec3d");
        auto construct=symbol<void(*)(void*,double,double,double)>(library,"_ZN5vec3dC1Eddd");
        std::ostringstream s;s << std::setprecision(17) << '[';
        for(int i=0;i<count;++i){
            for(int k=0;k<3;++k)if(!std::isfinite(coordinates[3*i+k]))throw std::runtime_error("Point coordinates must be finite.");
            alignas(vec3d) unsigned char storage[sizeof(vec3d)];construct(storage,coordinates[3*i],coordinates[3*i+1],coordinates[3*i+2]);
            vec3d point=transform(&matrix,*reinterpret_cast<vec3d*>(storage));
            for(double x:point.v)if(!std::isfinite(x))throw std::runtime_error("Native cloud transform produced undefined coordinates.");
            if(i)s << ',';s << '[' << point.v[0] << ',' << point.v[1] << ',' << point.v[2] << ']';
        }
        s << ']';output=s.str();
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}

extern "C" const char* studio_cloud_refresh(const char* engine,const char* geom) {
    static thread_local std::string output;void* library=nullptr;
    try {
        library=dlopen(engine,RTLD_NOW);if(!library)throw std::runtime_error(dlerror());
        auto find=symbol<void*(*)(const std::string&,const std::string&)>(library,"_ZN3vsp13FindGeomForOpERKNSt3__112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_");
        void* component=find(std::string(geom),"Studio point-cloud scale refresh");
        if(!component)throw std::runtime_error("Native point cloud unavailable.");
        symbol<void(*)(void*,double)>(library,"_ZN11PtCloudGeom10ApplyScaleEd")(component,1.0);
        symbol<void(*)(void*)>(library,"_ZN11PtCloudGeom10UpdateBBoxEv")(component);
        symbol<void(*)(void*)>(library,"_ZN11PtCloudGeom13UpdateDrawObjEv")(component);
        output="{}";
    }catch(const std::exception& error){output="{\"error\":"+quote(error.what())+"}";}
    if(library)dlclose(library);return output.c_str();
}
