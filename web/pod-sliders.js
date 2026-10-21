import {customSliderMarkup,bindCustomSliders} from './custom-sliders.js?v=20261021-more';
export function podSliderParameters(c){
 if(c.type.toUpperCase()!=='POD')return [];
 const length=c.params.find(p=>p.rawGroup==='Design'&&p.name==='Length'),ratio=c.params.find(p=>p.rawGroup==='Design'&&p.name==='FineRatio');
 if(!length||!ratio||!(length.value>0)||!(ratio.value>0)||!(ratio.min>0))return [];
 const active=ratio.active!==false&&!ratio.userLocked&&!ratio.readOnlyReason;
 return [
  {control:'diameter',name:'Pod diameter',dimension:'length',value:2*length.value/ratio.value,min:2*length.value/ratio.max,max:2*length.value/ratio.min},
  {control:'fineness',name:'Fineness ratio',dimension:null,value:ratio.value/2,min:ratio.min/2,max:ratio.max/2}
 ].map(p=>({...p,id:ratio.id,type:0,active,length:length.value,customSlider:{key:`pod:${c.id}:${p.control}`,range:Math.max(p.value*.5,.01),adjustable:true}}));
}
export function podSliderMarkup(c,control,options){const p=podSliderParameters(c).find(p=>p.control===control);return p?customSliderMarkup(p,'pod-'+control,{...options,parameterDimension:p=>p.dimension,readOnly:p=>!p.active}):'';}
export function bindPodSliders(host,c,{displayValue,nativeValue,isBusy,liveEdit}){
 bindCustomSliders(host,podSliderParameters(c),{displayValue,parameterDimension:p=>p.dimension,isBusy,liveEdit:(p,slider,value,finished)=>{
  const native=nativeValue(value,p.dimension),ratio=p.control==='diameter'?2*p.length/native:2*native;
  if(Number.isFinite(ratio))return liveEdit(p.id,slider,{operation:'parameter',id:p.id,value:ratio},finished);
 }});
}
