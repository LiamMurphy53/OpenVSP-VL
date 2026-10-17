"""Guides and exact saved geometry for native degenerate analyses."""
import native_ngon
import json,math
from pathlib import Path

NAMES={'DegenGeom','DegenGeomMesh'}

def annotate(v,name,inputs):
    modes=[dict(value='',label='Choose a mode…'),*[dict(value=m,label=v.GetModeName(m)) for m in v.GetAllModes()]]
    choices={'UseModeFlag':[dict(value=0,label='Geometry set'),dict(value=1,label='Native mode')],
             'ModeID':modes,'DegenGeomMeshType':[dict(value=v.TRI_MESH_TYPE,label='Native triangle mesh'),dict(value=v.QUAD_MESH_TYPE,label='Quadrilateral setting · this release emits triangles'),dict(value=v.NGON_MESH_TYPE,label='Native polygon mesh · Gmsh export is triangulated')]}
    labels={'Set':'Geometry set','UseModeFlag':'Geometry selection','ModeID':'Native mode','WriteCSVFlag':'Native degenerate-geometry CSV','WriteMFileFlag':'Native MATLAB file','DegenGeomMeshType':'Native mesh representation'}
    for e in inputs:
        key=e['name'];e['label']=labels.get(key,key)
        if key.startswith('Write'):e['choices']=[dict(value=0,label='Off'),dict(value=1,label='Save native file with this run')]
        if key in choices:e['choices']=list(choices[key])
        if name=='DegenGeom':
            if key=='Set':e['applicableWhen']=dict(input='UseModeFlag',values=[0])
            if key=='ModeID':
                e['applicableWhen']=dict(input='UseModeFlag',values=[1]);e['description']='This analysis applies the mode presets and uses its normal geometry set. The mode’s thin/degenerate set is not included.'
                if e['values'][0] not in [c['value'] for c in modes]:e['choices'].append(dict(value=e['values'][0],label='Unavailable native mode · '+e['values'][0]))
    note='OpenVSP computes full surface grids, flat plates, camber coordinates, section sticks and point properties. Symmetry copies and native records stay separate. Inspect and export these representations before using them in downstream analysis.' if name=='DegenGeom' else 'OpenVSP creates its degenerate MeshGeom or NGonMeshGeom from the selected geometry. The generated native aircraft is saved alongside its native Gmsh export. In this release, the quadrilateral setting creates the same triangular MeshGeom; polygon meshes are triangulated for viewing. Their original polygon data is saved as a native VSPGEOM file with its companion files; Studio also saves polygon snapshots in its project file for reopening here. Original OpenVSP does not restore those snapshots.'
    sections=[dict(title='Geometry',inputs=['UseModeFlag','ModeID','Set']),dict(title='Native files',inputs=['WriteCSVFlag','WriteMFileFlag'])] if name=='DegenGeom' else [dict(title='Geometry and representation',inputs=['Set','DegenGeomMeshType'])]
    return dict(guide=dict(title='Degenerate geometry representations' if name=='DegenGeom' else 'Degenerate geometry mesh',note=note,sensitivityNote='Compare native tessellation and section counts. These geometry outputs do not establish aerodynamic convergence or mesh quality.',sections=sections))

def validate(v,name,schema):
    fields={e['name']:e for e in schema['inputs']}
    for key,e in fields.items():
        if len(e['values'])!=1:raise ValueError(e['label']+': choose one native value.')
        if 'choices' in e and e['values'][0] not in [c['value'] for c in e['choices']]:raise ValueError(e['label']+': choose a supported native option.')
    if name=='DegenGeom' and fields['UseModeFlag']['values'][0]:
        if fields['ModeID']['values'][0] not in v.GetAllModes():raise ValueError('Choose an existing native mode for degenerate geometry.')
    else:
        index=fields['Set']['values'][0]
        if index not in range(v.GetNumSets()) or not v.GetGeomSetAtIndex(index):raise ValueError('Choose a geometry set containing components.')

def export_mesh(v,ids,filename):
    """Native exporter supplies every coordinate and connectivity record."""
    from native_worker import errors
    from mesh_io import read_gmsh
    slot=v.GetNumSets()-1;before=set(v.FindGeoms())
    flags={g:(v.GetSetFlag(g,slot),v.GetSetFlag(g,v.SET_SHOWN)) for g in before}
    try:
        for g in before:v.SetSetFlag(g,slot,g in ids)
        v.ExportFile(str(Path.cwd()/filename),slot,v.EXPORT_GMSH,1);errors(v)
        return read_gmsh(Path.cwd()/filename)
    finally:
        # Native export of an NGonMesh creates an auxiliary triangle mesh.
        # Keep the requested native mesh, and restore all affected selections.
        for g in set(v.FindGeoms())-before:v.DeleteGeom(g)
        for g,(member,shown) in flags.items():
            v.SetSetFlag(g,slot,member);v.SetSetFlag(g,v.SET_SHOWN,shown)

def export_polygon(v,ids,filename):
    """Preserve the live original polygon mesh before native VSP3 loses it."""
    from native_worker import errors
    folder=Path.cwd();before_files=set(folder.iterdir());slot=v.GetNumSets()-1;before=set(v.FindGeoms())
    flags={g:(v.GetSetFlag(g,slot),v.GetSetFlag(g,v.SET_SHOWN)) for g in before}
    try:
        for g in before:v.SetSetFlag(g,slot,g in ids)
        v.ExportFile(str(folder/filename),slot,v.EXPORT_VSPGEOM,1);errors(v)
        if not (folder/filename).is_file() or not (folder/filename).stat().st_size:raise ValueError('OpenVSP did not write the native polygon export.')
        return sorted(p.name for p in set(folder.iterdir())-before_files if p.is_file() and not p.is_symlink())
    finally:
        for g in set(v.FindGeoms())-before:v.DeleteGeom(g)
        for g,(member,shown) in flags.items():v.SetSetFlag(g,slot,member);v.SetSetFlag(g,v.SET_SHOWN,shown)


def geometry(results):
    by_id={r['id']:r for r in results};nodes=[];elements=[];groups=[];warnings=[]
    def values(r,key):return next((e['values'] for e in r['entries'] if e['name']==key),[])
    def one(r,key,default=None):return next(iter(values(r,key)),default)
    def grid(r,keys,label,surface,hidden=False,normal_keys=None):
        axes=[values(r,k) for k in keys]
        if not axes[0]:warnings.append(label+': native coordinate grid is empty.');return
        lengths=[[len(row) for row in axis] for axis in axes]
        if lengths[0]!=lengths[1] or lengths[0]!=lengths[2] or len(set(lengths[0]))!=1 or any(not isinstance(x,(int,float)) or not math.isfinite(x) for axis in axes for row in axis for x in row):warnings.append(label+': native grid is incomplete or undefined; see full saved results.');return
        rows=len(axes[0]);cols=lengths[0][0]
        if rows<2 or cols<2:warnings.append(label+': fewer than two native rows or columns.');return
        if len(nodes)+rows*cols>500000:warnings.append(label+': exceeds the 500,000-point display limit; full native results and exports remain available.');return
        group=len(groups)+1;offset=len(nodes);first=len(elements)
        nodes.extend([[axes[k][i][j] for k in range(3)] for i in range(rows) for j in range(cols)])
        normal_axes=[values(r,k) for k in normal_keys] if normal_keys else []
        for i in range(rows-1):
            for j in range(cols-1):
                entry=dict(id=len(elements)+1,type='native grid quad',kind='quad',group=group,nodes=[offset+i*cols+j,offset+(i+1)*cols+j,offset+(i+1)*cols+j+1,offset+i*cols+j+1],nativeSurface=surface,nativeResultID=r['id'])
                if normal_axes and all(i<len(a) and j<len(a[i]) and math.isfinite(a[i][j]) for a in normal_axes):entry['nativeNormal']=[a[i][j] for a in normal_axes]
                elements.append(entry)
        groups.append(dict(id=group,name=label,count=len(elements)-first,initiallyHidden=hidden,nativeResultID=r['id'],rows=rows,columns=cols))
    for parent in [r for r in results if r['name']=='Degen_DegenGeom']:
        label=str(one(parent,'name'))+' · surface '+str(one(parent,'surf_index'))+' · symmetry copy '+str(one(parent,'sym_copy_index'))
        surf=one(parent,'surf');surface=one(parent,'surf_index')
        if surf in by_id:grid(by_id[surf],['x','y','z'],label+' · full surface',surface,bool(values(parent,'plates')),['nx','ny','nz'])
        for i,rid in enumerate(values(parent,'plates')):
            if rid not in by_id:warnings.append(label+': native plate record is unavailable.');continue
            plate=by_id[rid];lifting=one(parent,'type')=='LIFTING_SURFACE';grid(plate,['x','y','z'],label+' · plate '+str(i),surface,lifting)
            grid(plate,['xCamberx','xCambery','xCamberz'],label+' · camber '+str(i),surface,not lifting)
    for blank in [r for r in results if r['name']=='Degen_BlankGeom']:
        points=values(blank,'X')
        if points and all(len(p)==3 and all(math.isfinite(x) for x in p) for p in points):
            group=len(groups)+1;offset=len(nodes);nodes.extend(points);mass=one(blank,'mass');label=str(one(blank,'name'))+' · native blank point'
            for i in range(len(points)):elements.append(dict(id=len(elements)+1,type='native blank point',kind='point',group=group,nodes=[offset+i],nativeSource=label,nativeMass=mass,nativeResultID=blank['id']))
            groups.append(dict(id=group,name=label,count=len(points),nativeResultID=blank['id']))
    if not nodes:warnings.append('The selected native geometry produced no surface or blank-point samples. Degenerate representations use a mode’s normal geometry set; choose another mode or a set containing surfaces.')
    return dict(filename='Native degenerate representations',nodes=nodes,nodeIDs=list(range(1,len(nodes)+1)),elements=elements,groups=groups,totalElements=len(elements),geometryPreview=True,warnings=warnings,displayNote='All points are exact native full-surface, flat-plate or camber-coordinate samples. Display quads connect adjacent native grid samples; they are not an exported analysis mesh. Groups preserve native surface and symmetry indices. Native cell-normal samples are retained where supplied.')

def save(v,data,name):
    if name=='DegenGeom':
        drawing=geometry(data['results']);filename='degenerate-representations.json';Path(filename).write_text(json.dumps(drawing,allow_nan=False));data['guideFile']=filename
        return data
    import native_mesh
    result=next(r for r in data['results'] if r['name']=='DegenGeomMesh');ids=next(e['values'] for e in result['entries'] if e['name']=='Mesh_GeomID')
    if not ids or ids[0] not in v.FindGeoms():raise ValueError('OpenVSP did not create a degenerate mesh for this selection.')
    gid=ids[0];kind=v.GetGeomTypeName(gid);filename='degenerate-geometry.msh';mesh=export_mesh(v,ids,filename)
    polygon=kind.upper() in ('NGONMESH','NGON_MESH');polygon_file='degenerate-polygons.vspgeom' if polygon else None
    polygon_files=export_polygon(v,ids,polygon_file) if polygon else []
    model='degenerate-mesh.vsp3';native_ngon.write(v,Path.cwd()/model)
    from native_worker import errors
    errors(v)
    data.update(meshFile=filename,meshSummary=native_mesh.summary(mesh),degenerateMesh=dict(nativeGeomType=kind,nativeGeomID=gid,modelFile=model,modelGeometrySaved=True,nativeModelGeometrySaved=not polygon,studioPolygonSnapshot=polygon,polygonFile=polygon_file,polygonFiles=polygon_files,requestedMeshType=next(e['values'][0] for e in data['inputs'] if e['name']=='DegenGeomMeshType')))
    return data
