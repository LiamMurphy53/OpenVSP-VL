export function customActionsMarkup(c,E,parameterField){
 const groups=new Map();
 for(const control of c.customExternalControls||[]){
  const key=control.tabIndex??'ungrouped';
  if(!groups.has(key))groups.set(key,{title:control.tab||'Component controls',controls:[]});
  groups.get(key).controls.push(control);
 }
 const external=[...groups].map(([key,group])=>`<details class="parameter-group geometry-primary" data-group="custom-external-${E(String(key))}" open><summary>${E(group.title)}</summary>${group.controls.map(control=>`<div data-custom-external-control="${control.index}"><p>${E(control.owner)}</p>${parameterField(control.parameter).replaceAll(`parm-${control.parameter.id}`,`external-${c.id}-${control.index}`).replaceAll('data-parm="','data-custom-external="').replaceAll('data-parm-trigger="','data-custom-external-trigger="')}</div>`).join('')}</details>`).join('');
 return external+(c.customActions?.length?`<details class="parameter-group geometry-primary" data-group="custom-actions" open><summary>Component actions</summary>${c.customActions.map(a=>`<button type="button" data-custom-action="${a.index}">${E(a.label)}</button>`).join('')}</details>`:'');
}

export function bindCustomActions(host,c,mutate,units){host.querySelectorAll('[data-custom-external-control]').forEach(wrapper=>{const index=Number(wrapper.dataset.customExternalControl),control=c.customExternalControls.find(x=>x.index===index),p=control.parameter,input=wrapper.querySelector('[data-custom-external]'),trigger=wrapper.querySelector('[data-custom-external-trigger]');let pending=false;const commit=async()=>{if(pending||units.isBusy()||p.displayReadOnly||p.active===false)return;const value=trigger?1:units.nativeValue(Number(input.value),units.parameterDimension(p));if(!trigger&&(!input.value.trim()||!Number.isFinite(value))){units.toast('Enter a finite number.');return;}if(value===p.value&&!trigger)return;pending=true;try{return await mutate({operation:'custom-control-parameter',geom:c.id,index,id:p.id,value});}finally{pending=false;}};if(trigger)trigger.onclick=commit;if(input){input.onchange=commit;input.onblur=commit;input.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();input.blur();}};}});host.querySelectorAll('[data-custom-action]').forEach(button=>button.onclick=()=>mutate({operation:'custom-trigger',geom:c.id,index:Number(button.dataset.customAction)}));}
