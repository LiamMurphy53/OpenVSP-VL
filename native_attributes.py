"""Typed native model metadata, including nested groups and parameter references."""
from native_tools import one,name,finite

KINDS={'Boolean':('BOOL_DATA','Bool'),'Integer':('INT_DATA','Int'),'Number':('DOUBLE_DATA','Double'),'Text':('STRING_DATA','String'),'Parameter':('PARM_REFERENCE_DATA','Parm'),'Vector':('VEC3D_DATA','Vec3d'),'Integer matrix':('INT_MATRIX_DATA','IntMatrix'),'Number matrix':('DOUBLE_MATRIX_DATA','DoubleMatrix'),'Group':('ATTR_COLLECTION_DATA','Group')}

def collections(v):
    from native_tools import containers
    native_containers=list(v.FindContainers());objects=set([v.GetVehicleID(),*v.FindGeoms(),*native_containers,*containers(v),*v.FindAttributedObjects(),*v.GetAllUserParms()])
    geometry_parameters={}
    for g in v.FindGeoms():
        ids=list(v.GetGeomParmIDs(g));objects.update(ids);geometry_parameters.update({p:g for p in ids})
        for i in range(v.GetNumXSecSurfs(g)):
            surface=v.GetXSecSurf(g,i);objects.add(surface)
            for j in range(v.GetNumXSec(surface)):
                section=v.GetXSec(surface,j);objects.add(section)
                objects.update(v.GetParmContainer(p) for p in v.GetXSecParmIDs(section))
    for c in native_containers:objects.update(v.FindContainerParmIDs(c))
    type_names={getattr(v,enum):label for enum,label in [('ATTROBJ_XSEC','Cross-section'),('ATTROBJ_SEC','Section'),('ATTROBJ_MODE','Mode'),('ATTROBJ_VARGROUP','Preset group'),('ATTROBJ_VARSETTING','Preset setting')]}
    result=[]
    for obj in sorted(objects):
        cid=v.GetChildCollection(obj)
        if not cid or cid in ('NONE','ID ERROR') or v.GetObjectType(cid)!=v.ATTROBJ_COLLECTION:continue
        title=v.GetObjectName(obj) or obj
        typ=v.GetObjectType(obj)
        if typ==v.ATTROBJ_PARM:
            owner=v.GetContainerName(v.GetParmContainer(obj));geom=geometry_parameters.get(obj)
            title=' / '.join(([v.GetGeomName(geom)] if geom and v.GetGeomName(geom)!=owner else [])+[owner,v.GetParmDisplayGroupName(obj),v.GetParmName(obj)])
        result.append(dict(id=cid,object=obj,name=title,type=type_names.get(typ,'Native container' if typ==v.ATTROBJ_FREE else v.GetObjectTypeName(obj))))
    # This native API indexes user-set collections, excluding the three built-ins.
    for i in range(v.GetNumSets()-3):result.append(dict(id=v.GetGeomSetCollection(i),object='set:'+str(i+3),name=v.GetSetName(i+3),type='Geometry set'))
    for a in v.FindAllAttributes():
        if v.GetAttributeType(a)==v.ATTR_COLLECTION_DATA:result.append(dict(id=v.GetChildCollection(a),object=a,name=v.GetAttributeName(a),type='Attribute group'))
    return sorted({c['id']:c for c in result}.values(),key=lambda c:(c['type'],c['name'],c['id']))

def editable(v,a):return not v.GetAttributeName(a).startswith('Studio.') and not a.startswith('_')

def snapshot(v):
    getters={getattr(v,enum):getattr(v,'GetAttribute'+suffix+'Val') for enum,suffix in [value for key,value in KINDS.items() if key not in ('Parameter','Group')]}
    attrs=[]
    for a in v.FindAllAttributes():
        # Binary package storage is managed internally, not an editable note.
        if v.GetAttributeName(a)=='Studio.CustomAssets':continue
        typ=v.GetAttributeType(a);kind=next((key for key,(enum,suffix) in KINDS.items() if getattr(v,enum)==typ),v.GetAttributeTypeName(a));values=[]
        if typ==v.PARM_REFERENCE_DATA:values=list(v.GetAttributeParmID(a))
        elif typ in getters:
            values=list(getters[typ](a))
            if typ==v.VEC3D_DATA:values=[[p.x(),p.y(),p.z()] for p in values]
            elif typ in (v.INT_MATRIX_DATA,v.DOUBLE_MATRIX_DATA):values=[list(row) for row in values]
        attrs.append(dict(id=a,collection=v.GetObjectParent(a),name=v.GetAttributeName(a),doc=v.GetAttributeDoc(a),kind=kind,values=values,editable=editable(v,a)))
    return dict(notes=list(v.GetAttributeStringVal('_AttrVehNotes'))[0],attributeCollections=collections(v),attributes=attrs,attributeKinds=list(KINDS))

def value(v,kind,x):
    if kind=='Group':return None
    if kind=='Text':
        if not isinstance(x,str) or len(x)>100000:raise ValueError('Use text up to 100000 characters.')
        return x
    if kind=='Boolean':return one(x,[True,False])
    if kind=='Integer':
        finite(x)
        if not isinstance(x,int) or not -2147483648<=x<=2147483647:raise ValueError('Enter a 32-bit integer.')
        return x
    if kind=='Number':return finite(x)
    if kind=='Parameter':
        if not v.ValidParm(x):raise ValueError('Choose a parameter in this aircraft.')
        return x
    if kind=='Vector':
        from native_fit import vector
        # The native attribute stores a list of vec3d, not just one coordinate.
        if isinstance(x,list) and len(x)==3 and all(isinstance(a,(int,float)) and not isinstance(a,bool) for a in x):x=[x]
        if not isinstance(x,list) or len(x)>10000:raise ValueError('Use up to 10000 vectors, each with X, Y and Z coordinates.')
        return [vector(v,p) for p in x]
    if kind.endswith('matrix'):
        if not isinstance(x,list) or len(x)>1000 or (x and (not isinstance(x[0],list) or len(x[0])>1000 or any(not isinstance(row,list) or len(row)!=len(x[0]) for row in x))):raise ValueError('Use a rectangular matrix with up to 1000 rows and columns.')
        return [[value(v,'Integer' if kind=='Integer matrix' else 'Number',a) for a in row] for row in x]

def mutate(v,r):
    op=r['operation']
    if op=='model-notes':
        v.SetAttributeString('_AttrVehNotes',value(v,'Text',r['content']));return True,None
    if op not in ('attribute-save','attribute-delete','attribute-copy'):return False,None
    attr=r.get('id');allattrs=list(v.FindAllAttributes())
    def destination():
        choices=collections(v)
        if 'owner' in r:
            owner=one(r['owner'],[c['object'] for c in choices])
            return next(c['id'] for c in choices if c['object']==owner)
        return one(r['collection'],[c['id'] for c in choices])
    if op in ('attribute-delete','attribute-copy') and not attr:raise ValueError('Choose an attribute first.')
    if attr:
        one(attr,allattrs)
        if not editable(v,attr):raise ValueError('Studio workflow metadata is managed by its dedicated editor.')
        if op in ('attribute-delete','attribute-copy'):
            def descendants(a):
                result=[a]
                if v.GetAttributeType(a)==v.ATTR_COLLECTION_DATA:
                    for child in v.FindAttributesInCollection(v.GetChildCollection(a)):result.extend(descendants(child))
                return result
            children=descendants(attr)
            if any(not editable(v,a) for a in children):raise ValueError('This group contains managed metadata. Use its dedicated editor.')
    if op=='attribute-delete':v.DeleteAttribute(attr)
    elif op=='attribute-copy':
        coll=destination()
        if any(v.GetAttributeType(a)==v.ATTR_COLLECTION_DATA and v.GetChildCollection(a)==coll for a in children):raise ValueError('Choose a destination outside the group being copied.')
        if v.CopyAttribute(attr)!=0:raise ValueError('OpenVSP could not copy this attribute.')
        if not list(v.PasteAttribute(coll)):raise ValueError('OpenVSP could not paste the attribute into this collection.')
    else:
        title=name(r['name']);doc=r.get('doc','')
        if title.startswith('Studio.'):raise ValueError('Studio. names are reserved for saved workflow references.')
        if not isinstance(doc,str) or len(doc)>100000:raise ValueError('Use a description up to 100000 characters.')
        kind=one(r['kind'],KINDS);enum,suffix=KINDS[kind];x=value(v,kind,r.get('value'))
        if attr:
            if v.GetAttributeType(attr)!=getattr(v,enum):raise ValueError('An existing attribute keeps its native value type.')
            if kind!='Group':getattr(v,'SetAttribute'+('ParmID' if kind=='Parameter' else suffix))(attr,x)
            v.SetAttributeName(attr,title)
        else:
            coll=destination();attr=getattr(v,'AddAttribute'+suffix)(coll,title,*([] if kind=='Group' else [x]))
        v.SetAttributeDoc(attr,doc)
    return True,None
