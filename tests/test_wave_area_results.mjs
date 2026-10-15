import assert from 'node:assert/strict';
import {waveSeries,waveChart,waveAreaResults,waveCSV,waveSliceSeries} from '../web/wave-area-results.js';
const c={coneIndex:1,thetaDegrees:0,length:2,volume:3,maxArea:4,startX:0,endX:2,flowFit:[0,null,0],totalFit:[2,4,6],flowSlices:[0,3,0],totalSlices:[2,7,6],componentFit:[[1,2,3]],buildupFit:[[2,4,6]],componentSlices:[[1,2,3]],buildupSlices:[[2,4,6]],searsHaack:[0,5,0]};
const d={cones:[c],components:[{name:'Body'}],componentIds:['id'],xNormalized:[0,.5,1],xFitNormalized:[0,.5,1],inletArea:2,exitArea:6,showPoints:true,file:'wave-reference-curves.json'};
const before=JSON.stringify(d);
assert.deepEqual(waveSeries(d,0,'total','searsHaack')[1].y,[0,5,0]);
assert.deepEqual(waveSeries(d,0,'components','searsHaack')[2].y,[2,9,6]);
assert.equal(waveSeries(d,0,'buildup','none')[0].label,'Cumulative · Body');
assert.match(waveChart(d,0,'total','searsHaack',true,String),/d="M[0-9.,]+\s+M[0-9.,]+" stroke="#285f48"/,'Undefined native values break paths');
assert.match(waveAreaResults(d,String),/Flow-corrected total/);
assert.match(waveCSV(waveSeries(d,0,'total','none')),/Flow-corrected total",0.5,\n/);
assert.equal(JSON.stringify(d),before,'Presentation must not change native arrays');
assert.equal(waveAreaResults(null,String),'','Old runs without the capture remain readable');
console.log('Native-array preservation, area modes, baseline display, gaps, CSV and old-run fallback passed.');

assert.deepEqual(waveSliceSeries(d,0,'total')[0].y,[0,3,0]);
assert.match(waveCSV(waveSliceSeries(d,0,'total')),/native slices/);
