"""Native CFD domain/mode references and guided settings; no domain calculations."""
import ctypes
import json
import math
from native_tools import finite,one
import native_references

FIELDS=['Set','DegenSet','UseMode','FarMesh','FarComp','FarAbsSize','FarManualLoc',
        'FarXScale','FarYScale','FarZScale','FarLength','FarWidth','FarHeight',
        'FarXLocation','FarYLocation','FarZLocation','HalfMesh','SymmetrySplitting']


def configuration(v,refs=None,parameter=None):
    refs=native_references.references(v) if refs is None else refs
    cid=next((c for c in refs if 'ModeID' in refs[c] and 'FarGeomID' in refs[c]),None)
    if cid is None:raise ValueError('The native CFD settings are unavailable.')
    ids={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)}
    if any(n not in ids for n in FIELDS):raise ValueError('The native CFD domain settings are incomplete.')
    if parameter is None:
        from native_worker import parameter
    return dict(id=cid,mode=refs[cid]['ModeID'],farGeom=v.GetCFDFarFieldGeomID(),params=[parameter(v,ids[n]) for n in FIELDS])


def mutate(v,request):
    config=configuration(v);params={p['name']:p for p in config['params']}
    values=request.get('values',{})
    if not isinstance(values,dict) or not values:raise ValueError('Choose CFD domain settings to save.')
    for name,value in values.items():
        p=params[one(name,params,'Unsupported CFD domain setting.')];finite(value)
        if not p['min']<=value<=p['max']:raise ValueError(p['name']+': value is outside the native limits.')
        if p['type'] in (v.PARM_INT_TYPE,v.PARM_BOOL_TYPE) and value!=int(value):raise ValueError('Use a whole number for '+p['name']+'.')
        if name in ['Set','DegenSet'] and value not in range(-1,v.GetNumSets()):raise ValueError('Choose an existing native geometry set.')
    current={p['name']:p['value'] for p in config['params']};current.update(values)
    mode=request.get('mode',config['mode']);far=request.get('farGeom',config['farGeom'])
    if not isinstance(mode,str) or not isinstance(far,str):raise ValueError('Choose named native mode and far-field references.')
    if mode:one(mode,v.GetAllModes(),'Choose an existing native mode.')
    if far:one(far,v.FindGeoms(),'Choose an existing far-field component.')
    if current['UseMode'] and not mode:raise ValueError('Choose a mode before enabling CFD mode selection.')
    if current['FarMesh'] and current['FarComp'] and not far:raise ValueError('Choose the far-field component before enabling a component boundary.')
    for name,value in values.items():v.SetParmVal(params[name]['id'],value)
    v.Update()
    if mode!=config['mode'] or far!=config['farGeom']:
        # References are stored through the engine's own documented native file
        # structure and validated by the existing fresh-engine reload transaction.
        native_references.set_references(v,config['id'],'CFDMeshSettings',{'ModeID':mode,'FarGeomID':far})


def guard_geometry_delete(v,gid):
    config=configuration(v);values={p['name']:p['value'] for p in config['params']}
    if values['FarMesh'] and values['FarComp'] and config['farGeom']==gid:raise ValueError('This component is the active CFD far-field boundary. Choose another boundary or disable component far-field meshing first.')


def guard_mode_delete(v,mode):
    config=configuration(v);values={p['name']:p['value'] for p in config['params']}
    if values['UseMode'] and config['mode']==mode:raise ValueError('This mode is selected for CFD meshing. Choose another mode or disable CFD mode selection first.')


def preview(v,request):
    from native_preview import adapter
    from native_worker import snapshot
    if not v.FindGeoms():raise ValueError('Add aircraft geometry before previewing the CFD domain.')
    config=configuration(v);values={p['name']:p['value'] for p in config['params']}
    mode=config['mode'] if values['UseMode'] else ''
    if values['UseMode']:one(mode,v.GetAllModes(),'Choose an existing CFD mode before previewing its domain.')
    if values['FarMesh'] and values['FarComp']:one(config['farGeom'],v.FindGeoms(),'Choose an existing CFD far-field component.')
    _,engine,library=adapter(v);function=library.studio_cfd_domain
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p];function.restype=ctypes.c_char_p
    objects=json.loads(function(engine,mode.encode()))
    if isinstance(objects,dict):raise ValueError(objects.get('error','Native CFD domain drawings unavailable.'))
    for obj in objects:
        if any(len(p)!=3 or not all(math.isfinite(x) for x in p) for p in obj['points']):raise ValueError('OpenVSP returned undefined CFD domain drawing points.')
    parts=[]
    for key,label in [('domain','Native domain bounds'),('symmetry','Native symmetry subdivisions'),('wake','Native wake paths')]:
        selected=[o for o in objects if o['owner']==key]
        if key=='domain' and not values['FarMesh']:continue
        if key=='symmetry' and (not values['FarMesh'] or not values['SymmetrySplitting'] or values['FarComp']):continue
        if selected:parts.append(dict(id=key,index=len(parts),name=label,objects=selected))
    warnings=[]
    if not values['FarMesh']:warnings.append('Far-field meshing is disabled. Enable it to include an outer boundary.')
    if values['FarMesh'] and values['FarComp']:warnings.append('The chosen component supplies the far-field boundary. Native domain bounds show the enclosing domain, not that component’s exact surface.')
    if values['FarMesh'] and values['SymmetrySplitting'] and not values['FarComp'] and not any(p['id']=='symmetry' for p in parts):warnings.append('OpenVSP returned no symmetry subdivisions for this domain. Review the box size and placement before meshing.')
    if not any(p['id']=='wake' for p in parts):warnings.append('No native wake paths were returned. Enable a wake on a supported aircraft component to preview it.')
    # Applying mode presets is native and ephemeral. Return the resulting engine
    # geometry for context rather than overlaying mode drawings on stale surfaces.
    if mode:
        mode_values={v.GetParmName(p):v.GetParmVal(p) for p in v.FindContainerParmIDs(mode)}
        normal,degen=[int(mode_values[n]) for n in ['NormalSet','DegenSet']]
    else:normal,degen=int(values['Set']),int(values['DegenSet'])
    selected=set()
    for index in [normal,degen]:
        if index!=v.SET_NONE:selected.update(v.GetGeomSetAtIndex(index))
    shown=set(selected)
    if values['FarMesh'] and values['FarComp']:
        shown.add(config['farGeom'])
        if config['farGeom'] not in selected:warnings.append('The far-field component is outside the selected sets. Include it in the mesh set or mode before meshing.')
    context=[c for c in snapshot(v)['components'] if c['id'] in shown]
    return dict(version=v.GetVSPVersion(),parts=parts,warnings=warnings,configuration=config,context=context,
                showContext=True,selectedGeoms=sorted(selected),normalSet=normal,degenSet=degen,filename='CFD domain and wake preview',
                engineOperation='CfdMeshMgr::TransferMeshSettings / ApplyModeSettings / UpdateSourcesAndWakes / UpdateDomain / LoadDrawObjs',
                displayNote='These bounds, symmetry subdivisions and wake paths are drawn by OpenVSP before meshing. Mode presets are applied to this preview’s aircraft context without saving them to the aircraft. The final boundary mesh is generated by CfdMeshAnalysis.')
