"""Saved geometry value constraints, checked before native transaction commit."""
import json
import math

ATTRIBUTE='Studio.PropertyLocks'


def records(v):
    out=[]
    for a in v.FindAttributesInCollection(v.GetChildCollection(v.GetVehicleID())):
        if v.GetAttributeName(a)==ATTRIBUTE:
            for text in v.GetAttributeStringVal(a):
                data=json.loads(text)
                if not isinstance(data,list):raise ValueError('Invalid saved property locks.')
                for item in data:
                    if not isinstance(item,dict) or not isinstance(item.get('id'),str) or not isinstance(item.get('value'),(float,int)) or not math.isfinite(item['value']):raise ValueError('Invalid saved property lock.')
                out.extend(data)
    return out


def set_locked(v,ids,locked):
    if type(locked)!=bool or not isinstance(ids,list) or not ids or any(not isinstance(p,str) for p in ids) or len(ids)!=len(set(ids)):raise ValueError('Choose properties to lock or unlock.')
    allowed={p for g in v.FindGeoms() for p in v.GetGeomParmIDs(g)}
    if any(p not in allowed for p in ids):raise ValueError('Choose an existing geometry property.')
    existing={item['id']:item for item in records(v)}
    for pid in ids:
        if locked and pid not in existing:
            owner=v.GetParmContainer(pid)
            existing[pid]=dict(id=pid,value=v.GetParmVal(pid),label=({'TotalAR':'Aspect ratio','TotalSpan':'Full wingspan','TotalArea':'Wing area'}.get(v.GetParmName(pid),v.GetParmName(pid).replace('_',' ')))+' ('+v.GetContainerName(owner)+')')
        elif not locked:existing.pop(pid,None)
    coll=v.GetChildCollection(v.GetVehicleID())
    for a in v.FindAttributesInCollection(coll):
        if v.GetAttributeName(a)==ATTRIBUTE:v.DeleteAttribute(a)
    if existing:v.AddAttributeString(coll,ATTRIBUTE,json.dumps(list(existing.values())))


def require_unchanged(v,locked):
    for item in locked:
        pid=item['id'];label=item.get('label',pid)
        if not v.ValidParm(pid):raise ValueError('Cannot remove locked property '+label+'. Unlock it first. The edit was not saved.')
        actual=v.GetParmVal(pid)
        if not math.isfinite(actual) or not math.isclose(actual,item['value'],rel_tol=1e-10,abs_tol=1e-12):
            raise ValueError('Cannot apply this edit: '+label+' is locked at '+format(item['value'],'.12g')+'. This edit would change it to '+format(actual,'.12g')+'. Unlock that property first. The edit was not saved.')


def annotate(v,field):
    field['userLocked']=any(item['id']==field['id'] for item in records(v))
