"""Name and select original gear/auxiliary drivers; all geometry stays native."""
import native_preview

AUX_CURVE_GROUPS={'Cap','Chevron','Close','Flap','Trim','XSecCurve','XSecCurve_Background'}

AUX_MODES=(('AUX_GEOM_ROTOR_TIP_PATH','Rotor tip path',('PROPELLER',)),('AUX_GEOM_ROTOR_BURST','Rotor burst zone',()),
 ('AUX_GEOM_THREE_PT_GROUND','Three-contact ground plane',('GEAR',)),('AUX_GEOM_TWO_PT_GROUND','Two-contact ground plane',('GEAR',)),
 ('AUX_GEOM_ONE_PT_GROUND','One-contact ground plane',('GEAR',)),('AUX_GEOM_THREE_PT_CCE','Composite clearance envelope',('GEAR',)),
 ('AUX_GEOM_SUPER_CONE','Super cone',()),('AUX_GEOM_SINGLE_GEAR','Single-gear clearance',('GEAR',)),
 ('AUX_GEOM_ROTOR_FRAGMENT','Rotor fragment',()),('AUX_GEOM_THROWN_BLADE','Thrown blade',('PROPELLER',)),
 ('AUX_GEOM_TIRE_SPRAY','Tire spray',('GEAR',)),('AUX_GEOM_WHEEL_TIRE_FAILURE','Wheel and tire failure',('GEAR',)))
LABELS={'NumAcross':'Wheels across','NumTandem':'Wheels in tandem','Symmetrical':'Mirror wheel group',
 'XContactPt':'Contact X (model units)','YContactPt':'Contact Y (model units)','ZAboveGround':'Height above ground (model units)',
 'TireMode':'Tire shape','DiameterMode':'Diameter driver','DiameterIn':'Tire diameter (inches)','DiameterModel':'Tire diameter (model units)',
 'WidthMode':'Width driver','WidthIn':'Tire width (inches)','WidthModel':'Tire width (model units)',
 'SpacingType':'Across-wheel spacing driver','PitchType':'Tandem spacing driver',
 'Spacing':'Across center distance (model units)','SpacingFrac':'Across center distance / tire width',
 'SpacingGap':'Across tire gap (model units)','SpacingGapFrac':'Across tire gap / tire width',
 'Pitch':'Tandem center distance (model units)','PitchFrac':'Tandem center distance / tire diameter',
 'PitchGap':'Tandem tire gap (model units)','PitchGapFrac':'Tandem tire gap / tire diameter',
 'SLRMode':'Loaded-radius driver','DeflectionPct':'Loaded deflection fraction','StaticRadiusIn':'Loaded radius (inches)',
 'StaticRadiusModel':'Loaded radius (model units)','m_ModelLenUnits':'Gear model-length convention','GearConfigMode':'Gear configuration',
 'AuxiliaryGeomType':'Auxiliary shape','RetMode':'Retraction driver',
 'AutoPlaneFlag':'Automatic ground-plane size','PlaneSize':'Ground-plane half-width (model units)',
 'ShowNominalGroundPlane':'Show ground plane'}
LABELS['CGLocalFlag']='CG coordinate frame'
for _axis in 'XYZ':
    for _part,_label in [('Nominal','Nominal'),('Min','Minimum'),('Max','Maximum')]:
        for _frame,_name in [('Local','gear axes'),('Global','world axes')]:
            LABELS[_axis+'CG'+_part+_frame]=_label+' CG '+_axis+' · '+_name+' (model units)'

def choices(v):
    dims=[(v.TIRE_DIM_IN,'Inches'),(v.TIRE_DIM_MODEL,'Model units'),(v.TIRE_DIM_FRAC,'Fraction')]
    spacing=[(getattr(v,n),s) for n,s in [('BOGIE_CENTER_DIST','Center distance'),('BOGIE_CENTER_DIST_FRAC','Center distance fraction'),('BOGIE_GAP','Tire gap'),('BOGIE_GAP_FRAC','Tire gap fraction')]]
    result={n:dims for n in ('DrimMode','WrimMode','WsMode','HsMode')}
    result.update(DiameterMode=dims[:2],WidthMode=dims[:2],SLRMode=[(v.TIRE_DIM_IN,'Radius in inches'),(v.TIRE_DIM_MODEL,'Radius in model units'),(v.TIRE_DIM_FRAC,'Deflection fraction')],
      SpacingType=spacing,PitchType=spacing,
      TireMode=[(getattr(v,n),s) for n,s in [('TIRE_TRA','TRA tire'),('TIRE_FAIR_FLANGE','TRA · faired flange'),('TIRE_FAIR_WHEEL','TRA · faired wheel'),('TIRE_BALLOON','Balloon tire'),('TIRE_BALLOON_WHEEL','Balloon tire with wheel'),('TIRE_BALLOON_FAIR_WHEEL','Balloon tire · faired wheel')]],
      GearConfigMode=[(getattr(v,n),s) for n,s in [('GEAR_CONFIGURATION_DOWN','Down'),('GEAR_CONFIGURATION_UP','Up'),('GEAR_CONFIGURATION_UP_AND_DOWN','Up and down'),('GEAR_CONFIGURATION_INTERMEDIATE','Intermediate'),('GEAR_CONFIGURATION_ALL','All configurations')]],
      RetMode=[(v.GEAR_STOWED_POSITION,'Stowed position'),(v.GEAR_MECHANISM,'Retraction mechanism')],
      m_ModelLenUnits=[(getattr(v,n),s) for n,s in [('LEN_MM','Millimeters'),('LEN_CM','Centimeters'),('LEN_M','Meters'),('LEN_IN','Inches'),('LEN_FT','Feet'),('LEN_YD','Yards')]],
      AuxiliaryGeomType=[(getattr(v,n),s) for n,s,_ in AUX_MODES])
    result['CGLocalFlag']=[(1,'Gear axes'),(0,'World axes')]
    for i in range(1,4):
        result[f'ContactPt{i}_Isymm']=[(0,'Base wheel group'),(1,'Mirrored wheel group')]
        result[f'ContactPt{i}_SuspensionMode']=[(getattr(v,n),s) for n,s in [('GEAR_SUSPENSION_NOMINAL','Nominal'),('GEAR_SUSPENSION_COMPRESSED','Compressed'),('GEAR_SUSPENSION_EXTENDED','Extended')]]
        result[f'ContactPt{i}_TireMode']=[(getattr(v,n),s) for n,s in [('TIRE_STATIC_LODED_CONTACT','Static loaded radius'),('TIRE_NOMINAL_CONTACT','Nominal tire radius'),('TIRE_GROWTH_CONTACT','Grown tire radius'),('TIRE_FLAT_CONTACT','Flat tire radius')]]
    result['ContactPt1_ClearanceMode']=[(getattr(v,n),s) for n,s in [('TIRE_NOMINAL_CLEARANCE','Nominal tire'),('TIRE_GROWTH_CLEARANCE','Grown tire'),('TIRE_CLEARANCE','TRA clearance envelope')]]
    result['ContactPt1_GearMode']=result['GearConfigMode']
    import native_gear_retraction
    result.update(native_gear_retraction.choices(v))
    import native_tire_controls
    result.update(native_tire_controls.choices(v))
    import native_auxiliary_controls
    result.update(native_auxiliary_controls.choices(v))
    return result

def owners(v):
    for g in v.FindGeoms():
        kind=v.GetGeomTypeName(g).upper()
        if kind in ('GEAR','AUXILIARY'):
            yield g,kind,list(v.GetGeomParmIDs(g))

def reasons(v,gid):
    ids=list(v.GetGeomParmIDs(gid));active=native_preview.parameter_activity(v,ids)
    locked={p:'Calculated or locked by OpenVSP for the current configuration.' for p in ids if not active[p]}
    if v.GetGeomTypeName(gid).upper()=='GEAR':
        ground={v.GetParmName(p):p for p in ids if v.GetParmGroupName(p)=='GroundPlane'}
        if v.GetParmVal(ground['AutoPlaneFlag']):
            locked[ground['PlaneSize']]='Calculated by OpenVSP from the aircraft bounds. Turn off automatic sizing to edit it.'
        follower='Global' if v.GetParmVal(ground['CGLocalFlag']) else 'Local'
        for axis in 'XYZ':
            for part in ('Min','Max','Nominal'):
                locked[ground[axis+'CG'+part+follower]]='Calculated by OpenVSP from the selected CG coordinate frame.'
        for b in v.GetAllBogies(gid):
            names={v.GetParmName(p):p for p in v.FindContainerParmIDs(b)}
            for mode,values in [('DiameterMode',['DiameterIn','DiameterModel']),('WidthMode',['WidthIn','WidthModel']),
              ('SLRMode',['StaticRadiusIn','StaticRadiusModel','DeflectionPct']),('DrimMode',['DrimIn','DrimModel','DrimFrac']),('WrimMode',['WrimIn','WrimModel','WrimFrac']),
              ('SpacingType',['Spacing','SpacingFrac','SpacingGap','SpacingGapFrac']),('PitchType',['Pitch','PitchFrac','PitchGap','PitchGapFrac'])]:
                driver=int(v.GetParmVal(names[mode]))
                for index,n in enumerate(values):
                    if index!=driver:locked[names[n]]='Calculated by OpenVSP from the selected '+LABELS.get(mode,mode).lower()+'.'
            for n in ('DFlangeModel','WGModel','DGModel','WsGModel','DsGModel'):
                if n in names:locked[names[n]]='Calculated by OpenVSP from the tire shape and dimensions.'
            import native_gear_retraction
            locked.update(native_gear_retraction.reasons(v,b,names))
            import native_tire_controls
            locked.update(native_tire_controls.reasons(v,names))
    elif v.GetGeomTypeName(gid).upper()=='AUXILIARY':
        fields={v.GetParmName(p):p for p in ids if v.GetParmGroupName(p)=='Design'}
        mode=int(v.GetParmVal(fields['AuxiliaryGeomType']))
        for p in ids:
            if mode!=v.AUX_GEOM_SUPER_CONE and v.GetParmGroupName(p) in AUX_CURVE_GROUPS:
                locked[p]='Internal profile rebuilt by OpenVSP. Use the auxiliary shape or clearance-envelope file controls.'
        if mode==v.AUX_GEOM_SUPER_CONE:
            import native_auxiliary_controls
            locked.update(native_auxiliary_controls.profile_locks(v,gid))
        if mode in (v.AUX_GEOM_THREE_PT_GROUND,v.AUX_GEOM_TWO_PT_GROUND,v.AUX_GEOM_ONE_PT_GROUND,v.AUX_GEOM_THREE_PT_CCE):
            for n in ('ContactPt1_GearMode','ContactPt1_KRetract'):
                locked[fields[n]]='OpenVSP uses the down gear position for this ground or clearance-envelope shape.'
    return active,locked

def enrich(v,gid,params):
    active,locked=reasons(v,gid);options=choices(v)
    import native_gear_retraction
    import native_tire_controls
    import native_auxiliary_controls
    labels={**LABELS,**native_gear_retraction.labels(v),**native_tire_controls.LABELS}
    if v.GetGeomTypeName(gid).upper()=='AUXILIARY':labels.update(native_auxiliary_controls.LABELS)
    cone=v.GetGeomTypeName(gid).upper()=='AUXILIARY' and v.GetParmVal(gid,'AuxiliaryGeomType','Design')==v.AUX_GEOM_SUPER_CONE
    cone_ids=set(v.FindContainerParmIDs(native_auxiliary_controls.curve_container(v,gid))) if cone else set()
    cone_labels={x['parameter']:'Profile '+x['label'].lower() for x in native_auxiliary_controls.dimensions(v,gid)['driverControls']} if cone else {}
    for p in params:
        if p['id'] in active:p['active']=active[p['id']]
        if p['id'] in locked:p.update(displayReadOnly=True,readOnlyReason=locked[p['id']])
        if p['name'] in labels:p['label']=labels[p['name']]
        if p['id'] in cone_ids:
            if p['name'] in ('Width','Height','Diameter','Width_Dummy','Height_Dummy'):p['label']='Profile '+p['name'].replace('_Dummy','').lower()+' (degrees)'
            elif p['name']=='Area':p['label']='Profile area (square degrees)'
            if p['id'] in cone_labels:p['label']=cone_labels[p['id']]
        if p['name'].startswith('ContactPt'):
            suffix=p['name'].split('_',1)[-1]
            label={'Isymm':'Wheel-group side','SuspensionMode':'Suspension','TireMode':'Tire contact radius',
                   'ClearanceMode':'Clearance tire shape','GearMode':'Gear position','KRetract':'Retraction fraction'}.get(suffix)
            if label:p['label']='Contact '+p['name'][9]+' · '+label
        if p['name'] in options:p['choices']=[dict(value=value,label=label) for value,label in options[p['name']] if p['min']<=value<=p['max']]

def read_only_reasons(v):
    return {p:r for g,_,_ in owners(v) for p,r in reasons(v,g)[1].items()}

def cg_coordinate(v,pid):
    if v.GetParmGroupName(pid)!='GroundPlane':return None
    name=v.GetParmName(pid)
    if name not in [axis+'CG'+part+frame for axis in 'XYZ' for part in ('Min','Max','Nominal') for frame in ('Local','Global')]:return None
    owner=v.GetParmContainer(pid)
    if owner not in v.FindGeoms() or v.GetGeomTypeName(owner).upper()!='GEAR':return None
    local=name.endswith('Local')
    return dict(parameter=v.FindParm(owner,'CGLocalFlag','GroundPlane'),value=1 if local else 0,label='Gear axes' if local else 'World axes')

def study_frame_controlled(v,pid,axes):
    coordinate=cg_coordinate(v,pid)
    return coordinate is not None and any(a.get('kind')=='parameter' and a.get('id')==coordinate['parameter'] and coordinate['value'] in a.get('values',[]) for a in axes if isinstance(a,dict))

def cg_range_controller(v,pid):
    """Original nominal parameter controlling a native local range limit."""
    if v.GetParmGroupName(pid)!='GroundPlane':return None
    name=v.GetParmName(pid)
    if name not in [axis+'CG'+part+'Local' for axis in 'XYZ' for part in ('Min','Max')]:return None
    owner=v.GetParmContainer(pid)
    if owner not in v.FindGeoms() or v.GetGeomTypeName(owner).upper()!='GEAR':return None
    return v.FindParm(owner,name[0]+'CGNominalLocal','GroundPlane')

def study_priority(v,pid):
    owner=v.GetParmContainer(pid)
    if owner not in v.FindGeoms() or v.GetGeomTypeName(owner).upper()!='GEAR':return None
    group=v.GetParmGroupName(pid);name=v.GetParmName(pid)
    if group=='GroundPlane':
        if name=='CGLocalFlag':return -6
        if name in [axis+'CGNominal'+frame for axis in 'XYZ' for frame in ('Local','Global')]:return -4
        if cg_range_controller(v,pid):return 2
    if group=='XForm':return -5

def study_limits(v,pid,value,swept_ids):
    """Defer only the bound that an included nominal CG driver will update."""
    lower=v.GetParmLowerLimit(pid);upper=v.GetParmUpperLimit(pid)
    controller=cg_range_controller(v,pid)
    if controller is not None and controller in swept_ids:
        if 'CGMin' in v.GetParmName(pid):return value>=lower
        return value<=upper
    return lower<=value<=upper

def refresh_auxiliary(v):
    """Evaluate native envelopes after the vehicle's scale bounds are available.

    DecodeXml evaluates these surfaces before Vehicle has accumulated its
    scale-independent bounding box. The public contact setter dirties and
    updates the native surface even when its saved reference is unchanged.
    Auxiliary surfaces are excluded from those scale bounds by OpenVSP.
    """
    geoms=list(v.FindGeoms())
    auxiliary=[g for g in geoms if v.GetGeomTypeName(g).upper()=='AUXILIARY' and v.GetGeomParent(g) in geoms]
    for g in auxiliary:
        v.SetAuxiliaryGeomContactPtID(g,0,v.GetAuxiliaryGeomContactPtID(g,0))
    if auxiliary:v.Update()

def validate_parameter(v,pid,value):
    owner=next((g for g,_,ids in owners(v) if pid in ids),None)
    if not owner:return
    import math
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('Enter a finite number.')
    reason=reasons(v,owner)[1].get(pid)
    if reason:raise ValueError(reason)
    option=choices(v).get(v.GetParmName(pid))
    if option and value not in [x[0] for x in option]:raise ValueError('Choose a supported native gear or auxiliary option.')
    if v.GetParmName(pid)=='AuxiliaryGeomType':
        mode=next(m for m in auxiliary_modes(v) if m['value']==value);parent=v.GetGeomParent(owner)
        if mode['parentTypes'] and (parent not in v.FindGeoms() or v.GetGeomTypeName(parent).upper() not in mode['parentTypes']):
            raise ValueError('Choose a compatible parent in Auxiliary shape & parent before changing this shape.')
    if isinstance(value,(int,float)) and v.GetParmType(pid) in (v.PARM_INT_TYPE,v.PARM_BOOL_TYPE,v.PARM_LIMITED_INT_TYPE,v.PARM_POWER_INT_TYPE) and value!=int(value):
        raise ValueError('Use a whole number for this native gear or auxiliary setting.')
    import native_gear_retraction
    native_gear_retraction.validate_parameter(v,pid,value)
    if v.GetParmName(pid)=='m_WheelTireFailureMode' and value==v.WHEEL_TIRE_4:raise ValueError('OpenVSP 3.52.2 does not implement the tire burst-pressure model. Choose one of the five implemented failure models.')
    if v.GetGeomTypeName(owner).upper()=='AUXILIARY' and v.GetParmName(pid) in ('ContactPt1_Isymm','ContactPt2_Isymm','ContactPt3_Isymm') and value==1:
        index=int(v.GetParmName(pid)[9])-1
        parent=v.GetGeomParent(owner);bid=v.GetAuxiliaryGeomContactPtID(owner,index)
        if parent not in v.FindGeoms() or bid not in v.GetAllBogies(parent) or not v.GetParmVal(bid,'Symmetrical','Bogie'):
            raise ValueError('Enable Mirror wheel group on the selected gear before choosing its mirrored contact.')

def auxiliary_modes(v):
    return [dict(value=getattr(v,n),label=label,parentTypes=list(types)) for n,label,types in AUX_MODES]

def setup_auxiliary(v,gid,parent,mode):
    from native_tools import one
    one(gid,[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='AUXILIARY'])
    selected=next((m for m in auxiliary_modes(v) if m['value']==mode),None)
    if selected is None:raise ValueError('Choose a supported auxiliary shape.')
    # Exclude the component and all its descendants from parent candidates.
    forbidden={gid};changed=True
    while changed:
        old=len(forbidden);forbidden.update(g for g in v.FindGeoms() if v.GetGeomParent(g) in forbidden);changed=len(forbidden)!=old
    one(parent,[g for g in v.FindGeoms() if g not in forbidden],'Choose a valid parent component.')
    if selected['parentTypes'] and v.GetGeomTypeName(parent).upper() not in selected['parentTypes']:
        raise ValueError('This auxiliary shape requires a '+', '.join(selected['parentTypes']).lower()+' parent.')
    import native_gear_retraction
    native_gear_retraction.require_dependency(v,gid,parent)
    reset=parent!=v.GetGeomParent(gid)
    v.SetGeomParent(gid,parent)
    if reset:
        for i in range(3):v.SetAuxiliaryGeomContactPtID(gid,i,'')
    v.SetParmValUpdate(gid,'AuxiliaryGeomType','Design',mode)

def guard_bogie_delete(v,bid):
    users=[v.GetGeomName(g) for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='AUXILIARY' and bid in [v.GetAuxiliaryGeomContactPtID(g,i) for i in range(3)]]
    if users:raise ValueError('Reassign contacts or change the dependent auxiliary parent before removing this wheel group: '+', '.join(users))
