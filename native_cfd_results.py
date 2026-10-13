"""Save the engine's own post-mesh intersections and classified problem geometry."""
import ctypes,json,math,subprocess
from pathlib import Path
from native_preview import adapter

LABELS={'RAWISECTCURVE':'Raw intersection curves','RAWBORDERCURVE':'Raw border curves',
        'ISECTCURVE':'Adapted intersection curves','BORDERCURVE':'Adapted border curves',
        'BADEDGE':'Native problem edges','BADTRI':'Native problem triangles','BADQUAD':'Native problem quads'}
WIDTHS={'lines':2,'triangles':3,'quads':4}


def save(v,meshed=True):
    try:return _save(v,meshed)
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        return dict(available=False,kind='cfd' if meshed else 'surface-intersections',reason='Native intersection drawing checks are unavailable: '+str(exc))


def _save(v,meshed):
    _,engine,library=adapter(v);function=library.studio_cfd_results
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_bool];function.restype=ctypes.c_char_p
    raw=Path.cwd()/'intersection-raw.curv';adapted=Path.cwd()/'intersection-adapted.curv'
    objects=json.loads(function(engine,str(raw).encode(),str(adapted).encode(),meshed))
    if isinstance(objects,dict):raise ValueError(objects.get('error','Native CFD diagnostic drawings unavailable.'))
    labels=LABELS if meshed else {k:v for k,v in LABELS.items() if 'CURVE' in k}
    parts=[];counts={key:0 for key in labels}
    for obj in objects:
        if obj['owner'] not in labels or obj['kind'] not in WIDTHS:raise ValueError('Unknown native CFD diagnostic drawing.')
        if len(obj['points'])%WIDTHS[obj['kind']] or any(len(p)!=3 or not all(math.isfinite(x) for x in p) for p in obj['points']):raise ValueError('OpenVSP returned invalid CFD diagnostic drawing points.')
        counts[obj['owner']]+=len(obj['points'])//WIDTHS[obj['kind']]
    for key,label in labels.items():
        parts.append(dict(id=key,index=len(parts),name=label,objects=[o for o in objects if o['owner']==key]))
    warnings=[]
    if not meshed:
        if not any(counts.values()):warnings.append('OpenVSP returned no intersection or border curves. Review the selected geometry sets and mode.')
    elif any(counts[k] for k in ['BADEDGE','BADTRI','BADQUAD']):warnings.append('OpenVSP classified problem edges or faces in this mesh. Inspect those native groups before using the mesh.')
    else:warnings.append('OpenVSP returned no classified problem edges or faces. This check does not establish overall mesh quality or solver suitability.')
    data=dict(version=v.GetVSPVersion(),filename='CFD intersections and native checks' if meshed else 'Native surface intersections',parts=parts,warnings=warnings,
              engineOperation=('GenerateMesh / CheckWaterTight' if meshed else 'SurfaceIntersection')+' / LoadDrawObjs / WriteGridToolCurvFile',
              counts=counts,displayNote=('All curve points and problem geometry come from this saved native mesh run. Raw curves show the engine’s original curve controls; adapted curves show its approximation. Empty problem groups mean no issues were classified by this native check; triangle quality and solver suitability still require review.' if meshed else 'These raw and adapted intersection/border curves are produced by the native SurfaceIntersection run. They are construction curves, not a mesh or a mesh-quality check.'))
    target=Path.cwd()/('cfd-native-drawings.json' if meshed else 'native-intersection-drawings.json');target.write_text(json.dumps(data,allow_nan=False))
    return dict(available=True,kind='cfd' if meshed else 'surface-intersections',drawingFile=target.name,rawCurvesFile=raw.name,adaptedCurvesFile=adapted.name,counts=counts,warnings=warnings,engineVersion=v.GetVSPVersion())
