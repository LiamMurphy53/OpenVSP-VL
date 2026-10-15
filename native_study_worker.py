"""Study setup and case files; all parameter evaluation stays in OpenVSP."""
import copy
import math
import native_analytical
import native_mesh
from native_tools import finite


def parameter_ids(v):
    ids=set(v.GetAllUserParms())
    for g in v.FindGeoms():ids.update(v.GetGeomParmIDs(g))
    for c in v.FindContainers():ids.update(v.FindContainerParmIDs(c))
    from native_tools import parameter_ids as extra
    ids.update(extra(v));return ids


def schema(v,parameter):
    import native_wave_controls
    native_wave_controls.refresh(v)
    import native_parasite_controls
    native_parasite_controls.refresh(v)
    import native_measurements
    native_measurements.refresh(v)
    import native_cfd_density
    native_cfd_density.refresh(v)
    import native_part_controls
    native_part_controls.refresh(v)
    import native_boundary_controls
    native_boundary_controls.refresh(v)
    import native_profile_controls
    native_profile_controls.refresh(v)
    import native_prop_drivers
    import native_references
    disk_fields={}
    if v.GetNumActuatorDisks():
        refs=native_references.references(v)
        for i in range(v.GetNumActuatorDisks()):
            for item in native_prop_drivers.configuration(v,v.FindActuatorDisk(i),refs,parameter)['params']:
                if item.get('active') is False:disk_fields[item['id']]='Calculated by OpenVSP from the saved disk drivers or automatic hub sizing.'
    geometry={p:v.GetGeomName(g) for g in v.FindGeoms() for p in v.GetGeomParmIDs(g)}
    import native_wing_controls
    wing_fields=native_wing_controls.read_only_reasons(v)
    import native_body_controls
    body_fields=native_body_controls.read_only_reasons(v)
    import native_skinning_controls
    skin_fields=native_skinning_controls.read_only_reasons(v)
    import native_attachments
    attachment_fields=native_attachments.read_only_reasons(v)
    import native_prop_controls
    blade_fields=native_prop_controls.read_only_reasons(v)
    import native_end_caps
    cap_fields=native_end_caps.read_only_reasons(v)
    cap_choices=native_end_caps.study_choices(v)
    import native_profile_controls
    profile_fields=native_profile_controls.read_only_reasons(v)
    import native_gear_controls
    gear_fields=native_gear_controls.read_only_reasons(v)
    import native_family_controls
    family_fields=native_family_controls.read_only_reasons(v)
    import native_family_studies
    family_dependencies=native_family_studies.metadata(v)
    import native_geometry_cases
    case_metadata={}
    for case in native_geometry_cases.snapshot(v,parameter,{})['geometryCases']:
        for field in case['params']:
            if field['name']=='SecondaryType':
                field['choices']=[dict(value=getattr(v,n),label=l) for n,l in [('SET_TARGET','Geometry set'),('GEOM_TARGET','Component'),('Z_TARGET','Ground-plane height'),('XYZ_TARGET','Entered observation point')]]
            if field.get('active') is False:
                field.update(editable=False,readOnlyReason=native_geometry_cases.calculated_reason(v,case['id'],field['name']) or 'This case field is inactive in the native baseline.')
            case_metadata[field['id']]=field
    family_metadata={}
    prop_metadata={}
    drag_metadata={}
    import native_component_drag
    for gid in v.FindGeoms():
        drag_fields=[parameter(v,pid) for pid in v.GetGeomParmIDs(gid) if v.GetParmGroupName(pid)=='ParasiteDragProps']
        native_component_drag.enrich(v,gid,drag_fields)
        drag_metadata.update({p['id']:p for p in drag_fields})
        if v.GetGeomTypeName(gid).upper() in ('PROP','PROPELLER'):
            fields=[parameter(v,pid) for pid in v.GetGeomParmIDs(gid)]
            native_prop_controls.enrich(v,gid,fields,[])
            for field in fields:
                if field.get('choices') is not None:field['choices']=[dict(value=c[0],label=c[1]) if isinstance(c,(list,tuple)) else c for c in field['choices']]
            prop_metadata.update({p['id']:p for p in fields})
        if v.GetGeomTypeName(gid).upper() in native_family_controls.SUPPORTED:
            fields=[parameter(v,pid) for pid in v.GetGeomParmIDs(gid)]
            native_family_controls.apply(v,gid,fields)
            for field in fields:
                if field.get('choices') is not None:field['choices']=[dict(value=c[0],label=c[1]) if isinstance(c,(list,tuple)) else c for c in field['choices']]
            family_metadata.update({p['id']:p for p in fields})
    gear_metadata={}
    for gid,_,ids in native_gear_controls.owners(v):
        fields=[parameter(v,pid) for pid in ids];native_gear_controls.enrich(v,gid,fields)
        gear_metadata.update({p['id']:p for p in fields})
    params=[]
    import native_human_controls
    human_fields=native_human_controls.read_only_reasons(v)
    human_metadata={};human_dependencies={}
    for gid in v.FindGeoms():
        if v.GetGeomTypeName(gid).upper()=='HUMAN':
            fields=[parameter(v,pid) for pid in v.GetGeomParmIDs(gid)]
            native_human_controls.enrich(v,gid,fields,eyes=False)
            human_metadata.update({p['id']:p for p in fields})
            human_dependencies.update(native_human_controls.study_metadata(v,gid))
    import native_rotor_identity
    rotor_fields=native_rotor_identity.fields(v)
    import native_property_controls
    property_refs=native_references.references(v) if v.GetFeaPropertyIDVec() else {}
    for p in parameter_ids(v):
        if not v.ValidParm(p):continue
        item=case_metadata.get(p) or drag_metadata.get(p) or human_metadata.get(p) or gear_metadata.get(p) or family_metadata.get(p) or prop_metadata.get(p) or parameter(v,p);owner=v.GetContainerName(v.GetParmContainer(p))
        native_property_controls.annotate(v,item,property_refs)
        if item['rawGroup']=='FeaProperty':
            item['studyNote']='Property model, beam section and declared units apply before property values. Dimension meanings follow each case’s chosen section. Values use native declared units; laminate-linked thickness and units remain calculated.'
            if item['name'].startswith('Dim') and not item['name'].endswith('_FEM'):item['label']='Section dimension '+item['name'][3:]+' (baseline '+item.get('label',item['name'])+')'
        if item['rawGroup']=='Connection':
            import native_connection_controls
            owner=native_connection_controls.owner_label(v,v.GetParmContainer(p)) or owner
        if item['rawGroup']=='FeaLayer':
            import native_material_controls
            owner=native_material_controls.owner_label(v,p) or owner
        if item['rawGroup'] in ('FeaLayer','FeaMaterial'):
            item['studyNote']='Material models and declared input units are applied before property and layer values. Values use each case’s declared native units; workspace display conversion is not applied. Prepare a baseline laminate containing every layer to sweep; calculated solver properties remain outputs.'
        named=cap_choices.get(p)
        title=named['label']+' ('+item['name']+')' if named else item.get('label',item['name'])
        item['label']=' / '.join(([geometry[p]] if p in geometry and geometry[p]!=owner else [])+[owner,item['group'],title])
        if named:item['choices']=copy.deepcopy(named['choices'])
        item['integer']=item['type'] in (v.PARM_INT_TYPE,v.PARM_BOOL_TYPE,v.PARM_LIMITED_INT_TYPE,v.PARM_POWER_INT_TYPE)
        reason=disk_fields.get(p) or wing_fields.get(p) or body_fields.get(p) or skin_fields.get(p) or attachment_fields.get(p) or blade_fields.get(p) or cap_fields.get(p) or profile_fields.get(p) or gear_fields.get(p) or family_fields.get(p) or native_prop_drivers.group_read_only_reason(v,p)
        reason=reason or human_fields.get(p)
        if reason:item.update(editable=False,readOnlyReason=reason)
        if p in rotor_fields:item['rotorBinding']=rotor_fields[p]
        if p in family_dependencies:
            item['modelingStudy']=family_dependencies[p]
            item['studyNote']='Controller axes are applied before dependent values. Include compatible controller choices; cases where OpenVSP keeps the field calculated stop before analysis. Joint limits are checked after this case’s limit controls are applied.'
            if v.GetParmContainer(p) in v.FindGeoms() and v.GetGeomTypeName(v.GetParmContainer(p)).upper() in ('PROP','PROPELLER'):
                item['studyNote']='Spacing, pitch and folding modes are applied before their blade values. Uniform spacing and the final two balanced blade angles remain calculated. Blade-count changes can remove native fields; choose a saved aircraft containing the blades to sweep.'
            if p in case_metadata:
                item['studyNote']='Case calculation, projection direction, symmetric rotation and automatic bounds are applied before dependent values. Include compatible controller choices; cases where OpenVSP calculates the field stop before analysis. Values use native model units and degrees.'
            if item['rawGroup']=='Connection':item['studyNote']='The connection mode is applied before its custom degrees of freedom. Include Custom in a mode axis to sweep these constraints; preset-mode cases keep their original calculated mask and stop before manual assignment.'
            if item['rawGroup']=='FeaBC':item['studyNote']='The boundary mode is applied before custom degrees of freedom. Include Custom in a mode axis to sweep these constraints. Coordinate limits use native model units and affect nodes only when their filter is enabled.'
            if item['rawGroup']=='FeaMaterial':item['studyNote']='Material models are applied before their independent properties. Include compatible model choices; cases where the engine derives the property stop before assignment. Declared material units apply to that case’s values without workspace conversion.'
            if item['rawGroup']=='FeaProperty':item['studyNote']='Property model, beam section and declared units apply before dimensions or entered section values. Shaped beam sections calculate area and inertias; General allows entered values. An assigned laminate supplies thickness and units until its material model changes. Values use native declared units.'
            if item['rawGroup'] in ('FeaPart','FeaRib','FeaSpar','FeaSlice','FeaRibArray','FeaSliceArray'):item['studyNote']='Placement units, orientation and array direction apply before driving positions or spacing. OpenVSP refreshes structural limits and linked values after each assignment. Fractions are dimensionless; absolute inputs use native model units. Include compatible controller choices; linked positions and unselected rotation axes remain calculated.'
            if item['rawGroup']=='SubSurface' or item['rawGroup'].startswith('SS_'):item['studyNote']='Region coordinate bases, distance units and matching flags apply before driving boundary values. Include compatible controller choices; linked coordinates, distances and angles remain calculated. Native surface coordinates are parameters, not physical lengths.'
            if item['rawGroup']=='FEAGridDensity':item['studyNote']='Sizing bases apply before geometry and maximum edge drivers; minimum edge and gap drivers follow them. Original structural updates calculate linked values using the native component size and structural scale. Absolute values use native structural units; fractions are dimensionless. Include compatible basis controllers to sweep linked baseline fields.'
        if p in human_dependencies:
            item['humanStudy']=human_dependencies[p]
            notes=[]
            condition=item['humanStudy'].get('condition')
            if condition:notes.append('Include '+condition['label']+' in a controller axis to sweep this field. Cases that keep it calculated stop before analysis.')
            if item['humanStudy'].get('unitControllers'):notes.append('Requested values use each case’s native Human units after unit axes are applied. No display-unit conversion is applied; mixed-unit values must be interpreted with their unit axes.')
            if item['humanStudy'].get('limitControllers'):notes.append('Human length units are applied before stature; each case is checked against the resulting original native limits.')
            item['studyNote']=' '.join(notes)
        frame=native_gear_controls.cg_coordinate(v,p)
        if frame:
            item['cgFrame']=frame
            item['studyNote']='CG coordinates are editable in '+frame['label']+'. A CG coordinate-frame axis is applied first; cases using the other frame stop before analysis because these coordinates are native calculated outputs.'
        if native_gear_controls.cg_range_controller(v,p):
            item['studyNote']+=' OpenVSP limits this range using the nominal CG. If that nominal coordinate is also swept, Studio applies it first and checks the range against each case’s native limits.'
        params.append(item)
    return dict(version=v.GetVSPVersion(),parameters=sorted(params,key=lambda p:(p['label'],p['id'])),
                structures=[dict(id=s,name=v.GetFeaStructName(v.GetFeaStructParentGeomID(s),v.GetFeaStructIndex(s))) for s in v.GetFeaStructIDVec()],
                assemblies=[dict(id=a,name=v.GetFeaAssemblyName(a)) for a in v.GetFeaAssemblyIDVec()],
                sets=[dict(index=i,name=v.GetSetName(i)) for i in range(v.GetNumSets())])


def stage_schema(v,stage,analysis_schema,set_inputs):
    name=stage['name']
    if name=='FlowPlaneSlicer':
        import native_flow_slices
        spec=native_flow_slices.inputs(v,stage);spec['defaultInputs']=native_flow_slices.schema(v)['inputs'];return spec
    if name in native_analytical.NAMES:
        defaults=native_analytical.schema(v,name)['inputs'];spec,_=native_analytical.inputs(v,stage);spec['defaultInputs']=defaults;return spec
    if name in ('FeaMeshAnalysis','FeaAssemblyMesh'):
        spec=(native_mesh.fea_schema if name=='FeaMeshAnalysis' else native_mesh.assembly_schema)(v,stage.get('structure'))
        # The structural schema includes engine inputs plus native export choices.
        known={(e['name'],e['index']):e for e in spec['inputs']}
        check_entries(v,stage.get('inputs',[]),known)
        if name=='FeaAssemblyMesh':
            entries=native_mesh.assembly_inputs(stage,spec['members'])
            for sid in spec['members']:
                _,gid,index=native_mesh.structure(v,sid)
                native_mesh.sizing(v,gid,index,entries[sid],apply=False)
                member=next(m for m in spec['guide']['memberSizing'] if m['id']==sid)
                for entry in entries[sid]:
                    member['values'][entry['name']]=entry['values'][0]
                    field=next(e for e in member['inputs'] if e['name']==entry['name'])
                    field['values']=copy.deepcopy(entry['values'])
        if any(f not in spec['exportFormats'] for f in stage.get('formats',[])):raise ValueError('Choose supported structural exports.')
        spec['defaultInputs']=copy.deepcopy(spec['inputs'])
        for entry in stage.get('inputs',[]):known[(entry['name'],entry.get('index',0))]['values']=copy.deepcopy(entry['values'])
        return spec
    defaults=analysis_schema(v,name)['inputs'];set_inputs(v,name,stage.get('inputs',[]),validate_guides=False);spec=analysis_schema(v,name,reset=False);spec['defaultInputs']=defaults
    if name in ('VSPAEROSweep','VSPAEROSinglePoint'):
        spec['geometrySchema']=analysis_schema(v,'VSPAEROComputeGeometry')
        spec['defaultGeometryInputs']=copy.deepcopy(spec['geometrySchema']['inputs']);set_inputs(v,'VSPAEROComputeGeometry',stage.get('geometryInputs',[]))
        spec['geometryInputs']=analysis_schema(v,'VSPAEROComputeGeometry',reset=False)['inputs']
        spec['preparedSingleGeomID']=next((e['values'][0] for e in spec['geometryInputs'] if e['name']=='SingleGeomID'), '')
    elif stage.get('geometryInputs'):raise ValueError('Geometry-preparation inputs require an aerodynamic solver step.')
    return spec


def check_entries(v,entries,known):
    if not isinstance(entries,list) or len(entries)>1000:raise ValueError('Use a list of native analysis inputs.')
    seen=set()
    for e in entries:
        key=(e.get('name'),e.get('index',0));values=e.get('values')
        if key not in known or key in seen:raise ValueError('Choose unique, known native analysis inputs.')
        seen.add(key);kind=known[key]['type']
        if not isinstance(values,list) or len(values)>10000:raise ValueError('Use native input arrays of at most 10000 values.')
        if kind in (v.INT_DATA,v.DOUBLE_DATA):
            for x in values:
                finite(x)
                if kind==v.INT_DATA and (not isinstance(x,int) or isinstance(x,bool)):raise ValueError('This native input requires integers.')
        elif kind==v.STRING_DATA:
            if any(not isinstance(x,str) for x in values):raise ValueError('This native input requires strings.')
        elif kind==v.VEC3D_DATA:
            for p in values:
                if not isinstance(p,list) or len(p)!=3:raise ValueError('This native input requires XYZ vectors.')
                for x in p:finite(x)
        else:raise ValueError('This native input is not editable.')


def resolve_sweeps(v,req,spec,key='inputs'):
    """Apply requested values to actual case inputs, preserving untouched values."""
    patches=req.get('inputSweeps',[])
    if not isinstance(patches,list) or len(patches)>10 or any(not isinstance(p,dict) or p.get('kind') not in ('input','geometryInput') for p in patches):raise ValueError('Use up to ten known native input sweeps.')
    kind='input' if key=='inputs' else 'geometryInput'
    patches=[p for p in patches if isinstance(p,dict) and p.get('kind')==kind]
    if not patches:return req
    member_patches=[p for p in patches if p.get('member') is not None]
    if member_patches:
        if kind!='input' or spec.get('name')!='FeaAssemblyMesh':raise ValueError('Member sizing sweeps require a structural assembly step.')
        import native_mesh
        members=spec['guide']['memberSizing'];ids=[m['id'] for m in members]
        if any(p['member'] not in ids for p in member_patches):raise ValueError('A swept assembly member is unavailable in this case.')
        merged=native_mesh.assembly_inputs(req,ids);records=[]
        for member in members:
            fields=copy.deepcopy(member['inputs'])
            for entry in merged[member['id']]:
                next(e for e in fields if e['name']==entry['name'])['values']=copy.deepcopy(entry['values'])
            selected=[{k:x for k,x in p.items() if k!='member'} for p in member_patches if p['member']==member['id']]
            values=[dict(name=e['name'],index=e['index'],values=[int(x) if e['type']==v.INT_DATA and x in (0,1) else x for x in e['values']]) for e in fields]
            resolved=resolve_sweeps(v,dict(inputs=values,inputSweeps=selected),dict(inputs=fields),key)
            records.append(dict(id=member['id'],inputs=resolved['inputs']))
        req={**req,'inputs':[],'memberInputs':records}
        patches=[p for p in patches if p.get('member') is None]
        if not patches:return req
    known={(e['name'],e['index']):copy.deepcopy(e) for e in spec['inputs']}
    entries=copy.deepcopy(req.get(key,[]));check_entries(v,entries,known)
    for e in entries:known[(e['name'],e.get('index',0))]['values']=copy.deepcopy(e['values'])
    for p in patches:
        binding=(p.get('name'),p.get('index',0));e=known.get(binding)
        if not e or not e.get('editable',True):raise ValueError('A swept native input is unavailable in this case.')
        if p.get('valueMode','element')=='array':e['values']=copy.deepcopy(p['value'])
        elif p.get('valueMode','element')=='element':
            element=p.get('element',0);component=p.get('component')
            if isinstance(element,bool) or not isinstance(element,int) or not 0<=element<len(e['values']):raise ValueError('The selected native input value is unavailable in this case.')
            if component is None:e['values'][element]=copy.deepcopy(p['value'])
            else:
                if e['type']!=v.VEC3D_DATA or isinstance(component,bool) or not isinstance(component,int) or not 0<=component<3:raise ValueError('Choose a native vector coordinate.')
                e['values'][element][component]=p['value']
        else:raise ValueError('Choose one native input value or its entire array.')
        item=dict(name=e['name'],index=e['index'],values=copy.deepcopy(e['values']));check_entries(v,[item],known)
        previous=next((x for x in entries if (x['name'],x.get('index',0))==binding),None)
        if previous:previous['values']=item['values']
        else:entries.append(item)
    return {**req,key:entries}


def validate(v,req,parameter,analysis_schema,set_inputs):
    stages=req.get('stages');axes=req.get('axes')
    if not isinstance(stages,list) or not 1<=len(stages)<=20:raise ValueError('Add 1–20 native analysis steps.')
    if not isinstance(axes,list) or len(axes)>10:raise ValueError('Use up to 10 sweep dimensions.')
    specs=[];clean_stages=[]
    for i,stage in enumerate(stages):
        if not isinstance(stage,dict):raise ValueError('Choose a native analysis for every step.')
        stage={k:copy.deepcopy(stage[k]) for k in ('name','inputs','memberInputs','geometryInputs','structure','formats','sourceStage','freezeInputs') if k in stage}
        if stage.get('name')=='VSPAEROSinglePoint':
            raise ValueError('OpenVSP retired VSPAEROSinglePoint. In Studies, replace this step with the supported single-condition solver, then save. It uses VSPAEROSweep with AlphaNpts, BetaNpts, MachNpts and ReCrefNpts set to one.')
        if stage.get('name')=='VSPAERODegenGeom':
            raise ValueError('OpenVSP retired VSPAERODegenGeom. Replace this step with supported VSPAERO geometry preparation (VSPAEROComputeGeometry), review the thin and thick geometry selections, then save.')
        source=stage.get('sourceStage')
        if source is not None:
            if isinstance(source,bool) or not isinstance(source,int) or not 0<=source<i or stage['name'] not in ('CpSlicer','VSPAEROReadPreviousAnalysis','FlowPlaneSlicer'):raise ValueError('A saved-solution step must refer to an earlier aerodynamic analysis.')
            if clean_stages[source]['name'] not in ('VSPAEROSweep','VSPAEROSinglePoint'):raise ValueError('Choose an earlier aerodynamic solution as the source.')
        if stage.get('name') in ('CpSlicer','VSPAEROReadPreviousAnalysis','FlowPlaneSlicer') and source is None:raise ValueError('Choose an earlier aerodynamic solution for this study step.')
        spec=stage_schema(v,stage,analysis_schema,set_inputs)
        check_entries(v,stage.get('inputs',[]),{(e['name'],e['index']):e for e in spec['inputs']})
        specs.append(spec);clean_stages.append(stage)
    params={p['id']:p for p in schema(v,parameter)['parameters']};clean_axes=[];seen=set();count=1
    import native_gear_controls
    import native_human_controls
    swept_ids={a.get('id') for a in axes if isinstance(a,dict) and a.get('kind')=='parameter'}
    import native_family_studies
    for a in axes:
        if not isinstance(a,dict):raise ValueError('Choose a sweep dimension.')
        values=a.get('values')
        if not isinstance(values,list) or not 1<=len(values)<=1000:raise ValueError('Give each dimension 1–1000 values.')
        count*=len(values)
        if count>1000:raise ValueError('This study exceeds 1000 cases. Split it into smaller saved studies.')
        kind=a.get('kind')
        if kind=='parameter':
            for x in values:finite(x)
            p=params.get(a.get('id'))
            if not p:raise ValueError('A study parameter no longer exists in its baseline aircraft.')
            if p.get('editable') is False and not (native_gear_controls.study_frame_controlled(v,p['id'],axes) or native_human_controls.study_controlled(v,p['id'],axes) or native_family_studies.controlled(v,p['id'],axes)):
                hint='Choose an editable driver in the study baseline.'
                if p.get('cgFrame'):hint='Choose an editable driver in the study baseline or include its CG coordinate frame as a study axis.'
                if p.get('humanStudy',{}).get('condition'):hint='Include '+p['humanStudy']['condition']['label']+' in a controller axis, or unlock this field in the baseline.'
                if p.get('modelingStudy'):hint='Include compatible controller axes: '+', '.join(dict.fromkeys(c['label'] for branch in p['modelingStudy'].get('alternatives',[p['modelingStudy'].get('conditions',[])]) for c in branch))+'.'
                raise ValueError(p['label']+': '+p['readOnlyReason']+' '+hint)
            for x in values:
                if not native_human_controls.deferred_limits(v,p['id'],swept_ids) and not native_family_studies.deferred_limits(v,p['id'],swept_ids) and not native_gear_controls.study_limits(v,p['id'],x,swept_ids):raise ValueError(p['label']+': value is outside the native parameter limits.')
                if p['integer'] and (not isinstance(x,int) or isinstance(x,bool)):raise ValueError(p['label']+': use integer values.')
                if p.get('choices') is not None and x not in [c['value'] for c in p['choices']]:raise ValueError(p['label']+': choose a supported native option.')
            axis=dict(kind=kind,id=p['id'],values=values,label=p['label'],baseline=p['value'],integer=p['integer'])
            if p.get('modelingStudy'):axis['modelingStudy']=copy.deepcopy(p['modelingStudy'])
            if p.get('humanStudy'):
                axis['humanStudy']=copy.deepcopy(p['humanStudy'])
                if any(c['parameter'] in swept_ids for c in p['humanStudy'].get('unitControllers',[])):
                    title={'Stature':'Stature','Mass':'Body mass','Density':'Body density'}.get(p['name'],p['name'])
                    axis['label']=' / '.join(p['label'].split(' / ')[:-1]+[title])+' · case Human units'
            if p.get('choices') is not None:axis['choices']=copy.deepcopy(p['choices'])
            binding=(kind,p['id'])
        elif kind in ('input','geometryInput'):
            step=a.get('stage');index=a.get('index',0)
            if isinstance(step,bool) or not isinstance(step,int) or not 0<=step<len(specs):raise ValueError('Choose an existing analysis step for this sweep.')
            if isinstance(index,bool) or not isinstance(index,int) or index<0:raise ValueError('Choose a native input data index.')
            member=a.get('member')
            if member is not None:
                if kind!='input' or clean_stages[step]['name']!='FeaAssemblyMesh':raise ValueError('Choose an assembly step for member sizing.')
                selected=next((m for m in specs[step]['guide']['memberSizing'] if m['id']==member),None)
                if selected is None:raise ValueError('Choose an existing assembly member to sweep.')
                entries=selected['inputs']
            else:
                entries=specs[step]['inputs' if kind=='input' else 'geometryInputs'] if kind=='input' or 'geometryInputs' in specs[step] else []
            e=next((e for e in entries if e['name']==a.get('name') and e['index']==index),None)
            if not e or not e.get('editable',True) or e['type'] not in (v.INT_DATA,v.DOUBLE_DATA,v.STRING_DATA,v.VEC3D_DATA):raise ValueError('Choose an editable native input to sweep.')
            mode=a.get('valueMode','element');element=a.get('element',0);component=a.get('component')
            if mode not in ('element','array'):raise ValueError('Choose one input value or its entire native array.')
            if component is not None and (e['type']!=v.VEC3D_DATA or isinstance(component,bool) or not isinstance(component,int) or not 0<=component<3):raise ValueError('Choose the X, Y or Z coordinate to sweep.')
            if mode=='array':
                if component is not None:raise ValueError('An entire array sweep cannot also select a vector coordinate.')
                baseline=copy.deepcopy(e['values']);selector=('array',)
            else:
                if isinstance(element,bool) or not isinstance(element,int) or not 0<=element<len(e['values']):raise ValueError('Choose an existing value in the native input array.')
                baseline=copy.deepcopy(e['values'][element] if component is None else e['values'][element][component]);selector=('element',element,component)
            field=(kind,step,e['name'],index)
            for old in clean_axes:
                if old['kind']=='parameter' or (old['kind'],old['stage'],old['name'],old['index'])!=field:continue
                if member is not None and old.get('member') is not None and member!=old['member']:continue
                if mode=='array' or old.get('valueMode','element')=='array' or element==old.get('element',0) and (component is None or old.get('component') is None or component==old['component']):raise ValueError('Sweep dimensions cannot overwrite the same native input value.')
            for x in values:
                candidate=copy.deepcopy(e['values'])
                if mode=='array':candidate=x
                elif component is None:candidate[element]=x
                else:candidate[element][component]=finite(x)
                check_entries(v,[dict(name=e['name'],index=index,values=candidate)],{(e['name'],index):e})
                # Guided slice planes and supplied area distributions are
                # native arrays. A guide alone does not make an input scalar.
                array_input=e.get('numericList') or clean_stages[step]['name']=='EmintonLord' or e['name']=='SSFlow_vec'
                if (specs[step].get('guide') and not array_input or specs[step].get('standaloneNative')) and len(candidate)!=1:raise ValueError(e['name']+': this native workflow requires one input value.')
                for value in candidate:
                    if e.get('choices') is not None and value not in [c['value'] for c in e['choices']]:raise ValueError(e.get('label',e['name'])+': choose a supported native option.')
                    if e.get('choiceList') is not None and value not in [c['value'] for c in e['choiceList']]:raise ValueError(e['name']+': choose an existing native reference.')
                    if e['type'] in (v.INT_DATA,v.DOUBLE_DATA) and ('min' in e and e['min'] is not None and value<e['min'] or 'max' in e and e['max'] is not None and value>e['max']):raise ValueError(e.get('label',e['name'])+': value is outside the native setting limits.')
            binding=(*field,member,*selector)
            integer=e['type']==v.INT_DATA
            suffix=' / entire array' if mode=='array' else (' / value '+str(element+1) if len(e['values'])>1 else '')+(' / '+['X','Y','Z'][component] if component is not None else ' / XYZ vector' if e['type']==v.VEC3D_DATA else '')
            axis=dict(kind=kind,stage=step,name=e['name'],index=index,valueMode=mode,component=component,type=e['type'],values=copy.deepcopy(values),baseline=baseline,integer=integer,baseValues=copy.deepcopy(e['values']),
                      label=f'Step {step+1} · {clean_stages[step]["name"]} / '+('Geometry / ' if kind=='geometryInput' else '')+e['name']+suffix)
            if mode=='element':axis['element']=element
            if member is not None:
                axis['member']=member
                axis['label']=f'Step {step+1} · '+selected['name']+' / '+e['name']+suffix
            for key in ('choices','choiceList','min','max'):
                if key in e:axis[key]=copy.deepcopy(e[key])
        else:raise ValueError('Choose a native parameter or analysis input to sweep.')
        if binding in seen:raise ValueError('A native field can only appear once in a study.')
        seen.add(binding);clean_axes.append(axis)
    # Swept values supersede the displayed setup. Validate a real first case,
    # so a swept reference is not rejected solely for its unused blank default.
    import native_guides
    for step,spec in enumerate(specs):
        candidate=copy.deepcopy(spec)
        for axis in clean_axes:
            if axis['kind']!='input' or axis['stage']!=step:continue
            if axis.get('member') is not None:continue
            entry=next(e for e in candidate['inputs'] if e['name']==axis['name'] and e['index']==axis['index']);value=axis['values'][0]
            if axis['valueMode']=='array':entry['values']=copy.deepcopy(value)
            elif axis['component'] is None:entry['values'][axis['element']]=copy.deepcopy(value)
            else:entry['values'][axis['element']][axis['component']]=value
        native_guides.validate(v,clean_stages[step]['name'],candidate)
    return dict(version=v.GetVSPVersion(),axes=clean_axes,stages=clean_stages,stageSchemas=specs,caseCount=count)


def prepare(v,req,model,errors):
    import native_property_locks
    locked=native_property_locks.records(v)
    import native_wave_controls
    native_wave_controls.refresh(v)
    import native_parasite_controls
    native_parasite_controls.refresh(v)
    import native_part_controls
    native_part_controls.refresh(v)
    import native_human_controls
    import native_family_studies
    import native_profile_controls
    native_profile_controls.refresh(v)
    records=[];allowed=parameter_ids(v);seen=set()
    import native_gear_controls
    swept_ids={item.get('id') for item in req.get('parameters',[])}
    for item in req.get('parameters',[]):
        pid=item.get('id');value=finite(item.get('value'))
        if pid in seen or pid not in allowed or not v.ValidParm(pid):raise ValueError('Choose unique native study parameters.')
        seen.add(pid)
        if not native_human_controls.deferred_limits(v,pid,swept_ids) and not native_family_studies.deferred_limits(v,pid,swept_ids) and not native_gear_controls.study_limits(v,pid,value,swept_ids):raise ValueError('A case value is outside its native parameter limits.')
        integer=v.GetParmType(pid) in (v.PARM_INT_TYPE,v.PARM_BOOL_TYPE,v.PARM_LIMITED_INT_TYPE,v.PARM_POWER_INT_TYPE)
        if integer and (not isinstance(value,int) or isinstance(value,bool)):raise ValueError('This native parameter requires an integer.')
        records.append(dict(id=pid,requested=value,baseline=v.GetParmVal(pid)))
    import native_prop_drivers
    import native_end_caps
    import native_profile_controls
    # Apply native activity/coupling controllers before dependent rotor values
    # regardless of axis order. The engine still evaluates every dependency.
    import native_gear_retraction
    def priority(item):
        import native_human_controls
        if native_human_controls.human(v,item['id']):
            if v.GetParmName(item['id'])=='GenderFlag':return -30
            if v.GetParmName(item['id']) in ('LenUnit','MassUnit'):return -20
            if v.GetParmName(item['id']) in ('RLSym','AutoDensity'):return -10
        cg=native_gear_controls.study_priority(v,item['id'])
        if cg is not None:return cg
        gear=native_gear_retraction.controller_priority(v,item['id'])
        if gear is not None:return gear
        family=native_family_studies.priority(v,item['id'])
        if family is not None:return family
        return 0 if v.GetParmName(item['id']) in ('AutoHubDiaFlag','UniformPropRPMFlag') or native_end_caps.controller(v,item['id']) else native_profile_controls.controller_priority(v,item['id'])
    ordered=sorted(records,key=priority)
    def require_case_parameter(item):
        # Native group enumeration refreshes groups after representation edits.
        # Check identity after that refresh, before reading or writing the parm.
        v.GetNumUnsteadyGroups();v.GetNumActuatorDisks()
        if not v.ValidParm(item['id']):
            raise ValueError('A swept parameter became unavailable after native geometry changes in this case. Propeller representation changes can regenerate rotor groups. Split representation and rotor-speed sweeps into separate studies using their own saved aircraft.')
    for item in ordered:
        require_case_parameter(item)
        import native_scale_controls
        native_scale_controls.validate_parameter(v,item['id'])
        import native_connection_controls
        if v.GetParmGroupName(item['id'])=='Connection':v.Update()
        native_connection_controls.validate_parameter(v,item['id'],item['requested'])
        import native_boundary_controls
        native_boundary_controls.validate_parameter(v,item['id'])
        import native_material_controls
        native_material_controls.validate_parameter(v,item['id'])
        import native_property_controls
        native_property_controls.validate_parameter(v,item['id'])
        import native_element_controls
        native_element_controls.validate_parameter(v,item['id'])
        import native_part_controls
        native_part_controls.refresh(v,pid=item['id'])
        native_part_controls.validate_parameter(v,item['id'],item['requested'])
        import native_region_controls
        native_region_controls.validate_parameter(v,item['id'])
        import native_fea_sizing
        native_fea_sizing.validate_parameter(v,item['id'])
        import native_cfd_density
        native_cfd_density.validate_parameter(v,item['id'])
        import native_export_controls
        native_export_controls.validate_parameter(v,item['id'])
        native_parasite_controls.validate_parameter(v,item['id'],item['requested'])
        native_wave_controls.validate_parameter(v,item['id'],item['requested'])
        import native_measurements
        native_measurements.validate_parameter(v,item['id'])
        import native_human_controls
        native_human_controls.validate_parameter(v,item['id'],study=True)
        if native_human_controls.deferred_limits(v,item['id'],swept_ids) and not v.GetParmLowerLimit(item['id'])<=item['requested']<=v.GetParmUpperLimit(item['id']):
            raise ValueError('The requested Human stature is outside the native limits after applying this case’s body model and length units.')
        native_prop_drivers.validate_parameter(v,item['id'])
        import native_prop_controls
        native_prop_controls.validate_parameter(v,item['id'])
        import native_wing_controls
        native_wing_controls.validate_parameter(v,item['id'])
        import native_body_controls
        native_body_controls.validate_parameter(v,item['id'])
        import native_skinning_controls
        native_skinning_controls.validate_parameter(v,item['id'])
        import native_attachments
        native_attachments.validate_parameter(v,item['id'])
        import native_family_controls
        native_family_controls.validate_parameter(v,item['id'])
        import native_case_studies
        native_case_studies.validate(v,item['id'])
        if native_family_studies.deferred_limits(v,item['id'],swept_ids) and not v.GetParmLowerLimit(item['id'])<=item['requested']<=v.GetParmUpperLimit(item['id']):
            raise ValueError('The requested dependent value is outside the native limits after applying this case’s controllers.')
        native_end_caps.validate_parameter(v,item['id'],item['requested'])
        native_profile_controls.validate_parameter(v,item['id'],item['requested'])
        import native_gear_controls
        native_gear_controls.validate_parameter(v,item['id'],item['requested'])
        if native_gear_controls.cg_range_controller(v,item['id']) and not v.GetParmLowerLimit(item['id'])<=item['requested']<=v.GetParmUpperLimit(item['id']):
            raise ValueError('The requested '+native_gear_controls.LABELS[v.GetParmName(item['id'])]+' is outside the native range limits after applying this case’s nominal CG. Choose a minimum at or below nominal and a maximum at or above nominal.')
        if not native_parasite_controls.set_parameter(v,item['id'],item['requested']):v.SetParmValUpdate(item['id'],item['requested'])
        native_parasite_controls.refresh(v)
        native_wave_controls.refresh(v)
        native_case_studies.refresh(v,item['id']);errors(v)
        native_part_controls.refresh(v,pid=item['id'])
        native_region_controls.refresh(v,item['id'])
        native_fea_sizing.refresh(v,item['id'])
        native_cfd_density.refresh(v)
        if v.GetParmGroupName(item['id'])=='FeaBC':native_boundary_controls.refresh(v,v.GetParmContainer(item['id']))
        if v.GetParmGroupName(item['id']) in ('FeaMaterial','FeaLayer','FeaProperty') or (v.GetParmGroupName(item['id'])=='FeaStructure' and v.GetParmName(item['id'])=='StructUnit'):v.Update()
    v.Update()
    import native_gear_controls
    import native_gear_retraction
    native_gear_retraction.refresh(v)
    native_gear_controls.refresh_auxiliary(v)
    import native_measurements
    native_measurements.refresh(v)
    errors(v)
    for item in records:
        require_case_parameter(item)
        item['effective']=v.GetParmVal(item['id'])
    native_property_locks.require_unchanged(v,locked)
    v.WriteVSPFile(str(model),v.SET_ALL);errors(v)
    return dict(version=v.GetVSPVersion(),parameters=records,warnings=[f'{x["id"]}: requested {x["requested"]}, native value {x["effective"]} after dependencies.' for x in records if not math.isclose(x['requested'],x['effective'],rel_tol=1e-10,abs_tol=1e-12)])
