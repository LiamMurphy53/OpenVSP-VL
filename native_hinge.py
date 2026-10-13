"""Original native hinge drawing objects in world coordinates."""
import ctypes,json
import native_preview


def preview(v,gid):
    if gid not in v.FindGeoms() or v.GetGeomTypeName(gid).upper()!='HINGE':raise ValueError('Choose an existing hinge.')
    _,engine,bridge=native_preview.adapter(v);function=bridge.studio_hinge_drawings
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p];function.restype=ctypes.c_char_p
    objects=json.loads(function(engine,gid.encode()))
    if isinstance(objects,dict):raise ValueError(objects.get('error','Native hinge drawings unavailable.'))
    def label(record):
        suffix=record['nativeID'][len(gid):]
        if suffix.startswith('Axis_'):return 'Attachment '+['X','Y','Z'][int(suffix[-1])]+' axis'
        if suffix.startswith('_Feature_'):
            i=int(suffix.split('_')[-1]);return ('Base ' if i<3 else 'Joint ')+['X','Y','Z'][i%3]+' axis'
        return {'MArrows':'Motion arrowheads','MLines':'Motion guides','PrimLines':'Orientation target','1':'Base point'}.get(suffix,suffix)
    return dict(component=dict(id=gid,name=v.GetGeomName(gid)),coordinateFrame='Native world XYZ',
                parts=[dict(index=i,name=label(record),objects=[record]) for i,record in enumerate(objects)],
                warnings=[],showContext=True,filename='Native hinge motion guides',
                displayNote='Original OpenVSP hinge drawing points in world XYZ and model length units. Inspector visibility is independent of main-window feature visibility.')
