"""Undoable case result actions using the installed engine's own evaluation."""
import ctypes,json,math
from native_tools import one
import native_geometry_cases as cases
import native_references


ROTATION_TYPES=('PLANE_2PT_ANGLE_INTERFERENCE','PLANE_1PT_ANGLE_INTERFERENCE','RISK_ANGLE')


def call(v,cid,action):
    from native_preview import adapter
    _,engine,bridge=adapter(v);fn=bridge.studio_geometry_case_action
    fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];fn.restype=ctypes.c_char_p
    result=json.loads(fn(engine,cid.encode(),action))
    if result.get('error'):raise ValueError(result['error'])
    return result['id']


def evaluate(v,cid):
    cases.require_observation_component(v,cid)
    cases.update(v)
    rid=call(v,cid,0)
    if not rid or not v.GetResultsName(rid):raise ValueError('OpenVSP did not produce a result for this case. Review its geometry selections and required auxiliary setup.')
    return rid


def mutate(v,r):
    cid=one(r['id'],v.GetAllGeometryAnalysesIDVec(),'This saved geometry case no longer exists.')
    typ=int(v.GetParmVal(v.FindParm(cid,'IntererenceCheckType','InterferenceCase')))
    if r['operation']=='geometry-case-result-mesh':
        evaluate(v,cid)
        from native_case_drawings import capture
        drawing=capture(v,cid)
        if not any(o['kind']=='triangles' and o['points'] for o in drawing['nativeObjects']):
            raise ValueError('This native calculation returned no result mesh. Inspect its result lines or points in Analyze instead.')
        gid=call(v,cid,1)
        if gid not in v.FindGeoms() or v.GetGeomTypeName(gid).upper()!='MESH':raise ValueError('OpenVSP did not create the result mesh.')
        v.SetGeomName(gid,v.GetContainerName(cid)+' · result mesh')
        return True,gid
    if r['operation']!='geometry-case-apply-rotation':raise ValueError('Unknown saved-case result action.')
    if typ not in [getattr(v,n) for n in ROTATION_TYPES]:raise ValueError('Apply rotation is available for one-point contact, two-point contact and debris risk-angle cases.')
    refs=native_references.references(v);gid=refs.get(cid,{}).get('SecondaryGeomID','')
    if gid not in v.FindGeoms() or v.GetGeomTypeName(gid).upper()!='AUXILIARY':raise ValueError('Choose the matching auxiliary as the secondary component before applying a calculated rotation.')
    rid=evaluate(v,cid)
    # Same result-to-control mapping used by GeometryAnalysisScreen's action.
    pairs=[('TipBogie','BogieTheta'),('TipWheel','WheelTheta')] if typ==v.PLANE_2PT_ANGLE_INTERFERENCE else [('RollAngle','RollTheta')] if typ==v.PLANE_1PT_ANGLE_INTERFERENCE else [('EntryExit','ReleaseAngle')]
    changes=[]
    for result_name,parameter_name in pairs:
        values=list(v.GetDoubleResults(rid,result_name,0))
        if not values or (result_name=='EntryExit' and len(values)!=2):raise ValueError('OpenVSP did not return the contact rotation required by this action.')
        pid=v.FindParm(gid,parameter_name,'Design')
        if not pid or not v.ValidParm(pid):raise ValueError('The selected auxiliary has no matching rotation control.')
        value=values[1] if result_name=='EntryExit' and v.GetParmVal(pid)==values[0] else values[0]
        if not math.isfinite(value):raise ValueError('OpenVSP returned an undefined rotation for this case.')
        changes.append((pid,value))
    for pid,value in changes:v.SetParmValUpdate(pid,value)
    return True,gid
