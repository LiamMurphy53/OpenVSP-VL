"""Match explicit native set selections when rebasing a frozen study."""
import copy
import math

SET_INPUTS={'Set','GeomSet','ThinGeomSet','ThickGeomSet','DegenSet','SelectedSetIndex','SelectedDegenSetIndex','TargetSet','BoundarySet','CGGeomSet','CGDegenSet'}


def references(stages,axes,selector_ids):
    for i,stage in enumerate(stages):
        for key in ('inputs','geometryInputs'):
            entries=stage.get(key,[])
            if not isinstance(entries,list) or any(not isinstance(e,dict) for e in entries):raise ValueError('Choose valid native study inputs.')
            for entry in entries:
                if entry.get('name') in SET_INPUTS:yield entry,'values',f'Step {i+1} · {entry["name"]}'
    for i,axis in enumerate(axes):
        if axis.get('kind') in ('input','geometryInput') and axis.get('name') in SET_INPUTS or axis.get('kind')=='parameter' and axis.get('id') in selector_ids:
            yield axis,'values',f'Sweep {i+1} · {axis.get("label",axis.get("name",axis.get("id")))}'


def user_indices(value):
    if isinstance(value,list):return {x for item in value for x in user_indices(item)}
    return {int(value)} if type(value) in (int,float) and math.isfinite(value) and value>=3 and value==int(value) else set()


def rebind(saved_ids,current_ids,stages,axes,selector_ids):
    if not isinstance(stages,list) or not isinstance(axes,list) or any(not isinstance(x,dict) for x in [*stages,*axes]):raise ValueError('Choose valid native study steps and sweep dimensions.')
    stages=copy.deepcopy(stages);axes=copy.deepcopy(axes);matches=[]
    for entry,key,label in references(stages,axes,selector_ids):
        indices=user_indices(entry[key]);mapping={}
        for old in sorted(indices):
            if not isinstance(saved_ids,list) or old>=len(saved_ids):raise ValueError(label+': saved set identity is unavailable. Configure explicit set selections in a new study using the current aircraft.')
            identity=saved_ids[old]
            if identity not in current_ids:raise ValueError(label+': a selected set was removed or replaced. Choose its replacement in a new study using the current aircraft.')
            new=current_ids.index(identity);mapping[old]=new
            matches.append(dict(label=label,oldIndex=old,index=new,changed=old!=new))
        def mapped(value):return [mapped(x) for x in value] if isinstance(value,list) else mapping.get(value,value)
        entry[key]=mapped(entry[key])
    return stages,axes,matches
