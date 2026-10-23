// Temporary DOM drafts belong to a step/axis object, not its current index.
// They never enter saved study definitions or native requests.
const stageKey=(id,index)=>id.replace(new RegExp(`^study-(step|geometry|member)-${index}-`),'study-$1-@-');
const axisKey=(id,index)=>id.replace(new RegExp(`^(study-(?:values|value|axis-search|axis-element|from|to|count))-${index}(?=-|$)`),'$1-@');
function snapshot(host,key,accept){
 return {fields:[...host.querySelectorAll('input[id],textarea[id],select[id]')].filter(el=>accept(el.id)).map(el=>({key:key(el.id),value:el.value,...el.multiple?{selected:[...el.selectedOptions].map(o=>o.value)}:{}})),open:host.open,details:[...host.querySelectorAll('details')].map(el=>el.open)};
}
function restore(host,data,key){
 if(!data)return;
 if(typeof data.open==='boolean')host.open=data.open;
 const fields=new Map(data.fields.map(field=>[field.key,field]));
 for(const el of host.querySelectorAll('input[id],textarea[id],select[id]')){
  const field=fields.get(key(el.id));if(!field)continue;
  if(field.selected){for(const option of el.options)option.selected=field.selected.includes(option.value);}
  else el.value=field.value;
 }
 [...host.querySelectorAll('details')].forEach((el,i)=>{if(i<data.details.length)el.open=data.details[i];});
}
export function rememberStudyForms(host,stages,axes){
 const steps=[...host.querySelectorAll('.study-step')],sweeps=[...host.querySelectorAll('.study-axis')];
 return {stages:new Map(stages.map((stage,i)=>[stage,snapshot(steps[i],id=>stageKey(id,i),id=>new RegExp(`^study-(step|geometry|member)-${i}-`).test(id))])),axes:new Map(axes.map((axis,i)=>[axis,snapshot(sweeps[i],id=>axisKey(id,i),id=>axisKey(id,i)!==id)]))};
}
export function restoreStudyForms(host,stages,axes,drafts){
 if(!drafts)return;
 const steps=[...host.querySelectorAll('.study-step')],sweeps=[...host.querySelectorAll('.study-axis')];
 stages.forEach((stage,i)=>restore(steps[i],drafts.stages.get(stage),id=>stageKey(id,i)));
 axes.forEach((axis,i)=>restore(sweeps[i],drafts.axes.get(axis),id=>axisKey(id,i)));
}
