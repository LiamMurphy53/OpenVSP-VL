"""Read exact native region polygons, including main surfaces and symmetry copies."""
import math
from native_tools import one


def regions(v, request):
    geoms=list(v.FindGeoms())
    if request.get('geom') is not None:geoms=[one(request['geom'],geoms)]
    records=[dict(id=s,geom=g,name=v.GetSubSurfName(s),type=v.GetSubSurfType(s),paths=[])
             for g in geoms for s in v.GetSubSurfIDVec(g)]
    result=dict(version=v.GetVSPVersion(),engineOperation='DegenGeom',regions=records,warnings=[])
    if not records:return result
    # Native results identify regions by name rather than stable native ID.
    # Unique temporary labels avoid ambiguity when users reuse names. This
    # runs in a read-only query worker, restores names, and never writes a model.
    labels={'studio_region_'+r['id']:r for r in records}
    selected={r['geom'] for r in records if v.GetTotalNumSurfs(r['geom'])>0}
    if selected:
        slot=v.GetNumSets()-1
        old_members={g:v.GetSetFlag(g,slot) for g in v.FindGeoms()}
        try:
            for label,r in labels.items():v.SetSubSurfName(r['id'],label)
            for g in old_members:v.SetSetFlag(g,slot,g in selected)
            v.Update();v.SetAnalysisInputDefaults('DegenGeom')
            v.SetIntAnalysisInput('DegenGeom','Set',[slot])
            v.SetIntAnalysisInput('DegenGeom','UseModeFlag',[0])
            for key in ('WriteCSVFlag','WriteMFileFlag'):v.SetIntAnalysisInput('DegenGeom',key,[0])
            rid=v.ExecAnalysis('DegenGeom')
            from native_worker import errors
            errors(v)
            if not rid:raise ValueError('OpenVSP did not return native region boundaries.')
            for parent in v.GetStringResults(rid,'Degen_DegenGeoms'):
                geom=v.GetStringResults(parent,'geom_id')[0]
                surface=v.GetIntResults(parent,'surf_index')[0]
                main=v.GetIntResults(parent,'main_surf_index')[0]
                copy=v.GetIntResults(parent,'sym_copy_index')[0]
                for child in v.GetStringResults(parent,'subsurfs'):
                    record=labels.get(v.GetStringResults(child,'name')[0])
                    if not record or record['geom']!=geom:continue
                    points=[[p.x(),p.y(),p.z()] for p in v.GetVec3dResults(child,'x')]
                    u=list(v.GetDoubleResults(child,'u'));w=list(v.GetDoubleResults(child,'w'))
                    valid=bool(points) and len(u)==len(w)==len(points) and all(math.isfinite(x) for p in points for x in p)
                    record['paths'].append(dict(surface=surface,mainSurface=main,symmetryCopy=copy,
                        points=points,u=u,w=w,valid=valid,nativeResultID=child,
                        typeName=v.GetStringResults(child,'typeName')[0],testType=v.GetIntResults(child,'testType')[0]))
        finally:
            for r in records:v.SetSubSurfName(r['id'],r['name'])
            for g,flag in old_members.items():v.SetSetFlag(g,slot,flag)
    for r in records:
        if not r['paths']:result['warnings'].append(r['name']+': the native engine returned no boundary paths. Configure or compute this region before inspecting it.')
        elif any(not p['valid'] for p in r['paths']):result['warnings'].append(r['name']+': some native boundary samples are empty or undefined; those paths are omitted from the display.')
    return result
