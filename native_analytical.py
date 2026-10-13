"""Saved workflows for the official engine's standalone aerodynamic math.

Only units, validation and presentation are handled here. Lifting-line,
airfoil transformations, pressure coefficients and flow integrals are native.
"""
import csv
import json
import math
from pathlib import Path


NAMES=('HersheyBarTheory','VKTAirfoilTheory','EllipsoidFlowTheory','AtmosphereReference','DragEquationReference')
LABELS={'HersheyBarTheory':'Rectangular wing · lift and drag',
        'VKTAirfoilTheory':'Analytical airfoil · profile and pressure',
        'EllipsoidFlowTheory':'Ellipsoid · pressure and flow integrals'}
DEFINITIONS={
 'HersheyBarTheory':(
  'OpenVSP lifting-line reference for a rectangular wing with unit chord. Returns local lift and induced-drag coefficients. This idealized reference does not model stall, viscosity, or the current aircraft.',
  [('NumPoints',1,80,'Points on each half-span (2–1000). The native solution uses a dense lifting-line system.'),
   ('AngleOfAttackDegrees',2,5.,'Angle of attack in degrees; converted to radians for the native API.'),
   ('FreestreamSpeed',2,100.,'Positive freestream speed in consistent length/time units.'),
   ('FullSpan',2,10.,'Full span in unit-chord lengths; numerically equals the aspect ratio of this reference wing.'),
   ('IncludeBothHalves',1,1,'0: one half-span; 1: native symmetric full-span distribution.')]),
 'VKTAirfoilTheory':(
  'OpenVSP von Kármán–Trefftz reference airfoil and inviscid pressure distribution. The native profile is normalized to unit chord. Shape parameters are analytical mapping parameters, not thickness/camber percentages of the current aircraft.',
  [('NumPoints',1,122,'Native perimeter samples (4–10000). Starts and closes at the trailing edge.'),
   ('AngleOfAttackDegrees',2,5.,'Angle of attack in degrees; the native profile is untwisted and Cp uses the specified incidence.'),
   ('ThicknessParameter',2,.1,'Nonnegative native epsilon thickness parameter. This is not t/c.'),
   ('CamberParameter',2,.1,'Native kappa camber parameter. This is not camber/chord.'),
   ('TrailingEdgeAngleDegrees',2,10.,'Trailing-edge angle in degrees (0 to less than 180). Zero gives a cusped Joukowski airfoil.')]),
 'EllipsoidFlowTheory':(
  'OpenVSP analytical potential-flow pressure on an axis-aligned ellipsoid and native flow integrals for all three axes. Pressure is evaluated in the centered native frame; display coordinates may use the chosen center. This is an idealized inviscid reference.',
  [('SemiAxisX',2,1.,'Positive semi-axis along X in consistent length units.'),
   ('SemiAxisY',2,2.,'Positive semi-axis along Y.'),('SemiAxisZ',2,3.,'Positive semi-axis along Z.'),
   ('Center',4,[0.,0.,0.],'Display center [X,Y,Z]. Translation does not change the centered pressure solution.'),
   ('FreestreamVelocity',4,[100.,0.,0.],'Nonzero freestream velocity [Vx,Vy,Vz] in consistent length/time units.'),
   ('NumPointsU',1,30,'Circumferential native samples (20–300).'),('NumPointsW',1,30,'Pole-to-pole native samples (20–300).')])}


def schema(v,name):
    if name in ('AtmosphereReference','DragEquationReference'):
        from native_reference_tables import schema as reference_schema
        return reference_schema(v,name)
    description,fields=DEFINITIONS[name]
    bounds={'NumPoints':(2,1000) if name=='HersheyBarTheory' else (4,10000),
            'FullSpan':(0,None),'FreestreamSpeed':(0,None),
            'ThicknessParameter':(0,None),'TrailingEdgeAngleDegrees':(0,None),
            'SemiAxisX':(0,None),'SemiAxisY':(0,None),'SemiAxisZ':(0,None),
            'NumPointsU':(20,300),'NumPointsW':(20,300)}
    entries=[]
    for n,t,value,doc in fields:
        e=dict(name=n,index=0,type=t,values=[value],editable=True,description=doc)
        if n in bounds:e.update(min=bounds[n][0],max=bounds[n][1])
        if n=='IncludeBothHalves':e['choices']=[dict(value=1,label='Both halves'),dict(value=0,label='One half')]
        entries.append(e)
    return dict(name=name,label=LABELS[name],description=description,standaloneNative=True,inputs=entries)


def inputs(v,req):
    from native_tools import finite
    spec=schema(v,req['name']);known={e['name']:e for e in spec['inputs']}
    seen=set()
    for item in req.get('inputs',[]):
        n=item.get('name');index=item.get('index',0);values=item.get('values')
        if n not in known or n in seen or index!=0:raise ValueError('Choose a known, unique reference input.')
        seen.add(n);e=known[n]
        if not isinstance(values,list) or len(values)!=1:raise ValueError(n+': enter one value.')
        if e['type']==v.VEC3D_DATA:
            value=values[0]
            if not isinstance(value,list) or len(value)!=3:raise ValueError(n+': enter [X,Y,Z].')
            for x in value:finite(x)
        else:
            value=finite(values[0])
            if e['type']==v.INT_DATA and not isinstance(value,int):raise ValueError(n+': enter an integer.')
        e['values']=values
    return spec,{n:e['values'][0] for n,e in known.items()}


def bounded(value,low,high,label):
    if not low<=value<=high:raise ValueError(f'{label} must be between {low} and {high}.')
    return value


def xyz(p):return [p.x(),p.y(),p.z()]


def result(v,name,columns,description):
    return dict(id='native-api-output',name=name,index=0,description=description,
                entries=[dict(name=n,index=0,type=v.DOUBLE_DATA,values=values,description=doc) for n,values,doc in columns])


def pressure_preview(nodes,cp,name):
    # Point elements associate each color with one native sample. No cell
    # interpolation, re-meshing, or derived pressure values are introduced.
    valid=[i for i,value in enumerate(cp) if math.isfinite(value)]
    if not valid:return None
    return dict(filename=name,nodes=nodes,nodeIDs=list(range(1,len(nodes)+1)),
                analyticalSamples=True,initialView='profile' if name.startswith('VKT') else '3d',
                elements=[dict(id=i+1,type='native analytical sample',kind='point',group=1,nodes=[i]) for i in valid],
                groups=[dict(id=1,name='Native analytical pressure samples',count=len(valid))],totalElements=len(valid),
                fields=[dict(name='Cp',label='Cp · native samples',values=[cp[i] for i in valid])],
                displayNote='Coordinates and Cp are native OpenVSP analytical outputs. Each displayed point is one exact returned sample. Undefined native pressure samples are omitted from coloring and retained as null in JSON and as undefined in the sample CSV.')


def write_csv(name,columns):
    path=Path.cwd()/(name+'.csv')
    with path.open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow([n for n,values,doc in columns])
        writer.writerows([[x if math.isfinite(x) else 'undefined' for x in row] for row in zip(*(values for n,values,doc in columns))])
    return path.name


def run(v,req):
    if req['name'] in ('AtmosphereReference','DragEquationReference'):
        from native_reference_tables import run as reference_run
        return reference_run(v,req)
    spec,p=inputs(v,req);name=req['name'];preview=None;functions=[]
    if name=='HersheyBarTheory':
        n=bounded(p['NumPoints'],2,1000,'Point count')
        if p['FreestreamSpeed']<=0 or p['FullSpan']<=0:raise ValueError('Use positive speed and full span.')
        flag=bounded(p['IncludeBothHalves'],0,1,'Both-halves flag');alpha=math.radians(p['AngleOfAttackDegrees'])
        functions=['GetHersheyBarLiftDist','GetHersheyBarDragDist']
        lift=list(v.GetHersheyBarLiftDist(n,alpha,p['FreestreamSpeed'],p['FullSpan'],bool(flag)))
        drag=list(v.GetHersheyBarDragDist(n,alpha,p['FreestreamSpeed'],p['FullSpan'],bool(flag)))
        columns=[('SpanStation',[q.x() for q in lift],'Native span station in unit-chord lengths.'),
                 ('cl',[q.y() for q in lift],'Native local coefficient of lift.'),
                 ('cdi',[q.y() for q in drag],'Native local coefficient of induced drag.')]
    elif name=='VKTAirfoilTheory':
        n=bounded(p['NumPoints'],4,10000,'Point count')
        if p['ThicknessParameter']<0:raise ValueError('Use a nonnegative thickness parameter.')
        if not 0<=p['TrailingEdgeAngleDegrees']<180:raise ValueError('Use a trailing-edge angle from 0 to less than 180 degrees.')
        alpha=math.radians(p['AngleOfAttackDegrees']);tau=math.radians(p['TrailingEdgeAngleDegrees'])
        functions=['GetVKTAirfoilPnts','GetVKTAirfoilCpDist']
        points=v.GetVKTAirfoilPnts(n,alpha,p['ThicknessParameter'],p['CamberParameter'],tau)
        cp=list(v.GetVKTAirfoilCpDist(alpha,p['ThicknessParameter'],p['CamberParameter'],tau,points));nodes=[xyz(q) for q in points]
        columns=[('X_Loc',[q[0] for q in nodes],'Native unit-chord X coordinate.'),('Y_Loc',[q[1] for q in nodes],'Native unit-chord airfoil ordinate.'),
                 ('Z_Loc',[q[2] for q in nodes],'Native Z coordinate.'),('Cp',cp,'Native potential-flow pressure coefficient; null means undefined at this sample.')]
        preview=pressure_preview(nodes,cp,'VKT analytical airfoil')
    elif name=='EllipsoidFlowTheory':
        radii=[p['SemiAxis'+a] for a in 'XYZ']
        if min(radii)<=0:raise ValueError('All semi-axis lengths must be positive.')
        if all(x==0 for x in p['FreestreamVelocity']):raise ValueError('Enter a nonzero freestream velocity vector.')
        u=bounded(p['NumPointsU'],20,300,'U sample count');w=bounded(p['NumPointsW'],20,300,'W sample count')
        abc=v.vec3d(*radii);functions=['GetEllipsoidSurfPnts','GetEllipsoidCpDist','IntegrateEllipsoidFlow']
        local=v.GetEllipsoidSurfPnts(v.vec3d(0,0,0),abc,u,w)
        points=v.GetEllipsoidSurfPnts(v.vec3d(*p['Center']),abc,u,w)
        cp=list(v.GetEllipsoidCpDist(local,abc,v.vec3d(*p['FreestreamVelocity'])));nodes=[xyz(q) for q in points]
        columns=[('X_Loc',[q[0] for q in nodes],'Native translated X coordinate.'),('Y_Loc',[q[1] for q in nodes],'Native translated Y coordinate.'),
                 ('Z_Loc',[q[2] for q in nodes],'Native translated Z coordinate.'),('Cp',cp,'Native centered potential-flow pressure coefficient.')]
        integrals=[v.IntegrateEllipsoidFlow(abc,i) for i in range(3)]
        preview=pressure_preview(nodes,cp,'Ellipsoid analytical pressure')
    else:raise ValueError('Unknown native analytical workflow.')
    if not columns or not columns[0][1] or len({len(values) for n,values,doc in columns})!=1:raise ValueError('OpenVSP returned incomplete reference samples.')
    if any(not math.isfinite(x) for n,values,doc in columns if n!='Cp' for x in values):raise ValueError('OpenVSP returned undefined geometry or reference values. Adjust the inputs.')
    output=[result(v,name,columns,spec['description'])]
    if name=='EllipsoidFlowTheory':output.append(result(v,'EllipsoidFlowIntegrals',[('Axis',[0,1,2],'0=X, 1=Y, 2=Z.'),('Integral',integrals,'Native IntegrateEllipsoidFlow output along each axis.')],spec['description']))
    csv_name=write_csv(name,columns)
    undefined=sum(not math.isfinite(x) for r in output for e in r['entries'] for x in e['values'])
    data=dict(version=v.GetVSPVersion(),analysis=name,resultID=None,engineOperation=', '.join(functions),nativeFunctions=functions,
              standaloneNative=True,description=spec['description'],inputs=spec['inputs'],geometryInputs=[],results=output,
              csvFile=csv_name,undefinedSamples=undefined)
    if name=='VKTAirfoilTheory':
        # Serialize the exact native coordinates in Selig order; the C++
        # WriteSeligAirfoilFile helper is not exposed by this Python binding.
        path=Path.cwd()/'VKT-reference.dat'
        path.write_text('OpenVSP VKT reference · native samples\n'+''.join(f'{x:.17g} {y:.17g}\n' for x,y,z in nodes))
        data['airfoilFile']=path.name
    if preview:
        path=Path.cwd()/'reference.theory.json';path.write_text(json.dumps(preview,allow_nan=False));data['theoryFile']=path.name
    return data
