"""Name native Bezier handles; geometry and tangent enforcement stay in OpenVSP."""


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
