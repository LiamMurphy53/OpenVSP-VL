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

const endings=[];
bindCustomSliders(host,[ordinary],{displayValue:x=>x,parameterDimension:()=>null,isBusy:()=>false,liveEdit:(p,el,value,finished)=>endings.push({value,finished})});
slider.value='10';slider.oninput();slider.value='11';slider.oninput();slider.value='10';slider.oninput();
slider.onpointerup();slider.onchange();slider.onblur();
assert.equal(endings.filter(e=>e.finished).length,1,'Returning to original value still ends drag exactly once');
assert.deepEqual(endings.at(-1),{value:10,finished:true});
slider.value='12';slider.oninput();slider.onblur();slider.onchange();
assert.equal(endings.filter(e=>e.finished).length,2,'Focus loss ends an active edit without duplicate change');
slider.value='13';slider.oninput();slider.onpointercancel();slider.onpointerup();
assert.equal(endings.filter(e=>e.finished).length,3,'Lost pointer capture ends the active edit once');
slider.disabled=true;slider.onblur();slider.onpointerup();slider.onchange();
assert.equal(endings.filter(e=>e.finished).length,3,'Disabled controls do not send final edits');

slider.disabled=false;slider.value='14';slider.oninput();slider.isConnected=false;slider.onblur();slider.onpointerup();
assert.equal(endings.filter(e=>e.finished).length,3,'A removed control cannot start another edit during error recovery');

// Original native type 3 is a continuous fraction; type 4 is a limited integer.
for(const type of [3,4]){
 const added={id:'extra-'+type,name:'Resolution',type,value:33,min:2,max:1001};
 assert.ok(sliderParameter(added).customSlider);
 const markup=customSliderMarkup(added,'extra',{esc:String,displayValue:x=>x,parameterDimension:()=>null,readOnly:p=>!p.active});
 assert.match(markup,type===4?/step="1"/:/step="any"/);
 assert.match(markup,/disabled/,'Native locks also apply to added parameter types');
 assert.doesNotMatch(customSliderMarkup({...added,active:true},'extra',{esc:String,displayValue:x=>x,parameterDimension:()=>null,readOnly:p=>!p.active}),/disabled/);
}
for(const type of [2,5,6])assert.equal(sliderParameter({...ordinary,type}).customSlider,undefined,'Do not invent steps for boolean, non-equal, or power-integer parameters');

// Draft-only editors must not reset unsaved values when resizing a range.
const draftEvents={},draftInput={value:'6.096',addEventListener:(name,callback)=>draftEvents[name]=callback};
const narrow={dataset:{sliderResize:'0.5'}},wide={dataset:{sliderResize:'2'}},low={},high={};
const draftSlider={dataset:{customSlider:'draft'},value:'3.048',disabled:false};
const draftWrapper={dataset:{sliderKey:'native:draft'},querySelector:selector=>selector==='[data-custom-slider]'?draftSlider:selector==='[data-slider-low]'?low:high,querySelectorAll:()=>[narrow,wide]};
const draftHost={querySelectorAll:()=>[draftWrapper],querySelector:()=>draftInput};
bindCustomSliders(draftHost,[{...ordinary,id:'draft'}],{displayValue:x=>x*.3048,parameterDimension:()=> 'length',isBusy:()=>false});
narrow.onclick();assert.equal(draftInput.value,'6.096');assert.equal(draftSlider.value,6.096,'Resizing centers on the edited native value, preserving display units');
draftInput.value='30.48';draftEvents.input();assert.equal(draftSlider.value,30.48);assert.ok(draftSlider.max>=30.48,'Exact entry beyond the old range expands its window');
wide.onclick();assert.equal(draftInput.value,'30.48');assert.equal(draftSlider.value,30.48);
const before={min:draftSlider.min,max:draftSlider.max,value:draftSlider.value};draftInput.value='';narrow.onclick();assert.deepEqual({min:draftSlider.min,max:draftSlider.max,value:draftSlider.value},before,'Incomplete entry is left intact');
assert.equal(draftInput.value,'');
