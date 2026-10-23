import assert from 'node:assert/strict';
import {analysisInputApplies as applies,editableAnalysisInputs as editable} from '../web/analysis-input-state.js';
const values={'analysis-UseCGModeFlag-0':{value:'1'},'analysis-UseModeFlag-0':{value:'0'},'analysis-PropBladesMode-0':{value:'1'},'analysis-AutoTimeStepFlag-0':{value:'0'}};
const host={getElementById:id=>values[id]};
const mode={input:'UseCGModeFlag',values:[1]},sets={input:'UseCGModeFlag',values:[0]};
const fields=[{name:'UseCGModeFlag',editable:true},{name:'CGModeID',editable:true,applicableWhen:mode},{name:'CGGeomSet',editable:true,applicableWhen:sets},{name:'CGDegenSet',editable:true,applicableWhen:sets},{name:'NativeReadout',editable:false}];
const spec={inputs:fields},before=JSON.stringify(spec);
assert.deepEqual(editable(spec,'analysis',host).map(e=>e.name),['UseCGModeFlag','CGModeID'],'Stale hidden set fields do not block a mode-based request');
values['analysis-UseCGModeFlag-0'].value='0';
assert.deepEqual(editable(spec,'analysis',host).map(e=>e.name),['UseCGModeFlag','CGGeomSet','CGDegenSet'],'Returning to set selection restores validation of both required targets');
const nested={all:[{input:'PropBladesMode',values:[1,2]},{input:'AutoTimeStepFlag',values:[0]}]};
assert.equal(applies(nested,'analysis',host),true);values['analysis-AutoTimeStepFlag-0'].value='1';assert.equal(applies(nested,'analysis',host),false);
assert.equal(applies({any:[mode,nested]},'analysis',host),false);values['analysis-UseCGModeFlag-0'].value='1';assert.equal(applies({any:[mode,nested]},'analysis',host),true);
assert.equal(applies({input:'Missing',values:[0]},'analysis',host),false);assert.deepEqual(editable(null,'analysis',host),[]);assert.equal(JSON.stringify(spec),before);
assert.equal(applies(mode,'geometry',host),false,'Separate preparation inputs never use flight controller values');
console.log('Guide applicability and request collection share native controller rules, including CG mode recovery, nested dependencies and prefix isolation.');
const projectionHost={getElementById:id=>({'analysis-TargetType-0':{value:'0'},'analysis-BoundaryType-0':{value:'0'},'analysis-DirectionType-0':{value:'2'}}[id])};
const projection={inputs:[{name:'TargetSet',editable:true,applicableWhen:{input:'TargetType',values:[0]}},{name:'BoundarySet',editable:true,applicableWhen:{input:'BoundaryType',values:[1]}},{name:'BoundaryGeomID',editable:true,applicableWhen:{input:'BoundaryType',values:[2]}},{name:'Direction',editable:true,applicableWhen:{input:'DirectionType',values:[4]}}]};
assert.deepEqual(editable(projection,'analysis',projectionHost).map(e=>e.name),['TargetSet'],'No-boundary fixed-axis projection omits stale boundary and manual-vector fields');
const limits={'analysis-AutoBoundFlag-0':{value:'1'}};const sliceHost={getElementById:id=>limits[id]};
const slicing={inputs:[{name:'AutoBoundFlag',editable:true},{name:'StartVal',editable:true,applicableWhen:{input:'AutoBoundFlag',values:[0]}},{name:'EndVal',editable:true,applicableWhen:{input:'AutoBoundFlag',values:[0]}}]};
assert.deepEqual(editable(slicing,'analysis',sliceHost).map(e=>e.name),['AutoBoundFlag']);limits['analysis-AutoBoundFlag-0'].value='0';assert.deepEqual(editable(slicing,'analysis',sliceHost).map(e=>e.name),['AutoBoundFlag','StartVal','EndVal']);
console.log('Projection boundary/direction and automatic/manual slice alternatives retain their native applicability.');
const studyHost={getElementById:id=>id==='study-step-0-BoundaryType-0'?{value:'0'}:null};
const studyFields={inputs:[{name:'BoundaryType',editable:true},{name:'BoundaryGeomID',editable:true,applicableWhen:{input:'BoundaryType',values:[2]}}]};
assert.deepEqual(editable(studyFields,'study-step-0',studyHost,true).map(e=>e.name),['BoundaryType','BoundaryGeomID'],'Studies retain configured fields that a future controller-sweep case can activate');
assert.deepEqual(editable(studyFields,'study-step-0',studyHost).map(e=>e.name),['BoundaryType'],'Single-run filtering remains the default');
const {collectAnalysisInputs:collect}=await import('../web/analysis-input-state.js');
const studyValues={
 'study-step-0-BoundaryType-0':{tagName:'SELECT',dataset:{scalar:'true'},value:'0'},
 'study-step-0-BoundaryGeomID-0':{tagName:'SELECT',dataset:{scalar:'true'},value:'body-id',selectedOptions:[{disabled:false}]},
 'study-step-0-ManualValue-0':{tagName:'INPUT',dataset:{scalar:'true'},value:''}
};
const captureHost={getElementById:id=>studyValues[id]};
const captureSpec={inputs:[{name:'BoundaryType',index:0,type:1,values:[0],editable:true},{name:'BoundaryGeomID',index:0,type:3,values:[''],editable:true,applicableWhen:{input:'BoundaryType',values:[2]}},{name:'ManualValue',index:0,type:2,values:[1],editable:true,applicableWhen:{input:'BoundaryType',values:[2]}}]};
assert.deepEqual(collect(captureSpec,'study-step-0',captureHost,true).map(e=>e.name),['BoundaryType']);
assert.deepEqual(collect(captureSpec,'study-step-0',captureHost,true,true),[{name:'BoundaryType',index:0,values:[0]},{name:'BoundaryGeomID',index:0,values:['body-id']}]);
studyValues['study-step-0-BoundaryGeomID-0'].value='';assert.deepEqual(collect(captureSpec,'study-step-0',captureHost,true,true).map(e=>e.name),['BoundaryType'],'Incomplete inactive drafts do not block an otherwise valid study');
studyValues['study-step-0-BoundaryType-0'].value='2';assert.throws(()=>collect(captureSpec,'study-step-0',captureHost,true,true),/ManualValue: enter a valid number/,'Active invalid values still reject');
console.log('Study capture preserves valid future inputs, skips incomplete inactive drafts and retains active validation.');
const parsedFields={list:{dataset:{numericList:'true'},value:'1, 2 3'},vector:{dataset:{vector:'true'},querySelectorAll:()=>[{value:'1'},{value:'-2'},{value:'3'}]},choices:{dataset:{choiceList:'true'},selectedOptions:[{value:'native-a'},{value:'native-b'}]},json:{dataset:{},value:'[[1,2,3]]'}};
const parsedSpec={inputs:Object.keys(parsedFields).map(name=>({name,index:0,type:name==='vector'||name==='json'?4:2,editable:true,values:[]}))};
assert.deepEqual(collect(parsedSpec,'p',{getElementById:id=>parsedFields[id.slice(2,-2)]},true).map(e=>e.values),[[1,2,3],[[1,-2,3]],['native-a','native-b'],[[1,2,3]]]);
parsedFields.list.value='bad';assert.throws(()=>collect(parsedSpec,'p',{getElementById:id=>parsedFields[id.slice(2,-2)]},true),/finite positions/);
console.log('Shared collection retains native numeric-list, XYZ, choice-list and JSON array formats.');
