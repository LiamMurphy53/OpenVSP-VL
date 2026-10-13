"""Native file formats and imported mesh display data."""
import base64
from pathlib import Path
from native_tools import one,name

EXPORTS={
 'STL':('EXPORT_STL','stl'),'OBJ':('EXPORT_OBJ','obj'),'STEP':('EXPORT_STEP','step'),'IGES':('EXPORT_IGES','igs'),'GMSH':('EXPORT_GMSH','msh'),'SVG':('EXPORT_SVG','svg'),
 'FELISA':('EXPORT_FELISA','fel'),'XSEC':('EXPORT_XSEC','hrm'),'AWAVE':('EXPORT_AWAVE','ram'),'NASCART':('EXPORT_NASCART','dat'),'POVRAY':('EXPORT_POVRAY','pov'),
 'CART3D':('EXPORT_CART3D','tri'),'VSPGEOM':('EXPORT_VSPGEOM','vspgeom'),'VORXSEC':('EXPORT_VORXSEC','hrm'),'XSECGEOM':('EXPORT_XSECGEOM','dat'),'X3D':('EXPORT_X3D','x3d'),
 'PLOT3D':('EXPORT_PLOT3D','p3d'),'BEM':('EXPORT_BEM','bem'),'DXF':('EXPORT_DXF','dxf'),'FACET':('EXPORT_FACET','facet'),'PMARC':('EXPORT_PMARC','pma'),
 'SELIG_AIRFOILS':('EXPORT_SELIG_AIRFOIL','csv'),'BEZIER_AIRFOILS':('EXPORT_BEZIER_AIRFOIL','csv'),'IGES_STRUCTURE':('EXPORT_IGES_STRUCTURE','igs'),'STEP_STRUCTURE':('EXPORT_STEP_STRUCTURE','stp')}
IMPORTS={'CUSTOM_PACKAGE':(None,'zip'),'CUSTOM_SCRIPT':(None,'vsppart'),'STL':('IMPORT_STL','stl'),'NASCART':('IMPORT_NASCART','dat'),'CART3D':('IMPORT_CART3D_TRI','tri'),'XSEC_MESH':('IMPORT_XSEC_MESH','hrm'),'POINTS':('IMPORT_PTS','pts'),'VSP_V2':('IMPORT_V2','vsp'),'BEM':('IMPORT_BEM','bem'),'XSEC_WIRE':('IMPORT_XSEC_WIRE','hrm'),'PLOT3D_WIRE':('IMPORT_P3D_WIRE','p3d')}
LEGACY_EXPORTS=['FELISA','AWAVE','VORXSEC','XSECGEOM']
# These enum constants remain in the API, but Vehicle::ExportFile in 3.52.2
# has no corresponding exporter. Do not present a no-op as a working format.
for legacy in LEGACY_EXPORTS:EXPORTS.pop(legacy)


DESIGN_ATTRIBUTE='Studio.DesignVariable'


def save_design(v):
    """Persist ephemeral native DesignVarMgr references in native attributes."""
    collection=v.GetChildCollection(v.GetVehicleID())
    for attr in v.FindAttributesInCollection(collection):
        if v.GetAttributeName(attr)==DESIGN_ATTRIBUTE:v.DeleteAttribute(attr)
    for i in range(v.GetNumDesignVars()):
        attr=v.AddAttributeParm(collection,DESIGN_ATTRIBUTE,v.GetDesignVar(i))
        v.SetAttributeDoc(attr,str(v.GetDesignVarType(i)))


def restore_design(v):
    collection=v.GetChildCollection(v.GetVehicleID())
    attrs=[a for a in v.FindAttributesInCollection(collection) if v.GetAttributeName(a)==DESIGN_ATTRIBUTE]
    v.DeleteAllDesignVars()
    for attr in attrs:
        doc=v.GetAttributeDoc(attr)
        if doc not in (str(v.XDDM_VAR),str(v.XDDM_CONST)):continue
        for pid in v.GetAttributeParmID(attr):
            if v.ValidParm(pid):v.AddDesignVar(pid,int(doc))


def apply_design(v,r):
    """Decode native file records, then evaluate updates in OpenVSP.

    The release's DES reader finds the first space after a parameter ID; names
    containing spaces corrupt values. It also uses delayed Parm::Set, which
    does not drive all dependent edits. Parsing is file I/O; parameter math and
    dependency evaluation stay in SetParmValUpdate, the native editing API.
    """
    from native_tools import finite,parameter_ids
    import xml.etree.ElementTree as ET
    fmt=one(r['format'],['DES','XDDM']);text=r['content']
    if not isinstance(text,str) or len(text.encode())>5_000_000 or '<!DOCTYPE' in text.upper():raise ValueError('Choose a design file smaller than 5 MB without document type declarations.')
    records=[]
    if fmt=='DES':
        rows=[line.strip() for line in text.splitlines() if line.strip()]
        if not rows:raise ValueError('The design file is empty.')
        count=int(rows[0])
        if not 0<=count<=10000 or len(rows)!=count+1:raise ValueError('The DES parameter count does not match its records.')
        for row in rows[1:]:
            pid=row.split(':',1)[0];_,separator,value=row.rpartition(':')
            if not separator:raise ValueError('Invalid DES parameter record.')
            records.append((pid,float(value),v.XDDM_VAR))
    else:
        root=ET.fromstring(text)
        if root.tag!='Model':raise ValueError('Expected an XDDM Model document.')
        for node in root:
            if node.tag in ('Variable','Constant'):
                records.append((node.attrib['VSPID'],float(node.attrib['Value']),v.XDDM_VAR if node.tag=='Variable' else v.XDDM_CONST))
        if len(records)>10000:raise ValueError('Use at most 10000 design variables.')
    allowed=parameter_ids(v)|{p for g in v.FindGeoms() for p in v.GetGeomParmIDs(g)}
    for pid,value,typ in records:one(pid,allowed,'A design-file parameter does not belong to this aircraft.');finite(value)
    if len({pid for pid,_,_ in records})!=len(records):raise ValueError('Design-file parameter IDs must be unique.')
    v.DeleteAllDesignVars()
    for pid,value,typ in records:
        v.AddDesignVar(pid,typ);v.SetParmValUpdate(pid,value)
    save_design(v)


def import_geometry(v,r):
    fmt=one(r['format'],IMPORTS);enum,ext=IMPORTS[fmt]
    content=r['content']
    if not isinstance(content,str) or len(content)>67_000_000:raise ValueError('Choose a geometry file smaller than 50 MB.')
    try:raw=base64.b64decode(content,validate=True)
    except ValueError:raise ValueError('Invalid geometry file data.')
    if not raw or len(raw)>50_000_000:raise ValueError('Choose a nonempty geometry file smaller than 50 MB.')
    if fmt in ('CUSTOM_SCRIPT','CUSTOM_PACKAGE'):
        import hashlib
        from native_custom_scripts import import_script,unpack_package
        parent=r.get('parent','')
        if parent:one(parent,v.FindGeoms())
        if fmt=='CUSTOM_PACKAGE':
            path=unpack_package(raw,Path.cwd()/'component-package')
        else:
            if len(raw)>5_000_000:raise ValueError('Choose a custom component script smaller than 5 MB.')
            path=Path.cwd()/'imported.vsppart';path.write_bytes(raw)
        try:path.read_text(encoding='utf-8')
        except UnicodeDecodeError:raise ValueError('Custom component scripts must be UTF-8 text.')
        gid=import_script(v,path,'StudioPart_'+hashlib.sha256(raw).hexdigest()[:16],parent,Path.cwd()/'component-package' if fmt=='CUSTOM_PACKAGE' else None)
        if r.get('name'):v.SetGeomName(gid,name(r['name']))
        v.Update()
        if v.GetGeomParent(gid)!=(parent or 'NONE'):raise ValueError('OpenVSP did not apply the chosen script component parent.')
        return gid
    from native_import_validation import validate
    native_input=validate(raw,fmt)
    parent=r.get('parent','')
    if parent:one(parent,v.FindGeoms())
    path=Path.cwd()/('imported.'+ext);path.write_bytes(native_input)
    before=set(v.FindGeoms());gid=v.ImportFile(str(path),getattr(v,enum),parent);v.Update()
    added=set(v.FindGeoms())-before
    if not added:raise ValueError(fmt+': OpenVSP produced no geometry from this file. Check its format and contents.')
    if parent:
        # Native wire readers explicitly clear the active geometry before
        # creating their Blank group. Apply the requested owner with the SDK,
        # preserving each imported subtree and its native attachment settings.
        roots=[g for g in added if v.GetGeomParent(g) not in added]
        for root in roots:
            if v.GetGeomParent(root)!=parent:v.SetGeomParent(root,parent)
        v.Update()
        if any(v.GetGeomParent(root)!=parent for root in roots):
            raise ValueError('OpenVSP did not apply the chosen import parent.')
    if gid in added and r.get('name'):v.SetGeomName(gid,name(r['name']))
    return gid if gid in added else sorted(added)[0]


def export(v,r):
    kind=r.get('kind')
    folder=Path.cwd()/'output';folder.mkdir(exist_ok=True)
    if kind=='fit':
        path=folder/'model.fit';v.SaveFitModelFile(str(path))
    elif kind=='design-variables':
        fmt=one(r['format'],['DES','XDDM']);path=folder/('design.'+('des' if fmt=='DES' else 'xddm'))
        (v.WriteDESFile if fmt=='DES' else v.WriteXDDMFile)(str(path))
    else:
        fmt=one(r['format'],EXPORTS);enum,ext=EXPORTS[fmt];index=one(r.get('set',0),range(v.GetNumSets()));thin=one(r.get('thinSet',-1),range(-1,v.GetNumSets()))
        mode=r.get('mode','')
        if mode:one(mode,v.GetAllModes())
        if fmt=='BEM':
            g=one(r.get('geom'),v.FindGeoms())
            if v.GetGeomTypeName(g).upper() not in ('PROP','PROPELLER'):raise ValueError('Choose a propeller for blade-element export.')
            v.SetBEMPropID(g)
        if fmt.endswith('_STRUCTURE'):
            structures=list(v.GetFeaStructIDVec());sid=one(r.get('structure'),structures,'Choose a structure for structural CAD export.')
            v.SetFeaMeshStructIndex(structures.index(sid))
            # Structural CAD uses Vehicle's export index, independently of the
            # FeaMeshMgr selection. Select the requested structure in both.
            v.SetParmVal(v.FindParm(v.GetVehicleID(),'StructureExportIndex','STEPSettings' if fmt.startswith('STEP') else 'IGESSettings'),structures.index(sid))
        path=folder/('aircraft.'+ext)
        v.ExportFile(str(path),index,getattr(v,enum),int(r.get('tagSubsurfaces',True)),thin,bool(mode),mode)
    files=[p for p in folder.iterdir() if p.is_file() and not p.is_symlink() and p.stat().st_size]
    if not files:raise ValueError('The native engine produced no export files for this selection.')
    return dict(filename=str(path.relative_to(Path.cwd())),files=[str(p.relative_to(Path.cwd())) for p in sorted(files)])


def mesh_geometry(v,gid):
    """Read engine-evaluated, transformed triangles through Results Manager."""
    rid=v.CreateGeomResults(gid,'Studio_Display_Mesh')
    keys=set(v.GetAllDataNames(rid));points=[];faces=[]
    if 'Tri_Pnts' in keys:
        points=[[p.x(),p.y(),p.z()] for p in v.GetVec3dResults(rid,'Tri_Pnts')]
        columns=[list(v.GetIntResults(rid,'Tri_Index'+str(k))) for k in range(3)]
        faces=[list(tri) for tri in zip(*columns)]
    if 'Num_Slices' in keys:
        for i in range(v.GetNumData(rid,'Slice_Tris_Pnt_0')):
            columns=[list(v.GetVec3dResults(rid,'Slice_Tris_Pnt_'+str(k),i)) for k in range(3)]
            for tri in zip(*columns):
                faces.append(list(range(len(points),len(points)+3)));points.extend([[p.x(),p.y(),p.z()] for p in tri])
    v.DeleteResult(rid)
    if len(points)>1_000_000 or len(faces)>1_000_000:raise ValueError('Imported mesh exceeds the one-million-element display limit.')
    if any(len(t)!=3 or any(not 0<=n<len(points) for n in t) for t in faces):raise ValueError('Invalid native display mesh connectivity.')
    return dict(points=points,triangles=faces)


def solid_preview(v,gid):
    """Official exporter supplies triangles for non-parametric native geometry."""
    import struct
    import uuid
    before=set(v.FindGeoms());index=v.GetNumSets()-1
    # The native STL exporter creates display meshes and hides source geometry.
    # A read-only preview must restore every original visibility/set flag.
    flags={g:[v.GetSetFlag(g,i) for i in range(v.GetNumSets())] for g in before}
    path=Path.cwd()/('preview-'+uuid.uuid4().hex+'.stl')
    try:
        for g in before:v.SetSetFlag(g,index,g==gid)
        v.ExportFile(str(path),index,v.EXPORT_STL,0)
        raw=path.read_bytes();points=[]
        count=struct.unpack_from('<I',raw,80)[0] if len(raw)>=84 else -1
        if len(raw)==84+50*count:
            for i in range(count):
                values=struct.unpack_from('<12f',raw,84+50*i);points.extend([list(values[j:j+3]) for j in [3,6,9]])
        else:
            for row in raw.decode().splitlines():
                parts=row.split()
                if parts and parts[0]=='vertex':points.append([float(x) for x in parts[1:4]])
        if not points or len(points)%3:raise ValueError('The native solid exporter returned no valid display triangles.')
        if len(points)>3_000_000:raise ValueError('Native solid exceeds the one-million-triangle display limit.')
        return dict(points=points,triangles=[list(range(i,i+3)) for i in range(0,len(points),3)],source='Native STL export')
    finally:
        path.unlink(missing_ok=True)
        for g in set(v.FindGeoms())-before:v.DeleteGeom(g)
        for g in before:
            for i,member in enumerate(flags[g]):v.SetSetFlag(g,i,member)
