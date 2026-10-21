"""Original material/layer input labels and calculated-property protection."""
def reason(v,pid):
    group=v.GetParmGroupName(pid);name=v.GetParmName(pid);owner=v.GetParmContainer(pid)
    if group not in ('FeaMaterial','FeaLayer'):return ''
    if name.endswith('_FEM'):return 'Calculated by OpenVSP in the selected structural solver units.'
    if group=='FeaLayer':return ''
    if owner.startswith('_'):return 'This is an original built-in material. Create a custom material to change its properties.'
    typ=v.GetParmVal(v.FindParm(owner,'FeaMaterialType','FeaMaterial'))
    scalar={'ElasticModulus','PoissonRatio','ThermalExpanCoeff'}
    directional={'E1','E2','E3','nu12','nu13','nu23','G12','G13','G23','A1','A2','A3'}
    if typ==v.FEA_LAMINATE and name in (scalar|directional|{'MassDensity'})-{'nu12','nu13','nu23'}:return 'Stored input for other material models. The laminate calculation uses its layers.'
    calculated=directional if typ==v.FEA_ISOTROPIC else scalar|{'E3','G13','nu13','G23','A3'} if typ==v.FEA_ENG_ORTHO_TRANS_ISO else scalar if typ==v.FEA_ENG_ORTHO else scalar|directional|{'Thickness','MassDensity'}
    return 'Calculated by OpenVSP from the selected material model or laminate layers.' if name in calculated else ''


def annotate(v,p):
    group=p['rawGroup'];name=p['name']
    if group=='FeaStructure' and name=='StructUnit':
        p.update(label='Structural solver unit system',choices=[dict(value=getattr(v,n),label=l) for n,l in [('SI_UNIT','SI · m, kg, N'),('CGS_UNIT','CGS · cm, g, dyn'),('MPA_UNIT','MPa · mm, tonne, N'),('BFT_UNIT','Foot · ft, slug, lbf'),('BIN_UNIT','Inch · in, lbf·s²/in, lbf')] if hasattr(v,n) and p['min']<=getattr(v,n)<=p['max']]);return
    if group not in ('FeaMaterial','FeaLayer'):return
    labels={'FeaMaterialType':'Material model','MassDensity':'Mass density','ElasticModulus':'Young’s modulus','PoissonRatio':'Poisson’s ratio','ThermalExpanCoeff':'Thermal expansion coefficient','Thickness':'Layer thickness (laminate length units)' if group=='FeaLayer' else 'Total laminate thickness','Theta':'Layer orientation (degrees)','LengthUnit':'Material and layer length units','DensityUnit':'Density units','ModulusUnit':'Modulus units','TemperatureUnit':'Thermal coefficient temperature units'}
    base=name.removesuffix('_FEM')
    p['label']=labels.get(base,{'E1':'Young’s modulus 1','E2':'Young’s modulus 2','E3':'Young’s modulus 3','G12':'Shear modulus 12','G13':'Shear modulus 13','G23':'Shear modulus 23','A1':'Thermal expansion 1','A2':'Thermal expansion 2','A3':'Thermal expansion 3','nu12':'Poisson ratio 12','nu13':'Poisson ratio 13','nu23':'Poisson ratio 23'}.get(base,base))+(' · solver units' if name.endswith('_FEM') else '')
    choices={
        'FeaMaterialType':[('FEA_ISOTROPIC','Isotropic'),('FEA_ENG_ORTHO','Orthotropic'),('FEA_ENG_ORTHO_TRANS_ISO','Transversely isotropic'),('FEA_LAMINATE','Laminate')],
        'LengthUnit':[('LEN_MM','mm'),('LEN_CM','cm'),('LEN_M','m'),('LEN_IN','in'),('LEN_FT','ft'),('LEN_YD','yd'),('LEN_UNITLESS','Unitless')],
        'DensityUnit':[('RHO_UNIT_SLUG_FT3','slug/ft³'),('RHO_UNIT_G_CM3','g/cm³'),('RHO_UNIT_KG_M3','kg/m³'),('RHO_UNIT_TONNE_MM3','tonne/mm³'),('RHO_UNIT_LBM_FT3','lbm/ft³'),('RHO_UNIT_LBFSEC2_IN4','lbf·s²/in⁴'),('RHO_UNIT_LBM_IN3','lbm/in³')],
        'ModulusUnit':[(n,l) for n,l in [('PRES_UNIT_PSF','psf'),('PRES_UNIT_PSI','psi'),('PRES_UNIT_BA','barye'),('PRES_UNIT_PA','Pa'),('PRES_UNIT_KPA','kPa'),('PRES_UNIT_MPA','MPa'),('PRES_UNIT_INCHHG','inHg'),('PRES_UNIT_MMHG','mmHg'),('PRES_UNIT_MMH20','mmH₂O'),('PRES_UNIT_MB','mbar'),('PRES_UNIT_ATM','atm')]],
        'TemperatureUnit':[('TEMP_UNIT_K','K'),('TEMP_UNIT_C','°C'),('TEMP_UNIT_F','°F'),('TEMP_UNIT_R','°R')]}
    if name in choices:p['choices']=[dict(value=getattr(v,n),label=l) for n,l in choices[name] if hasattr(v,n) and p['min']<=getattr(v,n)<=p['max']]
    unit=calculated_unit(v,p)
    if unit is not None:p['nativeUnit']=unit
    why=reason(v,p['id'])
    if why:p.update(active=False,readOnly=True,editable=False,readOnlyReason=why)


def validate_parameter(v,pid):
    why=reason(v,pid)
    if why:raise ValueError(why)


def study_metadata(v):
    out={}
    for material in v.GetFeaMaterialIDVec():
        if material.startswith('_'):continue
        controller=v.FindParm(material,'FeaMaterialType','FeaMaterial')
        for pid in v.FindContainerParmIDs(material):
            name=v.GetParmName(pid)
            allowed=None
            if name in ('ElasticModulus','PoissonRatio','ThermalExpanCoeff'):allowed=[v.FEA_ISOTROPIC]
            elif name in ('E3','nu13','G13','G23','A3'):allowed=[v.FEA_ENG_ORTHO]
            elif name in ('E1','E2','nu12','nu23','G12','A1','A2'):allowed=[v.FEA_ENG_ORTHO,v.FEA_ENG_ORTHO_TRANS_ISO]
            elif name=='MassDensity':allowed=[v.FEA_ISOTROPIC,v.FEA_ENG_ORTHO,v.FEA_ENG_ORTHO_TRANS_ISO]
            if allowed is not None:out[pid]=dict(conditions=[dict(parameter=controller,values=allowed,label='Material model')],limitControllers=[])
    return out


def study_priority(v,pid):
    group=v.GetParmGroupName(pid);name=v.GetParmName(pid)
    if group=='FeaMaterial':
        if name=='FeaMaterialType':return -12
        if name in ('LengthUnit','DensityUnit','ModulusUnit','TemperatureUnit'):return -8
        return 2
    if group=='FeaStructure' and name=='StructUnit':return -9
    if group=='FeaLayer':return 20
    return None


def owner_label(v,pid):
    if v.GetParmGroupName(pid)!='FeaLayer':return ''
    layer=v.GetParmContainer(pid)
    for material in v.GetFeaMaterialIDVec():
        if v.GetParmVal(v.FindParm(material,'FeaMaterialType','FeaMaterial'))!=v.FEA_LAMINATE:continue
        layers=list(v.GetFeaLayerIDVec(material))
        if layer in layers:return v.GetContainerName(material)+' / Layer '+str(layers.index(layer)+1)
    return ''


def calculated_unit(v,p):
    """Units of original material outputs; values are never converted here."""
    if p['rawGroup']!='FeaMaterial':return None
    name=p['name'];base=name.removesuffix('_FEM')
    if base in ('nu12','nu13','nu23','PoissonRatio'):return 'dimensionless'
    if name=='Thickness':
        owner=v.GetParmContainer(p['id'])
        length=v.GetParmVal(v.FindParm(owner,'LengthUnit','FeaMaterial'))
        return {getattr(v,k):label for k,label in [('LEN_MM','mm'),('LEN_CM','cm'),('LEN_M','m'),('LEN_IN','in'),('LEN_FT','ft'),('LEN_YD','yd'),('LEN_UNITLESS','unitless')]}.get(length)
    if not name.endswith('_FEM'):return None
    system=v.GetParmVal(v.FindParm(v.GetVehicleID(),'StructUnit','FeaStructure'))
    units={v.SI_UNIT:('m','kg/m³','Pa','1/K'),v.CGS_UNIT:('cm','g/cm³','barye','1/K'),v.MPA_UNIT:('mm','tonne/mm³','MPa','1/K'),v.BFT_UNIT:('ft','slug/ft³','psf','1/°R'),v.BIN_UNIT:('in','lbf·s²/in⁴','psi','1/°R')}.get(system)
    if units is None:return None
    if base=='Thickness':return units[0]
    if base=='MassDensity':return units[1]
    if base in ('ElasticModulus','E1','E2','E3','G12','G13','G23'):return units[2]
    if base in ('ThermalExpanCoeff','A1','A2','A3'):return units[3]
    return None
