"""Guided native wing drivers; all dependency calculations stay in OpenVSP."""
import native_preview

DRIVERS=(('AR_WSECT_DRIVER','Aspect ratio'),('SPAN_WSECT_DRIVER','Section span'),
         ('AREA_WSECT_DRIVER','Section area'),('TAPER_WSECT_DRIVER','Taper ratio'),
         ('AVEC_WSECT_DRIVER','Average chord'),('ROOTC_WSECT_DRIVER','Root chord'),
         ('TIPC_WSECT_DRIVER','Tip chord'),('SECSWEEP_WSECT_DRIVER','Secondary sweep'))
OUTPUTS={'MAC','CurvedArea','TotalAR','SmallPanelW','MaxGrowth'}


def enrich(v,gid,params,sections):
    by_id={p['id']:p for p in params}
    for p in params:
        if p['rawGroup']=='WingGeom' and p['name'] in OUTPUTS:
            p['displayReadOnly']=True;p['readOnlyReason']='Calculated by OpenVSP from the wing geometry.'
    for section in sections:
        # Wing sections have a native driver group on surface 0. The root
        # boundary's values follow its neighboring section, and cannot be
        # selected as a separate independent wing section in the native UI.
        if section['surface']!=0:continue
        ids=native_preview.wing_driver_parameters(v,gid,section['index'])
        choices=section.get('drivers',[])
        descriptors=[]
        for enum,label in DRIVERS:
            value=getattr(v,enum);p=by_id[ids[value]]
            p['wingDriver']=value;p['wingSection']=section['index'];p['displayReadOnly']=value not in choices
            if p['displayReadOnly']:p['readOnlyReason']='Calculated by OpenVSP from the selected wing-section drivers.' if choices else 'Root boundary dimension follows the first wing section.'
            descriptors.append(dict(value=value,label=label,parameter=p['id']))
        for name in ('ProjectedSpan',):
            for p in params:
                if p['rawGroup']=='XSec' and p['group']==by_id[ids[0]]['group'] and p['name']==name:
                    p['displayReadOnly']=True;p['readOnlyReason']='Projected section span is calculated by OpenVSP.'
        if choices:
            section['driverControls']=descriptors
            # Native IDs also include sweep and both reference locations.
            section['driverParameterIDs']=ids
            group=by_id[ids[0]]['group']
            section['shapeParameterIDs']=[p['id'] for p in params if p['rawGroup']=='XSec' and p['group']==group and p['name'] in ('Dihedral','Twist','Twist_Location')]


def validate_parameter(v,pid):
    owner=next((g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='WING' and pid in v.GetGeomParmIDs(g)),None)
    if not owner:return
    if v.GetParmGroupName(pid)=='WingGeom':
        if v.GetParmName(pid) in OUTPUTS:raise ValueError('OpenVSP calculates this wing output. Edit wing dimensions or section drivers instead.')
        return
    if v.GetParmGroupName(pid)!='XSec':return
    surf=v.GetXSecSurf(owner,0)
    for index in range(v.GetNumXSec(surf)):
        ids=native_preview.wing_driver_parameters(v,owner,index)
        if pid in ids[:8]:
            if index==0:raise ValueError('This root boundary dimension follows the first wing section. Edit section 1 instead.')
            choices=list(v.GetDriverGroup(owner,index))
            if ids.index(pid) not in choices:raise ValueError('OpenVSP calculates this section dimension. Select it as one of the three wing-section drivers before editing it.')
            return
        pgroup=v.GetParmDisplayGroupName(ids[0])
        if v.GetParmName(pid)=='ProjectedSpan' and v.GetParmDisplayGroupName(pid)==pgroup:raise ValueError('OpenVSP calculates projected section span. Edit section span or dihedral instead.')


def read_only_reasons(v):
    """Expose the same driver policy to frozen-aircraft parameter studies."""
    result={}
    for gid in v.FindGeoms():
        if v.GetGeomTypeName(gid).upper()!='WING':continue
        pids=v.GetGeomParmIDs(gid)
        for pid in pids:
            if v.GetParmGroupName(pid)=='WingGeom' and v.GetParmName(pid) in OUTPUTS:result[pid]='Calculated by OpenVSP from the wing geometry.'
        surf=v.GetXSecSurf(gid,0)
        for index in range(v.GetNumXSec(surf)):
            ids=native_preview.wing_driver_parameters(v,gid,index)
            choices=list(v.GetDriverGroup(gid,index)) if index else []
            for number,pid in enumerate(ids[:8]):
                if number not in choices:result[pid]='Calculated by OpenVSP from the saved wing-section drivers.' if index else 'Root boundary dimension follows the first wing section.'
            group=v.GetParmDisplayGroupName(ids[0])
            for pid in pids:
                if v.GetParmDisplayGroupName(pid)==group and v.GetParmName(pid)=='ProjectedSpan':result[pid]='Projected section span is calculated by OpenVSP.'
    return result


def validate_drivers(v,gid,surface,index,choices):
    if v.GetGeomTypeName(gid).upper()!='WING' or surface!=0 or index<1:raise ValueError('Choose wing section 1 or later for independent section drivers.')
    if not isinstance(choices,list) or len(choices)!=3 or any(type(x)!=int for x in choices) or sorted(choices) not in native_preview.wing_driver_combinations(v):
        raise ValueError('OpenVSP does not support these three drivers. Choose three different independent section dimensions.')
