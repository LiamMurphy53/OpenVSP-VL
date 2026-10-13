"""Read the original engine's ordered, untwisted foil-surface coordinates."""
import math
from native_tools import one,finite


def query(v,r):
    g=one(r.get('geom'),[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper() in ('WING','PROP','PROPELLER')],'Choose an existing wing or propeller.')
    u=finite(r.get('u'))
    if not 0<=u<=1:raise ValueError('Airfoil surface U must be between 0 and 1.')
    coordinates=[[x if math.isfinite(x) else None for x in (p.x(),p.y(),p.z())] for p in v.GetAirfoilCoordinates(g,u)]
    if not coordinates:raise ValueError('OpenVSP returned no airfoil coordinates for this component and station.')
    result=dict(nativeOperation='GetAirfoilCoordinates',component=g,u=u,airfoilCoordinates=coordinates,coordinateConvention='Original untwisted, unit-chord foil-surface XYZ in native Selig order; X/Y are the 2D export coordinates. Airfoil surface U runs from 0 to 1, excluding end caps. Sampling follows the saved native tessellation.')
    if any(x is None for row in coordinates for x in row):result['nativeWarning']='Undefined native coordinates are retained as null.'
    return result
