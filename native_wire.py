"""Guided wire settings; OpenVSP owns point processing and geometry math."""
import math

FIELDS=[
    ('WireType','Surface classification','Classification'),
    ('InvertFlag','Invert surface normals','Orientation'),
    ('FlipIJFlag','Swap I and J directions','Orientation'),
    ('RevIFlag','Reverse I direction','Orientation'),
    ('RevJFlag','Reverse J direction','Orientation'),
    ('ISkipStart','Trim I start','Trimming and sampling'),
    ('ISkipEnd','Trim I end','Trimming and sampling'),
    ('JSkipStart','Trim J start','Trimming and sampling'),
    ('JSkipEnd','Trim J end','Trimming and sampling'),
    ('IStride','I sampling stride','Trimming and sampling'),
    ('JStride','J sampling stride','Trimming and sampling'),
    ('IStartPatchType','I start patch','Boundary patches'),
    ('IEndPatchType','I end patch','Boundary patches'),
    ('JStartPatchType','J start patch','Boundary patches'),
    ('JEndPatchType','J end patch','Boundary patches'),
]


def settings(v,gid,parameters):
    by_name={p['name']:p for p in parameters if p['rawGroup'].lower()=='wireframe'}
    fields=[]
    for name,label,group in FIELDS:
        if name not in by_name:raise ValueError('A native wire geometry setting is unavailable: '+name)
        field=dict(by_name[name],label=label,section=group)
        field['help']=('Classifies the imported surface for native exports and analyses.' if name=='WireType' else
                       'Controls the native surface normal direction.' if name=='InvertFlag' else
                       'Reorders native grid directions before trimming and sampling.' if name in ('FlipIJFlag','RevIFlag','RevJFlag') else
                       'Removes this many boundary rows or columns. Excessive trimming leaves no geometry.' if 'Skip' in name else
                       'Keeps every chosen row or column and the final boundary.' if 'Stride' in name else
                       'Adds a native boundary patch: point center, paired-point line, opposite boundary copy, or halfway between boundaries.')
        if name=='WireType':field['choices']=[dict(value=0,label='Lifting surface'),dict(value=1,label='Nonlifting surface')]
        elif name.endswith('PatchType'):
            field['choices']=[dict(value=getattr(v,'PATCH_'+key),label=label) for key,label in
                              [('NONE','None'),('POINT','Point'),('LINE','Line'),('COPY','Copy'),('HALFWAY','Halfway')]]
        elif field['type']==v.PARM_BOOL_TYPE:field['choices']=[dict(value=0,label='Off'),dict(value=1,label='On')]
        fields.append(field)
    return dict(fields=fields,operation='WireGeom native parameters')


def mutate(v,r):
    from native_tools import one
    gid=one(r.get('geom'),v.FindGeoms(),'Choose an existing wire geometry.')
    if v.GetGeomTypeName(gid).upper()!='WIREFRAME':raise ValueError('Choose native wire geometry to edit.')
    parameters=[dict(id=p,name=v.GetParmName(p),rawGroup=v.GetParmGroupName(p),value=v.GetParmVal(p),
                     min=v.GetParmLowerLimit(p),max=v.GetParmUpperLimit(p),type=v.GetParmType(p)) for p in v.GetGeomParmIDs(gid)]
    schema=settings(v,gid,parameters)
    fields={p['name']:p for p in schema['fields']};values=r.get('values')
    if not isinstance(values,dict) or set(values)!=set(fields):raise ValueError('Supply all fifteen native wire settings.')
    # Validate the entire request before any native update or saved-file write.
    for name,value in values.items():
        p=fields[name]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value!=int(value):
            raise ValueError(p['label']+': enter a whole number.')
        if not p['min']<=value<=p['max']:raise ValueError(p['label']+': value is outside the native limits.')
        if 'choices' in p and value not in [c['value'] for c in p['choices']]:raise ValueError(p['label']+': choose a native option.')
    for name,value in values.items():v.SetParmValUpdate(fields[name]['id'],value)
    return gid
