"""Body section dimensions and positions using native identities and drivers."""
import native_preview


def point_outputs(v,xid):
    if v.GetXSecShape(xid)!=v.XS_POINT:return []
    return [pid for pid in v.GetXSecParmIDs(xid) if v.GetParmGroupName(pid)=='XSecCurve' and v.GetParmName(pid) in ('Area','HWRatio')]


def sections(v,gid):
    if v.GetGeomTypeName(gid).upper() not in ('FUSELAGE','STACK'):return
    for surface in range(v.GetNumXSecSurfs(gid)):
        surf=v.GetXSecSurf(gid,surface)
        for index in range(v.GetNumXSec(surf)):
            yield surface,index,v.GetXSec(surf,index)


def enrich(v,gid,params,entries):
    by_id={p['id']:p for p in params};kind=v.GetGeomTypeName(gid).upper()
    for section in entries:
        xid=section['id'];ids=native_preview.body_driver_parameters(v,gid,section['surface'],section['index'])
        import native_skinning_controls
        count=v.GetNumXSec(v.GetXSecSurf(gid,section['surface']))
        section['skinControls']=native_skinning_controls.enrich_section(v,xid,section['index'],count,params)
        for pid in point_outputs(v,xid):
            by_id[pid].update(displayReadOnly=True,readOnlyReason='Point profile dimensions are fixed by OpenVSP.')
        if ids:
            circle=section['shape']==v.XS_CIRCLE
            labels=['Diameter','Section area'] if circle else ['Width','Section area','Height','Height / width']
            choices=list(v.GetDriverGroup(gid,section['index']))
            airfoil=not circle and by_id[ids[2]]['name']=='ThickChord'
            if airfoil:labels=['Chord','Section area','Thickness / chord','Height / chord']
            section['bodyDrivers']=choices
            section['bodyDriversFixed']=airfoil
            section['bodyDriverCombinations']=[choices] if airfoil else native_preview.body_driver_combinations(v,circle)
            section['bodyDriverControls']=[dict(value=i,label=labels[i],parameter=pid) for i,pid in enumerate(ids)]
            for i,pid in enumerate(ids):
                p=by_id[pid];p['displayReadOnly']=i not in choices
                if i==0 or (i==2 and not airfoil):p['dimension']='length'
                elif i==1:p['dimension']='area'
                if p['displayReadOnly']:p['readOnlyReason']='Calculated by OpenVSP from the selected section dimension drivers.'
        names=['XLocPercent','YLocPercent','ZLocPercent'] if kind=='FUSELAGE' else ['XDelta','YDelta','ZDelta']
        labels=[axis+' position (body length fraction)' for axis in 'XYZ'] if kind=='FUSELAGE' else [axis+' offset from previous section' for axis in 'XYZ']
        names+=['XRotate','YRotate','ZRotate'];labels+=[axis+' section rotation' for axis in 'XYZ']
        if kind=='STACK':
            relative=v.GetParmVal(v.GetXSecParm(xid,'XSAbsRelFlag'))==v.REL
            names=['XSAbsRelFlag']+names if relative else ['XSAbsRelFlag','XAbs','YAbs','ZAbs','XRotateAbs','YRotateAbs','ZRotateAbs']
            labels=['Coordinate basis']+[axis+' offset from previous section' for axis in 'XYZ']+[axis+' rotation from previous section' for axis in 'XYZ'] if relative else ['Coordinate basis']+[axis+' position in component axes' for axis in 'XYZ']+[axis+' absolute section rotation' for axis in 'XYZ']
        pids=list(v.GetXSecParmIDs(xid))
        section['bodyPositionControls']=[dict(parameter=pid,label=label) for name,label in zip(names,labels) for pid in pids if v.GetParmName(pid)==name and v.GetParmGroupName(pid)=='XSec']
        for item in section['bodyPositionControls']:
            p=by_id[item['parameter']]
            if p['name'].endswith('Rotate'):p['dimension']='angle'
            elif p['name'].endswith('RotateAbs'):p['dimension']='angle'
            elif kind=='STACK' and p['name']!='XSAbsRelFlag':p['dimension']='length'


def read_only_reasons(v):
    import native_stack_positions
    result=native_stack_positions.read_only_reasons(v)
    for gid in v.FindGeoms():
        for surface,index,xid in sections(v,gid):
            for pid in point_outputs(v,xid):result[pid]='Point profile dimensions are fixed by OpenVSP.'
            ids=native_preview.body_driver_parameters(v,gid,surface,index)
            choices=list(v.GetDriverGroup(gid,index)) if ids else []
            for i,pid in enumerate(ids):
                if i not in choices:result[pid]='Calculated by OpenVSP from the saved section dimension drivers.'
    return result


def validate_parameter(v,pid,value=None):
    import native_stack_positions
    native_stack_positions.validate_parameter(v,pid,value)
    owner=next((g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper() in ('FUSELAGE','STACK') and pid in v.GetGeomParmIDs(g)),None)
    if not owner:return
    for surface,index,xid in sections(v,owner):
        if pid in point_outputs(v,xid):raise ValueError('Point profile dimensions are fixed by OpenVSP. Choose a non-point profile to edit its dimensions.')
        ids=native_preview.body_driver_parameters(v,owner,surface,index)
        if pid in ids and ids.index(pid) not in v.GetDriverGroup(owner,index):
            raise ValueError('OpenVSP calculates this section dimension. Select it as a section dimension driver before editing it.')


def validate_drivers(v,gid,surface,index,choices):
    if surface!=0:raise ValueError('Native section driver changes support surface 0.')
    ids=native_preview.body_driver_parameters(v,gid,surface,index)
    if not ids:raise ValueError('Point sections have no independent width or height.')
    count=1 if len(ids)==2 else 2
    combinations=native_preview.body_driver_combinations(v,len(ids)==2)
    if len(ids)==4 and v.GetParmName(ids[2])=='ThickChord':
        combinations=[list(v.GetDriverGroup(gid,index))]
        if choices not in combinations:raise ValueError('OpenVSP fixes airfoil drivers to chord and thickness / chord. Edit those dimensions instead.')
    if not isinstance(choices,list) or len(choices)!=count or any(type(x)!=int for x in choices) or sorted(choices) not in combinations:
        raise ValueError('Choose distinct section dimension drivers supported by OpenVSP.')
