"""Retain and explicitly restore native RPMs across regenerated group IDs."""
import json
import math

ATTRIBUTE='Studio.RotorSpeeds'


def linked_parameter(v):
    for c in v.FindContainers():
        if v.GetContainerName(c)=='VSPAEROSettings':
            return next(p for p in v.FindContainerParmIDs(c) if v.GetParmName(p)=='UniformPropRPMFlag')
    raise ValueError('Native rotor speed settings are unavailable.')


def groups(v):
    result=[]
    for i in range(v.GetNumUnsteadyGroups()):
        cid=v.FindUnsteadyGroup(i)
        parms={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)}
        if v.GetParmVal(parms['GeomPropertyType'])!=2:continue
        components=list(v.GetUnsteadyGroupCompIDs(i));surfaces=list(v.GetUnsteadyGroupSurfIndexes(i))
        if not components or len(components)!=len(surfaces):raise ValueError('Native rotor membership is incomplete.')
        key=sorted([[g,s] for g,s in zip(components,surfaces)])
        result.append(dict(key=key,name=v.GetUnsteadyGroupName(i),rpm=v.GetParmVal(parms['RPM']),parameter=parms['RPM']))
    if len({json.dumps(g['key']) for g in result})!=len(result):raise ValueError('Native rotor memberships are ambiguous.')
    return result


def saved(v):
    attrs=[a for a in v.FindAttributesInCollection(v.GetChildCollection(v.GetVehicleID())) if v.GetAttributeName(a)==ATTRIBUTE]
    if not attrs:return None
    try:
        if len(attrs)!=1:raise ValueError()
        values=list(v.GetAttributeStringVal(attrs[0]))
        if len(values)!=1 or len(values[0])>1000000:raise ValueError()
        data=json.loads(values[0])
        if type(data['version'])!=int or data['version']!=1 or type(data['linked'])!=int or data['linked'] not in (0,1):raise ValueError()
        records=data['groups']
        if not isinstance(records,list) or not 1<=len(records)<=1000:raise ValueError()
        for g in records:
            if not isinstance(g['name'],str) or len(g['name'])>1000:raise ValueError()
            if type(g['rpm']) not in (int,float) or not math.isfinite(g['rpm']):raise ValueError()
            if not isinstance(g['key'],list) or not g['key']:raise ValueError()
            for pair in g['key']:
                if not isinstance(pair,list) or len(pair)!=2 or not isinstance(pair[0],str) or type(pair[1])!=int or pair[1]<0:raise ValueError()
        if len({json.dumps(g['key']) for g in records})!=len(records):raise ValueError()
        if data['linked'] and len({g['rpm'] for g in records})!=1:raise ValueError()
        return data
    except (ValueError,KeyError,TypeError):raise ValueError('The saved rotor speed record is invalid. Save current rotor speeds to replace it.') from None


def assignments(v,data):
    current={json.dumps(g['key']):g for g in groups(v)}
    if set(current)!={json.dumps(g['key']) for g in data['groups']}:
        raise ValueError('Saved rotor components and surface copies do not match the current rotating groups. Restore their blade representation, aerodynamic selection and symmetry first, or save the current rotor speeds.')
    result=[]
    for g in data['groups']:
        pid=current[json.dumps(g['key'])]['parameter']
        if not v.GetParmLowerLimit(pid)<=g['rpm']<=v.GetParmUpperLimit(pid):raise ValueError('A saved RPM is outside the current native limits.')
        result.append((pid,g['rpm']))
    return result


def configuration(v):
    try:
        data=saved(v)
        if not data:return None
        try:assignments(v,data);ready=True;message='Current rotating groups match the saved components and native surface copies.'
        except ValueError as exc:ready=False;message=str(exc)
        return dict(data,restoreReady=ready,message=message)
    except ValueError as exc:return dict(restoreReady=False,message=str(exc),groups=[])


def mutate(v,operation):
    linked=linked_parameter(v)
    if operation=='rotor-speeds-save':
        records=groups(v)
        if not records:raise ValueError('Include rotating propeller blades in the aerodynamic selection before saving speeds.')
        data=dict(version=1,linked=int(v.GetParmVal(linked)),groups=[{k:g[k] for k in ('key','name','rpm')} for g in records])
        coll=v.GetChildCollection(v.GetVehicleID())
        for a in list(v.FindAttributesInCollection(coll)):
            if v.GetAttributeName(a)==ATTRIBUTE:v.DeleteAttribute(a)
        v.AddAttributeString(coll,ATTRIBUTE,json.dumps(data,allow_nan=False))
    elif operation=='rotor-speeds-restore':
        data=saved(v)
        if not data:raise ValueError('Save rotor speeds before restoring them.')
        edits=assignments(v,data)
        v.SetParmVal(linked,data['linked'])
        for pid,rpm in edits:v.SetParmVal(pid,rpm)
        v.Update()
        assignments(v,data)
        if v.GetParmVal(linked)!=data['linked'] or any(v.GetParmVal(pid)!=rpm for pid,rpm in edits):
            raise ValueError('OpenVSP did not retain the saved rotor speeds. The aircraft was not replaced.')
    else:raise ValueError('Choose a rotor speed operation.')
