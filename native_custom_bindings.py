"""Expose original custom GUI bindings without duplicating native parameters."""
import copy


def control_types(v):
    return {getattr(v,name) for name in ('GDEV_INPUT','GDEV_OUTPUT','GDEV_SLIDER_INPUT','GDEV_SLIDER_ADJ_RANGE_INPUT','GDEV_PARM_BUTTON','GDEV_TOGGLE_BUTTON','GDEV_TRIGGER_BUTTON','GDEV_COUNTER','GDEV_INDEX_SELECTOR','GDEV_CHOICE')}


def definitions_and_bindings(v,gid):
    import native_custom_scripts
    definitions=native_custom_scripts.gui_definitions(v,gid)
    bindings={u['index']:u['parameterId'] for u in native_custom_scripts.gui_updates(v,gid)}
    return definitions,bindings


def require_current_binding(v,request):
    index=request.get('index')
    if type(index)!=int:raise ValueError('Choose a current custom control.')
    definitions,bindings=definitions_and_bindings(v,request['geom'])
    definition=next((d for d in definitions if d['index']==index and d['type'] in control_types(v)),None)
    pid=bindings.get(index)
    if definition is None or not pid or not v.ValidParm(pid):raise ValueError('This custom control is disconnected.')
    if pid!=request.get('id'):raise ValueError('This custom control now targets another parameter. Refresh its current binding before editing.')
    if definition['type']==v.GDEV_OUTPUT:raise ValueError('This custom control is a calculated output.')
    return pid


def external_controls(v,component,parameters):
    import native_custom_library
    if not native_custom_library.is_custom(v,component['id']):return []
    from native_worker import parameter
    from native_preview import parameter_activity
    definitions,bindings=definitions_and_bindings(v,component['id']);own={p['id'] for p in component['params']};rows=[];last_choice=None
    tab=None
    tab_index=None
    for d in definitions:
        if d['type'] in (v.GDEV_TAB,v.GDEV_SCROLL_TAB):
            tab=d['label'] or None
            tab_index=d['index']
            continue
        if d['type']==v.GDEV_ADD_CHOICE_ITEM:
            if last_choice is not None:last_choice['parameter']['choices'].append([len(last_choice['parameter']['choices']),d['label']])
            continue
        if d['type']==v.GDEV_CHOICE:last_choice=None
        pid=bindings.get(d['index'])
        if d['type'] not in control_types(v) or not pid or pid in own or not v.ValidParm(pid):continue
        item=copy.deepcopy(parameters.get(pid) or parameter(v,pid))
        for key in ('customIndexSelector','customParmButton','trigger','triggerLabel'):item.pop(key,None)
        item['label']=d['label'].rstrip(':') or item.get('label') or item['name']
        item['active']=parameter_activity(v,[pid])[pid]
        if d['type']==v.GDEV_OUTPUT:item.update(displayReadOnly=True,readOnlyReason='Calculated output from the custom script.')
        if d['type']==v.GDEV_TRIGGER_BUTTON:item.update(trigger=True,triggerLabel=item['label'])
        if d['type']==v.GDEV_INDEX_SELECTOR:item['customIndexSelector']=d['index']
        if d['type']==v.GDEV_PARM_BUTTON:item['customParmButton']=True
        if d['type']==v.GDEV_CHOICE:item['choices']=[]
        row=dict(index=d['index'],parameter=item,owner=parameters.get(pid,{}).get('bindingOwner') or v.GetContainerName(v.GetParmContainer(pid)))
        if tab:row.update(tab=tab,tabIndex=tab_index)
        item.pop('bindingOwner',None);rows.append(row)
        if d['type']==v.GDEV_CHOICE:last_choice=row
    return rows
