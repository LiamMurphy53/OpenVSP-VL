"""Original OpenVSP volume search and coordinate conversion queries.

No coordinate conversion, distance or inverse geometry is implemented here.
"""
import math
from native_tools import finite,one

def vector(values,label,normalized=False):
    if not isinstance(values,list) or len(values)!=3:raise ValueError(label+': enter three coordinates.')
    result=[finite(x) for x in values]
    if normalized and any(x<0 or x>1 for x in result):raise ValueError(label+': coordinates must be between 0 and 1.')
    return result

def output(values,allow_undefined=False):
    values=list(values)
    if any(not math.isfinite(x) for x in values):
        if not allow_undefined:raise ValueError('OpenVSP returned undefined volume coordinates. Choose another point or surface.')
        return [x if math.isfinite(x) else None for x in values]
    return values

def point(v,g,s,rst):
    if any(x is None for x in rst):return None
    p=v.CompPntRST(g,s,*rst)
    return output([p.x(),p.y(),p.z()])

def query(v,request):
    g=one(request.get('geom'),v.FindGeoms(),'Choose an existing component.')
    s=request.get('surface',0)
    if isinstance(s,bool) or not isinstance(s,int) or s not in range(v.GetTotalNumSurfs(g)):raise ValueError('Choose an existing native surface.')
    op=request.get('operation')
    if op=='volume-project':
        xyz=vector(request.get('point'),'Model point');p=v.vec3d(*xyz)
        guess=request.get('guess')
        if guess is None:
            values=output(v.FindRST(g,s,p));operation='FindRST'
        else:
            seed=vector(guess,'R/S/T search guess',True)
            values=output(v.FindRSTGuess(g,s,p,*seed));operation='FindRSTGuess'
        distance,*rst=values
        if len(rst)!=3:raise ValueError('The native volume search returned an incomplete result.')
        lmn=output(v.ConvertRSTtoLMN(g,s,*rst),allow_undefined=True)
        result=dict(nativeOperation=operation,inputPoint=xyz,distance=distance,RST=rst,LMN=lmn,point=point(v,g,s,rst),inside=bool(v.InsideSurf(g,s,p)))
        if guess is not None:result['searchGuess']=seed
    elif op=='volume-convert':
        basis=one(request.get('basis'),['RST','LMN'],'Choose R/S/T or L/M/N input coordinates.')
        coordinates=vector(request.get('coordinates'),basis+' input',True)
        if basis=='RST':rst=coordinates;lmn=output(v.ConvertRSTtoLMN(g,s,*rst),allow_undefined=True);operation='ConvertRSTtoLMN'
        else:lmn=coordinates;rst=output(v.ConvertLMNtoRST(g,s,*lmn),allow_undefined=True);operation='ConvertLMNtoRST'
        result=dict(nativeOperation=operation,inputCoordinates=coordinates,inputBasis=basis,RST=rst,LMN=lmn,point=point(v,g,s,rst))
    else:raise ValueError('Choose a supported native volume query.')
    if any(x is None for key in ['RST','LMN'] for x in result[key]):
        result['nativeWarning']='OpenVSP returned undefined conversion coordinates at this location. Undefined native values are preserved as null.'
    return dict(engineVersion=v.GetVSPVersion(),component=g,surface=s,**result)
