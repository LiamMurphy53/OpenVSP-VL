"""Expose original BOR file-profile coordinates and point setters."""
from native_tools import finite,one


def coordinates(points):
    return [[p.x(),p.y(),p.z()] for p in points]


def snapshot(v,g):
    shape=v.GetBORXSecShape(g)
    if shape==v.XS_FILE_FUSE:return dict(kind='section',points=coordinates(v.GetBORXSecPnts(g)))
    if shape==v.XS_FILE_AIRFOIL:return dict(kind='airfoil',upper=coordinates(v.GetBORAirfoilUpperPnts(g)),lower=coordinates(v.GetBORAirfoilLowerPnts(g)))
    return None


def vector(v,raw,minimum):
    if not isinstance(raw,list) or not minimum<=len(raw)<=10000:raise ValueError(f'Enter {minimum}–10000 coordinate rows.')
    rows=[]
    for row in raw:
        if not isinstance(row,list) or len(row)!=3:raise ValueError('Use three finite coordinates per row: X Y Z.')
        rows.append([finite(x) for x in row])
    if len(set(tuple(row) for row in rows))<minimum:raise ValueError(f'Use at least {minimum} distinct coordinate points.')
    return [v.vec3d(*row) for row in rows]


def mutate(v,r):
    g=one(r['geom'],[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='BODYOFREVOLUTION']);shape=v.GetBORXSecShape(g)
    if r['operation']=='bor-file-section-points':
        if shape!=v.XS_FILE_FUSE:raise ValueError('Choose a file cross-section profile first.')
        points=section_vector(v,r['points'])
        v.SetBORXSecPnts(g,points)
    elif r['operation']=='bor-file-airfoil-points':
        if shape!=v.XS_FILE_AIRFOIL:raise ValueError('Choose a file airfoil profile first.')
        side=one(r['side'],['upper','lower','both'])
        if side=='both':
            upper=vector(v,r['upper'],2);lower=vector(v,r['lower'],2);v.SetBORAirfoilPnts(g,upper,lower)
        else:getattr(v,'SetBORAirfoil'+side.title()+'Pnts')(g,vector(v,r['points'],2))
    else:raise ValueError('Choose a supported file-profile coordinate operation.')
    return True,g


def section_vector(v,raw):
    points=vector(v,raw,4)
    # FileXSec::UpdateCurve uses bottom-index * 2 for the left quarter.
    # Validate that original indexing before handing user rows to it.
    rows=raw;n=len(rows)-int(rows[0]==rows[-1]);bottom=top=0
    for i in range(n):
        if rows[i][1]<0 and abs(rows[i][0])<abs(rows[bottom][0]):bottom=i
        if rows[i][1]>0 and abs(rows[i][0])<abs(rows[top][0]):top=i
    if not 0<bottom<2*bottom<top<n:raise ValueError('Use native cross-section point order: right side, bottom, left side, top, then close the outline. Keep the original quarter-point layout.')
    return points
