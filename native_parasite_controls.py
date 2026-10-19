"""Saved parasite-drag controls; the original manager owns atmosphere and units."""
import ctypes,json
LABELS={'FreestreamType':'Atmosphere / supplied properties','RefFlag':'Reference area source','Sref':'Reference area','LengthUnit':'Native model length units','AltLengthUnit':'Altitude / density units','TempUnit':'Temperature units','PresUnit':'Pressure units','VinfUnitType':'Airspeed units','Vinf':'Airspeed','Alt':'Altitude','DeltaTemp':'Temperature offset','Temp':'Temperature','Pres':'Pressure','Density':'Density','DynaVisc':'Dynamic viscosity','Mach':'Mach number','Re_L':'Reynolds number per model length','SpecificHeatRatio':'Specific heat ratio','LamCfEqnType':'Laminar friction method','TurbCfEqnType':'Turbulent friction method','Set':'Geometry set','UseModeMassFlag':'Geometry selection','ExportSubCompFlag':'Component detail in export','SortBy':'Native report sorting'}
UNIT_METHODS={'VinfUnitType':0,'AltLengthUnit':1,'TempUnit':2,'PresUnit':3}
FLOW={'Vinf','Alt','DeltaTemp','Temp','Pres','Density','DynaVisc','Mach','Re_L','SpecificHeatRatio','Sref'}


def ids(v):return {v.GetParmName(p):p for p in v.FindContainerParmIDs(v.FindContainer('ParasiteDragSettings',0)) if v.GetParmGroupName(p)=='ParasiteDrag'}


PRESSURE_ATTRIBUTE='Studio.ParasitePressureUnit'


def pressure_attribute(v):
    return next((a for a in v.FindAttributesInCollection(v.GetChildCollection(v.GetVehicleID())) if v.GetAttributeName(a)==PRESSURE_ATTRIBUTE),None)


def pressure_unit(v):
    attr=pressure_attribute(v)
    return v.GetAttributeIntVal(attr)[0] if attr else v.PRES_UNIT_PSF


def native_unit(v,kind,value):
    from native_preview import adapter
    _,engine,bridge=adapter(v);fn=bridge.studio_parasite_units;fn.argtypes=[ctypes.c_char_p,ctypes.c_int,ctypes.c_int];fn.restype=ctypes.c_char_p
    data=json.loads(fn(engine,kind,int(value)))
    if data.get('error'):raise ValueError(data['error'])


def refresh(v):
    # Original pressure units are an unsaved manager integer, not a Parm.
    # Restore the saved native attribute before the original atmosphere update;
    # retain the saved pressure number already expressed in that saved unit.
    if not hasattr(v,'_studio_parasite_pressure_unit'):
        unit=pressure_unit(v);pid=ids(v)['Pres'];saved=v.GetParmVal(pid)
        if unit!=v.PRES_UNIT_PSF:native_unit(v,3,unit);v.SetParmVal(pid,saved)
        v._studio_parasite_pressure_unit=unit
    v.UpdateParasiteDrag()


def options(v,name):
    from native_guides import choices
    maps={
      'FreestreamType':[('ATMOS_TYPE_US_STANDARD_1976','US Standard Atmosphere 1976'),('ATMOS_TYPE_HERRINGTON_1966','Herrington 1966'),('ATMOS_TYPE_MANUAL_P_R','Supplied pressure and density'),('ATMOS_TYPE_MANUAL_P_T','Supplied pressure and temperature'),('ATMOS_TYPE_MANUAL_R_T','Supplied density and temperature'),('ATMOS_TYPE_MANUAL_RE_L','Supplied Reynolds number per length')],
      'RefFlag':[('MANUAL_REF','Entered reference area'),('COMPONENT_REF','Native wing area')],
      'LengthUnit':[('LEN_MM','mm'),('LEN_CM','cm'),('LEN_M','m'),('LEN_IN','in'),('LEN_FT','ft'),('LEN_YD','yd'),('LEN_UNITLESS','Unitless')],
      'AltLengthUnit':[('PD_UNITS_IMPERIAL','ft · slug/ft³'),('PD_UNITS_METRIC','m · kg/m³')],
      'TempUnit':[('TEMP_UNIT_K','K'),('TEMP_UNIT_C','°C'),('TEMP_UNIT_F','°F'),('TEMP_UNIT_R','°R')],
      'PresUnit':[(n,l) for n,l in [('PRES_UNIT_PSF','lbf/ft²'),('PRES_UNIT_PSI','psi'),('PRES_UNIT_BA','barye'),('PRES_UNIT_PA','Pa'),('PRES_UNIT_KPA','kPa'),('PRES_UNIT_MPA','MPa'),('PRES_UNIT_INCHHG','inHg'),('PRES_UNIT_MMHG','mmHg'),('PRES_UNIT_MMH20','mmH₂O'),('PRES_UNIT_MB','mbar'),('PRES_UNIT_ATM','atm')]],
      'VinfUnitType':[('V_UNIT_FT_S','ft/s'),('V_UNIT_M_S','m/s'),('V_UNIT_MPH','mph'),('V_UNIT_KM_HR','km/h'),('V_UNIT_KEAS','knots · equivalent'),('V_UNIT_KTAS','knots · true'),('V_UNIT_MACH','Mach')],
      'LamCfEqnType':[('CF_LAM_BLASIUS','Blasius'),('CF_LAM_BLASIUS_W_HEAT','Blasius with heat transfer')],
      'TurbCfEqnType':[(n,n.removeprefix('CF_TURB_').replace('_',' ').title()) for n in dir(v) if n.startswith('CF_TURB_')],
    }
    if name=='Set':return [dict(value=i,label=v.GetSetName(i)+' · '+str(i)) for i in range(v.GetNumSets())]
    if name=='UseModeMassFlag':return [dict(value=0,label='Geometry set'),dict(value=1,label='Native mode')]
    return choices(v,maps[name]) if name in maps else None


def reason(v,pid):
    if v.GetParmGroupName(pid)!='ParasiteDrag' or v.GetParmContainer(pid)!=v.FindContainer('ParasiteDragSettings',0):return ''
    n=v.GetParmName(pid)
    if n in ('ExcresVal','ExcresType'):return 'Edit the named saved allowance using the drag-allowance editor.'
    if n=='Set' and v.GetParmVal(ids(v)['UseModeMassFlag']):return 'The saved native mode supplies geometry selection.'
    if n in FLOW:
        from native_preview import parameter_activity
        if not parameter_activity(v,[pid])[pid]:return 'Calculated or inactive in the original parasite-drag manager for the saved reference/atmosphere choices.'
    return ''


def annotate(v,p):
    if p['rawGroup']!='ParasiteDrag' or v.GetParmContainer(p['id'])!=v.FindContainer('ParasiteDragSettings',0):return
    if p['name'] in LABELS:p['label']=LABELS[p['name']]
    choices=options(v,p['name'])
    if choices:p['choices']=[c for c in choices if p['min']<=c['value']<=p['max']]
    why=reason(v,p['id'])
    if why:p.update(active=False,editable=False,readOnly=True,readOnlyReason=why)


def validate_parameter(v,pid,value=None):
    if v.GetParmGroupName(pid)!='ParasiteDrag' or v.GetParmContainer(pid)!=v.FindContainer('ParasiteDragSettings',0):return
    refresh(v);why=reason(v,pid)
    if why:raise ValueError(why)
    n=v.GetParmName(pid)
    if n in ('RefFlag','UseModeMassFlag') and value==1:
        import native_references
        refs=native_references.references(v).get(v.FindContainer('ParasiteDragSettings',0),{})
        key='ReferenceGeomID' if n=='RefFlag' else 'ModeID'
        available=[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='WING'] if n=='RefFlag' else list(v.GetAllModes())
        if refs.get(key) not in available:raise ValueError('Save an existing reference wing or mode before enabling its parasite-drag selection.')


def set_parameter(v,pid,value):
    if v.GetParmGroupName(pid)!='ParasiteDrag' or v.GetParmContainer(pid)!=v.FindContainer('ParasiteDragSettings',0) or v.GetParmName(pid) not in UNIT_METHODS:return False
    if isinstance(value,bool) or int(value)!=value:raise ValueError('Choose a native unit.')
    refresh(v);native_unit(v,UNIT_METHODS[v.GetParmName(pid)],value)
    refresh(v);return True


def configuration(v,refs):
    cid=v.FindContainer('ParasiteDragSettings',0);fields=ids(v)
    sections=[dict(title=title,parameters=[fields[n] for n in names if n in fields]) for title,names in [
        ('Geometry and reference area',['UseModeMassFlag','Set','RefFlag','Sref','LengthUnit']),
        ('Flight condition',['FreestreamType','Alt','DeltaTemp','Vinf','Mach','Re_L','SpecificHeatRatio']),
        ('Property units and supplied values',['AltLengthUnit','VinfUnitType','TempUnit','PresUnit','Temp','Pres','Density','DynaVisc']),
        ('Friction and export',['LamCfEqnType','TurbCfEqnType','ExportSubCompFlag'])]]
    return dict(sections=sections,reference=refs.get(cid,{}),pressureUnit=pressure_unit(v),pressureChoices=options(v,'PresUnit'),wings=[dict(id=g,name=v.GetGeomName(g)) for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='WING'],modes=[dict(id=m,name=v.GetModeName(m)) for m in v.GetAllModes()])


def mutate(v,r):
    from native_tools import one
    import native_references
    cid=v.FindContainer('ParasiteDragSettings',0)
    if r['operation']=='parasite-pressure-unit':
        value=one(r.get('unit'),[c['value'] for c in options(v,'PresUnit')]);refresh(v);native_unit(v,3,value);v._studio_parasite_pressure_unit=value
        attr=pressure_attribute(v)
        if attr:v.SetAttributeInt(attr,int(value))
        else:v.AddAttributeInt(v.GetChildCollection(v.GetVehicleID()),PRESSURE_ATTRIBUTE,int(value))
        refresh(v);return
    if r['operation']=='parasite-reference-wing':key='ReferenceGeomID';value=one(r.get('wing'),['']+[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='WING'])
    elif r['operation']=='parasite-reference-mode':key='ModeID';value=one(r.get('mode'),['']+list(v.GetAllModes()))
    else:raise ValueError('Unknown saved parasite-drag reference operation.')
    if not value and v.GetParmVal(ids(v)['RefFlag' if key=='ReferenceGeomID' else 'UseModeMassFlag']):raise ValueError('Switch to entered area or geometry sets before clearing the active parasite-drag reference.')
    native_references.set_reference(v,cid,'ParasiteDragMgr',key,value)


def study_metadata(v):
    p=ids(v);standard=[v.ATMOS_TYPE_US_STANDARD_1976,v.ATMOS_TYPE_HERRINGTON_1966];manual=[v.ATMOS_TYPE_MANUAL_P_R,v.ATMOS_TYPE_MANUAL_P_T,v.ATMOS_TYPE_MANUAL_R_T];out={}
    def condition(n,values):return dict(parameter=p[n],values=values,label=LABELS[n])
    def add(n,controller,values):out[p[n]]=dict(conditions=[condition(controller,values)],limitControllers=[p[k] for k in UNIT_METHODS if k in p])
    for n in ('Alt','DeltaTemp'):add(n,'FreestreamType',standard)
    add('Vinf','FreestreamType',standard+manual)
    add('Temp','FreestreamType',[v.ATMOS_TYPE_MANUAL_P_T,v.ATMOS_TYPE_MANUAL_R_T]);add('Pres','FreestreamType',[v.ATMOS_TYPE_MANUAL_P_R,v.ATMOS_TYPE_MANUAL_P_T]);add('Density','FreestreamType',[v.ATMOS_TYPE_MANUAL_P_R,v.ATMOS_TYPE_MANUAL_R_T])
    for n in ('Mach','Re_L'):add(n,'FreestreamType',[v.ATMOS_TYPE_MANUAL_RE_L])
    add('Sref','RefFlag',[v.MANUAL_REF]);add('Set','UseModeMassFlag',[0])
    out[p['SpecificHeatRatio']]=dict(alternatives=[[condition('FreestreamType',manual+[v.ATMOS_TYPE_MANUAL_RE_L])],[condition('TurbCfEqnType',[v.CF_TURB_ROUGHNESS_SCHLICHTING_AVG_FLOW_CORRECTION,v.CF_TURB_HEATTRANSFER_WHITE_CHRISTOPH])]],limitControllers=[])
    return out


def study_priority(v,pid):
    if v.GetParmGroupName(pid)!='ParasiteDrag' or v.GetParmContainer(pid)!=v.FindContainer('ParasiteDragSettings',0):return None
    return -20 if v.GetParmName(pid) in UNIT_METHODS or v.GetParmName(pid)=='LengthUnit' else -10 if v.GetParmName(pid) in ('FreestreamType','RefFlag','UseModeMassFlag','TurbCfEqnType') else 40


def guard_geometry_delete(v,gid):
    if v.GetParmVal(ids(v)['RefFlag'])!=v.COMPONENT_REF:return
    import native_references
    ref=native_references.references(v).get(v.FindContainer('ParasiteDragSettings',0),{}).get('ReferenceGeomID')
    removed={gid};pending=[gid]
    while pending:
        for child in v.GetGeomChildren(pending.pop()):
            if child not in removed:removed.add(child);pending.append(child)
    if ref in removed:raise ValueError('This wing supplies saved parasite-drag reference area. Choose another reference wing or entered area before removing it.')


def guard_mode_delete(v,mode):
    if not v.GetParmVal(ids(v)['UseModeMassFlag']):return
    import native_references
    ref=native_references.references(v).get(v.FindContainer('ParasiteDragSettings',0),{}).get('ModeID')
    if ref==mode:raise ValueError('This mode supplies saved parasite-drag geometry selection. Choose another mode or geometry sets before removing it.')
