"""Organize original component parameters; no geometry or transform equations."""
import re
import native_preview

SUPPORTED={'ELLIPSOID','HINGE','CONFORMAL','FUSELAGE','STACK','WING','COBRA','BODYOFREVOLUTION'}
HINGE_LABELS={
 'JointTranslateFlag':'Enable joint translation','JointTranslate':'Joint translation',
 'JointRotateFlag':'Enable joint rotation','JointRotate':'Joint rotation',
 'JointTransMinFlag':'Use minimum translation','JointTransMin':'Minimum translation',
 'JointTransMaxFlag':'Use maximum translation','JointTransMax':'Maximum translation',
 'JointRotMinFlag':'Use minimum rotation','JointRotMin':'Minimum rotation',
 'JointRotMaxFlag':'Use maximum rotation','JointRotMax':'Maximum rotation',
 'OrientRotFlag':'Orientation method','PrimaryDir':'Joint motion axis','SecondaryDir':'Secondary component axis',
 'PrimType':'Primary direction source','PrimVecAbsRelFlag':'Primary vector frame',
 'PrimOffAbsRelFlag':'Target point / offset frame','SecVecAbsRelFlag':'Secondary direction frame',
 'SecondaryVecDir':'Secondary reference direction','PrimULoc':'Parent surface U','PrimWLoc':'Parent surface W'}
CONFORMAL_LABELS={
 'Offset':'Surface offset','OffSetEnds':'Offset surface ends','DetachFlag':'Detach from source component',
 'HingeConformalPositionFlag':'Follow conformal source position on hinge',
 'UTrimFlag':'Enable longitudinal trimming','UMinTrimTypeFalg':'Start trim coordinate',
 'UMaxTrimTypeFalg':'End trim coordinate','UTrimMin':'Start U fraction','UTrimMax':'End U fraction',
 'L01Min':'Start L basis','L01Max':'End L basis','LTrimMin':'Start L fraction','LTrimMax':'End L fraction',
 'L0LenTrimMin':'Start distance along source','L0LenTrimMax':'End distance along source',
 'EtaTrimMin':'Start wing span fraction','EtaTrimMax':'End wing span fraction',
 'V1TrimFlag':'Enable perimeter trim 1','V1TrimBegin':'Perimeter trim 1 start','V1TrimEnd':'Perimeter trim 1 end',
 'V2TrimFlag':'Enable perimeter trim 2','V2TrimBegin':'Perimeter trim 2 start','V2TrimEnd':'Perimeter trim 2 end',
 'ChordTrimFlag':'Enable chord trimming','ChordTrimMin':'Start chord fraction','ChordTrimMax':'End chord fraction'}
WING_LABELS={'RotateAirfoilMatchDideralFlag':'Orient airfoils with dihedral',
 'CorrectAirfoilthicknessFlag':'Correct thickness for dihedral',
 'TwistAllInXZPlaneFlag':'Apply twist in the XZ plane'}
COBRA_LABELS={'XradN':'Nose X radius','YradN':'Nose Y radius','ZradNU':'Nose upper Z radius',
 'ZradNL':'Nose lower Z radius','PowX':'Nose lateral exponent','PowNU':'Nose upper exponent',
 'PowNL':'Nose lower exponent','NoseULSymm':'Match nose upper and lower shape',
 'XlenA':'Aft length','YradA':'Aft Y radius','ZradAU':'Aft upper Z radius',
 'ZradAL':'Aft lower Z radius','PowAU':'Aft upper exponent','PowAL':'Aft lower exponent',
 'AftULSymm':'Match aft upper and lower shape'}


def apply(v,gid,params):
    kind=v.GetGeomTypeName(gid).upper()
    if kind not in SUPPORTED:return []
    ids=[p['id'] for p in params];activity=native_preview.parameter_activity(v,ids)
    fields={p['name']:p for p in params if p['rawGroup']==('Hinge' if kind=='HINGE' else 'WingGeom' if kind=='WING' else 'Design')}
    import native_engine_controls
    groups=native_engine_controls.groups(params) if kind in ('FUSELAGE','STACK') else []
    def lock(name,reason):
        p=fields.get(name)
        if p:p.update(displayReadOnly=True,readOnlyReason=reason)
    def group(title,names,note,open=False):
        selected=[fields[n]['id'] for n in names if n in fields]
        if selected:groups.append(dict(title=title,parameters=selected,note=note,open=open))
    for p in params:
        # Retain stronger policies applied by section, attachment and cap editors.
        if p['id'] in activity and not activity[p['id']]:
            p['active']=False
            if not p.get('readOnlyReason'):p['readOnlyReason']='Locked or calculated by OpenVSP for the current component settings.'
    if kind=='ELLIPSOID':
        for name,axis in [('A_Radius','X'),('B_Radius','Y'),('C_Radius','Z')]:
            if name in fields:fields[name].update(label=axis+' radius',dimension='length')
    elif kind=='BODYOFREVOLUTION':
        import native_bor_dimensions
        native_bor_dimensions.enrich(v,gid,params)
        labels={'Mode':'Revolution mode','Diameter':'Flow-through diameter','Angle':'Flow-through profile angle','A0':'Leading-edge flow area (model units²)','Ae':'Trailing-edge flow area (model units²)','Amin':'Minimum flow area (model units²)','AminW':'Minimum-area profile position (0–1)','LECluster':'Leading-edge tessellation clustering','TECluster':'Trailing-edge tessellation clustering'}
        for name,label in labels.items():
            if name in fields:fields[name]['label']=label
        fields['Mode']['choices']=[[v.BOR_FLOWTHROUGH,'Flow-through'],[v.BOR_UPPER,'Revolve upper profile'],[v.BOR_LOWER,'Revolve lower profile']]
        fields['Diameter']['dimension']='length';fields['Angle']['dimension']='angle'
        if fields['Mode']['value']!=v.BOR_FLOWTHROUGH:
            for name in ('Diameter','Angle'):lock(name,'Used by native flow-through revolution; upper/lower modes revolve the selected profile half.')
        group('Body-of-revolution mode',['Mode','Diameter','Angle'],'Flow-through rotates and offsets the profile using its angle and diameter. Upper/lower modes revolve the selected native profile half.',True)
        group('Native revolution flow areas',['A0','Ae','Amin','AminW'],'These are original engine outputs. Upper/lower revolution modes return zero flow areas; profile and mode changes recalculate them.')
        group('Revolution surface sampling',['LECluster','TECluster'],'These original clustering controls determine native sampling near the profile edges.')
    elif kind in ('FUSELAGE','STACK'):
        p=fields.get('OrderPolicy')
        if p:p.update(label='Section ordering',choices=[[0,'Monotonic'],[1,'Loop'],[2,'Free']] if kind=='FUSELAGE' else [[0,'Free'],[1,'Loop']])
        group('Section ordering',['OrderPolicy'],'The native policy controls section ordering and loop closure. Change section positions and blending in the section editor.')
    elif kind=='WING':
        for n,label in WING_LABELS.items():
            if n in fields:fields[n]['label']=label
        group('Wing airfoil orientation',list(WING_LABELS),'These settings apply across the wing. OpenVSP orients profiles and applies its dihedral thickness correction; local section settings remain in the section editor.')
    elif kind=='COBRA':
        for n,label in COBRA_LABELS.items():
            if n in fields:fields[n]['label']=label
            if n in fields and ('rad' in n or n=='XlenA'):fields[n]['dimension']='length'
        for prefix,flag in [('Nose','NoseULSymm'),('Aft','AftULSymm')]:
            if fields[flag]['value']:
                for n in (['ZradNL','PowNL'] if prefix=='Nose' else ['ZradAL','PowAL']):lock(n,'The native lower shape follows the upper shape while matching is enabled.')
        group('Nose shape',['XradN','YradN','ZradNU','NoseULSymm','ZradNL','PowX','PowNU','PowNL'],'Native nose radii and superellipse exponents.',True)
        group('Aft shape',['XlenA','YradA','ZradAU','AftULSymm','ZradAL','PowAU','PowAL'],'Native aft length, radii and superellipse exponents.')
    elif kind=='HINGE':
        for n,label in HINGE_LABELS.items():
            if n in fields:fields[n]['label']=label
        axis=[[v.X_DIR,'X'],[v.Y_DIR,'Y'],[v.Z_DIR,'Z']];frame=[[v.ABS,'Global'],[v.REL,'Relative to attachment']]
        for n in ('PrimaryDir','SecondaryDir','SecondaryVecDir'):fields[n]['choices']=axis
        for n in ('PrimVecAbsRelFlag','PrimOffAbsRelFlag','SecVecAbsRelFlag'):fields[n]['choices']=frame
        fields['OrientRotFlag']['choices']=[[0,'Placement rotation angles'],[1,'Direction vectors / target point']]
        fields['PrimType']['choices']=[[0,'XYZ vector'],[1,'XYZ target point'],[2,'Parent surface point + offset'],[3,'Parent surface U direction'],[4,'Parent surface W direction'],[5,'Parent surface normal']]
        for n in fields:
            if n in ('JointTranslate','JointTransMin','JointTransMax') or re.fullmatch(r'Prim[XYZ]Off(Rel)?',n):fields[n]['dimension']='length'
            if n in ('JointRotate','JointRotMin','JointRotMax'):fields[n]['dimension']='angle'
            if re.fullmatch(r'Prim[XYZ](Vec|Off)(Rel)?',n):
                fields[n]['label']=('Primary vector ' if 'Vec' in n else 'Target point / offset ')+n[4]+(' relative' if n.endswith('Rel') else ' global')
        vector=fields['OrientRotFlag']['value']==1;typ=int(fields['PrimType']['value'])
        for base,flag in [('JointTranslate','JointTranslateFlag'),('JointRotate','JointRotateFlag')]:
            if not fields[flag]['value']:lock(base,'Enable this joint motion before changing its value; the native engine otherwise resets it to zero.')
        for n in ('PrimXVec','PrimYVec','PrimZVec','PrimXVecRel','PrimYVecRel','PrimZVecRel'):
            rel=n.endswith('Rel')
            if not vector or typ!=0 or rel!=(fields['PrimVecAbsRelFlag']['value']==v.REL):lock(n,'Calculated from the selected native hinge orientation. Select this vector and frame to edit it.')
        for n in ('PrimXOff','PrimYOff','PrimZOff','PrimXOffRel','PrimYOffRel','PrimZOffRel'):
            if not vector or typ not in (1,2) or n.endswith('Rel')!=(fields['PrimOffAbsRelFlag']['value']==v.REL):lock(n,'Select target-point orientation and this coordinate frame to edit the point or offset.')
        if vector:
            for p in params:
                if p['rawGroup']=='XForm' and re.fullmatch(r'[XYZ]_(Rel_)?Rotation',p['name']):p.update(displayReadOnly=True,readOnlyReason='OpenVSP derives hinge placement rotation from its direction vectors.')
        group('Joint motion',['PrimaryDir','JointRotateFlag','JointRotate','JointTranslateFlag','JointTranslate'],'Attach the moving wing, body or equipment to this hinge in its attachment editor. Native joint motion follows the primary component axis.',True)
        group('Joint travel limits',['JointRotMinFlag','JointRotMin','JointRotMaxFlag','JointRotMax','JointTransMinFlag','JointTransMin','JointTransMaxFlag','JointTransMax'],'Enable the desired minimum and maximum bounds. The native engine updates motion limits and applied values.')
        orientation=['OrientRotFlag']
        if vector:
            orientation+=['SecondaryDir','PrimType']
            if typ==0:
                suffix='Rel' if fields['PrimVecAbsRelFlag']['value']==v.REL else ''
                orientation+=['PrimVecAbsRelFlag']+['Prim'+axis+'Vec'+suffix for axis in 'XYZ']
            if typ in (1,2):
                suffix='Rel' if fields['PrimOffAbsRelFlag']['value']==v.REL else ''
                orientation+=['PrimOffAbsRelFlag']+['Prim'+axis+'Off'+suffix for axis in 'XYZ']
            if typ>=2:orientation+=['PrimULoc','PrimWLoc']
            orientation+=['SecVecAbsRelFlag','SecondaryVecDir']
        group('Hinge orientation',orientation,'Use Placement rotation angles or a native direction/target. Surface directions refer to the parent’s first surface. Global and relative alternatives follow the selected frame.')
    elif kind=='CONFORMAL':
        for n,label in CONFORMAL_LABELS.items():
            if n in fields:fields[n]['label']=label
        for i in range(1,5):
            fields['Side'+str(i)+'TrimFlag']['label']='Enable wing side '+str(i)+' trimming'
            fields['Side'+str(i)+'Trim']['label']='Wing side '+str(i)+' trim fraction'
        for n in ('Offset','L0LenTrimMin','L0LenTrimMax'):fields[n]['dimension']='length'
        for end in ('Min','Max'):
            fields['U'+end+'TrimTypeFalg']['choices']=[[v.U_TRIM,'Native U'],[v.L_TRIM,'Length along source'],[v.ETA_TRIM,'Wing span (eta)']]
            fields['L01'+end]['choices']=[[1,'Normalized fraction'],[0,'Physical length']]
            typ=int(fields['U'+end+'TrimTypeFalg']['value']);fraction=bool(fields['L01'+end]['value'])
            for n,enabled in [('UTrim'+end,typ==v.U_TRIM),('LTrim'+end,typ==v.L_TRIM and fraction),('L0LenTrim'+end,typ==v.L_TRIM and not fraction),('EtaTrim'+end,typ==v.ETA_TRIM)]:
                if not enabled:lock(n,'Calculated by OpenVSP from the selected trim coordinate and length basis.')
        group('Conformal offset',['Offset','OffSetEnds','DetachFlag','HingeConformalPositionFlag'],'The native engine offsets the source surface. Attached geometry follows the source’s attachment and symmetry. Detachment unlocks the native reference controls.',True)
        trim=['UTrimFlag']
        for end in ('Min','Max'):
            trim.append('U'+end+'TrimTypeFalg');typ=int(fields['U'+end+'TrimTypeFalg']['value'])
            if typ==v.U_TRIM:trim.append('UTrim'+end)
            elif typ==v.L_TRIM:trim+=['L01'+end,('LTrim' if fields['L01'+end]['value'] else 'L0LenTrim')+end]
            else:trim.append('EtaTrim'+end)
        group('Longitudinal trimming',trim,'Choose U, length along the source or wing span (eta) at each end. Eta applies to wing sources. Calculated alternatives remain protected; end-cap shaping stays in the cap editor.')
        group('Perimeter trimming',['V1TrimFlag','V1TrimBegin','V1TrimEnd','V2TrimFlag','V2TrimBegin','V2TrimEnd'],'Two native perimeter trim intervals use fractions of the source surface parameter.')
        group('Wing chord & side trimming',['ChordTrimFlag','ChordTrimMin','ChordTrimMax']+[n for i in range(1,5) for n in ('Side'+str(i)+'TrimFlag','Side'+str(i)+'Trim')],'These native controls apply to conformal wing geometry. Body sources use longitudinal and perimeter trimming.')
    return groups


def read_only_reasons(v):
    result={}
    for gid in v.FindGeoms():
        if v.GetGeomTypeName(gid).upper() not in SUPPORTED:continue
        fields=[dict(id=p,name=v.GetParmName(p),rawGroup=v.GetParmGroupName(p),value=v.GetParmVal(p)) for p in v.GetGeomParmIDs(gid)]
        apply(v,gid,fields)
        result.update({p['id']:p.get('readOnlyReason','Calculated by OpenVSP.') for p in fields if p.get('displayReadOnly') or p.get('active') is False})
    return result


def validate_parameter(v,pid):
    reason=read_only_reasons(v).get(pid)
    if reason:raise ValueError(reason)
