"""Resolve native settings managers independently of component display names.

FindContainer(name, 0) can return a geometry using that name. Verify native
manager fields and exclude geometry/user owners before using manager APIs.
"""
SIGNATURES={
 'CFDMeshSettings':{('Global','Set'),('Global','DegenSet'),('Global','UseMode')},
 'SurfaceIntersectSettings':{('Global','Set'),('Global','DegenSet'),('ExportIntersect','CADLenUnit')},
 'CFDGridDensity':{('CFDGridDensity','BaseLen'),('CFDGridDensity','MinLen'),('CFDGridDensity','MaxGap')},
 'VSPAEROSettings':{('VSPAERO','GeomSet'),('VSPAERO','ThinGeomSet'),('VSPAERO','MassSet')},
 'WaveDragSettings':{('WaveDrag','SelSetIndex'),('WaveDrag','NumRotSects')},
 'ParasiteDragSettings':{('ParasiteDrag','Set'),('ParasiteDrag','TempUnit'),('ParasiteDrag','Vinf')},
}
NAMES={'Vehicle',*SIGNATURES}


def manager(v,name):
    if name=='Vehicle':return v.GetVehicleID()
    signature=SIGNATURES[name];excluded=set(v.FindGeoms())|{v.GetUserParmContainer()};matches=[]
    for candidate in v.FindContainersWithName(name):
        if candidate in excluded:continue
        fields={(v.GetParmGroupName(p),v.GetParmName(p)) for p in v.FindContainerParmIDs(candidate)}
        if signature<=fields:matches.append(candidate)
    if len(matches)!=1:raise ValueError('The original '+name+' manager is unavailable or ambiguous.')
    return matches[0]


def ids(v):
    resolved={manager(v,name) for name in NAMES}
    return [c for c in v.FindContainers() if c in resolved]
