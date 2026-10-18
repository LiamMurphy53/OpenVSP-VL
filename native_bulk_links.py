"""Bulk matching and link evaluation belong to the original OpenVSP engine."""
from native_tools import one,parameter_ids


def pairs(v):
    return {v.GetParmLinkID(i):(v.GetParmLinkAParm(v.GetParmLinkID(i)),v.GetParmLinkBParm(v.GetParmLinkID(i))) for i in range(v.GetNumParmLinks())}


def apply(v,r):
    allowed={p for gid in v.FindGeoms() for p in v.GetGeomParmIDs(gid)}|parameter_ids(v)
    source=one(r['source'],allowed);target=one(r['target'],allowed)
    scope=one(r['scope'],['group','component'])
    if source==target:raise ValueError('Choose different source and target parameters.')
    before=pairs(v)
    accepted=(v.LinkAllGroup if scope=='group' else v.LinkAllComp)(source,target)
    after=pairs(v);created={lid:pair for lid,pair in after.items() if lid not in before}
    if not accepted or not created:raise ValueError('OpenVSP found no new matching parameters to link. Existing links were retained.')
    targets={b for _,b in before.values()};edges={}
    for a,b in before.values():edges.setdefault(a,[]).append(b)
    for i in range(len(v.GetAdvLinkNames())):
        outputs=list(v.GetAdvLinkOutputParms(i));targets.update(outputs)
        for a in v.GetAdvLinkInputParms(i):edges.setdefault(a,[]).extend(outputs)
    for a,b in created.values():
        if b in targets:raise ValueError('A matching target already has a driver link or expression. No bulk links were saved.')
        targets.add(b);edges.setdefault(a,[]).append(b)
    for a,b in created.values():
        stack=[b];seen=set()
        while stack:
            current=stack.pop()
            if current==a:raise ValueError('These matching links would create a dependency cycle. No bulk links were saved.')
            if current not in seen:seen.add(current);stack.extend(edges.get(current,[]))
    v.Update()
