"""Original OpenVSP ideal-body curves, using each saved cone's native values."""
import native_managers
import ctypes,json,math
from pathlib import Path
import native_preview


def curves(v,volume,length,area):
    _,engine,bridge=native_preview.adapter(v)
    fn=bridge.studio_wave_reference_curves
    fn.argtypes=[ctypes.c_char_p,ctypes.c_double,ctypes.c_double,ctypes.c_double]
    fn.restype=ctypes.c_char_p
    result=json.loads(fn(engine,volume,length,area))
    if 'error' in result:raise ValueError(result['error'])
    return result


def save(v,data):
    engine_path=native_preview.distribution()/'python/openvsp/openvsp/_vsp.so';stat=engine_path.stat()
    native_preview._verified_private_layout(str(engine_path),stat.st_size,stat.st_mtime_ns)
    _,engine,bridge=native_preview.adapter(v)
    fn=bridge.studio_wave_plot_data
    fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_char_p];fn.restype=ctypes.c_char_p
    cid=native_managers.manager(v,'WaveDragSettings')
    saved=json.loads(fn(engine,v.FindParm(cid,'MachNumber','WaveDrag').encode(),v.FindParm(cid,'NumSlices','WaveDrag').encode()))
    if 'error' in saved:raise ValueError(saved['error'])
    result=next(r for r in data['results'] if r['id']==data['resultID'])
    fields={e['name']:e['values'] for e in result['entries'] if e.get('index',0)==0}
    cones=[]
    for i,theta in enumerate(fields['Theta']):
        volume,length,area=(fields[n][i] for n in ('Volume','Length','MaxArea'))
        reference=curves(v,volume,length,area) if all(isinstance(x,(int,float)) and math.isfinite(x) for x in (volume,length,area)) and length>0 else dict(referenceWarning='Native equivalent-body dimensions are undefined or have zero length.')
        if 'xNormalized' in reference and reference['xNormalized']!=saved['xFitNormalized']:
            raise ValueError('Native ideal-body sampling differs from the saved fitted distribution.')
        cones.append(dict(**saved['cones'][i],thetaDegrees=theta,volume=volume,length=length,maxArea=area,
                          startX=fields['Start_X'][i],endX=fields['End_X'][i],**reference))
    output=dict(saved,cones=cones,components=[dict(id=g,name=v.GetGeomName(g) if g in v.FindGeoms() else g) for g in saved['componentIds']],
                coordinateConvention='Normalized axial position; areas in square saved model units. Ideal-body arrays are bare curves; component/buildup displays add the saved inlet/exit baseline for plotting.',
                nativeOperation='WaveDragSingleton area-distribution arrays / SearsHaack / vonKarman / Lighthill',version=data['version'])
    filename='wave-reference-curves.json'
    Path(filename).write_text(json.dumps(output,allow_nan=False))
    data['waveReferenceCurves']=dict(file=filename,**output)
    return data
