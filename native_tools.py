"""Native modeling workflows. Every edit below delegates to the OpenVSP API."""
import math
from pathlib import Path
import native_advanced
import native_structure
import native_region_curves
import native_components

MESH_SETTINGS = ['CFD_MAX_EDGE_LEN','CFD_MIN_EDGE_LEN','CFD_MAX_GAP','CFD_NUM_CIRCLE_SEGS','CFD_GROWTH_RATIO','CFD_LIMIT_GROWTH_FLAG','CFD_HALF_MESH_FLAG','CFD_INTERSECT_SUBSURFACE_FLAG']
EXPORTS = {'STL':('EXPORT_STL','stl'),'OBJ':('EXPORT_OBJ','obj'),'STEP':('EXPORT_STEP','step'),'IGES':('EXPORT_IGES','igs'),'GMSH':('EXPORT_GMSH','msh'),'SVG':('EXPORT_SVG','svg')}


def finite(x):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x): raise ValueError('Enter a finite number.')
    return x


def name(value):
    if not isinstance(value,str) or not value.strip() or len(value)>120: raise ValueError('Use a name of 1–120 characters.')
    return value.strip()


def one(value, choices, message='The selected item no longer exists.'):
    if value not in choices: raise ValueError(message)
    return value


def containers(v):
    ids=[]
    import native_flow_planes
    ids.extend(native_flow_planes.ids(v))
    for g in v.FindGeoms():
        ids.extend(v.GetSubSurfIDVec(g))
        ids.extend(v.GetCFDSourceID(g,i) for i in range(v.GetNumCFDSources(g)))
    ids.extend(v.FindControlSurfaceGroup(i) for i in range(v.GetNumControlSurfaceGroups()))
    ids.extend(v.GetParmLinkID(i) for i in range(v.GetNumParmLinks()))
    for s in v.GetFeaStructIDVec():
        ids.append(s);ids.extend(v.GetFeaPartIDVec(s))
    ids.extend(v.GetFeaMaterialIDVec());ids.extend(v.GetFeaPropertyIDVec())
    ids.extend(native_advanced.container_ids(v))
    import native_special
    ids.extend(native_special.containers(v))
    ids.extend(v.GetAllRulers());ids.extend(v.GetAllProbes());ids.extend(v.GetAllRSTProbes());ids.extend(v.GetAllProtractors())
    ids.extend(v.GetAllGeometryAnalysesIDVec())
    import native_references
    ids.extend(r['curveID'] for r in native_references.references(v).values() if r.get('curveID'))
    return ids


def parameter_ids(v):
    ids=set(v.GetAllUserParms())
    for c in containers(v): ids.update(v.FindContainerParmIDs(c))
    return ids


def snapshot(v, parameter):
    import native_flow_planes
    import native_cfd
    import native_references
    import native_files
    import native_fit
    import native_special
    import native_attributes
    import native_geometry_cases
    import native_export_controls
    import native_region_controls
    import native_structural_library
    refs=native_references.references(v)
    library_usage=native_structural_library.usage(v,refs)
    def parms(cid):
        fields=[parameter(v,p) for p in v.FindContainerParmIDs(cid)]
        import native_property_controls
        for field in fields:native_property_controls.annotate(v,field,refs)
        return fields
    controls=[];sources=[];structures=[]
    for g in v.FindGeoms():
        for sid in v.GetSubSurfIDVec(g):
            typ=v.GetSubSurfType(sid)
            curve=native_region_curves.details(v,sid,refs,parameter)
            curve_ids={p['id'] for p in (curve['sectionCurve']['params'] if curve['sectionCurve'] else [])}
            controls.append(dict(id=sid,geom=g,name=v.GetSubSurfName(sid),type=typ,propertyReferences={key:refs.get(sid,{}).get(key,'') for key in ('FeaPropertyID','CapFeaPropertyID')},boundaryGuide=native_region_controls.guide(v,sid,typ),intersectionTarget=v.GetIntersectSubSurfGeomID(sid) if typ==v.SS_INTERSECT else None,params=[parameter(v,p) for p in v.GetSubSurfParmIDs(sid) if p not in curve_ids],**curve))
        for i in range(v.GetNumCFDSources(g)):
            cid=v.GetCFDSourceID(g,i)
            import native_source_controls
            typ=v.GetCFDSourceType(g,i);fields=parms(cid);typeLabel=native_source_controls.enrich(v,g,typ,fields)
            sources.append(dict(id=cid,geom=g,index=i,name=v.GetCFDSourceName(g,i),type=typ,typeLabel=typeLabel,params=fields))
    for sid in v.GetFeaStructIDVec():
        gid=v.GetFeaStructParentGeomID(sid);index=v.GetFeaStructIndex(sid)
        parts=list(v.GetFeaPartIDVec(sid))
        structures.append(dict(id=sid,geom=gid,index=index,name=v.GetFeaStructName(gid,index),params=parms(sid),trimCandidates=native_structure.trim_candidates(v,parts),fixedPointParents=[p for p in parts if v.GetFeaPartType(p)!=v.FEA_FIX_POINT],parts=[dict(id=p,name=v.GetFeaPartName(p),type=v.GetFeaPartType(p),params=parms(p),**native_structure.details(v,p,parameter,refs)) for p in parts]))
    links=[]
    for i in range(v.GetNumParmLinks()):
        lid=v.GetParmLinkID(i)
        links.append(dict(id=lid,source=v.GetParmLinkAParm(lid),target=v.GetParmLinkBParm(lid),params=parms(lid)))
    presets=[]
    for gid in v.GetVarPresetGroups():
        presets.append(dict(id=gid,name=v.GetGroupName(gid),parameters=list(v.GetVarPresetParmIDs(gid)),settings=[dict(id=s,name=v.GetSettingName(s),values=list(v.GetVarPresetParmVals(s))) for s in v.GetVarPresetSettings(gid)]))
    return dict(
        **native_flow_planes.snapshot(v,parameter),
        **native_components.snapshot(v),
        **native_geometry_cases.snapshot(v,parameter,refs),
        controls=controls,controlGroups=[dict(id=v.FindControlSurfaceGroup(i),index=i,name=v.GetVSPAEROControlGroupName(i),members=list(v.GetActiveCSNameVec(i)),available=list(v.GetAvailableCSNameVec(i)),params=parms(v.FindControlSurfaceGroup(i))) for i in range(v.GetNumControlSurfaceGroups())],
        links=links,userParameters=[parameter(v,p) for p in v.GetAllUserParms()],presets=presets,
        sources=sources,cfdDomain=native_cfd.configuration(v,refs,parameter),cfdDensity=parms(v.FindContainer('CFDGridDensity',0)),meshSettings=[dict(name=n,value=v.GetCFDMeshVal(getattr(v,n))) for n in MESH_SETTINGS if hasattr(v,n)],
        structures=structures,materials=[dict(id=i,index=n,name=v.GetContainerName(i),params=parms(i),libraryUsers=library_usage.get(i,[]),builtIn=i.startswith('_')) for n,i in enumerate(v.GetFeaMaterialIDVec())],
        properties=[dict(id=i,index=n,name=v.GetContainerName(i),params=parms(i),references=refs.get(i,{}),libraryUsers=library_usage.get(i,[])) for n,i in enumerate(v.GetFeaPropertyIDVec())],
        exports=list(native_files.EXPORTS),legacyExports=native_files.LEGACY_EXPORTS,importFormats=list(native_files.IMPORTS),exportGuides=native_export_controls.configuration(v),
        curveTypes={n:getattr(v,n) for n in ['LINEAR','PCHIP','CEDIT']},
        sourceTypes={n:getattr(v,n) for n in ['POINT_SOURCE','LINE_SOURCE','BOX_SOURCE','ULINE_SOURCE','WLINE_SOURCE'] if hasattr(v,n)},
        fixedPointGeometries=native_structure.fixed_point_geometries(v),
        **native_advanced.snapshot(v,parameter,refs),**native_fit.snapshot(v,parameter),**native_special.snapshot(v,parameter),**native_attributes.snapshot(v))


def section(v,req):
    gid=one(req['geom'],v.FindGeoms());si=req.get('surface',0);index=req['index']
    if type(si)!=int or type(index)!=int:raise ValueError('Use whole-number section and surface indices.')
    if not 0<=si<v.GetNumXSecSurfs(gid): raise ValueError('Invalid surface index.')
    surf=v.GetXSecSurf(gid,si)
    if not 0<=index<v.GetNumXSec(surf): raise ValueError('Invalid section index.')
    return gid,surf,index,v.GetXSec(surf,index)


def mutate(v,r):
    op=r['operation'];gid=r.get('geom')
    if op.startswith('flow-plane-'):
        import native_flow_planes
        return native_flow_planes.mutate(v,r)
    if op.startswith('geometry-case-'):
        import native_geometry_cases
        return native_geometry_cases.mutate(v,r)
    if gid is not None: one(gid,v.FindGeoms())
    if op=='duplicate':
        import native_ngon
        gid=native_ngon.duplicate(v,gid)
        v.SetGeomName(gid,name(r.get('name',v.GetGeomName(gid)+' copy')))
    elif op=='reparent':
        parent=r.get('parent','')
        if parent:
            one(parent,v.FindGeoms());ancestor=parent;seen=set()
            while ancestor and ancestor!='NONE':
                if ancestor==gid or ancestor in seen: raise ValueError('A component cannot be parented to itself or a descendant.')
                seen.add(ancestor);ancestor=v.GetGeomParent(ancestor)
        import native_gear_retraction
        native_gear_retraction.require_dependency(v,gid,parent)
        v.SetGeomParent(gid,parent or v.GetVehicleID())
        if v.GetGeomParent(gid)!=(parent or 'NONE'): raise ValueError('OpenVSP did not apply the requested parent.')
    elif op=='visibility':
        v.SetSetFlag(gid,v.SET_SHOWN,bool(r['shown']))
    elif op.startswith('set-') or op=='group-transform':
        import native_components
        return native_components.mutate(v,r)
    elif op=='cfd-domain-settings':
        import native_cfd
        native_cfd.mutate(v,r)
    elif op=='intersection-settings':
        import native_intersections
        native_intersections.mutate_settings(v,r)
    elif op=='intersection-selection':
        import native_intersection_selection
        native_intersection_selection.mutate(v,r)
    elif op=='intersection-defaults':
        import native_intersection_defaults
        native_intersection_defaults.mutate(v,r)
    elif op=='wire-settings':
        import native_wire
        native_wire.mutate(v,r)
    elif op in ('section-file-section-points','section-file-airfoil-points'):
        import native_file_profiles
        return native_file_profiles.mutate(v,r)
    elif op in ('airfoil-import','curve-convert','curve-point','curve-tangent'):
        gid,surf,index,xid=section(v,r)
        if op=='curve-tangent':
            from native_editable_curves import move_tangent
            move_tangent(v,xid,r)
        elif op=='airfoil-import':
            text=r['content']
            if not isinstance(text,str) or len(text)>2_000_000 or '\x00' in text: raise ValueError('Choose an airfoil text file smaller than 2 MB.')
            coords=[]
            for line in text.splitlines():
                fields=line.split()
                if len(fields)==2:
                    try: pair=[float(x) for x in fields]
                    except ValueError: continue
                    if not all(math.isfinite(x) for x in pair): raise ValueError('Airfoil coordinates must be finite.')
                    coords.append(pair)
            if len(coords)<4: raise ValueError('No airfoil coordinate sequence was found.')
            path=Path.cwd()/'uploaded-airfoil.dat';path.write_text(text)
            from native_editable_curves import guard_shape_replacement
            guard_shape_replacement(v,xid,v.XS_FILE_AIRFOIL)
            v.ChangeXSecShape(surf,index,v.XS_FILE_AIRFOIL);xid=v.GetXSec(surf,index)
            v.ReadFileAirfoil(xid,str(path))
            if len(v.GetAirfoilUpperPnts(xid))<2 or len(v.GetAirfoilLowerPnts(xid))<2: raise ValueError('OpenVSP could not read the airfoil.')
        elif op=='curve-convert':
            if r.get('surface',0)!=0: raise ValueError('Curve conversion currently supports the first cross-section surface.')
            from native_editable_curves import guard_shape_replacement
            guard_shape_replacement(v,xid,v.XS_EDIT_CURVE)
            v.ConvertXSecToEdit(gid,index)
        else:
            if v.GetXSecShape(xid)!=v.XS_EDIT_CURVE: raise ValueError('Convert this section to an editable curve first.')
            if isinstance(r.get('point'),bool) or not isinstance(r.get('point'),int):raise ValueError('Choose a native curve point index.')
            pts=v.GetEditXSecCtrlVec(xid,True);idx=one(r['point'],range(len(pts)));p=r['xyz']
            if not isinstance(p,list) or len(p)!=3: raise ValueError('Enter three coordinates.')
            v.MoveEditXSecPnt(xid,idx,v.vec3d(*[finite(x) for x in p]))
    elif op in ('cst-fit','cst-coefficients','cst-degree'):
        gid,surf,index,xid=section(v,r)
        if v.GetGeomTypeName(gid).upper() not in ('WING','PROP','PROPELLER'):raise ValueError('CST editing requires an airfoil on a wing or propeller.')
        if op=='cst-fit':
            from native_cst_validation import fitting_degree
            degree=fitting_degree(r.get('degree'))
            from native_editable_curves import guard_shape_replacement
            guard_shape_replacement(v,xid,v.XS_CST_AIRFOIL)
            v.FitCSTAirfoil(surf,index,degree)
        else:
            if v.GetXSecShape(xid)!=v.XS_CST_AIRFOIL:raise ValueError('Fit this section to CST first.')
            if op=='cst-coefficients':
                from native_cst_validation import coefficients
                coefficients(v,v.GetXSecParmIDs(xid),r)
                v.SetUpperCST(xid,len(r['upper'])-1,r['upper']);v.SetLowerCST(xid,len(r['lower'])-1,r['lower'])
            else:
                side=one(r['side'],('upper','lower'));direction=one(r['direction'],('promote','demote'))
                degree=(v.GetUpperCSTDegree if side=='upper' else v.GetLowerCSTDegree)(xid)
                if (direction=='demote' and degree<=0) or (direction=='promote' and degree>=30):raise ValueError('The supported CST degree range is 0–30.')
                getattr(v,('Promote' if direction=='promote' else 'Demote')+'CST'+side.title())(xid)
    elif op in ('curve-replace-points','curve-init','curve-type','curve-split','curve-delete','curve-fixed','curve-smooth','curve-reparameterize'):
        gid,surf,index,xid=section(v,r)
        if v.GetXSecShape(xid)!=v.XS_EDIT_CURVE:raise ValueError('Convert this section to an editable curve first.')
        before=len(v.GetEditXSecCtrlVec(xid,True))
        if op=='curve-replace-points':
            from native_editable_curves import replace_control_points
            replace_control_points(v,xid,r)
        elif op=='curve-init':
            from native_editable_curves import guard_rebuild
            guard_rebuild(v,[dict(id=p,name=v.GetParmName(p)) for p in v.GetXSecParmIDs(xid)])
            shape=one(r.get('shape'),('EDIT_XSEC_CIRCLE','EDIT_XSEC_ELLIPSE','EDIT_XSEC_RECTANGLE'))
            v.SetParmVal(v.GetXSecParm(xid,'ShapeType'),getattr(v,shape));v.EditXSecInitShape(xid)
        elif op=='curve-type':
            target=getattr(v,one(r['type'],('LINEAR','PCHIP','CEDIT')))
            if (int(v.GetParmVal(v.GetXSecParm(xid,'CurveType')))==v.CEDIT)!=(target==v.CEDIT):
                from native_editable_curves import guard_rebuild
                guard_rebuild(v,[dict(id=p,name=v.GetParmName(p)) for p in v.GetXSecParmIDs(xid)])
            v.EditXSecConvertTo(xid,target)
        elif op=='curve-split':
            u=finite(r['u'])
            if not 0<u<1:raise ValueError('Split position must be strictly between 0 and 1.')
            from native_editable_curves import guard_rebuild
            guard_rebuild(v,[dict(id=p,name=v.GetParmName(p)) for p in v.GetXSecParmIDs(xid)])
            v.EditXSecSplit01(xid,u);v.Update()
            if len(v.GetEditXSecCtrlVec(xid,True))<=before:raise ValueError('OpenVSP did not add a point here. Choose a location between existing anchors.')
        elif op=='curve-reparameterize':v.ReparameterizeEditXSec(xid)
        elif op=='curve-smooth':
            if isinstance(r.get('point'),bool) or not isinstance(r.get('point'),int):raise ValueError('Choose a curve anchor index.')
            point=one(r['point'],range(before))
            if int(v.GetParmVal(v.GetXSecParm(xid,'CurveType')))!=v.CEDIT or point%3:
                raise ValueError('Smooth tangents require a cubic Bezier anchor.')
            if not isinstance(r['smooth'],bool):raise ValueError('Choose whether the tangent is smooth.')
            pid=v.GetXSecParm(xid,f'G1_{point}')
            from native_preview import parameter_activity
            if not parameter_activity(v,[pid])[pid]:raise ValueError('This tangent is locked by OpenVSP.')
            v.SetParmValUpdate(pid,int(r['smooth']))
        elif op=='curve-delete':
            if type(r.get('point'))!=int:raise ValueError('Choose a native curve point index.')
            point=one(r['point'],range(1,before-1),'The first and closing points cannot be removed.')
            typ=int(v.GetParmVal(v.GetXSecParm(xid,'CurveType')))
            if typ==v.CEDIT and point%3:raise ValueError('Remove a curve anchor, not a Bezier handle.')
            from native_editable_curves import guard_rebuild
            guard_rebuild(v,[dict(id=p,name=v.GetParmName(p)) for p in v.GetXSecParmIDs(xid)],{point-1,point,point+1} if typ==v.CEDIT else {point})
            v.EditXSecDelPnt(xid,point);v.Update()
            if len(v.GetEditXSecCtrlVec(xid,True))>=before:raise ValueError('OpenVSP could not remove this point with the current curve constraints.')
        else:
            if type(r.get('point'))!=int:raise ValueError('Choose a native curve point index.')
            flags=list(v.GetEditXSecFixedUVec(xid));point=one(r['point'],range(len(flags)))
            if not isinstance(r['fixed'],bool):raise ValueError('Choose whether the curve position is fixed.')
            flags[point]=r['fixed'];v.SetEditXSecFixedUVec(xid,flags)
    elif op=='control-add':
        if v.GetGeomTypeName(gid).upper() not in ('WING','PROP','PROPELLER'): raise ValueError('Control surfaces require a wing or propeller.')
        surf=int(r.get('surface',0))
        if not 0<=surf<v.GetNumMainSurfs(gid): raise ValueError('Invalid surface index.')
        sid=v.AddSubSurf(gid,v.SS_CONTROL,surf);v.SetSubSurfName(sid,name(r['name']))
        # Spanwise eta and fractional chord lengths are native control-surface drivers.
        for key,value in [('EtaFlag',1),('EtaStart',finite(r.get('start',.2))),('EtaEnd',finite(r.get('end',.8))),('Length_C_Start',finite(r.get('chord',.25))),('Length_C_End',finite(r.get('chord',.25)))]:
            if key!='EtaFlag' and not 0<=value<=1: raise ValueError('Control surface fractions must be between 0 and 1.')
            v.SetParmVal(v.FindParm(sid,key,'SS_Control'),value)
        if r.get('start',.2)>=r.get('end',.8): raise ValueError('The end span fraction must be greater than the start.')
    elif op=='control-delete':
        sid=one(r['id'],v.GetSubSurfIDVec(gid))
        import native_wave_controls
        native_wave_controls.guard_region_delete(v,sid)
        v.DeleteSubSurf(gid,sid)
    elif op=='control-group-create':
        label=name(r['name']);i=v.CreateVSPAEROControlSurfaceGroup();v.SetVSPAEROControlGroupName(label,i)
    elif op in ('control-group-rename','control-group-delete','control-group-member'):
        ids=[v.FindControlSurfaceGroup(i) for i in range(v.GetNumControlSurfaceGroups())]
        index=ids.index(one(r['group'],ids))
        if op=='control-group-delete':v.DeleteVSPAEROControlSurfaceGroup(index)
        elif op=='control-group-rename':v.SetVSPAEROControlGroupName(name(r['name']),index)
        else:
            add=r['add']
            if not isinstance(add,bool):raise ValueError('Choose add or remove for this group.')
            names=list((v.GetAvailableCSNameVec if add else v.GetActiveCSNameVec)(index))
            member=one(r['member'],range(1,len(names)+1),'This surface is no longer in the expected list.')
            if names[member-1]!=r['expectedName']:raise ValueError('Surface membership changed. Reload before editing.')
            (v.AddSelectedToCSGroup if add else v.RemoveSelectedFromCSGroup)([member],index)
    elif op=='control-groups-auto': v.AutoGroupVSPAEROControlSurfaces()
    elif op=='link-add':
        ids={p for g in v.FindGeoms() for p in v.GetGeomParmIDs(g)}|parameter_ids(v)
        a=one(r['source'],ids);b=one(r['target'],ids)
        edges={}
        for i in range(v.GetNumParmLinks()):
            lid=v.GetParmLinkID(i);pa=v.GetParmLinkAParm(lid);pb=v.GetParmLinkBParm(lid)
            if pb==b: raise ValueError('This target already has a driver link.')
            edges.setdefault(pa,[]).append(pb)
        for i in range(len(v.GetAdvLinkNames())):
            outputs=list(v.GetAdvLinkOutputParms(i))
            if b in outputs:raise ValueError('This target already has a driver expression.')
            for pa in v.GetAdvLinkInputParms(i):edges.setdefault(pa,[]).extend(outputs)
        stack=[b];seen=set()
        while stack:
            p=stack.pop()
            if p==a: raise ValueError('This link would create a dependency cycle.')
            if p not in seen: seen.add(p);stack.extend(edges.get(p,[]))
        lid=v.AddParmLink(a,b)
        if not lid: raise ValueError('OpenVSP rejected the parameter link.')
        v.SetParmLinkScaleFlag(lid,True);v.SetParmLinkOffsetFlag(lid,True)
        v.SetParmVal(v.FindParm(lid,'Scale','Link'),finite(r.get('scale',1)))
        v.SetParmVal(v.FindParm(lid,'Offset','Link'),finite(r.get('offset',0)))
        v.SetParmValUpdate(a,v.GetParmVal(a))
    elif op=='link-delete':
        v.DelParmLink(one(r['id'],[v.GetParmLinkID(i) for i in range(v.GetNumParmLinks())]))
    elif op=='user-add':
        p=v.AddUserParm(v.PARM_DOUBLE_TYPE,name(r['name']),'Studio')
        v.SetParmVal(p,finite(r.get('value',0)))
    elif op=='preset-save':
        ids={p for g in v.FindGeoms() for p in v.GetGeomParmIDs(g)}|parameter_ids(v)
        chosen=r['parameters']
        if not chosen or len(set(chosen))!=len(chosen): raise ValueError('Choose at least one unique parameter.')
        for p in chosen: one(p,ids)
        group=v.AddVarPresetGroup(name(r['name']))
        for p in chosen: v.AddVarPresetParm(group,p)
        setting=v.AddVarPresetSetting(group,'Saved values');v.SaveVarPresetParmVals(group,setting)
    elif op=='preset-apply':
        group=one(r['group'],v.GetVarPresetGroups());setting=one(r['setting'],v.GetVarPresetSettings(group));v.ApplyVarPresetSetting(group,setting)
    elif op=='preset-delete': v.DeleteVarPresetGroup(one(r['id'],v.GetVarPresetGroups()))
    elif op=='polygon-triangulate':
        import native_ngon
        native_ngon.triangulate(v,gid)
    elif op=='mesh-to-polygon':
        if gid not in v.FindGeoms() or v.GetGeomTypeName(gid).upper()!='MESH':raise ValueError('Choose a native triangle mesh to create a polygon mesh.')
        from native_references import document
        path,tree=document(v)
        try:
            record=next(g for g in tree.findall('./Vehicle/Geom') if g.findtext('ParmContainer/ID')==gid)
            if not record.findall('MeshGeom/TMesh/Tri_List/Tri'):raise ValueError('Choose a triangle mesh with geometry.')
        finally:path.unlink(missing_ok=True)
        import native_ngon
        created=native_ngon.convert(v,gid,r.get('levels',0),r.get('cull',False),r.get('fraction',.03),r.get('bodyWakes',False))
        if created not in v.FindGeoms():raise ValueError('OpenVSP did not create a polygon mesh.')
        graph=native_ngon.snapshot(v,created)
        if not graph['points'] or not graph['faces']:raise ValueError('OpenVSP produced an empty polygon mesh for this source.')
        native_ngon.validate(graph);gid=created
    elif op=='mesh-settings':
        for n,val in r['values'].items():
            one(n,MESH_SETTINGS);finite(val)
            if n.endswith('FLAG') and val not in (0,1): raise ValueError('Mesh flags must be 0 or 1.')
            if not n.endswith('FLAG') and val<=0: raise ValueError('Mesh sizing values must be positive.')
            v.SetCFDMeshVal(getattr(v,n),val)
    elif op=='source-defaults':
        if not v.FindGeoms():raise ValueError('Add aircraft geometry before generating refinement sources.')
        import native_cfd_density
        native_cfd_density.refresh(v)
        before={v.GetCFDSourceID(g,i) for g in v.FindGeoms() for i in range(v.GetNumCFDSources(g))}
        v.AddDefaultSources()
        after={v.GetCFDSourceID(g,i) for g in v.FindGeoms() for i in range(v.GetNumCFDSources(g))}
        if not before<=after:raise ValueError('OpenVSP replaced an existing refinement source unexpectedly.')
        if after==before:raise ValueError('OpenVSP added no default sources for the current geometry and native source state.')
    elif op=='source-add':
        typ=one(r.get('type','POINT_SOURCE'),['POINT_SOURCE','LINE_SOURCE','BOX_SOURCE','ULINE_SOURCE','WLINE_SOURCE'])
        import native_source_controls
        active=native_source_controls.creation_fields(typ)
        vals=[finite(r.get(k,d) if k in active else d) for k,d in [('length',.2),('radius',1),('u',.5),('w',.5),('length2',.2),('radius2',1),('u2',.8),('w2',.5)]]
        if min(vals[0:2]+vals[4:6])<=0 or any(not 0<=vals[i]<=1 for i in [2,3,6,7]): raise ValueError('Use positive sizes and surface coordinates between 0 and 1.')
        surface=one(r.get('surface',0),range(v.GetNumMainSurfs(gid)),'Choose a native surface on this component.')
        before=v.GetNumCFDSources(gid);v.AddCFDSource(getattr(v,typ),gid,surface,*vals)
        if v.GetNumCFDSources(gid)!=before+1:raise ValueError('OpenVSP did not create this refinement source.')
        if r.get('name'):v.SetCFDSourceName(gid,before,name(r['name']))
    elif op in ('source-delete','source-rename'):
        sources=[v.GetCFDSourceID(gid,i) for i in range(v.GetNumCFDSources(gid))]
        index=sources.index(one(r['id'],sources,'Choose an existing source on this component.')) if r.get('id') else one(int(r['index']),range(len(sources)))
        if op=='source-delete':v.DeleteCFDSource(gid,index)
        else:v.SetCFDSourceName(gid,index,name(r['name']))
    elif op=='source-scale':
        kind=one(r['kind'],['length','radius']);factor=finite(r['factor'])
        if factor<=0:raise ValueError('Use a positive source multiplier.')
        if not any(v.GetNumCFDSources(g) for g in v.FindGeoms()):raise ValueError('Add refinement sources before scaling them.')
        (v.AdjustAllCFDSourceLen if kind=='length' else v.AdjustAllCFDSourceRad)(factor)
    elif op=='structure-add':
        surface=one(r.get('surface',0),range(v.GetNumMainSurfs(gid)),'Choose a native surface on this component.')
        index=v.AddFeaStruct(gid,True,surface);v.SetFeaStructName(gid,index,name(r['name']))
    elif op in ('part-add','structure-delete','part-delete'):
        sid=one(r['structure'],v.GetFeaStructIDVec());gid=v.GetFeaStructParentGeomID(sid);index=v.GetFeaStructIndex(sid)
        if op=='structure-delete': v.DeleteFeaStruct(gid,index)
        elif op=='part-delete':
            part=one(r['id'],v.GetFeaPartIDVec(sid))
            if v.GetFeaPartType(part)==v.FEA_SKIN: raise ValueError('Keep the structure skin; delete the structure to remove it.')
            native_structure.guard_parent_delete(v,sid,part)
            v.DeleteFeaPart(gid,index,part)
        else:
            typ=one(r['type'],native_advanced.enums(v,native_advanced.PART_TYPES))
            if typ in ('FEA_RIB','FEA_SPAR','FEA_RIB_ARRAY','FEA_POLY_SPAR') and v.GetGeomTypeName(gid).upper()!='WING':raise ValueError('Ribs and spars require a wing structure. Choose a slice, dome, or another suitable part for this component.')
            p=v.AddFeaPart(gid,index,getattr(v,typ));v.SetFeaPartName(p,name(r['name']))
    elif op=='material-add':
        cid=v.AddFeaMaterial();v.SetContainerName(cid,name(r['name']))
    elif op=='property-add':
        cid=v.AddFeaProperty(one(int(r.get('type',0)),[0,1]));v.SetContainerName(cid,name(r['name']))
    else: return native_advanced.mutate(v,r)
    return True,gid


def export(v,r):
    if r.get('kind')=='airfoil':
        gid=one(r['geom'],v.FindGeoms());kind=one(r['format'],('selig','bezier'));u=finite(r['u'])
        if v.GetGeomTypeName(gid).upper() not in ('WING','PROP','PROPELLER'):raise ValueError('Select a wing or propeller to export an airfoil.')
        if not 0<=u<=1:raise ValueError('Airfoil surface U must be between 0 and 1.')
        path=Path.cwd()/('airfoil.dat' if kind=='selig' else 'airfoil.bz')
        (v.WriteSeligAirfoil if kind=='selig' else v.WriteBezierAirfoil)(str(path),gid,u)
        if not path.exists() or not path.stat().st_size:raise ValueError('OpenVSP produced no airfoil file.')
        return dict(filename=path.name)
    import native_files
    return native_files.export(v,r)
