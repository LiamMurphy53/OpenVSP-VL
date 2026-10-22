"""Semantic grouping from native custom GUI declarations; no pixel layout copy."""
def contexts(v,definitions):
    result={};tab=None;divider=None
    for d in definitions:
        if d['type'] in (v.GDEV_TAB,v.GDEV_SCROLL_TAB):tab=dict(index=d['index'],label=d['label']);divider=None
        elif d['type']==v.GDEV_DIVIDER_BOX:divider=dict(index=d['index'],label=d['label'])
        result[d['index']]=dict(tab=tab,divider=divider)
    return result


def annotate(parameter,definition,layout):
    parameter['customControlOrder']=definition['index']
    tab=layout[definition['index']]['tab']
    if tab:parameter.update(customTab=tab['label'],customTabIndex=tab['index'])
    else:
        parameter.pop('customTab',None);parameter.pop('customTabIndex',None)
    divider=layout[definition['index']]['divider']
    if divider:parameter['customDivider']=dict(divider)
    else:parameter.pop('customDivider',None)
