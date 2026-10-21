import assert from 'node:assert/strict';
import {preserveInspectorView} from '../web/inspector-view.js';
// Model replaced DOM nodes without requiring a browser; focus must target the
// replacement in the same group, and never leak to a different component/tab.
const group=name=>({dataset:{group:name}});
function range(key,owner,disabled=false){
 const wrapper={dataset:{sliderKey:key},closest:()=>group(owner)};
 const input={disabled,matches:()=>true,closest:selector=>selector==='[data-slider-key]'?wrapper:group(owner),focus(options){this.focusOptions=options;document.activeElement=this;}};
 wrapper.querySelector=()=>input;return {wrapper,input};
}
const detail=(name,open)=>({id:name,dataset:{},open});
let details=[detail('advanced',true)],ranges=[range('native:width','section')];
const scroller={scrollTop:240,scrollLeft:7};
const host={dataset:{viewContext:'wing/sections'},closest:()=>scroller,contains:el=>ranges.some(r=>r.input===el),querySelectorAll:selector=>selector==='details'?details:ranges.map(r=>r.wrapper)};
globalThis.document={activeElement:ranges[0].input};
let restore=preserveInspectorView(host,'wing/sections');
details=[detail('advanced',false)];ranges=[range('native:width','other'),range('native:width','section')];scroller.scrollTop=0;scroller.scrollLeft=0;
restore();assert.equal(details[0].open,true);assert.equal(document.activeElement,ranges[1].input);assert.deepEqual(ranges[1].input.focusOptions,{preventScroll:true});assert.equal(scroller.scrollTop,240);assert.equal(scroller.scrollLeft,7);
restore=preserveInspectorView(host,'wing/sections');ranges=[range('native:width','section',true)];const oldFocus=document.activeElement;restore();assert.equal(document.activeElement,oldFocus,'Do not focus a newly computed/locked field');
restore=preserveInspectorView(host,'other-wing/sections');details=[detail('advanced',false)];scroller.scrollTop=0;restore();assert.equal(details[0].open,false);assert.equal(scroller.scrollTop,0);assert.equal(host.dataset.viewContext,'other-wing/sections');
// Tool panels have no parameter-group wrapper; stable native IDs still restore.
ranges=[range('native:width','')];document.activeElement=ranges[0].input;
restore=preserveInspectorView(host,'other-wing/sections');ranges=[range('native:width','')];restore();assert.equal(document.activeElement,ranges[0].input);
console.log('Replacement slider focus, disabled guards, disclosure/scroll and component/tab isolation passed.');
