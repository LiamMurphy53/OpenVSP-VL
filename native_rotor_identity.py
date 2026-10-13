"""Exact native rotor membership for explicit saved-study field recovery."""
import native_references


def fields(v):
    result={}
    v.GetNumActuatorDisks();v.GetNumUnsteadyGroups()
    refs=native_references.references(v)
    for i in range(v.GetNumActuatorDisks()):
        cid=v.FindActuatorDisk(i);r=refs.get(cid,{})
        if not r.get('rotorParent') or r.get('rotorSurface',-1)<0:continue
        for p in v.FindContainerParmIDs(cid):
            result[p]=dict(kind='disk',members=[[r['rotorParent'],r['rotorSurface']]],field=v.GetParmName(p))
    for i in range(v.GetNumUnsteadyGroups()):
        cid=v.FindUnsteadyGroup(i);params={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)}
        if 'GeomPropertyType' not in params or v.GetParmVal(params['GeomPropertyType'])!=2:continue
        members=sorted([list(x) for x in zip(v.GetUnsteadyGroupCompIDs(i),v.GetUnsteadyGroupSurfIndexes(i))])
        if not members:continue
        for name,p in params.items():result[p]=dict(kind='rotating',members=members,field=name)
    return result
