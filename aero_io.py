"""Decode native VSPAERO display data, without evaluating aerodynamic equations.

Record layout verified against OpenVSP_3.52.2/src/vsp_aero/Viewer/glviewer.C
(LoadMeshData, UpdateMeshData, LoadSolutionData), RotorDisk.C and EngineFace.C.
Pressure remains on native triangles; no smoothing or nodal reconstruction.
"""
import math
import mmap
from pathlib import Path
import struct

MAGIC = {-123789456: 2, -123789453: 3}
LIMIT = 1_000_000


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0
        if len(data) < 4:
            raise ValueError('Truncated VSPAERO database.')
        self.endian = next((e for e in ('<', '>') if struct.unpack_from(e+'i', data)[0] in MAGIC), None)
        if not self.endian:
            raise ValueError('Unsupported VSPAERO database version.')
        self.version = MAGIC[self.take('i')[0]]

    def skip(self, size):
        if size < 0 or self.pos + size > len(self.data):
            raise ValueError('Truncated VSPAERO database.')
        start = self.pos
        self.pos += size
        return start

    def take(self, fmt):
        size = struct.calcsize(self.endian+fmt)
        values = struct.unpack_from(self.endian+fmt, self.data, self.skip(size))
        if any(isinstance(x, float) and not math.isfinite(x) for x in values):
            raise ValueError('Non-finite native aerodynamic data.')
        return values

    def count(self, maximum=LIMIT):
        value = self.take('i')[0]
        if not 0 <= value <= maximum:
            raise ValueError('Invalid or excessively large VSPAERO record count.')
        return value

    def records(self, fmt, count):
        size = struct.calcsize(self.endian+fmt)*count
        start = self.skip(size)
        records = list(struct.iter_unpack(self.endian+fmt, self.data[start:start+size]))
        if any(not math.isfinite(x) for row in records for x in row if isinstance(x, float)):
            raise ValueError('Non-finite native aerodynamic data.')
        return records


def case_list(path):
    sidecar = Path(str(path)+'.cases')
    if sidecar.is_symlink() or not sidecar.is_file() or sidecar.stat().st_size > 10_000_000:
        raise ValueError('The native case list is missing or exceeds the preview limit.')
    cases = []
    for line in sidecar.read_text().splitlines():
        fields = line.split(maxsplit=3)
        if len(fields) < 3:
            raise ValueError('Invalid native aerodynamic case list.')
        mach, alpha, beta = map(float, fields[:3])
        if not all(math.isfinite(x) for x in (mach, alpha, beta)):
            raise ValueError('Invalid native aerodynamic case conditions.')
        cases.append(dict(index=len(cases)+1, mach=mach, alpha=alpha, beta=beta,
                          label=fields[3].strip() if len(fields)>3 else ''))
    if not cases or len(cases) > 10000:
        raise ValueError('Invalid native aerodynamic case count.')
    return cases


def mesh_record(reader, nodes_count, triangles_count, keep):
    triangles = reader.records('6if', triangles_count) if keep else None
    if not keep:
        reader.skip(28*triangles_count)
    nodes = reader.records('3f', nodes_count) if keep else None
    if not keep:
        reader.skip(12*nodes_count)
    rotors = reader.count(10000)
    nozzles = reader.count(10000) if reader.version == 3 else 0
    reader.skip(rotors*11*8 + nozzles*7*8)
    for _ in range(reader.count(100)):
        coarse_nodes, edges = reader.count(), reader.count()
        reader.skip(coarse_nodes*12 + edges*16)
    reader.skip(reader.count()*4)  # Kutta edges
    reader.skip(reader.count()*4)  # Kutta nodes
    controls_count = reader.count(10000)
    controls = []
    for _ in range(controls_count):
        n = reader.count()
        if keep:
            points = reader.records('3f', n)
            hinge = reader.records('3f', 3)
            controls.append(dict(points=points, hinge=hinge[:2]))
        else:
            reader.skip(n*12+36)
        reader.skip(reader.count()*4)
    return nodes, triangles, controls, controls_count


def read_adb(path, case=1):
    path = Path(path)
    cases = case_list(path)
    if isinstance(case, bool) or not isinstance(case, int) or not 1 <= case <= len(cases):
        raise ValueError('Choose a case from the native solution list.')
    if path.stat().st_size > 2_000_000_000:
        raise ValueError('This database exceeds the 2 GB preview limit. Download the native file.')
    with path.open('rb') as stream:
        if path.stat().st_size < 60:
            raise ValueError('Truncated VSPAERO database.')
        with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            r = Reader(data)
            model_type, symmetry, unsteady = r.take('3i')
            loops, nodes_count, triangles_count, edges = [r.count() for _ in range(4)]
            references = r.take('6f')
            names = {}
            for _ in range(r.count(100000)):
                surface = r.take('i')[0]
                start = r.skip(100)
                label = data[start:start+100].split(b'\0',1)[0].decode('utf-8', errors='replace')
                component = r.take('i')[0]
                names[surface] = dict(name=label, component=component)
            for index in range(1, case+1):
                keep = index == case
                nodes, triangles, controls, controls_count = mesh_record(r, nodes_count, triangles_count, keep)
                mach, alpha, beta, cp_min, cp_max = r.take('5f')
                r.skip(loops*40 + edges*24)  # Native circulation, edge forces and velocities
                values = r.records('3f', triangles_count) if keep else None
                if not keep:
                    r.skip(triangles_count*12)
                wakes = []
                for _ in range(r.count()):
                    kutta_node = r.take('i')[0]
                    span = r.take('d')[0]
                    count = r.count()
                    if keep:
                        wakes.append(dict(node=kutta_node, span=span, points=r.records('3d', count)))
                    else:
                        r.skip(count*24)
                deflections = r.take(str(controls_count)+'f')
            elements = []
            for i, row in enumerate(triangles):
                n1, n2, n3, component, surface, valid_from, area = row
                if any(not 1 <= n <= nodes_count for n in (n1, n2, n3)):
                    raise ValueError('Invalid native aerodynamic triangle connectivity.')
                elements.append(dict(id=i+1, type=2, kind='face', group=surface, component=component,
                                     nodes=[n1-1,n2-1,n3-1], area=area, validFrom=valid_from, order=1))
            groups = [dict(id=g, name=names.get(g,{}).get('name','Wake mesh' if g==0 else f'Surface {g}'),
                           count=sum(e['group']==g for e in elements)) for g in sorted({e['group'] for e in elements})]
            # ADB conditions store angles in radians; the text case list stores degrees.
            conditions = dict(mach=mach, alpha=math.degrees(alpha), beta=math.degrees(beta))
            return dict(filename=path.name, version=r.version, modelType=model_type, symmetry=symmetry,
                        unsteady=bool(unsteady), references=dict(zip(('Sref','Cref','Bref','Xcg','Ycg','Zcg'),references)),
                        cases=cases, case=case, conditions=conditions, nodes=nodes, nodeIDs=list(range(1,nodes_count+1)),
                        elements=elements, groups=groups, totalElements=triangles_count, unsupportedElements=0,
                        higherOrder=False, wakes=wakes, controls=controls, deflections=deflections,
                        solverRange=[cp_min,cp_max], pressureLabel='ΔCp' if model_type==1 else 'Cp',
                        fields=[dict(name='Pressure',label='ΔCp' if model_type==1 else 'Cp',values=[x[0] for x in values]),
                                dict(name='Unsteady pressure',label='Unsteady Cp',values=[x[1] for x in values]),
                                dict(name='Vorticity',label='Γ',values=[x[2] for x in values])])


def read_flow_plane(path):
    path = Path(path)
    if path.stat().st_size > 150_000_000:
        raise ValueError('Flow plane exceeds the 150 MB preview limit.')
    rows = iter(path.read_text().splitlines())
    try:
        direction, location, reference, velocity_scale = map(float, next(rows).split())
        count, cells = map(int, next(rows).split())
        if not 0 < count <= LIMIT or not 0 < cells <= LIMIT:
            raise ValueError('Invalid native flow plane counts.')
        nodes, ids, velocities, pressure, lookup = [], [], [], [], {}
        for _ in range(count):
            row = next(rows).split()
            if len(row)!=8:
                raise ValueError('Invalid native flow plane node.')
            nid = int(row[0]); values = list(map(float,row[1:]))
            if nid in lookup or not all(math.isfinite(x) for x in values):
                raise ValueError('Invalid native flow plane node.')
            lookup[nid]=len(nodes);ids.append(nid);nodes.append(values[:3]);velocities.append(values[3:6]);pressure.append(values[6])
        elements=[]
        for _ in range(cells):
            row=list(map(int,next(rows).split()))
            if len(row)!=5 or any(n not in lookup for n in row[1:]):
                raise ValueError('Invalid native flow plane connectivity.')
            elements.append(dict(id=row[0],type=3,kind='face',group=0,nodes=[lookup[n] for n in row[1:]],order=1))
    except (StopIteration, OverflowError) as exc:
        raise ValueError('Truncated native flow plane.') from exc
    if not all(math.isfinite(x) for x in (direction,location,reference,velocity_scale)):
        raise ValueError('Invalid native flow plane header.')
    # Average only for flat cell colouring. All original nodal samples remain available.
    fields=[]
    for label, samples in [('Cp',pressure),('Speed',[math.hypot(*p) for p in velocities]),
                           ('U',[p[0] for p in velocities]),('V',[p[1] for p in velocities]),('W',[p[2] for p in velocities])]:
        fields.append(dict(name=label,label=label,values=[sum(samples[n] for n in e['nodes'])/4 for e in elements],nodeValues=samples))
    return dict(filename=path.name,nodes=nodes,nodeIDs=ids,elements=elements,totalElements=cells,
                groups=[dict(id=0,name='Native flow plane',count=cells)],higherOrder=False,unsupportedElements=0,
                fields=fields,velocities=velocities,direction=direction,location=location,referenceSpeed=reference,solverVelocityScale=velocity_scale,
                displayNote='Colours show cell averages of native nodal samples. Click a cell to inspect its original node values.')
