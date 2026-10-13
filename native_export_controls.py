"""Native export settings and labels from the installed Vehicle exporters."""
GROUPS={'STEPSettings','IGESSettings','DXFSettings','SVGSettings','STLSettings','AirfoilExport'}
LABELS={'LenUnit':'File length units','Tolerance':'Point tolerance','SplitSurfs':'Split surfaces','SplitSubSurfs':'Split at surface regions',
        'MergePoints':'Merge coincident points','ToCubic':'Convert surfaces to cubic','ToCubicTol':'Cubic conversion tolerance',
        'TrimTE':'Trim trailing edges','MergeLETE':'Merge leading and trailing edges','ExportPropMainSurf':'Export propeller main surface',
        'LabelID':'Include component ID','LabelName':'Include component name','LabelSurfNo':'Include surface number',
        'LabelSplitNo':'Include split number','LabelAirfoilPart':'Include airfoil part','LabelDelim':'Label separator',
        'DimFlag':'Drawing dimensions','ViewType':'View layout','DXFProjectionFlag':'Include projection outlines','SVGProjectionFlag':'Include projection outlines',
        'DXFTessFactor':'Drawing tessellation factor','SVGTessFactor':'Drawing tessellation factor','DXFAllXSecFlag':'Include all cross-sections',
        'SVGAllXSecFlag':'Include all cross-sections','DXFColorFlag':'Color by component','Scale':'Scale-bar length',
        'AFWTessFactor':'Airfoil coordinate tessellation factor','AFAppendGeomIDFlag':'Append component ID to airfoil filenames',
        'AFExportType':'Airfoil coordinate format','MultiSolid':'Separate STL solids'}


def annotate(v,p):
    group=p['rawGroup'];name=p['name']
    if group not in GROUPS:return
    base=name.removeprefix('Structure')
    if base in LABELS:p['label']=LABELS[base]
    if group=='SVGSettings' and name=='LenUnit':p['label']='Scale-bar units (coordinates unchanged)'
    if group=='DXFSettings' and name=='LenUnit':p['label']='DXF header units (coordinates unchanged)'
    choices=[]
    if name=='LenUnit':choices=[(n,l) for n,l in [('LEN_MM','mm'),('LEN_CM','cm'),('LEN_M','m'),('LEN_IN','in'),('LEN_FT','ft'),('LEN_YD','yd'),('LEN_UNITLESS','Unitless')]]
    elif base=='LabelDelim':choices=[('DELIM_COMMA','Comma'),('DELIM_USCORE','Underscore'),('DELIM_SPACE','Space'),('DELIM_NONE','None')]
    elif name=='DimFlag':choices=[('SET_3D','3D geometry'),('SET_2D','2D drawing')]
    elif name=='ViewType':choices=[('VIEW_1','One view'),('VIEW_2HOR','Two views · horizontal'),('VIEW_2VER','Two views · vertical'),('VIEW_4','Four views')]
    elif name.endswith('View'):
        p['label']=name.removesuffix('View').replace('TopLeft','Top left').replace('TopRight','Top right').replace('BottomLeft','Bottom left').replace('BottomRight','Bottom right')+' view'
        choices=[('VIEW_LEFT','Left'),('VIEW_RIGHT','Right'),('VIEW_TOP','Top'),('VIEW_BOTTOM','Bottom'),('VIEW_FRONT','Front'),('VIEW_REAR','Rear'),('VIEW_NONE','None')]
    elif name.endswith('Rotation'):
        p['label']=name.removesuffix('Rotation').replace('TopLeft','Top left').replace('TopRight','Top right').replace('BottomLeft','Bottom left').replace('BottomRight','Bottom right')+' rotation'
        choices=[('ROT_0','0°'),('ROT_90','90°'),('ROT_180','180°'),('ROT_270','270°')]
    elif name=='AFExportType':choices=[('SELIG_AF_EXPORT','Selig coordinates'),('BEZIER_AF_EXPORT','Bezier curves')]
    why=reason(v,p['id'])
    if why:p.update(active=False,editable=False,readOnly=True,readOnlyReason=why)
    if choices:p['choices']=[dict(value=getattr(v,n),label=l) for n,l in choices if hasattr(v,n) and p['min']<=getattr(v,n)<=p['max']]


def configuration(v):
    ids={(v.GetParmGroupName(p),v.GetParmName(p)):p for p in v.FindContainerParmIDs(v.GetVehicleID())}
    guides={}
    def section(group,title,names):return dict(title=title,parameters=[ids[(group,n)] for n in names if (group,n) in ids])
    for fmt,group in [('STEP','STEPSettings'),('IGES','IGESSettings'),('STEP_STRUCTURE','STEPSettings'),('IGES_STRUCTURE','IGESSettings')]:
        prefix='Structure' if fmt.endswith('_STRUCTURE') else ''
        names=lambda values:[prefix+n for n in values]
        sections=[section(group,'Units and surface preparation',['LenUnit']+names(['Tolerance','SplitSurfs','SplitSubSurfs','MergePoints','ToCubic','ToCubicTol'])),
                  section(group,'Surface labels',names(['LabelName','LabelID','LabelSurfNo','LabelSplitNo','LabelAirfoilPart','LabelDelim']))]
        if not prefix:sections.append(section(group,'Edges and propellers',['TrimTE','MergeLETE','ExportPropMainSurf']))
        guides[fmt]=dict(sections=sections,note='These original CAD settings are saved in the aircraft. File units and tolerances belong to the native exporter; workspace display units do not change them. Cubic conversion tolerance is used when cubic conversion is enabled.')
    for fmt in ('DXF','SVG'):
        group=fmt+'Settings';layout=v.GetParmVal(ids[(group,'ViewType')])
        positions=['TopLeft'] if layout==v.VIEW_1 else ['TopLeft','TopRight'] if layout==v.VIEW_2HOR else ['TopLeft','BottomLeft'] if layout==v.VIEW_2VER else ['TopLeft','TopRight','BottomLeft','BottomRight']
        if fmt=='DXF' and v.GetParmVal(ids[(group,'DimFlag')])!=v.SET_2D:positions=[]
        sections=[section(group,'Drawing setup',['LenUnit','DimFlag','ViewType','Scale',fmt+'ProjectionFlag',fmt+'TessFactor',fmt+'AllXSecFlag',fmt+'ColorFlag']),
                  section(group,'Drawing views',[pos+suffix for pos in positions for suffix in ('View','Rotation')])]
        guides[fmt]=dict(sections=sections,note='OpenVSP generates the drawing and projection outlines. SVG scale-bar units and DXF header units label native coordinates without rescaling them. DXF view layout applies to 2D drawings. Tessellation controls drawing sampling.')
    guides['STL']=dict(sections=[section('STLSettings','STL mesh options',['MultiSolid','ExportPropMainSurf'])],note='The native exporter supplies the mesh triangles. STL has no file unit metadata; use consistent native model units in the receiving application.')
    for fmt in ('SELIG_AIRFOILS','BEZIER_AIRFOILS'):
        guides[fmt]=dict(sections=[section('AirfoilExport','Airfoil files',['AFWTessFactor','AFAppendGeomIDFlag'])],note='The selected export format chooses Selig or Bezier output. OpenVSP generates the coordinate files and companion metadata; these sampling and filename settings persist in the aircraft.')
    return guides


def study_metadata(v):
    ids={(v.GetParmGroupName(p),v.GetParmName(p)):p for p in v.FindContainerParmIDs(v.GetVehicleID())};out={}
    def condition(group,name,values):return dict(parameter=ids[(group,name)],values=values,label=LABELS.get(name,name))
    for group in ('STEPSettings','IGESSettings'):
        for prefix in ('','Structure'):
            key=(group,prefix+'ToCubicTol')
            if key in ids:out[ids[key]]=dict(conditions=[condition(group,prefix+'ToCubic',[1])],limitControllers=[])
    for group in ('DXFSettings','SVGSettings'):
        dimensional=[condition(group,'DimFlag',[v.SET_2D])] if group=='DXFSettings' else []
        if dimensional:out[ids[(group,'ViewType')]]=dict(conditions=dimensional,limitControllers=[])
        layouts={'TopLeft':[v.VIEW_1,v.VIEW_2HOR,v.VIEW_2VER,v.VIEW_4],'TopRight':[v.VIEW_2HOR,v.VIEW_4],'BottomLeft':[v.VIEW_2VER,v.VIEW_4],'BottomRight':[v.VIEW_4]}
        for position,values in layouts.items():
            for suffix in ('View','Rotation'):
                conditions=dimensional+[condition(group,'ViewType',values)]
                if suffix=='Rotation':conditions+=[condition(group,position+'View',[value for value in range(v.VIEW_LEFT,v.VIEW_NONE) if value!=v.VIEW_NONE])]
                out[ids[(group,position+suffix)]]=dict(conditions=conditions,limitControllers=[])
    return out


def reason(v,pid):
    if v.GetParmGroupName(pid) not in GROUPS:return ''
    data=study_metadata(v).get(pid)
    if data and any(v.GetParmVal(c['parameter']) not in c['values'] for c in data['conditions']):return 'Unused with the saved export conversion, drawing dimensions, layout or view selection.'
    return ''


def validate_parameter(v,pid):
    why=reason(v,pid)
    if why:raise ValueError(why)


def study_priority(v,pid):
    group=v.GetParmGroupName(pid);name=v.GetParmName(pid)
    if group not in GROUPS:return None
    if name in ('DimFlag','ToCubic','StructureToCubic'):return -15
    if name=='ViewType':return -14
    if name.endswith('View'):return -13
    return 40
