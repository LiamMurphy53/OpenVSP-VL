import {customSliderMarkup,bindCustomSliders} from './custom-sliders.js?v=20261021-more';
export function cstSliderParameters(component,section){
 if(!section.cst)return [];
 return ['upper','lower'].flatMap(side=>section.cst[side].map((value,index)=>({
  id:`cst:${component.id}:${section.surface}:${section.index}:${side}:${index}`,
  name:`${side==='upper'?'Upper':'Lower'} coefficient ${index}`,side,index,value,
  type:0,min:-1e12,max:1e12,customSlider:{key:`cst:${component.id}:${section.surface}:${section.index}:${side}:${index}`,range:Math.max(.1,Math.abs(value)*.5),adjustable:true}
 })));
}
const units={displayValue:x=>x,parameterDimension:()=>null};
export function cstSliderMarkup(parameter,esc){
 return customSliderMarkup(parameter,`cst-${parameter.side}-${parameter.index}`,{...units,esc,readOnly:()=>false});
}
export function cstRequest(host,section,common){
 const values=Object.fromEntries(['upper','lower'].map(side=>[side,section.cst[side].map((_,i)=>{
  const input=host.querySelector(`#cst-${side}-${i}`);
  if(!input?.value.trim()||!Number.isFinite(Number(input.value)))throw Error('Enter finite CST coefficients.');
  return Number(input.value);
 })]));
 return {...common,operation:'cst-coefficients',...values};
}
export function bindCstSliders(host,component,section,common,{liveEdit,mutate,toast,isBusy}){
 if(!section.cst)return;
 bindCustomSliders(host,cstSliderParameters(component,section),{...units,isBusy,
  liveEdit:(p,slider,value,finished)=>{
   try{const request=cstRequest(host,section,common);return liveEdit?liveEdit(p.id,slider,request,finished):finished?mutate(request):undefined;}
   catch(error){toast(error.message);}
  }});
}
