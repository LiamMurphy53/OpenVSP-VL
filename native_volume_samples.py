"""Original vectorized volume points, searches and coordinate conversions."""
import math
from native_tools import one,finite
from native_fit import surface,coord


def query(v,r):
    g,s=surface(v,r);mode=one(r.get('mode'),['RST','LMN','XYZ','XYZ_GUESS']);rows=r.get('samples');width=6 if mode=='XYZ_GUESS' else 3
    if not isinstance(rows,list) or not 1<=len(rows)<=10000:raise ValueError('Enter 1–10000 volume sample rows.')
    if any(not isinstance(row,list) or len(row)!=width for row in rows):raise ValueError(f'Each row needs {width} coordinates for this operation.')
    inputs=[[coord(x) if mode in ('RST','LMN') or j>=3 else finite(x) for j,x in enumerate(row)] for row in rows];n=len(inputs);distance=None;ops=[]
    if mode=='RST':rst=[row[:] for row in inputs]
    elif mode=='LMN':
        vectors=v.ConvertLMNtoRSTVec(g,s,*map(list,zip(*inputs)));rst=[list(row) for row in zip(*vectors)];ops.append('ConvertLMNtoRSTVec')
    else:
        points=[v.vec3d(*row[:3]) for row in inputs]
        if mode=='XYZ_GUESS':vectors=v.FindRSTVecGuess(g,s,points,*map(list,zip(*(row[3:] for row in inputs))));ops.append('FindRSTVecGuess')
        else:vectors=v.FindRSTVec(g,s,points);ops.append('FindRSTVec')
        rs,ss,ts,distance=map(list,vectors);rst=[list(row) for row in zip(rs,ss,ts)]
    if len(rst)!=n or any(len(row)!=3 for row in rst) or (distance is not None and len(distance)!=n):raise ValueError('OpenVSP returned inconsistent volume coordinate-array lengths.')
    valid=[i for i,row in enumerate(rst) if all(math.isfinite(x) for x in row)];points=[[None]*3 for _ in inputs];lmn=[row[:] for row in inputs] if mode=='LMN' else [[None]*3 for _ in inputs]
    if valid:
        columns=list(map(list,zip(*(rst[i] for i in valid))))
        evaluated=list(v.CompVecPntRST(g,s,*columns));ops.append('CompVecPntRST')
        if len(evaluated)!=len(valid):raise ValueError('OpenVSP returned inconsistent volume point-array lengths.')
        for i,p in zip(valid,evaluated):points[i]=[p.x(),p.y(),p.z()]
        if mode!='LMN':
            converted=[list(row) for row in zip(*v.ConvertRSTtoLMNVec(g,s,*columns))];ops.append('ConvertRSTtoLMNVec')
            if len(converted)!=len(valid):raise ValueError('OpenVSP returned inconsistent uniform-coordinate-array lengths.')
            for i,row in zip(valid,converted):lmn[i]=row
    samples=[dict(input=inputs[i],RST=rst[i],LMN=lmn[i],point=points[i],**(dict(distance=distance[i]) if distance is not None else {})) for i in range(n)]
    result=dict(nativeOperation=' / '.join(ops),mode=mode,samples=samples,component=g,surface=s,coordinateConvention='Original model XYZ/length units; R/S/T and L/M/N retain native normalized volume conventions.')
    if any(x is None or not math.isfinite(x) for sample in samples for key in ('RST','LMN','point') for x in sample[key]):result['nativeWarning']='Some native coordinates are undefined. Undefined conversion rows retain null points and are not passed into another native point evaluation.'
    return result
