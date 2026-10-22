import assert from 'node:assert/strict';
import {engineSetupMarkup,engineSetupRequest,bindEngineSetup} from '../web/engine-setup.js';
const ends=['InletLip','InletFace','OutletLip','OutletFace'],params=[];
for(const name of ['GeomIOType','GeomInType','GeomOutType','InletModeType','OutletModeType',...ends.flatMap(e=>[e+'Mode',e+'Index',e+'U'])]){
 params.push({id:name,name,rawGroup:'EngineModel',value:0,min:0,max:4,choices:[{value:0,label:'Native zero'},{value:1,label:'Native one'}]});
}
const c={id:'body',type:'Fuselage',params};
const html=engineSetupMarkup(c,String);
assert.match(html,/Configure flowpath/);assert.match(html,/Setup flowpath component/);
assert.equal((html.match(/data-engine-end=/g)||[]).length,4);
assert.equal(engineSetupMarkup({...c,type:'WING'},String),'');
const fields=new Map(params.map(p=>[p.name,{dataset:{engineSetting:p.name},value:'0',disabled:false}]));
const button={},status={textContent:''},calls=[];
const host={querySelector:key=>key==='[data-engine-apply]'?button:key==='[data-engine-status]'?status:fields.get(key.match(/data-engine-setting="([^"]+)"/)?.[1]),querySelectorAll:()=>[...fields.values()]};
bindEngineSetup(host,c,request=>calls.push(request));
assert.equal(fields.get('OutletLipIndex').disabled,false);assert.equal(fields.get('OutletLipU').disabled,true);
fields.get('GeomIOType').value='2';fields.get('InletLipIndex').value='1';
fields.get('OutletLipMode').value='1';fields.get('OutletLipU').value='.75';fields.get('OutletLipMode').onchange();
button.onclick();
assert.equal(calls.length,1);assert.equal(calls[0].operation,'engine-configure');assert.equal(calls[0].geom,'body');
assert.equal(calls[0].settings.OutletLipU,.75);assert.equal(calls[0].settings.OutletLipMode,1);
assert.equal(calls[0].settings.InletLipIndex,1);assert.equal(calls[0].settings.GeomIOType,2);
assert.ok(!('OutletLipIndex' in calls[0].settings));
fields.get('OutletLipU').value='';button.onclick();assert.equal(calls.length,1);assert.match(status.textContent,/finite/);
fields.get('OutletLipU').value='.75';fields.get('GeomIOType').disabled=true;
assert.ok(!('GeomIOType' in engineSetupRequest(host,c).settings),'Never send a locked field');
console.log('Atomic native flowpath setup: choices, station basis, complete request, validation and locks passed.');
