"""Original native vector point projections and inside classification."""
import math
from native_tools import finite,one
from native_fit import surface,coord


def query(v,r):
    all_surfaces=r.get('allSurfaces',False)
    if type(all_surfaces)!=bool:raise ValueError('Choose a single surface or all native component surfaces.')
    if all_surfaces:
        g=one(r.get('geom'),v.FindGeoms());s=None
        if not v.GetTotalNumSurfs(g):raise ValueError('Choose a component with native surfaces.')
    else:g,s=surface(v,r)
    mode=one(r.get('mode'),['NEAREST','NEAREST_GUESS','AXIS','AXIS_GUESS']);guess=mode.endswith('GUESS');axis_mode=mode.startswith('AXIS');width=5 if guess else 3;rows=r.get('samples')
    if not isinstance(rows,list) or not 1<=len(rows)<=10000 or any(not isinstance(row,list) or len(row)!=width for row in rows):raise ValueError(f'Enter 1–10000 rows with {width} coordinates each.')
    inputs=[[finite(x) if j<3 else coord(x) for j,x in enumerate(row)] for row in rows];pts=[v.vec3d(*row[:3]) for row in inputs];guesses=list(map(list,zip(*(row[3:] for row in inputs)))) if guess else []
    axis=getattr(v,one(r.get('axis'),['X_DIR','Y_DIR','Z_DIR'])) if axis_mode else None
    if all_surfaces:
        if guess:raise ValueError('Component-wide projection uses unseeded native operations. Choose a particular surface to supply U/W guesses.')
        method='AxisProjPnt01I' if axis_mode else 'ProjPnt01I';samples=[]
        for row,point in zip(inputs,pts):
            distance,index,u,w=v.AxisProjPnt01I(g,axis,point) if axis_mode else v.ProjPnt01I(g,point)
            found=0<=index<v.GetTotalNumSurfs(g) and all(math.isfinite(x) and x>=0 for x in (distance,u,w));miss=axis_mode and distance==-1
            projected=row[:3] if miss else [None]*3;inside=None
            if found:
                p=v.CompPnt01(g,index,u,w);projected=[p.x(),p.y(),p.z()];inside=bool(v.InsideSurf(g,index,point))
            samples.append(dict(input=row,surface=index,u=u,w=w,distance=distance,point=projected,inside=inside,found=found,status='found' if found else 'miss' if miss else 'undefined'))
        return dict(nativeOperation=method+' / CompPnt01 / InsideSurf',mode=mode,allSurfaces=True,axis=r.get('axis') if axis_mode else None,component=g,surface=None,samples=samples,coordinateConvention='Original component-wide model XYZ/length units. OpenVSP selects the native surface, including physical copies; inside classification refers to that selected surface. Misses retain native values and input XYZ.')
    if axis_mode:
        method='AxisProjVecPnt01Guess' if guess else 'AxisProjVecPnt01';values=getattr(v,method)(g,s,axis,pts,*guesses)
    else:
        method='ProjVecPnt01Guess' if guess else 'ProjVecPnt01';values=getattr(v,method)(g,s,pts,*guesses)
    us,ws,distances=map(list,values);inside=list(v.VecInsideSurf(g,s,pts));n=len(inputs)
    if any(len(values)!=n for values in (us,ws,distances,inside)):raise ValueError('OpenVSP returned inconsistent projection-array lengths.')
    valid=[i for i in range(n) if all(math.isfinite(x) for x in (us[i],ws[i],distances[i])) and us[i]>=0 and ws[i]>=0 and distances[i]>=0]
    misses={i for i in range(n) if axis_mode and distances[i]==-1}
    projected=[row[:3] if i in misses else [None]*3 for i,row in enumerate(inputs)]
    if valid:
        found=list(v.CompVecPnt01(g,s,[us[i] for i in valid],[ws[i] for i in valid]))
        if len(found)!=len(valid):raise ValueError('OpenVSP returned inconsistent projected-point lengths.')
        for i,p in zip(valid,found):projected[i]=[p.x(),p.y(),p.z()]
    found_indices=set(valid);samples=[dict(input=inputs[i],surface=s,u=us[i],w=ws[i],distance=distances[i],point=projected[i],inside=bool(inside[i]),found=i in found_indices,status='found' if i in found_indices else 'miss' if i in misses else 'undefined') for i in range(n)]
    return dict(nativeOperation=method+' / VecInsideSurf / CompVecPnt01',mode=mode,axis=r.get('axis') if axis_mode else None,component=g,surface=s,samples=samples,coordinateConvention='Original model XYZ and length units. Axis misses retain the input point and native negative coordinates and -1 distance; inside classification of the input points comes from OpenVSP.')
