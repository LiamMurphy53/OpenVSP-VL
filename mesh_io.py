"""Read native Gmsh 2.x exports for display; no mesh generation or solver math."""
import math
import shlex
from pathlib import Path

# Gmsh type: (node count, number of corner nodes, display kind).
ELEMENTS={1:(2,2,'line'),2:(3,3,'face'),3:(4,4,'face'),8:(3,2,'line'),9:(6,3,'face'),10:(9,4,'face'),16:(8,4,'face'),15:(1,1,'point')}


def read_gmsh(path, native_point_mass_file=None):
    path=Path(path)
    if path.stat().st_size>150_000_000: raise ValueError('This mesh exceeds the 150 MB preview limit. Download the full native file.')
    masses=[]
    if native_point_mass_file is not None:
        source=Path(native_point_mass_file)
        if source.stat().st_size>150_000_000:raise ValueError('Native point-mass companion exceeds the preview limit.')
        for line in source.read_text().splitlines():
            if line.startswith('CONM2'):
                values=line.split(',')
                if len(values)<5:raise ValueError('Invalid native point-mass record.')
                masses.append(dict(id=int(values[1]),node=int(values[2]),mass=values[4].strip()))
    rows=iter(path.read_text().splitlines());nodes=[];node_ids=[];lookup={};elements=[];names={};skipped=0;total=0;missing=0
    for row in rows:
        if row=='$MeshFormat':
            fmt=next(rows).split()
            if not fmt[0].startswith('2.') or fmt[1]!='0': raise ValueError('Preview supports native ASCII Gmsh 2.x files.')
        elif row=='$PhysicalNames':
            for _ in range(int(next(rows))):
                parts=shlex.split(next(rows));names[int(parts[1])]=parts[2]
        elif row=='$Nodes':
            count=int(next(rows))
            if count>1_000_000: raise ValueError('Mesh exceeds the one-million-node preview limit. Download its native file.')
            for _ in range(count):
                p=next(rows).split();nid=int(p[0]);xyz=list(map(float,p[1:4]))
                if len(xyz)!=3 or not all(math.isfinite(x) for x in xyz) or nid in lookup: raise ValueError('Invalid mesh nodes.')
                lookup[nid]=len(nodes);node_ids.append(nid);nodes.append(xyz)
        elif row=='$Elements':
            total=int(next(rows))
            for _ in range(total):
                record=next(rows,None)
                if record is None or record=='$EndElements':
                    missing=total-_
                    # 3.52.2 counts point masses but its Gmsh virtual writer
                    # emits no record for them. Accept only an exact independent
                    # native CONM2 count; arbitrary truncation remains an error.
                    if missing!=len(masses):raise ValueError('The native mesh element list is incomplete.')
                    break
                p=list(map(int,record.split()));eid,typ,ntags=p[:3];tags=p[3:3+ntags];ids=p[3+ntags:]
                if typ not in ELEMENTS:skipped+=1;continue
                count,corners,kind=ELEMENTS[typ]
                if len(ids)!=count or any(n not in lookup for n in ids): raise ValueError('Invalid mesh element connectivity.')
                elements.append(dict(id=eid,type=typ,group=tags[0] if tags else 0,kind=kind,nodes=[lookup[n] for n in ids[:corners]],order=2 if count>corners else 1))
    if missing:
        group=max(names.keys()|{e['group'] for e in elements},default=0)+1
        names[group]='Native point masses (NASTRAN)'
        for mass in masses:
            if mass['node'] not in lookup:raise ValueError('Native point mass refers to a missing mesh node.')
            elements.append(dict(id='CONM2 '+str(mass['id']),type=15,group=group,kind='point',nodes=[lookup[mass['node']]],order=1,nativeSource='NASTRAN CONM2',nativeMass=mass['mass']))
    if not nodes or not any(e['kind'] in ('line','face') for e in elements): raise ValueError('The native file contains no displayable mesh elements.')
    groups=[]
    for gid in sorted({e['group'] for e in elements}):
        groups.append(dict(id=gid,name=names.get(gid,f'Region {gid}'),count=sum(e['group']==gid for e in elements)))
    return dict(nodes=nodes,nodeIDs=node_ids,elements=elements,groups=groups,totalElements=total,unsupportedElements=skipped,
                higherOrder=any(e['order']>1 for e in elements),filename=path.name,
                nativePointMasses=masses if missing else [],warnings=['OpenVSP’s Gmsh file omits point-mass elements. Their native nodes and masses are shown from the accompanying NASTRAN CONM2 records. The original files are unchanged.'] if missing else [])
