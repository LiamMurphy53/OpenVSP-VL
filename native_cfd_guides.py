"""Readable setup and validation for original native CFD mesh analysis."""
from pathlib import Path
import math
NAME='CfdMeshAnalysis'
EXPORTS={'FACET':'Facet mesh','GMSH':'Gmsh mesh','OBJ':'Wavefront mesh','POLY':'TetGen surface','STL':'STL surface','TRI':'Cart3D triangles'}
RESERVED={'aircraft.vsp3','request.json','response.json','response.json.tmp','engine.log','job.json','job.json.tmp','analysis-setup.json','analysis-setup.json.tmp','surface.msh','cfd-native-drawings.json','native-intersection-drawings.json','intersection-raw.curv','intersection-adapted.curv'}

def filename(value):
    if not isinstance(value,str) or '\\' in value or any(ord(c)<32 for c in value):raise ValueError('Choose a native mesh export filename.')
    name=Path(value).name
    if not name or name.startswith('.') or name.casefold() in RESERVED:raise ValueError('Choose a filename that does not replace a saved run file.')
    return name

def parameters(v):
    result={}
    for container in ['CFDGridDensity','CFDMeshSettings']:
        cid=v.FindContainer(container,0)
        for p in v.FindContainerParmIDs(cid):result[v.GetParmName(p)]=p
    return result

def annotate(v,inputs):
    onoff=[dict(value=0,label='Off'),dict(value=1,label='On')]
    labels=dict(BaseLen='Maximum edge length',MinLen='Minimum edge length',MaxGap='Surface approximation gap',NCircSeg='Circle segmentation',GrowthRatio='Mesh growth ratio',RigorLimit='Growth limiting',RelCurveTol='Relative curve tolerance',UseMode='Geometry selection',ModeID='Native mode',SelectedSetIndex='Normal geometry set',SelectedDegenSetIndex='Thin geometry set',GenerateHalfMesh='Geometry half',IntersectSubSurfs='Include surface regions',ExportRawFlag='Curve export samples',XYZIntCurveFlag='XYZ intersection curves',TaggedMultiSolid='STL solid tagging')
    maps={n:list(onoff) for n in ['IntersectSubSurfs','XYZIntCurveFlag']}
    maps.update(UseMode=[dict(value=0,label='Geometry sets'),dict(value=1,label='Native mode')],ModeID=[dict(value='',label='Choose a mode…'),*[dict(value=m,label=v.GetModeName(m)) for m in v.GetAllModes()]],GenerateHalfMesh=[dict(value=0,label='Whole selected geometry'),dict(value=1,label='Positive-Y half (Y ≥ 0)')],RigorLimit=[dict(value=0,label='Standard growth limiting'),dict(value=1,label='Rigorous growth limiting')],ExportRawFlag=[dict(value=0,label='Adapted curves'),dict(value=1,label='Raw intersection points')],TaggedMultiSolid=[dict(value=0,label='One STL solid'),dict(value=1,label='Tagged STL solids')])
    parms=parameters(v)
    for e in inputs:
        key=e['name'];e['label']=labels.get(key,key)
        if key=='UseSavedSizing':e.update(label='CFD sizing policy',choices=[dict(value=0,label='Enter absolute run lengths'),dict(value=1,label='Preserve saved sizing modes')])
        if key in ('BaseLen','MinLen','MaxGap'):e['applicableWhen']=dict(input='UseSavedSizing',values=[0])
        if key in maps:e['choices']=list(maps[key])
        p=parms.get({'GrowthRatio':'GrowRatio','GenerateHalfMesh':'HalfMesh'}.get(key,key))
        if p:e.update(min=v.GetParmLowerLimit(p),max=v.GetParmUpperLimit(p),nativeParameter=p)
        if key=='ModeID':
            e['applicableWhen']=dict(input='UseMode',values=[1])
            if e['values'][0] and e['values'][0] not in v.GetAllModes():e['choices'].append(dict(value=e['values'][0],label='Unavailable native mode · '+e['values'][0]))
        if key in ['SelectedSetIndex','SelectedDegenSetIndex']:e['applicableWhen']=dict(input='UseMode',values=[0])
        if key=='TaggedMultiSolid':e['applicableWhen']=dict(input='STLFileFlag',values=[1])
        for prefix,label in EXPORTS.items():
            if key==prefix+'FileFlag':e.update(label='Export '+label,choices=list(onoff))
            if key==prefix+'FileName':e.update(label=label+' filename',displayValue=Path(e['values'][0]).name,applicableWhen=dict(input=prefix+'FileFlag',values=[1]))
        if key in ['GMSHFileFlag','GMSHFileName']:
            e['displayReadOnly']=True
            e['editable']=False
            e['description']+=' Studio always saves surface.msh for its native mesh viewer. Other exports use the filenames below.'
    return dict(guide=dict(title='CFD surface mesh',note='OpenVSP intersects and meshes the selected normal and thin surfaces. Sources, far-field domain, wakes and additional native settings come from the saved aircraft; edit them in Modeling tools → Mesh setup. Choose entered absolute run lengths or preserve the saved native sizing modes and drivers. Saved sizing follows native geometry/mode and domain updates; fractions remain dimensionless. Working-aircraft settings are preserved. Studio always retains a Gmsh mesh for inspection.',sensitivityNote='Compare saved runs with finer edge lengths and curve tolerances, inspect native problem edges and faces, and review the engine log before using the mesh in a solver.',sections=[dict(title='Geometry',columns=2,inputs=['UseMode','ModeID','SelectedSetIndex','SelectedDegenSetIndex','GenerateHalfMesh','IntersectSubSurfs']),dict(title='Edge lengths and surface accuracy',inputs=['UseSavedSizing','BaseLen','MinLen','MaxGap','RelCurveTol']),dict(title='Mesh growth and curved surfaces',inputs=['GrowthRatio','RigorLimit','NCircSeg']),dict(title='Curve handling',columns=2,inputs=['ExportRawFlag','XYZIntCurveFlag']),dict(title='Native mesh files',inputs=[key for prefix in EXPORTS for key in [prefix+'FileFlag',prefix+'FileName']],rows=[[prefix+'FileFlag',prefix+'FileName'] for prefix in EXPORTS]),dict(title='STL labels',inputs=['TaggedMultiSolid'])]))

def validate(v,schema):
    fields={e['name']:e for e in schema['inputs']};values={}
    for key,e in fields.items():
        if len(e['values'])!=1:raise ValueError(e.get('label',key)+': choose one value.')
        x=e['values'][0];values[key]=x
        if isinstance(x,(int,float)) and (isinstance(x,bool) or not math.isfinite(x) or 'min' in e and x<e['min'] or 'max' in e and x>e['max']):raise ValueError(e.get('label',key)+': value is outside the native setting limits.')
        if 'choices' in e and x not in [c['value'] for c in e['choices']]:raise ValueError(e['label']+': choose a supported native option.')
    if not values.get('UseSavedSizing') and values['MinLen']>values['BaseLen']:raise ValueError('Minimum edge length cannot exceed maximum edge length.')
    if values['UseMode']:
        if values['ModeID'] not in v.GetAllModes():raise ValueError('Choose an existing native mode for CFD meshing.')
    else:
        for key in ['SelectedSetIndex','SelectedDegenSetIndex']:
            if values[key] not in range(-1,v.GetNumSets()):raise ValueError('Choose an existing native geometry set for CFD meshing.')
        if values['SelectedSetIndex']==values['SelectedDegenSetIndex']==-1:raise ValueError('Choose normal or thin geometry to mesh.')
    names=[filename(values[p+'FileName']) for p in EXPORTS if p!='GMSH' and values[p+'FileFlag']]
    if len(names)!=len({n.casefold() for n in names}):raise ValueError('Use different filenames for selected native mesh exports.')

def configure_outputs(v):
    for prefix in EXPORTS:
        if prefix=='GMSH':continue
        key=prefix+'FileName'
        if v.GetIntAnalysisInput(NAME,prefix+'FileFlag')[0]:
            v.SetStringAnalysisInput(NAME,key,[str(Path.cwd()/filename(v.GetStringAnalysisInput(NAME,key)[0]))])

def apply_registered_settings(v):
    """Original 3.52.2 Execute uses mismatched names for these two inputs.

    Set the original engine parameters in the isolated run copy. The engine
    owns all meshing; no replacement computation or source modification.
    """
    parms=parameters(v);applied={}
    # Registered BaseLen/MinLen/MaxGap inputs are absolute run overrides.
    # Keep saved relative modes in the source aircraft; this is the run copy.
    if not getattr(v,'_studio_cfd_saved_sizing',0):
        for key in ('BaseAbsRel','MinAbsRel','MaxGapAbsRel'):
            p=parms[key];value=v.SetParmVal(p,v.ABS)
            if value!=v.ABS:raise ValueError('OpenVSP did not accept absolute CFD run sizing.')
            applied[key]=dict(parameter=p,nativeName=key,value=value)
    import native_cfd_density
    applied['sizingPolicy']=dict(mode='saved' if getattr(v,'_studio_cfd_saved_sizing',0) else 'absolute',savedDensity={n:v.GetParmVal(parms[n]) for n in native_cfd_density.PAIRS}|{n:v.GetParmVal(parms[n]) for pair in native_cfd_density.PAIRS.values() for n in pair})
    for key,native,getter in [('GrowthRatio','GrowRatio',v.GetDoubleAnalysisInput),('XYZIntCurveFlag','SRF_XYZIntCurve',v.GetIntAnalysisInput)]:
        value=getter(NAME,key)[0];p=parms[native];actual=v.SetParmVal(p,value)
        if actual!=value:raise ValueError(key+': OpenVSP did not retain the requested setting.')
        applied[key]=dict(parameter=p,nativeName=native,value=actual)
    return applied
