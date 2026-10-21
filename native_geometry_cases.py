"""Saved geometry-analysis cases; calculations and parameter activity stay native."""
import os
import xml.etree.ElementTree as ET
from native_tools import finite, name, one
import native_references

TYPES = ['EXTERNAL_INTERFERENCE','PACKAGING_INTERFERENCE','EXTERNAL_SELF_INTERFERENCE',
         'PLANE_STATIC_DISTANCE_INTERFERENCE','PLANE_2PT_ANGLE_INTERFERENCE',
         'GEAR_CG_TIPBACK_ANALYSIS','PLANE_1PT_ANGLE_INTERFERENCE',
         'GEAR_WEIGHT_DISTRIBUTION_ANALYSIS','GEAR_TIPOVER_ANALYSIS','GEAR_TURN_ANALYSIS',
         'VISIBLE_FROM_POINT_ANALYSIS','CCE_INTERFERENCE','LINEAR_SWEPT_VOLUME_ANALYSIS',
         'VISIBLE_AT_SURF_ANALYSIS','RISK_ANGLE','COMP_GEOM','PLANAR_SLICE','PROJ_AREA','MASS_PROP','AERO_CENTER']
LABELS = ['External clearance','Internal packaging clearance','Self clearance','Distance to ground plane',
          'Two-point plane contact angle','Landing gear tipback','One-point plane contact angle',
          'Landing gear weight distribution','Landing gear tipover','Landing gear turning circles',
          'Visibility from a point','Composite clearance envelope','Linear swept volume',
          'Surface visibility','Debris risk angle','Wetted area and volume','Cross-sectional areas',
          'Projected area','Mass properties','Aerodynamic center']
REFS = ['PrimaryModeID','PrimaryGeomID','SecondaryGeomID','DirectionGeomID']
PARAM_LABELS = {'IntererenceCheckType':'Calculation','PrimaryType':'Primary selection','SecondaryType':'Secondary selection',
                'PrimarySet':'Primary geometry set','SecondarySet':'Secondary geometry set','LastResult':'Last native result',
                'NumSlices':'Integration slices','SliceDir':'Slicing axis','SecondaryZGround':'Ground-plane height',
                'DispX':'Displacement / direction X','DispY':'Displacement / direction Y','DispZ':'Displacement / direction Z',
                'AutoBoundsFlag':'Automatic slice limits','PlanarStartLocation':'Slice start coordinate','PlanarEndLocation':'Slice end coordinate'}
PARAM_LABELS.update({'DirectionType':'Projection direction','TargetHullFlag':'Use target hull',
                     'BoundaryEnableFlag':'Limit projection to boundary','BoundaryHullFlag':'Use boundary hull',
                     'DiskSegmentBreakdownFlag':'Report disk segments','HalfMeshFlag':'Use half mesh',
                     'UseSubSurfFlag':'Include surface regions','MeasureDuctFlag':'Measure internal duct area',
                     'DiscreteVisibilityFlag':'Use discrete visibility directions','PolyVisibleFlag':'Polygon visibility',
                     'SecondaryX':'Observation point X','SecondaryY':'Observation point Y','SecondaryZ':'Observation point Z'})


def editor_guide(v, case):
    """Promote the installed screen's case-specific controls; retain other fields."""
    values={p['name']:p['value'] for p in case['params']}
    typ=next((name for name in TYPES if getattr(v,name,None)==values['IntererenceCheckType']), '')
    single=typ in ('EXTERNAL_SELF_INTERFERENCE','GEAR_CG_TIPBACK_ANALYSIS','GEAR_WEIGHT_DISTRIBUTION_ANALYSIS','GEAR_TIPOVER_ANALYSIS','VISIBLE_AT_SURF_ANALYSIS','COMP_GEOM','PLANAR_SLICE','MASS_PROP','AERO_CENTER') or (typ=='PROJ_AREA' and not values['BoundaryEnableFlag'])
    base=['IntererenceCheckType','PrimaryType']
    if values['PrimaryType']==v.SET_TARGET:base.append('PrimarySet')
    if not single:
        base.append('SecondaryType')
        if values['SecondaryType']==v.SET_TARGET:base.append('SecondarySet')
        elif values['SecondaryType']==v.Z_TARGET:base.append('SecondaryZGround')
        elif values['SecondaryType']==v.XYZ_TARGET:base+=['SecondaryX','SecondaryY','SecondaryZ']
    groups=[dict(title='Calculation and geometry',names=base)]
    settings={
        'COMP_GEOM':('Wetted area and volume',['HalfMeshFlag','UseSubSurfFlag']),
        'PLANAR_SLICE':('Cross-sectional integration',['SliceDir','NumSlices','AutoBoundsFlag','PlanarStartLocation','PlanarEndLocation','MeasureDuctFlag']),
        'MASS_PROP':('Mass integration',['SliceDir','NumSlices']),
        'PROJ_AREA':('Projection',['DirectionType','DispX','DispY','DispZ','TargetHullFlag','BoundaryEnableFlag','BoundaryHullFlag','DiskSegmentBreakdownFlag']),
        'LINEAR_SWEPT_VOLUME_ANALYSIS':('Motion envelope',['ExtentType','DispX','DispY','DispZ','SymmRotX','RotXp','RotXn','SymmRotY','RotYp','RotYn','SymmRotZ','RotZp','RotZn']),
        'VISIBLE_FROM_POINT_ANALYSIS':('Visibility',['DiscreteVisibilityFlag','PolyVisibleFlag']),
        'VISIBLE_AT_SURF_ANALYSIS':('Surface visibility',['Azimuth','Elevation','N2RefractionIndex']),
        'PLANE_2PT_ANGLE_INTERFERENCE':('Plane contact',['SecondaryCCWFlag']),
        'PLANE_1PT_ANGLE_INTERFERENCE':('Plane contact',['SecondaryCCWFlag']),
    }
    if typ in settings:
        title,names=settings[typ];groups.append(dict(title=title,names=names))
        if typ=='PROJ_AREA' and not values['BoundaryEnableFlag']:
            groups[-1]['names']=[n for n in names if n not in ('BoundaryHullFlag','DiskSegmentBreakdownFlag')]
    references=[]
    if values['PrimaryType']==v.GEOM_TARGET:references.append('PrimaryGeomID')
    elif values['PrimaryType']==v.MODE_TARGET:references.append('PrimaryModeID')
    if not single and values['SecondaryType']==v.GEOM_TARGET:references.append('SecondaryGeomID')
    if typ=='PROJ_AREA' and values['DirectionType']==v.GEOM_PROJ:references.append('DirectionGeomID')
    return dict(groups=groups,references=references,visibility=typ=='VISIBLE_FROM_POINT_ANALYSIS',rotationAction=typ in ('PLANE_2PT_ANGLE_INTERFERENCE','PLANE_1PT_ANGLE_INTERFERENCE','RISK_ANGLE'),
                observationPoint=typ=='VISIBLE_FROM_POINT_ANALYSIS' and values['SecondaryType']==v.XYZ_TARGET,
                note='Choose the primary geometry, then configure the calculation below. Settings for other calculation types remain under Additional native parameters. Lengths follow the aircraft’s native model units; angles use degrees.')


def calculated_reason(v, cid, pname):
    value=lambda n:v.GetParmVal(v.FindParm(cid,n,'InterferenceCase'))
    if pname=='LastResult':return 'This value is an original-engine result.'
    if pname in ('PlanarStartLocation','PlanarEndLocation') and value('AutoBoundsFlag'):return 'Disable automatic slice limits to enter the slice bounds.'
    if pname in ('RotXn','RotYn','RotZn') and value('SymmRot'+pname[3]):return 'Disable symmetric rotation to enter the negative rotation limit.'
    if pname in ('DispX','DispY','DispZ') and value('IntererenceCheckType')==v.PROJ_AREA and value('DirectionType')!=v.VEC_PROJ:return 'Choose Entered direction vector to edit the projection direction.'
    if pname=='SecondaryType' and value('IntererenceCheckType') in [getattr(v,t) for t in ('PLANE_2PT_ANGLE_INTERFERENCE','PLANE_1PT_ANGLE_INTERFERENCE','GEAR_TURN_ANALYSIS','CCE_INTERFERENCE','RISK_ANGLE')]:return 'OpenVSP requires a secondary component for this calculation.'
    return ''


def validate_parameter(v,pid):
    cid=v.GetParmContainer(pid)
    if cid not in v.GetAllGeometryAnalysesIDVec():return
    reason=calculated_reason(v,cid,v.GetParmName(pid))
    if reason:raise ValueError(reason)


def type_choices(v):
    return [dict(value=getattr(v,t),label=label) for t,label in zip(TYPES,LABELS) if hasattr(v,t)]


def specialist_setup(v, case):
    """Explain the original manager's auxiliary requirements, without its math."""
    values={p['name']:p['value'] for p in case['params']}
    typ=values['IntererenceCheckType']
    rules={
        v.GEAR_CG_TIPBACK_ANALYSIS:('Primary','Two-contact ground plane', [v.AUX_GEOM_TWO_PT_GROUND], 'Set the attached gear’s nominal CG and CG range. OpenVSP calculates tipback about the selected two-contact pivot.'),
        v.GEAR_TIPOVER_ANALYSIS:('Primary','Two-contact ground plane', [v.AUX_GEOM_TWO_PT_GROUND], 'Set the attached gear’s nominal CG and CG range. OpenVSP calculates tipover about the selected side contacts.'),
        v.GEAR_WEIGHT_DISTRIBUTION_ANALYSIS:('Primary','Three-contact ground plane or composite clearance envelope', [v.AUX_GEOM_THREE_PT_GROUND,v.AUX_GEOM_THREE_PT_CCE], 'Choose three distinct gear contacts and set the attached gear’s nominal CG and CG range. Native reaction vectors follow contact order 1, 2, 3.'),
        v.GEAR_TURN_ANALYSIS:('Secondary','Three-contact ground plane or composite clearance envelope', [v.AUX_GEOM_THREE_PT_GROUND,v.AUX_GEOM_THREE_PT_CCE], 'Use the aircraft as the primary selection. Set steering limits on the attached gear; OpenVSP calculates the turning circles.'),
    }
    if typ not in rules:return None
    role,label,modes,note=rules[typ];geoms=list(v.FindGeoms());refs=case['references']
    compatible=[g for g in geoms if v.GetGeomTypeName(g).upper()=='AUXILIARY' and int(v.GetParmVal(g,'AuxiliaryGeomType','Design')) in modes and v.GetGeomParent(g) in geoms and v.GetGeomTypeName(v.GetGeomParent(g)).upper()=='GEAR']
    problems=[];selected=None;selection=values[role+'Type'];mode=None
    if values['PrimaryType']==v.MODE_TARGET:
        mid=refs['PrimaryModeID']
        if mid not in v.GetAllModes():problems.append('Choose an available primary native mode.')
        else:
            normal_set=int(v.GetParmVal(mid,'NormalSet','Sets'))
            mode=dict(id=mid,name=v.GetModeName(mid),normalSet=normal_set,setName=v.GetSetName(normal_set) if 0<=normal_set<v.GetNumSets() else 'None' if normal_set==-1 else 'Unavailable set',presets=[dict(group=g,setting=s) for g,s in zip(v.ModeGetAllGroups(mid),v.ModeGetAllSettings(mid))])
    if selection==v.GEOM_TARGET:
        selected=refs[role+'GeomID']
        if selected not in compatible and not mode:problems.append('Choose a '+label.lower()+' attached to a gear as the '+role.lower()+' component.')
    elif role=='Primary' and selection==v.SET_TARGET:
        # GetPrimaryAuxiliaryGeom chooses the first auxiliary in the native set.
        selected=next((g for g in geoms if v.GetGeomTypeName(g).upper()=='AUXILIARY' and v.GetSetFlag(g,int(values['PrimarySet']))),'')
        if selected not in compatible:problems.append('The primary set’s first auxiliary must be a '+label.lower()+' attached to a gear.')
    elif role=='Secondary':problems.append('Choose Component as the secondary selection, then choose the required auxiliary ground plane.')
    elif mode:
        selected=next((g for g in geoms if v.GetGeomTypeName(g).upper()=='AUXILIARY' and 0<=mode['normalSet']<v.GetNumSets() and v.GetSetFlag(g,mode['normalSet'])),'')
    return dict(role=role,required=label,note=note,compatible=[dict(id=g,name=v.GetGeomName(g)) for g in compatible],selected=selected,problems=problems,mode=mode,modeNote='OpenVSP applies this mode’s presets when the case runs. The compatible-component list describes the saved baseline; the native engine checks the resulting configuration.' if mode else '',selectionNote='For a primary set or mode, OpenVSP uses its first auxiliary geometry. Component selection lets you choose the auxiliary explicitly.')


def update(v):
    if not v.GetAllGeometryAnalysesIDVec():return
    import ctypes,json
    from native_preview import adapter
    _,engine,bridge=adapter(v)
    fn=bridge.studio_geometry_cases_update;fn.argtypes=[ctypes.c_char_p];fn.restype=ctypes.c_char_p
    result=json.loads(fn(engine))
    if result.get('error'):raise ValueError(result['error'])


def snapshot(v, parameter, refs):
    choices = {
        'IntererenceCheckType': type_choices(v),
        'PrimaryType': [dict(value=getattr(v,t),label=l) for t,l in [('SET_TARGET','Geometry set'),('GEOM_TARGET','Component'),('MODE_TARGET','Native mode')]],
        'SecondaryType': [dict(value=getattr(v,t),label=l) for t,l in [('SET_TARGET','Geometry set'),('GEOM_TARGET','Component')]],
        'PrimarySet': [dict(value=i,label=v.GetSetName(i)) for i in range(v.GetNumSets())],
        'SecondarySet': [dict(value=i,label=v.GetSetName(i)) for i in range(v.GetNumSets())],
        'SliceDir': [dict(value=getattr(v,t),label=l) for t,l in [('X_DIR','X · longitudinal'),('Y_DIR','Y · spanwise'),('Z_DIR','Z · vertical')]],
        'DirectionType': [dict(value=getattr(v,t),label=l) for t,l in [('X_PROJ','X · front'),('Y_PROJ','Y · side'),('Z_PROJ','Z · top'),('GEOM_PROJ','Component direction'),('VEC_PROJ','Entered direction vector')]],
        'ExtentType': [dict(value=getattr(v,t),label=t.removeprefix('EXTENT_').replace('_',' ').title()) for t in dir(v) if t.startswith('EXTENT_')],
    }
    cases=[]
    ids=list(v.GetAllGeometryAnalysesIDVec())
    if ids:
        from native_preview import parameter_activity
        activity=parameter_activity(v,[p for cid in ids for p in v.FindContainerParmIDs(cid)])
    else:activity={}
    for cid in ids:
        azel=[dict(index=i,azimuth=parameter(v,v.GetGeometryAnalysisAzimuthParm(cid,i)),elevation=parameter(v,v.GetGeometryAnalysisElevationParm(cid,i))) for i in range(v.GetNumGeometryAnalysisAzEl(cid))]
        azel_ids={p[k]['id'] for p in azel for k in ('azimuth','elevation')}
        params=[]
        for pid in v.FindContainerParmIDs(cid):
            if pid in azel_ids:continue
            p=parameter(v,pid);p['active']=activity.get(pid,True)
            if p['name'] in PARAM_LABELS:p['label']=PARAM_LABELS[p['name']]
            if p['name'] in choices:p['choices']=[dict(choice) for choice in choices[p['name']]]
            if p['name']=='LastResult':p['active']=False
            reason=calculated_reason(v,cid,p['name'])
            if reason:p.update(active=False,readOnly=True,description=reason)
            params.append(p)
        case=dict(id=cid,name=v.GetContainerName(cid),params=params,directions=azel,references={k:refs.get(cid,{}).get(k,'') for k in REFS},cutouts=refs.get(cid,{}).get('cutouts',[]))
        typ=next(p['value'] for p in params if p['name']=='IntererenceCheckType')
        secondary=next(p for p in params if p['name']=='SecondaryType')
        if typ==v.PLANE_STATIC_DISTANCE_INTERFERENCE:secondary['choices']=[dict(value=v.GEOM_TARGET,label='Component'),dict(value=v.Z_TARGET,label='Ground-plane height')]
        elif typ==v.VISIBLE_FROM_POINT_ANALYSIS:secondary['choices']+=[dict(value=v.XYZ_TARGET,label='Entered observation point')]
        case['editorGuide']=editor_guide(v,case)
        case['specialistSetup']=specialist_setup(v,case)
        cases.append(case)
    return dict(geometryCases=cases,geometryCaseTypes=type_choices(v))


def configuration(v):
    from native_worker import parameter
    return snapshot(v,parameter,native_references.references(v))['geometryCases']


def annotate(v,inputs):
    cases=configuration(v)
    for e in inputs:
        e['label']='Saved geometry analysis case'
        e['choices']=[dict(value='ALL',label='All saved cases')]+[dict(value=c['id'],label=c['name']) for c in cases]
        if e['values'][0] not in [c['value'] for c in e['choices']]:e['choices'].append(dict(value=e['values'][0],label='Unavailable saved case · '+e['values'][0]))
    return dict(guide=dict(title='Saved geometry analysis cases',note='Create and configure named checks in Modeling tools → Geometry checks. OpenVSP evaluates the selected saved case, or all cases, using its native clearance, visibility, geometry and landing-gear calculations. Special checks require the corresponding auxiliary or landing-gear geometry.',sensitivityNote='Review the native result descriptions and compare geometry tessellation and case settings before relying on a result.',sections=[dict(title='Saved case selection',inputs=['CaseID'])],cases=cases))


def require_observation_component(v,cid):
    value=lambda name:v.GetParmVal(v.FindParm(cid,name,'InterferenceCase'))
    if value('IntererenceCheckType')==v.VISIBLE_FROM_POINT_ANALYSIS and value('SecondaryType')==v.XYZ_TARGET:
        raise ValueError(v.GetContainerName(cid)+': the installed OpenVSP XYZ visibility path crashes. In Geometry checks, use Create observation-point component, then run this case with that component selected.')


def validate(v,schema):
    values=next(e['values'] for e in schema['inputs'] if e['name']=='CaseID')
    if len(values)!=1:raise ValueError('Choose one saved geometry analysis case.')
    if not v.GetAllGeometryAnalysesIDVec():raise ValueError('Create a named case in Modeling tools → Geometry checks before running this analysis.')
    if values[0] not in ['ALL','all',*v.GetAllGeometryAnalysesIDVec()]:raise ValueError('Choose an available saved geometry analysis case.')
    cases=configuration(v)
    # ExecAll applies each mode in case order. Later component-based checks can
    # depend on earlier presets; do not reject them against the initial baseline.
    sequential_modes=values[0] in ('ALL','all') and any(next(p['value'] for p in c['params'] if p['name']=='PrimaryType')==v.MODE_TARGET for c in cases)
    for case in cases:
        if values[0] not in ('ALL','all',case['id']):continue
        require_observation_component(v,case['id'])
        setup=case['specialistSetup']
        if setup and setup['problems'] and not sequential_modes:raise ValueError(case['name']+': '+setup['problems'][0])


def mutate(v,r):
    op=r['operation']
    if op in ('geometry-case-result-mesh','geometry-case-apply-rotation'):
        from native_case_actions import mutate as result_action
        return result_action(v,r)
    if op=='geometry-case-add':
        cid=v.AddGeometryAnalysis();v.SetContainerName(cid,name(r['name']))
        typ=one(r.get('type',v.COMP_GEOM),[c['value'] for c in type_choices(v)])
        v.SetParmVal(v.FindParm(cid,'IntererenceCheckType','InterferenceCase'),typ)
        return True,None
    cid=one(r['id'],v.GetAllGeometryAnalysesIDVec(),'This saved geometry case no longer exists.')
    if op=='geometry-case-observation-point':
        value=lambda name:v.GetParmVal(v.FindParm(cid,name,'InterferenceCase'))
        if value('IntererenceCheckType')!=v.VISIBLE_FROM_POINT_ANALYSIS or value('SecondaryType')!=v.XYZ_TARGET:
            raise ValueError('Choose an entered observation point on a point-visibility case first.')
        coordinates=[finite(value('Secondary'+axis)) for axis in 'XYZ']
        gid=v.AddGeom('BLANK');v.SetGeomName(gid,v.GetContainerName(cid)+' observation point')
        for axis,coordinate in zip('XYZ',coordinates):
            v.SetParmVal(v.FindParm(gid,axis+'_Rel_Location','XForm'),coordinate)
        v.SetParmVal(v.FindParm(cid,'SecondaryType','InterferenceCase'),v.GEOM_TARGET)
        v.Update()
        native_references.set_reference(v,cid,'GeometryAnalysis','SecondaryGeomID',gid)
    elif op=='geometry-case-delete':v.DeleteGeometryAnalysis(cid)
    elif op=='geometry-case-rename':v.SetContainerName(cid,name(r['name']))
    elif op=='geometry-case-reference':
        key=one(r['key'],REFS)
        values=v.GetAllModes() if key=='PrimaryModeID' else v.FindGeoms()
        value=one(r['value'],['',*values],'Choose an available native component or mode.')
        native_references.set_reference(v,cid,'GeometryAnalysis',key,value)
    elif op=='geometry-case-cutouts':
        selected=r['values'];valid={s for g in v.FindGeoms() for s in v.GetSubSurfIDVec(g)}
        if not isinstance(selected,list) or any(s not in valid for s in selected) or len(set(selected))!=len(selected):raise ValueError('Choose distinct existing surface regions for visibility cutouts.')
        filename=v.GetVSPFileName();path,tree=native_references.document(v)
        try:
            node=next(n for n in tree.findall('.//GeometryAnalysis') if n.findtext('ParmContainer/ID')==cid)
            old=node.find('CutoutSS_List')
            if old is not None:node.remove(old)
            parent=ET.SubElement(node,'CutoutSS_List')
            for sid in selected:ET.SubElement(ET.SubElement(parent,'CutoutSS'),'cutoutSS_ID').text=sid
            tree.write(path,encoding='utf-8',xml_declaration=True);os.replace(path,filename)
        finally:path.unlink(missing_ok=True)
        raise native_references.ReloadRequired()
    elif op=='geometry-case-direction-add':
        az=finite(r['azimuth']);el=finite(r['elevation'])
        if not -180<=az<=180 or not -90<=el<=90:raise ValueError('Use azimuth from −180 to 180° and elevation from −90 to 90°.')
        v.AddGeometryAnalysisAzEl(cid,az,el)
    elif op=='geometry-case-direction-delete':v.DeleteGeometryAnalysisAzEl(cid,one(r['index'],range(v.GetNumGeometryAnalysisAzEl(cid))))
    else:raise ValueError('Unknown geometry case operation.')
    return True,None
