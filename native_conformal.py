"""Original native conformal source references, without geometry equations."""
import ctypes,json
import native_preview


def source(v,gid,parent=None):
    if gid not in v.FindGeoms() or v.GetGeomTypeName(gid).upper()!='CONFORMAL':raise ValueError('Choose an existing conformal component.')
    _,engine,bridge=native_preview.adapter(v);function=bridge.studio_conformal_source
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_bool];function.restype=ctypes.c_char_p
    result=json.loads(function(engine,gid.encode(),(parent or '').encode(),parent is not None))
    if 'error' in result:raise ValueError(result['error'])
    return result['source']


def depends_on(v,gid,target,seen=None):
    seen=set() if seen is None else seen
    if gid==target:return True
    if gid not in v.FindGeoms() or gid in seen:return False
    seen.add(gid);references=[v.GetGeomParent(gid)]
    if v.GetGeomTypeName(gid).upper()=='CONFORMAL':references.append(source(v,gid))
    return any(depends_on(v,ref,target,seen) for ref in references)


def metadata(v,gid):
    sid=source(v,gid);exists=sid in v.FindGeoms()
    choices=[dict(id=g,name=v.GetGeomName(g),type=v.GetGeomTypeName(g)) for g in v.FindGeoms()
             if v.GetNumMainSurfs(g)>0 and not depends_on(v,g,gid)]
    return dict(id=sid,name=v.GetGeomName(sid) if exists else 'Unavailable source',
                type=v.GetGeomTypeName(sid) if exists else None,
                detached=bool(v.GetParmVal(gid,'DetachFlag','Design')),choices=choices)


def set_source(v,gid,parent):
    data=metadata(v,gid)
    if not data['detached']:raise ValueError('Enable Detach from source component before selecting an independent source.')
    if parent not in [g['id'] for g in data['choices']]:raise ValueError('Choose a source with native surfaces that does not depend on this conformal component.')
    source(v,gid,parent);v.Update()
    if source(v,gid)!=parent:raise ValueError('OpenVSP did not retain this conformal source reference.')


def guard_geometry_delete(v,gid):
    # Follow the same subtree deletion scope as the native hierarchy operation.
    removed={g for g in v.FindGeoms() if g==gid or _descendant(v,g,gid)}
    users=[v.GetGeomName(g) for g in v.FindGeoms() if g not in removed and v.GetGeomTypeName(g).upper()=='CONFORMAL' and source(v,g) in removed]
    if users:raise ValueError('Choose another conformal source before deleting this geometry: '+', '.join(users))


def _descendant(v,gid,parent):
    seen=set()
    while gid in v.FindGeoms() and gid not in seen:
        seen.add(gid);gid=v.GetGeomParent(gid)
        if gid==parent:return True
    return False
