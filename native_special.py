"""Native specialized geometry and cross-section operations."""
from pathlib import Path
from native_tools import finite,name,one,section

BOR_CST_FIT_SHAPES=['XS_FOUR_SERIES','XS_SIX_SERIES','XS_FOUR_DIGIT_MOD','XS_FIVE_DIGIT','XS_FIVE_DIGIT_MOD','XS_ONE_SIX_SERIES','XS_FILE_AIRFOIL']
SHAPES=['XS_POINT','XS_CIRCLE','XS_ELLIPSE','XS_SUPER_ELLIPSE','XS_ROUNDED_RECTANGLE','XS_GENERAL_FUSE','XS_FILE_FUSE','XS_FOUR_SERIES','XS_SIX_SERIES','XS_BICONVEX','XS_WEDGE','XS_EDIT_CURVE','XS_FILE_AIRFOIL','XS_CST_AIRFOIL','XS_VKT_AIRFOIL','XS_FOUR_DIGIT_MOD','XS_FIVE_DIGIT','XS_FIVE_DIGIT_MOD','XS_ONE_SIX_SERIES','XS_AC25_773']

def xyz(p):return [p.x(),p.y(),p.z()]
def text_file(content,filename):
    if not isinstance(content,str) or not content.strip() or len(content.encode())>5_000_000 or '\x00' in content:raise ValueError('Choose a nonempty coordinate file smaller than 5 MB.')
    path=Path.cwd()/filename;path.write_text(content)
    from native_section_file_validation import validate_profile_file
    validate_profile_file(path)
    return str(path)
def containers(v):
    return [p for g in v.FindGeoms() for p in (v.GetAllRoutingPtIds(g) if v.GetGeomTypeName(g).upper()=='ROUTING' else v.GetAllBogies(g) if v.GetGeomTypeName(g).upper()=='GEAR' else [])]

def refresh_routing_anchors(v):
    # Decode can update a route before a later parent surface is ready. A
    # second vehicle Update does not dirty these attachment limits. Rebind the
    # unchanged native parent after all geometry loads to evaluate native limits.
    geoms=set(v.FindGeoms())
    for g in geoms:
        if v.GetGeomTypeName(g).upper()!='ROUTING':continue
        for p in v.GetAllRoutingPtIds(g):
            parent=v.GetRoutingPtParentID(p)
            if parent in geoms:v.SetRoutingPtParentID(p,parent)
    v.Update()

def snapshot(v,parameter):
    def params(cid):return [parameter(v,p) for p in v.FindContainerParmIDs(cid)]
    routes=[];gears=[];bors=[];aux=[];clouds=[]
    for g in v.FindGeoms():
        typ=v.GetGeomTypeName(g).upper()
        if typ=='ROUTING':
            from native_preview import symmetry_count
            copies=[dict(index=i,points=[xyz(p) for p in v.GetAllRoutingPtCoords(g,i)],curve=[xyz(p) for p in v.GetRoutingCurve(g,i)]) for i in range(symmetry_count(v,g))]
            planes=[(v.SYM_XY,'X/Y'),(v.SYM_XZ,'X/Z'),(v.SYM_YZ,'Y/Z')]
            planar=[dict(value=0,label='No mirror')]
            for mask in range(1,8):
                selected=[p for i,p in enumerate(planes) if mask&(1<<i)]
                planar.append(dict(value=sum(p[0] for p in selected),label='Mirror '+', '.join(p[1] for p in selected)))
            symmetry=dict(planar=dict(id=v.FindParm(g,'Sym_Planar_Flag','Sym'),choices=planar),axial=dict(id=v.FindParm(g,'Sym_Axial_Flag','Sym'),choices=[dict(value=value,label=label) for value,label in [(v.SYM_NONE,'No rotation copies'),(v.SYM_ROT_X,'Around X'),(v.SYM_ROT_Y,'Around Y'),(v.SYM_ROT_Z,'Around Z')]]),rotations=v.FindParm(g,'Sym_Rot_N','Sym'))
            routes.append(dict(id=g,points=[dict(id=p,index=i,parent=v.GetRoutingPtParentID(p),point=xyz(v.GetMainRoutingPtCoord(p)),params=params(p)) for i,p in enumerate(v.GetAllRoutingPtIds(g))],curve=copies[0]['curve'],copies=copies,symmetry=symmetry))
        elif typ=='GEAR':
            import native_gear_controls
            bogies=[]
            for b in v.GetAllBogies(g):
                fields=params(b);native_gear_controls.enrich(v,g,fields)
                import native_gear_retraction
                bogies.append(dict(id=b,name=v.GetContainerName(b),params=fields,retraction=native_gear_retraction.metadata(v,g,b,drawings=True)))
            import native_tire_controls
            gears.append(dict(id=g,bogies=bogies,inspectionOptions=native_tire_controls.inspection_options(v)))
        elif typ=='BODYOFREVOLUTION':
            import native_bor_curves
            b=dict(id=g,shape=v.GetBORXSecShape(g),profile=[xyz(v.ComputeBORXSecPnt(g,i/100)) for i in range(101)])
            b['editable']=native_bor_curves.details(v,g,parameter)
            import native_bor_points
            b['filePoints']=native_bor_points.snapshot(v,g)
            import native_bor_dimensions
            b['dimensions']=native_bor_dimensions.dimensions(v,g)
            b['cstFitAllowed']=b['shape'] in [getattr(v,n) for n in BOR_CST_FIT_SHAPES]
            if b['shape']==v.XS_CST_AIRFOIL:b['cst']=dict(upper=list(v.GetBORUpperCSTCoefs(g)),lower=list(v.GetBORLowerCSTCoefs(g)))
            bors.append(b)
        elif typ=='AUXILIARY':
            import native_gear_controls
            parent=v.GetGeomParent(g)
            import native_auxiliary_controls
            aux.append(dict(id=g,parent=parent,modes=native_gear_controls.auxiliary_modes(v),contacts=[v.GetAuxiliaryGeomContactPtID(g,i) for i in range(3)],bogies=list(v.GetAllBogies(parent)) if parent in v.FindGeoms() and v.GetGeomTypeName(parent).upper()=='GEAR' else [],controls=native_auxiliary_controls.metadata(v,g)))
        elif typ in ('PTCLOUD','POINTCLOUD','POINT_CLOUD'):
            import native_cloud
            clouds.append(dict(id=g,points=[xyz(p) for p in v.GetPtCloudPnts(g)],worldPoints=[xyz(p) for p in native_cloud.world_points(v,g)],coordinateFrame='Native local point coordinates'))
    return dict(routes=routes,gears=gears,bodiesOfRevolution=bors,auxiliary=aux,pointClouds=clouds,stackPresets={n:getattr(v,n) for n in dir(v) if n.startswith('STACK_PRESET_')})

def mutate(v,r):
    op=r['operation'];g=r.get('geom')
    if op.startswith('routing-'):
        one(g,[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='ROUTING']);points=list(v.GetAllRoutingPtIds(g))
        if op in ('routing-add','routing-insert'):
            parent=one(r['parent'],[p for p in v.FindGeoms() if p!=g]);surf=one(r['surface'],range(v.GetTotalNumSurfs(parent)))
            if op=='routing-add':v.AddRoutingPt(g,parent,surf)
            else:v.InsertRoutingPt(g,one(r['index'],range(len(points))),parent,surf)
        elif op=='routing-delete':v.DelRoutingPt(g,one(r['index'],range(len(points))))
        elif op=='routing-move':v.MoveRoutingPt(g,one(r['index'],range(len(points))),getattr(v,one(r['direction'],['REORDER_MOVE_UP','REORDER_MOVE_DOWN','REORDER_MOVE_TOP','REORDER_MOVE_BOTTOM'])))
        elif op=='routing-parent':
            point=one(r['id'],points);parent=one(r['parent'],[p for p in v.FindGeoms() if p!=g]);v.SetRoutingPtParentID(point,parent)
        else:return False,None
    elif op.startswith('bogie-'):
        one(g,[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='GEAR'])
        if op=='bogie-add':v.CreateAndAddBogie(g)
        elif op=='bogie-delete':
            import native_gear_controls
            bid=one(r['id'],v.GetAllBogies(g));native_gear_controls.guard_bogie_delete(v,bid);v.DelBogie(g,bid)
        elif op=='bogie-attachment':
            import native_gear_retraction
            bid=one(r['id'],v.GetAllBogies(g));native_gear_retraction.set_parent(v,g,bid,r['side'],r['parent'])
        else:return False,None
    elif op=='gear-inspection-create':
        import native_tire_controls
        g,_,_,_,_=native_tire_controls.create_inspection(v,r)
    elif op.startswith('auxiliary-profile-'):
        import native_auxiliary_controls
        native_auxiliary_controls.mutate(v,r)
    elif op=='auxiliary-setup':
        import native_gear_controls
        native_gear_controls.setup_auxiliary(v,g,r['parent'],r['type'])
    elif op=='auxiliary-contact':
        one(g,[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='AUXILIARY']);index=one(r['index'],range(3));parent=v.GetGeomParent(g)
        bogies=list(v.GetAllBogies(parent)) if parent in v.FindGeoms() and v.GetGeomTypeName(parent).upper()=='GEAR' else []
        v.SetAuxiliaryGeomContactPtID(g,index,one(r['bogie'],['']+bogies,'Choose a wheel group from the attached gear, or use its first group automatically.'))
    elif op=='auxiliary-cce':
        one(g,[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='AUXILIARY'])
        content=r['content'];path=text_file(content,'envelope.cce');lines=[s.split() for s in content.splitlines() if s.strip()]
        if len(lines)<2 or any(len(s)!=2 for s in lines):raise ValueError('Use at least two clearance-envelope rows, each containing two finite coordinates.')
        try:
            for row in lines:
                for x in row:finite(float(x))
        except (ValueError,TypeError):raise ValueError('Use two finite coordinates on each clearance-envelope row.')
        v.ReadAuxiliaryGeomCCEFile(g,path)
    elif op=='stack-preset':
        one(g,[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='STACK']);preset=one(r['preset'],[n for n in dir(v) if n.startswith('STACK_PRESET_')]);v.InitStackPreset(g,getattr(v,preset))
    elif op.startswith('bor-'):
        one(g,[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='BODYOFREVOLUTION'])
        if op=='bor-profile-drivers':
            import native_bor_dimensions
            native_bor_dimensions.set_drivers(v,r)
        if op=='bor-profile-copy':
            import native_bor_clipboard
            return native_bor_clipboard.paste(v,g,r['source'])
        if op.startswith('bor-file-'):
            import native_bor_points
            return native_bor_points.mutate(v,r)
        if op.startswith('bor-curve-'):
            import native_bor_curves
            return native_bor_curves.mutate(v,r)
        if op=='bor-shape':
            from native_editable_curves import guard_bor_shape_replacement
            shape=getattr(v,one(r['shape'],SHAPES));guard_bor_shape_replacement(v,g,shape);v.ChangeBORXSecShape(g,shape)
        elif op in ('bor-airfoil','bor-profile'):
            from native_editable_curves import guard_bor_shape_replacement
            shape=v.XS_FILE_AIRFOIL if op=='bor-airfoil' else v.XS_FILE_FUSE
            guard_bor_shape_replacement(v,g,shape);v.ChangeBORXSecShape(g,shape)
            (v.ReadBORFileAirfoil if op=='bor-airfoil' else v.ReadBORFileXSec)(g,text_file(r['content'],'bor-profile.dat'))
        elif op=='bor-cst-fit':
            if v.GetBORXSecShape(g) not in [getattr(v,n) for n in BOR_CST_FIT_SHAPES]:raise ValueError('Choose a supported airfoil profile before fitting CST.')
            from native_editable_curves import guard_bor_shape_replacement
            guard_bor_shape_replacement(v,g,v.XS_CST_AIRFOIL)
            from native_cst_validation import fitting_degree
            v.FitBORAfCST(g,fitting_degree(r.get('degree')))
        elif op=='bor-cst-degree':
            if v.GetBORXSecShape(g)!=v.XS_CST_AIRFOIL:raise ValueError('Choose a CST profile before changing its degree.')
            side=one(r['side'],['upper','lower']);direction=one(r['direction'],['promote','demote'])
            degree=getattr(v,'GetBOR'+side.title()+'CSTDegree')(g)
            if (direction=='demote' and degree<=0) or (direction=='promote' and degree>=30):raise ValueError('The supported CST degree range is 0–30.')
            getattr(v,('Promote' if direction=='promote' else 'Demote')+'BORCST'+side.title())(g)
        elif op=='bor-cst-coefficients':
            if v.GetBORXSecShape(g)!=v.XS_CST_AIRFOIL:raise ValueError('Fit the profile to CST first.')
            from native_cst_validation import coefficients
            coefficients(v,v.GetGeomParmIDs(g),r)
            v.SetBORUpperCST(g,len(r['upper'])-1,r['upper']);v.SetBORLowerCST(g,len(r['lower'])-1,r['lower'])
        else:return False,None
    elif op=='section-copy-from':
        if isinstance(r.get('source'),dict):
            source=r['source']
            if r.get('curveOnly',True):
                target,ts,ti,_=section(v,r)
                from native_curve_copy_points import copy_to_section
                copy_to_section(v,source,ts,ti)
                return True,target
            if source.get('kind')!='section':raise ValueError('Whole-section copies require an ordinary section source. Choose Profile only for this source.')
            r={**r,'sourceGeom':source['geom'],'sourceSurface':source.get('surface',0),'sourceIndex':source['index']}
        if r.get('sourceKind')=='bor':
            if not r.get('curveOnly',True):raise ValueError('Choose Profile only when copying from a body of revolution.')
            target,ts,ti,_=section(v,r)
            if r.get('surface',0)!=0:raise ValueError('Native section clipboard uses section surface 0.')
            from native_curve_copy_points import copy_to_section
            copy_to_section(v,dict(kind='bor',geom=r['sourceGeom']),ts,ti)
            return True,target
        target,ts,ti,tx=section(v,r);source,ss,si,sx=section(v,dict(geom=r['sourceGeom'],surface=r['sourceSurface'],index=r['sourceIndex']))
        if r.get('curveOnly',True):
            from native_curve_copy_points import copy_to_section
            copy_to_section(v,dict(kind='section',geom=source,surface=r['sourceSurface'],index=si),ts,ti)
        else:
            from native_section_copy import replace
            replace(v,r)
    elif op=='body-skin-reset-all':
        one(g,[gid for gid in v.FindGeoms() if v.GetGeomTypeName(gid).upper() in ('FUSELAGE','STACK')],'Choose a fuselage or stack.')
        for surface in range(v.GetNumXSecSurfs(g)):
            surf=v.GetXSecSurf(g,surface)
            for i in range(v.GetNumXSec(surf)):v.ResetXSecSkinParms(v.GetXSec(surf,i))
    elif op in ('section-skin','section-skin-reset','section-profile-import','section-reparameterize'):
        g,s,i,x=section(v,r)
        if op.startswith('section-skin'):
            if v.GetGeomTypeName(g).upper() not in ('FUSELAGE','STACK'):raise ValueError('Skinning controls require a fuselage or stack section.')
            if op=='section-skin-reset':v.ResetXSecSkinParms(x)
            else:
                v.SetXSecContinuity(x,one(r['continuity'],range(3)))
                side=getattr(v,one(r['side'],['XSEC_LEFT_SIDE','XSEC_RIGHT_SIDE','XSEC_BOTH_SIDES']))
                for label,fn in [('angles',v.SetXSecTanAngles),('slews',v.SetXSecTanSlews),('strengths',v.SetXSecTanStrengths),('curvatures',v.SetXSecCurvatures)]:
                    values=r[label]
                    if not isinstance(values,list) or len(values)!=4:raise ValueError('Enter top, right, bottom, and left constraints.')
                    fn(x,side,*[finite(value) for value in values])
        elif op=='section-profile-import':
            from native_editable_curves import guard_shape_replacement
            guard_shape_replacement(v,x,v.XS_FILE_FUSE)
            v.ChangeXSecShape(s,i,v.XS_FILE_FUSE);v.ReadFileXSec(v.GetXSec(s,i),text_file(r['content'],'section.fxs'))
        else:
            if v.GetXSecShape(x)!=v.XS_EDIT_CURVE:raise ValueError('Choose an editable curve.')
            v.ReparameterizeEditXSec(x)
    elif op=='point-cloud-create':
        points=r['points']
        if not isinstance(points,list) or not 1<=len(points)<=100000:raise ValueError('Use 1–100000 points.')
        from native_fit import vector
        g=v.CreatePtCloudGeomFromPts([vector(v,p) for p in points],name(r['name']))
    elif op=='point-cloud-from-mesh':
        one(g,[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='MESH']);g=v.CreatePtCloudGeom(g)
    elif op=='point-cloud-hull':
        one(g,[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper() in ('PTCLOUD','POINTCLOUD','POINT_CLOUD')]);source=g;g=v.CreateConvexHull(source)
        if g not in v.FindGeoms():raise ValueError('A three-dimensional hull needs noncoplanar native points.')
        v.SetGeomParent(g,source);parms={v.GetParmName(p):p for p in v.GetGeomParmIDs(g)}
        for key,value in [('Trans_Attach_Flag',v.ATTACH_TRANS_COMP),('Rots_Attach_Flag',v.ATTACH_ROT_COMP),('Scale',v.GetParmVal(source,'Scale_From_Original','XForm'))]:v.SetParmValUpdate(parms[key],value)
    elif op=='point-cloud-project':
        one(g,[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper() in ('PTCLOUD','POINTCLOUD','POINT_CLOUD')]);target=one(r['target'],v.FindGeoms());surf=one(r['surface'],range(v.GetTotalNumSurfs(target)));direction=one(r['direction'],[v.X_DIR,v.Y_DIR,v.Z_DIR])
        import native_cloud
        native_cloud.project(v,g,target,surf,direction)
    else:return False,None
    return True,g
