"""Original BOR profile dimension identities and saved driver choices."""
import ctypes,json
import native_preview,native_references


def dimensions(v,gid):
    ref=native_references.references(v)[gid];cid=ref['curveID'];shape=ref['curveType'];drivers=ref['curveDrivers']
    if shape==v.XS_POINT:return dict(drivers=[],driverControls=[],driverCombinations=[],driversFixed=True)
    _,engine,bridge=native_preview.adapter(v);fn=bridge.studio_body_driver_parameters;fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_bool];fn.restype=ctypes.c_char_p
    ids=json.loads(fn(engine,cid.encode(),shape==v.XS_CIRCLE))
    if isinstance(ids,dict):raise ValueError(ids.get('error','Native profile dimensions unavailable.'))
    circle=shape==v.XS_CIRCLE;airfoil=not circle and v.GetParmName(ids[2])=='ThickChord';fixed=airfoil or any(v.GetParmName(p).endswith('_Dummy') for p in ids)
    labels=['Diameter (model units)','Profile area (model units²)'] if circle else ['Chord (model units)' if airfoil else 'Width (model units)','Profile area (model units²)','Thickness / chord' if airfoil else 'Height (model units)','Height / chord' if airfoil else 'Height / width']
    return dict(drivers=drivers,driverControls=[dict(value=i,label=label,parameter=p) for i,(label,p) in enumerate(zip(labels,ids))],driverCombinations=[drivers] if fixed else native_preview.body_driver_combinations(v,circle),driversFixed=fixed)


def enrich(v,gid,fields):
    d=dimensions(v,gid);by={p['id']:p for p in fields}
    for c in d['driverControls']:
        if c['parameter'] not in by:continue
        p=by[c['parameter']];p['label']=c['label']
        if c['value'] not in d['drivers']:p.update(displayReadOnly=True,readOnlyReason='Calculated by OpenVSP from the revolution profile dimension drivers.')
    return d


def set_drivers(v,r):
    import os
    from native_tools import one
    gid=one(r['geom'],[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='BODYOFREVOLUTION']);d=dimensions(v,gid);selected=r.get('drivers')
    if d['driversFixed']:raise ValueError('This profile has fixed native dimension drivers. Edit its active dimensions instead.')
    if not isinstance(selected,list) or any(type(x)!=int for x in selected) or sorted(selected) not in d['driverCombinations']:raise ValueError('Choose distinct profile dimension drivers supported by OpenVSP.')
    filename=v.GetVSPFileName();path,tree=native_references.document(v)
    try:
        node=next(n for n in tree.findall('.//Geom') if n.findtext('ParmContainer/ID')==gid)
        node.find('XSecCurve/XSecCurve/XSecCurveDriverGroup/ChoiceVec').text=', '.join(str(x) for x in selected)+', '
        tree.write(path,encoding='utf-8',xml_declaration=True);os.replace(path,filename)
    finally:path.unlink(missing_ok=True)
    raise native_references.ReloadRequired()
