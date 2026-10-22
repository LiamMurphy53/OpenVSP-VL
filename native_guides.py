"""Human-readable setup for official analyses; all calculations remain native."""
import native_managers
import json
import math
import shutil
from pathlib import Path

NAMES={'MassProp','PlanarSlice','Projection','WaveDrag','ParasiteDrag','BladeElement','CompGeom'}
DEFINITIONS={
 'CompGeom':('Component areas and volumes','OpenVSP intersects and trims component meshes to compute exposed wetted areas and combined volumes. Untrimmed values describe each original component; trimmed values describe its contribution after intersections. Areas use square model units and volumes use cubic model units.',[
  ('Geometry',['UseModeFlag','ModeID','Set','DegenSet']),('Native mesh handling',['HalfMeshFlag','SubSurfFlag']),('Native reports',['WriteTXTFlag','WriteCSVFlag'])]),
 'MassProp':('Mass properties','OpenVSP computes volume, mass, center of gravity and inertia using the aircraft’s native density, shell and point-mass settings.',[
  ('Geometry',['UseModeFlag','ModeID','Set','DegenSet']),('Integration',['NumMassSlices','MassSliceDir'])]),
 'PlanarSlice':('Cross-sectional areas','OpenVSP intersects the aircraft with parallel planes. Automatic limits come from the selected geometry; manual limits are coordinates along the normalized slice direction.',[
  ('Geometry',['UseModeFlag','ModeID','Set']),('Slice planes',['Norm','NumSlices','AutoBoundFlag','StartVal','EndVal','MeasureDuct'])]),
 'Projection':('Projected area','OpenVSP projects the target and can clip it against a projected boundary. Individual component areas can overlap; the combined area is the native union.',[
  ('Target',['TargetType','TargetSet','TargetGeomID','TargetModeID','TargetHullFlag']),('Direction',['DirectionType','Direction','DirectionGeomID']),('Boundary',['BoundaryType','BoundarySet','BoundaryGeomID','BoundaryHullFlag','DiskSegmentBreakdown'])]),
 'WaveDrag':('Wave drag','OpenVSP performs its supersonic area-rule calculation. Review reference area, Mach number, axial slices, cone sections and propulsive faces.',[
  ('Geometry',['UseModeFlag','ModeID','Set','SSFlow_vec']),('Supersonic slicing',['Mach','NumSlices','NumRotSects','SymmFlag'])]),
 'ParasiteDrag':('Parasite drag buildup','OpenVSP computes the atmosphere, Reynolds numbers, friction and form-factor buildup. Model length units, airspeed units and reference area must describe the same aircraft and flight condition.',[
  ('Geometry',['UseModeFlag','ModeID','GeomSet','RecomputeGeom']),('Reference and units',['RefFlag','WingID','Sref','LengthUnit','VelocityUnit','AltLengthUnit','TempUnit','PresUnit']),('Flight condition',['FreestreamPropChoice','Altitude','DeltaTemp','Vinf','Mach','Temperature','Pressure','Density','DynaVisc','KineVisc','Re_L','SpecificHeatRatio']),('Friction and export',['LamCfEqnChoice','TurbCfEqnChoice','ExportSubCompFlag','FileName'])])}
LABELS={'Set':'Geometry set','GeomSet':'Geometry set','DegenSet':'Degenerate geometry set','UseModeFlag':'Geometry selection','ModeID':'Native mode','NumMassSlices':'Mass integration slices','MassSliceDir':'Mass slicing direction','NumSlices':'Number of slices','Norm':'Slice-plane normal','AutoBoundFlag':'Slice limits','StartVal':'Start coordinate','EndVal':'End coordinate','MeasureDuct':'Measure ducts','TargetType':'Target selection','TargetSet':'Target set','TargetGeomID':'Target component','TargetModeID':'Target mode','TargetHullFlag':'Target convex hull','DirectionType':'Projection direction','Direction':'Custom projection vector','DirectionGeomID':'Direction component','BoundaryType':'Clipping boundary','BoundarySet':'Boundary set','BoundaryGeomID':'Boundary component','BoundaryHullFlag':'Boundary convex hull','DiskSegmentBreakdown':'Disk segment breakdown','Mach':'Mach number','NumRotSects':'Cone sections','SSFlow_vec':'Propulsive face regions','SymmFlag':'Slicing symmetry','RecomputeGeom':'Refresh native geometry','RefFlag':'Reference area source','WingID':'Reference wing','Sref':'Reference area','LengthUnit':'Model length unit','VelocityUnit':'Airspeed unit','AltLengthUnit':'Altitude unit','TempUnit':'Temperature unit','PresUnit':'Pressure unit','FreestreamPropChoice':'Atmosphere / supplied properties','Altitude':'Altitude','DeltaTemp':'Temperature offset','Vinf':'Airspeed','DynaVisc':'Dynamic viscosity','KineVisc':'Kinematic viscosity','Re_L':'Reynolds number per unit length','SpecificHeatRatio':'Specific heat ratio','LamCfEqnChoice':'Laminar friction method','TurbCfEqnChoice':'Turbulent friction method','ExportSubCompFlag':'Component detail in export','FileName':'Native CSV filename'}


def choices(v,pairs):return [dict(value=getattr(v,n),label=label) for n,label in pairs if hasattr(v,n)]


def annotate(v,name,inputs):
    if name in ('CpSlicer','VSPAEROReadPreviousAnalysis'):
        if name=='CpSlicer':
            for e in inputs:
                e['label']={'XSlicePosVec':'X slice positions','YSlicePosVec':'Y slice positions','ZSlicePosVec':'Z slice positions'}[e['name']]
                e['numericList']=True
                e['description']='Coordinates in the saved solution’s model units. Separate positions with commas or spaces; leave unused directions empty.'
        return dict(guide=dict(title='Pressure slices from a saved solution' if name=='CpSlicer' else 'Reopen saved aerodynamic results',note='Choose a completed aerodynamic solution. OpenVSP reads a copy of its saved aircraft and native result files. The current aircraft and original solution remain unchanged.'+(' Enter slice-plane coordinates along one or more axes. OpenVSP reports Cp or delta Cp according to the saved native surface model.' if name=='CpSlicer' else ' This operation reads existing histories, loads, polars and rotor records; it does not run the solver again.'),sensitivityNote='The saved solution retains its original numerical resolution and convergence limits.',sections=[dict(title='Native slice planes',inputs=[e['name'] for e in inputs])] if inputs else []))
    if name=='GeometryAnalysis':
        import native_geometry_cases
        return native_geometry_cases.annotate(v,inputs)
    if name=='SurfacePatches':
        import native_surface_patches
        return native_surface_patches.annotate(v,inputs)
    if name in ('DegenGeom','DegenGeomMesh'):
        import native_degenerate
        return native_degenerate.annotate(v,name,inputs)
    if name=='EmintonLord':
        for e in inputs:
            e['label']={'X_vec':'Longitudinal stations','Area_vec':'Cross-sectional areas'}[e['name']]
            e['description']='Enter matching lists with at least three samples. Stations must increase strictly; areas must be nonnegative. Use consistent model length and square-length units.'
        return dict(guide=dict(title='Area-distribution wave drag',note='OpenVSP performs the Eminton–Lord integration on your supplied station and area samples. Drag area is the native Donq result; Coeff contains the native integration coefficients, not an aircraft drag coefficient.',sensitivityNote='Compare distributions with additional measured samples to assess sensitivity. This calculation uses the entered distribution rather than sampling the aircraft.',sections=[dict(title='Paired area samples',inputs=['X_vec','Area_vec'])]))
    if name=='BladeElement':
        props=[dict(value=g,label=v.GetGeomName(g)) for g in v.FindGeoms() if v.GetGeomTypeName(g).upper() in ('PROP','PROPELLER')]
        for e in inputs:
            e['label']={'PropID':'Propeller','ExportBEMFlag':'Write blade-element file','BEMFileName':'BEM filename'}[e['name']]
            if e['name']=='PropID':
                e['choices']=[dict(value='',label='Choose a propeller…'),*props]
                if e['values'][0] and e['values'][0] not in [p['value'] for p in props]:e['choices'].append(dict(value=e['values'][0],label='Unavailable native propeller · '+e['values'][0]))
            if e['name']=='ExportBEMFlag':e['choices']=[dict(value=0,label='Results only'),dict(value=1,label='Results and BEM file')]
            if e['name']=='BEMFileName':
                e['applicableWhen']=dict(input='ExportBEMFlag',values=[1]);e['displayValue']=Path(e['values'][0]).name
        return dict(guide=dict(title='Propeller blade elements',note='OpenVSP samples the selected propeller’s radial geometry and airfoil sections. These are geometry data, not a thrust or power prediction. Edit the propeller in Modeling tools before creating another saved run.',sensitivityNote='Compare native section counts and saved geometry samples when assessing discretization.',sections=[dict(title='Propeller and export',inputs=['PropID','ExportBEMFlag','BEMFileName'])]))
    if name=='FlowPlaneSlicer':
        import native_flow_slices
        return native_flow_slices.validate(v,schema)
    if name in ('VSPAEROSweep','VSPAEROComputeGeometry'):
        import native_aero_guides
        return native_aero_guides.annotate(v,inputs,geometry=name=='VSPAEROComputeGeometry')
    if name=='CfdMeshAnalysis':
        import native_cfd_guides
        return native_cfd_guides.annotate(v,inputs)
    if name=='SurfaceIntersection':
        import native_intersections
        return native_intersections.annotate(v,inputs)
    if name not in NAMES:return {}
    title,note,sections=DEFINITIONS[name];maps={
     'MassSliceDir':choices(v,[('X_DIR','X · longitudinal'),('Y_DIR','Y · spanwise'),('Z_DIR','Z · vertical')]),
     'TargetType':choices(v,[('SET_TARGET','Geometry set'),('GEOM_TARGET','One component'),('MODE_TARGET','Native mode')]),
     'BoundaryType':choices(v,[('NO_BOUNDARY','No clipping boundary'),('SET_BOUNDARY','Geometry set'),('GEOM_BOUNDARY','One component')]),
     'DirectionType':choices(v,[('X_PROJ','X · front'),('Y_PROJ','Y · side'),('Z_PROJ','Z · top'),('GEOM_PROJ','Component direction'),('VEC_PROJ','Custom vector')]),
     'FreestreamPropChoice':choices(v,[('ATMOS_TYPE_US_STANDARD_1976','US Standard Atmosphere 1976'),('ATMOS_TYPE_HERRINGTON_1966','Herrington 1966'),('ATMOS_TYPE_MANUAL_P_R','Supplied pressure and density'),('ATMOS_TYPE_MANUAL_P_T','Supplied pressure and temperature'),('ATMOS_TYPE_MANUAL_R_T','Supplied density and temperature'),('ATMOS_TYPE_MANUAL_RE_L','Supplied Reynolds number per length')]),
     'LengthUnit':choices(v,[('LEN_MM','mm'),('LEN_CM','cm'),('LEN_M','m'),('LEN_IN','in'),('LEN_FT','ft'),('LEN_YD','yd'),('LEN_UNITLESS','Unitless')]),
     'VelocityUnit':choices(v,[('V_UNIT_FT_S','ft/s'),('V_UNIT_M_S','m/s'),('V_UNIT_MPH','mph'),('V_UNIT_KM_HR','km/h'),('V_UNIT_KEAS','knots · equivalent'),('V_UNIT_KTAS','knots · true'),('V_UNIT_MACH','Mach')]),
     'TempUnit':choices(v,[('TEMP_UNIT_K','K'),('TEMP_UNIT_C','°C'),('TEMP_UNIT_F','°F'),('TEMP_UNIT_R','°R')]),
     'AltLengthUnit':choices(v,[('PD_UNITS_IMPERIAL','ft'),('PD_UNITS_METRIC','m')]),
     'PresUnit':choices(v,[(n,label) for n,label in [('PRES_UNIT_PSF','lbf/ft²'),('PRES_UNIT_PSI','psi'),('PRES_UNIT_BA','barye'),('PRES_UNIT_PA','Pa'),('PRES_UNIT_KPA','kPa'),('PRES_UNIT_MPA','MPa'),('PRES_UNIT_INCHHG','inHg'),('PRES_UNIT_MMHG','mmHg'),('PRES_UNIT_MMH20','mmH₂O'),('PRES_UNIT_MB','mbar'),('PRES_UNIT_ATM','atm')]]),
     'LamCfEqnChoice':choices(v,[('CF_LAM_BLASIUS','Blasius'),('CF_LAM_BLASIUS_W_HEAT','Blasius with heat transfer')]),
     'TurbCfEqnChoice':choices(v,[(n,n.removeprefix('CF_TURB_').replace('_',' ').title()) for n in dir(v) if n.startswith('CF_TURB_')])}
    for key in ['MeasureDuct','TargetHullFlag','BoundaryHullFlag','DiskSegmentBreakdown','SymmFlag','RecomputeGeom','ExportSubCompFlag']:maps[key]=[dict(value=0,label='Off'),dict(value=1,label='On')]
    maps['HalfMeshFlag']=[dict(value=0,label='Whole selected geometry'),dict(value=1,label='Positive-Y half (Y ≥ 0)')]
    maps['SubSurfFlag']=[dict(value=0,label='Ignore surface regions'),dict(value=1,label='Include surface regions')]
    for key in ('WriteTXTFlag','WriteCSVFlag'):maps[key]=[dict(value=0,label='Off'),dict(value=1,label='Save native report with this run')]
    maps['UseModeFlag']=[dict(value=0,label='Geometry sets'),dict(value=1,label='Native mode')]
    maps['AutoBoundFlag']=[dict(value=1,label='Automatic native bounds'),dict(value=0,label='Manual start / end')]
    maps['RefFlag']=[dict(value=0,label='Entered reference area'),dict(value=1,label='Native wing area')]
    modes=[dict(value='',label='Choose a mode…'),*[dict(value=m,label=v.GetModeName(m)) for m in v.GetAllModes()]]
    maps['ModeID']=modes;maps['TargetModeID']=modes
    for key in ['TargetGeomID','BoundaryGeomID','DirectionGeomID']:maps[key]=[dict(value='',label='Choose a component…'),*[dict(value=g,label=v.GetGeomName(g)) for g in v.FindGeoms()]]
    maps['WingID']=[dict(value='',label='Choose a wing…'),*[dict(value=g,label=v.GetGeomName(g)) for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='WING']]
    owners={'MassProp':('Vehicle',{'NumMassSlices':'NumMassSlices'}),'PlanarSlice':('Vehicle',{'NumSlices':'NumPlanerSlices','StartVal':'PlanarStartLocation','EndVal':'PlanarEndLocation'}),'WaveDrag':('WaveDragSettings',{'NumSlices':'NumSlices','NumRotSects':'NumRotSects','Mach':'MachNumber'}),'ParasiteDrag':('ParasiteDragSettings',{'Sref':'Sref','Altitude':'Alt','Vinf':'Vinf','Temperature':'Temp','Pressure':'Pres','Density':'Density','DynaVisc':'DynaVisc','DeltaTemp':'DeltaTemp','SpecificHeatRatio':'SpecificHeatRatio','Re_L':'Re_L'})}
    native_limits={}
    if name in owners:
        owner,mapping=owners[name]
        c=native_managers.manager(v,owner)
        group={'MassProp':'MassProperties','PlanarSlice':'PSlice','WaveDrag':'WaveDrag','ParasiteDrag':'ParasiteDrag'}[name]
        for key,pn in mapping.items():
            pid=v.FindParm(c,pn,group)
            if pid:native_limits[key]=(v.GetParmLowerLimit(pid),v.GetParmUpperLimit(pid))
    applicable={}
    def when(key,controller,values):applicable[key]=dict(input=controller,values=values)
    if name!='Projection':
        when('ModeID','UseModeFlag',[1])
        for key in ('Set','GeomSet','DegenSet'):when(key,'UseModeFlag',[0])
    if name=='PlanarSlice':
        for key in ('StartVal','EndVal'):when(key,'AutoBoundFlag',[0])
    if name=='Projection':
        for key,controller,values in [('TargetSet','TargetType',[v.SET_TARGET]),('TargetGeomID','TargetType',[v.GEOM_TARGET]),('TargetModeID','TargetType',[v.MODE_TARGET]),('BoundarySet','BoundaryType',[v.SET_BOUNDARY]),('BoundaryGeomID','BoundaryType',[v.GEOM_BOUNDARY]),('BoundaryHullFlag','BoundaryType',[v.SET_BOUNDARY,v.GEOM_BOUNDARY]),('Direction','DirectionType',[v.VEC_PROJ]),('DirectionGeomID','DirectionType',[v.GEOM_PROJ])]:when(key,controller,values)
    if name=='ParasiteDrag':
        when('WingID','RefFlag',[1]);when('Sref','RefFlag',[0])
        standard=[v.ATMOS_TYPE_US_STANDARD_1976,v.ATMOS_TYPE_HERRINGTON_1966]
        manual=[v.ATMOS_TYPE_MANUAL_P_R,v.ATMOS_TYPE_MANUAL_P_T,v.ATMOS_TYPE_MANUAL_R_T]
        for key in ('Altitude','DeltaTemp'):when(key,'FreestreamPropChoice',standard)
        for key in ('Vinf','VelocityUnit'):when(key,'FreestreamPropChoice',standard+manual)
        when('Temperature','FreestreamPropChoice',[v.ATMOS_TYPE_MANUAL_P_T,v.ATMOS_TYPE_MANUAL_R_T])
        when('Pressure','FreestreamPropChoice',[v.ATMOS_TYPE_MANUAL_P_R,v.ATMOS_TYPE_MANUAL_P_T])
        when('Density','FreestreamPropChoice',[v.ATMOS_TYPE_MANUAL_P_R,v.ATMOS_TYPE_MANUAL_R_T])
        for key in ('Mach','Re_L'):when(key,'FreestreamPropChoice',[v.ATMOS_TYPE_MANUAL_RE_L])
        # Native UpdateParmActivity also enables gamma for these two methods.
        applicable['SpecificHeatRatio']=dict(any=[dict(input='FreestreamPropChoice',values=manual+[v.ATMOS_TYPE_MANUAL_RE_L]),dict(input='TurbCfEqnChoice',values=[v.CF_TURB_ROUGHNESS_SCHLICHTING_AVG_FLOW_CORRECTION,v.CF_TURB_HEATTRANSFER_WHITE_CHRISTOPH])])
    for e in inputs:
        key=e['name'];e['label']=LABELS.get(key,key)
        if name=='CompGeom':
            e['label']={'Set':'Normal geometry set','DegenSet':'Degenerate geometry set','HalfMeshFlag':'Geometry half','SubSurfFlag':'Surface regions','WriteTXTFlag':'Native text report','WriteCSVFlag':'Native CSV report'}.get(key,e['label'])
            if key=='DegenSet':
                e['editable']=False;e['displayReadOnly']=True
                e['description']='OpenVSP 3.52.2 ignores this registered input. To include degenerate geometry, choose a native mode with a degenerate set configured in Modeling tools → Modes.'
        if key in applicable:e['applicableWhen']=applicable[key]
        if name=='ParasiteDrag' and key in ('DynaVisc','KineVisc'):
            e['displayReadOnly']=True
            e['description']='Computed by OpenVSP from the selected atmosphere. Current aircraft value; the saved run reports the value actually used.'
        if key in maps:
            e['choices']=list(maps[key])
            if e['type']==v.STRING_DATA and e['values'][0] not in [c['value'] for c in e['choices']]:e['choices'].append(dict(value=e['values'][0],label='Unavailable native reference · '+e['values'][0]))
        if key in native_limits:e['min'],e['max']=native_limits[key]
        if key in ('Norm','Direction'):e['vectorCoordinates']=True
        if key=='SSFlow_vec':e['choiceList']=[dict(value=s,label=v.GetGeomName(g)+' · '+v.GetSubSurfName(s)) for g in v.FindGeoms() for s in v.GetSubSurfIDVec(g)]
        if key=='FileName':e['displayValue']=Path(e['values'][0]).name
    guide=dict(title=title,note=note,sections=[dict(title=t,inputs=keys) for t,keys in sections])
    if name=='CompGeom':guide['sensitivityNote']='Compare native geometry tessellation and review merged, removed and degenerate mesh diagnostics. The saved mesh is the native trimmed component mesh, not a CFD-quality mesh. For degenerate geometry, use a native mode; this release ignores the separate degenerate-set input.'
    if name=='WaveDrag':
        cid=native_managers.manager(v,'WaveDragSettings');pid=v.FindParm(cid,'Sref','WaveDrag');ref=v.FindParm(cid,'RefFlag','WaveDrag')
        guide['reference']=dict(parameter=pid,value=v.GetParmVal(pid),source=int(v.GetParmVal(ref)),min=v.GetParmLowerLimit(pid),max=v.GetParmUpperLimit(pid),wings=[dict(id=g,name=v.GetGeomName(g),area=v.GetParmVal(v.FindParm(g,'TotalArea','WingGeom'))) for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='WING'])
    if name=='Projection':
        from native_saved_analysis_controls import projection_options
        guide['savedProjectionOptions']=projection_options(v)
    if name=='MassProp':
        guide['massComponents']=[dict(id=g,name=v.GetGeomName(g),settings=[dict(id=p,name=v.GetParmName(p),value=v.GetParmVal(p)) for p in v.GetGeomParmIDs(g) if v.GetParmGroupName(p)=='Mass_Props']) for g in v.FindGeoms()]
    return dict(guide=guide)


def validate(v,name,schema):
    if name=='CpSlicer':
        values=[x for e in schema['inputs'] for x in e['values']]
        if not values:raise ValueError('Enter at least one slice position along X, Y or Z.')
        if any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) for x in values):raise ValueError('Enter finite slice positions in the saved solution’s model units.')
        return
    if name=='GeometryAnalysis':
        import native_geometry_cases
        return native_geometry_cases.validate(v,schema)
    if name=='SurfacePatches':
        import native_surface_patches
        return native_surface_patches.validate(v,schema)
    if name in ('DegenGeom','DegenGeomMesh'):
        import native_degenerate
        return native_degenerate.validate(v,name,schema)
    if name=='EmintonLord':
        fields={e['name']:e['values'] for e in schema['inputs']}
        x,area=fields['X_vec'],fields['Area_vec']
        if len(x)!=len(area) or len(x)<3:raise ValueError('Enter matching station and area lists with at least three samples.')
        if any(not math.isfinite(t) for t in x+area):raise ValueError('Enter finite station and area samples.')
        if any(b<=a for a,b in zip(x,x[1:])):raise ValueError('Longitudinal stations must increase strictly; remove repeated or reversed stations.')
        if any(a<0 for a in area):raise ValueError('Cross-sectional areas must be nonnegative.')
        return
    if name=='BladeElement':
        fields={e['name']:e['values'] for e in schema['inputs']}
        if any(len(x)!=1 for x in fields.values()):raise ValueError('Blade elements require one propeller and one export setting.')
        if fields['PropID'][0] not in [g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper() in ('PROP','PROPELLER')]:raise ValueError('Choose an existing native propeller for blade elements.')
        if fields['ExportBEMFlag'][0] not in (0,1):raise ValueError('Choose results only or results and a BEM file.')
        return
    if name in ('VSPAEROSweep','VSPAEROComputeGeometry'):
        import native_aero_guides
        return native_aero_guides.validate(v,schema)
    if name=='CfdMeshAnalysis':
        import native_cfd_guides
        return native_cfd_guides.validate(v,schema)
    if name=='SurfaceIntersection':
        import native_intersections
        return native_intersections.validate(v,schema)
    if name not in NAMES:return
    fields={e['name']:e for e in schema['inputs']}
    def value(key):
        values=fields[key]['values']
        if len(values)!=1:raise ValueError(key+': enter one value.')
        return values[0]
    for key,e in fields.items():
        if key=='SSFlow_vec':
            known={s for g in v.FindGeoms() for s in v.GetSubSurfIDVec(g)}
            if any(s not in known for s in e['values']):raise ValueError('Choose existing propulsive face regions.')
            continue
        x=value(key)
        if 'choices' in e and x not in [c['value'] for c in e['choices']]:raise ValueError(e.get('label',key)+': choose a supported native option.')
        if isinstance(x,(int,float)) and ('min' in e and x<e['min'] or 'max' in e and x>e['max']):raise ValueError(e.get('label',key)+': value is outside the native setting limits.')
    def set_exists(key):
        index=value(key)
        if index not in range(v.GetNumSets()) or not v.GetGeomSetAtIndex(index):raise ValueError(fields[key].get('label',key)+': choose a set containing geometry.')
    if name in ('MassProp','CompGeom','PlanarSlice','WaveDrag','ParasiteDrag'):
        if value('UseModeFlag'):
            m=value('ModeID')
            if m not in v.GetAllModes():raise ValueError('Choose an existing native mode.')
            # The native mode applies its presets during execution; those can
            # change its selected sets. Do not substitute a pre-apply result.
        elif name!='MassProp':set_exists('GeomSet' if name=='ParasiteDrag' else 'Set')
    if name=='CompGeom' and not value('UseModeFlag') and value('DegenSet')!=-1:
        raise ValueError('OpenVSP 3.52.2 ignores the separate degenerate-set input for component analysis. Choose a native mode with the desired degenerate set instead.')
    if name=='MassProp' and not value('UseModeFlag'):
        selected=[value('Set'),value('DegenSet')]
        if any(x not in range(-1,v.GetNumSets()) for x in selected) or not any(x>=0 and v.GetGeomSetAtIndex(x) for x in selected):raise ValueError('Choose a normal or degenerate set containing geometry.')
    if name=='MassProp' and not value('UseModeFlag') and value('DegenSet')!=-1:set_exists('DegenSet')
    if name=='PlanarSlice':
        if not any(value('Norm')):raise ValueError('Enter a nonzero slice-plane normal.')
        if not value('AutoBoundFlag') and value('StartVal')>=value('EndVal'):raise ValueError('The ending slice coordinate must follow the starting coordinate.')
    if name=='WaveDrag' and value('Mach')<=1:raise ValueError('Wave drag requires a supersonic Mach number greater than 1.')
    if name=='Projection':
        if value('TargetType')==v.SET_TARGET:set_exists('TargetSet')
        elif value('TargetType')==v.GEOM_TARGET:
            if value('TargetGeomID') not in v.FindGeoms():raise ValueError('Choose a target component.')
        elif value('TargetModeID') not in v.GetAllModes():raise ValueError('Choose a target mode.')
        if value('BoundaryType')==v.SET_BOUNDARY:set_exists('BoundarySet')
        elif value('BoundaryType')==v.GEOM_BOUNDARY and value('BoundaryGeomID') not in v.FindGeoms():raise ValueError('Choose a boundary component.')
        if value('DirectionType')==v.GEOM_PROJ and value('DirectionGeomID') not in v.FindGeoms():raise ValueError('Choose a direction component.')
        if value('DirectionType')==v.VEC_PROJ and not any(value('Direction')):raise ValueError('Enter a nonzero projection vector.')
    if name=='ParasiteDrag':
        if value('RefFlag') and value('WingID') not in [g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='WING']:raise ValueError('Choose a reference wing.')
        if not value('RefFlag') and value('Sref')<=0:raise ValueError('Enter a positive reference area.')
        if value('FreestreamPropChoice')==v.ATMOS_TYPE_MANUAL_RE_L and value('Re_L')<=0:raise ValueError('Enter a positive Reynolds number per unit length.')


def set_reference(v,r):
    from native_tools import finite,one
    if r['analysis']!='WaveDrag':raise ValueError('Choose the native wave-drag reference settings.')
    c=native_managers.manager(v,'WaveDragSettings');p=v.FindParm(c,'Sref','WaveDrag')
    if r.get('wing'):
        g=one(r['wing'],[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='WING'])
        area=v.GetParmVal(v.FindParm(g,'TotalArea','WingGeom'))
    else:area=finite(r['value'])
    if not v.GetParmLowerLimit(p)<=area<=v.GetParmUpperLimit(p):raise ValueError('Reference area is outside the native limits.')
    v.SetParmValUpdate(v.FindParm(c,'RefFlag','WaveDrag'),0);v.SetParmValUpdate(p,area)


def preview(results,name):
    """Encode exact native point/outline outputs for the existing viewer."""
    if name=='GeometryAnalysis':return gear_case_preview(results)
    result_name={'MassProp':'Mass_Properties','PlanarSlice':'Slice','Projection':'Projection'}.get(name)
    r=next((r for r in results if r['name']==result_name),None)
    if not r:return None
    nodes=[];elements=[];groups=[]
    def add(label,points,kind='point'):
        if not points:return
        if any(not isinstance(p,list) or len(p)!=3 or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in p) for p in points):return
        group=len(groups)+1;offset=len(nodes);nodes.extend(points)
        indices=[[offset+i] for i in range(len(points))] if kind=='point' else [[offset+i,offset+i+1] for i in range(len(points)-1)]
        first=len(elements)
        elements.extend(dict(id=first+i+1,type='native result '+kind,kind=kind,group=group,nodes=row) for i,row in enumerate(indices))
        groups.append(dict(id=group,name=label,count=len(indices)))
    def values(key):return next((e['values'] for e in r['entries'] if e['name']==key),[])
    if name=='MassProp':
        for label,p in zip(values('Comp_Name'),values('Comp_CG')):add(label+' · CG',[p])
        add('Total center of gravity',values('Total_CG'))
    elif name=='PlanarSlice':add('Native area centroids',values('Slice_Area_Center'))
    else:
        for e in r['entries']:
            if e['name']=='Path':add('Native outline '+str(e['index']+1),e['values'],'line')
    if not nodes or not elements:return None
    return dict(filename='Native '+result_name,nodes=nodes,nodeIDs=list(range(1,len(nodes)+1)),elements=elements,groups=groups,totalElements=len(elements),geometryPreview=True,displayNote='Coordinates are the exact saved native result samples. Mass markers are centers of gravity; slice markers are area centroids; projection lines are native boundary paths. No surface or volume is reconstructed from these markers.')


def gear_case_preview(results):
    """Original GeometryAnalysisCase draws these Pts as VSP_LINES pairs."""
    nodes=[];elements=[];groups=[]
    for r in results:
        if r['name'] not in ('Gear_CG_Tipback','Gear_Tipover','Gear_Turn'):continue
        for e in r['entries']:
            if e['name']!='Pts' or not e['values']:continue
            points=e['values']
            if len(points)%2 or any(not isinstance(p,list) or len(p)!=3 or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in p) for p in points):
                raise ValueError('OpenVSP returned an undefined landing-gear drawing. Review the contacts, CG and steering settings.')
            offset=len(nodes);group=len(groups)+1;nodes.extend(points)
            for i in range(0,len(points),2):elements.append(dict(id=len(elements)+1,type='native gear check line',kind='line',group=group,nodes=[offset+i,offset+i+1]))
            groups.append(dict(id=group,name=r['description']+' · '+e['description'],count=len(points)//2))
    if not elements:return None
    return dict(filename='Native landing-gear check',nodes=nodes,nodeIDs=list(range(1,len(nodes)+1)),elements=elements,groups=groups,totalElements=len(elements),geometryPreview=True,displayNote='These are OpenVSP’s exact saved line pairs for the gear check. Tipback and tipover show native CG/contact construction lines; turning checks show the native rotation axis and swept circles. Coordinates preserve the native result frame.')


def save_preview(v,data,name):
    if name=='SurfacePatches':
        import native_surface_patches
        return native_surface_patches.save(data)
    if name in ('DegenGeom','DegenGeomMesh'):
        import native_degenerate
        return native_degenerate.save(v,data,name)
    if name=='CompGeom':
        # Export only the MeshGeom returned by this native run. Temporary set
        # selection is restored, including preexisting members and its name.
        import native_mesh
        result=next(r for r in data['results'] if r['name']=='Comp_Geom')
        ids=next(e['values'] for e in result['entries'] if e['name']=='Mesh_GeomID')
        slot=v.GetNumSets()-1;members={g:v.GetSetFlag(g,slot) for g in v.FindGeoms()}
        try:
            for g in members:v.SetSetFlag(g,slot,g in ids)
            filename='component-geometry.msh';v.ExportFile(str(Path.cwd()/filename),slot,v.EXPORT_GMSH,1)
            from native_worker import errors
            errors(v)
            mesh=native_mesh.read_gmsh(Path.cwd()/filename)
            data['meshFile']=filename;data['meshSummary']=native_mesh.summary(mesh)
        finally:
            for g,flag in members.items():v.SetSetFlag(g,slot,flag)
        import native_ngon
        model_file='component-mesh.vsp3';native_ngon.write(v,Path.cwd()/model_file)
        data['componentMeshModel']=dict(file=model_file,geometryIDs=ids,triangleMetadata=all(g in getattr(v,'_studio_mesh_tag_data',{}) for g in ids))
    if name=='ParasiteDrag':
        requested=Path(next(e['values'][0] for e in data['inputs'] if e['name']=='FileName'))
        # ComputeBuildUp refreshes native default filenames while rebuilding
        # geometry, overriding the analysis FileName input in this version.
        # Preserve its bytes and record that native source when copying to the
        # requested run-local name; no result values or CSV contents are edited.
        if requested.is_file():source=requested
        else:
            candidates=list(Path.cwd().glob('*_ParasiteBuildUp.csv'))
            if len(candidates)!=1:raise ValueError('The native parasite-drag CSV output is missing or ambiguous.')
            source=candidates[0];shutil.copy2(source,requested)
        data['csvFile']=requested.name;data['nativeCSVSource']=source.name
    if name=='WaveDrag':
        c=native_managers.manager(v,'WaveDragSettings')
        data['guideSettings']={n:v.GetParmVal(v.FindParm(c,n,'WaveDrag')) for n in ('Sref','RefFlag')}
        import native_wave_references
        native_wave_references.save(v,data)
        import native_wave_drawings
        native_wave_drawings.save(v,data)
    geometry=preview(data['results'],name)
    if geometry:
        filename='analysis-geometry.guide.json';Path(filename).write_text(json.dumps(geometry,allow_nan=False));data['guideFile']=filename
    return data


def configure_output(v,name):
    if name=='BladeElement' and v.GetIntAnalysisInput(name,'ExportBEMFlag')[0]:
        filename=Path(v.GetStringAnalysisInput(name,'BEMFileName')[0]).name
        if not filename or filename in ('.','..') or '\\' in filename or '\x00' in filename:raise ValueError('Choose a BEM filename for this run.')
        v.SetStringAnalysisInput(name,'BEMFileName',[str(Path.cwd()/filename)])
    if name=='ParasiteDrag':
        filename=Path(v.GetStringAnalysisInput(name,'FileName')[0]).name
        if not filename or filename in ('.','..') or '\\' in filename or '\x00' in filename:raise ValueError('Choose a CSV filename for this run.')
        # Saved native files may contain a previous absolute export location.
        # Each analysis retains its own output in its isolated run directory.
        v.SetStringAnalysisInput(name,'FileName',[str(Path.cwd()/filename)])
