"""Named choices for the original native geometry symmetry parameters."""


def annotate(v,field):
    if field['rawGroup']!='Sym':return field
    name=field['name']
    labels={'Sym_Planar_Flag':'Mirror planes','Sym_Axial_Flag':'Rotation axis',
            'Sym_Rot_N':'Number of rotation copies','Sym_Ancestor':'Symmetry reference',
            'Sym_Ancestor_Origin_Flag':'Reference origin'}
    if name in labels:field['label']=labels[name]
    if name=='Sym_Planar_Flag':
        planes=[(v.SYM_XY,'XY'),(v.SYM_XZ,'XZ'),(v.SYM_YZ,'YZ')]
        field['choices']=[[v.SYM_NONE,'No mirror']]+[
            [sum(code for i,(code,label) in enumerate(planes) if mask&(1<<i)),
             'Mirror '+', '.join(label for i,(code,label) in enumerate(planes) if mask&(1<<i))]
            for mask in range(1,8)]
    elif name=='Sym_Axial_Flag':
        field['choices']=[[v.SYM_NONE,'No rotation copies'],[v.SYM_ROT_X,'Around X'],
                          [v.SYM_ROT_Y,'Around Y'],[v.SYM_ROT_Z,'Around Z']]
    elif name=='Sym_Ancestor_Origin_Flag':
        field['choices']=[[1,'Attachment origin'],[0,'Component origin']]
    elif name=='Sym_Ancestor':
        owner=v.GetParmContainer(field['id']);choices=[[0,'Global axes']]
        current=owner;depth=1;seen=set()
        while current in v.FindGeoms() and current not in seen:
            seen.add(current)
            choices.append([depth,('This component' if depth==1 else 'Ancestor '+str(depth-1))+' · '+v.GetGeomName(current)])
            current=v.GetGeomParent(current);depth+=1
        if field['value'] not in [value for value,label in choices]:
            choices.append([field['value'],'Saved ancestor index '+str(int(field['value']))])
        field['choices']=choices
    return field
