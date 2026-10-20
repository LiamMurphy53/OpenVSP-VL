import assert from 'node:assert/strict';
import {sliderWindow,resizeSliderWindow,customSliderMarkup,sliderParameter,bindCustomSliders} from '../web/custom-sliders.js';
const p={id:'native-id',name:'Length',value:5,min:0,max:100,type:0,customSlider:{key:'component:1:native-id',range:10,adjustable:true}};
assert.deepEqual(sliderWindow(p),{low:0,high:15});
assert.deepEqual(sliderWindow({...p,value:8},{low:0,high:15}),{low:0,high:15},'Do not recenter on every saved edit');
assert.deepEqual(sliderWindow({...p,value:30},{low:0,high:15}),{low:20,high:40});
assert.deepEqual(resizeSliderWindow(p,{low:0,high:15},.5),{low:1.25,high:8.75});
assert.deepEqual(sliderWindow({...p,type:1,value:2,min:1.2,max:4.8,customSlider:{range:10}}),{low:2,high:4});
assert.equal(sliderWindow({...p,customSlider:{range:0}}),null);
const units={esc:String,displayValue:x=>x*.3048,parameterDimension:()=> 'length',readOnly:p=>p.active===false};
const html=customSliderMarkup(p,'field',units);
assert.match(html,/min="0" max="4.572"/);assert.match(html,/value="1.524"/);
assert.match(html,/Narrow Length slider range/);
assert.match(customSliderMarkup({...p,active:false},'locked',units),/disabled/);
assert.doesNotMatch(customSliderMarkup({...p,customSlider:{...p.customSlider,key:'plain',adjustable:false}},'plain',units),/data-slider-resize/);
console.log('Native windows, units, integer limits, range adjustment and disabled controls passed.');

const ordinary={id:'length',name:'Length',value:10,min:0,max:1e12,type:0};
assert.ok(sliderParameter(ordinary).customSlider);
assert.equal(sliderParameter({...ordinary,type:2}).customSlider,undefined);
assert.equal(sliderParameter({...ordinary,choices:[]}).customSlider,undefined);
let live=[];const input={value:''},slider={dataset:{customSlider:'field'},value:'11',disabled:false};
const wrapper={dataset:{sliderKey:'native:length'},querySelector:()=>slider,querySelectorAll:()=>[]};
const host={querySelectorAll:()=>[wrapper],querySelector:()=>input};
bindCustomSliders(host,[ordinary],{displayValue:x=>x,parameterDimension:()=>null,isBusy:()=>false,liveEdit:(p,el,value,finished)=>live.push({value,finished})});
slider.oninput();assert.deepEqual(live,[{value:11,finished:false}],'Send native update during input, before release');
slider.onchange();assert.equal(live[1].finished,true);
slider.disabled=true;slider.oninput();assert.equal(live.length,2,'Locked controls do not send live edits');

// Modeling-tool sliders retain exact entry and commit through its native handler on release.
let releases=0;
input.onchange=()=>{releases++;};
bindCustomSliders(host,[ordinary],{displayValue:x=>x,parameterDimension:()=>null,isBusy:()=>false});
slider.disabled=false;slider.value='12.5';slider.oninput();
assert.equal(input.value,'12.5');assert.equal(releases,0);
slider.onchange();assert.equal(releases,1);

// Tool parameters use native units and IDs, including parameters outside the selected geometry.
const toolEvents=[];
bindCustomSliders(host,[ordinary],{displayValue:x=>x,parameterDimension:()=>null,isBusy:()=>false,liveEdit:(p,el,value,finished)=>toolEvents.push({operation:'parameter',id:p.id,value,finished})});
slider.value='13.75';slider.oninput();slider.onchange();
assert.deepEqual(toolEvents,[{operation:'parameter',id:'length',value:13.75,finished:false},{operation:'parameter',id:'length',value:13.75,finished:true}]);
