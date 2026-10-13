"""Original native tire/suspension inputs and temporary native inspection geometry."""
INSPECTION_NAME='Tire and suspension inspection'
LABELS={'DrimMode':'Rim diameter driver','DrimIn':'Rim diameter (inches)','DrimModel':'Rim diameter (model units)','DrimFrac':'Rim diameter / tire diameter',
 'WrimMode':'Rim width driver','WrimIn':'Rim width between flanges (inches)','WrimModel':'Rim width between flanges (model units)','WrimFrac':'Rim width / tire width',
 'WsMode':'Shoulder width driver','WsIn':'Shoulder width (inches)','WsModel':'Shoulder width (model units)','WsFrac':'Shoulder width / tire width',
 'HsMode':'Shoulder height driver','HsIn':'Shoulder height (inches)','HsModel':'Shoulder height (model units)','HsFrac':'Shoulder height / tire section height',
 'PlyRating':'Tire ply rating','SpeedRating':'Tire speed rating (mph)',
 'DFlangeModel':'Flange diameter (model units)','WGModel':'Grown tire width (model units)','DGModel':'Grown tire diameter (model units)',
 'WsGModel':'Grown shoulder width (model units)','DsGModel':'Grown shoulder diameter (model units)',
 'TravelX':'Compression direction X','TravelY':'Compression direction Y','TravelZ':'Compression direction Z',
 'TravelCompressed':'Compression travel (model units)','TravelExtended':'Extension travel (model units)',
 'BogieThetaMin':'Minimum bogie pitch (degrees)','BogieThetaMax':'Maximum bogie pitch (degrees)','SteeringAngle':'Steering-angle limit (degrees)'}


def reasons(v,fields):
    result={}
    for prefix in ('Ws','Hs'):
        mode=int(v.GetParmVal(fields[prefix+'Mode']))
        # Installed 3.52.2 UpdateParms repeats the IN branch for MODEL.
        # Preserve the native mode and actual fraction driver; do not promise
        # an ineffective length edit or replace the engine's equations.
        driver='In' if mode==v.TIRE_DIM_IN else 'Frac'
        for suffix in ('In','Model','Frac'):
            if suffix!=driver:result[fields[prefix+suffix]]='Calculated by OpenVSP from the shoulder '+('inch dimension.' if driver=='In' else 'fraction. In OpenVSP 3.52.2 the model-unit shoulder mode also uses this fraction.')
    return result


def choices(v):
    result={}
    for prefix,label in [('Drim','Tire diameter'),('Wrim','Tire width'),('Ws','Tire width'),('Hs','Tire section height')]:
        result[prefix+'Mode']=[(v.TIRE_DIM_IN,'Inches'),(v.TIRE_DIM_MODEL,'Model units · native uses fraction' if prefix in ('Ws','Hs') else 'Model units'),(v.TIRE_DIM_FRAC,'Fraction of '+label.lower())]
    return result


def inspection_options(v):
    return dict(clearance=[dict(value=getattr(v,n),label=s) for n,s in [('TIRE_NOMINAL_CLEARANCE','Nominal tire'),('TIRE_GROWTH_CLEARANCE','Grown tire'),('TIRE_CLEARANCE','TRA clearance envelope')]],
                suspension=[dict(value=getattr(v,n),label=s) for n,s in [('GEAR_SUSPENSION_NOMINAL','Nominal'),('GEAR_SUSPENSION_COMPRESSED','Compressed'),('GEAR_SUSPENSION_EXTENDED','Extended')]],
                configuration=[dict(value=getattr(v,n),label=s) for n,s in [('GEAR_CONFIGURATION_DOWN','Down'),('GEAR_CONFIGURATION_UP','Up'),('GEAR_CONFIGURATION_INTERMEDIATE','Intermediate')]])


def selection(v,r):
    from native_tools import one,finite
    for key in ('mirror','clearance','suspension','configuration'):
        if key in r:finite(r[key])
    gid=one(r.get('geom'),[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='GEAR'],'Choose a landing gear.')
    bid=one(r.get('bogie'),v.GetAllBogies(gid),'Choose a wheel group in this landing gear.')
    mirror=one(r.get('mirror',0),[0,1] if v.GetParmVal(bid,'Symmetrical','Bogie') else [0],'Enable wheel-group mirroring before choosing its mirrored side.')
    clearance=one(r.get('clearance',v.TIRE_NOMINAL_CLEARANCE),[v.TIRE_NOMINAL_CLEARANCE,v.TIRE_GROWTH_CLEARANCE,v.TIRE_CLEARANCE],'Choose nominal, grown, or TRA clearance tires.')
    suspension=one(r.get('suspension',v.GEAR_SUSPENSION_NOMINAL),[v.GEAR_SUSPENSION_NOMINAL,v.GEAR_SUSPENSION_COMPRESSED,v.GEAR_SUSPENSION_EXTENDED],'Choose a native suspension position.')
    configuration=one(r.get('configuration',v.GEAR_CONFIGURATION_DOWN),[v.GEAR_CONFIGURATION_DOWN,v.GEAR_CONFIGURATION_UP,v.GEAR_CONFIGURATION_INTERMEDIATE],'Choose down, up, or intermediate gear.')
    fraction=finite(r.get('fraction',0))
    if not 0<=fraction<=1:raise ValueError('Use a retraction fraction from 0 to 1.')
    if configuration==v.GEAR_CONFIGURATION_INTERMEDIATE and v.GetParmVal(bid,'RetMode','Retract')!=v.GEAR_MECHANISM:raise ValueError('Choose the mechanism driver before inspecting intermediate retraction.')
    pitch=finite(r.get('pitch',0))
    if not -180<=pitch<=180:raise ValueError('Use a bogie pitch from -180 to 180 degrees.')
    return gid,bid,dict(mirror=mirror,clearance=clearance,suspension=suspension,configuration=configuration,fraction=fraction,pitch=pitch)


def create_inspection(v,r):
    gid,bid,settings=selection(v,r)
    aux=v.AddGeom('AUXILIARY',gid);v.SetGeomName(aux,INSPECTION_NAME)
    v.SetParmValUpdate(aux,'AuxiliaryGeomType','Design',v.AUX_GEOM_SINGLE_GEAR)
    v.SetAuxiliaryGeomContactPtID(aux,0,bid)
    mapping={'mirror':'ContactPt1_Isymm','clearance':'ContactPt1_ClearanceMode','suspension':'ContactPt1_SuspensionMode','configuration':'ContactPt1_GearMode','fraction':'ContactPt1_KRetract','pitch':'BogieTheta'}
    for key,name in mapping.items():v.SetParmValUpdate(aux,name,'Design',settings[key])
    v.Update();v.SetAuxiliaryGeomContactPtID(aux,0,bid);v.Update()
    return aux,gid,bid,settings,sample_surfaces(v,aux)


def sample_surfaces(v,aux):
    import math
    surfaces=[]
    for i in range(v.GetTotalNumSurfs(aux)):
        u,w=v.GetUWTess01(aux,i%max(1,v.GetNumMainSurfs(aux)))
        if len(u)<2 or len(w)<2:raise ValueError('OpenVSP returned a degenerate tire inspection. Check tire and rim dimensions.')
        points=v.CompVecPnt01(aux,i,[x for x in u for _ in w],[y for _ in u for y in w])
        xyz=[[p.x(),p.y(),p.z()] for p in points]
        if len(xyz)!=len(u)*len(w) or any(not math.isfinite(x) for p in xyz for x in p):raise ValueError('OpenVSP returned undefined tire inspection points. Check tire, rim and shoulder dimensions.')
        surfaces.append(dict(index=i,rows=len(u),cols=len(w),points=xyz))
    if not surfaces:raise ValueError('OpenVSP returned no tire inspection surfaces. Check the wheel-group setup.')
    return surfaces


def preview(v,r):
    aux,gid,bid,settings,surfaces=create_inspection(v,r)
    return dict(engine=v.GetVSPVersion(),geom=gid,bogie=bid,settings=settings,coordinateFrame='Native world XYZ',component=dict(id=aux,name=INSPECTION_NAME,mainSurfaceCount=v.GetNumMainSurfs(aux),surfaces=surfaces,paths=[],points=[],mesh=None),warnings=[])
