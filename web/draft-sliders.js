import {customSliderMarkup,bindCustomSliders} from './custom-sliders.js?v=20261022-drafts';

// Creation and query fields stay drafts until their existing action is used.
// Bounds are supplied by each editor in its own units, never inferred by name.
export function draftSliderParameter(label,id,value,{min,max}){
 const number=String(value).trim()?Number(value):NaN;
 return {id,name:label,type:0,min,max,value:Number.isFinite(number)?Math.min(max,Math.max(min,number)):min,
  customSlider:{key:'draft:'+id,range:max-min,adjustable:false}};
}
export function draftSliderField(parameter,value,esc){
 const p=parameter;
 return `<label class="tool-field">${esc(p.name)}<input id="${esc(p.id)}" aria-label="${esc(p.name)}" type="number" step="any" min="${p.min}" max="${p.max}" value="${esc(value)}">${customSliderMarkup(p,p.id,{esc,displayValue:x=>x,parameterDimension:()=>null,readOnly:()=>false})}</label>`;
}
export function bindDraftSliders(host,parameters){
 bindCustomSliders(host,parameters,{displayValue:x=>x,parameterDimension:()=>null,isBusy:()=>false,
  liveEdit:(p,slider,value,finished)=>{
   const input=host.querySelector(`[id="${p.id}"]`);
   // Notify existing draft listeners too, including those installed with
   // addEventListener rather than an onchange property.
   input.dispatchEvent(new Event(finished?'change':'input',{bubbles:true}));
  }});
}
