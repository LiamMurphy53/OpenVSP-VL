import {customSliderMarkup,bindCustomSliders} from './custom-sliders.js?v=20261022-drafts';

const locked=p=>p.active===false||p.displayReadOnly||p.userLocked;
const units={displayValue:x=>x,parameterDimension:()=>null,readOnly:locked};
export function propCurveSliderParameters(component,curve){
 const byID=new Map(component.params.map(p=>[p.id,p]));
 return curve.pointControls.flatMap((control,index)=>['station','value'].flatMap(kind=>{
  const p=byID.get(control[kind]);if(!p)return [];
  return [{...p,kind,index,fieldId:`tool-prop-${kind}-${index}`,
   label:kind==='station'?`Radius fraction ${index}`:`${curve.label} ${index}`,
   active:p.active!==false&&control[kind+'Active'],
   customSlider:{key:`tool-prop:${component.id}:${curve.name}:${kind}:${index}`,range:Math.min(p.max-p.min,Math.max(Math.abs(p.value)*.5,kind==='value'&&curve.dimension==='angle'?10:.1)),adjustable:true}}];
 }));
}
export function propCurveSliderMarkup(parameter,esc){
 return parameter?customSliderMarkup(parameter,parameter.fieldId,{...units,esc}):'';
}
export function propCurveRequest(host,component,curve,parameters){
 const data={stations:[...curve.stations],values:[...curve.values]};
 for(const p of parameters){
  if(locked(p))continue;
  const input=host.querySelector(`[id="${p.fieldId}"]`),value=Number(input.value);
  if(!input.value.trim()||!Number.isFinite(value))throw Error('Enter finite blade-curve values.');
  if(value<p.min||value>p.max)throw Error('Keep blade-curve values within the native limits.');
  data[p.kind==='station'?'stations':'values'][p.index]=value;
 }
 if(data.stations.some((value,index)=>value<0||value>1||(index&&value<=data.stations[index-1])))throw Error('Radius fractions must increase from root to tip, between zero and one.');
 return {operation:'prop-curve-set',geom:component.id,curve:curve.name,...data};
}
export function bindPropCurveSliders(host,component,curve,parameters,{liveEdit,mutate,toast,isBusy=()=>false}){
 let lastRequest=null;
 bindCustomSliders(host,parameters,{...units,isBusy,liveEdit:(p,slider,value,finished)=>{
  if(locked(p))return;
  let request;
  try{request=propCurveRequest(host,component,curve,parameters);}
  catch(error){
   if(finished){toast(error.message);if(lastRequest&&liveEdit)return liveEdit(`prop-curve:${component.id}:${curve.name}`,slider,lastRequest,true);}
   return;
  }
  lastRequest=request;
  if(liveEdit)return liveEdit(`prop-curve:${component.id}:${curve.name}`,slider,request,finished);
  if(finished&&!isBusy())return mutate(request);
 }});
}
