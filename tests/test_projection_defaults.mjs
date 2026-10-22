import assert from 'node:assert/strict';
import {projectionOptionInputs} from '../web/projection-defaults.js';
const spec={inputs:[{name:'DirectionType',index:0,editable:true,choices:[{value:0},{value:1},{value:2}]},{name:'Direction',index:0,editable:true}],guide:{savedProjectionOptions:[{name:'DirectionType',index:0,values:[1]},{name:'Direction',index:0,values:[[0,1,0]]}]}};
const out=projectionOptionInputs(spec);assert.deepEqual(out,spec.guide.savedProjectionOptions);out[1].values[0][0]=9;assert.equal(spec.guide.savedProjectionOptions[1].values[0][0],0);
assert.ok(out.every(e=>!['TargetGeomID','TargetSet','BoundaryGeomID','BoundarySet','TargetModeID','DirectionGeomID'].includes(e.name)),'Reference selections remain untouched');
spec.guide.savedProjectionOptions[0].values=[4];assert.throws(()=>projectionOptionInputs(spec),/saved option is unavailable/);assert.equal(spec.guide.savedProjectionOptions[1].values[0][0],0);
console.log('Saved native projection options copy atomically without mutating source records or geometry references');
