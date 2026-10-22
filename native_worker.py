"""Execute a single transaction using unmodified OpenVSP, in a separate process."""
import native_ngon
import json
import math
from pathlib import Path
import sys
from vsp_runtime import load
import native_tools
import native_analytical
import native_mesh
import native_files
import native_fit
from native_references import ReloadRequired


def errors(v):
    manager = v.ErrorMgrSingleton.getInstance()
    messages = []
    while manager.GetNumTotalErrors():
        messages.append(manager.PopLastError().m_ErrorString)
    if messages:
        raise ValueError('; '.join(messages))
    import native_custom_assets
    native_custom_assets.require_reads(v)


def parameter(v, pid):
    field=dict(id=pid, name=v.GetParmName(pid), group=v.GetParmDisplayGroupName(pid),
                rawGroup=v.GetParmGroupName(pid), value=v.GetParmVal(pid),
                min=v.GetParmLowerLimit(pid), max=v.GetParmUpperLimit(pid),
                type=v.GetParmType(pid), description=v.GetParmDescript(pid))
    if field['rawGroup']=='Design' and field['name']=='FineRatio':
        field.update(label='Native pod length / radius ratio',description='OpenVSP 3.52.2 native pod ratio. The guided Fineness ratio field shows length / diameter (half this value).')
    if field['rawGroup']=='Sym':
        import native_symmetry
        native_symmetry.annotate(v,field)
    elif field['rawGroup']=='Mass_Props':
        labels={'Density':'Volume density (native mass / length³)',
                'Mass_Area':'Shell area density (native mass / length²)',
                'Mass_Prior':'Volume overlap priority','Shell_Flag':'Include shell mass',
                'PointMass':'Additional point mass (native mass units)',
                'CGx':'Point mass local X','CGy':'Point mass local Y','CGz':'Point mass local Z',
                'Ixx':'Local Ixx','Iyy':'Local Iyy','Izz':'Local Izz',
                'Ixy':'Local Ixy','Ixz':'Local Ixz','Iyz':'Local Iyz'}
        if field['name'] in labels:field['label']=labels[field['name']]
        if field['name'] in ('CGx','CGy','CGz'):field['dimension']='length'
    import native_parasite_controls
    native_parasite_controls.annotate(v,field)
    import native_aero_guides
    native_aero_guides.annotate_parameter(v,field)
    import native_wave_controls
    native_wave_controls.annotate(v,field)
    import native_measurements
    native_measurements.annotate(v,field)
    import native_export_controls
    native_export_controls.annotate(v,field)
    import native_intersection_defaults
    native_intersection_defaults.annotate(v,field)
    import native_connection_controls
    native_connection_controls.annotate(v,field)
    import native_boundary_controls
    native_boundary_controls.annotate(v,field)
    import native_material_controls
    native_material_controls.annotate(v,field)
    import native_property_controls
    native_property_controls.annotate(v,field)
    import native_element_controls
    native_element_controls.annotate(v,field)
    import native_part_controls
    native_part_controls.annotate(v,field)
    import native_region_controls
    native_region_controls.annotate(v,field)
    native_mesh.annotate(field,v)
    import native_fea_sizing
    native_fea_sizing.annotate(v,field)
    import native_cfd_density
    native_cfd_density.annotate(v,field)
    import native_scale_controls
    native_scale_controls.annotate(v,field)
    import native_saved_analysis_controls
    native_saved_analysis_controls.annotate(v,field)
    import native_engine_controls
    native_engine_controls.annotate(v,field)
    import native_wing_blending
    native_wing_blending.annotate(v,field)
    import native_stack_positions
    native_stack_positions.annotate(v,field)
    import native_property_locks
    native_property_locks.annotate(v,field)
    return field


def snapshot(v):
    import native_parasite_controls
    native_parasite_controls.refresh(v)
    import native_wave_controls
    native_wave_controls.refresh(v)
    import native_cfd_density
    native_cfd_density.refresh(v)
    import native_part_controls
    native_part_controls.refresh(v)
    import native_boundary_controls
    native_boundary_controls.refresh(v)
    components = []
    warnings = []
    for gid in v.FindGeoms():
        kind = v.GetGeomTypeName(gid)
        import native_custom_library
        native_custom_library.validate_surfaces(v,gid)
        params = [parameter(v, p) for p in v.GetGeomParmIDs(gid)]
        surfaces = []
        for i in range(v.GetTotalNumSurfs(gid)):
            # Query the engine's surface coordinates and actual points, including symmetry.
            u, w = v.GetUWTess01(gid, i % max(1, v.GetNumMainSurfs(gid)))
            if len(u)<2 or len(w)<2:
                warnings.append(f'{v.GetGeomName(gid)}: native surface {i} is degenerate; configure its geometry before sampling.')
                continue
            if len(u) * len(w) > 120000:
                warnings.append(f'{v.GetGeomName(gid)}: dense display surface reduced; model unchanged.')
                u = u[::max(1, len(u)//150)]
                w = w[::max(1, len(w)//150)]
                if u[-1] != 1: u = list(u) + [1.]
                if w[-1] != 1: w = list(w) + [1.]
            pts = v.CompVecPnt01(gid, i, [x for x in u for _ in w], [y for _ in u for y in w])
            xyz=[[p.x(), p.y(), p.z()] for p in pts]
            if kind.upper() in ('GEAR','AUXILIARY') and any(not math.isfinite(x) for p in xyz for x in p):
                warnings.append(f'{v.GetGeomName(gid)}: native surface {i} contains undefined points; review tire, rim, shoulder and auxiliary settings.')
            surfaces.append(dict(index=i,rows=len(u), cols=len(w), points=xyz))
        import native_custom_library
        generated_sections=native_custom_library.is_custom(v,gid)
        sections = []
        if generated_sections or kind in ('Wing', 'Fuselage', 'Stack', 'Propeller', 'WING', 'FUSELAGE', 'STACK', 'PROP'):
            for si in range(v.GetNumXSecSurfs(gid)):
                surf = v.GetXSecSurf(gid, si)
                for ix in range(v.GetNumXSec(surf)):
                    xid = v.GetXSec(surf, ix)
                    entry = dict(generated=generated_sections,surface=si, index=ix, id=xid, shape=v.GetXSecShape(xid),alias=v.GetXSecAlias(xid),curveAlias=v.GetXSecCurveAlias(xid))
                    if kind.upper() in ('FUSELAGE','STACK'):
                        entry['skin']=dict(continuity=v.GetXSecContinuity(xid),sides={label:dict(angles=list(v.GetXSecTanAngles(xid,side)),slews=list(v.GetXSecTanSlews(xid,side)),strengths=list(v.GetXSecTanStrengths(xid,side)),curvatures=list(v.GetXSecCurvatures(xid,side))) for label,side in [('XSEC_LEFT_SIDE',v.XSEC_LEFT_SIDE),('XSEC_RIGHT_SIDE',v.XSEC_RIGHT_SIDE)]})
                    import native_file_profiles
                    entry['filePoints']=native_file_profiles.snapshot(v,xid)
                    entry['profile']=[[p.x(),p.y(),p.z()] for p in [v.ComputeXSecPnt(xid,i/100) for i in range(101)]]
                    if entry['shape']==v.XS_EDIT_CURVE:
                        entry['controlPoints']=[[p.x(),p.y(),p.z()] for p in v.GetEditXSecCtrlVec(xid,True)]
                        entry['curveU']=list(v.GetEditXSecUVec(xid));entry['fixedU']=list(v.GetEditXSecFixedUVec(xid))
                        entry['rounding']=[v.GetParmVal(v.GetXSecParm(xid,f'R_{i}')) for i in range(len(entry['controlPoints']))]
                        entry['curveType']=int(v.GetParmVal(v.GetXSecParm(xid,'CurveType')))
                        entry['smooth']=[bool(v.GetParmVal(v.GetXSecParm(xid,f'G1_{i}'))) for i in range(len(entry['controlPoints']))]
                        curve_parameters=[parameter(v,p) for p in v.GetXSecParmIDs(xid)]
                        from native_preview import editable_activity
                        entry.update(editable_activity(v,curve_parameters,len(entry['controlPoints'])))
                        from native_editable_curves import tangent_controls,initialization_shape
                        entry['initShape']=initialization_shape(v,curve_parameters)
                        entry['tangentControls']=tangent_controls(v,curve_parameters,entry['controlPoints'])
                        active={p['id']:p['active'] for p in curve_parameters}
                        for p in params:
                            if p['id'] in active:p['active']=active[p['id']]
                        entry['curveParameters']=[p for p in curve_parameters if p['name'] in ('SymType','CloseFlag','Width','Height','PreserveARFlag')]
                    if entry['shape']==v.XS_CST_AIRFOIL:
                        entry['cst']=dict(upper=list(v.GetUpperCSTCoefs(xid)),lower=list(v.GetLowerCSTCoefs(xid)),upperDegree=v.GetUpperCSTDegree(xid),lowerDegree=v.GetLowerCSTDegree(xid))
                    if kind.upper() == 'WING' and ix > 0:
                        entry['drivers'] = list(v.GetDriverGroup(gid, ix))
                    sections.append(entry)
        if kind.upper()=='WING':
            import native_wing_controls
            native_wing_controls.enrich(v,gid,params,sections)
        elif kind.upper() in ('PROP','PROPELLER'):
            import native_prop_controls
            native_prop_controls.enrich(v,gid,params,sections)
        elif kind.upper() in ('FUSELAGE','STACK'):
            import native_body_controls
            native_body_controls.enrich(v,gid,params,sections)
        mesh=native_files.mesh_geometry(v,gid) if kind.upper() in ('MESH','NGONMESH','NGON_MESH') else native_files.solid_preview(v,gid) if kind.upper()=='HUMAN' else None
        human_controls=None
        if kind.upper()=='HUMAN':
            import native_human_controls
            human_controls=native_human_controls.enrich(v,gid,params)
        if kind.upper() in ('GEAR','AUXILIARY'):
            import native_gear_controls
            native_gear_controls.enrich(v,gid,params)
        paths=[]
        isolated_points=[]
        wire_settings=None
        if kind.upper()=='WIREFRAME':
            from native_preview import wire_geometry,parameter_activity
            import native_wire
            drawing=wire_geometry(v,gid);surfaces=drawing['surfaces'];paths=drawing['paths'];isolated_points=drawing['points']
            activity=parameter_activity(v,[p['id'] for p in params])
            for p in params:p['active']=activity[p['id']]
            wire_settings=native_wire.settings(v,gid,params)
        if not surfaces and not mesh and not paths and kind.upper() not in ('BLANK','HINGE','PTCLOUD','POINTCLOUD','POINT_CLOUD','ROUTING','AUXILIARY'):
            warnings.append(f'{v.GetGeomName(gid)}: no wire drawing points remain; reduce trimming or import a populated wire file.' if wire_settings else f'{v.GetGeomName(gid)}: this geometry has no API surface preview; inspect it in native OpenVSP.')
        import native_attachments
        attachment=native_attachments.enrich(v,gid,params)
        import native_end_caps
        end_caps=native_end_caps.enrich(v,gid,params,sections)
        import native_profile_controls
        profile_controls=native_profile_controls.enrich(v,gid,params,sections)
        import native_family_controls
        family_controls=native_family_controls.apply(v,gid,params)
        import native_component_drag
        family_controls+=native_component_drag.enrich(v,gid,params)
        conformal_source=None
        if kind.upper()=='CONFORMAL':
            import native_conformal
            conformal_source=native_conformal.metadata(v,gid)
        from native_preview import geometry_features
        features=geometry_features(v,gid) if kind.upper() in ('POD','WING','FUSELAGE','STACK','PROP','PROPELLER','ELLIPSOID','BODYOFREVOLUTION','CONFORMAL','COBRA') else []
        import native_custom_library
        native_custom_library.enrich(v,gid,params)
        import native_design_assist
        design_assist=native_design_assist.metadata(v,gid)
        from native_preview import blank_drawings
        reference_drawings=blank_drawings(v,gid) if kind.upper()=='BLANK' else []
        if kind.upper() in ('NGONMESH','NGON_MESH'):
            reference_drawings=[dict(obj,selectionOnly=False) for obj in native_ngon.drawings(v,gid) if obj['visible']]
        if kind.upper()=='HINGE':
            import native_hinge
            reference_drawings=[obj for part in native_hinge.preview(v,gid)['parts'] for obj in part['objects']]
        custom_actions=[]
        if kind in native_custom_library.TYPES or kind=='Custom' or kind.startswith('StudioPart_'):
            from native_custom_scripts import actions
            custom_actions=actions(v,gid)
        from native_special import SHAPES
        import native_prop_profiles
        profile_shapes=[n for n in SHAPES if not (native_prop_profiles.is_prop(v,gid) and n=='XS_POINT')]
        components.append(dict(profileShapes=profile_shapes,customActions=custom_actions,designAssist=design_assist,id=gid, name=v.GetGeomName(gid), type=kind, params=params,attachment=attachment,endCaps=end_caps,profileControls=profile_controls,humanControls=human_controls,familyControls=family_controls,conformalSource=conformal_source,
                               parent=v.GetGeomParent(gid), shown=v.GetSetFlag(gid,v.SET_SHOWN), mainSurfaceCount=v.GetNumMainSurfs(gid), surfaces=surfaces, referenceDrawings=reference_drawings,featureLines=features, paths=paths, points=isolated_points, wireSettings=wire_settings, mesh=mesh, sections=sections))
    import native_custom_bindings
    binding_parameters={p['id']:{**p,'bindingOwner':c['name']} for c in components for p in c['params']}
    for c in components:
        controls=native_custom_bindings.external_controls(v,c,binding_parameters,include_own=True)
        c['customOwnControls']=[row for row in controls if row.get('owned')]
        c['customExternalControls']=[row for row in controls if not row.get('owned')]
    tools=native_tools.snapshot(v,parameter)
    import native_property_locks
    tools['propertyLocks']=native_property_locks.snapshot(v)
    warnings.extend('Saved lock needs attention: '+item.get('label',item['id'])+'. Unlock it in Properties before editing.' for item in tools['propertyLocks'] if item['conflict'])
    for c in components:
        cloud=next((p for p in tools['pointClouds'] if p['id']==c['id']),None)
        if cloud:c['points']=cloud['worldPoints']
        route=next((p for p in tools['routes'] if p['id']==c['id']),None)
        if route:
            c['paths']=[copy['curve'] for copy in route['copies'] if copy['curve']]
            c['points']=[p for copy in route['copies'] for p in copy['points']]
    errors(v)
    from native_preview import wing_driver_combinations
    return dict(tools=tools,version=v.GetVSPVersion(), components=components, warnings=warnings,
                wingDriverCombinations=wing_driver_combinations(v) if any(c['type'].upper()=='WING' for c in components) else [],
                types=list(v.GetGeomTypes()), analyses=list(v.ListAnalysis())+['FeaAssemblyMesh','FlowPlaneSlicer']+list(native_analytical.NAMES),
                shapes={n:getattr(v,n) for n in __import__('native_special').SHAPES if hasattr(v,n)},
                drivers={n: getattr(v,n) for n in ('AR_WSECT_DRIVER','SPAN_WSECT_DRIVER','AREA_WSECT_DRIVER','TAPER_WSECT_DRIVER','AVEC_WSECT_DRIVER','ROOTC_WSECT_DRIVER','TIPC_WSECT_DRIVER','SECSWEEP_WSECT_DRIVER')})


def analysis_schema(v, name, reset=True):
    if name=='CfdMeshAnalysis':
        import native_cfd_density
        native_cfd_density.refresh(v)
    if name=='FlowPlaneSlicer':
        from native_flow_slices import schema
        return schema(v)
    if name not in v.ListAnalysis():
        raise ValueError('Unknown analysis.')
    if reset:
        v.SetAnalysisInputDefaults(name)
        if name=='CfdMeshAnalysis':v._studio_cfd_saved_sizing=0
    inputs = []
    getters = {v.INT_DATA:v.GetIntAnalysisInput, v.DOUBLE_DATA:v.GetDoubleAnalysisInput,
               v.STRING_DATA:v.GetStringAnalysisInput, v.VEC3D_DATA:v.GetVec3dAnalysisInput}
    for key in v.GetAnalysisInputNames(name):
        kind = v.GetAnalysisInputType(name, key)
        for index in range(v.GetNumAnalysisInputData(name, key)):
            if kind not in getters:
                inputs.append(dict(name=key,index=index,type=kind,values=[],editable=False,description=v.GetAnalysisInputDoc(name,key)))
                continue
            values = list(getters[kind](name,key,index))
            if kind == v.VEC3D_DATA:
                values = [[p.x(),p.y(),p.z()] for p in values]
            inputs.append(dict(name=key, index=index, type=kind, values=values, editable=True,
                               description=v.GetAnalysisInputDoc(name,key)))
    errors(v)
    if name=='CfdMeshAnalysis':inputs.append(dict(name='UseSavedSizing',index=0,type=v.INT_DATA,values=[getattr(v,'_studio_cfd_saved_sizing',0)],editable=True,description='Studio run policy: preserve original saved sizing bases/values, or apply entered absolute run lengths. All density calculations remain native.'))
    import native_guides
    guidance=native_guides.annotate(v,name,inputs)
    import native_saved_analysis_controls
    native_saved_analysis_controls.bind_inputs(v,name,inputs)
    return dict(name=name, description=v.GetAnalysisDoc(name), inputs=inputs,**guidance)


def set_inputs(v, name, entries, validate_guides=True, prepared_single_geom=''):
    known = { (e['name'],e['index']):e for e in analysis_schema(v,name)['inputs'] }
    if name=='CfdMeshAnalysis':
        policy=next((e.get('values') for e in entries if e.get('name')=='UseSavedSizing'),[0])
        if not isinstance(policy,list) or len(policy)!=1 or isinstance(policy[0],bool) or policy[0] not in (0,1):raise ValueError('Choose a supported CFD sizing policy.')
        v._studio_cfd_saved_sizing=int(policy[0])
    setters = {v.INT_DATA:v.SetIntAnalysisInput,v.DOUBLE_DATA:v.SetDoubleAnalysisInput,
               v.STRING_DATA:v.SetStringAnalysisInput,v.VEC3D_DATA:v.SetVec3dAnalysisInput}
    for e in entries:
        key = (e['name'],e.get('index',0))
        if key not in known: raise ValueError('Unknown analysis input.')
        spec=known[key]; kind=spec['type']; values=e['values']
        if not isinstance(values,list) or len(values)>10000: raise ValueError('Inputs must be arrays of at most 10000 values.')
        if kind in (v.INT_DATA,v.DOUBLE_DATA):
            if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in values):
                raise ValueError(f'{key[0]} requires finite numeric values.')
            if kind==v.INT_DATA:
                if any(int(x)!=x for x in values): raise ValueError(f'{key[0]} requires integers.')
                values=[int(x) for x in values]
        elif kind==v.STRING_DATA:
            if any(not isinstance(x,str) for x in values): raise ValueError('String input required.')
        elif kind==v.VEC3D_DATA:
            if any(not isinstance(p,list) or len(p)!=3 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in p) for p in values): raise ValueError('Expected an array of XYZ vectors.')
            values=[v.vec3d(*p) for p in values]
        else: raise ValueError('This input type requires the native interface.')
        if name=='CfdMeshAnalysis' and (key[0]=='UseSavedSizing' or getattr(v,'_studio_cfd_saved_sizing',0) and key[0] in ('BaseLen','MinLen','MaxGap')):continue
        setters[kind](name,key[0],values,key[1])
    errors(v)
    import native_guides
    if validate_guides:
        spec=analysis_schema(v,name,reset=False)
        spec['preparedSingleGeomID']=prepared_single_geom
        native_guides.validate(v,name,spec)
    native_guides.configure_output(v,name)


def collect_results(v):
    output=[]
    getters={v.INT_DATA:v.GetIntResults,v.DOUBLE_DATA:v.GetDoubleResults,v.STRING_DATA:v.GetStringResults,
             v.VEC3D_DATA:v.GetVec3dResults,v.DOUBLE_MATRIX_DATA:v.GetDoubleMatResults}
    for name in v.GetAllResultsNames():
        for index in range(v.GetNumResults(name)):
            rid=v.FindResultsID(name,index)
            entries=[]
            for key in v.GetAllDataNames(rid):
                kind=v.GetResultsType(rid,key)
                if kind not in getters: continue
                for j in range(v.GetNumData(rid,key)):
                    values=list(getters[kind](rid,key,j))
                    if kind==v.VEC3D_DATA: values=[[p.x(),p.y(),p.z()] for p in values]
                    elif kind==v.DOUBLE_MATRIX_DATA: values=[list(row) for row in values]
                    entries.append(dict(name=key,index=j,type=kind,values=values,description=v.GetResultsEntryDoc(rid,key)))
            output.append(dict(id=rid,name=name,index=index,description=v.GetResultsSetDoc(rid),entries=entries))
    return output


def mutate(v, req):
    import native_components
    before_set_count=v.GetNumSets()
    action=req['operation']
    gid=req.get('geom')
    if gid is not None and gid not in v.FindGeoms(): raise ValueError('This component no longer exists.')
    import native_custom_library
    if gid and native_custom_library.is_custom(v,gid) and (action in ('shape','insert-section','cut-section','split-section','drivers','airfoil-import','body-skin-reset-all') or action.startswith(('curve-','cst-')) or action.startswith('section-') and action!='section-labels'):
        raise ValueError('These sections are generated by the custom script. Edit its component controls or script.')
    if action in ('scale-accept','scale-reset'):
        import native_scale_controls
        native_scale_controls.mutate(v,req)
    elif action=='property-lock':
        import native_property_locks
        native_property_locks.set_locked(v,req['parameters'],req['locked'])
    elif action=='custom-trigger':
        import native_custom_scripts
        native_custom_scripts.trigger(v,gid,req.get('index'))
    elif action=='custom-control-parameter':
        import native_custom_bindings
        pid=native_custom_bindings.require_current_binding(v,req)
        return mutate(v,{**req,'operation':'parameter','id':pid})
    elif action=='custom-index-step':
        import native_custom_scripts
        native_custom_scripts.index_step(v,gid,req.get('index'),req.get('delta'))
    elif action=='engine-configure':
        import native_engine_controls
        native_engine_controls.configure(v,req)
    elif action=='parameter':
        pid=req['id']
        allowed={p for g in v.FindGeoms() for p in v.GetGeomParmIDs(g)} | native_tools.parameter_ids(v)
        if pid not in allowed: raise ValueError('This parameter no longer exists.')
        import native_custom_library
        native_custom_library.validate(v,pid)
        import native_prop_drivers
        native_prop_drivers.validate_parameter(v,pid)
        import native_scale_controls
        native_scale_controls.validate_parameter(v,pid)
        import native_human_controls
        native_human_controls.validate_parameter(v,pid)
        import native_prop_controls
        native_prop_controls.validate_parameter(v,pid)
        import native_wing_controls
        native_wing_controls.validate_parameter(v,pid,req.get('value'))
        import native_body_controls
        native_body_controls.validate_parameter(v,pid,req.get('value'))
        import native_skinning_controls
        native_skinning_controls.validate_parameter(v,pid)
        import native_attachments
        native_attachments.validate_parameter(v,pid)
        import native_end_caps
        native_end_caps.validate_parameter(v,pid,req.get('value'))
        import native_profile_controls
        native_profile_controls.validate_parameter(v,pid,req.get('value'))
        import native_gear_controls
        native_gear_controls.validate_parameter(v,pid,req.get('value'))
        import native_family_controls
        native_family_controls.validate_parameter(v,pid)
        import native_engine_controls
        native_engine_controls.validate_parameter(v,pid,req.get('value'))
        import native_geometry_cases
        native_geometry_cases.validate_parameter(v,pid)
        import native_connection_controls
        native_connection_controls.validate_parameter(v,pid,req.get('value'))
        import native_boundary_controls
        native_boundary_controls.validate_parameter(v,pid)
        import native_material_controls
        native_material_controls.validate_parameter(v,pid)
        import native_property_controls
        native_property_controls.validate_parameter(v,pid)
        import native_element_controls
        native_element_controls.validate_parameter(v,pid)
        import native_part_controls
        native_part_controls.validate_parameter(v,pid)
        import native_region_controls
        native_region_controls.validate_parameter(v,pid)
        import native_fea_sizing
        native_fea_sizing.validate_parameter(v,pid)
        import native_cfd_density
        native_cfd_density.validate_parameter(v,pid)
        import native_export_controls
        native_export_controls.validate_parameter(v,pid)
        import native_parasite_controls
        native_parasite_controls.validate_parameter(v,pid,req.get('value'))
        import native_wave_controls
        native_wave_controls.validate_parameter(v,pid,req.get('value'))
        import native_measurements
        native_measurements.validate_parameter(v,pid)
        import native_aero_guides
        native_aero_guides.validate_saved_parameter(v,pid,req.get('value'))
        value=req['value']
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value): raise ValueError('Enter a finite number.')
        kind=v.GetParmType(pid)
        if kind in (v.PARM_INT_TYPE,v.PARM_LIMITED_INT_TYPE,v.PARM_POWER_INT_TYPE,v.PARM_BOOL_TYPE) and value!=int(value):raise ValueError('Enter a whole number for this native count, choice or switch.')
        if not v.GetParmLowerLimit(pid)<=value<=v.GetParmUpperLimit(pid): raise ValueError('Value is outside the OpenVSP parameter limits.')
        if kind==v.PARM_BOOL_TYPE and value not in (0,1):raise ValueError('Use Off (0) or On (1) for this native switch.')
        import native_components
        if pid==native_components.count_parameter(v):native_components.resize(v,value)
        elif not native_parasite_controls.set_parameter(v,pid,value):v.SetParmValUpdate(pid,value)
        native_part_controls.refresh(v,pid=pid)
        native_region_controls.refresh(v,pid)
        native_measurements.refresh(v)
        native_fea_sizing.refresh(v,pid)
        native_cfd_density.refresh(v)
    elif action=='human-preset':
        import native_human_controls
        native_human_controls.preset(v,req)
    elif action=='conformal-source':
        import native_conformal
        native_conformal.set_source(v,gid,req['source'])
    elif action=='add':
        if req['type'] not in v.GetGeomTypes(): raise ValueError('Unknown geometry type.')
        parent=req.get('parent','')
        if parent and parent not in v.FindGeoms(): raise ValueError('Invalid parent component.')
        if req['type']=='CONFORMAL' and not parent: raise ValueError('Choose a supported parent for conformal geometry.')
        gid=v.AddGeom(req['type'],parent)
    elif action=='delete':
        import native_conformal
        native_conformal.guard_geometry_delete(v,gid)
        import native_structure
        native_structure.guard_geometry_delete(v,gid)
        import native_cfd
        native_cfd.guard_geometry_delete(v,gid)
        import native_gear_retraction
        native_gear_retraction.guard_geometry_delete(v,gid)
        import native_measurements
        native_measurements.guard_geometry_delete(v,gid)
        import native_parasite_controls
        native_parasite_controls.guard_geometry_delete(v,gid)
        import native_wave_controls
        native_wave_controls.guard_geometry_delete(v,gid)
        v.DeleteGeom(gid)
    elif action=='rename':
        name=str(req['name']).strip()
        if not name or len(name)>120: raise ValueError('Use a name of 1–120 characters.')
        v.SetGeomName(gid,name)
    elif action=='design-assist':
        import native_design_assist
        native_design_assist.apply(v,req)
    elif action=='section-labels':
        si=req.get('surface',0);index=req['index']
        if type(si)!=int or type(index)!=int or not 0<=si<v.GetNumXSecSurfs(gid):raise ValueError('Choose a valid section surface.')
        surf=v.GetXSecSurf(gid,si)
        if not 0<=index<v.GetNumXSec(surf):raise ValueError('Choose an existing section.')
        labels=[req.get('alias',''),req.get('curveAlias','')]
        if any(not isinstance(label,str) or len(label)>120 for label in labels):raise ValueError('Use section labels of up to 120 characters.')
        x=v.GetXSec(surf,index);v.SetXSecAlias(x,labels[0].strip());v.SetXSecCurveAlias(x,labels[1].strip())
    elif action=='section-copy-from':
        import native_section_copy
        if isinstance(req.get('source'),dict) or 'curveOnly' in req or req.get('sourceKind')=='bor':
            import native_special
            routed=req
            if not isinstance(req.get('source'),dict):
                source=dict(kind=req.get('sourceKind','section'),geom=req['sourceGeom'])
                if source['kind']=='section':source.update(surface=req.get('sourceSurface',0),index=req['sourceIndex'])
                routed={**req,'source':source}
            native_special.mutate(v,routed)
            if routed.get('curveOnly',True):native_section_copy.refresh_owner(v,gid)
        else:native_section_copy.replace(v,req)
    elif action in ('shape','insert-section','cut-section','split-section','drivers'):
        gid,surf,index,_=native_tools.section(v,req)
        before_count=v.GetNumXSec(surf)
        if action in ('shape','insert-section'):
            from native_special import SHAPES
            shape=req.get('shape')
            if type(shape)!=int or shape not in [getattr(v,name) for name in SHAPES]:raise ValueError('Choose a supported native profile shape.')
            import native_prop_profiles
            native_prop_profiles.validate_shape(v,gid,shape)
        if action=='shape':
            from native_editable_curves import guard_shape_replacement
            guard_shape_replacement(v,v.GetXSec(surf,index),shape)
            v.ChangeXSecShape(surf,index,shape)
        elif action=='insert-section': v.InsertXSec(gid,index,shape)
        elif action=='cut-section': v.CutXSec(gid,index)
        elif action=='split-section': v.SplitWingXSec(gid,index)
        else:
            drivers=req['drivers']
            import native_wing_controls
            if v.GetGeomTypeName(gid).upper()=='WING':native_wing_controls.validate_drivers(v,gid,int(req.get('surface',0)),index,drivers)
            else:
                import native_body_controls
                native_body_controls.validate_drivers(v,gid,int(req.get('surface',0)),index,drivers)
            v.SetDriverGroup(gid,index,*[int(x) for x in drivers])
        v.Update()
        expected=before_count + (1 if action in ('insert-section','split-section') else -1 if action=='cut-section' else 0)
        if v.GetNumXSec(surf)!=expected:
            raise ValueError('OpenVSP did not allow this section operation. Wing section 0 is the root boundary; select section 1 or later, and retain the minimum number of sections.')
    else:
        handled,gid=native_tools.mutate(v,req)
        if not handled: raise ValueError('Unsupported operation.')
    v.Update()
    import native_geometry_cases
    native_geometry_cases.update(v)
    import native_boundary_controls
    native_boundary_controls.refresh(v)
    import native_gear_controls
    import native_gear_retraction
    native_gear_retraction.refresh(v)
    native_gear_controls.refresh_auxiliary(v)
    if v.GetNumSets()<before_set_count and any(r['value']>=v.GetNumSets() for r in native_components.references(v)):
        raise ValueError('A setting, mode or preset refers to a removed set. Reassign its geometry set before applying this edit.')
    errors(v)
    return gid



def execute_analysis(v,req):
    name=req['name']
    prepared_single_geom=''
    if name=='FlowPlaneSlicer':
        from native_flow_slices import run,inputs
        from native_study_worker import resolve_sweeps
        req=resolve_sweeps(v,req,inputs(v,req))
        return run(v,req)
    if name=='GeometryAnalysis':
        import native_geometry_cases
        native_geometry_cases.update(v)
    from native_study_worker import resolve_sweeps
    if name in native_analytical.NAMES:
        req=resolve_sweeps(v,req,native_analytical.schema(v,name))
        data=native_analytical.run(v,req);errors(v);return data
    if name=='FeaMeshAnalysis':
        req=resolve_sweeps(v,req,native_mesh.fea_schema(v,req.get('structure')))
        native_mesh.validate_swept_sizing(v,req)
        data=native_mesh.run_fea(v,req);errors(v);return data
    if name=='FeaAssemblyMesh':
        req=resolve_sweeps(v,req,native_mesh.assembly_schema(v,req.get('structure')))
        native_mesh.validate_swept_sizing(v,req)
        data=native_mesh.run_assembly(v,req);errors(v);return data
    if name.startswith('VSPAERO') and name in ('VSPAEROSweep','VSPAEROSinglePoint'):
        import native_aero_guides
        flight_spec=analysis_schema(v,name)
        prep_spec=analysis_schema(v,'VSPAEROComputeGeometry')
        req=resolve_sweeps(v,req,flight_spec)
        req=resolve_sweeps(v,req,prep_spec,'geometryInputs')
        req=native_aero_guides.align_geometry(req,flight_spec,prep_spec)
        set_inputs(v,'VSPAEROComputeGeometry',req.get('geometryInputs',[]))
        geometry=analysis_schema(v,'VSPAEROComputeGeometry',reset=False)['inputs']
        prepared_single_geom=next((e['values'][0] for e in geometry if e['name']=='SingleGeomID'), '')
        # Validate flight inputs before starting native geometry preparation.
        set_inputs(v,name,req.get('inputs',[]),prepared_single_geom=prepared_single_geom)
        req={**req,'inputs':analysis_schema(v,name,reset=False)['inputs']}
        set_inputs(v,'VSPAEROComputeGeometry',geometry)
        geometry=analysis_schema(v,'VSPAEROComputeGeometry',reset=False)['inputs']
        prep=v.ExecAnalysis('VSPAEROComputeGeometry')
        errors(v)
        if not prep: raise ValueError('VSPAERO geometry preparation produced no results.')
    if name not in ('VSPAEROSweep','VSPAEROSinglePoint'):
        req=resolve_sweeps(v,req,analysis_schema(v,name))
    set_inputs(v,name,req.get('inputs',[]),prepared_single_geom=prepared_single_geom)
    if name=='CfdMeshAnalysis': cfd_settings=native_mesh.configure_cfd(v,name)
    elif name=='SurfaceIntersection':native_mesh.configure_outputs(v,name)
    effective_spec=analysis_schema(v,name,reset=False)
    effective_inputs=effective_spec['inputs']
    # Persist native-applied inputs before entering calculations that can abort
    # the process. A failed run must retain its setup without inventing results.
    from native_run_setup import save
    details=dict(geometryInputs=geometry if name in ('VSPAEROSweep','VSPAEROSinglePoint') else [])
    if name in ('VSPAEROSweep','VSPAEROSinglePoint'):
        import native_flow_planes
        details['cuttingPlanes']=native_flow_planes.snapshot(v,parameter)
    if name=='CfdMeshAnalysis':details['nativeSettingOverrides']=cfd_settings
    save(v,name,effective_inputs,**details)
    before_analysis_geoms=set(v.FindGeoms()) if name in ('CompGeom','DegenGeomMesh') else set()
    import native_evaluated_capture
    with native_evaluated_capture.solver(v,name,effective_inputs) as writer:
        result=v.ExecAnalysis(name)
    errors(v)
    evaluated_capture=native_evaluated_capture.seal_outputs(writer) if writer and result else None
    if name in ('CompGeom','DegenGeomMesh'):
        mesh_candidates=set(v.FindGeoms())-before_analysis_geoms
        if result:mesh_candidates.update(v.GetStringResults(result,'Mesh_GeomID'))
        for gid in mesh_candidates:
            if gid in v.FindGeoms() and v.GetGeomTypeName(gid).upper()=='MESH':native_ngon.capture_mesh(v,gid)
    if name=='CfdMeshAnalysis':
        mesh=native_mesh.read_gmsh(Path.cwd()/'surface.msh')
        import native_cfd_results
        checks=native_cfd_results.save(v)
        return dict(version=v.GetVSPVersion(),analysis=name,resultID=result,inputs=effective_inputs,geometryInputs=[],results=collect_results(v),meshFile='surface.msh',meshSummary=native_mesh.summary(mesh),cfdChecks=checks,nativeSettingOverrides=cfd_settings)
    if name=='SurfaceIntersection':
        import native_cfd_results
        # This native analysis exports files and intentionally returns no result ID.
        checks=native_cfd_results.save(v,meshed=False)
        return dict(version=v.GetVSPVersion(),analysis=name,resultID=result,inputs=effective_inputs,geometryInputs=[],results=collect_results(v),cfdChecks=checks)
    if name in ('VSPAEROSweep','VSPAEROSinglePoint') and not result and next((e['values'][0] for e in effective_inputs if e['name']=='StopBeforeRun'),0)==1:
        import native_solver_setup
        setup=native_solver_setup.read(Path.cwd())
        if not setup['available'] or not list(Path.cwd().glob('*.vspgeom')):
            raise ValueError('OpenVSP did not write the requested native solver setup and geometry.')
        return dict(version=v.GetVSPVersion(),analysis=name,resultID=result,inputs=effective_inputs,geometryInputs=geometry,results=collect_results(v),solverSetup=setup,executionMode='setup-only',solverExecuted=False)
    if not result: raise ValueError('The engine did not return a result. Inspect the run log and native settings.')
    import native_guides
    data=dict(version=v.GetVSPVersion(),analysis=name,resultID=result,inputs=effective_inputs,geometryInputs=geometry if name in ('VSPAEROSweep','VSPAEROSinglePoint') else [],results=collect_results(v))
    if name=='VSPAEROReadPreviousAnalysis' and not any(e['values'] for r in data['results'] if r['name']=='VSPAERO_Wrapper' for e in r['entries'] if e['name']=='ResultsVec'):
        raise ValueError('The saved solution contains no readable native aerodynamic records. Choose a completed solution with its native history and result files.')
    if name=='GeometryAnalysis':
        data['geometryCases']=effective_spec['guide']['cases']
        import native_case_drawings
        native_case_drawings.save(v,data)
    if name in ('VSPAEROSweep','VSPAEROSinglePoint'):
        import native_solver_setup
        data['solverSetup']=native_solver_setup.read(Path.cwd())
        if evaluated_capture:data['evaluatedStateCapture']=evaluated_capture
    return native_guides.save_preview(v,data,name)

def run(req, model):
    v=load()
    action=req['action']
    v.ClearVSPModel()
    if model.exists():
        import native_custom_assets
        readable=native_custom_assets.prepare(v,model)
        try:v.ReadVSPFile(str(readable))
        finally:
            if readable!=model:readable.unlink(missing_ok=True)
        if readable!=model:v.SetVSP3FileName(str(model))
        errors(v)
        # Synchronize derived values and edit baselines before applying edits.
        # In particular, wing TotalSpan/TotalArea setters depend on the last
        # evaluated value, which is not serialized in the native document.
        v.Update()
        native_ngon.restore_file(v,model)
        import native_cloud
        native_cloud.refresh(v)
        import native_profile_controls
        native_profile_controls.refresh(v)
        native_files.restore_design(v)
        native_fit.restore(v)
        import native_geometry_cases
        native_geometry_cases.update(v)
        import native_gear_controls
        import native_gear_retraction
        native_gear_retraction.refresh(v)
        native_gear_controls.refresh_auxiliary(v)
        import native_special
        native_special.refresh_routing_anchors(v)
        errors(v)
    v.SetVSP3FileName(str(model))
    import native_wave_controls
    native_wave_controls.refresh(v)
    import native_parasite_controls
    native_parasite_controls.refresh(v)
    if req.get('validatePropertyLocks') and action!='mutate':
        import native_property_locks
        native_property_locks.require_unchanged(v,native_property_locks.records(v))
    if action=='geometry-case-preflight':
        ids=req.get('cases')
        if not isinstance(ids,list) or not ids or any(cid not in v.GetAllGeometryAnalysesIDVec() for cid in ids):raise ValueError('Choose existing geometry cases for preflight.')
        data=native_geometry_cases.check_observation_targets(v,ids,apply_modes=True)
        errors(v);return data
    if action=='assembly-connection-preflight':
        import native_connection_controls
        aid=native_tools.one(req.get('assembly'),v.GetFeaAssemblyIDVec(),'Choose an existing structural assembly.')
        return dict(issues=native_connection_controls.connection_issues(v,aid))
    if action.startswith('study-'):
        import native_study_worker as study
        if action=='study-schema':data=study.schema(v,parameter)
        elif action=='study-validate':data=study.validate(v,req,parameter,analysis_schema,set_inputs)
        elif action=='study-model':data=study.prepare(v,req,model,errors)
        else:raise ValueError('Unknown study operation.')
        errors(v);return data
    if action=='create':
        wing=v.AddGeom('WING')
        v.SetGeomName(wing,'Main wing')
        v.Update()
        errors(v)
        native_ngon.write(v,model)
    if action=='query':
        if req['operation']=='configuration-values':
            import native_configuration_preview
            return native_configuration_preview.values(v,req)
        if req['operation']=='polygon-report':
            data=native_ngon.report(v,req['geom'])
        elif req['operation']=='flow-plane-preview':
            import native_flow_planes
            data=native_flow_planes.preview(v)
        elif req['operation']=='structural-preview':
            import native_preview
            data=native_preview.structure(v,req)
        elif req['operation']=='assembly-preview':
            import native_preview
            data=native_preview.assembly(v,req)
        elif req['operation']=='cfd-source-preview':
            import native_preview
            data=native_preview.cfd_sources(v,req)
        elif req['operation']=='cfd-domain-preview':
            import native_cfd
            data=native_cfd.preview(v,req)
        elif req['operation']=='region-boundaries':
            import native_overlays
            data=native_overlays.regions(v,req)
        elif req['operation']=='gear-tire-preview':
            import native_tire_controls
            data=native_tire_controls.preview(v,req)
        elif req['operation']=='hinge-preview':
            import native_hinge
            data=native_hinge.preview(v,req['geom'])
        else:data=native_fit.query(v,req)
        errors(v);return data
    if action=='export-geometry':
        data=native_tools.export(v,req);errors(v);return data
    if action=='schema':
        if req['name'] in native_analytical.NAMES:return native_analytical.schema(v,req['name'])
        if req['name']=='FeaMeshAnalysis': return native_mesh.fea_schema(v,req.get('structure'))
        if req['name']=='FeaAssemblyMesh': return native_mesh.assembly_schema(v,req.get('structure'))
        data=analysis_schema(v,req['name'])
        if req['name']=='CfdMeshAnalysis':
            for e in data['inputs']:
                if e['name'] in ('GMSHFileName','GMSHFileFlag'):e['editable']=False
            data['description']+=' Mesh outputs are stored with the run; Gmsh output is always enabled for inspection.'
        return data
    if action=='analysis':
        pids=req.get('studyParameters',[]) if req.get('studyID') else []
        if not isinstance(pids,list) or any(not v.ValidParm(p) for p in pids):raise ValueError('A swept native parameter is unavailable before this analysis.')
        before={p:v.GetParmVal(p) for p in pids}
        data=execute_analysis(v,req)
        if req.get('studyID'):
            data['studyParameters']=[];data['studyParameterWarnings']=[]
            for p in pids:
                available=v.ValidParm(p);after=v.GetParmVal(p) if available else None
                data['studyParameters'].append(dict(id=p,value=after if available else before[p],valueBeforeAnalysis=before[p],valueAfterAnalysis=after,availableAfterAnalysis=available))
                if not available:data['studyParameterWarnings'].append(f'{p}: OpenVSP replaced this setting during the analysis. Its last native value before replacement was {before[p]}; no value is available afterward.')
            native_ngon.write(v,Path.cwd()/'native-model-after-analysis.vsp3')
            errors(v)
        return data

    changed=None
    if action=='mutate':
        import native_property_locks
        locked=native_property_locks.records(v)
        from native_editable_curves import referenced_parameters,require_reference_survival
        import native_prop_profiles
        old_prop_points=native_prop_profiles.point_sections(v)
        copy_refs=referenced_parameters(v) if req.get('operation') in ('section-copy-from','bor-profile-copy','region-curve-copy-from','auxiliary-profile-copy') else {}
        changed=mutate(v,req)
        native_prop_profiles.validate_new_points(v,old_prop_points)
        import native_wing_controls
        if req.get('operation')=='drivers' and v.GetGeomTypeName(req['geom']).upper()=='WING':native_wing_controls.evaluate_selected_drivers(v,req['geom'],req['index'])
        native_wing_controls.validate_finite_dimensions(v)
        import native_wave_controls
        native_wave_controls.refresh(v)
        import native_parasite_controls
        native_parasite_controls.refresh(v)
        import native_custom_library
        native_custom_library.validate_gui(v)
        native_custom_library.validate_surfaces(v)
        require_reference_survival(v,copy_refs)
        import native_custom_assets
        native_custom_assets.require_reads(v)
        if req.get('operation')=='property-lock' and req.get('locked') is False:locked=[item for item in locked if item['id'] not in req['parameters']]
        native_property_locks.require_unchanged(v,locked)
        native_ngon.write(v,model)
        errors(v)
        # DecodeXml reconstructs file-curve limits and wing chord values at
        # native precision. Return authoritative saved geometry/metadata
        # through a fresh engine instead of altering native stored values.
        if req.get('operation') in ('region-curve-import','auxiliary-profile-import') or (
            req.get('operation')=='design-assist' and req.get('control')=='wing-taper'
        ):
            raise ReloadRequired()
    data=snapshot(v)
    data['changed']=changed
    return data


def sanitize(obj):
    if isinstance(obj,float) and not math.isfinite(obj): return None
    if isinstance(obj,dict): return {k:sanitize(v) for k,v in obj.items()}
    if isinstance(obj,list): return [sanitize(v) for v in obj]
    return obj

if __name__=='__main__':
    request, model, response=map(Path,sys.argv[1:4])
    # Preserve worker locks across a server restart, without leaking them into
    # external solver programs launched by the official API.
    import fcntl
    import os
    for fd in map(int,sys.argv[4:]):fcntl.fcntl(fd,fcntl.F_SETFD,fcntl.FD_CLOEXEC)
    if len(sys.argv)>4:
        owner=request.with_name('.engine-owner.json');temp=owner.with_name(owner.name+'.tmp')
        temp.write_text(json.dumps(dict(pid=os.getpid())));os.replace(temp,owner)
    def reply(data):
        temp=response.with_name(response.name+'.tmp')
        temp.write_text(json.dumps(sanitize(data),allow_nan=False));os.replace(temp,response)
    # Keep the incoming candidate recoverable across fresh-process decoding.
    # Only our internally generated reload request can carry this local name.
    import re,uuid
    rollback=None;original=None
    def restore_candidate():
        if original is not None:
            temp=model.with_name('.native-restore-'+uuid.uuid4().hex+'.vsp3');temp.write_bytes(original);os.replace(temp,model)
    def clear_rollback():
        if rollback is not None:rollback.unlink(missing_ok=True)
    try:
        req=json.loads(request.read_text())
        rollback_name=req.pop('_nativeRollbackFile',None)
        if request.name=='reload-request.json' and isinstance(rollback_name,str) and re.fullmatch(r'\.native-rollback-[0-9a-f]{32}\.vsp3',rollback_name):
            rollback=model.parent/rollback_name
        original=rollback.read_bytes() if rollback is not None else model.read_bytes() if req.get('action')=='mutate' and model.exists() else None
        data=run(req,model)
        reply(data)
        clear_rollback()
    except ReloadRequired as exc:
        import os
        reload_request=request.with_name('reload-request.json')
        # File-based native edits must satisfy the same saved geometry locks
        # after DecodeXml and dependency updates as ordinary mutations.
        next_request={**(exc.request or {'action':'state'}),'validatePropertyLocks':True}
        if original is not None:
            if rollback is None:
                rollback=model.parent/('.native-rollback-'+uuid.uuid4().hex+'.vsp3');rollback.write_bytes(original)
            next_request['_nativeRollbackFile']=rollback.name
        reload_request.write_text(json.dumps(next_request))
        for fd in map(int,sys.argv[4:]):os.set_inheritable(fd,True)
        os.execv(sys.executable,[sys.executable,str(Path(__file__).resolve()),str(reload_request),str(model),str(response),*sys.argv[4:]])
    except Exception as exc:
        restore_candidate()
        clear_rollback()
        reply({'error':str(exc)})
        raise
