"""Retain original GeometryAnalysisCase drawings immediately after evaluation."""
import ctypes,json,math
from pathlib import Path
import native_preview


def capture(v,cid):
    if cid not in v.GetAllGeometryAnalysesIDVec():raise ValueError('Choose an existing native geometry check.')
    _,engine,bridge=native_preview.adapter(v);fn=bridge.studio_geometry_case_drawings
    fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p];fn.restype=ctypes.c_char_p
    objects=json.loads(fn(engine,cid.encode()))
    if isinstance(objects,dict):raise ValueError(objects.get('error','Native case drawings unavailable.'))
    parts=[];warnings=[]
    for i,obj in enumerate(objects):
        suffix=obj['nativeID'][len(cid):]
        label={'Line':'Native result lines','Point':'Native result points','VizPoint':'Native visibility observation point'}.get(suffix,'Native result mesh '+suffix.lstrip('_'))
        valid=obj['kind'] in ('lines','points','triangles') and all(len(p)==3 and all(isinstance(x,(int,float)) and math.isfinite(x) for x in p) for p in obj['points'])
        if not valid and obj['points']:warnings.append(label+': contains an unsupported drawing type or undefined coordinate. Original records remain in the native-point download.')
        if valid and obj['points']:parts.append(dict(index=i,name=label,objects=[obj]))
    return dict(case=dict(id=cid,name=v.GetContainerName(cid),type=int(v.GetParmVal(v.FindParm(cid,'IntererenceCheckType','InterferenceCase')))),
                coordinateFrame='Native world XYZ',nativeObjects=objects,parts=parts,warnings=warnings,
                filename=v.GetContainerName(cid)+' · native case drawings',showContext=False,
                displayNote='Original OpenVSP result mesh vertices, result lines, result points and available observation points captured from this run. Coordinates use this run’s model length units. These drawings retain the evaluated case; they are not recomputed from the current aircraft.')


def save(v,data):
    selected=next((e['values'][0] for e in data['inputs'] if e['name']=='CaseID'),'ALL')
    cases=[c for c in data['geometryCases'] if selected in ('ALL','all') or c['id']==selected]
    records=[]
    for index,case in enumerate(cases):
        drawing=capture(v,case['id']);filename='geometry-case-'+str(index+1)+'.drawing.json'
        drawing.update(version=data['version'],resultID=data['resultID'])
        Path(filename).write_text(json.dumps(drawing,allow_nan=False))
        records.append(dict(id=case['id'],name=case['name'],file=filename,
                            objects=len(drawing['nativeObjects']),points=sum(len(o['points']) for o in drawing['nativeObjects']),
                            displayable=bool(drawing['parts']),warnings=drawing['warnings']))
    data['geometryCaseDrawings']=records
    return data
