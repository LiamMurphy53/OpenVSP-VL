"""Names for original GeomEngine parameters; no flowpath geometry equations."""

CHOICES={
 'GeomIOType': [('ENGINE_GEOM_NONE','No flowpath'),('ENGINE_GEOM_INLET','Inlet'),
                ('ENGINE_GEOM_INLET_OUTLET','Inlet and outlet'),('ENGINE_GEOM_OUTLET','Outlet')],
 'GeomInType': [('ENGINE_GEOM_FLOWTHROUGH','Flow-through'),('ENGINE_GEOM_TO_LIP','To lip'),
                ('ENGINE_GEOM_FLOWPATH','Flowpath'),('ENGINE_GEOM_TO_FACE','To face')],
 'InletModeType': [('ENGINE_MODE_FLOWTHROUGH','Flow-through'),
    ('ENGINE_MODE_FLOWTHROUGH_NEG','Flow-through with negative flowpath'),
    ('ENGINE_MODE_FLOWTHROUGH_NEG_ONLY','Negative flowpath only'),
    ('ENGINE_MODE_TO_LIP','To lip'),('ENGINE_MODE_TO_FACE','To face'),
    ('ENGINE_MODE_TO_FACE_NEG','To face with negative flowpath'),
    ('ENGINE_MODE_TO_FACE_NEG_ONLY','Negative flowpath to face only'),
    ('ENGINE_MODE_EXTEND','Farfield extension')],
 'InletFaceMode':[('ENGINE_LOC_INDEX','Cross-section index'),('ENGINE_LOC_U','Surface U fraction')]
}
LABELS={'GeomIOType':'Flowpath component','GeomInType':'Modeled inlet geometry',
 'GeomOutType':'Modeled outlet geometry','InletModeType':'Inlet representation','OutletModeType':'Outlet representation',
 'EngineShowStationsFlag':'Show flowpath stations','RotExtensionFlag':'Rotate extensions',
 'ExtensionDistance':'Extension distance','AutoExtensionFlag':'Automatic extension distance',
 'AutoExtensionSet':'Extension reference geometry set'}
for end in ('Inlet','Outlet'):
 for location in ('Face','Lip'):
  for suffix,label in [('Mode','location basis'),('Index','cross-section'),('U','surface U fraction')]:
   LABELS[end+location+suffix]=end+' '+location.lower()+' '+label
ORDER=['GeomIOType','GeomInType','InletModeType','InletLipMode','InletLipIndex','InletLipU',
 'InletFaceMode','InletFaceIndex','InletFaceU','GeomOutType','OutletModeType',
 'OutletLipMode','OutletLipIndex','OutletLipU','OutletFaceMode','OutletFaceIndex','OutletFaceU',
 'AutoExtensionFlag','AutoExtensionSet','ExtensionDistance','RotExtensionFlag','EngineShowStationsFlag']


def owner(v,pid):
 if v.GetParmGroupName(pid)!='EngineModel':return None
 gid=v.GetParmContainer(pid)
 if gid not in v.FindGeoms() or v.GetGeomTypeName(gid).upper() not in ('FUSELAGE','STACK'):return None
 return gid


def annotate(v,p):
 gid=owner(v,p['id'])
 if not gid:return
 name=p['name'];p['label']=LABELS.get(name,name)
 if name in ORDER:p['presentationOrder']=ORDER.index(name)
 key='GeomInType' if name=='GeomOutType' else 'InletModeType' if name=='OutletModeType' else 'InletFaceMode' if name.endswith('Mode') else name
 if key in CHOICES:
  p['choices']=[dict(value=getattr(v,code),label=label) for code,label in CHOICES[key] if p['min']<=getattr(v,code)<=p['max']]
 elif name.endswith('Index'):
  p['choices']=[dict(value=i,label='Section '+str(i)) for i in range(v.GetNumXSec(v.GetXSecSurf(gid,0))) if p['min']<=i<=p['max']]
 elif name=='AutoExtensionSet':
  p['choices']=[dict(value=i,label=v.GetSetName(i)+' · '+str(i)) for i in range(v.GetNumSets()) if p['min']<=i<=p['max']]
  if p['value'] not in [c['value'] for c in p['choices']]:
   p['choices'].append(dict(value=p['value'],label='Unavailable saved geometry set · '+str(p['value'])))
 descriptions={
  'GeomIOType':'Identifies the flowpath portions already present in this body.',
  'GeomInType':'Describes the modeled inlet before flowpath processing.',
  'GeomOutType':'Describes the modeled outlet before flowpath processing.',
  'InletModeType':'Controls which native inlet surfaces are retained.',
  'OutletModeType':'Controls which native outlet surfaces are retained.',
  'AutoExtensionFlag':'Size extensions from the selected reference geometry set.',
  'AutoExtensionSet':'Geometry used for automatic extension distance.',
  'ExtensionDistance':'Used when automatic extension distance is off.',
  'RotExtensionFlag':'Used by farfield extension representations.',
  'EngineShowStationsFlag':'Saved visibility of native flowpath station guides.'}
 if name.endswith('Index'):p['description']='Section 0 is the first cross-section.'
 elif name.endswith('Mode'):p['description']='Choose a section index or normalized U coordinate.'
 elif name.endswith('U'):p['description']='Normalized body coordinate, from 0 to 1.'
 elif name in descriptions:p['description']=descriptions[name]
 if name=='ExtensionDistance':p['dimension']='length'


def groups(params):
 by_name={p['name']:p['id'] for p in params if p['rawGroup']=='EngineModel'}
 fields=[by_name[name] for name in ORDER if name in by_name]
 return [dict(title='Inlet & outlet flowpath',open=False,parameters=fields,
  note='Select the geometry already modeled by this body, then its flowpath representation. Face and lip locations use native section indices or surface U fractions. OpenVSP controls dependent settings and creates any negative flowpath or farfield extensions.')] if fields else []


def require_distinct_stations(v,gid,settings):
 """Reject coincident stations that leave a singular native flowpath surface."""
 value=lambda name:settings.get(name,v.GetParmVal(gid,name,'EngineModel'))
 if value('GeomIOType')!=v.ENGINE_GEOM_INLET_OUTLET:return
 locations=['InletFace','InletLip','OutletFace','OutletLip']
 modes=[value(n+'Mode') for n in locations]
 if len(set(modes))==1 and modes[0] in (v.ENGINE_LOC_INDEX,v.ENGINE_LOC_U):
  stations=[value(n+('Index' if modes[0]==v.ENGINE_LOC_INDEX else 'U')) for n in locations]
  if len(set(stations))==1:
   raise ValueError('The inlet and outlet stations coincide. Configure distinct flowpath locations together before enabling both. The edit was not saved.')


def validate_parameter(v,pid,value):
 gid=owner(v,pid)
 if gid:
  if v.GetParmName(pid)=='AutoExtensionSet' and value not in range(v.GetNumSets()):
   raise ValueError('Choose an existing flowpath extension reference set.')
  require_distinct_stations(v,gid,{v.GetParmName(pid):value})


def configure(v,request):
 from native_tools import finite
 gid=request['geom']
 if v.GetGeomTypeName(gid).upper() not in ('FUSELAGE','STACK'):raise ValueError('Choose a fuselage or stack flowpath.')
 settings=request.get('settings')
 if not isinstance(settings,dict) or not settings or set(settings)-set(ORDER):
  raise ValueError('Choose known native flowpath settings.')
 updates=[]
 for name,value in settings.items():
  value=finite(value);pid=v.FindParm(gid,name,'EngineModel')
  if not pid or v.GetParmType(pid) in (1,2,4,6) and int(value)!=value:
   raise ValueError('Use integer flowpath choices and section indices.')
  if not v.GetParmLowerLimit(pid)<=value<=v.GetParmUpperLimit(pid):
   raise ValueError('Use a flowpath setting within its native limits.')
  if name=='AutoExtensionSet' and value not in range(v.GetNumSets()):raise ValueError('Choose an existing flowpath extension reference set.')
  updates.append((pid,value))
 for end in ('InletFace','InletLip','OutletFace','OutletLip'):
  mode=settings.get(end+'Mode',v.GetParmVal(gid,end+'Mode','EngineModel'))
  if end+'U' in settings and mode!=v.ENGINE_LOC_U or end+'Index' in settings and mode!=v.ENGINE_LOC_INDEX:
   raise ValueError('Choose the matching section-index or U-fraction basis for each station.')
 require_distinct_stations(v,gid,settings)
 # Stage the native parameters before the existing transaction's single Update.
 # Inactive station inputs can become active when the role/basis changes.
 for pid,value in updates:v.SetParmVal(pid,value)
