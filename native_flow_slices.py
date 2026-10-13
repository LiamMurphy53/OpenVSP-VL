"""Original native saved-database interrogation, preserving solved flight setup."""
import math,re
from pathlib import Path

NAME='FlowPlaneSlicer'


def schema(v):
    fields=[dict(name=a+'SlicePosVec',index=0,type=v.DOUBLE_DATA,values=[2.] if a=='Y' else [],editable=True,numericList=True,label=a+' plane positions',description='Comma-separated coordinates in the saved solution’s native model units.') for a in 'XYZ']
    cid=v.FindContainer('VSPAEROSettings',0);pid=v.FindParm(cid,'QuadTreeBufferLevels','VSPAERO')
    fields.append(dict(name='QuadTreeBufferLevels',index=0,type=v.INT_DATA,values=[0],editable=True,label='Flow-plane buffer levels',min=v.GetParmLowerLimit(pid),max=v.GetParmUpperLimit(pid),description=v.GetParmDescript(pid)))
    note='Compute new airflow planes from a completed saved native pressure database. The original solver interrogates the saved solution; it does not solve new flight conditions. Positions use that solution’s native coordinate units.'
    return dict(name=NAME,label='Airflow planes from a saved solution',description=note,inputs=fields,engineOperation='VSPAERO::RestartAndInterrogateSolution (saved-reader repair)',guide=dict(title='Airflow planes from a saved solution',note=note,sensitivityNote='Compare buffer levels and plane positions. The underlying aerodynamic solution and its convergence remain those of the selected source run.',sections=[dict(title='Native cutting planes',inputs=[e['name'] for e in fields])]))


def inputs(v,req):
    spec=schema(v);known={e['name']:e for e in spec['inputs']};seen=set()
    for e in req.get('inputs',[]):
        n=e.get('name');values=e.get('values')
        if n not in known or n in seen or e.get('index',0)!=0:raise ValueError('Choose unique native flow-plane inputs.')
        seen.add(n)
        if not isinstance(values,list) or len(values)>10000 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in values):raise ValueError('Enter finite native plane coordinates.')
        known[n]['values']=values
    validate(v,spec)
    return spec


def validate(v,spec):
    values={e['name']:e['values'] for e in spec['inputs']}
    positions=[p for a in 'XYZ' for p in values[a+'SlicePosVec']]
    if not positions:raise ValueError('Enter at least one airflow-plane position.')
    if any(not math.isfinite(p) or not -1e12<=p<=1e12 for p in positions):raise ValueError('Plane coordinates are outside native limits.')
    level=values['QuadTreeBufferLevels']
    if len(level)!=1 or isinstance(level[0],bool) or not isinstance(level[0],(int,float)) or not math.isfinite(level[0]) or int(level[0])!=level[0] or not 0<=level[0]<=100:raise ValueError('Buffer levels must be a native integer from 0 to 100.')


def rewrite_planes(path,planes,level):
    """Change only the original solver's plane records, retaining every other byte."""
    text=path.read_text();pattern=r'^NumberOfQuadTrees\s*=\s*(\d+)[^\n]*\n'
    match=re.search(pattern,text,re.M)
    block='NumberOfQuadTrees = '+str(len(planes))+' \n'+''.join(f'{i+1} {axis+1} {position:.17g} \n' for i,(axis,position) in enumerate(planes))
    if match:
        end=match.end()
        for _ in range(int(match[1])):
            newline=text.find('\n',end)
            if newline<0:raise ValueError('The saved native cutting-plane block is incomplete.')
            if not re.fullmatch(r'\s*\d+\s+[123]\s+\S+\s*',text[end:newline]):raise ValueError('The saved native cutting-plane record is invalid.')
            end=newline+1
        text=text[:match.start()]+block+text[end:]
    else:
        marker=re.search(r'^NumberOfInlets\s*=',text,re.M)
        if not marker:raise ValueError('The saved native setup has no cutting-plane insertion point.')
        text=text[:marker.start()]+block+text[marker.start():]
    buffer='QuadTreeBufferLevels = '+str(int(level))+' \n'
    if re.search(r'^QuadTreeBufferLevels\s*=',text,re.M):text=re.sub(r'^QuadTreeBufferLevels\s*=[^\n]*\n',buffer,text,flags=re.M)
    else:text=text.replace(block,buffer+block,1)
    path.write_text(text)


def run(v,req):
    spec=inputs(v,req);values={e['name']:e['values'] for e in spec['inputs']}
    root=Path.cwd();setups=list(root.glob('*.vspaero'));adbs=list(root.glob('*.adb'))
    if len(setups)!=1 or len(adbs)!=1:raise ValueError('Choose a saved solution with its original solver setup and pressure database.')
    from native_run_setup import save
    save(v,NAME,spec['inputs'],engineOperation=spec['engineOperation'],sourceRun=req.get('sourceRun'))
    planes=[(getattr(v,a+'_DIR'),p) for a in 'XYZ' for p in values[a+'SlicePosVec']]
    import native_solver_setup
    written=native_solver_setup.read(root)
    fields={e['name']:e['value'] for e in written['fields']}
    rewrite_planes(setups[0],planes,values['QuadTreeBufferLevels'][0])
    # Read the database's original time-accuracy flag rather than inferring a
    # reversed manager flag from propeller mode. Never rewrite the source ADB.
    from aero_io import Reader
    with adbs[0].open('rb') as stream:header=Reader(stream.read(60))
    model_type,symmetry,unsteady=header.take('3i')
    if unsteady not in (0,1):raise ValueError('The saved native time-accuracy flag is invalid.')
    import native_flow_reader
    provenance=native_flow_reader.run(v,setups[0],bool(unsteady),int(fields.get('VSP_StabilityType','0')))
    files=sorted(root.glob('*.case.*.quad.*.dat'))
    if not files:raise ValueError('The original solver produced no airflow planes. Inspect its saved run log.')
    from aero_io import read_flow_plane
    summaries=[]
    for path in files:
        mesh=read_flow_plane(path)
        summaries.append(dict(file=path.name,direction=mesh['direction'],position=mesh['location'],nodes=len(mesh['nodes']),elements=len(mesh['elements'])))
    from aero_io import case_list
    cases=case_list(adbs[0])
    records={case['index']:case for case in cases}
    expected={(case['index'],i+1,axis+1,float(position)) for case in cases for i,(axis,position) in enumerate(planes)}
    actual=set()
    for item in summaries:
        match=re.fullmatch(r'.+\.case\.(-?\d+)\.quad\.(\d+)\.dat',item['file'])
        record=abs(int(match[1]))
        actual.add((record,int(match[2]),int(item['direction']),float(item['position'])))
        if record in records:
            item.update(solutionRecord=record,solutionLabel=records[record]['label'],timeAccurate=bool(unsteady))
    if actual!=expected:
        raise ValueError('The original saved-database reader did not return every requested case and plane. Review the native log; these partial files are not a completed airflow result.')
    return dict(version=v.GetVSPVersion(),analysis=NAME,engineOperation=spec['engineOperation'],inputs=spec['inputs'],geometryInputs=[],results=[],flowPlanes=summaries,solverSetup=native_solver_setup.read(root),readerProvenance=provenance)
