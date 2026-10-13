"""Original OpenVSP ideal-body curves, using each saved cone's native values."""
import ctypes,json
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
    result=next(r for r in data['results'] if r['id']==data['resultID'])
    fields={e['name']:e['values'] for e in result['entries'] if e.get('index',0)==0}
    cones=[]
    for i,theta in enumerate(fields['Theta']):
        volume,length,area=(fields[n][i] for n in ('Volume','Length','MaxArea'))
        cones.append(dict(coneIndex=i+1,thetaDegrees=theta,volume=volume,length=length,maxArea=area,**curves(v,volume,length,area)))
    output=dict(cones=cones,coordinateConvention='Normalized axial position; cross-sectional area in saved model units squared. Bare ideal-body curves without inlet/exit area offsets.',nativeOperation='WaveDragSingleton::SearsHaack / vonKarman / Lighthill',version=data['version'])
    filename='wave-reference-curves.json'
    Path(filename).write_text(json.dumps(output,allow_nan=False))
    data['waveReferenceCurves']=dict(file=filename,**output)
    return data
