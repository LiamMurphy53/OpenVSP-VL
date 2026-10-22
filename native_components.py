"""Component groups and native geometry-set slots; no geometry arithmetic."""
import native_managers
import math

# Native integer selectors in the model-global settings and Mode containers.
# NumUserSets is a count, not a selector. Geometry set slots keep their indices.
SET_SELECTORS={'SVGSet','Set','DegenSet','GeomSet','ThinGeomSet','ThickGeomSet',
               'MassSet','MassDegenSet','SelSetIndex','NormalSet','PrimarySet','SecondarySet'}


def integer(value,low,high):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value!=int(value) or not low<=value<=high:
        raise ValueError(f'Enter a whole number between {low} and {high}.')
    return int(value)


def count_parameter(v):
    return v.FindParm(v.GetVehicleID(),'NumUserSets','Sets')


def references(v):
    selectors={}
    for c in dict.fromkeys([*native_managers.ids(v),*v.GetAllModes(),*v.GetAllGeometryAnalysesIDVec()]):
        for p in v.FindContainerParmIDs(c):
            if v.GetParmType(p)==v.PARM_INT_TYPE and v.GetParmName(p) in SET_SELECTORS:
                selectors[p]=dict(key='parameter:'+p,id=p,value=int(v.GetParmVal(p)),
                    label=f'{v.GetContainerName(c)} · {v.GetParmDisplayGroupName(p)} · {v.GetParmName(p)}',
                    min=int(v.GetParmLowerLimit(p)),max=int(v.GetParmUpperLimit(p)))
    # Flowpath extension references are owned by geometry, not a manager.
    for g in v.FindGeoms():
        if v.GetGeomTypeName(g).upper() not in ('FUSELAGE','STACK'):continue
        p=v.FindParm(g,'AutoExtensionSet','EngineModel')
        if p:
            selectors[p]=dict(key='parameter:'+p,id=p,value=int(v.GetParmVal(p)),
                label=f'{v.GetGeomName(g)} · Flowpath extension reference set',
                min=int(v.GetParmLowerLimit(p)),max=int(v.GetParmUpperLimit(p)))
    refs=list(selectors.values())
    for g in v.GetVarPresetGroups():
        pids=list(v.GetVarPresetParmIDs(g))
        for s in v.GetVarPresetSettings(g):
            for p,x in zip(pids,v.GetVarPresetParmVals(s)):
                if p in selectors:
                    refs.append(dict(selectors[p],key=f'preset:{g}:{s}:{p}',group=g,setting=s,value=x,
                        label=f'Preset {v.GetGroupName(g)} / {v.GetSettingName(s)} · {selectors[p]["label"]}'))
    return refs


def snapshot(v):
    p=count_parameter(v)
    sets=[]
    for i in range(v.GetNumSets()):
        members=list(v.GetGeomSetAtIndex(i));box=v.GetBBoxSet(i) if members else [False]
        sets.append(dict(index=i,name=v.GetSetName(i),members=members,
                         bounds=dict(min=list(box[1:4]),size=list(box[4:7])) if box[0] else None))
    return dict(sets=sets,setConfig=dict(parameter=p,count=int(v.GetParmVal(p)),
                min=int(v.GetParmLowerLimit(p)),max=int(v.GetParmUpperLimit(p)),references=references(v)))


def resize(v,count,replacements=None):
    p=count_parameter(v);count=integer(count,int(v.GetParmLowerLimit(p)),int(v.GetParmUpperLimit(p)))
    total=count+v.SET_FIRST_USER
    shrinking=total<v.GetNumSets()
    affected={r['key']:r for r in references(v) if shrinking and total<=r['value']}
    replacements={} if replacements is None else replacements
    if not isinstance(replacements,dict) or any(k not in affected for k in replacements):
        raise ValueError('Only references to the removed sets can be reassigned.')
    missing=set(affected)-set(replacements)
    if missing:
        labels='; '.join(affected[k]['label'] for k in sorted(missing))
        raise ValueError('Choose replacement sets before reducing the count: '+labels)
    values={k:integer(x,max(-1,r['min']),min(total-1,r['max'])) for k,r in affected.items() for x in [replacements[k]]}
    for k,r in affected.items():
        if 'group' in r:v.SetVarPresetParmVal(r['group'],r['setting'],r['id'],values[k])
        else:v.SetParmValUpdate(r['id'],values[k])
    v.SetParmValUpdate(p,count);v.Update()
    if int(v.GetParmVal(p))!=count:raise ValueError('OpenVSP did not apply the requested set count.')
    # Dependencies may update a selector again. Fail the isolated transaction
    # instead of committing a model with a reference to a removed slot.
    if shrinking and any(total<=r['value'] for r in references(v)):
        raise ValueError('A native dependency still refers to a removed set. Update that dependency first.')


def reorder(v,order):
    """Move user-set contents and references; native slot indices stay fixed."""
    import copy,os
    import native_references,native_property_locks
    slots=list(range(v.SET_FIRST_USER,v.GetNumSets()))
    if not isinstance(order,list) or any(type(i)!=int for i in order) or len(order)!=len(slots) or set(order)!=set(slots):raise ValueError('Provide each user-set index exactly once; built-in sets cannot move.')
    if order==slots:return
    mapping={old:new for new,old in zip(slots,order)}
    original={i:dict(name=v.GetSetName(i),members=set(v.GetGeomSetAtIndex(i))) for i in slots}
    refs=references(v);locks=native_property_locks.records(v)
    path,tree=native_references.document(v)
    try:attrs=copy.deepcopy(tree.find('.//SetAttrs'))
    finally:path.unlink(missing_ok=True)
    for destination,source in zip(slots,order):
        v.SetSetName(destination,original[source]['name'])
        for geom in v.FindGeoms():v.SetSetFlag(geom,destination,geom in original[source]['members'])
    for ref in refs:
        value=mapping.get(ref['value'],ref['value'])
        if value==ref['value']:continue
        if not ref['min']<=value<=ref['max']:raise ValueError('A saved set reference cannot follow the requested order: '+ref['label'])
        if 'group' in ref:v.SetVarPresetParmVal(ref['group'],ref['setting'],ref['id'],value)
        else:v.SetParmValUpdate(ref['id'],value)
    v.Update()
    expected={ref['key']:mapping.get(ref['value'],ref['value']) for ref in refs}
    if any(expected.get(ref['key'])!=ref['value'] for ref in references(v)):raise ValueError('A native dependency prevents moving these set references. The edit was not saved.')
    for destination,source in zip(slots,order):
        if v.GetSetName(destination)!=original[source]['name'] or set(v.GetGeomSetAtIndex(destination))!=original[source]['members']:raise ValueError('OpenVSP could not retain the requested set contents.')
    native_property_locks.require_unchanged(v,locks)
    filename=v.GetVSPFileName();path,tree=native_references.document(v)
    try:
        existing=tree.find('.//SetAttrs')
        if attrs is not None:
            parent=next(node for node in tree.iter() if existing in list(node))
            parent.remove(existing)
            for node in attrs.findall('Set'):
                old=int(node.get('SetIndex'))+v.SET_FIRST_USER
                node.set('SetIndex',str(mapping[old]-v.SET_FIRST_USER))
                node.set('SetName',original[old]['name'])
            parent.append(attrs)
        tree.write(path,encoding='utf-8',xml_declaration=True);os.replace(path,filename)
    finally:path.unlink(missing_ok=True)
    raise native_references.ReloadRequired(dict(action='state',validatePropertyLocks=True))


def mutate(v,r):
    from native_tools import name,finite,one
    op=r['operation']
    if op=='set-reorder':reorder(v,r['order'])
    elif op=='set-count':resize(v,r['count'],r.get('replacements'))
    elif op=='set-create':
        label=name(r['name']);p=count_parameter(v);count=int(v.GetParmVal(p))
        if count>=v.GetParmUpperLimit(p):raise ValueError('The native geometry set limit has been reached.')
        source=r.get('source')
        if source is not None:source=integer(source,0,v.GetNumSets()-1)
        index=v.GetNumSets();resize(v,count+1);v.SetSetName(index,label)
        if source is not None:copy_membership(v,source,index)
    elif op in ('set-name','set-member','set-copy'):
        index=integer(r['index'],v.SET_FIRST_USER,v.GetNumSets()-1)
        if op=='set-name':v.SetSetName(index,name(r['name']))
        elif op=='set-copy':copy_membership(v,integer(r['source'],0,v.GetNumSets()-1),index)
        else:
            one(r['geom'],v.FindGeoms())
            if not isinstance(r['member'],bool):raise ValueError('Choose whether the component belongs to the set.')
            v.SetSetFlag(r['geom'],index,r['member'])
    elif op=='group-transform':
        index=integer(r['set'],0,v.GetNumSets()-1)
        if not v.GetGeomSetAtIndex(index):raise ValueError('Choose a set containing components.')
        typ=one(r['type'],['translate','rotate','scale','combined'])
        def xyz(key):
            values=r[key]
            if not isinstance(values,list) or len(values)!=3:raise ValueError('Enter X, Y and Z values.')
            return [finite(x) for x in values]
        if typ in ('scale','combined'):
            scale=finite(r['value'])
            if scale<=0:raise ValueError('Use a positive scale factor.')
        if typ=='translate':v.TranslateSet(index,v.vec3d(*xyz('xyz')))
        elif typ=='rotate':v.RotateSet(index,*xyz('xyz'))
        elif typ=='scale':v.ScaleSet(index,scale)
        else:
            flag=r.get('scaleTranslations')
            if not isinstance(flag,bool):raise ValueError('Choose whether to scale component positions.')
            translation=xyz('xyz');rotation=xyz('rotation')
            v.TransformSet(index,v.vec3d(*translation),*rotation,scale,flag)
    else:return False,None
    return True,r.get('geom')


def copy_membership(v,source,destination):
    # CopyPasteSet intentionally ignores the three built-in sets. Materialize
    # their engine-reported membership with the official per-geometry setter.
    members=set(v.GetGeomSetAtIndex(source))
    if source>=v.SET_FIRST_USER:v.CopyPasteSet(source,destination)
    else:
        for g in v.FindGeoms():v.SetSetFlag(g,destination,g in members)
    if set(v.GetGeomSetAtIndex(destination))!=members:
        raise ValueError('OpenVSP did not apply the requested set membership.')
