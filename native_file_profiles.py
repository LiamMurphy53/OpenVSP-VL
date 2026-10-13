"""Original stored file cross-section and airfoil point editing."""
from native_bor_points import coordinates,vector,section_vector
from native_tools import section,one


def snapshot(v,x):
    shape=v.GetXSecShape(x)
    if shape==v.XS_FILE_FUSE:return dict(kind='section',points=coordinates(v.GetXSecPnts(x)))
    if shape==v.XS_FILE_AIRFOIL:return dict(kind='airfoil',upper=coordinates(v.GetAirfoilUpperPnts(x)),lower=coordinates(v.GetAirfoilLowerPnts(x)))
    return None


def mutate(v,r):
    g,_,_,x=section(v,r);shape=v.GetXSecShape(x)
    if r['operation']=='section-file-section-points':
        if shape!=v.XS_FILE_FUSE:raise ValueError('Choose a file cross-section profile first.')
        v.SetXSecPnts(x,section_vector(v,r['points']))
    elif r['operation']=='section-file-airfoil-points':
        if shape!=v.XS_FILE_AIRFOIL:raise ValueError('Choose a file airfoil profile first.')
        side=one(r['side'],['upper','lower','both'])
        if side=='both':
            upper=vector(v,r['upper'],2);lower=vector(v,r['lower'],2);v.SetAirfoilPnts(x,upper,lower)
        else:getattr(v,'SetAirfoil'+side.title()+'Pnts')(x,vector(v,r['points'],2))
    else:raise ValueError('Choose a supported file-profile coordinate operation.')
    return True,g
