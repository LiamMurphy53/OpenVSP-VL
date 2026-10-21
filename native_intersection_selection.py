"""Saved native intersection geometry selection and ModeID references."""
import native_managers
import native_references

FIELDS=['UseMode','Set','DegenSet']


def configuration(v,parameter=None):
    cid=native_managers.manager(v,'SurfaceIntersectSettings')
    if parameter is None:
        from native_worker import parameter
    ids={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)}
    path,tree=native_references.document(v)
    try:
        nodes=[n for n in tree.findall('.//SurfaceIntersectSettings') if n.findtext('ParmContainer/ID')==cid]
        if len(nodes)!=1:raise ValueError('Native intersection settings are unavailable.')
        mode=nodes[0].findtext('ModeID','')
    finally:path.unlink(missing_ok=True)
    return dict(id=cid,mode=mode,params=[parameter(v,ids[n]) for n in FIELDS])


def mutate(v,request):
    from native_tools import finite,one
    config=configuration(v);params={p['name']:p for p in config['params']}
    values=request.get('values',{})
    if not isinstance(values,dict):raise ValueError('Choose intersection selection settings.')
    if not values and 'mode' not in request:raise ValueError('Choose intersection selection settings to save.')
    for name,value in values.items():
        p=params[one(name,FIELDS,'Unsupported intersection selection setting.')];finite(value)
        if value!=int(value):raise ValueError(name+': choose a whole number.')
        if not p['min']<=value<=p['max']:raise ValueError(name+': value is outside the native limits.')
        if name in ['Set','DegenSet']:one(int(value),range(-1,v.GetNumSets()),'Choose an existing native geometry set.')
    current={p['name']:p['value'] for p in config['params']};current.update(values)
    mode=request.get('mode',config['mode'])
    if not isinstance(mode,str):raise ValueError('Choose a named native intersection mode.')
    if current['UseMode']:
        one(mode,v.GetAllModes(),'Choose an existing mode before enabling intersection mode selection.')
    elif mode and mode!=config['mode']:
        one(mode,v.GetAllModes(),'Choose an existing native intersection mode.')
    if not current['UseMode']:
        for name in ['Set','DegenSet']:one(int(current[name]),range(-1,v.GetNumSets()),'Choose existing intersection geometry sets.')
    for name,value in values.items():v.SetParmVal(params[name]['id'],value)
    v.Update()
    if mode!=config['mode']:
        native_references.set_reference(v,config['id'],'SurfaceIntersectSettings','ModeID',mode)


def guard_mode_delete(v,mode):
    config=configuration(v)
    if next(p['value'] for p in config['params'] if p['name']=='UseMode') and config['mode']==mode:
        raise ValueError('This mode is selected for surface intersections. Choose another mode or disable intersection mode selection first.')
