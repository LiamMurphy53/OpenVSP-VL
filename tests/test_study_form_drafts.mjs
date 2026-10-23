import assert from 'node:assert/strict';
import {rememberStudyForms,restoreStudyForms} from '../web/study-form-drafts.js';
const field=(id,value,selected)=>({id,value,...selected?{multiple:true,selectedOptions:selected.map(value=>({value})),options:['a','b','c'].map(value=>({value,selected:false}))}:{}});
function form(fields,open=true){const details=[{open:false},{open:true}];return {fields,open,details,querySelectorAll:selector=>selector==='details'?details:fields};}
const root=(steps,axes)=>({querySelectorAll:selector=>selector==='.study-step'?steps:axes});
const first={},second={},axisA={},axisB={};
const before=root([
 form([field('study-step-0-NumSlices-0',''),field('study-step-0-Norm-0','[[1,'),field('study-geometry-0-Mach-0','0.21'),field('study-member-0-1-BaseLen-0',''),field('study-step-0-Targets-0','',['a','c']),field('study-source-0','1')],false),
 form([field('study-step-1-NumSlices-0','17.0')])
],[form([field('study-values-0','1, bad, 3'),field('study-from-0',''),field('study-axis-field-0','old binding')]),form([field('study-value-1-0-0-2',''),field('study-value-1-1-0-2','4.500')])]);
const drafts=rememberStudyForms(before,[first,second],[axisA,axisB]);
const moved=root([form([field('study-step-0-NumSlices-0','5')]),form([field('study-step-1-NumSlices-0','7'),field('study-step-1-Norm-0','[[0,0,1]]'),field('study-geometry-1-Mach-0','1'),field('study-member-1-1-BaseLen-0','1'),field('study-step-1-Targets-0','',[]),field('study-source-1','0')])],
 [form([field('study-value-0-0-0-2','0'),field('study-value-0-1-0-2','0')]),form([field('study-values-1','0'),field('study-from-1','1'),field('study-axis-field-1','remapped binding')])]);
restoreStudyForms(moved,[second,first],[axisB,axisA],drafts);
const steps=moved.querySelectorAll('.study-step'),axes=moved.querySelectorAll('.study-axis');
assert.equal(steps[0].fields[0].value,'17.0','Exact unsaved text follows its original step');
assert.deepEqual(steps[1].fields.slice(0,4).map(f=>f.value),['','[[1,','0.21',''],'Blank, malformed JSON, preparation and member drafts survive reindexing');
assert.deepEqual(steps[1].fields[4].options.filter(o=>o.selected).map(o=>o.value),['a','c']);
assert.equal(steps[1].fields[5].value,'0','Native source-step references use the remapped model, not old raw indices');
assert.equal(steps[1].open,false);assert.deepEqual(steps[1].details.map(d=>d.open),[false,true]);
assert.deepEqual(axes[0].fields.map(f=>f.value),['','4.500'],'Structured vector cases retain exact drafts');
assert.deepEqual(axes[1].fields.map(f=>f.value),['1, bad, 3','','remapped binding'],'An input sweep keeps its remapped native binding');
const replacement={},fresh=root([form([field('study-step-0-NumSlices-0','9')])],[form([field('study-values-0','2')])]);
restoreStudyForms(fresh,[replacement],[{}],drafts);
assert.equal(fresh.querySelectorAll('.study-step')[0].fields[0].value,'9','Replacing a step does not inherit discarded text');
assert.equal(fresh.querySelectorAll('.study-axis')[0].fields[0].value,'2');
assert.deepEqual(first,{});assert.deepEqual(axisA,{},'Raw UI drafts never become serialized study fields');
console.log('Unsaved study text, vectors, arrays, member scopes and details follow stable owners through rearrangement.');
