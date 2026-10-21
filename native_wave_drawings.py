"""Capture original native wave slicing-plane triangles and boundary loops."""
import native_managers
import ctypes,json,math
from pathlib import Path
import native_preview


def objects(v):
    _,engine,bridge=native_preview.adapter(v);fn=bridge.studio_wave_drawings;fn.argtypes=[ctypes.c_char_p];fn.restype=ctypes.c_char_p
    records=json.loads(fn(engine))
    if isinstance(records,dict):raise ValueError(records.get('error','Native wave drawings unavailable.'))
    return records


def capture(v,data):
    result=next(r for r in data['results'] if r['id']==data['resultID']);fields={e['name']:e['values'] for e in result['entries'] if e.get('index',0)==0};angles=fields['Theta'];mach=fields['Mach'][0]
    cid=native_managers.manager(v,'WaveDragSettings');ids={n:v.FindParm(cid,n,'WaveDrag') for n in ('MachNumber','ThetaIndex','SlicingLoc')};saved={n:v.GetParmVal(pid) for n,pid in ids.items()};planes=[]
    try:
        # Registered analysis Mach can differ from the saved manager default.
        # Set the original drawing manager to the native result's Mach before
        # asking it for coordinates; retain/restore all saved manager values.
        v.SetParmVal(ids['MachNumber'],mach)
        for i,angle in enumerate(angles):
            v.SetParmVal(ids['ThetaIndex'],i+1);raw=objects(v);parts=[];warnings=[]
            for j,obj in enumerate(raw):
                valid=obj['kind'] in ('triangles','loop') and all(len(p)==3 and all(isinstance(x,(int,float)) and math.isfinite(x) for x in p) for p in obj['points'])
                if valid and obj['points']:parts.append(dict(index=j,name='Original slicing plane' if obj['kind']=='triangles' else 'Original plane boundary',objects=[obj]))
                elif obj['points']:warnings.append('Original drawing contains unsupported or undefined coordinates; raw records are retained.')
            planes.append(dict(coneIndex=i+1,thetaDegrees=angle,position=saved['SlicingLoc'],nativeObjects=raw,parts=parts,warnings=warnings,filename=f'Wave slicing plane · cone {i+1}',showContext=True,displayNote='Original OpenVSP plane triangles and boundary points captured immediately after this saved run. The drawing manager uses the native result Mach and cone angle; plane X position uses this run’s saved SlicingLoc. No local Mach-angle or plane reconstruction is used. Aircraft context connects original native surface samples.'))
    finally:
        for n,pid in ids.items():v.SetParmVal(pid,saved[n])
    # Preserve native component samples with the run, independently of later edits.
    context=[]
    for g in v.FindGeoms():
        if v.GetGeomTypeName(g).upper() in ('MESH','NGONMESH'):continue
        surfaces=[]
        for i in range(v.GetTotalNumSurfs(g)):
            u,w=v.GetUWTess01(g,i%max(1,v.GetNumMainSurfs(g)))
            if len(u)<2 or len(w)<2:continue
            if len(u)*len(w)>120000:continue
            points=[[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(g,i,[x for x in u for _ in w],[y for _ in u for y in w])]
            if not all(math.isfinite(x) for p in points for x in p):continue
            surfaces.append(dict(index=i,rows=len(u),cols=len(w),points=points))
        if surfaces:context.append(dict(id=g,name=v.GetGeomName(g),surfaces=surfaces))
    return dict(enabled=bool(v.GetParmVal(v.FindParm(cid,'PlaneFlag','WaveDrag'))),selectedCone=int(saved['ThetaIndex']),version=data['version'],resultID=data['resultID'],nativeOperation='WaveDragSingleton::LoadDrawObjs',mach=mach,coordinateFrame='Original world XYZ in saved model units',planes=planes,context=context)


def save(v,data):
    drawing=capture(v,data);filename='wave-slicing-planes.drawing.json';Path(filename).write_text(json.dumps(drawing,allow_nan=False));data['waveDrawings']=dict(file=filename,enabled=drawing['enabled'],selectedCone=drawing['selectedCone'],cones=len(drawing['planes']),position=drawing['planes'][0]['position'] if drawing['planes'] else None,nativeOperation=drawing['nativeOperation']);return data
