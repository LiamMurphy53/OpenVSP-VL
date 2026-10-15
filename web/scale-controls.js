// Native actions retain the ordinary geometry transaction and Undo history.
export function scaleActionsMarkup(parameter,esc){
 if(!parameter.scaleActions)return '';
 const disabled=parameter.active===false||parameter.displayReadOnly===true||parameter.value===1;
 return `<div class="tool-actions" aria-label="Scale actions">${[['accept','Accept scale','Keep this size and set the scale factor to 1.'],['reset','Reset scale','Undo scaling since the last accepted size.']].map(([action,label,title])=>`<button type="button" data-scale-action="${action}" data-scale-geom="${esc(parameter.scaleActions.geom)}" title="${title}" ${disabled?'disabled':''}>${label}</button>`).join('')}</div>`;
}
export function bindScaleActions(host,mutate){
 for(const button of host.querySelectorAll('[data-scale-action]'))button.onclick=()=>mutate({operation:'scale-'+button.dataset.scaleAction,geom:button.dataset.scaleGeom});
}
