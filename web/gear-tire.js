import {drawingMesh} from './structural-preview.js?v=20261010-123';
import {mountMeshViewer} from './mesh-viewer.js?v=20261022-live-geometry';
import {customSliderMarkup,bindCustomSliders} from './custom-sliders.js?v=20261022-drafts';
import {latestPreview} from './live-preview.js?v=20261022';
let cleanup=null,live=null,generation=0;
const sliderUnits={displayValue:x=>x,parameterDimension:()=>null,readOnly:p=>!p.active};
export function tireInspectionSliders(key){return [
 {id:'fraction',name:'Inspection retraction fraction',type:0,value:0,min:0,max:1,active:false}
].map(p=>({...p,customSlider:{key:`tire-inspection:${key}:${p.id}`,range:p.max-p.min,adjustable:false}}));}
export function tireInspectionValue(input,name){
 // Inactive pose fields do not drive the native inspection. Keep their drafts
 // in the UI, without allowing a blank unused field to block another pose.
 if(input.disabled)return 0;
 const value=Number(input.value);
 if(!input.value.trim()||!Number.isFinite(value)||value<Number(input.min)||value>Number(input.max))throw Error(`Enter ${name} between ${input.min} and ${input.max}.`);
 return value;
}
export const tireDetailNames=['DrimMode','DrimIn','DrimModel','DrimFrac','WrimMode','WrimIn','WrimModel','WrimFrac','WsMode','WsIn','WsModel','WsFrac','HsMode','HsIn','HsModel','HsFrac','PlyRating','SpeedRating','DFlangeModel','WGModel','DGModel','WsGModel','DsGModel'];
export const suspensionNames=['TravelX','TravelY','TravelZ','TravelCompressed','TravelExtended','BogieThetaMin','BogieThetaMax','SteeringAngle'];
export function tireDetailsMarkup(b,h){
 const fields=names=>h.params(names.flatMap(n=>b.params.filter(p=>p.name===n)));
 return `<details><summary>Rim, shoulder & tire clearance</summary><p>Inches are always inches. Model-unit dimensions follow the gear’s length convention. OpenVSP calculates flange and grown-tire dimensions.</p><h4>Wheel rim</h4><div class="tool-fields">${fields(tireDetailNames.slice(0,8))}</div><h4>Tire shoulder</h4><p>In the installed OpenVSP version, a shoulder’s Model units mode still uses its fraction. Edit inches or the fraction to change the shoulder; the resulting model-unit length is shown below.</p><div class="tool-fields">${fields(tireDetailNames.slice(8,16))}</div><h4>Ratings & calculated clearance dimensions</h4><div class="tool-fields">${fields(tireDetailNames.slice(16))}</div></details>`;
}
export function suspensionMarkup(b,h){return `<details><summary>Suspension & steering</summary><p>Direction components are in the gear frame; OpenVSP normalizes the compression direction. Inspect compressed or extended wheels below. Steering and pitch limits are used by the native gear-envelope calculations.</p><div class="tool-fields">${h.params(suspensionNames.flatMap(n=>b.params.filter(p=>p.name===n)))}</div></details>`;}
export function disposeTireInspection(){generation++;if(live){live.dispose();live=null;}if(cleanup){cleanup();cleanup=null;}}
export function mountTireInspection(host,gear,component,app,h){
 disposeTireInspection();if(!host)return;if(!gear.bogies.length){host.innerHTML='<p>Add a wheel group to inspect its tires and suspension.</p>';return;}
 const token=generation,revision=app.model().revision,{E,select}=h,options=gear.inspectionOptions,sliders=tireInspectionSliders(gear.id);
 host.innerHTML=`<p>Inspect one wheel group as nominal tires, grown tires or the native clearance envelope, at its chosen suspension and retraction position. Suspension travel applies with the gear down. Choose Intermediate to adjust retraction with the slider.</p><div class="tool-fields">${select('Inspection wheel group','tire-inspect-bogie',gear.bogies.map((b,i)=>[b.id,`Wheel group ${i+1} · ${b.name}`]),gear.bogies[0].id)}${select('Inspection tire shape','tire-inspect-clearance',options.clearance.map(o=>[o.value,o.label]),options.clearance[0].value)}${select('Inspection suspension','tire-inspect-suspension',options.suspension.map(o=>[o.value,o.label]),options.suspension[0].value)}${select('Inspection side','tire-inspect-mirror',[[0,'Base wheel group'],[1,'Mirrored wheel group']],0)}${select('Inspection gear position','tire-inspect-configuration',options.configuration.map(o=>[o.value,o.label]),options.configuration[0].value)}${sliders.map(p=>`<label class="tool-field" for="tire-inspect-${p.id}">${E(p.name)}<input id="tire-inspect-${p.id}" aria-label="${E(p.name)}" type="number" step="any" min="${p.min}" max="${p.max}" value="0">${customSliderMarkup(p,'tire-inspect-'+p.id,{...sliderUnits,esc:E})}</label>`).join('')}</div><div class="tool-actions"><button data-tire-inspect>Update tire inspection</button><button data-tire-download disabled>Download tire inspection</button><button data-tire-create disabled>Save inspected shape as auxiliary</button></div><p data-tire-status role="status" aria-live="polite">Adjust a control to preview, or choose Update tire inspection.</p><div data-tire-viewer></div>`;
 const get=id=>host.querySelector('#tire-inspect-'+id),status=host.querySelector('[data-tire-status]'),viewer=host.querySelector('[data-tire-viewer]'),download=host.querySelector('[data-tire-download]'),create=host.querySelector('[data-tire-create]'),update=host.querySelector('[data-tire-inspect]');let result=null;
 const current=()=>host.isConnected&&token===generation&&revision===app.model().revision;
 const unavailable=message=>{result=null;download.disabled=create.disabled=true;status.textContent=message;};
 const configure=()=>{const b=gear.bogies.find(b=>b.id===get('bogie').value),mirrored=!!b.params.find(p=>p.name==='Symmetrical')?.value,mechanism=b.retraction.mode!==0;get('mirror').disabled=!mirrored;if(!mirrored)get('mirror').value='0';const intermediate=options.configuration[2].value;get('configuration').querySelector(`option[value="${intermediate}"]`).disabled=!mechanism;if(!mechanism&&Number(get('configuration').value)===intermediate)get('configuration').value=String(options.configuration[0].value);get('fraction').disabled=Number(get('configuration').value)!==intermediate;const down=Number(get('configuration').value)===options.configuration[0].value;get('suspension').disabled=!down;
  for(const p of sliders)host.querySelector(`[data-custom-slider="tire-inspect-${p.id}"]`).disabled=get(p.id).disabled;
 };
 const settings=()=>({operation:'gear-tire-preview',geom:component.id,bogie:get('bogie').value,...Object.fromEntries(['clearance','suspension','mirror','configuration'].map(n=>[n,h.num('tire-inspect-'+n)])),fraction:tireInspectionValue(get('fraction'),'a retraction fraction'),pitch:0,revision});
 live=latestPreview({isCurrent:current,request:settings=>app.api('/api/query',settings),
  pending:()=>unavailable('Updating native tire inspection…'),
  fail:error=>unavailable(error.message),
  show:data=>{
   const mesh=drawingMesh({parts:[],warnings:data.warnings,showContext:true,filename:'Native tire & suspension inspection',displayNote:'Tire profiles, clearance allowance, suspension displacement and retraction are generated by OpenVSP. Inspect points or download the exact native surface samples.'},data.component);
   if(!mesh.elements.length)throw Error('OpenVSP returned no inspection surfaces. Check the wheel-group setup.');
   if(!cleanup?.replaceGeometry?.(mesh)){if(cleanup)cleanup();cleanup=mountMeshViewer(viewer,mesh,E);}
   result=data;status.textContent='Native tire inspection ready. The saved aircraft is unchanged.';download.disabled=create.disabled=false;
  }
 });
 const refresh=(immediate=false)=>{configure();try{live.schedule(settings(),immediate);}catch(error){live.invalidate();unavailable(error.message);}};
 bindCustomSliders(host,sliders,{...sliderUnits,isBusy:()=>false,liveEdit:(p,slider,value,finished)=>refresh(finished)});
 for(const p of sliders){get(p.id).addEventListener('input',()=>refresh());get(p.id).onchange=()=>refresh(true);}
 host.querySelectorAll('select').forEach(el=>el.onchange=()=>refresh(true));configure();
 update.onclick=()=>refresh(true);
 download.onclick=()=>{if(!result)return;const url=URL.createObjectURL(new Blob([JSON.stringify({...result,revision},null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='tire-inspection.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 create.onclick=()=>result&&h.mutate({operation:'gear-inspection-create',geom:result.geom,bogie:result.bogie,...result.settings});
}
