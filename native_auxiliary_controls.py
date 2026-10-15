"""Auxiliary editor organization and original native SuperCone operations."""
import ctypes,json

LABELS={'AutoDiam':'Automatic envelope diameter','Diameter':'Envelope diameter (model units)','FlapRadiusFract':'Flapping radius / rotor radius',
 'RootLength':'Envelope root length (model units)','RootOffset':'Root offset / root length','ThetaThrust':'Thrust-side angle (degrees)','ThetaAntiThrust':'Opposite-side angle (degrees)',
 'RotorFragmentMode':'Rotor fragment model','DiskRadius':'Disk radius (model units)','BladeLength':'Blade length (model units)','BladeRootRadius':'Blade root radius (model units)',
 'FragLength':'Fragment length (model units)','CGRadius':'Fragment CG radius (model units)','ReleaseAngle':'Release angle (degrees)','RotDir':'Rotation direction',
 'ThrownBladeMode':'Thrown-blade model','ThrownBladeCGFrac':'Blade CG / blade span','CCEUnits':'Clearance-envelope file units','CCEMainGearOffset':'Main-gear envelope offset (model units)',
 'SCWorldAligned':'Cone alignment','BogieTheta':'Bogie pitch (degrees)','WheelTheta':'Wheel angle (degrees)','RollTheta':'Aircraft roll (degrees)',
 'SprayTireContactWidth':'Contact width / tire diameter','SprayTireContactHalfLength':'Contact half-length / tire diameter',
 'SpraySideElevationAngle':'Side-spray elevation (degrees)','SpraySidePlanAngle':'Side-spray plan angle (degrees)','SpraySideIncrementalAngle':'Side-spray increment (degrees)',
 'SpraySideInclinationAngle':'Side-spray inclination (degrees)','SprayCenterElevationAngle':'Center-spray elevation (degrees)','SprayCenterWidth':'Center-spray width / tire diameter',
 'm_WheelTireFailureMode':'Wheel and tire failure model'}

# Field group membership follows AuxiliaryGeomScreen, not new engineering math.
SPECS={
 'AUX_GEOM_ROTOR_TIP_PATH':(0,[('Rotor envelope',['AutoDiam','Diameter','FlapRadiusFract','ThetaThrust','ThetaAntiThrust'])]),
 'AUX_GEOM_ROTOR_BURST':(0,[('Burst envelope',['AutoDiam','Diameter','RootLength','RootOffset','ThetaThrust','ThetaAntiThrust'])]),
 'AUX_GEOM_ROTOR_FRAGMENT':(0,[('Fragment model',['RotorFragmentMode','ReleaseAngle','RotDir']),('Fragment dimensions',['DiskRadius','BladeLength','BladeRootRadius','FragLength','CGRadius','ThetaThrust','ThetaAntiThrust'])]),
 'AUX_GEOM_THROWN_BLADE':(0,[('Thrown blade',['ThrownBladeMode','ThrownBladeCGFrac','ReleaseAngle','ThetaThrust','ThetaAntiThrust'])]),
 'AUX_GEOM_THREE_PT_GROUND':(3,[]),
 'AUX_GEOM_TWO_PT_GROUND':(2,[('Aircraft attitude',['BogieTheta','WheelTheta'])]),
 'AUX_GEOM_ONE_PT_GROUND':(1,[('Aircraft attitude',['BogieTheta','WheelTheta','RollTheta'])]),
 'AUX_GEOM_THREE_PT_CCE':(3,[('Clearance envelope',['CCEUnits','CCEMainGearOffset'])]),
 'AUX_GEOM_SINGLE_GEAR':(1,[('Wheel-group attitude',['BogieTheta'])]),
 'AUX_GEOM_TIRE_SPRAY':(1,[('Tire contact',['SprayTireContactWidth','SprayTireContactHalfLength']),('Side spray',['SpraySideElevationAngle','SpraySidePlanAngle','SpraySideIncrementalAngle','SpraySideInclinationAngle']),('Center spray',['SprayCenterElevationAngle','SprayCenterWidth'])]),
 'AUX_GEOM_WHEEL_TIRE_FAILURE':(1,[('Failure envelope',['m_WheelTireFailureMode'])]),
 'AUX_GEOM_SUPER_CONE':(0,[('Cone alignment',['SCWorldAligned'])])}

def choices(v):
    enum=lambda items:[(getattr(v,n),s) for n,s in items]
    return dict(RotorFragmentMode=enum([('ONE_THIRD_ROTOR_FRAGMENT','One-third rotor'),('INTERMEDIATE_FRAGMENT','Intermediate rotor'),('ALTERNATE_FRAGMENT','Alternate rotor'),('FAN_FRAGMENT','Fan blade'),('SMALL_FRAGMENT','Small fragment'),('GENERIC_FRAGMENT','Generic fragment')]),
      ThrownBladeMode=enum([('PROP_BLADE_TRADITIONAL','Basic blade'),('PROP_BLADE_NONTRADITIONAL','Unconventional blade')]),
      m_WheelTireFailureMode=enum([('WHEEL_TIRE_1LG','Model 1 · large'),('WHEEL_TIRE_1SM','Model 1 · small'),('WHEEL_TIRE_2','Model 2'),('WHEEL_TIRE_3E','Model 3E'),('WHEEL_TIRE_3R','Model 3R'),('WHEEL_TIRE_4','Tire burst pressure · not implemented by OpenVSP')]),
      CCEUnits=enum([('LEN_MM','Millimeters'),('LEN_CM','Centimeters'),('LEN_M','Meters'),('LEN_IN','Inches'),('LEN_FT','Feet'),('LEN_YD','Yards'),('LEN_UNITLESS','Match model units')]),
      SCWorldAligned=[(0,'Parent component axes'),(1,'World axes')],RotDir=[(0,'Default direction'),(1,'Opposite direction')],
      CockpitSide=enum([('XSEC_LEFT_SIDE','Left seat'),('XSEC_RIGHT_SIDE','Right seat')]))

def curve_container(v,gid):
    ids=[p for p in v.GetGeomParmIDs(gid) if v.GetParmGroupName(p)=='XSecCurve']
    if not ids:raise ValueError('Native auxiliary profile unavailable.')
    return v.GetParmContainer(ids[0])

def curve(v,gid,operation=0,argument=0):
    from native_tools import one
    one(gid,[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='AUXILIARY'],'Choose an auxiliary geometry.')
    if v.GetParmVal(gid,'AuxiliaryGeomType','Design')!=v.AUX_GEOM_SUPER_CONE:raise ValueError('Choose Super cone before editing its profile.')
    import native_preview
    _,engine,bridge=native_preview.adapter(v);function=bridge.studio_auxiliary_curve
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int,ctypes.c_int];function.restype=ctypes.c_char_p
    data=json.loads(function(engine,gid.encode(),curve_container(v,gid).encode(),operation,argument))
    if data.get('error'):raise ValueError(data['error'])
    return data

def metadata(v,gid):
    mode=int(v.GetParmVal(gid,'AuxiliaryGeomType','Design'))
    name=next(n for n in SPECS if getattr(v,n)==mode);count,groups=SPECS[name]
    result=dict(mode=name,contactCount=count,groups=[dict(title=t,names=n) for t,n in groups],clearanceFile=mode==v.AUX_GEOM_THREE_PT_CCE)
    parent=v.GetGeomParent(gid)
    if count==3 and parent in v.FindGeoms() and v.GetGeomTypeName(parent).upper()=='GEAR':
        import native_preview
        _,engine,bridge=native_preview.adapter(v);function=bridge.studio_gear_contact_point
        function.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int,ctypes.c_int,ctypes.c_int];function.restype=ctypes.c_char_p
        contacts=[]
        for i in range(count):
            bid=v.GetAuxiliaryGeomContactPtID(gid,i);prefix=f'ContactPt{i+1}_'
            item=dict(index=i,bogie=bid,mirrored=int(v.GetParmVal(gid,prefix+'Isymm','Design')))
            item['mirrorAvailable']=bool(v.GetParmVal(bid,'Symmetrical','Bogie')) if bid in v.GetAllBogies(parent) else False
            if item['mirrored'] and not item['mirrorAvailable']:item['warning']='The selected mirrored side is not enabled on this wheel group.'
            if bid:
                point=json.loads(function(engine,parent.encode(),bid.encode(),item['mirrored'],int(v.GetParmVal(gid,prefix+'TireMode','Design')),int(v.GetParmVal(gid,prefix+'SuspensionMode','Design'))))
                if isinstance(point,dict):item['warning']=point['error']
                else:item['point']=point
            contacts.append(item)
        result['contactPositions']=dict(frame='Native gear-local XYZ',units=int(v.GetParmVal(parent,'m_ModelLenUnits','Gear')),contacts=contacts)
    if result['clearanceFile']:
        import native_references
        points=native_references.references(v)[gid]['ccePoints']
        result['clearanceCoordinates']=dict(points=points,units=int(v.GetParmVal(gid,'CCEUnits','Design')),modelUnits=int(v.GetParmVal(parent,'m_ModelLenUnits','Gear')) if parent in v.FindGeoms() and v.GetGeomTypeName(parent).upper()=='GEAR' else None,nativeDefault=points==[[-1000.,0.,0.],[1000.,0.,0.]],exportable=len(points)>=2 and all(len(p)==3 and p[0]==0 for p in points),frame='Native envelope-local XYZ')
    if mode==v.AUX_GEOM_SUPER_CONE:
        from native_special import SHAPES
        cid=curve_container(v,gid)
        result['profile']=dict(id=cid,parameterIDs=sorted(v.FindContainerParmIDs(cid)),**curve(v,gid),shapes={n:getattr(v,n) for n in SHAPES if hasattr(v,n)})
        result['profile'].update(dimensions(v,gid))
        if result['profile']['type']==v.XS_EDIT_CURVE:
            from native_preview import editable_activity
            result['profile'].update(edit(v,gid))
            parameters=[dict(id=p,name=v.GetParmName(p)) for p in v.FindContainerParmIDs(cid)]
            from native_editable_curves import initialization_shape
            result['profile']['initShape']=initialization_shape(v,parameters)
            result['profile'].update(editable_activity(v,parameters,len(result['profile']['controlPoints'])))
            result['profile']['curveType']=int(v.GetParmVal(next(p['id'] for p in parameters if p['name']=='CurveType')))
    return result

def edit(v,gid,operation=0,argument=0,u=0):
    if curve(v,gid)['type']!=v.XS_EDIT_CURVE:raise ValueError('Convert this cone profile to an editable curve first.')
    import native_preview
    _,engine,bridge=native_preview.adapter(v);function=bridge.studio_auxiliary_edit_curve
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int,ctypes.c_int,ctypes.c_double];function.restype=ctypes.c_char_p
    data=json.loads(function(engine,gid.encode(),operation,argument,u))
    if data.get('error'):raise ValueError(data['error'])
    return data

def dimensions(v,gid):
    import native_references,native_preview
    ref=native_references.references(v)[gid];cid=ref['curveID'];shape=ref['curveType'];drivers=ref['curveDrivers']
    if shape==v.XS_POINT:return dict(drivers=[],driverControls=[],driverCombinations=[],driversFixed=True)
    _,engine,bridge=native_preview.adapter(v);function=bridge.studio_body_driver_parameters
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_bool];function.restype=ctypes.c_char_p
    ids=json.loads(function(engine,cid.encode(),shape==v.XS_CIRCLE))
    if isinstance(ids,dict):raise ValueError(ids.get('error','Native cone dimensions unavailable.'))
    circle=shape==v.XS_CIRCLE;airfoil=not circle and v.GetParmName(ids[2])=='ThickChord'
    fixed=airfoil or any(v.GetParmName(p).endswith('_Dummy') for p in ids)
    labels=['Diameter (degrees)','Area (square degrees)'] if circle else ['Width (degrees)','Area (square degrees)','Thickness / chord' if airfoil else 'Height (degrees)','Height / width']
    return dict(drivers=drivers,driverControls=[dict(value=i,label=s,parameter=p) for i,(s,p) in enumerate(zip(labels,ids))],driverCombinations=[drivers] if fixed else native_preview.body_driver_combinations(v,circle),driversFixed=fixed)

def profile_locks(v,gid):
    data=dimensions(v,gid)
    if not data['driverControls']:
        cid=curve_container(v,gid)
        return {p:'Point-profile dimensions are calculated by OpenVSP.' for p in v.FindContainerParmIDs(cid) if v.GetParmName(p) in ('Area','HWRatio')}
    return {c['parameter']:'Calculated by OpenVSP from the cone profile’s native dimension drivers.' for c in data['driverControls'] if c['value'] not in data['drivers']}

def set_drivers(v,r):
    import os,native_references
    data=dimensions(v,r['geom']);selected=r.get('drivers')
    if data['driversFixed']:raise ValueError('This native profile has fixed dimension drivers. Edit its active dimensions instead.')
    if not isinstance(selected,list) or any(type(x)!=int for x in selected) or sorted(selected) not in data['driverCombinations']:
        raise ValueError('Choose distinct cone dimension drivers supported by OpenVSP.')
    filename=v.GetVSPFileName();path,tree=native_references.document(v)
    try:
        node=next(n for n in tree.findall('.//Geom') if n.findtext('ParmContainer/ID')==r['geom'])
        node.find('Geom/Auxiliary/XSecCurve/XSecCurve/XSecCurveDriverGroup/ChoiceVec').text=', '.join(str(x) for x in selected)+', '
        tree.write(path,encoding='utf-8',xml_declaration=True);os.replace(path,filename)
    finally:path.unlink(missing_ok=True)
    raise native_references.ReloadRequired()

def mutate(v,r):
    from native_tools import one
    gid=r['geom'];current=curve(v,gid)['type']
    from native_editable_curves import guard_container_shape_replacement
    def protect(target):guard_container_shape_replacement(v,curve_container(v,gid),current,target)
    if r['operation'].startswith('auxiliary-profile-edit-'):
        from native_region_curves import mutate_edit_native
        from native_tools import finite
        from native_preview import parameter_activity
        cid=curve_container(v,gid);parms={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)}
        before=edit(v,gid);op=r['operation'].replace('auxiliary-profile-edit-','region-curve-')
        index=r.get('point')
        if op in ('region-curve-point','region-curve-fixed','region-curve-smooth'):
            if type(index)!=int or not 0<=index<len(before['controlPoints']):raise ValueError('Choose an existing curve point.')
            if op=='region-curve-point':
                xyz=r.get('xyz')
                if not isinstance(xyz,list) or len(xyz)!=3:raise ValueError('Enter three coordinates.')
                updates=[(parms[f'{axis}_{index}'],finite(x)) for axis,x in zip('XYZ',xyz)]
            else:
                key='fixed' if op=='region-curve-fixed' else 'smooth'
                if type(r.get(key))!=bool:raise ValueError('Choose whether this curve constraint is enabled.')
                updates=[(parms[f'FixedU_{index}' if key=='fixed' else f'G1_{index}'],int(r[key]))]
            activity=parameter_activity(v,[p for p,_ in updates])
            for pid,value in updates:
                if not activity[pid] and value!=v.GetParmVal(pid):raise ValueError('This curve coordinate or constraint is locked by OpenVSP.')
                if not v.GetParmLowerLimit(pid)<=value<=v.GetParmUpperLimit(pid):raise ValueError('Use a value within the native parameter limits.')
        mutate_edit_native(v,{**r,'operation':op},cid,lambda operation=0,argument=0,u=0:edit(v,gid,operation,argument,u))
    elif r['operation']=='auxiliary-profile-drivers':set_drivers(v,r)
    elif r['operation']=='auxiliary-profile-shape':
        from native_special import SHAPES
        shape=one(r['shape'],SHAPES,'Choose a native profile family.');protect(getattr(v,shape));curve(v,gid,1,getattr(v,shape))
    elif r['operation']=='auxiliary-profile-copy':
        source=r['source']
        if not isinstance(source,dict):
            source=one(source,v.FindGeoms(),'Choose an existing source component.')
            if v.GetGeomTypeName(source).upper()=='AUXILIARY':source=dict(kind='auxiliary',geom=source)
            else:
                if not v.GetNumXSecSurfs(source):raise ValueError('Choose a source with ordinary sections or a Super cone profile.')
                i=one(r.get('index',1),range(v.GetNumXSec(v.GetXSecSurf(source,0))),'Choose an existing source section.')
                source=dict(kind='section',geom=source,surface=0,index=i)
        import native_bor_clipboard
        from native_curve_copy_points import capture,restore
        payload=capture(v,source)
        native_bor_clipboard.copy(v,source);curve(v,gid,3)
        if payload is not None:
            restore(v,curve_container(v,gid),payload);edit(v,gid)
    elif r['operation']=='auxiliary-profile-import':
        from native_region_curves import import_profile
        fmt=one(r.get('format'),('airfoil','section'))
        protect(v.XS_FILE_AIRFOIL if fmt=='airfoil' else v.XS_FILE_FUSE)
        import_profile(v,r);curve(v,gid,3)
    elif r['operation']=='auxiliary-profile-convert':
        protect(v.XS_EDIT_CURVE);curve(v,gid,4)
    else:raise ValueError('Unknown auxiliary profile operation.')
    v.Update()
