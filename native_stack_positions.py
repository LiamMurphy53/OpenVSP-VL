"""Native Stack section coordinate bases and StackScreen eligibility."""
RELATIVE=('XDelta','YDelta','ZDelta','XRotate','YRotate','ZRotate')
ABSOLUTE=('XAbs','YAbs','ZAbs','XRotateAbs','YRotateAbs','ZRotateAbs')
NAMES=set(RELATIVE+ABSOLUTE+('XSAbsRelFlag','Spin','VAlign'))


def context(v,pid):
    if v.GetParmGroupName(pid)!='XSec' or v.GetParmName(pid) not in NAMES:return None
    container=v.GetParmContainer(pid)
    for gid in v.FindGeoms():
        if v.GetGeomTypeName(gid).upper()!='STACK':continue
        for surface in range(v.GetNumXSecSurfs(gid)):
            surf=v.GetXSecSurf(gid,surface);count=v.GetNumXSec(surf)
            for index in range(count):
                xid=v.GetXSec(surf,index)
                if xid==container:return gid,xid,index,count
    return None


def reason(v,pid,found=None):
    found=found or context(v,pid)
    if found is None:return None
    gid,xid,index,count=found;name=v.GetParmName(pid)
    if index==0 and name not in ('Spin','VAlign'):return 'The first stack profile anchors the section chain; its placement controls are fixed in OpenVSP’s section editor.'
    if index==count-1 and v.GetParmVal(gid,'OrderPolicy','Design')==1:
        return 'OpenVSP closes the stack loop using the final profile. Choose Free section ordering to edit its placement.'
    relative=v.GetParmVal(v.GetXSecParm(xid,'XSAbsRelFlag'))==v.REL
    if (relative and name in ABSOLUTE) or (not relative and name in RELATIVE):
        return 'Calculated by OpenVSP from the selected section coordinate basis. Change Coordinate basis to edit this representation.'
    return None


def annotate(v,p):
    found=context(v,p['id']) if p['name'] in NAMES and p['rawGroup']=='XSec' else None
    if found is None:return
    name=p['name']
    if name=='XSAbsRelFlag':p.update(label='Coordinate basis',choices=[[v.REL,'Relative to previous section'],[v.ABS,'Absolute in component axes']],description='Select the native position and rotation representation for this stack profile. Absolute coordinates use component axes, before the component placement transform.')
    elif name in RELATIVE+ABSOLUTE:
        rotation='Rotate' in name;absolute=name in ABSOLUTE
        p['label']=name[0]+(' absolute section rotation' if rotation and absolute else ' rotation from previous section' if rotation else ' position in component axes' if absolute else ' offset from previous section')
        p['dimension']='angle' if rotation else 'length'
    readonly=reason(v,p['id'],found)
    if readonly:p.update(displayReadOnly=True,readOnlyReason=readonly)


def validate_parameter(v,pid,value=None):
    found=context(v,pid)
    if found is None:return
    readonly=reason(v,pid,found)
    if readonly:raise ValueError(readonly)
    if v.GetParmName(pid)=='XSAbsRelFlag' and value is not None and value not in (v.ABS,v.REL):raise ValueError('Choose a native absolute or relative section coordinate basis.')


def read_only_reasons(v):
    out={}
    for gid in v.FindGeoms():
        if v.GetGeomTypeName(gid).upper()!='STACK':continue
        for pid in v.GetGeomParmIDs(gid):
            message=reason(v,pid)
            if message:out[pid]=message
    return out


def study_metadata(v):
    out={}
    for gid in v.FindGeoms():
        if v.GetGeomTypeName(gid).upper()!='STACK':continue
        for surface in range(v.GetNumXSecSurfs(gid)):
            surf=v.GetXSecSurf(gid,surface);count=v.GetNumXSec(surf)
            for index in range(1,count):
                xid=v.GetXSec(surf,index);basis=v.GetXSecParm(xid,'XSAbsRelFlag')
                order=[dict(parameter=v.FindParm(gid,'OrderPolicy','Design'),values=[0],label='Free section ordering')] if index==count-1 else []
                for name in NAMES:
                    conditions=list(order)
                    if name in RELATIVE+ABSOLUTE:conditions.append(dict(parameter=basis,values=[v.REL if name in RELATIVE else v.ABS],label='Section coordinate basis'))
                    if conditions:out[v.GetXSecParm(xid,name)]=dict(conditions=conditions,limitControllers=[],stackPosition=True)
    return out


def study_priority(v,pid):
    if v.GetParmName(pid)=='OrderPolicy' and any(v.GetGeomTypeName(g).upper()=='STACK' and v.GetParmContainer(pid)==g for g in v.FindGeoms()):return -18
    if v.GetParmName(pid)=='XSAbsRelFlag' and context(v,pid):return -17
    return None
