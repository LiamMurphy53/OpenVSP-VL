"""Study dependencies for native component controls; all evaluation stays native."""
import re
import native_family_controls
import native_prop_controls


def metadata(v):
    out={}
    for gid in v.FindGeoms():
        kind=v.GetGeomTypeName(gid).upper()
        if kind not in ('HINGE','CONFORMAL','COBRA','PROP','PROPELLER','BODYOFREVOLUTION'):continue
        group='Hinge' if kind=='HINGE' else 'Design'
        ids={v.GetParmName(p):p for p in v.GetGeomParmIDs(gid) if v.GetParmGroupName(p)==group}
        def condition(name,values):
            return dict(parameter=ids[name],values=values,label=native_prop_controls.LABELS.get(name,native_family_controls.HINGE_LABELS.get(name,native_family_controls.CONFORMAL_LABELS.get(name,native_family_controls.COBRA_LABELS.get(name,name)))))
        def add(name,conditions,limits=()):
            if name in ids:out[ids[name]]=dict(conditions=conditions,limitControllers=[ids[n] for n in limits if n in ids])
        if kind=='BODYOFREVOLUTION':
            for name in ('Diameter','Angle'):add(name,[condition('Mode',[v.BOR_FLOWTHROUGH])])
        elif kind=='HINGE':
            for base,flag,limits in [('JointRotate','JointRotateFlag',['JointRotMinFlag','JointRotMin','JointRotMaxFlag','JointRotMax']),('JointTranslate','JointTranslateFlag',['JointTransMinFlag','JointTransMin','JointTransMaxFlag','JointTransMax'])]:
                add(base,[condition(flag,[1])],limits)
            for n in ('JointRotMin','JointRotMax','JointTransMin','JointTransMax'):add(n,[condition(n+'Flag',[1])])
            vector=[condition('OrientRotFlag',[1])]
            for name in ('SecondaryDir','PrimType','SecVecAbsRelFlag','SecondaryVecDir'):add(name,vector)
            add('PrimVecAbsRelFlag',vector+[condition('PrimType',[0])])
            add('PrimOffAbsRelFlag',vector+[condition('PrimType',[1,2])])
            for name in ('PrimULoc','PrimWLoc'):add(name,vector+[condition('PrimType',[2,3,4,5])])
            for name in ids:
                if re.fullmatch(r'Prim[XYZ](Vec|Off)(Rel)?',name):
                    isvec='Vec' in name
                    add(name,vector+[condition('PrimType',[0] if isvec else [1,2]),condition('PrimVecAbsRelFlag' if isvec else 'PrimOffAbsRelFlag',[v.REL if name.endswith('Rel') else v.ABS])])
        elif kind=='CONFORMAL':
            for end in ('Min','Max'):
                enabled=[condition('UTrimFlag',[1])]
                add('U'+end+'TrimTypeFalg',enabled)
                add('L01'+end,enabled+[condition('U'+end+'TrimTypeFalg',[v.L_TRIM])])
                for name,typ,basis in [('UTrim',v.U_TRIM,None),('LTrim',v.L_TRIM,1),('L0LenTrim',v.L_TRIM,0),('EtaTrim',v.ETA_TRIM,None)]:
                    conditions=enabled+[condition('U'+end+'TrimTypeFalg',[typ])]
                    if basis is not None:conditions+=[condition('L01'+end,[basis])]
                    add(name+end,conditions)
            for i in (1,2):
                for suffix in ('Begin','End'):add('V'+str(i)+'Trim'+suffix,[condition('V'+str(i)+'TrimFlag',[1])])
            for end in ('Min','Max'):add('ChordTrim'+end,[condition('ChordTrimFlag',[1])])
            for i in range(1,5):add('Side'+str(i)+'Trim',[condition('Side'+str(i)+'TrimFlag',[1])])
        elif kind=='COBRA':
            for name in ('ZradNL','PowNL'):add(name,[condition('NoseULSymm',[0])])
            for name in ('ZradAL','PowAL'):add(name,[condition('AftULSymm',[0])])
        else:
            def count(minimum):return dict(parameter=ids['NumBlade'],minimum=minimum,label='Blade count ≥ '+str(minimum))
            add('Beta34',[condition('UseBeta34Flag',[1])])
            add('Feather',[condition('UseBeta34Flag',[0])])
            for name in ids:
                if re.fullmatch(r'FoldAngle_\d+',name):add(name,[condition('IndividualBladeFoldFlag',[1]),count(int(name.split('_')[-1])+1)])
                elif re.fullmatch(r'(BladeAz|DeltaAz)_\d+',name):
                    blade=int(name.split('_')[-1]);frame=condition('BladeAzimuthDeltaFlag',[1 if name.startswith('DeltaAz') else 0])
                    out[ids[name]]=dict(alternatives=[[condition('BladeAzimuthMode',[v.PROP_AZI_FREE]),frame,count(blade)],
                        [condition('BladeAzimuthMode',[v.PROP_AZI_BALANCED]),frame,count(max(4,blade+2))]],limitControllers=[])
            out[ids['BladeAzimuthDeltaFlag']]=dict(alternatives=[[condition('BladeAzimuthMode',[v.PROP_AZI_FREE])],
                [condition('BladeAzimuthMode',[v.PROP_AZI_BALANCED]),count(4)]],limitControllers=[])
    import native_engine_controls
    out.update(native_engine_controls.study_metadata(v))
    import native_case_studies
    out.update(native_case_studies.metadata(v))
    import native_connection_controls
    out.update(native_connection_controls.study_metadata(v))
    import native_boundary_controls
    out.update(native_boundary_controls.study_metadata(v))
    import native_material_controls
    out.update(native_material_controls.study_metadata(v))
    import native_property_controls
    out.update(native_property_controls.study_metadata(v))
    import native_part_controls
    out.update(native_part_controls.study_metadata(v))
    import native_region_controls
    out.update(native_region_controls.study_metadata(v))
    import native_fea_sizing
    out.update(native_fea_sizing.study_metadata(v))
    import native_cfd_density
    out.update(native_cfd_density.study_metadata(v))
    import native_export_controls
    out.update(native_export_controls.study_metadata(v))
    import native_measurements
    out.update(native_measurements.study_metadata(v))
    import native_parasite_controls
    out.update(native_parasite_controls.study_metadata(v))
    import native_wave_controls
    out.update(native_wave_controls.study_metadata(v))
    return out


def controlled(v,pid,axes):
    data=metadata(v).get(pid)
    if not data:return False
    swept={a.get('id'):a.get('values',[]) for a in axes if isinstance(a,dict) and a.get('kind')=='parameter'}
    branches=data.get('alternatives',[data.get('conditions',[])])
    return any(any(c['parameter'] in swept for c in conditions) and all(any(matches(c,x) for x in swept.get(c['parameter'],[v.GetParmVal(c['parameter'])])) for c in conditions) for conditions in branches)


def matches(condition,value):
    return value in condition['values'] if 'values' in condition else value>=condition['minimum']


def deferred_limits(v,pid,swept):
    if v.GetParmGroupName(pid)=='ParasiteDrag' and v.GetParmName(pid)=='Temp':
        import native_parasite_controls
        return native_parasite_controls.ids(v)['TempUnit'] in swept
    import native_part_controls
    if native_part_controls.deferred_limits(v,pid,swept):return True
    if v.GetParmGroupName(pid)!='Hinge' or v.GetParmName(pid) not in ('JointRotate','JointTranslate'):return False
    return bool(set(metadata(v).get(pid,{}).get('limitControllers',[])) & swept)


def priority(v,pid):
    import native_engine_controls
    if native_engine_controls.owner(v,pid):return -5
    import native_wave_controls
    wave=native_wave_controls.study_priority(v,pid)
    if wave is not None:return wave
    import native_parasite_controls
    parasite=native_parasite_controls.study_priority(v,pid)
    if parasite is not None:return parasite
    if v.GetParmGroupName(pid)=='Measure':return -10 if v.GetParmName(pid)=='LMNFlag' else 40
    import native_export_controls
    export=native_export_controls.study_priority(v,pid)
    if export is not None:return export
    import native_cfd_density
    density=native_cfd_density.study_priority(v,pid)
    if density is not None:return density
    import native_fea_sizing
    sizing=native_fea_sizing.study_priority(v,pid)
    if sizing is not None:return sizing
    import native_region_controls
    region=native_region_controls.study_priority(v,pid)
    if region is not None:return region
    import native_part_controls
    part=native_part_controls.study_priority(v,pid)
    if part is not None:return part
    import native_property_controls
    prop=native_property_controls.study_priority(v,pid)
    if prop is not None:return prop
    import native_material_controls
    material=native_material_controls.study_priority(v,pid)
    if material is not None:return material
    import native_boundary_controls
    boundary=native_boundary_controls.study_priority(v,pid)
    if boundary is not None:return boundary
    import native_connection_controls
    connection=native_connection_controls.study_priority(v,pid)
    if connection is not None:return connection
    import native_case_studies
    case=native_case_studies.priority(v,pid)
    if case is not None:return case
    owner=next((g for g in v.FindGeoms() if pid in v.GetGeomParmIDs(g)),None)
    if not owner or v.GetGeomTypeName(owner).upper() not in ('HINGE','CONFORMAL','COBRA','PROP','PROPELLER','BODYOFREVOLUTION'):return None
    name=v.GetParmName(pid)
    if v.GetGeomTypeName(owner).upper()=='BODYOFREVOLUTION':return -10 if name=='Mode' else None
    if v.GetGeomTypeName(owner).upper() in ('PROP','PROPELLER'):
        if name=='NumBlade':return -9
        if name=='BladeAzimuthMode':return -8
        if name in ('BladeAzimuthDeltaFlag','IndividualBladeFoldFlag','UseBeta34Flag'):return -6
        return None
    if name=='OrientRotFlag':return -8
    if name in ('PrimType','UMinTrimTypeFalg','UMaxTrimTypeFalg'):return -7
    if name.endswith('Flag') or name in ('L01Min','L01Max','NoseULSymm','AftULSymm','UMinTrimTypeFalg','UMaxTrimTypeFalg'):return -6
    if name in ('JointRotMin','JointRotMax','JointTransMin','JointTransMax'):return -4
    return None
