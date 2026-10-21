import assert from 'node:assert/strict';
import {stepInputOverrides,useSweptDefault,useAllSweptDefaults,omitFollowedDefaults,followingSpec,overridesMarkup} from '../web/study-overrides.js';
const field={name:'CADLenUnit',index:0,nativeParameter:'unit',label:'CAD length unit',values:[4],choices:[{value:1,label:'cm'},{value:4,label:'ft'}],editable:true};
const draft={stages:[{name:'SurfaceIntersection',freezeInputs:true,inputs:[{name:'CADLenUnit',values:[4]},{name:'STEPFileFlag',values:[1]}]}],axes:[{kind:'parameter',id:'unit',values:[1,4]}]};
let items=stepInputOverrides(draft.stages,draft.axes,[{inputs:[field]}]);assert.equal(items.length,1);assert.match(overridesMarkup(items,String,false),/Step input: ft/);
useSweptDefault(draft,items[0]);assert.equal(draft.stages[0].freezeInputs,true);assert.deepEqual(draft.stages[0].inputs,[{name:'STEPFileFlag',values:[1]}]);
assert.deepEqual(omitFollowedDefaults(draft.stages[0],'inputs',[{name:'CADLenUnit',values:[4]},{name:'STEPFileFlag',values:[1]}]),draft.stages[0].inputs);
assert.equal(followingSpec({inputs:[field]},draft.stages[0],'inputs').inputs[0].editable,false);assert.equal(field.editable,true);
assert.equal(stepInputOverrides(draft.stages,draft.axes,[{inputs:[field]}]).length,0);
const geo={stages:[{geometryInputs:[{name:'ThinGeomSet',values:[3]}]}],axes:[{kind:'parameter',id:'set',values:[3,4]},{kind:'geometryInput',stage:0,name:'ThinGeomSet',values:[3]}]};
items=stepInputOverrides(geo.stages,geo.axes,[{inputs:[],geometryInputs:[{name:'ThinGeomSet',index:0,nativeParameter:'set',values:[3]}]}]);assert.equal(items[0].inputSweep,true);useSweptDefault(geo,items[0]);assert.equal(geo.axes.length,1);assert.deepEqual(geo.stages[0].geometryInputs,[]);
assert.equal(stepInputOverrides([{inputs:[{name:'Unrelated',values:[1]}]}],draft.axes,[{inputs:[field]}]).length,0);
assert.equal(stepInputOverrides([{inputs:[{name:'CADLenUnit',values:[4]}]}],[{kind:'parameter',id:'user',name:'CADLenUnit',values:[1]}],[{inputs:[field]}]).length,0,'Same-name user parameters are unrelated');
console.log('Explicit-input review, per-field inheritance, frozen-setting preservation and geometry sweeps passed.');

const coupled={stages:[{freezeInputs:true,inputs:[{name:'ThinGeomSet',values:[3]},{name:'AlphaStart',values:[4]}],geometryInputs:[{name:'ThinGeomSet',values:[3]}]}],axes:[{kind:'parameter',id:'set',values:[3,4]}]};
const fields=[{name:'ThinGeomSet',index:0,nativeParameter:'set',values:[3]}];
const records=stepInputOverrides(coupled.stages,coupled.axes,[{inputs:fields,geometryInputs:fields}]);assert.equal(records.length,2);assert.match(records[1].label,/Geometry preparation/);assert.match(overridesMarkup(records,String,false),/Use swept defaults in all listed inputs/);
useAllSweptDefaults(coupled,records);assert.equal(coupled.stages[0].followDefaults.length,2);assert.deepEqual(coupled.stages[0].inputs,[{name:'AlphaStart',values:[4]}]);assert.deepEqual(coupled.stages[0].geometryInputs,[]);assert.equal(coupled.stages[0].freezeInputs,true);
