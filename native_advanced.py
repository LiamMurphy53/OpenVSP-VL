"""Additional native engineering workflows and model-global settings."""
import native_references
import native_regions
import native_region_curves
import native_intersection_selection
import native_intersection_defaults
import re
import native_prop_drivers

GLOBAL_NAMES={'Vehicle','CFDMeshSettings','SurfaceIntersectSettings','CFDGridDensity','VSPAEROSettings','WaveDragSettings','ParasiteDragSettings'}
PROP_CURVES=['PROP_CHORD','PROP_TWIST','PROP_THICK','PROP_CLI','PROP_RAKE','PROP_SKEW','PROP_SWEEP','PROP_AXIAL','PROP_TANGENTIAL']
SUBSURF_TYPES=['SS_LINE','SS_RECTANGLE','SS_ELLIPSE','SS_CONTROL','SS_LINE_ARRAY','SS_FINITE_LINE','SS_XSEC_CURVE','SS_INTERSECT']
PART_TYPES=['FEA_RIB','FEA_SPAR','FEA_SLICE','FEA_FIX_POINT','FEA_DOME','FEA_RIB_ARRAY','FEA_SLICE_ARRAY','FEA_TRIM','FEA_POLY_SPAR']


def enums(v,names):return {n:getattr(v,n) for n in names if hasattr(v,n)}


def laminate_materials(v):
    return [m for m in v.GetFeaMaterialIDVec() if v.GetParmVal(v.FindParm(m,'FeaMaterialType','FeaMaterial'))==v.FEA_LAMINATE]


def container_ids(v):
    ids=[c for c in v.FindContainers() if v.GetContainerName(c) in GLOBAL_NAMES]
    ids.extend(v.FindActuatorDisk(i) for i in range(v.GetNumActuatorDisks()))
    ids.extend(v.FindUnsteadyGroup(i) for i in range(v.GetNumUnsteadyGroups()))
    for s in v.GetFeaStructIDVec():
        ids.extend(v.GetFeaBCIDVec(s));ids.extend(v.GetFeaSubSurfIDVec(s))
        for p in v.GetFeaPartIDVec(s):
            if v.GetFeaPartType(p)==v.FEA_POLY_SPAR:ids.extend(v.GetAllFeaPolySparPtIDVec(p))
    for m in laminate_materials(v):ids.extend(v.GetFeaLayerIDVec(m))
    for a in v.GetFeaAssemblyIDVec():
        ids.append(a);ids.extend(v.GetFeaAssemblyConnectionID(a,i) for i in range(v.NumFeaAssemblyConnections(a)))
    ids.extend(v.GetAllModes())
    return ids


def snapshot(v,parameter,refs=None):
    import native_excrescences
    import native_parasite_controls
    import native_wave_controls
    import native_connection_controls
    import native_rotor_speeds
    import native_rotor_disks
    def parms(cid):return [parameter(v,p) for p in v.FindContainerParmIDs(cid)]
    if refs is None:refs=native_references.references(v)
    propellers=[]
    for g in v.FindGeoms():
        if v.GetGeomTypeName(g).upper() not in ('PROP','PROPELLER'):continue
        import native_prop_controls
        curves=[]
        for n in PROP_CURVES:
            if not hasattr(v,n):continue
            curve=dict(name=n,index=getattr(v,n),type=v.PCurveGetType(g,getattr(v,n)),stations=list(v.PCurveGetTVec(g,getattr(v,n))),values=list(v.PCurveGetValVec(g,getattr(v,n))))
            curve.update(native_prop_controls.curve_details(v,g,curve));curves.append(curve)
        propellers.append(dict(id=g,curves=curves))
    return dict(
        rotorSpeedBackup=native_rotor_speeds.configuration(v),
        rotorDiskBackup=native_rotor_disks.configuration(v),
        propellers=propellers,propModes=enums(v,['PROP_BLADES','PROP_BOTH','PROP_DISK']),
        globalSettings=[dict(id=c,name=v.GetContainerName(c),params=parms(c),waveGuide=native_wave_controls.configuration(v,refs) if v.GetContainerName(c)=='WaveDragSettings' else None,parasiteGuide=native_parasite_controls.configuration(v,refs) if v.GetContainerName(c)=='ParasiteDragSettings' else None,selection=native_intersection_selection.configuration(v,parameter) if v.GetContainerName(c)=='SurfaceIntersectSettings' else None,exportDefaults=native_intersection_defaults.configuration(v,parameter) if v.GetContainerName(c)=='SurfaceIntersectSettings' else None) for c in v.FindContainers() if v.GetContainerName(c) in GLOBAL_NAMES],
        propDriverCombinations=native_prop_drivers.native_preview.prop_driver_combinations(v) if v.GetNumActuatorDisks() else [],
        disks=[dict(id=v.FindActuatorDisk(i),index=i,name=v.GetContainerName(v.FindActuatorDisk(i)),**native_prop_drivers.configuration(v,v.FindActuatorDisk(i),refs,parameter)) for i in range(v.GetNumActuatorDisks())],
        rotatingGroups=[dict(id=v.FindUnsteadyGroup(i),index=i,name=v.GetUnsteadyGroupName(i),components=list(v.GetUnsteadyGroupCompIDs(i)),surfaces=list(v.GetUnsteadyGroupSurfIndexes(i)),params=parms(v.FindUnsteadyGroup(i))) for i in range(v.GetNumUnsteadyGroups())],
        boundaryConditions=[dict(structure=s,id=b,name=v.GetContainerName(b),references=refs.get(b,{}),params=parms(b)) for s in v.GetFeaStructIDVec() for b in v.GetFeaBCIDVec(s)],
        structuralSubsurfaces=[dict(structure=s,id=p,name=v.GetFeaSubSurfName(p),params=native_region_curves.parameters(v,p,refs,parameter),**native_regions.details(v,p,refs),**native_region_curves.details(v,p,refs,parameter)) for s in v.GetFeaStructIDVec() for p in v.GetFeaSubSurfIDVec(s)],
        layers=[dict(material=m,id=l,name=v.GetContainerName(l),references=refs.get(l,{}),params=parms(l)) for m in laminate_materials(v) for l in v.GetFeaLayerIDVec(m)],
        assemblies=[dict(id=a,name=v.GetFeaAssemblyName(a),structures=list(v.GetFeaAssemblyStructureIDVec(a)),fixedPoints=native_connection_controls.catalog(v,a),params=parms(a),connections=[dict(id=v.GetFeaAssemblyConnectionID(a,i),index=i,references=refs.get(v.GetFeaAssemblyConnectionID(a,i),{}),params=parms(v.GetFeaAssemblyConnectionID(a,i))) for i in range(v.NumFeaAssemblyConnections(a))]) for a in v.GetFeaAssemblyIDVec()],
        modes=[dict(id=m,name=v.GetModeName(m),params=parms(m),groups=list(v.ModeGetAllGroups(m)),settings=list(v.ModeGetAllSettings(m))) for m in v.GetAllModes()],
        advancedLinks=[dict(index=i,name=v.GetAdvLinkName(i),code=v.GetAdvLinkCode(i),inputs=[dict(name=n,parameter=p) for n,p in zip(v.GetAdvLinkInputNames(i),v.GetAdvLinkInputParms(i))],outputs=[dict(name=n,parameter=p) for n,p in zip(v.GetAdvLinkOutputNames(i),v.GetAdvLinkOutputParms(i))]) for i in range(len(v.GetAdvLinkNames()))],
        designVariables=[dict(parameter=v.GetDesignVar(i),type=v.GetDesignVarType(i)) for i in range(v.GetNumDesignVars())],
        subsurfaceTypes=enums(v,SUBSURF_TYPES),partTypes=enums(v,PART_TYPES),
        polySparPointTypes=enums(v,['POLY_SPAR_POINT_U01','POLY_SPAR_POINT_U0N','POLY_SPAR_POINT_ETA']),
        ribOrientations=enums(v,['NO_NORMAL','LE_NORMAL','TE_NORMAL','SPAR_NORMAL']),
        fixedPointTypes=enums(v,['FEA_FIX_PT_ON_BODY','FEA_FIX_PT_GLOBAL_XYZ','FEA_FIX_PT_DELTA_XYZ','FEA_FIX_PT_DELTA_UVN','FEA_FIX_PT_GEOM_ORIGIN','FEA_FIX_PT_GEOM_CG']),
        fixedPointMassUnits=enums(v,['MASS_UNIT_G','MASS_UNIT_KG','MASS_UNIT_TONNE','MASS_UNIT_LBM','MASS_UNIT_SLUG','MASS_LBFSEC2IN']),
        regionTests=enums(v,['INSIDE','OUTSIDE','NONE']),regionLineTypes=enums(v,['CONST_U','CONST_W']),
        boundaryTypes=enums(v,['FEA_BC_STRUCTURE','FEA_BC_PART','FEA_BC_SUBSURF']),boundaryModes=enums(v,['FEA_BCM_USER','FEA_BCM_ALL','FEA_BCM_PIN','FEA_BCM_SYMM','FEA_BCM_ASYMM']),
        materialTypes=enums(v,['FEA_ISOTROPIC','FEA_ENG_ORTHO','FEA_ENG_ORTHO_TRANS_ISO','FEA_LAMINATE']),
        reorderTypes=enums(v,['REORDER_MOVE_UP','REORDER_MOVE_DOWN','REORDER_MOVE_TOP','REORDER_MOVE_BOTTOM']),
        excrescences=native_excrescences.read(v),excrescenceChoices=native_excrescences.choices(v),excrescenceCount=v.GetNumExcrescences(),excrescenceTypes=enums(v,[n for n in dir(v) if n.startswith('EXCRESCENCE_')]))


def mutate(v,r):
    from native_tools import finite,name,one
    op=r['operation'];g=r.get('geom')
    if op in ('property-rename','property-delete','material-rename','material-delete','property-copy','material-copy'):
        import native_structural_library
        return native_structural_library.mutate(v,r)
    if op=='property-material':
        prop=one(r['id'],v.GetFeaPropertyIDVec());material=one(r['material'],v.GetFeaMaterialIDVec())
        native_references.set_reference(v,prop,'FeaPropertyInfo','FeaMaterialID',material)
    if op=='assembly-connection-edit':
        import native_connection_controls
        native_connection_controls.edit(v,r)
    if op in ('rotor-disks-save','rotor-disks-restore','rotor-disks-restore-values'):
        import native_rotor_disks
        native_rotor_disks.mutate(v,op)
        return True,None
    if op in ('rotor-speeds-save','rotor-speeds-restore'):
        import native_rotor_speeds
        native_rotor_speeds.mutate(v,op)
        return True,None
    if op=='rotor-disk-drivers':
        native_prop_drivers.mutate(v,r)
        return True,None
    if op in ('region-curve-replace-points','region-curve-init','region-curve-point','region-curve-fixed','region-curve-smooth','region-curve-type','region-curve-split','region-curve-delete','region-curve-reparameterize'):
        import native_region_curves
        return native_region_curves.mutate_edit(v,r)
    if op in ('region-curve-shape','region-curve-convert','region-curve-copy-from','region-curve-import'):
        import native_region_curves
        return native_region_curves.mutate(v,r)
    elif op=='analysis-reference':
        import native_guides
        native_guides.set_reference(v,r)
        return True,None
    elif op.startswith('attribute-') or op=='model-notes':
        import native_attributes
        return native_attributes.mutate(v,r)
    elif op.startswith('part-'):
        import native_structure
        return native_structure.mutate(v,r)
    elif op.startswith(('routing-','bogie-','bor-','section-','point-cloud-','auxiliary-')) or op in ('stack-preset','body-skin-reset-all','gear-inspection-create'):
        import native_special
        return native_special.mutate(v,r)
    elif op.startswith('fit-') or op=='clearance-snap' or op.startswith('measurement-'):
        import native_fit
        return native_fit.mutate(v,r)
    elif op=='geometry-import':
        import native_files
        g=native_files.import_geometry(v,r)
    elif op=='design-file-apply':
        import native_files
        native_files.apply_design(v,r)
    elif op.startswith('prop-'):
        one(g,v.FindGeoms())
        if v.GetGeomTypeName(g).upper() not in ('PROP','PROPELLER'):raise ValueError('Choose a propeller component.')
        if op=='prop-approximate':v.ApproximateAllPropellerPCurves(g)
        elif op=='prop-reset-thickness':v.ResetPropellerThicknessCurve(g)
        else:
            curve=getattr(v,one(r['curve'],PROP_CURVES));stations=list(v.PCurveGetTVec(g,curve));typ=v.PCurveGetType(g,curve)
            if op=='prop-curve-type':v.PCurveConvertTo(g,curve,getattr(v,one(r['type'],['LINEAR','PCHIP','CEDIT'])))
            elif op=='prop-curve-set':
                t,y=r['stations'],r['values']
                if not isinstance(t,list) or not isinstance(y,list) or len(t)!=len(y) or not 2<=len(t)<=1000:raise ValueError('Use matching station/value arrays with 2–1000 points.')
                for x in t+y:finite(x)
                if any(not 0<=x<=1 for x in t) or any(a>=b for a,b in zip(t,t[1:])):raise ValueError('Radius fractions must increase strictly between 0 and 1.')
                if typ==v.CEDIT and (len(t)-1)%3:raise ValueError('Bezier curves require groups of three handles plus the final endpoint.')
                v.SetPCurve(g,curve,t,y,typ)
            elif op=='prop-curve-split':
                t=finite(r['station'])
                if not stations[0]<t<stations[-1]:raise ValueError('Insert inside the existing radius range.')
                v.PCurveSplit(g,curve,t)
            elif op=='prop-curve-delete':
                i=one(r['index'],range(1,len(stations)-1))
                if typ==v.CEDIT and i%3:raise ValueError('Remove a Bezier anchor, not an individual handle.')
                v.PCurveDeletePt(g,curve,i)
            else:return False,None
    elif op in ('subsurface-add','subsurface-rename','subsurface-reorder','subsurface-intersect','subsurface-property'):
        one(g,v.FindGeoms())
        if op=='subsurface-add':
            typ=one(r['type'],enums(v,SUBSURF_TYPES));surface=one(r.get('surface',0),range(v.GetNumMainSurfs(g)))
            if typ=='SS_LINE_ARRAY':raise ValueError('Line arrays are structural regions. Add one in Constraints & laminates.')
            if typ=='SS_CONTROL' and v.GetGeomTypeName(g).upper() not in ('WING','PROP','PROPELLER'):raise ValueError('Control boundaries require a wing or propeller.')
            cid=v.AddSubSurf(g,getattr(v,typ),surface);v.SetSubSurfName(cid,name(r['name']))
        else:
            sid=one(r['id'],v.GetSubSurfIDVec(g))
            if op=='subsurface-property':
                role=one(r['role'],['shell','beam']);typ=v.FEA_SHELL if role=='shell' else v.FEA_BEAM
                prop=one(r['property'],[p for p in v.GetFeaPropertyIDVec() if v.GetParmVal(v.FindParm(p,'FeaPropertyType','FeaProperty'))==typ],'Choose a matching '+role+' property.')
                native_references.set_reference(v,sid,'SubSurface','FeaPropertyID' if role=='shell' else 'CapFeaPropertyID',prop)
            elif op=='subsurface-rename':v.SetSubSurfName(sid,name(r['name']))
            elif op=='subsurface-intersect':
                if v.GetSubSurfType(sid)!=v.SS_INTERSECT:raise ValueError('Choose an intersection region.')
                target=one(r['target'],[x for x in v.FindGeoms() if x!=g],'Choose another component to intersect.')
                v.SetIntersectSubSurfGeomID(sid,target);v.Update();v.IntersectSubSurf(sid)
            else:v.ReorderSubSurf(g,sid,getattr(v,one(r['direction'],enums(v,['REORDER_MOVE_UP','REORDER_MOVE_DOWN','REORDER_MOVE_TOP','REORDER_MOVE_BOTTOM']))))
    elif op=='component-reorder':
        one(g,v.FindGeoms());v.ReorderGeom(g,getattr(v,one(r['direction'],enums(v,['REORDER_MOVE_UP','REORDER_MOVE_DOWN','REORDER_MOVE_TOP','REORDER_MOVE_BOTTOM']))))
    elif op in ('boundary-add','boundary-delete'):
        s=one(r['structure'],v.GetFeaStructIDVec())
        if op=='boundary-add':
            b=v.AddFeaBC(s,getattr(v,one(r['type'],enums(v,['FEA_BC_STRUCTURE','FEA_BC_PART','FEA_BC_SUBSURF']))));v.SetContainerName(b,name(r['name']))
        else:v.DelFeaBC(s,one(r['id'],v.GetFeaBCIDVec(s)))
    elif op in ('layer-add','layer-delete','layer-reorder'):
        m=one(r['material'],v.GetFeaMaterialIDVec())
        if v.GetParmVal(v.FindParm(m,'FeaMaterialType','FeaMaterial'))!=v.FEA_LAMINATE:raise ValueError('Choose a laminate material.')
        if op=='layer-add':v.AddFeaLayer(m)
        else:
            l=one(r['id'],v.GetFeaLayerIDVec(m))
            if op=='layer-delete':
                if v.NumFeaLayers(m)<=1:raise ValueError('Keep at least one layer in a laminate.')
                v.DeleteFeaLayer(m,l)
            else:v.ReorderFeaLayer(m,l,getattr(v,one(r['direction'],enums(v,['REORDER_MOVE_UP','REORDER_MOVE_DOWN','REORDER_MOVE_TOP','REORDER_MOVE_BOTTOM']))))
    elif op=='layer-material':
        m=one(r['material'],laminate_materials(v));l=one(r['id'],v.GetFeaLayerIDVec(m));lamina=one(r['lamina'],v.GetFeaMaterialIDVec())
        if lamina in laminate_materials(v):raise ValueError('Choose a single lamina material, not another laminate.')
        native_references.set_reference(v,l,'FeaLayerInfo','FeaLaminaID',lamina)
    elif op=='boundary-target':
        s=one(r['structure'],v.GetFeaStructIDVec());b=one(r['id'],v.GetFeaBCIDVec(s));typ=int(v.GetParmVal(v.FindParm(b,'Type','FeaBC')))
        if typ==v.FEA_BC_PART:key='PartID';target=one(r['target'],v.GetFeaPartIDVec(s))
        elif typ==v.FEA_BC_SUBSURF:key='SubSurfID';target=one(r['target'],v.GetFeaSubSurfIDVec(s))
        else:raise ValueError('Whole-structure constraints do not require a part target.')
        native_references.set_reference(v,b,'FeaBCInfo',key,target)
    elif op in ('assembly-connection-add','assembly-connection-delete'):
        a=one(r['assembly'],v.GetFeaAssemblyIDVec())
        if op.endswith('delete'):v.DeleteFeaAssemblyConnection(a,one(r['index'],range(v.NumFeaAssemblyConnections(a))))
        else:
            ends=[]
            for side in ('start','end'):
                s=one(r[side+'Structure'],v.GetFeaAssemblyStructureIDVec(a));p=one(r[side+'Point'],v.GetFeaPartIDVec(s))
                if v.GetFeaPartType(p)!=v.FEA_FIX_POINT:raise ValueError('Connections require fixed-point structural parts.')
                index=r.get(side+'Index',0)
                if isinstance(index,bool) or not isinstance(index,int) or index<0:raise ValueError('Use a nonnegative fixed-point copy index.')
                import native_connection_controls
                one(index,range(len(native_connection_controls.copies(v,p))),'Choose an available native fixed-point copy.')
                ends.extend([p,s,index])
            if ends[:3]==ends[3:]:raise ValueError('Choose two different fixed points.')
            v.AddFeaAssemblyConnection(a,*ends)
    elif op in ('assembly-add','assembly-delete','assembly-member','assembly-rename'):
        if op=='assembly-add':a=v.AddFeaAssembly();v.SetFeaAssemblyName(a,name(r['name']))
        else:
            a=one(r['id'],v.GetFeaAssemblyIDVec())
            if op=='assembly-delete':v.DeleteFeaAssembly(a)
            elif op=='assembly-rename':v.SetFeaAssemblyName(a,name(r['name']))
            else:
                s=one(r['structure'],v.GetFeaStructIDVec());add=r['member']
                if not isinstance(add,bool):raise ValueError('Choose whether this structure belongs to the assembly.')
                present=s in v.GetFeaAssemblyStructureIDVec(a)
                if add and not present:v.AddFeaStructureToAssembly(a,s)
                if not add and present:v.DeleteFeaStructureFromAssembly(a,s)
    elif op.startswith('structural-subsurface-'):
        return native_regions.mutate(v,r)
    elif op=='mode-add':
        v.CreateAndAddMode(name(r['name']),one(r['set'],range(v.GetNumSets())),one(r.get('degenSet',-1),range(-1,v.GetNumSets())))
    elif op in ('mode-delete','mode-apply','mode-rename','mode-preset-add','mode-preset-remove'):
        m=one(r['id'],v.GetAllModes())
        if op=='mode-delete':
            import native_cfd
            import native_parasite_controls
            native_parasite_controls.guard_mode_delete(v,m)
            import native_wave_controls
            native_wave_controls.guard_mode_delete(v,m)
            native_cfd.guard_mode_delete(v,m)
            native_intersection_selection.guard_mode_delete(v,m)
            v.DelMode(m)
        elif op=='mode-rename':v.SetModeName(m,name(r['name']))
        elif op=='mode-apply':v.ApplyModeSettings(m)
        elif op=='mode-preset-remove':v.RemoveGroupSetting(m,one(r['index'],range(len(v.ModeGetAllGroups(m)))))
        else:
            p=one(r['group'],v.GetVarPresetGroups());s=one(r['setting'],v.GetVarPresetSettings(p));v.ModeAddGroupSetting(m,p,s)
    elif op=='preset-setting-values':
        group=one(r['group'],v.GetVarPresetGroups());setting=one(r['setting'],v.GetVarPresetSettings(group))
        entries=r['entries'];allowed=set(v.GetVarPresetParmIDs(group));seen=set();changes=[]
        if not isinstance(entries,list) or not entries:raise ValueError('Choose saved parameter values to edit.')
        for entry in entries:
            if not isinstance(entry,dict):raise ValueError('Choose a saved parameter and numeric value.')
            parameter=one(entry.get('parameter'),allowed)
            if parameter in seen:raise ValueError('Each saved parameter may appear only once.')
            seen.add(parameter);changes.append((parameter,finite(entry.get('value'))))
        for parameter,value in changes:v.SetVarPresetParmVal(group,setting,parameter,value)
    elif op in ('preset-setting-add','preset-setting-delete','preset-setting-update','preset-setting-rename'):
        p=one(r['group'],v.GetVarPresetGroups())
        if op=='preset-setting-add':s=v.AddVarPresetSetting(p,name(r['name']));v.SaveVarPresetParmVals(p,s)
        else:
            s=one(r['setting'],v.GetVarPresetSettings(p))
            if op=='preset-setting-delete':
                import native_preset_references
                native_preset_references.guard_delete(v,p,s);v.DeleteVarPresetSetting(p,s)
            elif op=='preset-setting-update':v.SaveVarPresetParmVals(p,s)
            else:v.SetSettingName(s,name(r['name']))
    elif op=='user-limits':
        p=one(r['id'],v.GetAllUserParms());lo=finite(r['min']);hi=finite(r['max'])
        if lo>hi:raise ValueError('The lower limit must not exceed the upper limit.')
        v.SetParmUpperLimit(p,max(hi,v.GetParmLowerLimit(p)));v.SetParmLowerLimit(p,lo);v.SetParmUpperLimit(p,hi);v.SetParmValUpdate(p,v.GetParmVal(p))
    elif op=='user-delete':v.DeleteUserParm(one(r['id'],v.GetAllUserParms()))
    elif op in ('advanced-link-save','advanced-link-delete'):
        names=list(v.GetAdvLinkNames());index=r.get('index')
        if index is not None:
            one(index,range(len(names)));one(r.get('expectedName'),[names[index]],'This expression changed. Reload before editing it.')
        if op=='advanced-link-delete':
            if index is None:raise ValueError('Choose an expression to remove.')
            v.DelAdvLink(index)
        else:
            title=name(r['name'])
            if any(n==title and i!=index for i,n in enumerate(names)):raise ValueError('Use a unique expression name.')
            from native_tools import parameter_ids
            allowed=parameter_ids(v)|{p for g in v.FindGeoms() for p in v.GetGeomParmIDs(g)}
            inputs,outputs=r['inputs'],r['outputs'];code=r['code']
            if not isinstance(code,str) or not code.strip() or len(code)>100000:raise ValueError('Enter native expression code of 1–100000 characters.')
            if not isinstance(inputs,list) or not isinstance(outputs,list) or not inputs or not outputs or len(inputs)+len(outputs)>100:raise ValueError('Declare input and output variables (at most 100 total).')
            for e in inputs+outputs:
                one(e['parameter'],allowed)
                if not isinstance(e['name'],str) or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',e['name']):raise ValueError('Variable names must be identifiers, such as span or chord.')
            if len({e['name'] for e in inputs+outputs})!=len(inputs)+len(outputs):raise ValueError('Use unique expression variable names.')
            if len({e['parameter'] for e in outputs})!=len(outputs):raise ValueError('Each output must drive a different parameter.')
            edges={}
            def connect(a,b):edges.setdefault(a,set()).add(b)
            for i in range(v.GetNumParmLinks()):connect(v.GetParmLinkAParm(v.GetParmLinkID(i)),v.GetParmLinkBParm(v.GetParmLinkID(i)))
            for i in range(len(names)):
                if i!=index:
                    for a in v.GetAdvLinkInputParms(i):
                        for b in v.GetAdvLinkOutputParms(i):connect(a,b)
            for a in inputs:
                for b in outputs:connect(a['parameter'],b['parameter'])
            visited,stack=set(),set()
            def visit(p):
                if p in stack:raise ValueError('This expression would create a parameter dependency cycle.')
                if p in visited:return
                stack.add(p)
                for q in edges.get(p,[]):visit(q)
                stack.remove(p);visited.add(p)
            for p in edges:visit(p)
            if index is None:v.AddAdvLink(title);index=v.GetLinkIndex(title)
            else:v.SetAdvLinkName(index,title);v.DelAllAdvLinkInputs(index);v.DelAllAdvLinkOutputs(index)
            for e in inputs:v.AddAdvLinkInput(index,e['parameter'],e['name'])
            for e in outputs:v.AddAdvLinkOutput(index,e['parameter'],e['name'])
            v.SetAdvLinkCode(index,code)
            if not v.BuildAdvLinkScript(index):raise ValueError('OpenVSP could not compile the expression. Check variable names and native AngelScript syntax. The previous model is preserved.')
    elif op=='design-variables':
        from native_tools import parameter_ids
        ids={p for g in v.FindGeoms() for p in v.GetGeomParmIDs(g)}|parameter_ids(v)
        entries=r['entries']
        for e in entries:one(e['parameter'],ids);one(e['type'],[v.XDDM_VAR,v.XDDM_CONST])
        v.DeleteAllDesignVars()
        for e in entries:v.AddDesignVar(e['parameter'],e['type'])
        import native_files
        native_files.save_design(v)
    elif op in ('wave-reference-wing','wave-reference-mode','wave-flow-faces'):
        import native_wave_controls
        native_wave_controls.mutate(v,r)
        return True,None
    elif op in ('parasite-reference-wing','parasite-reference-mode','parasite-pressure-unit'):
        import native_parasite_controls
        native_parasite_controls.mutate(v,r)
        return True,None
    elif op in ('excrescence-add','excrescence-delete','excrescence-update','excrescence-clear'):
        import native_excrescences
        return native_excrescences.mutate(v,r)
    else:return False,None
    return True,g
