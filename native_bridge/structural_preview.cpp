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
        for(size_t i=0;i<definitions.size();++i){auto& d=definitions[i];if(!first)json<<',';first=false;json<<"{\"index\":"<<i<<",\"type\":"<<d.m_Type<<",\"label\":"<<quote(d.m_Label)<<",\"parameter\":"<<quote(d.m_ParmName)<<",\"group\":"<<quote(d.m_GroupName)<<'}';}
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
