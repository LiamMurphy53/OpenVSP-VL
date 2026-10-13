import {profileSources} from './profile-sources.js?v=20261012-1';
import {editableRegionCurve,bindRegionCurves} from './region-curve-editor.js?v=20261010-123';
export function auxiliaryMarkup(a,c,model,h){
 const {E,params,paramDetails,select,button,card}=h,controls=a.controls,fields=names=>names.flatMap(n=>c.params.filter(p=>p.name===n)),used=new Set(controls.groups.flatMap(g=>g.names)),bogies=[['','Automatic · first wheel group'],...model.tools.gears.filter(g=>g.id===a.parent).flatMap(g=>g.bogies.map((b,i)=>[b.id,`Wheel group ${i+1} · ${b.name}`]))];
 let html='';
 if(controls.contactCount){html+=card('Auxiliary contacts',`<p>Choose wheel groups from this auxiliary shape’s attached gear. Automatic contacts use its first group. Use distinct contact locations to define a ground plane.</p>${a.contacts.slice(0,controls.contactCount).map((p,i)=>`<article class="tool-item"><h3>Contact ${i+1}${controls.mode==='AUX_GEOM_THREE_PT_CCE'?i===0?' · nose gear':' · main gear':''}</h3>${select('Contact '+(i+1),'aux-contact-'+i,bogies.some(b=>b[0]===p)?bogies:[[p,'Unavailable saved wheel group · '+p],...bogies],p)}<button data-aux-contact="${i}">Assign contact ${i+1}</button><div class="tool-fields">${paramDetails(c.params.filter(x=>x.name.startsWith('ContactPt'+(i+1)+'_')),['ContactPt'+(i+1)+'_Isymm','ContactPt'+(i+1)+'_SuspensionMode',controls.mode==='AUX_GEOM_SINGLE_GEAR'?'ContactPt1_ClearanceMode':'ContactPt'+(i+1)+'_TireMode',...(controls.mode==='AUX_GEOM_SINGLE_GEAR'?['ContactPt1_GearMode','ContactPt1_KRetract']:[])])}</div></article>`).join('')}<p>Reassign contacts before removing a referenced wheel group.</p>`,'wide');}
 html+=controls.groups.map(g=>card(g.title,`<div class="tool-fields">${params(fields(g.names))}</div>`)).join('');
 if(controls.contactPositions)html+=contactPositionsMarkup(controls.contactPositions,h);
 if(controls.clearanceFile)html+=clearanceFileMarkup(controls.clearanceCoordinates,h);
 if(controls.profile){const profile=controls.profile,primaryIDs=new Set(profile.driverControls.filter(d=>profile.drivers.includes(d.value)).map(d=>d.parameter)),profileFields=c.params.filter(p=>profile.parameterIDs.includes(p.id)),primary=profileFields.filter(p=>(primaryIDs.has(p.id)&&!p.name.endsWith('_Dummy'))||['CockpitSide','SymType','CloseFlag','PreserveARFlag'].includes(p.name)),other=profileFields.filter(p=>!primary.includes(p));html+=card('Super-cone profile',`<p>Profile coordinates describe horizontal and vertical angles in degrees. OpenVSP maps this curve onto the cone. Choose a native family or copy/import a profile, then edit its native parameters.</p>${select('Cone profile family','aux-profile-shape',Object.entries(profile.shapes).map(([n,v])=>[n,n.replace(/^XS_/,'').replaceAll('_',' ').toLowerCase()]),Object.keys(profile.shapes).find(n=>profile.shapes[n]===profile.type))}${button('aux-profile-apply','Apply native cone profile')}${profile.driverControls.length?`<p>OpenVSP calculates the remaining dimensions from these drivers. ${profile.driversFixed?'This family fixes its native drivers.':''}</p>${profile.driversFixed?'':`<div class="tool-fields">${profile.drivers.map((value,i)=>select('Cone dimension driver '+(i+1),'aux-profile-driver-'+i,profile.driverControls.map(d=>[d.value,d.label]),value)).join('')}</div>${button('aux-profile-drivers','Apply cone dimension drivers')}`}`:''}<div class="tool-fields">${params(primary)}</div><div id="aux-profile-plot"></div>${pEditable(profile,a.id,h)}${paramDetails(other,[])}${select('Copy profile from','aux-profile-source',profileSources(model.components,model.tools,a.id))}${button('aux-profile-copy','Copy source profile')}${button('aux-profile-convert','Convert cone profile to editable curve')}<label class="file-drop">Import cone section (.fxs)<input id="aux-profile-section" type="file" accept=".fxs,.txt"></label><label class="file-drop">Import cone airfoil (.dat)<input id="aux-profile-airfoil" type="file" accept=".dat,.txt"></label><p data-aux-profile-status>Imported profiles use native section normalization. Adjust their angular width and height afterward.</p>`,'wide');}
 html+=card('Native auxiliary coordinates',`${button('aux-native-download','Download native auxiliary coordinates')}<p>Includes every sampled surface in world XYZ, original parameter IDs, contact references and the saved model revision. Cone profile samples use degrees.</p>`);
 html+=card('Additional native settings',paramDetails(c.params.filter(p=>p.rawGroup==='Design'&&!p.name.startsWith('ContactPt')&&p.name!=='AuxiliaryGeomType'&&!used.has(p.name)),[]));
 return html;
}

export function bindAuxiliary(a,c,h,model){
 const {bind,val,mutate,plotSVG}=h;
 bind('aux-native-download',()=>{const data={engine:model.version,revision:model.revision,coordinateFrame:'Native world XYZ',profileAngleUnits:'degrees',component:c,auxiliary:a},url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download='auxiliary-geometry.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
 document.querySelectorAll('[data-aux-contact]').forEach(b=>b.onclick=()=>mutate({operation:'auxiliary-contact',geom:c.id,index:Number(b.dataset.auxContact),bogie:val('aux-contact-'+b.dataset.auxContact)}));
 const file=(id,operation,format,status)=>{const el=document.querySelector('#'+id);if(!el)return;el.onchange=async e=>{const f=e.target.files[0];if(!f)return;const message=document.querySelector(status);if(f.size>5_000_000){message.textContent='Choose a file up to 5 MB.';el.value='';return;}message.textContent='Reading '+f.name+'…';try{await mutate({operation,geom:c.id,format,content:await f.text()});}catch(error){if(message.isConnected)message.textContent=error.message;}finally{if(el.isConnected)el.value='';}};};
 file('aux-cce','auxiliary-cce',null,'[data-aux-file-status]');
 if(a.controls.clearanceCoordinates){
  const coordinates=a.controls.clearanceCoordinates;
  const download=document.querySelector('#aux-cce-download');download.disabled=!coordinates.exportable;
  if(coordinates.exportable){
   const units=unitName(coordinates.units===6?coordinates.modelUnits:coordinates.units);
   document.querySelector('#aux-cce-plot').innerHTML=plotSVG(coordinates.points.map(p=>p[1]),coordinates.points.map(p=>p[2]),'Lateral Y ('+units+')','Vertical Z ('+units+')',true);
  }
  bind('aux-cce-download',()=>{
   const text=coordinates.points.map(p=>`${p[1]} ${p[2]}`).join('\n')+'\n';
   const url=URL.createObjectURL(new Blob([text],{type:'text/plain'})),link=document.createElement('a');
   link.href=url;link.download='clearance-envelope.cce';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
 }
 if(a.controls.profile){const p=a.controls.profile;if(p.controlPoints)bindRegionCurves({...h,mutate:r=>{const {id,...request}=r;return mutate({...request,geom:c.id,operation:r.operation.replace('region-curve-','auxiliary-profile-edit-')});}},{});document.querySelector('#aux-profile-plot').innerHTML=plotSVG(p.profile.map(x=>x[0]),p.profile.map(x=>x[1]),'Horizontal angle (degrees)','Vertical angle (degrees)',true);
  bind('aux-profile-drivers',()=>mutate({operation:'auxiliary-profile-drivers',geom:c.id,drivers:p.drivers.map((_,i)=>Number(val('aux-profile-driver-'+i)))}));
  bind('aux-profile-apply',()=>mutate({operation:'auxiliary-profile-shape',geom:c.id,shape:val('aux-profile-shape')}));
  bind('aux-profile-copy',()=>{const text=val('aux-profile-source');if(!text)throw Error('Add a source component with cross-sections first.');return mutate({operation:'auxiliary-profile-copy',geom:c.id,source:JSON.parse(text)});});
  bind('aux-profile-convert',()=>mutate({operation:'auxiliary-profile-convert',geom:c.id}));
  file('aux-profile-section','auxiliary-profile-import','section','[data-aux-profile-status]');file('aux-profile-airfoil','auxiliary-profile-import','airfoil','[data-aux-profile-status]');
 }
}

function pEditable(profile,id,h){return editableRegionCurve({id,sectionCurve:profile},h,'Cone');}

function unitName(code){return ['millimeters','centimeters','meters','inches','feet','yards','model units'][code]||'unavailable';}

function contactPositionsMarkup(position,h){
 const {E,card}=h,points=position.contacts.filter(p=>p.point);
 const duplicate=points.some((p,i)=>points.slice(0,i).some(q=>q.point.every((v,j)=>v===p.point[j])));
 return card('Native contact positions',`<p>Coordinates use the attached gear’s local X/Y/Z axes and its ${E(unitName(position.units))} model units. These are OpenVSP’s mean tire contact locations with the selected side, suspension and tire radius.</p><div class="aux-contact-table"><table><thead><tr><th>Contact</th><th>X</th><th>Y</th><th>Z</th></tr></thead><tbody>${position.contacts.map(p=>`<tr><td>${p.index+1}</td>${p.point?p.point.map(v=>`<td>${E(v)}</td>`).join(''):`<td colspan="3">${E(p.warning||'Choose an available wheel group.')}</td>`}</tr>`).join('')}</tbody></table></div>${position.contacts.filter(p=>p.warning).map(p=>`<p role="status">Contact ${p.index+1}: ${E(p.warning)}</p>`).join('')}${duplicate?'<p role="status">Two contacts occupy the same native position. Choose separate locations, such as the nose gear and both main-gear sides, to define the ground plane.</p>':''}`,'wide');
}

function clearanceFileMarkup(coordinates,h){
 const {E,card,button}=h;
 return card('Clearance-envelope file',`<p>Each .cce row contains lateral Y and vertical Z coordinates in the envelope’s local plane. Choose the file’s length units above. OpenVSP positions the envelope using the nose and main-gear contacts and converts the coordinates to the attached gear’s ${E(unitName(coordinates.modelUnits))} model units.</p><label class="file-drop">Read clearance envelope (.cce)<input type="file" id="aux-cce" accept=".cce,.txt"></label><p data-aux-file-status>${coordinates.nativeDefault?'Using OpenVSP’s default straight-line envelope. Read a .cce file to define its cross-section.':`${coordinates.points.length} coordinate points saved in the native model · ${E(coordinates.units===6?'matching gear model units':unitName(coordinates.units))}.`}</p><div id="aux-cce-plot"></div>${button('aux-cce-download','Download saved clearance file')}<p>Choose at least two finite coordinate pairs, up to 5 MB. The plot and download preserve the file-unit coordinates; the surface preview shows the native aircraft geometry.</p>`,'wide');
}
