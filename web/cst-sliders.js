import {customSliderMarkup,bindCustomSliders} from './custom-sliders.js?v=20261022-drafts';
export function cstEditorMarkup(component,section,{card,field,button,E}){
 if(section.generated||(!section.cst&&!section.cstFitAllowed))return '';
 const coefFields=side=>`<h3>${side==='upper'?'Upper':'Lower'} surface · degree ${section.cst[side].length-1}</h3><div class="tool-fields cst-coefficients">${cstSliderParameters(component,section).filter(p=>p.side===side).map(p=>`<div>${field(p.name,`cst-${side}-${p.index}`,p.value)}${cstSliderMarkup(p,E)}</div>`).join('')}</div><div class="tool-actions"><button data-cst-degree="${side}" data-direction="promote">Increase ${side} degree</button><button data-cst-degree="${side}" data-direction="demote" ${section.cst[side].length===1?'disabled':''}>Reduce ${side} degree</button></div>`;
 return card('CST airfoil',`<p>CST describes each side with coefficients. Native fitting approximates the current profile; compare the result before using it.</p>${section.cst?`${coefFields('upper')}${coefFields('lower')}<div class="tool-actions">${button('apply-cst','Apply coefficients',true)}</div><p class="native-tip">OpenVSP applies its leading-edge and continuity constraints. Reducing the degree can change the shape.</p>`:`<div class="inline-fields">${field('Fitting degree (1–20)','cst-degree',8)}${button('fit-cst','Fit current profile to CST',true)}</div>`}`,'wide');
}

export function cstSliderParameters(component,section){
 if(!section.cst)return [];
 return ['upper','lower'].flatMap(side=>section.cst[side].map((value,index)=>({
  id:`cst:${component.id}:${section.surface}:${section.index}:${side}:${index}`,
  name:`${side==='upper'?'Upper':'Lower'} coefficient ${index}`,side,index,value,
  type:0,min:-1e12,max:1e12,customSlider:{key:`cst:${component.id}:${section.surface}:${section.index}:${side}:${index}`,range:Math.max(.1,Math.abs(value)*.5),adjustable:true}
 })));
}
const units={displayValue:x=>x,parameterDimension:()=>null};
export function cstSliderMarkup(parameter,esc,prefix='cst'){
 return customSliderMarkup(parameter,`${prefix}-${parameter.side}-${parameter.index}`,{...units,esc,readOnly:()=>false});
}
export function cstRequest(host,section,common,{prefix='cst',operation='cst-coefficients'}={}){
 const values=Object.fromEntries(['upper','lower'].map(side=>[side,section.cst[side].map((_,i)=>{
  const input=host.querySelector(`#${prefix}-${side}-${i}`);
  if(!input?.value.trim()||!Number.isFinite(Number(input.value)))throw Error('Enter finite CST coefficients.');
  return Number(input.value);
 })]));
 return {...common,operation,...values};
}
export function bindCstSliders(host,component,section,common,{liveEdit,mutate,toast,isBusy,prefix='cst',operation='cst-coefficients'}){
 if(!section.cst)return;
 bindCustomSliders(host,cstSliderParameters(component,section),{...units,isBusy,
  liveEdit:(p,slider,value,finished)=>{
   try{const request=cstRequest(host,section,common,{prefix,operation});return liveEdit?liveEdit(p.id,slider,request,finished):finished?mutate(request):undefined;}
   catch(error){toast(error.message);}
  }});
}
