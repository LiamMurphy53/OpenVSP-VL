"""Native structural region identity, ordering and array workflows."""
import os
import native_references


def details(v,region,refs):
    import native_region_controls
    values=refs.get(region,{})
    return dict(type=values.get('regionType'),boundaryGuide=native_region_controls.guide(v,region,values.get('regionType')),intersectionTarget=values.get('IntersectID',''),propertyReferences={key:values.get(key,'') for key in ('FeaPropertyID','CapFeaPropertyID')})


def guard_remove(v,structure,region):
    refs=native_references.references(v)
    users=[v.GetContainerName(b) for b in v.GetFeaBCIDVec(structure)
           if v.GetParmVal(v.FindParm(b,'Type','FeaBC'))==v.FEA_BC_SUBSURF
           and refs.get(b,{}).get('SubSurfID')==region]
    if users:raise ValueError('Choose another region for these boundary conditions before removing or expanding this region: '+', '.join(users))


def reorder(v,structure,region,direction):
    # Matching FeaStructure::ReorderFeaSubSurf / ReorderVectorIndex. There is
    # no structural-region reorder wrapper in this installed Python binding.
    filename=v.GetVSPFileName()
    path,tree=native_references.document(v)
    try:
        owner=next((n for n in tree.findall('.//FeaStructureInfo') if n.findtext('ParmContainer/ID')==structure),None)
        if owner is None:raise ValueError('The native structure is unavailable.')
        regions=owner.findall('FeaSubSurface');index=next(i for i,n in enumerate(regions) if n.findtext('ParmContainer/ID')==region)
        target={'REORDER_MOVE_UP':max(0,index-1),'REORDER_MOVE_DOWN':min(len(regions)-1,index+1),'REORDER_MOVE_TOP':0,'REORDER_MOVE_BOTTOM':len(regions)-1}[direction]
        slots=[list(owner).index(n) for n in regions];regions.insert(target,regions.pop(index))
        for n in owner.findall('FeaSubSurface'):owner.remove(n)
        for slot,node in zip(slots,regions):owner.insert(slot,node)
        tree.write(path,encoding='utf-8',xml_declaration=True);os.replace(path,filename)
    finally:path.unlink(missing_ok=True)
    raise native_references.ReloadRequired()



def intersect(v,structure,region,target,curve):
    import copy,json,subprocess,sys,tempfile
    from pathlib import Path
    import xml.etree.ElementTree as ET
    from native_tools import one
    geom=v.GetFeaStructParentGeomID(structure)
    target=one(target,[g for g in v.FindGeoms() if g!=geom],'Choose another component to intersect with.')
    if isinstance(curve,bool) or not isinstance(curve,int) or curve<0:raise ValueError('Choose a native intersection curve.')
    filename=v.GetVSPFileName();path,tree=native_references.document(v)
    try:
        owner=next(n for n in tree.findall('.//FeaStructureInfo') if n.findtext('ParmContainer/ID')==structure)
        node=next(n for n in owner.findall('FeaSubSurface') if n.findtext('ParmContainer/ID')==region)
        if int(node.findtext('SubSurfaceInfo/Type'))!=v.SS_INTERSECT:raise ValueError('Choose a structural intersection region.')
        with tempfile.TemporaryDirectory(prefix='native-region-',dir=Path.cwd()) as folder:
            folder=Path(folder);scratch=copy.deepcopy(tree)
            temp_owner=next(n for n in scratch.findall('.//FeaStructureInfo') if n.findtext('ParmContainer/ID')==structure)
            temp_node=next(n for n in temp_owner.findall('FeaSubSurface') if n.findtext('ParmContainer/ID')==region)
            temp_owner.remove(temp_node);temp_node.tag='SubSurface'
            parent=next(n for n in scratch.findall('.//Geom') if n.findtext('ParmContainer/ID')==geom)
            regions=parent.find('Geom/SubSurfaces')
            if regions is None:raise ValueError('The native parent surface-region list is unavailable.')
            regions.append(temp_node)
            model=folder/'intersection.vsp3';scratch.write(model,encoding='utf-8',xml_declaration=True)
            request=folder/'request.json';response=folder/'response.json'
            request.write_text(json.dumps(dict(region=region,target=target,curve=curve)))
            with (folder/'native.log').open('w') as log:
                run=subprocess.run([sys.executable,str(Path(__file__).with_name('native_region_worker.py')),str(request),str(model),str(response)],stdout=log,stderr=log,timeout=90)
            if not response.exists():raise ValueError('The native intersection process did not return a result.')
            result=json.loads(response.read_text())
            if run.returncode:raise ValueError(result.get('error','The native intersection failed.'))
            computed=next((n for n in ET.parse(model).findall('.//SubSurface') if n.findtext('ParmContainer/ID')==region),None)
            if computed is None:raise ValueError('OpenVSP did not retain this region identity.')
            computed.tag='FeaSubSurface'
            # Intersection calculation does not edit structural assignments.
            # Keep their original native IDs even if the scratch load remapped
            # an unused default property. The final engine resolves indices.
            for key in ('FeaPropertyID','CapFeaPropertyID'):
                original=node.find(key);assigned=computed.find(key)
                if original is not None and assigned is not None:assigned.text=original.text
            # Copy the entire native computed region, including its Bezier curve,
            # back into the original document. Every other owner is retained.
            slot=list(owner).index(node);owner.remove(node);owner.insert(slot,computed)
        tree.write(path,encoding='utf-8',xml_declaration=True);os.replace(path,filename)
    finally:path.unlink(missing_ok=True)
    raise native_references.ReloadRequired()


def mutate(v,r):
    from native_tools import one,name
    from native_advanced import SUBSURF_TYPES,enums
    from native_structure import refresh
    operation=r['operation'];structure=one(r['structure'],v.GetFeaStructIDVec())
    geom=v.GetFeaStructParentGeomID(structure);index=v.GetFeaStructIndex(structure)
    if operation=='structural-subsurface-add':
        typ=one(r['type'],enums(v,SUBSURF_TYPES))
        if typ=='SS_CONTROL' and v.GetGeomTypeName(geom).upper() not in ('WING','PROP','PROPELLER'):raise ValueError('Control boundaries require a wing or propeller.')
        region=v.AddFeaSubSurf(geom,index,getattr(v,typ))
        if not region:raise ValueError('OpenVSP could not create this structural region.')
        v.SetFeaSubSurfName(region,name(r['name']))
    else:
        regions=list(v.GetFeaSubSurfIDVec(structure));region=one(r['id'],regions,'Choose a region in this structure.')
        if operation=='structural-subsurface-property':
            role=one(r['role'],['shell','beam']);typ=v.FEA_SHELL if role=='shell' else v.FEA_BEAM
            prop=one(r['property'],[p for p in v.GetFeaPropertyIDVec() if v.GetParmVal(v.FindParm(p,'FeaPropertyType','FeaProperty'))==typ],'Choose a matching '+role+' property.')
            native_references.set_reference(v,region,'FeaSubSurface','FeaPropertyID' if role=='shell' else 'CapFeaPropertyID',prop)
        elif operation=='structural-subsurface-rename':v.SetFeaSubSurfName(region,name(r['name']))
        elif operation=='structural-subsurface-intersect':
            intersect(v,structure,region,r.get('target'),r.get('curve',0))
        elif operation=='structural-subsurface-reorder':
            direction=one(r['direction'],('REORDER_MOVE_UP','REORDER_MOVE_DOWN','REORDER_MOVE_TOP','REORDER_MOVE_BOTTOM'))
            reorder(v,structure,region,direction)
        elif operation in ('structural-subsurface-delete','structural-subsurface-individualize'):
            guard_remove(v,structure,region)
            if operation.endswith('delete'):v.DeleteFeaSubSurf(geom,index,region)
            else:
                refs=native_references.references(v)
                if refs.get(region,{}).get('regionType')!=v.SS_LINE_ARRAY:raise ValueError('Choose a structural line array to expand.')
                refresh(v,structure);v.IndividualizeFeaPart(geom,index,region)
                after=list(v.GetFeaSubSurfIDVec(structure))
                if region in after or len(after)<len(regions):raise ValueError('OpenVSP did not expand this line array. Check its spacing and range.')
        else:return False,None
    return True,geom
