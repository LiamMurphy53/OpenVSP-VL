"""Historical fit receipts from original parameter and target APIs only."""
from native_parameter_units import unit


def xyz(p):return [p.x(),p.y(),p.z()]


def capture(v):
    from native_worker import parameter
    from native_fit_variables import key
    variables=[]
    for pid in v.GetFitModelVarVec():
        p=parameter(v,pid)
        variables.append(dict(id=key(v,pid),label=' / '.join([v.GetContainerName(v.GetParmContainer(pid)),p['rawGroup'],p.get('label',p['name'])]),value=v.GetParmVal(pid),min=p['min'],max=p['max'],unit=unit(p)))
    targets=[dict(index=i,geom=v.GetFitModelTargetPtGeom(i),surface=v.GetFitModelTargetPtSurfIndx(i),point=xyz(v.GetFitModelTargetPt(i)),surfacePoint=xyz(v.GetFitModelTargetPtSurfPt(i)),distance=v.GetFitModelTargetPtDist(i),u=v.GetFitModelTargetPtU(i),w=v.GetFitModelTargetPtW(i)) for i in range(v.GetNumFitModelTargetPts())]
    return dict(variables=variables,targets=targets)


def finish(v,before):
    after=capture(v)
    return dict(schemaVersion=1,engineVersion=v.GetVSPVersion(),variables=[dict(**{k:x for k,x in a.items() if k!='value'},before=a['value'],after=b['value']) for a,b in zip(before['variables'],after['variables'])],targets=[dict(index=a['index'],geom=a['geom'],surface=a['surface'],point=a['point'],beforeSurfacePoint=a['surfacePoint'],afterSurfacePoint=b['surfacePoint'],before=a['distance'],after=b['distance'],beforeUW=[a['u'],a['w']],afterUW=[b['u'],b['w']]) for a,b in zip(before['targets'],after['targets'])])
