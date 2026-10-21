"""Guided native meshing setup and export verification."""
from pathlib import Path
from native_tools import one,finite
from mesh_io import read_gmsh

FEA_INPUTS={'BaseLen':'CFD_MAX_EDGE_LEN','MinLen':'CFD_MIN_EDGE_LEN','MaxGap':'CFD_MAX_GAP','NCircSeg':'CFD_NUM_CIRCLE_SEGS','GrowthRatio':'CFD_GROWTH_RATIO','RigorLimit':'CFD_LIMIT_GROWTH_FLAG','HalfMeshFlag':'CFD_HALF_MESH_FLAG'}
FEA_EXPORTS={'GMSH':'msh','CALCULIX':'inp','NASTRAN':'bdf','NKEY':'nkey','MASS':'txt','STL':'stl','SRF':'srf','CURV':'curv','PLOT3D':'p3d','IGES':'igs','STEP':'stp'}
ASSEMBLY_EXPORTS={n:FEA_EXPORTS[n] for n in ['GMSH','CALCULIX','NASTRAN','MASS','STL']}
FEA_PARAMETERS={n:('HalfMesh','FarField') if n=='HalfMeshFlag' else ('GrowRatio' if n=='GrowthRatio' else n,'FEAGridDensity') for n in FEA_INPUTS}
FEA_LABELS={'BaseLen':'Maximum edge length','MinLen':'Minimum edge length','MaxGap':'Surface approximation gap','NCircSeg':'Circle segmentation','GrowthRatio':'Mesh growth ratio','RigorLimit':'Growth limiting','HalfMeshFlag':'Geometry half'}
FEA_SETTINGS={
    'BaseAbsRel':('BaseAbsRel','FEAGridDensity','Maximum edge length basis','Choose an absolute native length or a fraction of the native parent-component size and structural scale.'),
    'BaseLenFrac':('BaseLenFrac','FEAGridDensity','Maximum edge length fraction','Dimensionless fraction of the native parent-component size.'),
    'MinAbsRel':('MinAbsRel','FEAGridDensity','Minimum edge length basis','Choose an absolute native length or a fraction of the current maximum edge length.'),
    'MinFrac':('MinFrac','FEAGridDensity','Minimum edge length fraction','Dimensionless fraction of the native maximum edge length.'),
    'MaxGapAbsRel':('MaxGapAbsRel','FEAGridDensity','Surface gap basis','Choose an absolute native gap or a fraction of the current maximum edge length.'),
    'MaxGapFrac':('MaxGapFrac','FEAGridDensity','Surface gap fraction','Dimensionless fraction of the native maximum edge length.'),
    'ConvertToQuadsFlag':('ConvertToQuadsFlag','Global','Element shapes','Convert the native triangle mesh to quadrilaterals where supported.'),
    'HighOrderElementFlag':('HighOrderElementFlag','Global','Element order','Promote native elements to high order.'),
    'IntersectSubSurfs':('IntersectSubSurfs','Global','Intersect surface regions','Include native surface-region boundaries in intersection processing.'),
    'RelCurveTol':('RelCurveTol','Global','Relative intersection curve tolerance','Original relative tolerance for native intersection curves.'),
    'DemoteSurfsCubicFlag':('DemoteSurfsCubicFlag','Global','Convert surfaces to cubic','Use the original cubic surface approximation before intersection.'),
    'CubicSurfTolerance':('CubicSurfTolerance','Global','Cubic surface tolerance','Native surface approximation tolerance; used when cubic conversion is enabled.'),
    'NodeOffset':('NodeOffset','StructSettings','Node ID offset','Offset added to original exported node identifiers.'),
    'ElementOffset':('ElementOffset','StructSettings','Element ID offset','Offset added to original exported element identifiers.'),
    'BeamPerElementNormal':('BeamPerElementNormal','StructSettings','CalculiX beam normals','Choose per-element or per-part beam normals in the native CalculiX deck.'),
}
FEA_PARAMETERS.update({n:(field,group) for n,(field,group,_,_) in FEA_SETTINGS.items()})
FEA_LABELS.update({n:label for n,(_,_,label,_) in FEA_SETTINGS.items()})
FEA_SETTING_CHOICES={'ConvertToQuadsFlag':['Triangles','Convert to quadrilaterals'],'HighOrderElementFlag':['Linear elements','High-order elements'],'IntersectSubSurfs':['Skip region intersections','Intersect region boundaries'],'DemoteSurfsCubicFlag':['Original surfaces','Cubic surface approximation'],'BeamPerElementNormal':['Per-part beam normals','Per-element beam normals']}
FEA_CAD={
    'CADLenUnit':('CAD file length units','Native IGES/STEP output units, independent of workspace display units.'),
    'STEPTol':('STEP point tolerance','Original native STEP tolerance.'),
    'STEP':('Merge STEP points','Original native STEP point merging.'),
    'STEPRepresentation':('STEP representation','Export original native shell or BREP representation.'),
    'CADLabelName':('Include component name','Include native component names in CAD labels.'),
    'CADLabelID':('Include component ID','Include native component IDs in CAD labels.'),
    'CADLabelSurfNo':('Include surface number','Include native surface numbers in CAD labels.'),
    'CADLabelSplitNo':('Include split number','Include native split numbers in CAD labels.'),
    'CADLabelDelim':('CAD label separator','Separator used in original CAD labels.'),
    'ExportRawFlag':('Curve export samples','Choose original raw or adapted intersection curve samples.'),
    'SRF_XYZIntCurve':('Include XYZ intersection curves','Include original XYZ intersection curves in native surface data.'),
}
FEA_SETTINGS.update({n:(n,'ExportFEA',label,description) for n,(label,description) in FEA_CAD.items()})
FEA_PARAMETERS.update({n:(n,'ExportFEA') for n in FEA_CAD})
FEA_LABELS.update({n:label for n,(label,_) in FEA_CAD.items()})
FEA_SETTING_CHOICES.update({'STEP':['Keep separate points','Merge coincident points'],'ExportRawFlag':['Adapted curves','Raw intersection samples'],'SRF_XYZIntCurve':['Surface data only','Include XYZ intersection curves']})
FEA_PAIRS={'BaseAbsRel':('BaseLen','BaseLenFrac'),'MinAbsRel':('MinLen','MinFrac'),'MaxGapAbsRel':('MaxGap','MaxGapFrac')}


def annotate(field,v=None):
    setting=FEA_SETTINGS.get(field['name'])
    if not setting or field['rawGroup']!=setting[1]:return
    if v is not None:
        import native_fea_sizing
        if not native_fea_sizing.owns(v,field['id']):return
    field['label']=setting[2]
    if field['name'] in FEA_SETTING_CHOICES:field['choices']=[dict(value=i,label=l) for i,l in enumerate(FEA_SETTING_CHOICES[field['name']])]
    if v is not None:
        choices=cad_choices(v).get(field['name'])
        if choices:field['choices']=choices


def cad_choices(v):
    pairs={'CADLenUnit':[('LEN_MM','mm'),('LEN_CM','cm'),('LEN_M','m'),('LEN_IN','in'),('LEN_FT','ft'),('LEN_YD','yd')],'CADLabelDelim':[('DELIM_COMMA','Comma'),('DELIM_USCORE','Underscore'),('DELIM_SPACE','Space'),('DELIM_NONE','No separator')],'STEPRepresentation':[('STEP_SHELL','Shell'),('STEP_BREP','BREP solid')]}
    return {n:[dict(value=getattr(v,k),label=l) for k,l in values] for n,values in pairs.items()}


def sizing_parameters(v,sid):
    """Resolve the original structure's sizing parameters and native limits."""
    parameters=list(v.FindContainerParmIDs(sid));result={}
    for name,(native_name,group) in FEA_PARAMETERS.items():
        matches=[p for p in parameters if v.GetParmName(p)==native_name and v.GetParmGroupName(p)==group]
        if len(matches)!=1:raise ValueError('Native structural sizing parameter unavailable: '+name)
        result[name]=matches[0]
    return result


def formats(req,supported=FEA_EXPORTS):
    selected=req.get('formats',['GMSH'])
    if not isinstance(selected,list) or len(selected)>len(supported):raise ValueError('Select supported structural export formats.')
    return list(dict.fromkeys(['GMSH']+[one(f,supported,'This structural workflow does not export '+str(f)+'.') for f in selected]))


def point_mass_export(v,structures,selected):
    if any(v.GetFeaPartType(p)==v.FEA_FIX_POINT and v.GetParmVal(v.FindParm(p,'FixPointMassFlag','FeaFixPoint')) for s in structures for p in v.GetFeaPartIDVec(s)):
        if 'NASTRAN' not in selected:selected.append('NASTRAN')
        return True
    return False


def sizing(v,gid,index,entries,apply=True):
    parameters=sizing_parameters(v,v.GetFeaStructID(gid,index));pending={}
    for e in entries:
        n=one(e['name'],FEA_PARAMETERS);values=e['values']
        if n in pending or e.get('index',0)!=0:raise ValueError('Choose unique structural sizing inputs at index 0.')
        if not isinstance(values,list) or len(values)!=1:raise ValueError('Mesh sizing needs one value per input.')
        x=finite(values[0])
        if n in ('RigorLimit','HalfMeshFlag'):
            if x not in (0,1): raise ValueError('Mesh flags must be 0 or 1.')
        elif n in FEA_INPUTS and x<=0:raise ValueError('Mesh sizing must be positive.')
        p=parameters[n]
        if v.GetParmType(p) in (v.PARM_INT_TYPE,v.PARM_BOOL_TYPE,v.PARM_LIMITED_INT_TYPE) and int(x)!=x:raise ValueError(FEA_LABELS[n]+': use a native integer setting.')
        if not v.GetParmLowerLimit(p)<=x<=v.GetParmUpperLimit(p):
            raise ValueError(FEA_LABELS[n]+': use the native range '+str(v.GetParmLowerLimit(p))+' to '+str(v.GetParmUpperLimit(p))+'.')
        pending[n]=x
    mode=lambda n:pending.get(n,v.GetParmVal(parameters[n]))
    followers={pair[1] if mode(controller)==v.ABS else pair[0] for controller,pair in FEA_PAIRS.items()}
    current=lambda n:pending.get(n,v.GetFeaMeshVal(gid,index,getattr(v,FEA_INPUTS[n])))
    if mode('BaseAbsRel')==v.ABS and mode('MinAbsRel')==v.ABS and current('MinLen')>current('BaseLen'):
        raise ValueError('Minimum edge length cannot exceed maximum edge length.')
    if apply:
        for n,x in pending.items():
            if n in followers:continue
            if n in FEA_INPUTS:v.SetFeaMeshVal(gid,index,getattr(v,FEA_INPUTS[n]),x)
            else:v.SetParmVal(parameters[n],x)
        v.Update()
        import native_part_controls
        native_part_controls.refresh(v,v.GetFeaStructID(gid,index))
        if v.GetParmVal(parameters['MinLen'])>v.GetParmVal(parameters['BaseLen']):raise ValueError('The native minimum edge length exceeds the native maximum edge length after sizing modes are applied.')


def structure(v,sid=None):
    ids=list(v.GetFeaStructIDVec())
    if not ids: raise ValueError('Create a structure in Modeling tools → Structures first.')
    sid=one(sid or ids[0],ids,'Select an existing structure for this mesh run.')
    return sid,v.GetFeaStructParentGeomID(sid),v.GetFeaStructIndex(sid)


def fea_schema(v,sid=None):
    sid,gid,index=structure(v,sid)
    import native_part_controls
    native_part_controls.refresh(v,sid)
    parameters=sizing_parameters(v,sid);inputs=[]
    descriptions={'BaseLen':'Maximum target edge length in native structural units.','MinLen':'Minimum target edge length in native structural units.','MaxGap':'Maximum surface approximation gap in native structural units.','NCircSeg':'Native circle segmentation target. OpenVSP stores this as a continuous value.','GrowthRatio':'Native limit on the growth of neighboring mesh edge lengths.','RigorLimit':'Apply OpenVSP’s rigorous growth limiting.','HalfMeshFlag':'Choose the whole structure or the original positive-Y half mesh.'}
    for n,e in FEA_INPUTS.items():
        p=parameters[n];entry=dict(name=n,index=0,type=v.INT_DATA if n.endswith(('Flag','Limit')) else v.DOUBLE_DATA,values=[v.GetFeaMeshVal(gid,index,getattr(v,e))],editable=True,label=FEA_LABELS[n],description=descriptions[n],min=v.GetParmLowerLimit(p),max=v.GetParmUpperLimit(p),nativeParameter=p)
        if n=='RigorLimit':entry['choices']=[dict(value=0,label='Standard growth limiting'),dict(value=1,label='Rigorous growth limiting')]
        if n=='HalfMeshFlag':entry['choices']=[dict(value=0,label='Whole structure'),dict(value=1,label='Positive-Y half (Y ≥ 0)')]
        for controller,(absolute,relative) in FEA_PAIRS.items():
            if n==absolute:entry['applicableWhen']=dict(input=controller,values=[v.ABS])
        inputs.append(entry)
    for n,(_,_,label,description) in FEA_SETTINGS.items():
        p=parameters[n];entry=dict(name=n,index=0,type=v.INT_DATA if v.GetParmType(p) in (v.PARM_INT_TYPE,v.PARM_BOOL_TYPE,v.PARM_LIMITED_INT_TYPE) else v.DOUBLE_DATA,values=[v.GetParmVal(p)],editable=True,label=label,description=description,min=v.GetParmLowerLimit(p),max=v.GetParmUpperLimit(p),nativeParameter=p)
        if n in FEA_SETTING_CHOICES:entry['choices']=[dict(value=i,label=l) for i,l in enumerate(FEA_SETTING_CHOICES[n])]
        if n in cad_choices(v):entry['choices']=cad_choices(v)[n]
        if v.GetParmType(p)==v.PARM_BOOL_TYPE and 'choices' not in entry:entry['choices']=[dict(value=0,label='Off'),dict(value=1,label='On')]
        if n in FEA_PAIRS:entry['choices']=[dict(value=v.ABS,label='Absolute · native length'),dict(value=v.REL,label='Relative · fraction')]
        for controller,(absolute,relative) in FEA_PAIRS.items():
            if n==relative:entry['applicableWhen']=dict(input=controller,values=[v.REL])
        inputs.append(entry)
    for entry in inputs:
        if entry.get('applicableWhen'):
            controller=entry['applicableWhen']['input'];basis='absolute length' if entry['name']==FEA_PAIRS[controller][0] else 'relative fraction'
            entry['studyNote']='This input drives sizing only when '+FEA_SETTINGS[controller][2]+' uses '+basis+'. Cases that sweep a calculated sizing value stop before meshing.'
    return dict(name='FeaMeshAnalysis',structure=sid,exportFormats=list(FEA_EXPORTS),description='Generate the selected structure’s mesh with the original OpenVSP engine. All selected formats share one generated native mesh.',inputs=inputs,guide=dict(title='Structural mesh',note='Part geometry, materials, properties and boundary conditions come from the selected saved structure. Absolute lengths use native structural units; relative fractions are dimensionless. Linked sizing values are calculated by OpenVSP.',sensitivityNote='Compare saved runs with finer sizing and review the native mesh and log. Stress calculations use the exported decks in an external structural solver.',sections=[dict(title='Edge lengths and surface accuracy',inputs=['BaseAbsRel','BaseLen','BaseLenFrac','MinAbsRel','MinLen','MinFrac','MaxGapAbsRel','MaxGap','MaxGapFrac']),dict(title='Mesh growth and curved surfaces',inputs=['GrowthRatio','RigorLimit','NCircSeg']),dict(title='Geometry selection',inputs=['HalfMeshFlag']),dict(title='Elements and intersections',inputs=['ConvertToQuadsFlag','HighOrderElementFlag','IntersectSubSurfs','RelCurveTol','DemoteSurfsCubicFlag','CubicSurfTolerance']),dict(title='Solver deck identifiers and beam normals',inputs=['NodeOffset','ElementOffset','BeamPerElementNormal']),dict(title='CAD and curve output',inputs=list(FEA_CAD))]))


def validate_swept_sizing(v,req):
    """A sizing sweep must drive the selected native absolute/relative basis."""
    patches=[p for p in req.get('inputSweeps',[]) if p.get('kind')=='input']
    if not patches:return
    if req['name']=='FeaAssemblyMesh':
        _,members=assembly(v,req.get('structure'));merged=assembly_inputs(req,members)
    else:
        sid,_,_=structure(v,req.get('structure'));members=[sid];merged={sid:req.get('inputs',[])}
    for sid in members:
        parameters=sizing_parameters(v,sid)
        values={n:v.GetParmVal(pid) for n,pid in parameters.items()}
        values.update({e['name']:e['values'][0] for e in merged[sid] if len(e.get('values',[]))==1})
        for patch in patches:
            if patch.get('member') not in (None,sid):continue
            for controller,(absolute,relative) in FEA_PAIRS.items():
                follower,driver=(relative,absolute) if values[controller]==v.ABS else (absolute,relative)
                if patch.get('name')==follower:
                    label=FEA_LABELS.get(follower,FEA_SETTINGS.get(follower,(None,None,follower))[2])
                    target=FEA_LABELS.get(driver,FEA_SETTINGS.get(driver,(None,None,driver))[2])
                    parent=v.GetFeaStructParentGeomID(sid);index=v.GetFeaStructIndex(sid)
                    raise ValueError(v.GetFeaStructName(parent,index)+': '+label+' is calculated in this case. Sweep '+target+' or change '+FEA_SETTINGS[controller][2]+'.')


def run_fea(v,req):
    from native_boundary_results import report as boundary_report
    sid,gid,index=structure(v,req.get('structure'))
    from native_boundary_controls import validate_targets
    validate_targets(v,[sid])
    sizing(v,gid,index,req.get('inputs',[]))
    spec=fea_schema(v,sid)
    selected=formats(req)
    has_masses=point_mass_export(v,[sid],selected)
    for fmt in selected:
        enum=getattr(v,'FEA_'+fmt+'_FILE_NAME')
        # Native NASTRAN treats the supplied name as its .dat SET companion
        # and appends .bdf unless that suffix is .dat. Keep the bulk deck at
        # structure.bdf, rather than silently returning SETs as a .bdf file.
        extension='dat' if fmt=='NASTRAN' else FEA_EXPORTS[fmt]
        v.SetFeaMeshFileName(gid,index,enum,str(Path.cwd()/('structure.'+extension)))
    # The public API clears export flags and regenerates the mesh every call.
    # Generate once, then let the original manager export that same mesh.
    from native_run_setup import save
    save(v,'FeaMeshAnalysis',spec['inputs'],structure=sid,formats=selected)
    v.ComputeFeaMesh(gid,index,v.FEA_GMSH_FILE_NAME)
    if len(selected)>1:
        for p in v.FindContainerParmIDs(sid):
            if v.GetParmGroupName(p)=='ExportFEA' and v.GetParmName(p).endswith('_Export'):
                v.SetParmVal(p,int(v.GetParmName(p)[:-7] in selected))
        import native_preview
        native_preview.export_fea_mesh(v,sid)
    mesh=read_gmsh(Path.cwd()/'structure.msh',Path.cwd()/'structure.bdf' if has_masses else None)
    return dict(version=v.GetVSPVersion(),analysis='FeaMeshAnalysis',engineOperation='ComputeFeaMesh',meshGenerations=1,exportOperation='ExportFeaMesh and ExportCADFiles' if len(selected)>1 else 'ComputeFeaMesh',structure=sid,formats=selected,resultID='',inputs=spec['inputs'],geometryInputs=[],results=[],meshFile='structure.msh',meshSummary=summary(mesh),boundaryReport=boundary_report(v,[sid],selected,Path.cwd()/'structure.inp'))


def assembly(v,aid=None):
    ids=list(v.GetFeaAssemblyIDVec())
    if not ids:raise ValueError('Create an assembly and add member structures in Modeling tools → Assemblies first.')
    aid=one(aid or ids[0],ids,'Select an existing structural assembly.')
    members=list(v.GetFeaAssemblyStructureIDVec(aid))
    if not members:raise ValueError('Add at least one member structure to this assembly.')
    return aid,members


def assembly_schema(v,aid=None,check_connections=True):
    aid,members=assembly(v,aid)
    spec=fea_schema(v,members[0])
    spec['inputs']=[e for e in spec['inputs'] if e['name'] not in FEA_CAD]
    spec['guide']['sections']=[g for g in spec['guide']['sections'] if g['title']!='CAD and curve output']
    member_settings=[]
    for sid in members:
        _,gid,index=structure(v,sid)
        inputs=[e for e in fea_schema(v,sid)['inputs'] if e['name'] not in FEA_CAD]
        member_settings.append(dict(id=sid,name=v.GetFeaStructName(gid,index),component=v.GetGeomName(gid),values={e['name']:e['values'][0] for e in inputs},inputs=inputs))
    spec.update(name='FeaAssemblyMesh',structure=aid,members=members,exportFormats=list(ASSEMBLY_EXPORTS),description='Mesh and export a native structural assembly, including fixed-point connections. Choose shared mesh settings for every member or separate settings for each member. Parts, materials, properties and constraints remain defined by each member.')
    spec['guide'].update(title='Structural assembly mesh',note='Shared mesh settings start with the first member’s saved sizing, element and deck settings and apply to every member. Separate settings use each member’s own values and native limits. Each member keeps its own parts, materials, properties, constraints and connections.',memberSizing=member_settings,sections=spec['guide']['sections'])
    from native_connection_controls import inspect_assembly
    if check_connections:spec['guide']['connectionIssues']=inspect_assembly(v,aid)
    return spec


def assembly_inputs(req,members):
    records=req.get('memberInputs',[])
    if not isinstance(records,list):raise ValueError('Use a list of member sizing settings.')
    per_member={}
    for record in records:
        sid=one(record.get('id'),members,'Select an existing assembly member.')
        if sid in per_member:raise ValueError('Supply each assembly member once.')
        per_member[sid]=record.get('inputs',[])
    result={}
    for sid in members:
        merged={}
        for entries in [per_member.get(sid,[]),req.get('inputs',[])]:
            if not isinstance(entries,list):raise ValueError('Use a list of native sizing inputs.')
            names=[e['name'] for e in entries]
            if len(names)!=len(set(names)):raise ValueError('Supply each sizing input once.')
            for e in entries:merged[e['name']]=e
        result[sid]=list(merged.values())
    return result


def run_assembly(v,req):
    from native_boundary_results import report as boundary_report
    aid,members=assembly(v,req.get('structure'))
    inputs=assembly_inputs(req,members)
    selected=formats(req,ASSEMBLY_EXPORTS)
    has_masses=point_mass_export(v,members,selected)
    # Validate every member before changing any native sizing/export settings.
    for sid in members:
        _,gid,index=structure(v,sid)
        sizing(v,gid,index,inputs[sid],apply=False)
    from native_boundary_controls import validate_targets
    validate_targets(v,members)
    from native_connection_controls import validate_assembly
    validate_assembly(v,aid)
    for sid in members:
        _,gid,index=structure(v,sid)
        sizing(v,gid,index,inputs[sid])
        # Member exports are unnecessary; prevent imported absolute output paths.
        for p in v.FindContainerParmIDs(sid):
            if v.GetParmGroupName(p)=='ExportFEA' and v.GetParmName(p).endswith('_Export'):v.SetParmVal(p,0)
    for p in v.FindContainerParmIDs(aid):
        if v.GetParmGroupName(p)=='ExportFEA' and v.GetParmName(p).endswith('_Export'):
            v.SetParmVal(p,int(v.GetParmName(p)[:-7] in selected))
    for fmt,ext in ASSEMBLY_EXPORTS.items():
        v.SetFeaAssemblyFileName(aid,getattr(v,'FEA_'+fmt+'_FILE_NAME'),str(Path.cwd()/('assembly.'+('dat' if fmt=='NASTRAN' else ext))))
    spec=assembly_schema(v,aid,check_connections=False)
    from native_run_setup import save
    save(v,'FeaAssemblyMesh',spec['inputs'],structure=aid,formats=selected,
         members=members,memberSizing=spec['guide']['memberSizing'])
    v.ComputeFeaAssemblyMesh(aid)
    mesh=read_gmsh(Path.cwd()/'assembly.msh',Path.cwd()/'assembly.bdf' if has_masses else None)
    generated=assembly_schema(v,aid,check_connections=False)
    return dict(version=v.GetVSPVersion(),analysis='FeaAssemblyMesh',engineOperation='ComputeFeaAssemblyMesh',assemblyComputations=1,exportOperation='ExportAssemblyMesh',structure=aid,members=members,memberSizing=spec['guide']['memberSizing'],generatedMemberSizing=generated['guide']['memberSizing'],formats=selected,resultID='',inputs=spec['inputs'],geometryInputs=[],results=[],meshFile='assembly.msh',meshSummary=summary(mesh),boundaryReport=boundary_report(v,members,selected,Path.cwd()/'assembly.inp'))


def summary(mesh):
    return dict(nodes=len(mesh['nodes']),elements=mesh['totalElements'],groups=mesh['groups'],higherOrder=mesh['higherOrder'],unsupportedElements=mesh['unsupportedElements'])


def configure_outputs(v,name):
    if name=='SurfaceIntersection':
        import native_intersections
        return native_intersections.configure_outputs(v)
    # Native output paths are scoped to the isolated run, including imported model defaults.
    for key in v.GetAnalysisInputNames(name):
        if key.endswith('FileName'):
            value=list(v.GetStringAnalysisInput(name,key))
            extension={'STL':'.stl','GMSH':'.msh','OBJ':'.obj','TRI':'.tri','POLY':'.poly','FACET':'.facet'}.get(key[:-8],Path(value[0]).suffix if value else '.dat')
            v.SetStringAnalysisInput(name,key,[str(Path.cwd()/('mesh-'+key[:-8].lower()+extension))])


def configure_cfd(v,name):
    import native_cfd_guides
    native_cfd_guides.configure_outputs(v)
    v.SetIntAnalysisInput(name,'GMSHFileFlag',[1])
    v.SetStringAnalysisInput(name,'GMSHFileName',[str(Path.cwd()/'surface.msh')])
    return native_cfd_guides.apply_registered_settings(v)
