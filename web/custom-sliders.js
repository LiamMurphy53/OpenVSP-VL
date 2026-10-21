// Slider windows are presentation state in native units. Setters and geometry
// remain in the existing validated native parameter transaction.
const windows=new Map();
const integer=p=>[1,4,6].includes(p.type);
const compact=value=>Number(value.toPrecision(12));
export function sliderParameter(p){
 if(p.customSlider)return p;
 if(![0,1].includes(p.type)||p.choices||p.trigger||![p.value,p.min,p.max].every(Number.isFinite)||p.min>=p.max)return p;
 const span=p.max-p.min,range=span<=360?span:Math.max(Math.abs(p.value)*.5,p.type===1?10:1);
 return {...p,customSlider:{key:'native:'+p.id,range,adjustable:true}};
}
export function sliderWindow(p,previous){
 const range=p.customSlider?.range;
 if(!Number.isFinite(range)||range<=0||![p.value,p.min,p.max].every(Number.isFinite))return null;
 let low=previous?.low,high=previous?.high;
 if(!(low<high)||p.value<low||p.value>high){low=p.value-range;high=p.value+range;}
 low=Math.max(low,p.min);high=Math.min(high,p.max);
 if(integer(p)){low=Math.ceil(low);high=Math.floor(high);}
 return low<high?{low,high}:null;
}
export function resizeSliderWindow(p,current,factor){
 if(!Number.isFinite(factor)||factor<=0)return current;
 const span=(current.high-current.low)*factor/2;
 return sliderWindow({...p,customSlider:{...p.customSlider,range:Math.max(integer(p)?1:0,span)}},null)||current;
}
export function customSliderMarkup(p,fieldId,{esc,displayValue,parameterDimension,readOnly}){
 p=sliderParameter(p);
 if(!p.customSlider)return '';
 const key=p.customSlider.key,bounds=sliderWindow(p,windows.get(key));if(!bounds)return '';
 windows.set(key,bounds);
 const dimension=parameterDimension(p),convert=x=>compact(displayValue(x,dimension)),label=p.label||p.name;
 return `<div class="custom-slider" data-slider-key="${esc(key)}"><input type="range" data-custom-slider="${esc(fieldId)}" aria-label="${esc(label)} slider" min="${convert(bounds.low)}" max="${convert(bounds.high)}" step="${integer(p)?displayValue(1,dimension):'any'}" value="${convert(p.value)}" ${readOnly(p)?'disabled':''}><div class="custom-slider-range"><small data-slider-low>${convert(bounds.low)}</small>${p.customSlider.adjustable?`<div><button type="button" data-slider-resize="0.5" aria-label="Narrow ${esc(label)} slider range" ${readOnly(p)?'disabled':''}>−</button><button type="button" data-slider-resize="2" aria-label="Widen ${esc(label)} slider range" ${readOnly(p)?'disabled':''}>+</button></div>`:''}<small data-slider-high>${convert(bounds.high)}</small></div></div>`;
}
export function bindCustomSliders(host,parameters,{displayValue,parameterDimension,isBusy,liveEdit}){
 const byKey=new Map(parameters.map(sliderParameter).filter(p=>p.customSlider).map(p=>[p.customSlider.key,p]));
 for(const wrapper of host.querySelectorAll('[data-slider-key]')){
  const key=wrapper.dataset.sliderKey,p=byKey.get(key);if(!p)continue;
  const slider=wrapper.querySelector('[data-custom-slider]'),input=host.querySelector(`[id="${slider.dataset.customSlider}"]`);
  if(!input)continue;
  const dimension=parameterDimension(p),convert=x=>compact(displayValue(x,dimension));
  let editing=false,lastFinishedValue=null;
  const finish=()=>{
   if(slider.disabled||slider.isConnected===false||(!editing&&lastFinishedValue===slider.value))return;
   editing=false;lastFinishedValue=slider.value;input.value=slider.value;
   if(liveEdit)return liveEdit(p,slider,Number(slider.value),true);
   if(!isBusy())return input.onchange?.();
  };
  slider.oninput=()=>{if(!slider.disabled){editing=true;input.value=slider.value;if(liveEdit)return liveEdit(p,slider,Number(slider.value),false);}};
  slider.onchange=finish;
  // A drag can return to its starting value, or lose focus/capture before
  // change arrives. Finish once, without depending on browser event order.
  slider.onpointerup=()=>{if(editing&&liveEdit)return finish();};
  slider.onpointercancel=()=>{if(editing&&liveEdit)return finish();};
  slider.onblur=()=>{if(editing&&liveEdit)return finish();};
  for(const button of wrapper.querySelectorAll('[data-slider-resize]'))button.onclick=()=>{
   if(isBusy()||slider.disabled)return;
   const current=windows.get(key)||sliderWindow(p);if(!current)return;
   const next=resizeSliderWindow(p,current,Number(button.dataset.sliderResize));windows.set(key,next);
   slider.min=convert(next.low);slider.max=convert(next.high);slider.value=convert(p.value);
   input.value=convert(p.value);
   wrapper.querySelector('[data-slider-low]').textContent=convert(next.low);
   wrapper.querySelector('[data-slider-high]').textContent=convert(next.high);
  };
 }
}
