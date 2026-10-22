import assert from 'node:assert/strict';
import {runInputDraft} from '../web/run-input-draft.js';
import {resolveSetSelection} from '../web/set-selection.js';
const spec={inputs:[{name:'Set',type:1,index:0},{name:'FileName',type:3,index:0},{name:'Center',type:4,index:0}]};
const fields={'#analysis-Set-0':{dataset:{scalar:'true'}},'#analysis-FileName-0':{dataset:{scalar:'true'}},'#analysis-Center-0':{dataset:{vector:'true'}}};
const host={querySelector:id=>fields[id]},job={id:'run',setIdentities:['builtin:0','builtin:1','builtin:2','wing','pod']};
const inputs=[{name:'Set',values:[3]},{name:'FileName',values:['/old/run/report.csv']},{name:'Center',values:[[1,-2,3]]}];
const draft=runInputDraft(spec,inputs,'analysis',host,job);
assert.equal(draft[0].setIdentity,'wing');assert.equal(draft[1].value,'report.csv');assert.deepEqual(draft[2].value,['1','-2','3']);
assert.equal(resolveSetSelection([{index:4,identity:'wing'}],draft[0].value,draft[0].setIdentity).value,'4');
assert.equal(resolveSetSelection([{index:3,identity:'replacement'}],draft[0].value,draft[0].setIdentity).value,'');
const legacy=runInputDraft(spec,inputs,'analysis',host,{id:'old'});assert.equal(resolveSetSelection([{index:3,identity:'replacement'}],legacy[0].value,legacy[0].setIdentity).value,'','Untracked runs require an explicit replacement');
const geo=runInputDraft({inputs:[{name:'ThinGeomSet',type:1,index:0}]},[{name:'ThinGeomSet',values:[4]}],'geometry',{querySelector:()=>({dataset:{scalar:'true'}})},job);assert.equal(geo[0].setIdentity,'pod');
console.log('Saved run values, geometry setup, set moves, replaced sets and untracked selection recovery passed.');
for(const name of ['CGGeomSet','CGDegenSet']){
 const cg=runInputDraft({inputs:[{name,type:1,index:0}]},[{name,values:[3]}],'analysis',{querySelector:()=>({dataset:{scalar:'true'}})},job)[0];
 assert.equal(cg.setIdentity,'wing',name+' must preserve saved native set identity');
 assert.equal(resolveSetSelection([{index:4,identity:'wing'}],cg.value,cg.setIdentity).value,'4');
 assert.equal(resolveSetSelection([{index:3,identity:'replacement'}],cg.value,cg.setIdentity).value,'');
}
console.log('Both CG geometry sets follow saved-run identities and reject replacement occupants.');
