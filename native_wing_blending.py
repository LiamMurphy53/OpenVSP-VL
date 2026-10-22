"""Wing blending presentation and eligibility from original BlendScreen::Update.

Geometry, angle matching and tangent evaluation remain in the installed engine.
"""
EDGES=(('InLE','Inboard leading edge'),('OutLE','Outboard leading edge'),
       ('InTE','Inboard trailing edge'),('OutTE','Outboard trailing edge'))
MODES=(('BLEND_FREE','Automatic'),('BLEND_ANGLES','Set sweep and dihedral'),
       ('BLEND_MATCH_IN_LE_TRAP','Match inboard leading-edge trapezoid'),
       ('BLEND_MATCH_IN_TE_TRAP','Match inboard trailing-edge trapezoid'),
       ('BLEND_MATCH_OUT_LE_TRAP','Match outboard leading-edge trapezoid'),
       ('BLEND_MATCH_OUT_TE_TRAP','Match outboard trailing-edge trapezoid'),
       ('BLEND_MATCH_IN_ANGLES','Match inboard angles'),
       ('BLEND_MATCH_LE_ANGLES','Match leading-edge angles'))
NAMES={edge+suffix for edge,_ in EDGES for suffix in ('Mode','Sweep','Dihedral','Strength')}


def context(v,pid):
    if v.GetParmGroupName(pid)!='XSec' or v.GetParmName(pid) not in NAMES:return None
    container=v.GetParmContainer(pid)
    for gid in v.FindGeoms():
        if v.GetGeomTypeName(gid).upper()!='WING':continue
        surf=v.GetXSecSurf(gid,0);count=v.GetNumXSec(surf)
        for index in range(count):
            xid=v.GetXSec(surf,index)
            if xid==container:
                values={edge:int(v.GetParmVal(v.GetXSecParm(xid,edge+'Mode'))) for edge,_ in EDGES}
                return index,count,values
    return None


def policy(v,name,index,count,values):
    edge=next(e for e,_ in EDGES if name.startswith(e));suffix=name[len(edge):]
    first=index==0;last=index==count-1
    endpoint=(first and edge.startswith('In')) or (last and edge.startswith('Out'))
    allowed={getattr(v,enum) for enum,_ in MODES}
    if edge=='InLE':allowed-={v.BLEND_MATCH_IN_ANGLES,v.BLEND_MATCH_LE_ANGLES}
    if edge=='InTE':allowed.discard(v.BLEND_MATCH_IN_ANGLES)
    if edge=='OutLE':allowed.discard(v.BLEND_MATCH_LE_ANGLES)
    if first:allowed-={v.BLEND_MATCH_IN_LE_TRAP,v.BLEND_MATCH_IN_TE_TRAP}
    if last:allowed-={v.BLEND_MATCH_OUT_LE_TRAP,v.BLEND_MATCH_OUT_TE_TRAP}
    if values['InLE']!=v.BLEND_ANGLES:
        if edge=='InTE':allowed.discard(v.BLEND_MATCH_LE_ANGLES)
        if edge=='OutLE':allowed.discard(v.BLEND_MATCH_IN_ANGLES)
    if edge=='OutTE':
        if values['InTE'] not in (v.BLEND_ANGLES,v.BLEND_MATCH_LE_ANGLES):allowed.discard(v.BLEND_MATCH_IN_ANGLES)
        if values['OutLE'] not in (v.BLEND_ANGLES,v.BLEND_MATCH_IN_ANGLES):allowed.discard(v.BLEND_MATCH_LE_ANGLES)
    reason=None
    if endpoint:reason='This profile has no '+('inboard' if first else 'outboard')+' neighbor.'
    elif suffix!='Mode':
        if values[edge]==v.BLEND_FREE:reason='Calculated by OpenVSP in Automatic mode. Choose a blend constraint to edit it.'
        elif suffix!='Strength' and values[edge]!=v.BLEND_ANGLES:reason='Angles follow the selected native matching constraint.'
    return allowed,reason


def annotate(v,p):
    found=context(v,p['id']) if p['name'] in NAMES and p['rawGroup']=='XSec' else None
    if found is None:return
    edge,label=next((e,label) for e,label in EDGES if p['name'].startswith(e))
    suffix=p['name'][len(edge):];allowed,reason=policy(v,p['name'],*found)
    p['label']=label+' '+{'Mode':'blend','Sweep':'sweep','Dihedral':'dihedral','Strength':'strength'}[suffix]
    p['description']='Native wing tangent constraint at this airfoil profile. Matching uses OpenVSP’s neighboring trapezoid or angle values.'
    if suffix=='Mode':
        p['choices']=[[getattr(v,enum),label] for enum,label in MODES if getattr(v,enum) in allowed]
        if p['value'] not in allowed:p['choices'].append([p['value'],'Saved native setting (currently unavailable)'])
    else:
        p['customSlider']=dict(key='wing-blend:'+p['id'],range={'Sweep':90,'Dihedral':20,'Strength':1}[suffix],adjustable=True)
        if suffix in ('Sweep','Dihedral'):p['dimension']='angle'
    if reason:p.update(displayReadOnly=True,readOnlyReason=reason)


def validate_parameter(v,pid,value=None):
    found=context(v,pid)
    if found is None:return
    name=v.GetParmName(pid);allowed,reason=policy(v,name,*found)
    if reason:raise ValueError(reason)
    if name.endswith('Mode') and value is not None and value not in allowed:
        raise ValueError('Choose an available wing blend mode for this profile and its current angle constraints.')


def read_only_reasons(v):
    result={}
    for gid in v.FindGeoms():
        if v.GetGeomTypeName(gid).upper()!='WING':continue
        for pid in v.GetGeomParmIDs(gid):
            found=context(v,pid)
            if found:
                _,reason=policy(v,v.GetParmName(pid),*found)
                if reason:result[pid]=reason
    return result


def study_metadata(v):
    out={}
    for gid in v.FindGeoms():
        if v.GetGeomTypeName(gid).upper()!='WING':continue
        surf=v.GetXSecSurf(gid,0);count=v.GetNumXSec(surf)
        for index in range(count):
            xid=v.GetXSec(surf,index)
            for edge,label in EDGES:
                if (index==0 and edge.startswith('In')) or (index==count-1 and edge.startswith('Out')):continue
                mode=v.GetXSecParm(xid,edge+'Mode')
                for suffix in ('Sweep','Dihedral','Strength'):
                    allowed=[v.BLEND_ANGLES] if suffix!='Strength' else [getattr(v,e) for e,_ in MODES if e!='BLEND_FREE']
                    out[v.GetXSecParm(xid,edge+suffix)]=dict(conditions=[dict(parameter=mode,values=allowed,label=label+' blend')],limitControllers=[],wingBlend=True)
    return out


def study_choices(v,pid):
    found=context(v,pid)
    if found is None or not v.GetParmName(pid).endswith('Mode'):return None
    index,count,_=found
    # Cross-axis controller values can activate matching modes. Expose original
    # structurally valid choices, then validate each case after ordered modes.
    allowed,_=policy(v,v.GetParmName(pid),index,count,{edge:v.BLEND_ANGLES for edge,_ in EDGES})
    return [dict(value=getattr(v,enum),label=label) for enum,label in MODES if getattr(v,enum) in allowed]


def study_priority(v,pid):
    if v.GetParmName(pid) not in NAMES:return None
    if context(v,pid) is None:return None
    name=v.GetParmName(pid)
    return {'InLEMode':-14,'InTEMode':-13,'OutLEMode':-12,'OutTEMode':-11}.get(name)
