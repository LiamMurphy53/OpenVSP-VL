"""Saved native CAD/curve export defaults; no geometry calculations."""
import native_managers
FIELDS=['IntersectSubSurfs','RelCurveTol','ExportRawFlag','SRF_Export','CURV_Export','PLOT3D_Export','IGES_Export','STEP_Export','CADLenUnit','CADLabelDelim','CADLabelID','CADLabelName','CADLabelSurfNo','CADLabelSplitNo','STEPRepresentation','STEPTol']
INPUT_NAMES={'SRF_Export':'SRFFileFlag','CURV_Export':'CURVFileFlag','PLOT3D_Export':'P3DFileFlag','IGES_Export':'IGESFileFlag','STEP_Export':'STEPFileFlag'}
LABELS={'IntersectSubSurfs':'Include surface regions','RelCurveTol':'Relative curve tolerance','ExportRawFlag':'Curve export samples','SRF_Export':'Export surface data','CURV_Export':'Export intersection curves','PLOT3D_Export':'Export Plot3D surfaces','IGES_Export':'Export IGES CAD','STEP_Export':'Export STEP CAD','CADLenUnit':'CAD length unit','CADLabelDelim':'CAD label separator','CADLabelID':'Include component ID','CADLabelName':'Include component name','CADLabelSurfNo':'Include surface number','CADLabelSplitNo':'Include split number','STEPRepresentation':'STEP representation','STEPTol':'STEP tolerance'}


def enum_choices(v):
    from native_mesh import cad_choices
    return {**cad_choices(v), 'ExportRawFlag':[dict(value=0,label='Adapted curves'),dict(value=1,label='Raw intersection points')]}


def annotate(v,p):
    if p['name'] not in FIELDS or v.GetParmContainer(p['id'])!=native_managers.manager(v,'SurfaceIntersectSettings'):return
    p['label']=LABELS[p['name']]
    p['studyLabel']='Surface intersections / Saved defaults / '+p['label']
    p['studyNote']='Saved defaults apply only when a study step does not explicitly override that input.'
    choices=enum_choices(v).get(p['name'])
    if choices:p['choices']=choices
    elif p['type']==v.PARM_BOOL_TYPE:p['choices']=[dict(value=0,label='Off'),dict(value=1,label='On')]


def configuration(v,parameter=None):
    if parameter is None:
        from native_worker import parameter
    cid=native_managers.manager(v,'SurfaceIntersectSettings')
    ids={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)}
    enums=enum_choices(v)
    fields=[]
    for name in FIELDS:
        p=dict(parameter(v,ids[name]),label=LABELS[name])
        if name in enums:p['choices']=enums[name]
        elif p['type']==v.PARM_BOOL_TYPE:p['choices']=[dict(value=0,label='Off'),dict(value=1,label='On')]
        fields.append(p)
    return dict(id=cid,params=fields)


def mutate(v,request):
    from native_tools import finite,one
    params={p['name']:p for p in configuration(v)['params']}
    values=request.get('values')
    if not isinstance(values,dict) or not values:raise ValueError('Choose saved intersection export defaults.')
    for name,value in values.items():
        p=params[one(name,FIELDS,'Unsupported intersection export default.')];finite(value)
        if not p['min']<=value<=p['max']:raise ValueError(p['label']+': value is outside the native limits.')
        if p['type'] in (v.PARM_INT_TYPE,v.PARM_BOOL_TYPE) and value!=int(value):raise ValueError(p['label']+': choose a whole number.')
        if 'choices' in p:one(value,[c['value'] for c in p['choices']],p['label']+': choose a supported native option.')
    for name,value in values.items():v.SetParmVal(params[name]['id'],value)
    v.Update()
