import {waveSettings,bindWaveSettings} from './wave-settings.js?v=20261012-1';
import {parasiteSettings,bindParasiteSettings} from './parasite-settings.js?v=20261012-1';
import {excrescenceEditor,bindExcrescences} from './excrescence-editor.js?v=20261012-1';
import {bindStructuralLibrary} from './structural-library.js?v=20261011-library';
import {laminateEditor} from './laminate-editor.js?v=20261021-units';
import {boundaryEditor} from './boundary-editor.js?v=20261021-units';
import {connectionEditor,bindConnectionEditors} from './assembly-connections.js?v=20261011-assembly';
import {structuralRegions,bindStructuralRegions} from './structural-regions.js?v=20261010-123';
import {mountStructuralPreview,mountAssemblyPreview} from './structural-preview.js?v=20261010-123';
import {renderDataTools} from './data-tools.js?v=20261010-123';
import {renderSpecialized} from './specialized-tools.js?v=20261010-123';
import {renderMeasurements} from './measurement-tools.js?v=20261010-123';
import {renderFiles} from './file-tools.js?v=20261010-123';
import {renderConfigurations} from './configuration-tools.js?v=20261010-123';
import {intersectionSettings,bindIntersectionSettings,intersectionSelection,bindIntersectionSelection} from './intersection-settings.js?v=20261010-123';
import {intersectionDefaults,bindIntersectionDefaults} from './intersection-defaults.js?v=20261010-123';
// Guided editors for additional native engineering workflows.
let curveChoice='PROP_CHORD',settingsChoice='',structChoice='',materialChoice='',assemblyPreviewChoice='';
export function chooseEngineeringSettings(id){settingsChoice=id;}
export function renderAdvanced(ctx){
 const specialized=renderSpecialized(ctx),measurements=renderMeasurements(ctx),dataTools=renderDataTools(ctx);
 if(specialized||measurements||dataTools||renderFiles(ctx)||renderConfigurations(ctx))return true;
 const {active,app,model,geom,data:d,helpers:h}=ctx;
 const {E,nice,field,select,button,card,paramDetails,params,mutate,bind,val,num,plotSVG}=h;
 const root=document.querySelector('#tool-content'),c=geom;
 const types=o=>Object.entries(o||{}).map(([name,v])=>[name,nice(name)]);
 const selectParam=(p,items,label=nice(p.name))=>`<label class="tool-field">${E(label)}<select data-tool-param="${E(p.id)}">${items.map(([v,label])=>`<option value="${v}" ${Number(v)===p.value?'selected':''}>${E(label)}</option>`).join('')}</select></label>`;
 if(active==='propellers'){
  const prop=d.propellers.find(p=>p.id===c?.id);
  if(!prop){root.innerHTML=card('Choose a propeller','<p>Add a propeller in Design, then select it as the working component. Its blade curves and solver groups appear here.</p>');return;}
  const curve=prop.curves.find(p=>p.name===curveChoice)||prop.curves[0];curveChoice=curve.name;
  const settings=c.params.filter(p=>['Design','Sym','XForm'].includes(p.rawGroup)),representation=settings.find(p=>p.name==='PropMode');
  const representationChoices=Object.entries(d.propModes||{}).map(([name,value])=>[value,{PROP_BLADES:'Individual blades',PROP_BOTH:'Blades and actuator disk',PROP_DISK:'Actuator disk'}[name]]);
  const aeroSettings=d.globalSettings.find(g=>g.name==='VSPAEROSettings');
  const uniformRPM=aeroSettings?.params.find(p=>p.name==='UniformPropRPMFlag');
  const rotorSpeeds=uniformRPM?`${selectParam(uniformRPM,[[1,'Same RPM for all rotors'],[0,'Independent rotor RPM']],'Rotor speeds')}<p>With rotating blades, OpenVSP can link all rotor speeds. Changing one linked RPM updates the other rotating groups.</p>`:'';
  const backup=d.rotorSpeedBackup;
  const speedRecovery=`<h3>Keep rotor speeds through geometry changes</h3><p>Save all rotating groups’ RPM and their linked or independent setting before changing propeller representation. Restore after returning to matching components and native surface copies. The saved speeds travel with the aircraft and support Undo.</p><div class="tool-actions"><button id="rotor-speeds-save" ${d.rotatingGroups.some(g=>g.params.find(p=>p.name==='GeomPropertyType')?.value===2)?'':'disabled'}>Save all rotor speeds</button><button id="rotor-speeds-restore" ${backup?.restoreReady?'':'disabled'}>Restore saved rotor speeds</button></div>${backup?`<p>${E(backup.message)}</p><dl>${backup.groups.map(g=>`<div><dt>${E(g.key.map(([id,s])=>`${model.components.find(c=>c.id===id)?.name||id} · surface ${s}`).join('; '))}</dt><dd>${E(g.rpm)} RPM</dd></div>`).join('')}</dl><p>Saved speed setting: ${backup.linked===1?'Same RPM for all rotors':backup.linked===0?'Independent rotor RPM':'Unavailable'}.</p>`:'<p>No rotor speeds saved yet.</p>'}`;
  const diskBackup=d.rotorDiskBackup;
  const diskRecovery=`<h3>Keep disk settings through geometry changes</h3><p>Save all disks’ three driving values, driver choices and hub setting before changing representation. Restore to matching components and native surface copies. OpenVSP recalculates outputs using the current geometry, airspeed and density. These settings travel with the aircraft and support Undo.</p><div class="tool-actions"><button id="rotor-disks-save" ${d.disks.length?'':'disabled'}>Save all disk settings</button><button id="rotor-disks-restore" ${diskBackup?.restoreReady?'':'disabled'}>Restore saved disk settings</button></div>${diskBackup?`<p>${E(diskBackup.message)}</p>${diskBackup.disks.map(g=>`<h4>${E(model.components.find(c=>c.id===g.key[0])?.name||g.key[0])} · surface ${E(g.key[1])}</h4><dl>${Object.entries(g.inputs).map(([name,value])=>`<div><dt>${E(nice(name.replace('Rotor','')))}</dt><dd>${E(value)}</dd></div>`).join('')}<div><dt>Hub diameter</dt><dd>${g.automaticHub?'Automatic from current geometry':E(g.hub)+' model units'}</dd></div></dl>`).join('')}`:'<p>No disk settings saved yet.</p>'}`;
  const nativeGroup=(g)=>{
   const rotor=g.params.find(p=>p.name==='GeomPropertyType')?.value===2;
   const generated=new Set(['RotorDia','Ox','Oy','Oz','Rx','Ry','Rz']);
   const geometryLabels={RotorDia:'Native rotor diameter',Ox:'Rotation origin X',Oy:'Rotation origin Y',Oz:'Rotation origin Z',Rx:'Rotation axis X',Ry:'Rotation axis Y',Rz:'Rotation axis Z'};
   const geometry=g.params.filter(p=>generated.has(p.name));
   const editable=g.params.filter(p=>!generated.has(p.name)).map(p=>p.name==='RPM'&&!rotor?{...p,active:false}:p);
   return `<article class="tool-item"><h3>${E(g.name)}</h3><p>${rotor?'Rotating rotor group':'Fixed or moving geometry group'} · ${g.components.map((id,i)=>`${E(model.components.find(c=>c.id===id)?.name||id)} · native surface ${E(g.surfaces[i])}`).join('; ')}</p>${paramDetails(editable,['RPM'])}<details><summary>Native rotation geometry</summary><p>OpenVSP derives the diameter, rotation origin and axis from the propeller geometry and its surface copy. Edit the component to change them.</p><dl>${geometry.map(p=>`<div><dt>${E(geometryLabels[p.name])}</dt><dd>${E(Number(p.value.toPrecision(9)))}</dd></div>`).join('')}</dl></details></article>`;
  };
  const diskEditor=g=>{
   const choices=g.driverChoices,selected=new Set(choices),native=g.drivers;
   const inputs=native.filter(d=>selected.has(d.value)).map(d=>({...g.params.find(p=>p.id===d.parameter),name:d.label}));
   const outputs=native.filter(d=>!selected.has(d.value)).map(d=>({...g.params.find(p=>p.id===d.parameter),label:d.label}));
   const hub=g.params.filter(p=>['AutoHubDiaFlag','RotorHubDiameter'].includes(p.name)).map(p=>({...p,name:p.name==='AutoHubDiaFlag'?'Automatic hub diameter':'Manual hub diameter',max:p.effectiveMax??p.max}));
   const diameter=g.params.find(p=>p.name==='RotorDiameter');
   const flow=d.globalSettings.find(s=>s.name==='VSPAEROSettings')?.params||[];
   const airspeed=flow.find(p=>p.name==='Vinf')?.value,density=flow.find(p=>p.name==='Rho')?.value;
   return `<article class="tool-item" data-disk="${E(g.id)}"><h3>${E(g.name)}</h3><p>Choose three independent variables. OpenVSP calculates the other six from these drivers, rotor diameter, and the saved aerodynamic airspeed and density.</p><p class="native-tip">Saved airspeed: ${E(airspeed)} · density: ${E(density)}. Set these in Engineering settings → Aerodynamic model settings; use consistent model units.</p><div class="tool-fields">${choices.map((value,i)=>select(`Driver ${i+1}`,`disk-driver-${g.id}-${i}`,native.map(d=>[d.value,d.label]),value)).join('')}</div><p data-disk-choice-status>Current native driver selection.</p><button data-disk-drivers="${E(g.id)}">Apply drivers</button><h4>Driving values</h4>${paramDetails(inputs,inputs.map(p=>p.name))}<details><summary>Calculated by OpenVSP</summary><dl>${[...outputs,{...diameter,label:'Native rotor diameter'}].map(p=>`<div><dt>${E(p.label)}</dt><dd>${p.value==null?'Undefined native value':E(Number(p.value.toPrecision(9)))}</dd></div>`).join('')}</dl></details><h4>Hub diameter</h4><p>Automatic hub diameter follows the propeller geometry. Turn it off to enter a manual diameter from zero to ${E(diameter.value)} in model units. OpenVSP clamps a larger hub to the current disk diameter when it updates the rotor.</p>${paramDetails(hub,hub.map(p=>p.name))}</article>`;
  };
  root.innerHTML=card('Propeller geometry',`<p>Blade dimensions and radial distributions are evaluated by OpenVSP. Individual blades create native rotating groups; actuator disks use thrust and power coefficients.</p>${representation&&representationChoices.length?selectParam(representation,representationChoices,'Propeller representation'):''}${paramDetails(settings.filter(p=>p!==representation||!representationChoices.length),['Diameter','NumBlade','Beta34','Rotate','RevFlag'])}`)+
   card('Native blade curve',`${select('Distribution','prop-curve',prop.curves.map(x=>[x.name,x.label||nice(x.name.replace('PROP_',''))]),curve.name)}<p class="native-tip">Ratios are dimensionless; twist and sweep use degrees.</p>${plotSVG(curve.sampleStations,curve.sampleValues,'Radius fraction',curve.label+(curve.dimension==='angle'?' (degrees)':''))}<div class="tool-fields">${select('Interpolation','prop-interpolation',types(d.curveTypes),Object.keys(d.curveTypes).find(k=>d.curveTypes[k]===curve.type))}${field('Insert at radius fraction','prop-insert',.55)}</div><div class="tool-actions">${button('prop-convert','Apply interpolation')}${button('prop-split','Insert station')}</div><div class="curve-table"><table><thead><tr><th>Point</th><th>Radius fraction</th><th>Value</th><th></th></tr></thead><tbody>${curve.stations.map((t,i)=>`<tr><td>${i}${curve.type===d.curveTypes.CEDIT&&i%3?' · handle':''}</td><td><input data-prop-station="${i}" aria-label="Radius fraction ${i}" type="number" step="any" value="${t}" ${curve.pointControls[i]?.stationActive?'':'disabled title="Locked by OpenVSP"'}></td><td><input data-prop-value="${i}" aria-label="Blade curve value ${i}" type="number" step="any" value="${curve.values[i]}" ${curve.pointControls[i]?.valueActive?'':'disabled title="Locked by OpenVSP"'}></td><td><button data-prop-remove="${i}" ${i===0||i===curve.stations.length-1||(curve.type===d.curveTypes.CEDIT&&i%3)?'disabled':''}>Remove</button></td></tr>`).join('')}</tbody></table></div>${button('prop-apply','Apply control points',true)}<div class="tool-actions">${button('prop-approximate','Approximate all curves as Bezier')}${button('prop-thickness','Reset thickness from airfoils')}</div>`,'wide')+
   card('Rotor disks and moving groups',`<p>OpenVSP builds these from the propeller representation and saved aerodynamic sets or mode. Include the propeller in that selection to create its group. Set each rotor’s RPM here, then choose the blade model and time settings in Analyze. These edits are saved in the aircraft and support Undo. Changing representation can recreate native groups; review RPM and disk settings afterward.</p>${rotorSpeeds}${speedRecovery}${diskRecovery}${d.disks.map(diskEditor).join('')}${d.rotatingGroups.map(nativeGroup).join('')}${!d.disks.length&&!d.rotatingGroups.length?'<p>No native rotor disks or moving groups in the saved aerodynamic geometry selection.</p>':''}`,'wide');
  bind('rotor-speeds-save',()=>mutate({operation:'rotor-speeds-save'}));
  bind('rotor-speeds-restore',()=>mutate({operation:'rotor-speeds-restore'}));
  bind('rotor-disks-save',()=>mutate({operation:'rotor-disks-save'}));
  bind('rotor-disks-restore',()=>mutate({operation:'rotor-disks-restore'}));
  d.disks.forEach(g=>{
   const selectors=g.driverChoices.map((_,i)=>document.querySelector(`#disk-driver-${g.id}-${i}`));
   const article=root.querySelector(`[data-disk="${g.id}"]`),apply=article.querySelector('[data-disk-drivers]'),status=article.querySelector('[data-disk-choice-status]');
   const read=()=>selectors.map(e=>Number(e.value));
   const refresh=()=>{const key=read().sort((a,b)=>a-b).join(','),valid=d.propDriverCombinations.some(c=>c.join(',')===key);apply.disabled=!valid;status.textContent=valid?'Apply to change the driving variables.':'Choose three independent drivers; OpenVSP does not support this combination.';};
   selectors.forEach(e=>e.onchange=refresh);
   apply.onclick=()=>mutate({operation:'rotor-disk-drivers',id:g.id,choices:read()});
  });
  document.querySelector('#prop-curve').onchange=e=>{curveChoice=e.target.value;ctx.render();};
  bind('prop-convert',()=>mutate({operation:'prop-curve-type',geom:c.id,curve:curve.name,type:val('prop-interpolation')}));
  bind('prop-split',()=>mutate({operation:'prop-curve-split',geom:c.id,curve:curve.name,station:num('prop-insert')}));
  bind('prop-apply',()=>mutate({operation:'prop-curve-set',geom:c.id,curve:curve.name,stations:[...document.querySelectorAll('[data-prop-station]')].map(e=>Number(e.value)),values:[...document.querySelectorAll('[data-prop-value]')].map(e=>Number(e.value))}));
  bind('prop-approximate',()=>mutate({operation:'prop-approximate',geom:c.id}));bind('prop-thickness',()=>mutate({operation:'prop-reset-thickness',geom:c.id}));
  document.querySelectorAll('[data-prop-remove]').forEach(b=>b.onclick=()=>mutate({operation:'prop-curve-delete',geom:c.id,curve:curve.name,index:Number(b.dataset.propRemove)}));
 }else if(active==='settings'){
  const labels={Vehicle:'Project and export options',CFDMeshSettings:'CFD mesh options',SurfaceIntersectSettings:'Surface intersections',CFDGridDensity:'CFD grid density',VSPAEROSettings:'Aerodynamic model settings',WaveDragSettings:'Wave drag settings',ParasiteDragSettings:'Parasite drag settings'};
  const group=d.globalSettings.find(x=>x.id===settingsChoice)||d.globalSettings.find(x=>x.name==='VSPAEROSettings')||d.globalSettings[0];settingsChoice=group.id;
  root.innerHTML=card('Engineering settings',`<p>Saved defaults. Analyze can override them for an individual run.</p>${select('Settings','engineering-settings',d.globalSettings.map(x=>[x.id,labels[x.name]||x.name]),group.id)}<input id="settings-search" class="parameter-search" placeholder="Find a setting by name or description…" aria-label="Find engineering setting"><div id="settings-fields">${params(group.params)}</div>`,'wide')+
  (group.name==='ParasiteDragSettings'?card('Parasite drag allowances',excrescenceEditor(d,h)):'');
  if(group.name==='WaveDragSettings'){
   const guided=new Set(group.waveGuide.sections.flatMap(s=>s.parameters));
   root.querySelector('#settings-fields').innerHTML=waveSettings(group,h)+`<details><summary>Additional native display settings</summary>${params(group.params.filter(p=>!guided.has(p.id)))}</details>`;
   bindWaveSettings(h);
  }
  if(group.name==='ParasiteDragSettings'){
   const guided=new Set(group.parasiteGuide.sections.flatMap(s=>s.parameters));
   root.querySelector('#settings-fields').innerHTML=parasiteSettings(group,h)+`<details><summary>Additional native settings</summary>${params(group.params.filter(p=>!guided.has(p.id)&&!['ExcresVal','ExcresType'].includes(p.name)))}</details>`;
   bindParasiteSettings(h);
  }
  if(group.name==='SurfaceIntersectSettings'){
   root.firstElementChild.insertAdjacentHTML('afterend',intersectionSelection(group,d,h)+intersectionSettings(group,h)+intersectionDefaults(group,h));
   bindIntersectionSelection(group,h);
   bindIntersectionSettings(group,h);
   bindIntersectionDefaults(group,h);
   const guided=new Set(['DemoteSurfsCubicFlag','CubicSurfTolerance','HalfMesh','STEPMergePoints','UseMode','Set','DegenSet',...group.exportDefaults.params.map(p=>p.name)]);
   root.querySelector('#settings-fields').innerHTML=`<details><summary>Additional native settings</summary>${params(group.params.filter(p=>!guided.has(p.name)&&p.name!=='SRF_XYZIntCurve'))}<p class="native-tip">The installed engine’s standalone intersection workflow does not apply its saved XYZ export flag. Original native exports are preserved.</p></details>`;
  }
  document.querySelector('#engineering-settings').onchange=e=>{settingsChoice=e.target.value;ctx.render();};
  document.querySelector('#settings-search').oninput=e=>{const query=e.target.value.toLowerCase();document.querySelectorAll('#settings-fields .tool-field').forEach(el=>el.hidden=!`${el.textContent} ${el.title}`.toLowerCase().includes(query));};
  bindExcrescences(h);
 }else if(active==='structural'){
  const s=d.structures.find(x=>x.id===structChoice)||d.structures.find(x=>x.geom===c?.id)||d.structures[0];if(s)structChoice=s.id;
  const material=d.materials.find(x=>x.id===materialChoice)||d.materials.find(x=>!x.id.startsWith('_'))||d.materials[0];materialChoice=material?.id;
  const boundaries=s?d.boundaryConditions.filter(x=>x.structure===s.id):[];
  const boundary=b=>boundaryEditor(b,s,d,h);
  const layers=material?d.layers.filter(l=>l.material===material.id):[],isLaminate=material?.params.find(p=>p.name==='FeaMaterialType')?.value===d.materialTypes.FEA_LAMINATE;
  root.innerHTML=card('Structural constraints',s?`${select('Structure','advanced-structure',d.structures.map(x=>[x.id,x.name]),s.id)}<div class="tool-fields">${field('Name','boundary-name','Root constraint','text')}${select('Scope','boundary-type',[['FEA_BC_STRUCTURE','Whole structure'],['FEA_BC_PART','Structural part'],['FEA_BC_SUBSURF','Structural region']],'FEA_BC_STRUCTURE')}</div>${button('boundary-add','Add boundary condition',true)}${boundaries.map(boundary).join('')}`:'<p>Create a structure in the Structures tab first.</p>','wide')+
   card('Laminate materials',laminateEditor(material,layers,d,h),'wide')+
   card('Structural subsurfaces',s?`<p>Native subsurfaces partition the structural mesh and provide targets for constraints.</p><div class="tool-fields">${field('Name','fea-sub-name','Structural region','text')}${select('Type','fea-sub-type',types(d.subsurfaceTypes),'SS_RECTANGLE')}</div>${button('fea-sub-add','Add structural region',true)}${structuralRegions(s,d,{...h,modelComponents:model.components})}`:'<p>Select a structure first.</p>','wide');
  document.querySelectorAll('[data-boundary-bit]').forEach(e=>e.onchange=()=>mutate({operation:'parameter',id:e.dataset.boundaryBit,value:[...document.querySelectorAll(`[data-boundary-bit="${e.dataset.boundaryBit}"]:checked`)].reduce((mask,b)=>mask|Number(b.dataset.bit),0)}));
  bindStructuralLibrary(h);
  if(s){root.insertAdjacentHTML('beforeend',card('Structural preview','<div id="native-structural-preview"></div>','wide'));mountStructuralPreview(document.querySelector('#native-structural-preview'),s,ctx.app);bindStructuralRegions(s,h);document.querySelector('#advanced-structure').onchange=e=>{structChoice=e.target.value;ctx.render();};bind('boundary-add',()=>mutate({operation:'boundary-add',structure:s.id,type:val('boundary-type'),name:val('boundary-name')}));bind('fea-sub-add',()=>mutate({operation:'structural-subsurface-add',structure:s.id,type:val('fea-sub-type'),name:val('fea-sub-name')}));document.querySelectorAll('[data-boundary-delete]').forEach(b=>b.onclick=()=>mutate({operation:'boundary-delete',structure:s.id,id:b.dataset.boundaryDelete}));document.querySelectorAll('[data-boundary-target]').forEach(e=>e.onchange=()=>mutate({operation:'boundary-target',structure:s.id,id:e.dataset.boundaryTarget,target:e.value}));document.querySelectorAll('[data-fea-sub-delete]').forEach(b=>b.onclick=()=>mutate({operation:'structural-subsurface-delete',structure:s.id,id:b.dataset.feaSubDelete}));}
  if(material){document.querySelector('#laminate-material').onchange=e=>{materialChoice=e.target.value;ctx.render();};bind('layer-add',()=>mutate({operation:'layer-add',material:material.id}));document.querySelectorAll('[data-layer-material]').forEach(e=>e.onchange=()=>mutate({operation:'layer-material',material:material.id,id:e.dataset.layerMaterial,lamina:e.value}));document.querySelectorAll('[data-layer-delete]').forEach(b=>b.onclick=()=>mutate({operation:'layer-delete',material:material.id,id:b.dataset.layerDelete}));document.querySelectorAll('[data-layer-order]').forEach(b=>b.onclick=()=>mutate({operation:'layer-reorder',material:material.id,id:b.dataset.layerOrder,direction:b.dataset.layerDirection}));}
 }else if(active==='assemblies'){
  root.innerHTML=card('Create an assembly',`<p>Gather native structures and connect their fixed points. Each member keeps its own part and material settings. Run FeaAssemblyMesh in Analyze to inspect the combined mesh and download solver files.</p>${field('Assembly name','assembly-name','Aircraft structure','text')}${button('assembly-add','Create assembly',true)}`)+d.assemblies.map(a=>card(a.name,`<div class="inline-fields">${field('Assembly name','assembly-name-'+a.id,a.name,'text')}<button data-assembly-rename="${E(a.id)}">Rename assembly</button></div><div class="set-members">${d.structures.map(s=>`<label><input data-assembly-member="${a.id}" data-assembly-structure="${s.id}" type="checkbox" ${a.structures.includes(s.id)?'checked':''}>${E(s.name)}</label>`).join('')}</div>${paramDetails(a.params)}${a.connections.map(conn=>connectionEditor(a,conn,h)).join('')}<div class="tool-fields">${['start','end'].map(side=>`<label class="tool-field">${side==='start'?'Start':'End'} fixed point<select data-connection-${side}="${a.id}">${d.structures.filter(s=>a.structures.includes(s.id)).flatMap(s=>s.parts.filter(p=>p.type===d.partTypes.FEA_FIX_POINT).map(p=>`<option value="${E(s.id+'|'+p.id)}">${E(s.name+' / '+p.name)}</option>`)).join('')}</select></label>${field(side==='start'?'Start copy index':'End copy index','connection-new-'+a.id+'-'+side,0)}`).join('')}</div><button data-connection-add="${a.id}">Connect fixed points</button><div class="tool-actions"><button data-assembly-delete="${a.id}">Remove assembly</button></div>`,'wide')).join('');
  if(d.assemblies.length){const a=d.assemblies.find(a=>a.id===assemblyPreviewChoice)||d.assemblies[0];assemblyPreviewChoice=a.id;root.insertAdjacentHTML('beforeend',card('Assembly construction preview',`${select('Assembly to inspect','assembly-preview-choice',d.assemblies.map(a=>[a.id,a.name]),a.id)}<p>Inspect native member parts, region boundaries and fixed-point connections before meshing.</p><div id="native-assembly-preview"></div>`,'wide'));document.querySelector('#assembly-preview-choice').onchange=e=>{assemblyPreviewChoice=e.target.value;ctx.render();};mountAssemblyPreview(document.querySelector('#native-assembly-preview'),a,ctx.app);}
  bindConnectionEditors(d.assemblies,h,ctx.app);
  document.querySelectorAll('[data-assembly-rename]').forEach(b=>b.onclick=()=>mutate({operation:'assembly-rename',id:b.dataset.assemblyRename,name:val('assembly-name-'+b.dataset.assemblyRename)}));
  bind('assembly-add',()=>mutate({operation:'assembly-add',name:val('assembly-name')}));document.querySelectorAll('[data-assembly-member]').forEach(e=>e.onchange=()=>mutate({operation:'assembly-member',id:e.dataset.assemblyMember,structure:e.dataset.assemblyStructure,member:e.checked}));document.querySelectorAll('[data-assembly-delete]').forEach(b=>b.onclick=()=>mutate({operation:'assembly-delete',id:b.dataset.assemblyDelete}));document.querySelectorAll('[data-connection-delete]').forEach(b=>b.onclick=()=>mutate({operation:'assembly-connection-delete',assembly:b.dataset.connectionDelete,index:Number(b.dataset.connectionIndex)}));document.querySelectorAll('[data-connection-add]').forEach(b=>b.onclick=()=>{const id=b.dataset.connectionAdd,start=document.querySelector(`[data-connection-start="${id}"]`).value.split('|'),end=document.querySelector(`[data-connection-end="${id}"]`).value.split('|');mutate({operation:'assembly-connection-add',assembly:id,startStructure:start[0],startPoint:start[1],startIndex:num('connection-new-'+id+'-start'),endStructure:end[0],endPoint:end[1],endIndex:num('connection-new-'+id+'-end')});});
 }else return false;
 return true;
}
