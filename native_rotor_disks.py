"""Recover native disk driver selections and inputs after object regeneration."""
import json,math,os
import native_prop_drivers as drivers
import native_references as references

ATTRIBUTE='Studio.RotorDiskSettings'


def disks(v):
    count=v.GetNumActuatorDisks()
    refs=references.references(v);result=[]
    for i in range(count):
        cid=v.FindActuatorDisk(i);r=refs.get(cid,{})
        if not r.get('rotorParent') or r.get('rotorSurface',-1)<0:raise ValueError('Native disk membership is incomplete.')
        p={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)}
        choices=r['propDrivers']
        result.append(dict(id=cid,key=[r['rotorParent'],r['rotorSurface']],choices=choices,parameters=p))
    if len({json.dumps(d['key']) for d in result})!=len(result):raise ValueError('Native disk memberships are ambiguous.')
    return result


def saved(v):
    attrs=[a for a in v.FindAttributesInCollection(v.GetChildCollection(v.GetVehicleID())) if v.GetAttributeName(a)==ATTRIBUTE]
    if not attrs:return None
    try:
        if len(attrs)!=1:raise ValueError()
        values=list(v.GetAttributeStringVal(attrs[0]))
        if len(values)!=1 or len(values[0])>1000000:raise ValueError()
        data=json.loads(values[0])
        if type(data['version'])!=int or data['version']!=1:raise ValueError()
        if not isinstance(data['disks'],list) or not 1<=len(data['disks'])<=1000:raise ValueError()
        valid=drivers.native_preview.prop_driver_combinations(v)
        for d in data['disks']:
            key=d['key'];choices=d['choices'];inputs=d['inputs']
            if not isinstance(key,list) or len(key)!=2 or not isinstance(key[0],str) or type(key[1])!=int or key[1]<0:raise ValueError()
            if not isinstance(choices,list) or len(choices)!=3 or any(type(x)!=int for x in choices) or sorted(choices) not in valid:raise ValueError()
            expected={name for enum,name,label in drivers.DRIVERS if getattr(v,enum) in choices}
            if not isinstance(inputs,dict) or set(inputs)!=expected:raise ValueError()
            if any(type(x) not in (int,float) or not math.isfinite(x) for x in inputs.values()):raise ValueError()
            if type(d['automaticHub'])!=int or d['automaticHub'] not in (0,1):raise ValueError()
            if d['automaticHub']==0 and (type(d['hub']) not in (int,float) or not math.isfinite(d['hub'])):raise ValueError()
        if len({json.dumps(d['key']) for d in data['disks']})!=len(data['disks']):raise ValueError()
        return data
    except (KeyError,TypeError,ValueError):raise ValueError('The saved disk settings are invalid. Save current disk settings to replace them.') from None


def matches(v,data):
    current={json.dumps(d['key']):d for d in disks(v)}
    if set(current)!={json.dumps(d['key']) for d in data['disks']}:
        raise ValueError('Saved disk components and native surface copies do not match. Restore their disk representation, aerodynamic selection and symmetry, or save the current settings.')
    result=[]
    for old in data['disks']:
        d=current[json.dumps(old['key'])];p=d['parameters']
        for name,x in old['inputs'].items():
            if not v.GetParmLowerLimit(p[name])<=x<=v.GetParmUpperLimit(p[name]):raise ValueError('A saved disk input is outside its current native limits.')
        if not old['automaticHub'] and not 0<=old['hub']<=v.GetParmVal(p['RotorDiameter']):
            raise ValueError('A saved manual hub exceeds the current disk diameter. Restore the propeller diameter first or save current disk settings.')
        result.append((old,d))
    return result


def configuration(v):
    try:
        data=saved(v)
        if not data:return None
        try:matches(v,data);ready=True;message='Current native disks match the saved components and surface copies.'
        except ValueError as exc:ready=False;message=str(exc)
        return dict(data,restoreReady=ready,message=message)
    except ValueError as exc:return dict(disks=[],restoreReady=False,message=str(exc))


def mutate(v,operation):
    if operation=='rotor-disks-save':
        current=disks(v)
        if not current:raise ValueError('Include actuator disks in the aerodynamic selection before saving settings.')
        records=[]
        for d in current:
            p=d['parameters'];choices=d['choices'];auto=int(v.GetParmVal(p['AutoHubDiaFlag']))
            inputs={name:v.GetParmVal(p[name]) for enum,name,label in drivers.DRIVERS if getattr(v,enum) in choices}
            records.append(dict(key=d['key'],choices=choices,inputs=inputs,automaticHub=auto,hub=None if auto else v.GetParmVal(p['RotorHubDiameter'])))
        coll=v.GetChildCollection(v.GetVehicleID())
        for a in list(v.FindAttributesInCollection(coll)):
            if v.GetAttributeName(a)==ATTRIBUTE:v.DeleteAttribute(a)
        v.AddAttributeString(coll,ATTRIBUTE,json.dumps(dict(version=1,disks=records),allow_nan=False))
        return
    data=saved(v)
    if not data:raise ValueError('Save disk settings before restoring them.')
    pairs=matches(v,data)
    if operation=='rotor-disks-restore':
        # The official API has no disk driver setter. Persist its matching
        # ChoiceVec format, then reopen before applying native driving values.
        filename=v.GetVSPFileName();path,tree=references.document(v)
        try:
            for old,d in pairs:
                nodes=[n for n in tree.findall('.//VSPAEROSettings/Rotor') if n.findtext('ParmContainer/ID')==d['id']]
                if len(nodes)!=1 or nodes[0].find('DriverGroup/ChoiceVec') is None:raise ValueError('Native disk driver record is unavailable.')
                nodes[0].find('DriverGroup/ChoiceVec').text=', '.join(map(str,old['choices']))+', '
            tree.write(path,encoding='utf-8',xml_declaration=True);os.replace(path,filename)
        finally:path.unlink(missing_ok=True)
        raise references.ReloadRequired(dict(action='mutate',operation='rotor-disks-restore-values'))
    if operation!='rotor-disks-restore-values':raise ValueError('Choose a disk recovery operation.')
    for old,d in pairs:
        if d['choices']!=old['choices']:raise ValueError('Native disk driver choices did not survive reopening.')
        p=d['parameters'];v.SetParmVal(p['AutoHubDiaFlag'],old['automaticHub'])
        if not old['automaticHub']:v.SetParmVal(p['RotorHubDiameter'],old['hub'])
        for name,x in old['inputs'].items():v.SetParmVal(p[name],x)
    v.Update()
    for old,d in matches(v,data):
        p=d['parameters']
        if v.GetParmVal(p['AutoHubDiaFlag'])!=old['automaticHub'] or any(v.GetParmVal(p[n])!=x for n,x in old['inputs'].items()):raise ValueError('OpenVSP did not retain the saved disk drivers. The aircraft was not replaced.')
        if not old['automaticHub'] and v.GetParmVal(p['RotorHubDiameter'])!=old['hub']:raise ValueError('OpenVSP did not retain the saved manual hub. The aircraft was not replaced.')
