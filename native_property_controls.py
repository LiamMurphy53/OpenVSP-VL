"""Structural property guidance; section calculations remain in FeaProperty Update."""
LABELS={'FeaPropertyType':'Property model','CrossSectType':'Beam cross-section','LengthUnit':'Property length units','Thickness':'Shell thickness','CrossSecArea':'Cross-sectional area','Izz':'Bending inertia Izz','Iyy':'Bending inertia Iyy','Izy':'Product of inertia Izy','Ixx':'Torsional constant J'}
SECTIONS=[('FEA_XSEC_GENERAL','General · entered section properties',[]),('FEA_XSEC_CIRC','Solid circular',['Radius']),('FEA_XSEC_PIPE','Circular tube',['Outer radius','Inner radius']),('FEA_XSEC_I','I-section',['Total height','Flange A width','Flange B width','Web thickness','Flange A thickness','Flange B thickness']),('FEA_XSEC_RECT','Solid rectangular',['Width','Height']),('FEA_XSEC_BOX','Rectangular box',['Outer width','Outer height','Horizontal wall thickness','Vertical wall thickness'])]


def reason(v,pid,refs=None):
    if v.GetParmGroupName(pid)!='FeaProperty':return ''
    name=v.GetParmName(pid);owner=v.GetParmContainer(pid)
    if name=='FeaMaterialIndex':return 'Deprecated legacy material index. Use the saved native material-ID picker.'
    if name.endswith('_FEM'):return 'Calculated by OpenVSP in structural solver units.'
    if name in ('CrossSecArea','Izz','Iyy','Izy','Ixx') and v.GetParmVal(v.FindParm(owner,'FeaPropertyType','FeaProperty'))==v.FEA_BEAM and v.GetParmVal(v.FindParm(owner,'CrossSectType','FeaProperty'))!=v.FEA_XSEC_GENERAL:return 'Calculated by OpenVSP from the chosen beam cross-section dimensions.'
    if name in ('Thickness','LengthUnit') and refs is not None:
        material=refs.get(owner,{}).get('FeaMaterialID','')
        if material in v.GetFeaMaterialIDVec() and v.GetParmVal(v.FindParm(material,'FeaMaterialType','FeaMaterial'))==v.FEA_LAMINATE:return 'OpenVSP takes thickness and length units from the assigned laminate material.'
    return ''


def annotate(v,p,refs=None):
    if p['rawGroup']!='FeaProperty':return
    name=p['name'];base=name.removesuffix('_FEM');p['label']=LABELS.get(base,base)+(' · solver units' if name.endswith('_FEM') else '')
    if name=='FeaPropertyType':p['choices']=[dict(value=v.FEA_SHELL,label='Shell'),dict(value=v.FEA_BEAM,label='Beam')]
    elif name=='CrossSectType':p['choices']=[dict(value=getattr(v,n),label=l) for n,l,_ in SECTIONS]
    elif name=='LengthUnit':p['choices']=[dict(value=getattr(v,n),label=l) for n,l in [('LEN_MM','mm'),('LEN_CM','cm'),('LEN_M','m'),('LEN_IN','in'),('LEN_FT','ft'),('LEN_YD','yd'),('LEN_UNITLESS','Unitless')] if p['min']<=getattr(v,n)<=p['max']]
    elif name.startswith('Dim') and not name.endswith('_FEM'):
        shape=v.GetParmVal(v.FindParm(v.GetParmContainer(p['id']),'CrossSectType','FeaProperty'))
        labels=next((labels for n,_,labels in SECTIONS if getattr(v,n)==shape),[]);index=int(name[3:])-1
        if index<len(labels):p['label']=labels[index]
    why=reason(v,p['id'],refs)
    if why:p.update(active=False,editable=False,readOnly=True,readOnlyReason=why)


def validate_parameter(v,pid):
    from native_references import references
    why=reason(v,pid,references(v) if v.GetParmGroupName(pid)=='FeaProperty' and v.GetParmName(pid) in ('Thickness','LengthUnit') else None)
    if why:raise ValueError(why)


def study_metadata(v):
    from native_references import references
    refs=references(v);out={}
    for prop in v.GetFeaPropertyIDVec():
        fields={v.GetParmName(p):p for p in v.FindContainerParmIDs(prop)}
        condition=lambda n,values:dict(parameter=fields[n],values=values,label=LABELS.get(n,n))
        for name in ('CrossSecArea','Izz','Iyy','Izy','Ixx'):
            out[fields[name]]=dict(alternatives=[[condition('FeaPropertyType',[v.FEA_SHELL])],[condition('FeaPropertyType',[v.FEA_BEAM]),condition('CrossSectType',[v.FEA_XSEC_GENERAL])]],limitControllers=[])
        material=refs.get(prop,{}).get('FeaMaterialID','')
        if material in v.GetFeaMaterialIDVec() and not material.startswith('_'):
            controller=v.FindParm(material,'FeaMaterialType','FeaMaterial')
            for name in ('Thickness','LengthUnit'):out[fields[name]]=dict(conditions=[dict(parameter=controller,values=[v.FEA_ISOTROPIC,v.FEA_ENG_ORTHO,v.FEA_ENG_ORTHO_TRANS_ISO],label='Assigned material model · non-laminate')],limitControllers=[])
    return out


def study_priority(v,pid):
    if v.GetParmGroupName(pid)!='FeaProperty':return None
    name=v.GetParmName(pid)
    return -12 if name=='FeaPropertyType' else -10 if name=='CrossSectType' else -8 if name=='LengthUnit' else 20
