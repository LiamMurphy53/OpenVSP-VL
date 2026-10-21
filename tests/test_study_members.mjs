import assert from 'node:assert/strict';
import {memberSpecs,separateMembers,shareFirstMember,memberMarkup,memberPrefix} from '../web/study-members.js';
const input=(name,value)=>({name,index:0,values:[value],editable:true});
const spec={name:'FeaAssemblyMesh',guide:{sections:[],memberSizing:[{id:'a',name:'Front',component:'Wing A',inputs:[input('BaseLen',1),input('MinLen',.2)]},{id:'b',name:'Rear',component:'Wing B',inputs:[input('BaseLen',2),input('MinLen',.3)]}]}};
const stage={name:'FeaAssemblyMesh',inputs:[input('BaseLen',4)],memberInputs:[{id:'a',inputs:[input('BaseLen',3),input('MinLen',.1)]}]};
assert.deepEqual(memberSpecs(spec,stage).map(m=>m.spec.inputs.map(e=>e.values[0])),[[4,.1],[4,.3]],'Shared settings take precedence exactly as the native assembly merger');
separateMembers(spec,stage);assert.deepEqual(stage.inputs,[]);assert.equal(stage.memberInputs.length,2);assert.equal(stage.memberInputs[1].inputs[1].values[0],.3);
assert.equal(spec.guide.memberSizing[0].inputs[0].values[0],1,'Saved schema is never changed');
const markup=memberMarkup(spec,stage,2,{esc:String,inputMarkup:(s,p)=>p});
assert.match(markup,/study-member-2-0/);assert.match(markup,/study-member-2-1/);assert.equal(memberPrefix(2,1),'study-member-2-1');
assert.match(memberMarkup(spec,{name:'FeaAssemblyMesh',inputs:[]},0,{esc:String}),/Edit settings separately/);
console.log('Study member editor preserves native precedence, independent values and unique field scopes');

shareFirstMember(spec,stage);assert.equal(stage.memberInputs,undefined);assert.deepEqual(stage.inputs.map(e=>e.values[0]),[4,.1]);
assert.equal(stage.freezeInputs,true,'Copying first member to all must retain shared values equal to the first native defaults');
