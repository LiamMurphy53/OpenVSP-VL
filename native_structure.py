"""Structural part references and point operations through the official API."""
from pathlib import Path
import uuid


def refresh(v,sid):
    """Evaluate native structure surfaces before expanding an array.

    Update() evaluates geometry and material managers, but does not call
    FeaStructure::Update(). The official structural CAD exporter does. This
    temporary native export supplies that missing evaluation without meshing
    or reimplementing array spacing math.
    """
    pid=v.FindParm(v.GetVehicleID(),'StructureExportIndex','IGESSettings')
    previous=v.GetParmVal(pid)
    path=Path.cwd()/('structure-refresh-'+uuid.uuid4().hex+'.igs')
    try:
        v.SetParmVal(pid,list(v.GetFeaStructIDVec()).index(sid))
        v.ExportFile(str(path),v.SET_ALL,v.EXPORT_IGES_STRUCTURE)
        if not path.exists() or not path.stat().st_size:raise ValueError('OpenVSP could not evaluate the structure surfaces.')
    finally:
        v.SetParmVal(pid,previous);path.unlink(missing_ok=True)


def details(v,part,parameter,refs=None):
    typ=v.GetFeaPartType(part)
    if refs is None:
        import native_references
        refs=native_references.references(v)
    import native_part_controls
    result={'placementGuide':native_part_controls.guide(v,part),'propertyReferences':{key:refs.get(part,{}).get(key,'') for key in ('FeaPropertyID','CapFeaPropertyID')}}
    if typ==v.FEA_FIX_POINT:
        if refs is None:
            import native_references
            refs=native_references.references(v)
        result['fixedPoint']=refs.get(part,{})
    if typ in (v.FEA_RIB,v.FEA_RIB_ARRAY):
        result['perpendicularSpar']=v.GetFeaPartPerpendicularSparID(part)
    if typ==v.FEA_TRIM:result['trimTargets']=list(v.GetFeaTrimPartIDVec(part))
    if typ==v.FEA_POLY_SPAR:
        result['points']=[dict(id=p,index=i,name=v.GetFeaPolySparPtName(part,i),
                              params=[parameter(v,pid) for pid in v.FindContainerParmIDs(p)])
                          for i,p in enumerate(v.GetAllFeaPolySparPtIDVec(part))]
    return result


def fixed_point_geometries(v):
    # Matching the native fixed-point geometry picker's excluded types.
    excluded={'MESH','HUMAN','PTCLOUD','WIREFRAME','BLANK'}
    return [g for g in v.FindGeoms() if v.GetGeomTypeName(g).replace(' ','').upper() not in excluded]


def guard_parent_delete(v,sid,part):
    import native_references
    refs=native_references.references(v)
    users=[v.GetFeaPartName(p) for p in v.GetFeaPartIDVec(sid) if v.GetFeaPartType(p)==v.FEA_FIX_POINT and v.GetParmVal(v.FindParm(p,'FixedPointType','FeaFixPoint')) in (v.FEA_FIX_PT_ON_BODY,v.FEA_FIX_PT_DELTA_XYZ,v.FEA_FIX_PT_DELTA_UVN) and refs.get(p,{}).get('ParentFeaPartID')==part]
    if users:raise ValueError('Choose another parent part for these fixed points before removing this part: '+', '.join(users))


def guard_geometry_delete(v,gid):
    import native_references
    removed={gid};pending=[gid]
    while pending:
        for child in v.GetGeomChildren(pending.pop()):
            if child not in removed:removed.add(child);pending.append(child)
    refs=native_references.references(v);users=[]
    for sid in v.GetFeaStructIDVec():
        if v.GetFeaStructParentGeomID(sid) in removed:continue
        for p in v.GetFeaPartIDVec(sid):
            if v.GetFeaPartType(p)==v.FEA_FIX_POINT and v.GetParmVal(v.FindParm(p,'FixedPointType','FeaFixPoint')) in (v.FEA_FIX_PT_GEOM_ORIGIN,v.FEA_FIX_PT_GEOM_CG) and refs.get(p,{}).get('OtherGeomID') in removed:users.append(v.GetFeaPartName(p))
    if users:raise ValueError('Choose another reference component for these fixed points before removing this component: '+', '.join(users))
    regions=[v.GetFeaSubSurfName(p) for sid in v.GetFeaStructIDVec() if v.GetFeaStructParentGeomID(sid) not in removed for p in v.GetFeaSubSurfIDVec(sid) if refs.get(p,{}).get('regionType')==v.SS_INTERSECT and refs.get(p,{}).get('IntersectID') in removed]
    if regions:raise ValueError('Choose another intersection component for these structural regions before removing this component: '+', '.join(regions))


def configure_fixed_point(v,part,parts,r):
    import native_references
    from native_tools import finite,one
    mode=r.get('mode')
    if isinstance(mode,bool) or not isinstance(mode,int):raise ValueError('Choose a native fixed-point placement mode.')
    one(mode,[v.FEA_FIX_PT_ON_BODY,v.FEA_FIX_PT_GLOBAL_XYZ,v.FEA_FIX_PT_DELTA_XYZ,v.FEA_FIX_PT_DELTA_UVN,v.FEA_FIX_PT_GEOM_ORIGIN,v.FEA_FIX_PT_GEOM_CG])
    references={}
    if mode in (v.FEA_FIX_PT_ON_BODY,v.FEA_FIX_PT_DELTA_XYZ,v.FEA_FIX_PT_DELTA_UVN):
        references['ParentFeaPartID']=one(r.get('parent'),[p for p in parts if v.GetFeaPartType(p)!=v.FEA_FIX_POINT],'Choose a parent part in this structure.')
    elif mode in (v.FEA_FIX_PT_GEOM_ORIGIN,v.FEA_FIX_PT_GEOM_CG):
        references['OtherGeomID']=one(r.get('reference'),fixed_point_geometries(v),'Choose a supported reference component.')
    values=r.get('values',{})
    allowed={'PosU','PosW','AbsX','AbsY','AbsZ','DeltaX','DeltaY','DeltaZ','DeltaU','DeltaV','DeltaN','FixPointMassFlag','FixPointMass','MassUnit'}
    if not isinstance(values,dict) or set(values)-allowed:raise ValueError('Choose supported fixed-point settings.')
    edits=[]
    for name,value in values.items():
        pid=v.FindParm(part,name,'FeaFixPoint');value=finite(value)
        if not v.GetParmLowerLimit(pid)<=value<=v.GetParmUpperLimit(pid):raise ValueError('Value is outside the OpenVSP parameter limits: '+name)
        if v.GetParmType(pid) in (v.PARM_INT_TYPE,v.PARM_BOOL_TYPE) and int(value)!=value:raise ValueError('Use a native integer setting: '+name)
        edits.append((pid,value))
    for pid,value in edits:v.SetParmVal(pid,value)
    v.SetParmVal(v.FindParm(part,'FixedPointType','FeaFixPoint'),mode);v.Update()
    if references:native_references.set_references(v,part,'FeaPartInfo',references)


def trim_candidates(v,parts):
    # Matching FeaPartEditScreen::UpdateTrimPartChoice: exclude skin, fixed
    # points, arrays and trim parts, which do not define usable trim surfaces.
    excluded=(v.FEA_SKIN,v.FEA_FIX_POINT,v.FEA_RIB_ARRAY,v.FEA_SLICE_ARRAY,v.FEA_TRIM)
    return [p for p in parts if v.GetFeaPartType(p) not in excluded]


def mutate(v,r):
    from native_tools import one,name
    op=r['operation'];sid=one(r['structure'],v.GetFeaStructIDVec())
    if op=='part-property':
        import native_references
        part=one(r['id'],v.GetFeaPartIDVec(sid));role=one(r['role'],['shell','beam'])
        typ=v.FEA_SHELL if role=='shell' else v.FEA_BEAM
        prop=one(r['property'],[p for p in v.GetFeaPropertyIDVec() if v.GetParmVal(v.FindParm(p,'FeaPropertyType','FeaProperty'))==typ],'Choose a matching '+role+' property.')
        native_references.set_reference(v,part,'FeaPartInfo','FeaPropertyID' if role=='shell' else 'CapFeaPropertyID',prop)
    gid=v.GetFeaStructParentGeomID(sid);index=v.GetFeaStructIndex(sid)
    parts=list(v.GetFeaPartIDVec(sid));part=one(r['id'],parts)
    typ=v.GetFeaPartType(part)
    if op=='part-fixed-point':
        if typ!=v.FEA_FIX_POINT:raise ValueError('Choose a fixed-point part.')
        configure_fixed_point(v,part,parts,r)
    elif op=='part-rename':v.SetFeaPartName(part,name(r['name']))
    elif op=='part-reorder':
        direction=one(r['direction'],('REORDER_MOVE_UP','REORDER_MOVE_DOWN','REORDER_MOVE_TOP','REORDER_MOVE_BOTTOM'))
        v.ReorderFeaPart(gid,index,part,getattr(v,direction))
    elif op=='part-individualize':
        if typ not in (v.FEA_RIB_ARRAY,v.FEA_SLICE_ARRAY):raise ValueError('Choose a rib or slice array to expand.')
        refresh(v,sid)
        v.IndividualizeFeaPart(gid,index,part)
        after=list(v.GetFeaPartIDVec(sid))
        if part in after or len(after)<len(parts):raise ValueError('OpenVSP did not expand this array. Check its spacing and range.')
    elif op=='part-perpendicular-spar':
        if typ not in (v.FEA_RIB,v.FEA_RIB_ARRAY):raise ValueError('Only ribs and rib arrays can be oriented to a spar.')
        spar=one(r['spar'],[p for p in parts if v.GetFeaPartType(p)==v.FEA_SPAR])
        pid=next((p for p in v.FindContainerParmIDs(part) if v.GetParmName(p)=='PerpendicularEdgeType'),None)
        if not pid:raise ValueError('This part has no native orientation setting.')
        v.SetFeaPartPerpendicularSparID(part,spar);v.SetParmValUpdate(pid,v.SPAR_NORMAL)
    elif op in ('part-trim-add','part-trim-delete'):
        if typ!=v.FEA_TRIM:raise ValueError('Choose a trim part.')
        targets=list(v.GetFeaTrimPartIDVec(part))
        if op=='part-trim-add':
            target=one(r['target'],trim_candidates(v,parts),'Choose a surface part in this structure.')
            if target in targets:raise ValueError('This part is already in the trim list.')
            v.AddFeaTrimPart(part,target)
        else:
            target=one(r['target'],targets);v.DeleteFeaTrimPart(part,targets.index(target))
    elif op.startswith('part-point-'):
        if typ!=v.FEA_POLY_SPAR:raise ValueError('Choose a polyline spar to edit its points.')
        points=list(v.GetAllFeaPolySparPtIDVec(part))
        if op=='part-point-add':v.AddFeaPolySparPt(part)
        else:
            point=one(r['point'],points);i=points.index(point)
            if op=='part-point-insert':v.InsertFeaPolySparPt(part,i)
            elif op=='part-point-delete':
                if len(points)<=2:raise ValueError('Keep at least two points in a polyline spar.')
                v.DelFeaPolySparPt(part,i)
            elif op=='part-point-rename':v.SetFeaPolySparPtName(part,i,name(r['name']))
            elif op=='part-point-reorder':
                direction=one(r['direction'],('REORDER_MOVE_UP','REORDER_MOVE_DOWN','REORDER_MOVE_TOP','REORDER_MOVE_BOTTOM'))
                v.MoveFeaPolySparPt(part,i,getattr(v,direction))
            else:return False,None
    else:return False,None
    return True,gid
