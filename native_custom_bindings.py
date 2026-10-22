"""Expose original custom GUI bindings without duplicating native parameters."""
import copy


def control_types(v):
    return {getattr(v,name) for name in ('GDEV_INPUT','GDEV_OUTPUT','GDEV_SLIDER_INPUT','GDEV_SLIDER_ADJ_RANGE_INPUT','GDEV_PARM_BUTTON','GDEV_TOGGLE_BUTTON','GDEV_TRIGGER_BUTTON','GDEV_COUNTER','GDEV_INDEX_SELECTOR','GDEV_CHOICE')}


def definitions_and_bindings(v,gid,with_previous=False):
    import native_custom_scripts
    definitions=native_custom_scripts.gui_definitions(v,gid)
    updates=native_custom_scripts.gui_updates(v,gid)
    bindings={u['index']:u['parameterId'] for u in updates}
    previous={u['index']:u['parameterId'] for u in updates if u['parameterId']}
    return (definitions,bindings,previous) if with_previous else (definitions,bindings)


def require_current_binding(v,request):
    index=request.get('index')
    if type(index)!=int:raise ValueError('Choose a current custom control.')
    definitions,bindings=definitions_and_bindings(v,request['geom'])
    definition=next((d for d in definitions if d['index']==index and d['type'] in control_types(v)),None)
    pid=bindings.get(index)
    if definition is None or not pid or not v.ValidParm(pid):raise ValueError('This custom control is disconnected.')
    if pid!=request.get('id'):raise ValueError('This custom control now targets another parameter. Refresh its current binding before editing.')
    if definition['type']==v.GDEV_OUTPUT:raise ValueError('This custom control is a calculated output.')
    from native_preview import parameter_activity
    if not parameter_activity(v,[pid])[pid]:raise ValueError('This custom control is locked by OpenVSP.')
    return pid


def external_controls(v,component,parameters,include_own=False):
    import native_custom_library
    if not native_custom_library.is_custom(v,component['id']):return []
    from native_worker import parameter
    from native_preview import parameter_activity
    definitions,bindings,previous=definitions_and_bindings(v,component['id'],with_previous=True);own={p['id'] for p in component['params']};rows=[];last_choice=None
    import native_custom_layout
    layout=native_custom_layout.contexts(v,definitions)
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
        pid=bindings.get(d['index']);disconnected=False
        if include_own and not pid and previous.get(d['index']) in own:
            pid=previous[d['index']];disconnected=True
        if d['type'] not in control_types(v) or not pid or (pid in own and not include_own) or not v.ValidParm(pid):continue
        item=copy.deepcopy(parameters.get(pid) or parameter(v,pid))
        for key in ('customIndexSelector','customParmButton','customSlider','trigger','triggerLabel'):item.pop(key,None)
        native_custom_layout.annotate(item,d,layout)
        if item.get('description') in ('Default Description','Custom Descript'):item['description']=''
        item['label']=d['label'].rstrip(':') or item.get('label') or item['name']
        item['active']=parameter_activity(v,[pid])[pid]
        slider_key=f'{component["id"]}:{d["index"]}:{pid}'
        item['customSliderKey']=slider_key
        if pid not in parameters:item.update(displayReadOnly=True,readOnlyReason='Generated profile property. Use the script’s saved component inputs to change it.')
        if disconnected:item.update(displayReadOnly=True,readOnlyReason='Disconnected by the custom script in this configuration.')
        if d['type']==v.GDEV_OUTPUT:item.update(displayReadOnly=True,readOnlyReason='Calculated output from the custom script.')
        if d['type']==v.GDEV_TRIGGER_BUTTON:item.update(trigger=True,triggerLabel=item['label'])
        if d['type']==v.GDEV_INDEX_SELECTOR:item['customIndexSelector']=d['index']
        if d['type']==v.GDEV_PARM_BUTTON:item['customParmButton']=True
        if d['type'] in (v.GDEV_SLIDER_INPUT,v.GDEV_SLIDER_ADJ_RANGE_INPUT):
            item['customSlider']=dict(range=d.get('range'),adjustable=d['type']==v.GDEV_SLIDER_ADJ_RANGE_INPUT,
                                      key=slider_key)
        if d['type']==v.GDEV_CHOICE:item['choices']=[]
        row=dict(index=d['index'],parameter=item,owner=parameters.get(pid,{}).get('bindingOwner') or v.GetContainerName(v.GetParmContainer(pid)))
        if pid in own:row['owned']=True
        if tab:row.update(tab=tab,tabIndex=tab_index)
        item.pop('bindingOwner',None);rows.append(row)
        if d['type']==v.GDEV_CHOICE:last_choice=row
    return rows
