"""Native fitting, surface evaluation, and measurement workflows."""
import json
from native_tools import one,finite,name

TARGETS='Studio.FitTargets';VARIABLE='Studio.FitVariable'
REPORT='Studio.FitReport'
VARIABLE_REF='Studio.FitVariableReference'
TERMINATION={1:'Residual change reached native tolerance.',2:'Variable change reached native tolerance.',3:'Residual and variable changes reached native tolerance.',4:'Residual is orthogonal to the Jacobian within native tolerance.',5:'Function evaluation limit reached.',6:'Tolerance is too small for further residual reduction.',7:'Tolerance is too small for further variable improvement.',8:'Tolerance is too small for further orthogonality improvement.'}


def xyz(p):return [p.x(),p.y(),p.z()]
def vector(v,p):
    if not isinstance(p,list) or len(p)!=3:raise ValueError('Enter three model coordinates X, Y, Z.')
    return v.vec3d(*[finite(x) for x in p])
def coord(x):
    x=finite(x)
    if not 0<=x<=1:raise ValueError('Surface coordinates must be between 0 and 1.')
    return x

def surface(v,r,prefix=''):
    g=one(r[prefix+'geom'],v.FindGeoms());s=one(r.get(prefix+'surface',0),range(v.GetTotalNumSurfs(g)))
    u,w=v.GetUWTess01(g,s%max(1,v.GetNumMainSurfs(g)))
    if len(u)<2 or len(w)<2:raise ValueError('This native surface is degenerate. Configure its geometry before evaluating or fitting it.')
    return g,s


def save(v):
    for g in v.FindGeoms():
        coll=v.GetChildCollection(g)
        for a in v.FindAttributesInCollection(coll):
            if v.GetAttributeName(a)==TARGETS:v.DeleteAttribute(a)
        records=[dict(index=i,point=xyz(v.GetFitModelTargetPt(i)),surface=v.GetFitModelTargetPtSurfIndx(i),u=v.GetFitModelTargetPtU(i),w=v.GetFitModelTargetPtW(i),utype=v.GetFitModelTargetPtUType(i),wtype=v.GetFitModelTargetPtWType(i)) for i in range(v.GetNumFitModelTargetPts()) if v.GetFitModelTargetPtGeom(i)==g]
        if records:v.AddAttributeString(coll,TARGETS,json.dumps(records))
    coll=v.GetChildCollection(v.GetVehicleID())
    for a in v.FindAttributesInCollection(coll):
        if v.GetAttributeName(a) in (VARIABLE,VARIABLE_REF):v.DeleteAttribute(a)
    from native_fit_variables import key
    for p in v.GetFitModelVarVec():
        ref=key(v,p)
        if ref==p:v.AddAttributeParm(coll,VARIABLE,p)
        else:v.AddAttributeString(coll,VARIABLE_REF,ref)


def restore(v):
    v.ResetFitModel();records=[]
    for g in v.FindGeoms():
        for a in v.FindAttributesInCollection(v.GetChildCollection(g)):
            if v.GetAttributeName(a)==TARGETS:
                for content in v.GetAttributeStringVal(a):
                    entries=json.loads(content)
                    if not isinstance(entries,list) or len(entries)>10000:raise ValueError('Invalid saved fit targets.')
                    for e in entries:
                        if e['surface'] in range(v.GetTotalNumSurfs(g)):records.append((g,e))
    if len(records)>10000:raise ValueError('Use at most 10000 fitting targets.')
    for g,e in sorted(records,key=lambda p:p[1]['index']):
        ut=one(e['utype'],[v.FIT_MODEL_FIXED,v.FIT_MODEL_FREE]);wt=one(e['wtype'],[v.FIT_MODEL_FIXED,v.FIT_MODEL_FREE]);u=coord(e['u']);w=coord(e['w'])
        i=v.AddFitModelTargetPt(g,e['surface'],vector(v,e['point']),ut,wt,u,w);v.SetFitModelTargetPtUW(i,u,w)
    for a in v.FindAttributesInCollection(v.GetChildCollection(v.GetVehicleID())):
        if v.GetAttributeName(a)==VARIABLE_REF:
            from native_fit_variables import resolve
            for ref in v.GetAttributeStringVal(a):
                p=resolve(v,ref)
                if p not in v.GetFitModelVarVec():v.AddFitModelVar(p)
        if v.GetAttributeName(a)==VARIABLE:
            for p in v.GetAttributeParmID(a):
                if v.ValidParm(p) and p not in v.GetFitModelVarVec():v.AddFitModelVar(p)


def snapshot(v,parameter):
    import native_fit_variables,native_measurements
    native_measurements.refresh(v)
    measurementRefs=native_measurements.references(v)
    reports=[json.loads(content) for a in v.FindAttributesInCollection(v.GetChildCollection(v.GetVehicleID())) if v.GetAttributeName(a)==REPORT for content in v.GetAttributeStringVal(a)]
    return dict(fit=dict(variableChoices=native_fit_variables.configuration(v,parameter),report=reports[-1] if reports else None,distance=v.UpdateFitModelDist() if v.GetNumFitModelTargetPts() else None,degreesOfFreedom=v.GetNumFitModelOptVars(),variables=[native_fit_variables.key(v,p) for p in v.GetFitModelVarVec()],targets=[dict(index=i,geom=v.GetFitModelTargetPtGeom(i),surface=v.GetFitModelTargetPtSurfIndx(i),point=xyz(v.GetFitModelTargetPt(i)),surfacePoint=xyz(v.GetFitModelTargetPtSurfPt(i)),distance=v.GetFitModelTargetPtDist(i),u=v.GetFitModelTargetPtU(i),w=v.GetFitModelTargetPtW(i),utype=v.GetFitModelTargetPtUType(i),wtype=v.GetFitModelTargetPtWType(i)) for i in range(v.GetNumFitModelTargetPts())]),
                measurements=[dict(id=p,kind=kind,name=v.GetContainerName(p),references=measurementRefs.get(p,{}),params=[parameter(v,x) for x in v.FindContainerParmIDs(p)]) for kind,ids in [('ruler',v.GetAllRulers()),('probe',v.GetAllProbes()),('rst-probe',v.GetAllRSTProbes()),('protractor',v.GetAllProtractors())] for p in ids])


def query(v,r):
    op=r['operation']
    if op=='airfoil-coordinate-evaluate':
        import native_airfoil_coordinates
        return native_airfoil_coordinates.query(v,r)
    if op=='wing-coordinate-convert':
        import native_wing_coordinates
        return native_wing_coordinates.query(v,r)
    if op=='surface-batch-project':
        import native_surface_projection
        return native_surface_projection.query(v,r)
    if op=='volume-batch-evaluate':
        import native_volume_samples
        return native_volume_samples.query(v,r)
    if op=='surface-batch-evaluate':
        import native_surface_samples
        return native_surface_samples.query(v,r)
    if op=='measurement-preview':
        import native_measurements
        return native_measurements.preview(v)
    if op=='profile-evaluate':
        import native_profile_queries
        return native_profile_queries.query(v,r)
    if op in ['volume-project','volume-convert']:
        surface(v,r)
        import native_volume
        return native_volume.query(v,r)
    if op=='clearance':
        g=one(r['geom'],v.FindGeoms())
        return dict(distance=v.ComputeMinClearanceDistance(g,one(r['set'],range(v.GetNumSets()))))
    g,s=surface(v,r)
    if op=='surface-evaluate':
        u,w=coord(r['u']),coord(r['w'])
        return dict(point=xyz(v.CompPnt01(g,s,u,w)),normal=xyz(v.CompNorm01(g,s,u,w)),tangentU=xyz(v.CompTanU01(g,s,u,w)),tangentW=xyz(v.CompTanW01(g,s,u,w)),curvature=list(v.CompCurvature01(g,s,u,w)))
    if op=='surface-project':
        p=vector(v,r['point']);distance,u,w=v.ProjPnt01(g,s,p)
        return dict(distance=distance,u=u,w=w,point=xyz(v.CompPnt01(g,s,u,w)),inside=bool(v.InsideSurf(g,s,p)))
    if op=='volume-evaluate':return dict(point=xyz(v.CompPntRST(g,s,*[coord(r[k]) for k in ['r','s','t']])))
    raise ValueError('Unknown surface query.')


def mutate(v,r):
    op=r['operation']
    if op.startswith('fit-'):
        if op=='fit-import':
            import xml.etree.ElementTree as ET
            from pathlib import Path
            content=r['content']
            if not isinstance(content,str) or len(content.encode())>5_000_000 or '<!DOCTYPE' in content.upper():raise ValueError('Choose a native fit file smaller than 5 MB without document type declarations.')
            root=ET.fromstring(content)
            if root.tag!='Vsp_FitModel' or int(root.findtext('Version','0')) not in (1,2):raise ValueError('Expected a supported native Vsp_FitModel file.')
            targets=root.findall('TargetPt');variables=root.findall('Variable')
            if not 1<=len(targets)<=10000 or len(variables)>1000:raise ValueError('Use 1–10000 targets and at most 1000 geometry variables.')
            for node in targets:
                surface(v,dict(geom=node.findtext('MatchGeom'),surface=int(node.findtext('SurfIndx','0'))))
                vector(v,[float(x) for x in node.findtext('Pt','').split(',') if x.strip()])
                uw=[float(x) for x in node.findtext('UW','').split(',') if x.strip()]
                if len(uw)!=2:raise ValueError('Invalid native target surface coordinates.')
                for x in uw:coord(x)
                for key in ['UType','WType']:one(int(node.findtext(key,'-1')),[v.FIT_MODEL_FIXED,v.FIT_MODEL_FREE])
            for node in variables:
                if not v.ValidParm(node.findtext('ParmID','')):raise ValueError('A fit variable does not belong to this aircraft.')
            path=Path.cwd()/'uploaded.fit';path.write_text(content);v.ResetFitModel()
            code=v.LoadFitModelFile(str(path))
            if code:raise ValueError('The native engine could not load this fit file.')
        elif op=='fit-reset':
            v.ResetFitModel()
            for a in v.FindAttributesInCollection(v.GetChildCollection(v.GetVehicleID())):
                if v.GetAttributeName(a)==REPORT:v.DeleteAttribute(a)
        elif op in ('fit-targets-add','fit-targets-cloud'):
            g,s=surface(v,r)
            if op=='fit-targets-cloud':
                cloud=one(r['cloud'],[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper() in ('PTCLOUD','POINTCLOUD','POINT_CLOUD')],'Choose an existing native point cloud.')
                if not 1<=len(v.GetPtCloudPnts(cloud))<=10000-v.GetNumFitModelTargetPts():raise ValueError('The point cloud must contain 1–10000 points within the remaining fitting target capacity.')
                from native_cloud import world_points
                points=[xyz(p) for p in world_points(v,cloud)]
            else:points=r['points']
            if not isinstance(points,list) or not points or len(points)+v.GetNumFitModelTargetPts()>10000:raise ValueError('Add 1–10000 fitting points in total.')
            points=[vector(v,p) for p in points];ut=v.FIT_MODEL_FIXED if r.get('fixedU') else v.FIT_MODEL_FREE;wt=v.FIT_MODEL_FIXED if r.get('fixedW') else v.FIT_MODEL_FREE;u=coord(r.get('u',.5));w=coord(r.get('w',.5))
            coordinates=r.get('coordinates',[[u,w] for _ in points])
            if not isinstance(coordinates,list) or len(coordinates)!=len(points) or any(not isinstance(pair,list) or len(pair)!=2 for pair in coordinates):raise ValueError('Provide one U, W coordinate pair for each target point.')
            coordinates=[(coord(pair[0]),coord(pair[1])) for pair in coordinates]
            for p,(u,w) in zip(points,coordinates):
                index=v.AddFitModelTargetPt(g,s,p,ut,wt,u,w);v.SetFitModelTargetPtUW(index,u,w)
        elif op=='fit-target-update':
            i=one(r['index'],range(v.GetNumFitModelTargetPts()));g,s=surface(v,r)
            v.SetFitModelTargetPtGeom(i,g);v.SetFitModelTargetPtSurfIndx(i,s);v.SetFitModelTargetPt(i,vector(v,r['point']));v.SetFitModelTargetPtUType(i,v.FIT_MODEL_FIXED if r['fixedU'] else v.FIT_MODEL_FREE);v.SetFitModelTargetPtWType(i,v.FIT_MODEL_FIXED if r['fixedW'] else v.FIT_MODEL_FREE);v.SetFitModelTargetPtUW(i,coord(r['u']),coord(r['w']))
        elif op=='fit-target-delete':v.DelFitModelTargetPt(one(r['index'],range(v.GetNumFitModelTargetPts())))
        elif op=='fit-variable-delete':
            from native_fit_variables import resolve
            v.DelFitModelVar(one(resolve(v,r['parameter']),v.GetFitModelVarVec(),'Choose a saved fitting variable.'))
        elif op=='fit-targets-sort':v.SortFitModelTargetPtsByDist()
        elif op=='fit-targets-clear':v.DelAllFitModelTargetPts()
        elif op=='fit-target-move':v.MoveFitModelTargetPt(one(r['index'],range(v.GetNumFitModelTargetPts())),one(r['direction'],[v.REORDER_MOVE_UP,v.REORDER_MOVE_DOWN,v.REORDER_MOVE_TOP,v.REORDER_MOVE_BOTTOM]))
        elif op=='fit-variables':
            from native_tools import parameter_ids
            allowed=parameter_ids(v)|{p for g in v.FindGeoms() for p in v.GetGeomParmIDs(g)};ids=r['parameters']
            if not isinstance(ids,list) or len(ids)!=len(set(ids)) or len(ids)>1000:raise ValueError('Choose at most 1000 unique fit variables.')
            from native_fit_variables import resolve
            ids=[resolve(v,p) for p in ids]
            if len(ids)!=len(set(ids)):raise ValueError('Choose unique fit variables.')
            for p in ids:one(p,allowed)
            from native_fit_variables import validate
            validate(v,ids)
            v.DelAllFitModelVars()
            for p in ids:v.AddFitModelVar(p)
        elif op=='fit-search':v.SearchFitModelTargetUW()
        elif op=='fit-refine':v.RefineFitModelTargetUW()
        elif op=='fit-optimize':
            if not v.GetNumFitModelTargetPts() or not v.GetNumFitModelVars():raise ValueError('Add target points and at least one independent geometry variable.')
            from native_fit_variables import validate
            validate(v,v.GetFitModelVarVec())
            if 3*v.GetNumFitModelTargetPts()<v.GetNumFitModelOptVars():raise ValueError('The fit needs at least as many point-coordinate residuals as degrees of freedom. Add more points or fix U/W coordinates.')
            before=v.UpdateFitModelDist();code=v.OptimizeFitModel()
            if code==0:raise ValueError('The native optimizer rejected the fit. Choose independent variables that move the target surfaces.')
            coll=v.GetChildCollection(v.GetVehicleID())
            for a in v.FindAttributesInCollection(coll):
                if v.GetAttributeName(a)==REPORT:v.DeleteAttribute(a)
            v.AddAttributeString(coll,REPORT,json.dumps(dict(code=code,message=TERMINATION.get(code,'Native optimizer terminated.'),before=before,after=v.UpdateFitModelDist(),converged=code in [1,2,3,4])))
        else:return False,None
        save(v)
    elif op=='clearance-snap':
        g=one(r['geom'],v.FindGeoms());p=one(r['parameter'],v.GetGeomParmIDs(g));target=finite(r['distance'])
        if target<0 or not isinstance(r['increase'],bool):raise ValueError('Use a nonnegative clearance and choose the movement direction.')
        v.SnapParm(p,target,r['increase'],one(r['set'],range(v.GetNumSets())))
    elif op in ('measurement-rename','measurement-attachment'):
        import native_measurements
        native_measurements.edit(v,r)
    elif op=='measurement-refresh':pass
    elif op=='measurement-add':
        kind=one(r['kind'],['ruler','probe','rst-probe','protractor']);g,s=surface(v,r);title=name(r['name'])
        if kind=='probe':v.AddProbe(g,s,coord(r['u']),coord(r['w']),title)
        elif kind=='rst-probe':v.AddRSTProbe(g,s,*[coord(r[k]) for k in ['r','s','t']],title)
        elif kind=='protractor':
            mid,ms=surface(v,r,'mid');end,es=surface(v,r,'end');v.AddProtractor(g,s,coord(r['u']),coord(r['w']),mid,ms,coord(r['midu']),coord(r['midw']),end,es,coord(r['endu']),coord(r['endw']),title)
        else:
            end,es=surface(v,r,'end');v.AddRuler(g,s,coord(r['u']),coord(r['w']),end,es,coord(r['endu']),coord(r['endw']),title)
    elif op=='measurement-delete':
        kind=one(r['kind'],['ruler','probe','rst-probe','protractor']);getter,deleter={'ruler':(v.GetAllRulers,v.DelRuler),'probe':(v.GetAllProbes,v.DelProbe),'rst-probe':(v.GetAllRSTProbes,v.DelRSTProbe),'protractor':(v.GetAllProtractors,v.DelProtractor)}[kind];deleter(one(r['id'],getter()))
    else:return False,None
    if op.startswith('measurement-'):
        import native_measurements
        native_measurements.refresh(v)
    return True,None
