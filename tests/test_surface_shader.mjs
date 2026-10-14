import assert from 'node:assert/strict';
import {smoothSurfaceVertices} from '../web/surface-shader.js';
const face={id:'body',surfaceKey:'body:0',points:[[0,0,0],[1,0,0],[1,1,0],[0,1,0]]};
const before=JSON.stringify(face),vertices=smoothSurfaceVertices([face],'body');
assert.equal(vertices.length,54);assert.equal(JSON.stringify(face),before);
for(let i=0;i<vertices.length;i+=9){assert.ok(face.points.some(p=>p.every((x,k)=>Math.fround(x)===vertices[i+k])));assert.deepEqual([...vertices.slice(i+3,i+6)],[0,0,1]);}
const sharp={id:'body',surfaceKey:'body:0',points:[[1,0,0],[1,0,1],[1,1,1],[1,1,0]]};
const cube=smoothSurfaceVertices([face,sharp],'body');
assert.deepEqual([...cube.slice(3,6)],[0,0,1]);
assert.deepEqual([...cube.slice(54+3,54+6)],[-1,0,0]);
const shallow={id:'body',surfaceKey:'body:0',points:[[1,0,0],[2,0,.2],[2,1,.2],[1,1,0]]};
const curved=smoothSurfaceVertices([face,shallow],'body');
assert.ok(curved[9+3]<0&&curved[9+5]>.9,'Shared smooth edge must blend neighboring normals');
assert.equal(smoothSurfaceVertices([{...face,kind:'line'}],'body').length,0);
assert.equal(smoothSurfaceVertices([{...face,selectionOnly:true}],'other').length,0);
console.log('Native position preservation, smooth edges, sharp corners, selection and line exclusion passed.');
