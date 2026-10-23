import assert from 'node:assert/strict';
import {studyResultLabel} from '../web/study-result-labels.js';
import {plotSVG} from '../web/plot-svg.js';
const field={field:'Slice_Area',unit:'model length²'},xs=[1,3],ys=[1.0108052985748082,2.5488544547506806],before=JSON.stringify({field,xs,ys});
const label=studyResultLabel(field);assert.equal(label,'Slice_Area (model length²)');
const svg=plotSVG(xs,ys,'Starting position',label,false,null,true);assert.match(svg,/model length²/);assert.equal(JSON.stringify({field,xs,ys}),before);
assert.equal(studyResultLabel({field:'Unknown result'}),'Unknown result');assert.equal(studyResultLabel({field:'Nodes',unit:'count'}),'Nodes (count)');
console.log('Study unit labels reach standalone plots without modifying native values.');
