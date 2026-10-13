"""Original wing section-coordinate and span-fraction conversion queries."""
import math
from native_tools import one,finite


def query(v,r):
    g=one(r.get('geom'),[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='WING'],'Choose an existing wing.');basis=one(r.get('basis'),['ETA','U']);values=r.get('values')
    if not isinstance(values,list) or not 1<=len(values)<=10000:raise ValueError('Enter 1–10000 wing coordinates.')
    interval=[v.ConvertEtatoU(g,0.),v.ConvertEtatoU(g,1.)]
    if any(not math.isfinite(x) for x in interval):raise ValueError('The native wing span-coordinate interval is undefined for this geometry.')
    lower,upper=(0.,1.) if basis=='ETA' else (min(interval),max(interval));inputs=[finite(x) for x in values]
    if any(not lower<=x<=upper for x in inputs):raise ValueError(f'Use {basis} coordinates within the native wing interval {lower}–{upper}.')
    rows=[dict(eta=x,nativeU=v.ConvertEtatoU(g,x)) if basis=='ETA' else dict(eta=v.ConvertUtoEta(g,x),nativeU=x) for x in inputs]
    return dict(nativeOperation='ConvertEtatoU' if basis=='ETA' else 'ConvertUtoEta',component=g,basis=basis,nativeWingUInterval=interval,wingCoordinates=rows,coordinateConvention='Eta is the native wing span fraction. Native wing U is a section coordinate including the original cap offset; it is not normalized surface U.')
