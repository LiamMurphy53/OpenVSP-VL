"""Guided native surface-intersection inputs; no geometry or CAD calculations."""
from pathlib import Path

EXPORTS={'SRF':'Surface data','CURV':'Intersection curves','P3D':'Plot3D surfaces','IGES':'IGES CAD','STEP':'STEP CAD'}
RESERVED={'aircraft.vsp3','request.json','response.json','response.json.tmp','engine.log','job.json','job.json.tmp','native-intersection-drawings.json','intersection-raw.curv','intersection-adapted.curv'}

PERSISTENT_FIELDS=['DemoteSurfsCubicFlag','CubicSurfTolerance','HalfMesh','STEPMergePoints']


def mutate_settings(v,request):
    from native_tools import finite,one
    cid=v.FindContainer('SurfaceIntersectSettings',0)
    params={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)}
    values=request.get('values')
    if not isinstance(values,dict) or not values:raise ValueError('Choose intersection settings to save.')
    # Validate the complete request before changing any native parameter.
    for name,value in values.items():
        one(name,PERSISTENT_FIELDS,'Unsupported persistent intersection setting.')
        finite(value);p=params[name]
        if not v.GetParmLowerLimit(p)<=value<=v.GetParmUpperLimit(p):raise ValueError(name+': value is outside the native limits.')
        if v.GetParmType(p) in (v.PARM_INT_TYPE,v.PARM_BOOL_TYPE) and value!=int(value):raise ValueError(name+': choose a whole number.')
    for name,value in values.items():v.SetParmVal(params[name],value)
    v.Update()


def filename(value):
    # Imported native defaults may contain an old absolute output directory.
    # Every export stays in this saved run; only its basename is reused.
    if not isinstance(value,str) or '\\' in value or any(ord(c)<32 for c in value):raise ValueError('Choose a filename for the native intersection export.')
    result=Path(value).name
    if not result or result in ('.','..') or result.startswith('.') or result.lower() in RESERVED:
        raise ValueError('Choose an export filename that does not replace a saved run file.')
    return result


def annotate(v,inputs):
    labels={'UseMode':'Geometry selection','ModeID':'Native mode','SelectedSetIndex':'Normal geometry set','SelectedDegenSetIndex':'Thin geometry set','IntersectSubSurfs':'Include surface regions','RelCurveTol':'Relative curve tolerance','ExportRawFlag':'Curve export samples','CADLenUnit':'CAD length unit','CADLabelDelim':'CAD label separator','CADLabelID':'Include component ID','CADLabelName':'Include component name','CADLabelSurfNo':'Include surface number','CADLabelSplitNo':'Include split number','STEPRepresentation':'STEP representation','STEPTol':'STEP tolerance'}
    onoff=[dict(value=0,label='Off'),dict(value=1,label='On')]
    def choices(pairs):return [dict(value=getattr(v,key),label=label) for key,label in pairs]
    maps={key:list(onoff) for key in ['IntersectSubSurfs','CADLabelID','CADLabelName','CADLabelSurfNo','CADLabelSplitNo',*[key+'FileFlag' for key in EXPORTS]]}
    maps.update(UseMode=[dict(value=0,label='Geometry sets'),dict(value=1,label='Native mode')],
                ExportRawFlag=[dict(value=0,label='Adapted curves'),dict(value=1,label='Raw intersection points')],
                STEPRepresentation=choices([('STEP_SHELL','Shell'),('STEP_BREP','BREP solid')]),
                CADLenUnit=choices([('LEN_MM','mm'),('LEN_CM','cm'),('LEN_M','m'),('LEN_IN','in'),('LEN_FT','ft'),('LEN_YD','yd')]),
                CADLabelDelim=choices([('DELIM_COMMA','Comma'),('DELIM_USCORE','Underscore'),('DELIM_SPACE','Space'),('DELIM_NONE','No separator')]),
                ModeID=[dict(value='',label='Choose a mode…'),*[dict(value=m,label=v.GetModeName(m)) for m in v.GetAllModes()]])
    cid=v.FindContainer('SurfaceIntersectSettings',0)
    parms={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)}
    for e in inputs:
        key=e['name'];e['label']=labels.get(key,key)
        if key in maps:e['choices']=maps[key]
        if key=='ModeID' and e['values'][0] and e['values'][0] not in v.GetAllModes():
            e['choices'].append(dict(value=e['values'][0],label='Unavailable native mode · '+e['values'][0]))
        if key in parms:e['min'],e['max']=v.GetParmLowerLimit(parms[key]),v.GetParmUpperLimit(parms[key])
        if key=='ModeID':e['applicableWhen']=dict(input='UseMode',values=[1])
        if key in ['SelectedSetIndex','SelectedDegenSetIndex']:e['applicableWhen']=dict(input='UseMode',values=[0])
        if key in ['STEPRepresentation','STEPTol']:e['applicableWhen']=dict(input='STEPFileFlag',values=[1])
        if key in ['CADLenUnit','CADLabelDelim','CADLabelID','CADLabelName','CADLabelSurfNo','CADLabelSplitNo']:
            e['applicableWhen']=dict(any=[dict(input='IGESFileFlag',values=[1]),dict(input='STEPFileFlag',values=[1])])
        for prefix,label in EXPORTS.items():
            if key==prefix+'FileFlag':e['label']='Export '+label
            if key==prefix+'FileName':
                e['label']=label+' filename';e['displayValue']=Path(e['values'][0]).name
                e['applicableWhen']=dict(input=prefix+'FileFlag',values=[1])
                e['description']+=' Saved in this run; imported output directories are not reused.'
    return dict(guide=dict(preparation=dict(id=cid,values={n:v.GetParmVal(parms[n]) for n in PERSISTENT_FIELDS}),title='Surface intersections and CAD',note='OpenVSP intersects the selected normal and thin surfaces, including optional surface regions. Inspect its saved curves and original engine messages before using CAD exports; creating a CAD file does not prove valid shell or solid topology.',sensitivityNote='Compare saved runs at different native curve tolerances to assess approximation. STEP shell and BREP solid exports should be checked in the CAD tool that will use them.',sections=[
        dict(title='Geometry',columns=2,inputs=['UseMode','ModeID','SelectedSetIndex','SelectedDegenSetIndex','IntersectSubSurfs']),
        dict(title='Curves',columns=2,inputs=['RelCurveTol','ExportRawFlag']),
        dict(title='Native files',inputs=[name for prefix in EXPORTS for name in [prefix+'FileFlag',prefix+'FileName']],rows=[[prefix+'FileFlag',prefix+'FileName'] for prefix in EXPORTS]),
        dict(title='CAD units and labels',columns=2,inputs=['CADLenUnit','CADLabelDelim','CADLabelID','CADLabelName','CADLabelSurfNo','CADLabelSplitNo']),
        dict(title='STEP representation',columns=2,inputs=['STEPRepresentation','STEPTol'])]))


def validate(v,schema):
    fields={e['name']:e for e in schema['inputs']};values={}
    for key,e in fields.items():
        if len(e['values'])!=1:raise ValueError(e.get('label',key)+': choose one value.')
        x=e['values'][0];values[key]=x
        if 'choices' in e and x not in [c['value'] for c in e['choices']]:raise ValueError(e['label']+': choose a supported native option.')
        if isinstance(x,(int,float)) and ('min' in e and x<e['min'] or 'max' in e and x>e['max']):raise ValueError(e['label']+': value is outside the native setting limits.')
    if values['UseMode']:
        if values['ModeID'] not in v.GetAllModes():raise ValueError('Choose an existing native mode for surface intersections.')
    else:
        for key in ['SelectedSetIndex','SelectedDegenSetIndex']:
            if values[key] not in range(-1,v.GetNumSets()):raise ValueError('Choose an existing native geometry set for surface intersections.')
    names=[]
    for prefix,label in EXPORTS.items():
        try:names.append(filename(values[prefix+'FileName']))
        except ValueError as error:raise ValueError(label+' filename: '+str(error)) from error
    if len(names)!=len({name.casefold() for name in names}):raise ValueError('Use a different filename for each native intersection export.')


def configure_outputs(v):
    for prefix in EXPORTS:
        key=prefix+'FileName';name=filename(v.GetStringAnalysisInput('SurfaceIntersection',key)[0])
        v.SetStringAnalysisInput('SurfaceIntersection',key,[str(Path.cwd()/name)])
