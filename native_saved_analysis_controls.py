"""Readable choices for original Vehicle-owned engineering defaults."""
AXES=[('X_DIR','X · longitudinal'),('Y_DIR','Y · spanwise'),('Z_DIR','Z · vertical')]
FIELDS={
 ('MassProperties','MassSliceDir'):('Mass slicing direction',AXES),
 ('PSlice','PlanarAxisType'):('Planar slicing axis',AXES),
 ('Projection','DirectionType'):('Projection direction',[('X_PROJ','X · front'),('Y_PROJ','Y · side'),('Z_PROJ','Z · top'),('GEOM_PROJ','Component direction'),('VEC_PROJ','Custom vector')]),
 ('Projection','BoundaryType'):('Projection clipping boundary',[('NO_BOUNDARY','No clipping boundary'),('SET_BOUNDARY','Geometry set'),('GEOM_BOUNDARY','One component')]),
 ('DegenGeom','DegenGeomMeshType'):('Degenerate mesh representation',[('TRI_MESH_TYPE','Native triangle mesh'),('QUAD_MESH_TYPE','Quadrilateral setting · this release emits triangles'),('NGON_MESH_TYPE','Native polygon mesh · Gmsh export is triangulated')]),
 ('Measure','LenUnit'):('Measurement length units',[('LEN_MM','mm'),('LEN_CM','cm'),('LEN_M','m'),('LEN_IN','in'),('LEN_FT','ft'),('LEN_YD','yd'),('LEN_UNITLESS','Unitless')])}

def annotate(v,p):
    definition=FIELDS.get((p['rawGroup'],p['name']))
    if not definition or v.GetParmContainer(p['id'])!=v.GetVehicleID():return
    label,items=definition
    choices=[dict(value=getattr(v,name),label=text) for name,text in items if hasattr(v,name) and p['min']<=getattr(v,name)<=p['max']]
    if p['value'] not in [c['value'] for c in choices]:choices.append(dict(value=p['value'],label='Saved native value '+str(p['value'])))
    p.update(label=label,choices=choices,studyLabel='Vehicle / '+p['rawGroup']+' / '+label)
    if p['rawGroup']=='Projection':p['description']='Use Apply saved projection options in Analyze to copy this setting. Configure component and set references there.'
    if p['rawGroup']=='Measure':p['description']='Original OpenVSP measurement units. Workspace display units are selected separately in the top bar.'

def projection_options(v):
    mapping={'TargetType':'TargetType','BoundaryType':'BoundaryType','DirectionType':'DirectionType','TargetHullFlag':'TargetHullFlag','BoundaryHullFlag':'BoundaryHullFlag','DiskSegmentBreakdown':'DiskSegmentBreakdownFlag'}
    owner=v.GetVehicleID()
    entries=[dict(name=name,index=0,values=[int(v.GetParmVal(v.FindParm(owner,parm,'Projection')))]) for name,parm in mapping.items()]
    entries.append(dict(name='Direction',index=0,values=[[v.GetParmVal(v.FindParm(owner,axis+'Comp','Projection')) for axis in 'XYZ']]))
    return entries

def bind_inputs(v,name,inputs):
    # Declare only fields the original SDK actually inherits on reset.
    mapping={'MassProp':{'MassSliceDir':('MassProperties','MassSliceDir')},'DegenGeomMesh':{'DegenGeomMeshType':('DegenGeom','DegenGeomMeshType')}}.get(name,{})
    for field in inputs:
        if field['name'] in mapping:
            group,parm=mapping[field['name']];field['nativeParameter']=v.FindParm(v.GetVehicleID(),parm,group)
