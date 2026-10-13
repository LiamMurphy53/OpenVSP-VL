"""Native structural library names and guarded removal of saved definitions."""
import native_references
import os


def copy_parameters(v,source,target,group):
    """Copy stored inputs by native name; let the engine recompute outputs."""
    for pid in v.FindContainerParmIDs(source):
        name=v.GetParmName(pid)
        if v.GetParmGroupName(pid)!=group or name.endswith('_FEM') or name=='FeaMaterialIndex':continue
        dest=v.FindParm(target,name,group)
        if not dest:raise ValueError('The native copy is missing an input: '+name)
        value=v.GetParmVal(pid)
        v.SetParmVal(dest,value)
        if v.GetParmVal(dest)!=value:raise ValueError('The native copy could not retain the input: '+name)


def copy_definition(v,cid,material,title):
    refs=native_references.references(v);assignments=[]
    if material:
        target=v.AddFeaMaterial();copy_parameters(v,cid,target,'FeaMaterial')
        source_path,source_tree=native_references.document(v)
        try:
            node=next((n for n in source_tree.findall('.//FeaMaterialInfo') if n.findtext('ParmContainer/ID')==cid),None)
            # Inactive layer stacks remain stored after a model change. The
            # native public layer enumeration only accepts laminate models.
            layers=[n.findtext('ParmContainer/ID') for n in node.findall('FeaLayerInfo')] if node is not None else []
        finally:source_path.unlink(missing_ok=True)
        if layers:
            mode=v.FindParm(target,'FeaMaterialType','FeaMaterial');previous=v.GetParmVal(mode)
            v.SetParmVal(mode,v.FEA_LAMINATE)
            for source in layers:
                layer=v.AddFeaLayer(target);copy_parameters(v,source,layer,'FeaLayer')
                v.SetContainerName(layer,v.GetContainerName(source))
                assignments.append((layer,'FeaLayerInfo','FeaLaminaID',refs.get(source,{}).get('FeaLaminaID','')))
            v.SetParmVal(mode,previous)
    else:
        target=v.AddFeaProperty(int(v.GetParmVal(v.FindParm(cid,'FeaPropertyType','FeaProperty'))))
        copy_parameters(v,cid,target,'FeaProperty')
        assignments.append((target,'FeaPropertyInfo','FeaMaterialID',refs.get(cid,{}).get('FeaMaterialID','')))
    v.SetContainerName(target,title)
    if assignments:
        # Preserve new native identities; assign saved string references in one
        # transaction before any update can evaluate temporary default layers.
        filename=v.GetVSPFileName();path,tree=native_references.document(v)
        try:
            for owner,tag,key,value in assignments:
                node=next(n for n in tree.findall('.//'+tag) if n.findtext('ParmContainer/ID')==owner)
                node.find(key).text=value
            tree.write(path,encoding='utf-8',xml_declaration=True);os.replace(path,filename)
        finally:path.unlink(missing_ok=True)
        raise native_references.ReloadRequired()
    v.Update()
    return target


def usage(v,refs=None):
    if refs is None:refs=native_references.references(v)
    out={}
    for owner,values in refs.items():
        for key in ('FeaPropertyID','CapFeaPropertyID','FeaMaterialID','FeaLaminaID'):
            target=values.get(key)
            if target:
                out.setdefault(target,[]).append(dict(id=owner,name=v.GetContainerName(owner),role={'FeaPropertyID':'Shell property','CapFeaPropertyID':'Beam property','FeaMaterialID':'Property material','FeaLaminaID':'Layer material'}[key]))
    return out


def mutate(v,r):
    from native_tools import one,name
    operation=r['operation'];material=operation.startswith('material-')
    definitions=v.GetFeaMaterialIDVec() if material else v.GetFeaPropertyIDVec()
    cid=one(r['id'],definitions,'Choose an existing structural definition.')
    if operation.endswith('-copy'):
        copy_definition(v,cid,material,name(r.get('name') or (v.GetContainerName(cid)[:115]+' copy')))
        return True,None
    if material and cid.startswith('_'):raise ValueError('Built-in materials are retained by OpenVSP. Edit a custom material instead.')
    if operation.endswith('-rename'):
        v.SetContainerName(cid,name(r['name']))
    elif operation.endswith('-delete'):
        users=usage(v).get(cid,[])
        if users:raise ValueError('Reassign this definition before removing it: '+', '.join(u['name']+' ('+u['role']+')' for u in users))
        if material:v.DeleteFeaMaterial(cid)
        else:v.DeleteFeaProperty(cid)
        remaining=v.GetFeaMaterialIDVec() if material else v.GetFeaPropertyIDVec()
        if cid in remaining:raise ValueError('OpenVSP retained this definition; it could not be removed.')
    else:return False,None
    return True,None
