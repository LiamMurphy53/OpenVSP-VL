"""Native surface-region driver guidance; all boundary math stays in OpenVSP."""
LABELS={'Test_Type':'Region to tag','Const_Line_Type':'Constant coordinate','ConstLineType':'Constant coordinate','Value_01':'Line coordinate basis','Const_Line_Value':'Normalized line coordinate (0–1)','Const_Line_Value0N':'Native surface coordinate (0–N)','PositiveDirectionFlag':'Line array direction','Spacing':'Line spacing fraction','StartLocation':'First line fraction','EndLocation':'Last line limit fraction','Center_U':'Center U (0–1)','Center_W':'Center W (0–1)','U_Length':'Length in U','W_Length':'Length in W','Theta':'Rotation (degrees)','Tess_Num':'Boundary tessellation','UStart':'Start surface U (0–1)','UEnd':'End surface U (0–1)','WStart':'Start surface W (0–1)','WEnd':'End surface W (0–1)','EtaFlag':'Span coordinate basis','EtaStart':'Start span fraction (eta)','EtaEnd':'End span fraction (eta)','Abs_Rel_Flag':'Chord distance units','Length_C_Start':'Start chord fraction','Length_C_End':'End chord fraction','Length_Start':'Start chord distance (model units)','Length_End':'End chord distance (model units)','SE_Const_Flag':'Match start and end chord setting','LE_Flag':'Boundary edge','Surf_Type':'Surface side','StartAngleFlag':'Specify start angle','EndAngleFlag':'Specify end angle','SameAngleFlag':'Match start and end angles','StartAngle':'Start angle (degrees)','EndAngle':'End angle (degrees)'}


def supported(group):return group=='SubSurface' or group.startswith('SS_')


def reason(v,pid):
    group=v.GetParmGroupName(pid);name=v.GetParmName(pid)
    if not supported(group):return ''
    owner=v.GetParmContainer(pid);get=lambda n,g=group:v.GetParmVal(v.FindParm(owner,n,g))
    if group=='SubSurface' and name in ('Const_Line_Value','Const_Line_Value0N'):
        follower='Const_Line_Value0N' if get('Value_01') else 'Const_Line_Value'
        if name==follower:return 'OpenVSP calculates this linked surface coordinate from the chosen line basis.'
    if group=='SS_Control':
        if name in ('EtaStart','EtaEnd','UStart','UEnd'):
            if name.startswith('U')==bool(get('EtaFlag')):return 'OpenVSP calculates this linked span coordinate from the chosen span basis.'
        if name in ('Length_C_Start','Length_C_End','Length_Start','Length_End'):
            if name.endswith('End') and get('SE_Const_Flag'):return 'OpenVSP links the end chord setting to the start setting.'
            if name.startswith('Length_C_')!=(get('Abs_Rel_Flag')==v.REL):return 'OpenVSP calculates this linked chord distance from the chosen distance units.'
        if name=='StartAngle' and not get('StartAngleFlag'):return 'OpenVSP calculates the start angle unless Specify start angle is enabled.'
        if name=='EndAngle':
            if not get('EndAngleFlag'):return 'OpenVSP calculates the end angle unless Specify end angle is enabled.'
            if get('SameAngleFlag') and get('StartAngleFlag'):return 'OpenVSP links the end angle to the specified start angle.'
    return ''


def annotate(v,p):
    group=p['rawGroup'];name=p['name']
    if not supported(group):return
    if name in LABELS:p['label']=LABELS[name]
    if name=='MainSurfIndx':
        owner=v.GetParmContainer(p['id'])
        parent=next((g for g in v.FindGeoms() if owner in v.GetSubSurfIDVec(g)),None)
        if parent is None:
            parent=next((v.GetFeaStructParentGeomID(s) for s in v.GetFeaStructIDVec() if owner in v.GetFeaSubSurfIDVec(s)),None)
        if parent:
            p.update(label='Parent surface',choices=[dict(value=-1,label='All main surfaces')]+[dict(value=i,label='Surface '+str(i)) for i in range(v.GetNumMainSurfs(parent))])
    elif name=='Test_Type':
        # SSLineSeg::GT/LT/NO are 0/1/2 in the matching official header.
        pairs=[(0,'Greater than line coordinate'),(1,'Less than line coordinate'),(2,'No surface tagging')] if group=='SubSurface' else [(v.INSIDE,'Inside boundary'),(v.OUTSIDE,'Outside boundary'),(v.NONE,'No surface tagging')]
        p['choices']=[dict(value=value,label=label) for value,label in pairs if p['min']<=value<=p['max']]
    elif name in ('Const_Line_Type','ConstLineType'):p['choices']=[dict(value=v.CONST_U,label='Constant U'),dict(value=v.CONST_W,label='Constant W')]
    elif name=='Value_01':p['choices']=[dict(value=1,label='Normalized · 0–1'),dict(value=0,label='Native surface · 0–N')]
    elif name=='PositiveDirectionFlag':p['choices']=[dict(value=1,label='Increasing coordinate'),dict(value=0,label='Decreasing coordinate')]
    elif name=='EtaFlag':p['choices']=[dict(value=1,label='Span fraction · eta'),dict(value=0,label='Surface coordinate · U')]
    elif name=='Abs_Rel_Flag':p['choices']=[dict(value=v.REL,label='Chord fraction'),dict(value=v.ABS,label='Absolute · model units')]
    elif name=='LE_Flag':p['choices']=[dict(value=0,label='Trailing edge'),dict(value=1,label='Leading edge')]
    elif name=='Surf_Type':p['choices']=[dict(value=0,label='Upper surface'),dict(value=1,label='Lower surface'),dict(value=2,label='Both surfaces')]
    why=reason(v,p['id'])
    if why:p.update(active=False,editable=False,readOnly=True,readOnlyReason=why)


def validate_parameter(v,pid):
    why=reason(v,pid)
    if why:raise ValueError(why)


def refresh(v,pid):
    if not supported(v.GetParmGroupName(pid)):return
    owner=v.GetParmContainer(pid)
    structure=next((s for s in v.GetFeaStructIDVec() if owner in v.GetFeaSubSurfIDVec(s)),None)
    if structure:
        import native_part_controls
        native_part_controls.refresh(v,structure)


def guide(v,owner,typ):
    fields={v.GetParmName(p):p for p in v.FindContainerParmIDs(owner)}
    val=lambda n:v.GetParmVal(fields[n])
    names=['MainSurfIndx','Test_Type']
    if typ==v.SS_LINE:names+=['Const_Line_Type','Value_01','Const_Line_Value' if val('Value_01') else 'Const_Line_Value0N']
    elif typ in (v.SS_RECTANGLE,v.SS_ELLIPSE):names+=['Center_U','Center_W','U_Length','W_Length','Theta']
    elif typ==v.SS_LINE_ARRAY:names+=['ConstLineType','PositiveDirectionFlag','StartLocation','EndLocation','Spacing']
    elif typ==v.SS_FINITE_LINE:names+=['UStart','WStart','UEnd','WEnd']
    elif typ==v.SS_CONTROL:
        names+=['EtaFlag','EtaStart' if val('EtaFlag') else 'UStart','EtaEnd' if val('EtaFlag') else 'UEnd','LE_Flag','Surf_Type','Abs_Rel_Flag','SE_Const_Flag']
        names+=['Length_C_Start' if val('Abs_Rel_Flag')==v.REL else 'Length_Start']
        if not val('SE_Const_Flag'):names+=['Length_C_End' if val('Abs_Rel_Flag')==v.REL else 'Length_End']
        names+=['StartAngleFlag','EndAngleFlag','SameAngleFlag']
        for n in ('StartAngle','EndAngle'):
            if not reason(v,fields[n]):names+=[n]
    elif typ in (v.SS_XSEC_CURVE,v.SS_INTERSECT):names+=['Center_U','Center_W','NCurves','ICurve']
    return dict(primary=[fields[n] for n in names if n in fields],note='U and W are native surface parameters. Normalized values and span/chord fractions are dimensionless; native 0–N surface coordinates are not physical lengths. OpenVSP evaluates linked coordinates and boundaries.')


def study_metadata(v):
    owners=list(v.GetAllSubSurfIDs())+[r for s in v.GetFeaStructIDVec() for r in v.GetFeaSubSurfIDVec(s)];out={}
    for owner in owners:
        fields={v.GetParmName(p):p for p in v.FindContainerParmIDs(owner)}
        cond=lambda n,values:dict(parameter=fields[n],values=values,label=LABELS.get(n,n))
        def add(n,conditions):
            if n in fields:out[fields[n]]=dict(conditions=conditions,limitControllers=[])
        if 'Value_01' in fields:
            add('Const_Line_Value',[cond('Value_01',[1])]);add('Const_Line_Value0N',[cond('Value_01',[0])])
        if 'EtaFlag' in fields:
            for n in ('EtaStart','EtaEnd'):add(n,[cond('EtaFlag',[1])])
            for n in ('UStart','UEnd'):add(n,[cond('EtaFlag',[0])])
            for n in ('Length_C_Start','Length_C_End','Length_Start','Length_End'):
                add(n,[cond('Abs_Rel_Flag',[v.REL if n.startswith('Length_C_') else v.ABS])]+([cond('SE_Const_Flag',[0])] if n.endswith('End') else []))
            add('StartAngle',[cond('StartAngleFlag',[1])])
            out[fields['EndAngle']]=dict(alternatives=[[cond('EndAngleFlag',[1]),cond('SameAngleFlag',[0])],[cond('EndAngleFlag',[1]),cond('StartAngleFlag',[0])]],limitControllers=[])
    return out


def study_priority(v,pid):
    if not supported(v.GetParmGroupName(pid)):return None
    name=v.GetParmName(pid)
    return -10 if name in ('Value_01','Const_Line_Type','ConstLineType','EtaFlag','Abs_Rel_Flag','SE_Const_Flag','StartAngleFlag','EndAngleFlag','SameAngleFlag','PositiveDirectionFlag','MainSurfIndx') else 20
