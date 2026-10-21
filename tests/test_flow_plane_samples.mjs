import assert from 'node:assert/strict';
import {flowPlaneCSV,flowPlaneHeader} from '../web/flow-plane-samples.js';
const fields={U:[100.12345678901235,-1e-20],V:[2,3],W:[-4,5],Cp:[-.12345678901234568,.2],Speed:[100.22345678901235,5.830951894845301]};
const mesh={nodes:[[1.2345678901234567,0,-2],[3,4,5]],nodeIDs:[12,98],direction:2,location:-3.25,referenceSpeed:100,solverVelocityScale:250,fields:Object.entries(fields).map(([name,nodeValues])=>({name,nodeValues,values:[999]}))};
const rows=flowPlaneCSV(mesh).trim().split('\r\n').map(line=>line.split(','));
assert.deepEqual(rows[0],['NodeID','X','Y','Z','U','V','W','Cp','Speed']);
for(let i=0;i<mesh.nodes.length;i++)assert.deepEqual(rows[i+1].map(Number),[mesh.nodeIDs[i],...mesh.nodes[i],...Object.values(fields).map(values=>values[i])]);
assert.match(flowPlaneHeader(mesh),/Y = -3.25/);assert.match(flowPlaneHeader(mesh),/Vmax\): 250/);
assert.throws(()=>flowPlaneCSV({...mesh,nodeIDs:[12]}),/incomplete/);
assert.throws(()=>flowPlaneCSV({...mesh,fields:mesh.fields.slice(1)}),/incomplete/);
console.log('Original nodal IDs/coordinates/fields retain full numeric precision; cell averages are not exported.');

assert.match(flowPlaneHeader(mesh),/native length\/s; Cp is dimensionless/);
