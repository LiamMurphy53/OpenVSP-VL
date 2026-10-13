"""Expose the official SurfacePatches result hierarchy and exact native grids."""
import json,math
from pathlib import Path

def annotate(v,inputs):
    for e in inputs:
        if e['name']=='Set':e['label']='Geometry set'
    return dict(guide=dict(title='Surface patch inspection',note='OpenVSP samples each native surface patch as a structured grid of coordinates and normals. Select a geometry set, inspect patches by component and native surface index, and download the exact samples. This is a geometry inspection, not a CFD or structural mesh.',sensitivityNote='Compare native surface tessellation when inspecting geometry detail. Cap patches and collapsed boundaries retain their original samples and normals.',sections=[dict(title='Geometry',inputs=['Set'])]))

def validate(v,schema):
    e=next(e for e in schema['inputs'] if e['name']=='Set')
    if len(e['values'])!=1 or e['values'][0]<v.SET_NONE or e['values'][0]>=v.GetNumSets():raise ValueError('Choose one existing native geometry set.')

def geometry(results):
    byid={r['id']:r for r in results}
    def vals(r,key):return next((e['values'] for e in r['entries'] if e['name']==key),[])
    def one(r,key):return next(iter(vals(r,key)),None)
    names={one(r,'id'):one(r,'name') for r in results if r['name']=='ComponentSurfaces'}
    out=dict(filename='Native surface patches',geometryPreview=True,nodes=[],nodeIDs=[],elements=[],groups=[],warnings=[],displayNote='Coordinates and point normals are exact native patch samples. Display faces and lines connect adjacent samples in each original grid. Native component, surface and patch identifiers are retained; this display is not an exported analysis mesh.')
    for patch in (r for r in results if r['name']=='SurfacePatch'):
        xyz=[vals(patch,k) for k in ('x','y','z')];normals=[vals(patch,k) for k in ('nx','ny','nz')]
        rows=len(xyz[0]);cols=len(xyz[0][0]) if rows else 0
        valid=rows and cols and all(len(a)==rows and all(isinstance(row,list) and len(row)==cols and all(isinstance(t,(int,float)) and math.isfinite(t) for t in row) for row in a) for a in xyz+normals)
        if not valid:out['warnings'].append('Native patch '+patch['id']+' has no rectangular finite coordinate/normal grid; original result arrays remain in JSON and CSV.');continue
        if len(out['nodes'])+rows*cols>500000:out['warnings'].append('Patch preview point limit reached. Complete native grids remain in the saved results.');break
        gid=len(out['groups'])+1;start=len(out['nodes']);points=[list(p) for section in zip(*xyz) for p in zip(*section)];point_normals=[list(p) for section in zip(*normals) for p in zip(*section)];out['nodes']+=points;out['nodeIDs']+=list(range(start+1,start+len(points)+1));before=len(out['elements'])
        def cell(indices,kind):
            out['elements'].append(dict(id=len(out['elements'])+1,type='native patch grid',kind=kind,group=gid,nodes=[start+i for i in indices],nativeSurface=one(patch,'surf_index'),nativePatch=one(patch,'patch_index'),nativeResultID=patch['id'],nativePointNormals=[point_normals[i] for i in indices]))
        if rows>1 and cols>1:
            for i in range(rows-1):
                for j in range(cols-1):cell([i*cols+j,(i+1)*cols+j,(i+1)*cols+j+1,i*cols+j+1],'face')
        elif len(points)>1:
            for i in range(len(points)-1):cell([i,i+1],'line')
        else:cell([0],'point')
        comp=one(patch,'comp_id');out['groups'].append(dict(id=gid,name=str(names.get(comp,comp))+' · surface '+str(one(patch,'surf_index'))+' · patch '+str(one(patch,'patch_index')),count=len(out['elements'])-before,rows=rows,columns=cols,nativeComponentID=comp,nativeSurface=one(patch,'surf_index'),nativePatch=one(patch,'patch_index'),nativeResultID=patch['id']))
    out['totalElements']=len(out['elements'])
    if not out['nodes'] and not out['warnings']:out['warnings'].append('The selected native set produced no surface-patch samples. Choose a set containing surface geometry.')
    return out

def save(data):
    name='surface-patches.json';Path(name).write_text(json.dumps(geometry(data['results']),allow_nan=False));data['guideFile']=name;return data
