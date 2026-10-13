"""Evaluate an exact native structural region through OpenVSP's exposed lookup.

The caller temporarily relocates its native XML node into the parent geometry's
region list because the installed generic API does not search FEA regions.
Only OpenVSP generates the intersection and native editable curve.
"""
import json
from pathlib import Path
import sys
from vsp_runtime import load


def compute(model,region,target,curve):
    v=load();v.ClearVSPModel();v.ReadVSPFile(str(model));v.Update()
    import native_gear_retraction
    native_gear_retraction.refresh(v)
    manager=v.ErrorMgrSingleton.getInstance()
    def check():
        messages=[]
        while manager.GetNumTotalErrors():messages.append(manager.PopLastError().m_ErrorString)
        if messages:raise ValueError('; '.join(messages))
    check()
    if v.GetSubSurfType(region)!=v.SS_INTERSECT:raise ValueError('Choose a native intersection region.')
    v.SetIntersectSubSurfGeomID(region,target)
    pid=v.FindParm(region,'ICurve','SS_Intersect')
    if not v.GetParmLowerLimit(pid)<=curve<=v.GetParmUpperLimit(pid):raise ValueError('Choose an intersection curve within the native limits.')
    v.SetParmVal(pid,curve);v.Update();v.IntersectSubSurf(region);v.Update();check()
    count=int(v.GetParmVal(v.FindParm(region,'NCurves','SS_Intersect')))
    if not count:raise ValueError('OpenVSP found no intersection curves on this surface. The saved region is unchanged.')
    if curve>=count:raise ValueError(f'OpenVSP found {count} intersection curves. Choose a curve from 1 to {count}.')
    v.WriteVSPFile(str(model),v.SET_ALL);check()
    return dict(nativeCurveCount=count,nativeCurveIndex=int(v.GetParmVal(pid)))


if __name__=='__main__':
    request,model,response=map(Path,sys.argv[1:4])
    try:
        r=json.loads(request.read_text());result=compute(model,r['region'],r['target'],r['curve']);response.write_text(json.dumps(result))
    except Exception as exc:
        response.write_text(json.dumps(dict(error=str(exc))));raise
