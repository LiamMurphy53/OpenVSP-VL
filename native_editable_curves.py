"""Name native Bezier handles; geometry and tangent enforcement stay in OpenVSP."""
import re


def replace_control_points(v,xid,request):
    from native_tools import finite,one
    if v.GetXSecShape(xid)!=v.XS_EDIT_CURVE:raise ValueError('Convert this section to an editable curve first.')
    typ=getattr(v,one(request.get('type'),('LINEAR','PCHIP','CEDIT')))
    raw=request.get('rows')
    if not isinstance(raw,list) or not 2<=len(raw)<=10000:raise ValueError('Use 2–10000 control-point rows.')
    if any(not isinstance(row,list) or len(row)!=5 for row in raw):raise ValueError('Use five values per row: U X Y Z rounding.')
    rows=[[finite(value) for value in row] for row in raw]
    if rows[0][0]!=0 or rows[-1][0]!=1 or any(a[0]>=b[0] for a,b in zip(rows,rows[1:])):raise ValueError('Curve U positions must increase from 0 to 1.')
    if typ==v.CEDIT and (len(rows)<4 or (len(rows)-1)%3):raise ValueError('Cubic Bezier curves need 3n+1 rows, including their handles.')
    for column,name in [(1,'X_0'),(2,'Y_0'),(3,'Z_0'),(4,'R_0')]:
        pid=v.GetXSecParm(xid,name)
        if any(not v.GetParmLowerLimit(pid)<=row[column]<=v.GetParmUpperLimit(pid) for row in rows):raise ValueError('Control-point values exceed native coordinate or rounding limits.')
    guard_rebuild(v,[dict(id=p,name=v.GetParmName(p)) for p in v.GetXSecParmIDs(xid)])
    v.EditXSecConvertTo(xid,typ)
    v.SetEditXSecPnts(xid,[row[0] for row in rows],[v.vec3d(*row[1:4]) for row in rows],[row[4] for row in rows])
    v.Update()


def guard_rebuild(v,parameters,indices=None):
    """Native initialization recreates point IDs; protect saved references."""
    ids={p['id'] for p in parameters if re.fullmatch(r'(?:[UXYZR]|G1|FixedU)_\d+',p['name']) and (indices is None or int(p['name'].rsplit('_',1)[1]) in indices)}
    guard_parameter_replacement(v,ids)


def guard_parameter_replacement(v,ids,label='native point IDs'):
    users=[]
    for i in range(v.GetNumParmLinks()):
        link=v.GetParmLinkID(i)
        if ids & {v.GetParmLinkAParm(link),v.GetParmLinkBParm(link)}:users.append('parameter link')
    for i,link_name in enumerate(v.GetAdvLinkNames()):
        if ids & (set(v.GetAdvLinkInputParms(i))|set(v.GetAdvLinkOutputParms(i))):users.append('expression '+link_name)
    for group in v.GetVarPresetGroups():
        if ids & set(v.GetVarPresetParmIDs(group)):users.append('preset '+v.GetGroupName(group))
    if ids & {v.GetDesignVar(i) for i in range(v.GetNumDesignVars())}:users.append('design variable')
    for attr in v.FindAllAttributes():
        if v.GetAttributeType(attr)==v.PARM_REFERENCE_DATA and ids & set(v.GetAttributeParmID(attr)):users.append('parameter reference '+v.GetAttributeName(attr))
    if users:raise ValueError('This curve edit deletes or recreates '+label+' used by '+', '.join(sorted(set(users)))+'. Reassign or remove those references before editing. The edit was not saved.')


def guard_shape_replacement(v,xid,target):
    if v.GetXSecShape(xid)==target:return
    cid=v.GetParmContainer(v.GetXSecParm(xid,'Theta'))
    ids={p for p in v.GetXSecParmIDs(xid) if v.GetParmContainer(p)==cid or v.GetParmGroupName(p).startswith('XSecCurve')}
    guard_parameter_replacement(v,ids,'native profile parameter IDs')


def guard_bor_shape_replacement(v,gid,target):
    if v.GetBORXSecShape(gid)==target:return
    parameters=list(v.GetGeomParmIDs(gid))
    theta=next(p for p in parameters if v.GetParmName(p)=='Theta' and v.GetParmGroupName(p)=='XSecCurve')
    cid=v.GetParmContainer(theta)
    ids={p for p in parameters if v.GetParmContainer(p)==cid or v.GetParmGroupName(p).startswith('XSecCurve')}
    guard_parameter_replacement(v,ids,'native profile parameter IDs')


def initialization_shape(v,parameters):
    pid=next((p['id'] for p in parameters if p['name']=='ShapeType'),None)
    if not pid:return None
    value=v.GetParmVal(pid)
    return next((name for name in ('EDIT_XSEC_CIRCLE','EDIT_XSEC_ELLIPSE','EDIT_XSEC_RECTANGLE') if value==getattr(v,name)),None)


def tangent_controls(v, parameters, points):
    by_name = {p['name']: p for p in parameters}
    if int(by_name['CurveType']['value']) != v.CEDIT:
        return []
    count = len(points)
    closed = bool(by_name['CloseFlag']['value'])
    controls = []
    # A closed curve's final anchor duplicates its first anchor.
    for anchor in range(0, count - int(closed), 3):
        handles = {}
        for side, index in [('incoming', anchor - 1), ('outgoing', anchor + 1)]:
            if not 0 <= index < count:
                if not closed:
                    continue
                index = count - 2 if side == 'incoming' else 1
            handles[side] = dict(point=index, coordinates=points[index],
                                 parameters=[by_name[f'{axis}_{index}'] for axis in 'XYZ'])
        smooth = by_name[f'G1_{anchor}']
        controls.append(dict(anchor=anchor, u=by_name[f'U_{anchor}']['value'],
                             smooth=bool(smooth['value']), smoothActive=smooth['active'],
                             handles=handles))
    return controls


def move_tangent(v, xid, request):
    from native_tools import finite, one
    from native_preview import parameter_activity
    if v.GetXSecShape(xid) != v.XS_EDIT_CURVE:
        raise ValueError('Convert this section to an editable curve first.')
    if int(v.GetParmVal(v.GetXSecParm(xid, 'CurveType'))) != v.CEDIT:
        raise ValueError('Tangent drivers require a cubic Bezier curve.')
    points = v.GetEditXSecCtrlVec(xid, True)
    anchor = request.get('anchor')
    if isinstance(anchor, bool) or not isinstance(anchor, int) or anchor % 3:
        raise ValueError('Choose a cubic Bezier anchor.')
    closed = bool(v.GetParmVal(v.GetXSecParm(xid, 'CloseFlag')))
    one(anchor, range(0, len(points) - int(closed), 3), 'Choose an existing curve anchor.')
    side = one(request.get('side'), ('incoming', 'outgoing'), 'Choose the incoming or outgoing tangent.')
    index = anchor - 1 if side == 'incoming' else anchor + 1
    if not 0 <= index < len(points):
        if not closed:
            raise ValueError('This open endpoint has no ' + side + ' tangent.')
        index = len(points) - 2 if side == 'incoming' else 1
    xyz = request.get('xyz')
    if not isinstance(xyz, list) or len(xyz) != 3:
        raise ValueError('Enter three tangent handle coordinates.')
    values = [finite(x) for x in xyz]
    ids = [v.GetXSecParm(xid, f'{axis}_{index}') for axis in 'XYZ']
    activity = parameter_activity(v, ids)
    for pid, value in zip(ids, values):
        if not activity[pid] and value != v.GetParmVal(pid):
            raise ValueError('This tangent coordinate is locked by OpenVSP.')
        if not v.GetParmLowerLimit(pid) <= value <= v.GetParmUpperLimit(pid):
            raise ValueError('Use a tangent coordinate within the native limits.')
    # Selecting/moving the actual native handle establishes its driving side.
    # SetSelectPntID, MovePnt and EnforceG1 run inside the official engine.
    v.MoveEditXSecPnt(xid, index, v.vec3d(*values))


def guard_container_shape_replacement(v,cid,current,target):
    if current==target:return
    guard_parameter_replacement(v,set(v.FindContainerParmIDs(cid)),'native profile parameter IDs')


def referenced_parameters(v):
    """Capture references before a native clipboard decode can remove links."""
    refs={}
    def record(ids,label):
        for pid in ids:
            if v.ValidParm(pid):refs.setdefault(pid,set()).add(label)
    for i in range(v.GetNumParmLinks()):
        link=v.GetParmLinkID(i);record([v.GetParmLinkAParm(link),v.GetParmLinkBParm(link)],'parameter link')
    for i,name in enumerate(v.GetAdvLinkNames()):
        record(list(v.GetAdvLinkInputParms(i))+list(v.GetAdvLinkOutputParms(i)),'expression '+name)
    for group in v.GetVarPresetGroups():record(v.GetVarPresetParmIDs(group),'preset '+v.GetGroupName(group))
    record([v.GetDesignVar(i) for i in range(v.GetNumDesignVars())],'design variable')
    for attr in v.FindAllAttributes():
        if v.GetAttributeType(attr)==v.PARM_REFERENCE_DATA:record(v.GetAttributeParmID(attr),'parameter reference '+v.GetAttributeName(attr))
    return refs


def require_reference_survival(v,refs):
    missing={pid:users for pid,users in refs.items() if not v.ValidParm(pid)}
    if missing:
        users=sorted(set().union(*missing.values()))
        raise ValueError('This copy replaces native parameter IDs used by '+', '.join(users)+'. Reassign or remove those references before copying. The edit was not saved.')
