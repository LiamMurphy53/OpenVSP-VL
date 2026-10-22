"""Explicit native parameter unit labels; no numeric conversion."""
def unit(p):
    if p.get('nativeUnit'):return p['nativeUnit']
    dimension=p.get('dimension')
    if p['type']==0 and not dimension:
        group,name=p['rawGroup'],p['name']
        if group=='BBox':dimension='length'
        elif group=='Design' and name in ('Length','Diameter'):dimension='length'
        elif group=='WingGeom':dimension={'TotalSpan':'length','TotalProjectedSpan':'length','TotalChord':'length','MAC':'length','TotalArea':'area','CurvedArea':'area'}.get(name)
        elif group=='XForm':
            if name in [axis+suffix for axis in 'XYZ' for suffix in ('_Location','_Rel_Location')]:dimension='length'
            elif name in [axis+suffix for axis in 'XYZ' for suffix in ('_Rotation','_Rel_Rotation')]:dimension='angle'
    return {'length':'model length units','area':'model length units²','volume':'model length units³','angle':'degrees'}.get(dimension,'native input units')

