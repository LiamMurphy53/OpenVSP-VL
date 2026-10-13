"""Original OpenVSP vectorized surface and collapsed-point queries."""
import math
from native_tools import one
from native_fit import surface,coord


def query(v,r):
    g,s=surface(v,r);rows=r.get('samples')
    if not isinstance(rows,list) or not 1<=len(rows)<=10000:raise ValueError('Enter 1–10000 U/W sample rows.')
    for row in rows:
        if not isinstance(row,list) or len(row)!=2:raise ValueError('Each sample row needs U and W.')
    uv=[[coord(x) for x in row] for row in rows];us,ws=map(list,zip(*uv));points=list(v.CompVecPnt01(g,s,us,ws));normals=list(v.CompVecNorm01(g,s,us,ws));curvatures=[list(values) for values in v.CompVecCurvature01(g,s,us,ws)]
    degen=r.get('degenType');alternate=[]
    if degen is not None:
        if type(degen)!=int:raise ValueError('Choose a native collapsed representation.')
        one(degen,range(4));alternate=list(v.CompVecDegenPnt01(g,s,degen,us,ws))
    if any(len(values)!=len(uv) for values in [points,normals,*curvatures]+([alternate] if degen is not None else [])):raise ValueError('OpenVSP returned inconsistent native sample-array lengths.')
    def xyz(p):return [p.x(),p.y(),p.z()]
    samples=[dict(u=row[0],w=row[1],point=xyz(points[i]),normal=xyz(normals[i]),curvature=[values[i] for values in curvatures],**(dict(collapsedPoint=xyz(alternate[i])) if degen is not None else {})) for i,row in enumerate(uv)]
    result=dict(nativeOperation='CompVecPnt01 / CompVecNorm01 / CompVecCurvature01'+(' / CompVecDegenPnt01' if degen is not None else ''),component=g,surface=s,degenType=degen,samples=samples,coordinateConvention='Original native surface XYZ and model length units; normals and curvature belong to the original surface.')
    if any(not math.isfinite(x) for sample in samples for key in ('point','normal','curvature','collapsedPoint') for x in sample.get(key,[])):result['nativeWarning']='OpenVSP returned undefined sample values. Undefined entries remain null in the saved result.'
    return result
