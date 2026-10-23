import assert from 'node:assert/strict';
import {tireInspectionSliders,tireInspectionValue} from '../web/gear-tire.js';
import {customSliderMarkup} from '../web/custom-sliders.js';
import {canReplaceGeometry} from '../web/geometry-preview-update.js';
const fields=tireInspectionSliders('gear');
assert.deepEqual(fields.map(p=>[p.id,p.min,p.max]),[['fraction',0,1]]);
for(const p of fields){const html=customSliderMarkup(p,p.id,{esc:String,displayValue:x=>x,parameterDimension:()=>null,readOnly:p=>!p.active});assert.match(html,/type="range"/);assert.doesNotMatch(html,/data-slider-resize/);}
const input={value:'0.325',min:'0',max:'1',disabled:false};assert.equal(tireInspectionValue(input,'fraction'),.325);
for(const value of ['', 'NaN','1.01','-.01'])assert.throws(()=>tireInspectionValue({...input,value},'fraction'),/between/);
assert.equal(tireInspectionValue({...input,value:'',disabled:true},'fraction'),0,'An unused draft does not block another native pose');
const mesh={geometryPreview:true,nodes:[[0,0,0],[1,0,0],[0,1,0]],nodeIDs:['a','b','c'],elements:[{id:1,kind:'face',nodes:[0,1,2],group:0}],groups:[{id:0,name:'Tire',count:1}],totalElements:1,warnings:[]};
const before=JSON.stringify(mesh),next={...mesh,nodes:mesh.nodes.map(p=>p.map(x=>x+1)),nodeIDs:['d','e','f']};
assert.equal(canReplaceGeometry(mesh,next),true,'Coordinates and native sample IDs can refresh without resetting the viewer');
for(const replacement of [
 {...next,nodes:[[0,0,0]]}, {...next,nodes:[[NaN,0,0],[1,0,0],[0,1,0]]},
 {...next,elements:[{...mesh.elements[0],nodes:[1,0,2]}]},
 {...next,groups:[{id:0,name:'Other wheel',count:1}]}, {...next,warnings:['Check dimensions']},
 {...next,fields:[{name:'Cp',values:[1]}]}, {...next,geometryPreview:false}
])assert.equal(canReplaceGeometry(mesh,replacement),false,'Different topology, diagnostics, solution fields or invalid samples require separate handling');
assert.equal(JSON.stringify(mesh),before,'Compatibility checks do not alter native data');
console.log('Tire inspection slider limits, exact input, inactive recovery and native geometry replacement guards passed.');
