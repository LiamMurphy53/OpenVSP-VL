import assert from 'node:assert/strict';
import {draftSliderParameter,draftSliderField,bindDraftSliders} from '../web/draft-sliders.js';

// The draft's raw text remains authoritative, even when the browser's range
// control needs a valid fallback. Rendering must not repair an invalid draft.
for(const value of ['', '1.25', '0.25000000000001']){
 const p=draftSliderParameter('U','u',value,{min:0,max:1});
 assert.match(draftSliderField(p,value,String),new RegExp('max="1" value="'+value+'"'));
 assert.ok(p.value>=0&&p.value<=1);
}
const p=draftSliderParameter('Span (%)','span',20,{min:0,max:100});
const input=new EventTarget();input.value='20';
const slider={dataset:{customSlider:'span'},value:'32.5',disabled:false};
let sliderValue=slider.value;
Object.defineProperty(slider,'value',{get:()=>sliderValue,set:value=>{sliderValue=String(value);}});
const low={},high={},events=[];
const wrapper={dataset:{sliderKey:'draft:span'},querySelector:s=>s==='[data-custom-slider]'?slider:s==='[data-slider-low]'?low:high,querySelectorAll:()=>[]};
const host={querySelectorAll:()=>[wrapper],querySelector:()=>input};
for(const name of ['input','change'])input.addEventListener(name,e=>events.push([e.type,input.value,e.bubbles]));
bindDraftSliders(host,[p]);
slider.oninput();assert.deepEqual(events,[['input','32.5',true]]);
slider.onpointerup();slider.onchange();slider.onblur();
assert.deepEqual(events,[['input','32.5',true],['change','32.5',true]],'A release notifies saved-draft listeners once');
input.value='47.1234567890123';input.dispatchEvent(new Event('input'));
assert.equal(input.value,'47.1234567890123','Exact text is not rounded by slider synchronization');
assert.equal(Number(slider.value),47.123456789);
input.value='';input.dispatchEvent(new Event('input'));assert.equal(input.value,'');
assert.equal(Number(slider.value),47.123456789,'A blank draft does not silently become zero');
const count=events.length;slider.disabled=true;slider.oninput();slider.onchange();assert.equal(events.length,count);
console.log('Draft sliders retain exact/invalid text and notify existing input/change listeners without duplicate release.');
