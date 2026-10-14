"""Fitting variable guidance shared with the native study driver metadata."""

import json


def key(v,pid):
    owner=v.GetParmContainer(pid)
    if owner.startswith('_') and owner in v.GetFeaMaterialIDVec():
        return '@fit:'+json.dumps([owner,v.GetParmGroupName(pid),v.GetParmName(pid)],separators=(',',':'))
    return pid


def resolve(v,value):
    if isinstance(value,str) and value.startswith('@fit:'):
        try:owner,group,name=json.loads(value[5:])
        except (ValueError,TypeError):raise ValueError('Invalid saved fitting variable reference.')
        if not all(isinstance(x,str) for x in (owner,group,name)) or not owner.startswith('_') or owner not in v.GetFeaMaterialIDVec():raise ValueError('The fitting material is no longer available.')
        value=v.FindParm(owner,name,group)
    if not isinstance(value,str) or not v.ValidParm(value):raise ValueError('A selected fitting variable is no longer available in this aircraft.')
    return value


def configuration(v,parameter):
    from native_study_worker import schema
    fields=schema(v,parameter)['parameters']
    geometry={p for g in v.FindGeoms() for p in v.GetGeomParmIDs(g)}
    users=set(v.GetAllUserParms())
    selected=set(v.GetFitModelVarVec())
    found={p['id'] for p in fields}
    # Retain valid native selections even if they are not in the normal catalog.
    for pid in selected-found:
        if v.ValidParm(pid):
            p=parameter(v,pid);p['label']=' / '.join([v.GetContainerName(v.GetParmContainer(pid)),p['group'],p.get('label',p['name'])]);fields.append(p)
    out=[]
    for p in fields:
        discrete=p['type'] not in (v.PARM_DOUBLE_TYPE,v.PARM_FRACTION_TYPE)
        reason=p.get('readOnlyReason','') if p.get('editable') is False else ''
        if p['rawGroup']=='BBox':reason='Native bounding-box values are calculated from the geometry.'
        if p['name'].endswith('_FEM'):reason='This value is calculated by the native structural model.'
        recommended=not reason and not discrete and (p['id'] in geometry or p['id'] in users) and p['rawGroup'] not in ('BBox','Mass_Props','ParasiteDragProps')
        note=reason or ('Discrete native input. The optimizer changes values continuously; review whether this input can produce a useful fit.' if discrete else 'Native engine input. Use it only when it drives the target geometry, directly or through a native parameter link.' if not recommended else '')
        out.append(dict(id=key(v,p['id']),label=p['label'],value=p['value'],min=p['min'],max=p['max'],recommended=recommended,editable=not bool(reason),discrete=discrete,note=note))
    return sorted(out,key=lambda p:(not p['recommended'],p['label'],p['id']))


def validate(v,ids):
    from native_worker import parameter
    fields={p['id']:p for p in configuration(v,parameter)}
    for pid in ids:
        if not v.ValidParm(pid):raise ValueError('A selected fitting variable is no longer available in this aircraft.')
        field=fields.get(key(v,pid))
        if field and not field['editable']:raise ValueError(field['label']+': '+field['note']+' Choose an independent native driver or change its controller setting before fitting.')
