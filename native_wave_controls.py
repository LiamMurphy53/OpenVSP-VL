"""Original saved wave-drag references and propulsive-face selections."""
import ctypes,json,os,xml.etree.ElementTree as ET
import native_references
LABELS={'UseMode':'Geometry selection','SelSetIndex':'Geometry set','RefFlag':'Reference area source','Sref':'Reference area (square model units)','MachNumber':'Supersonic Mach number','NumSlices':'Axial slices','NumRotSects':'Cone sections','SymmFlag':'Native slicing symmetry','PlaneFlag':'Show native slicing plane','ThetaIndex':'Native cone section for display','SlicingLoc':'Native plane position','SelBodyIndex':'Native comparison body','AreaPlotType':'Native area plot type','PointPlotFlag':'Show native plot points'}


def ids(v):return {v.GetParmName(p):p for p in v.FindContainerParmIDs(v.FindContainer('WaveDragSettings',0))}


def refresh(v):
    from native_preview import adapter
    _,engine,bridge=adapter(v);fn=bridge.studio_wave_update;fn.argtypes=[ctypes.c_char_p];fn.restype=ctypes.c_char_p
    data=json.loads(fn(engine))
    if data.get('error'):raise ValueError(data['error'])


def refs(v):return native_references.references(v).get(v.FindContainer('WaveDragSettings',0),{})


def reason(v,pid):
    if v.GetParmGroupName(pid)!='WaveDrag':return ''
    n=v.GetParmName(pid);p=ids(v)
    if n=='SelSetIndex' and v.GetParmVal(p['UseMode']):return 'The saved mode supplies wave-drag geometry selection.'
    if n=='Sref' and v.GetParmVal(p['RefFlag'])==v.COMPONENT_REF:return 'Calculated by the original wave-drag manager from its saved reference wing.'
    return ''


def annotate(v,p):
    if p['rawGroup']!='WaveDrag':return
    if p['name'] in LABELS:p['label']=LABELS[p['name']]
    if p['name']=='RefFlag':p['choices']=[dict(value=v.MANUAL_REF,label='Entered reference area'),dict(value=v.COMPONENT_REF,label='Native wing area')]
    elif p['name']=='UseMode':p['choices']=[dict(value=0,label='Geometry set'),dict(value=1,label='Native mode')]
    elif p['name']=='SelSetIndex':p['choices']=[dict(value=i,label=v.GetSetName(i)+' · '+str(i)) for i in range(v.GetNumSets())]
    why=reason(v,p['id'])
    if why:p.update(active=False,editable=False,readOnly=True,readOnlyReason=why)


def validate_parameter(v,pid,value=None):
    if v.GetParmGroupName(pid)!='WaveDrag':return
    refresh(v);why=reason(v,pid)
    if why:raise ValueError(why)
    n=v.GetParmName(pid)
    if n in ('RefFlag','UseMode') and value==1:
        ref=refs(v);available=[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='WING'] if n=='RefFlag' else list(v.GetAllModes());key='ReferenceGeomID' if n=='RefFlag' else 'ModeID'
        if ref.get(key) not in available:raise ValueError('Save an existing wave-drag reference wing or mode before enabling its selection.')


def configuration(v,references):
    cid=v.FindContainer('WaveDragSettings',0);p=ids(v)
    return dict(reference=references.get(cid,{}),sections=[dict(title='Geometry and reference area',parameters=[p[n] for n in ['UseMode','SelSetIndex','RefFlag','Sref']]),dict(title='Supersonic slicing',parameters=[p[n] for n in ['MachNumber','NumSlices','NumRotSects','SymmFlag']]),dict(title='Saved plane inspector',parameters=[p[n] for n in ['PlaneFlag','ThetaIndex','SlicingLoc']])],wings=[dict(id=g,name=v.GetGeomName(g)) for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='WING'],modes=[dict(id=m,name=v.GetModeName(m)) for m in v.GetAllModes()],faces=[dict(id=s,name=v.GetGeomName(g)+' · '+v.GetSubSurfName(s)) for g in v.FindGeoms() for s in v.GetSubSurfIDVec(g)])


def mutate(v,r):
    from native_tools import one
    p=ids(v);cid=v.FindContainer('WaveDragSettings',0);op=r['operation']
    if op=='wave-flow-faces':
        selected=r.get('faces');valid=[s for g in v.FindGeoms() for s in v.GetSubSurfIDVec(g)]
        if not isinstance(selected,list) or len(set(selected))!=len(selected) or any(s not in valid for s in selected):raise ValueError('Choose unique existing propulsive-face regions.')
        filename=v.GetVSPFileName();path,tree=native_references.document(v)
        try:
            node=tree.find('.//WaveDragMgr/FlowSS_List');node.clear()
            for sid in selected:ET.SubElement(ET.SubElement(node,'FlowSS'),'flowSS_ID').text=sid
            tree.write(path,encoding='utf-8',xml_declaration=True);os.replace(path,filename)
        finally:path.unlink(missing_ok=True)
        raise native_references.ReloadRequired()
    if op=='wave-reference-wing':key='ReferenceGeomID';value=one(r.get('wing'),['']+[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='WING']);flag='RefFlag'
    elif op=='wave-reference-mode':key='ModeID';value=one(r.get('mode'),['']+list(v.GetAllModes()));flag='UseMode'
    else:raise ValueError('Unknown saved wave-drag operation.')
    if not value and v.GetParmVal(p[flag]):raise ValueError('Switch to entered area or geometry sets before clearing the active wave-drag reference.')
    native_references.set_reference(v,cid,'WaveDragMgr',key,value)


def guard_geometry_delete(v,gid):
    ref=refs(v);removed={gid};pending=[gid]
    while pending:
        for child in v.GetGeomChildren(pending.pop()):
            if child not in removed:removed.add(child);pending.append(child)
    if v.GetParmVal(ids(v)['RefFlag'])==v.COMPONENT_REF and ref.get('ReferenceGeomID') in removed:raise ValueError('Choose another wave-drag reference wing or entered area before removing this wing.')
    faces={s for g in removed for s in v.GetSubSurfIDVec(g)}
    if faces.intersection(ref.get('flowFaces',[])):raise ValueError('Remove this component’s regions from saved wave-drag propulsive faces before deleting it.')


def guard_region_delete(v,sid):
    if sid in refs(v).get('flowFaces',[]):raise ValueError('Remove this region from saved wave-drag propulsive faces before deleting it.')


def guard_mode_delete(v,mode):
    if v.GetParmVal(ids(v)['UseMode']) and refs(v).get('ModeID')==mode:raise ValueError('Choose another wave-drag mode or geometry sets before removing this mode.')


def study_metadata(v):
    p=ids(v);return {p[n]:dict(conditions=[dict(parameter=p[c],values=[0],label=LABELS[c])],limitControllers=[]) for n,c in [('Sref','RefFlag'),('SelSetIndex','UseMode')]}


def study_priority(v,pid):
    if v.GetParmGroupName(pid)!='WaveDrag':return None
    return -10 if v.GetParmName(pid) in ('RefFlag','UseMode') else 40
