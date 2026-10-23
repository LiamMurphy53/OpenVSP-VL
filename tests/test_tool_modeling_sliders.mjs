import assert from 'node:assert/strict';
// Skinning angles use the selected display unit; the native request stays degrees.
globalThis.localStorage={getItem:()=>JSON.stringify({base:'ft',length:'ft',angle:'rad'})};
const {skinningField,bindSkinning}=await import('../web/skinning-controls.js');
const {propCurveSliderParameters,propCurveSliderMarkup,propCurveRequest,bindPropCurveSliders}=await import('../web/prop-curve-sliders.js');
const base={id:'angle',type:0,value:0,min:-180,max:180,active:true,dimension:'angle',label:'Top before tangent angle'};
assert.match(skinningField(base,String),/Top before tangent angle slider/);
assert.match(skinningField({...base,userLocked:true},String),/type="range"[^>]*disabled/);
assert.match(skinningField({...base,displayReadOnly:true},String),/type="range"[^>]*disabled/);
assert.doesNotMatch(skinningField({...base,type:2},String),/type="range"/);
const input={dataset:{skinParam:base.id},value:'0'},slider={dataset:{customSlider:'skin-param-angle'},value:String(Math.PI/6),disabled:false};
const wrapper={dataset:{sliderKey:'skin:angle'},querySelector:()=>slider,querySelectorAll:()=>[]};
const host={querySelector:s=>s.startsWith('[data-skin-reset')?{}:input,querySelectorAll:s=>s==='[data-skin-param]'?[input]:[wrapper]};
const skinCalls=[];
bindSkinning(host,{id:'body',params:[base]},{skinControls:{},surface:0,index:2},{mutate:assert.fail,toast:assert.fail,liveEdit:(...args)=>skinCalls.push(args)});
slider.oninput();slider.onpointerup();slider.onchange();slider.onblur();
assert.equal(skinCalls.length,2);assert.equal(skinCalls[0][3],false);assert.equal(skinCalls[1][3],true);
assert.ok(Math.abs(skinCalls[0][2].value-30)<1e-12);
assert.deepEqual(skinCalls[0][2],{operation:'parameter',id:'angle',value:skinCalls[0][2].value});

const curve={name:'PROP_CHORD',label:'Chord ratio',dimension:null,stations:[.2,.6,1],values:[.1,.2,.1],
 pointControls:[0,1,2].map(i=>({station:'r'+i,value:'c'+i,stationActive:i===1,valueActive:true}))};
const component={id:'prop',params:curve.pointControls.flatMap((p,i)=>[
 {id:p.station,name:'Radius',type:0,value:curve.stations[i],min:0,max:1},
 {id:p.value,name:'Chord',type:0,value:curve.values[i],min:0,max:10,userLocked:i===2}])};
const parameters=propCurveSliderParameters(component,curve);
assert.equal(parameters.length,6);
assert.match(propCurveSliderMarkup(parameters[0],String),/type="range"[^>]*disabled/);
assert.match(propCurveSliderMarkup(parameters[5],String),/type="range"[^>]*disabled/);
assert.notEqual(parameters[0].customSlider.key,propCurveSliderParameters({...component,id:'another'},curve)[0].customSlider.key);
const fields=new Map(parameters.map(p=>[p.fieldId,{value:String(p.value)}]));
const p=parameters.find(p=>p.kind==='value'&&p.index===1),propSlider={dataset:{customSlider:p.fieldId},value:'.25',disabled:false};
const propWrapper={dataset:{sliderKey:p.customSlider.key},querySelector:()=>propSlider,querySelectorAll:()=>[]};
const propHost={querySelector:s=>fields.get(s.match(/id="([^"]+)"/)[1]),querySelectorAll:()=>[propWrapper]};
const calls=[],errors=[];
bindPropCurveSliders(propHost,component,curve,parameters,{mutate:assert.fail,liveEdit:(...args)=>calls.push(args),toast:e=>errors.push(e)});
propSlider.oninput();assert.deepEqual(calls[0][2].values,[.1,.25,.1]);assert.equal(calls[0][3],false);
// Busy-disabled numeric inputs still contain the in-progress gesture.
for(const field of fields.values())field.disabled=true;
propSlider.value='.3';propSlider.oninput();propSlider.onpointerup();propSlider.onchange();
assert.equal(calls.length,3);assert.equal(calls[2][3],true);assert.deepEqual(calls[2][2].values,[.1,.3,.1]);
fields.get('tool-prop-value-2').value='999';
assert.equal(propCurveRequest(propHost,component,curve,parameters).values[2],.1,'User-locked point remains unchanged');
fields.get('tool-prop-value-1').value='';assert.throws(()=>propCurveRequest(propHost,component,curve,parameters),/finite/);
fields.get('tool-prop-value-1').value='20';assert.throws(()=>propCurveRequest(propHost,component,curve,parameters),/limits/);
fields.get('tool-prop-value-1').value='.3';fields.get('tool-prop-station-1').value='.1';
assert.throws(()=>propCurveRequest(propHost,component,curve,parameters),/increase/);
// Finish the last valid native preview if a companion draft becomes invalid.
propSlider.value='.4';propSlider.oninput();propSlider.onpointerup();
assert.equal(calls.length,4);assert.equal(calls[3][3],true);assert.deepEqual(calls[3][2].values,[.1,.3,.1]);assert.equal(errors.length,1);
console.log('Modeling-tool sliders: live native requests, radians, locks, valid companion values and single gesture completion passed.');
