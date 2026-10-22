import {cstSliderParameters,cstSliderMarkup,bindCstSliders,cstRequest} from './cst-sliders.js?v=20261022-bor';
import {generatedProfileMarkup,bindGeneratedProfile} from './generated-profile.js?v=20261012';
import {profileSources} from './profile-sources.js?v=20261012-1';
import {borFilePointsMarkup,bindBORFilePoints} from './bor-file-points.js?v=20261012-1';
import {editableRegionCurve,bindRegionCurves} from './region-curve-editor.js?v=20261010-123';
import {crewToolsEnabled,humanControlsMarkup,bindHumanControls,disposeHumanInspection} from './human-controls.js?v=20261010-123';
import {tireDetailsMarkup,suspensionMarkup,tireDetailNames,suspensionNames,mountTireInspection,disposeTireInspection} from './gear-tire.js?v=20261010-123';
import {auxiliaryMarkup,bindAuxiliary} from './auxiliary-controls.js?v=20261010-123';
import {gearRetractionMarkup,gearRetractionIDs} from './gear-retraction.js?v=20261010-123';
import {skinningMarkup,skinningField,bindSkinning} from './skinning-controls.js?v=20261010-123';
import {mountMeshViewer} from './mesh-viewer.js?v=20261010-123';
import {drawingMesh} from './structural-preview.js?v=20261010-123';
let previewCleanup=null,sectionChoice=0,gearGroundPreview=false;
export function routingPreview(route,name){
 const mesh={filename:name,geometryPreview:true,nodes:[],nodeIDs:[],elements:[],groups:[],displayNote:'Curves and anchor coordinates come directly from OpenVSP, including radiused corners and every physical symmetry copy.'};
 for(const copy of route.copies){
  const label=copy.index===0?'Base route':`Route copy ${copy.index+1}`,group=copy.index+1,start=mesh.nodes.length;
  mesh.nodes.push(...copy.curve);mesh.nodeIDs.push(...copy.curve.map((_,i)=>`Copy ${copy.index+1} · curve sample ${i+1}`));
  for(let i=1;i<copy.curve.length;i++)mesh.elements.push({id:mesh.elements.length+1,type:'native routing curve',group,kind:'line',nodes:[start+i-1,start+i],nativeDrawingID:route.id,nativeDrawingType:`routing curve · copy ${copy.index+1}`});
  const anchors=mesh.nodes.length;mesh.nodes.push(...copy.points);mesh.nodeIDs.push(...copy.points.map((_,i)=>route.points[i]?.id??`Anchor ${i+1}`));
  copy.points.forEach((_,i)=>mesh.elements.push({id:mesh.elements.length+1,type:'native routing anchor',group,kind:'point',nodes:[anchors+i],nativeDrawingID:route.points[i]?.id,nativeDrawingType:`routing anchor ${i+1} · copy ${copy.index+1}`}));
  mesh.groups.push({id:group,name:label,count:Math.max(0,copy.curve.length-1)+copy.points.length});
 }
 mesh.totalElements=mesh.elements.length;return mesh;
}
export function renderSpecialized(ctx){
 disposeTireInspection();disposeHumanInspection();
 if(previewCleanup){previewCleanup();previewCleanup=null;}
 if(!['specialized','sections'].includes(ctx.active))return false;
 const {active,geom:c,model,data:d,helpers:h,app,render}=ctx,{E,nice,field,select,button,card,params,paramDetails,mutate,bind,val,num,plotSVG}=h,root=document.querySelector('#tool-content');
 if(!c){root.innerHTML=card('Choose a component','<p>Add or choose a component in Design.</p>');return true;}
 const surfaceChoices=model.components.flatMap(g=>g.surfaces.map((s,i)=>[`${g.id}:${s.index??i}`,`${g.name} · surface ${s.index??i}`]));
 if(active==='sections'){
  if(!c.sections.length){root.innerHTML=card('Cross-section tools','<p>Choose a wing, fuselage, stack, or propeller with cross-sections. Bodies of revolution use Specialized geometry.</p>');return true;}
  sectionChoice=Math.min(sectionChoice,c.sections.length-1);const s=c.sections[sectionChoice],common={geom:c.id,surface:s.surface,index:s.index};
  if(s.generated){root.innerHTML=generatedProfileMarkup(c,s,sectionChoice,{card,select});bindGeneratedProfile(root,s,i=>{sectionChoice=i;render();},plotSVG);return true;}
  root.innerHTML=card('Cross-section shapes',`${select('Section','special-section',c.sections.map((s,i)=>[i,`Surface ${s.surface} · section ${s.index}`]),sectionChoice)}${select('Native shape family','special-shape',(c.profileShapes||Object.keys(model.shapes)).map(k=>[k,nice(k)]),Object.keys(model.shapes).find(k=>model.shapes[k]===s.shape))}${button('special-shape-apply','Apply native shape',true)}<div id="special-section-plot"></div><label class="file-drop">Import a fuselage cross-section (.fxs)<input type="file" id="special-profile-file" accept=".fxs,.txt,.dat"></label><p class="native-tip">Airfoil-file and CST editors are in Airfoils & curves. Parameters for every shape family are searchable in Design.</p>`)+
  card('Copy a native section',`<p>Copy a profile or whole section from another component.</p>${select('Source section','copy-section-source',profileSources(model.components,d,s.id))}${select('Copy scope','copy-section-scope',[[1,'Profile only'],[0,'Section with compatible settings']],1)}${button('copy-section-apply','Copy to selected section')}<p class="native-tip">Profile copying supports every listed native surface. Section copying uses OpenVSP’s clipboard on the selected surface; compatible section settings copy with the profile.</p>${s.controlPoints?button('section-reparameterize','Redistribute editable curve U'):''}`)+
  (s.skinControls?card('Section skinning',`<div id="tool-skinning">${skinningMarkup(c,s,{esc:E,parameterField:p=>skinningField(p,E)})}</div>`,'wide'):'');
  document.querySelector('#special-section-plot').innerHTML=plotSVG(s.profile.map(p=>p[c.type.toUpperCase()==='WING'?0:1]),s.profile.map(p=>p[2]),'Profile','Z',true);
  document.querySelector('#special-section').onchange=e=>{sectionChoice=Number(e.target.value);render();};bind('special-shape-apply',()=>mutate({...common,operation:'shape',shape:model.shapes[val('special-shape')]}));
  bind('copy-section-apply',()=>{return mutate({...common,operation:'section-copy-from',source:JSON.parse(val('copy-section-source')),curveOnly:!!num('copy-section-scope')});});
  bind('section-reparameterize',()=>mutate({...common,operation:'section-reparameterize'}));
  document.querySelector('#special-profile-file').onchange=async e=>{const f=e.target.files[0];if(f&&f.size<=5_000_000)await mutate({...common,operation:'section-profile-import',content:await f.text()});};
  if(s.skinControls)bindSkinning(document.querySelector('#tool-skinning'),c,s,{mutate,toast:app.toast});
 }else{
  const typ=c.type.toUpperCase();
  if(typ==='HUMAN'){
   if(crewToolsEnabled){root.innerHTML=humanControlsMarkup(c,{esc:E,parameterField:p=>params([p]),nativeAngles:true});bindHumanControls(c,mutate,E,root);}else root.innerHTML=card('Choose an aircraft component','<p>Choose a wing, body, propeller or landing gear to work on the autonomous aircraft. Existing component parameters remain available in Design.</p>');
  }else if(typ==='BODYOFREVOLUTION'){
   const b=d.bodiesOfRevolution.find(b=>b.id===c.id);
   const coefficientSliders=cstSliderParameters(c,{surface:'bor',index:0,cst:b.cst}),dimension=b.dimensions,dimensionIDs=new Set(dimension.driverControls.map(d=>d.parameter));
   root.innerHTML=card('Body of revolution profile',`<p>Revolve this profile using the component’s axis, diameter and mode.</p>${select('Profile family','bor-shape',(c.profileShapes||Object.keys(model.shapes)).map(k=>[k,nice(k)]),Object.keys(model.shapes).find(k=>model.shapes[k]===b.shape))}${button('bor-shape-apply','Apply profile family',true)}<div id="bor-profile-plot"></div>${select('Coordinate file kind','bor-file-kind',[['bor-airfoil','Airfoil coordinates'],['bor-profile','Fuselage cross-section']],'bor-airfoil')}<label class="file-drop">Choose profile file<input id="bor-file" type="file" accept=".dat,.af,.fxs,.txt"></label>`)+card('Native CST profile',b.cst?`${['upper','lower'].map(side=>`<h3>${side} surface · degree ${b.cst[side].length-1}</h3><div class="tool-fields">${b.cst[side].map((x,i)=>`<div>${field((side==='upper'?'Upper':'Lower')+' coefficient '+i,`bor-${side}-${i}`,x)}${cstSliderMarkup(coefficientSliders.find(p=>p.side===side&&p.index===i),E,'bor')}</div>`).join('')}</div><div class="tool-actions"><button data-bor-cst-degree="${side}" data-direction="promote" ${b.cst[side].length>=31?'disabled':''}>Increase ${side} degree</button><button data-bor-cst-degree="${side}" data-direction="demote" ${b.cst[side].length<=1?'disabled':''}>Reduce ${side} degree</button></div>`).join('')}${button('bor-cst-save','Apply native coefficients',true)}<p class="native-tip">OpenVSP changes each side’s degree independently. Reducing degree can change the profile.</p>`:`<p>Fit this airfoil to CST.</p>${field('Degree (1–20)','bor-degree',8)}${b.cstFitAllowed?button('bor-cst-fit','Fit native CST',true):'<p class="native-tip">Choose a four-series, six-series, modified four-digit, five-digit, modified five-digit, one-six-series or file airfoil to fit CST.</p>'}`)+card('Revolution and profile parameters',paramDetails(c.params.filter(p=>!dimensionIDs.has(p.id)&&!['XForm','BBox'].includes(p.rawGroup)&&(!b.editable||p.rawGroup!=='XSecCurve'||['Width','Height','SymType','CloseFlag','PreserveARFlag'].includes(p.name))),['Diameter','Mode','Angle','Width','Height','SymType','CloseFlag']),'wide');
   document.querySelector('#bor-profile-plot').innerHTML=plotSVG(b.profile.map(p=>p[0]),b.profile.map(p=>p[1]),'X','Y',true);
   document.querySelector('#bor-profile-plot').insertAdjacentHTML('afterend',b.editable?`<h4>Editable revolution profile</h4><p>Control coordinates use normalized profile X/Y; profile dimensions use native model units. OpenVSP evaluates the curve and revolved surface.</p>${editableRegionCurve({id:c.id,sectionCurve:b.editable},h,'Revolution profile')}`:`<button id="bor-curve-convert">Convert revolution profile to editable curve</button>`);
   document.querySelector('#bor-profile-plot').insertAdjacentHTML('afterend',borFilePointsMarkup(b.filePoints,E));
   bindBORFilePoints(c.id,mutate,app.toast);
   document.querySelectorAll('[data-bor-cst-degree]').forEach(button=>button.onclick=()=>mutate({operation:'bor-cst-degree',geom:c.id,side:button.dataset.borCstDegree,direction:button.dataset.direction}));
   document.querySelector('#bor-profile-plot').insertAdjacentHTML('beforebegin',`<h4>Profile dimensions</h4><p>OpenVSP calculates linked dimensions from the selected drivers. ${dimension.driversFixed?'This profile family fixes its native dimension drivers.':''}</p>${dimension.driversFixed?'':`${dimension.drivers.map((value,i)=>select('Profile dimension driver '+(i+1),'bor-profile-driver-'+i,dimension.driverControls.map(d=>[d.value,d.label]),value)).join('')}<button id="bor-profile-drivers">Apply profile dimension drivers</button>`}<div class="tool-fields">${params(c.params.filter(p=>dimensionIDs.has(p.id)&&!p.name.endsWith('_Dummy')))}</div>`);
   bind('bor-profile-drivers',()=>mutate({operation:'bor-profile-drivers',geom:c.id,drivers:dimension.drivers.map((_,i)=>num('bor-profile-driver-'+i))}));
   const borCopyChoices=profileSources(model.components,d,c.id);
   document.querySelector('#bor-profile-plot').insertAdjacentHTML('beforebegin',`<details><summary>Copy a native profile</summary><p>Replace this profile with a native section or revolution profile. Its shape and curve settings are copied by OpenVSP; the revolution component keeps its placement and mode. Section clipboard sources use surface 0.</p>${select('Profile source','bor-profile-source',borCopyChoices)}<button id="bor-profile-copy" ${borCopyChoices.length?'':'disabled'}>Copy to revolution profile</button></details>`);
   bind('bor-profile-copy',()=>mutate({operation:'bor-profile-copy',geom:c.id,source:JSON.parse(val('bor-profile-source'))}));
   bind('bor-curve-convert',()=>mutate({operation:'bor-curve-convert',geom:c.id}));
   if(b.editable)bindRegionCurves({...h,mutate:r=>mutate({...r,geom:c.id,operation:r.operation.replace('region-curve-','bor-curve-')})},{geom:c.id});
   bind('bor-shape-apply',()=>mutate({operation:'bor-shape',geom:c.id,shape:val('bor-shape')}));bind('bor-cst-fit',()=>mutate({operation:'bor-cst-fit',geom:c.id,degree:num('bor-degree')}));if(b.cst){
    const section={surface:'bor',index:0,cst:b.cst},common={geom:c.id},options={prefix:'bor',operation:'bor-cst-coefficients'};
    bindCstSliders(root,c,section,common,{...options,liveEdit:app.liveEdit,mutate,toast:app.toast,isBusy:()=>app.isBusy?.()||false});
    bind('bor-cst-save',()=>mutate(cstRequest(root,section,common,options)));
   }document.querySelector('#bor-file').onchange=async e=>{const f=e.target.files[0];if(f&&f.size<=5_000_000)await mutate({operation:val('bor-file-kind'),geom:c.id,content:await f.text()});};
  }else if(typ==='ROUTING'){
   const route=d.routes.find(r=>r.id===c.id),sym=route.symmetry;
   const symmetryChoice=(label,spec)=>{const p=c.params.find(p=>p.id===spec.id);return `<label>${E(label)}<select data-tool-param="${E(p.id)}" aria-label="${E(label)}">${(spec.choices.some(o=>o.value===p.value)?spec.choices:[{value:p.value,label:'Current native value · '+p.value},...spec.choices]).map(o=>`<option value="${o.value}" ${o.value===p.value?'selected':''}>${E(o.label)}</option>`).join('')}</select></label>`;};
   root.innerHTML=card('Native routing',`<p>Attach routing points to surfaces, then set corner radii.</p>${select('Anchor surface','routing-surface',surfaceChoices)}${button('routing-add','Add routing point',true)}${paramDetails(c.params.filter(p=>!['XForm','BBox'].includes(p.rawGroup)&&![sym.planar.id,sym.axial.id,sym.rotations].includes(p.id)),['Length','Radius'])}`)+card('Routing points',route.points.map(p=>`<article class="tool-item"><h3>Point ${p.index+1} · ${E(p.point.map(x=>Number(x.toPrecision(7))).join(', '))}</h3>${select('Anchor component','routing-parent-'+p.id,model.components.filter(g=>g.id!==c.id&&g.surfaces.length).map(g=>[g.id,g.name]),p.parent)}<button data-route-parent="${p.id}">Change anchor</button>${paramDetails(p.params,['U','W','SurfIndex','Radius'])}<div class="tool-actions"><button data-route-insert="${p.index}">Insert before</button>${Object.keys(d.reorderTypes).map(dir=>`<button data-route-move="${p.index}" data-direction="${dir}">${E(nice(dir.replace('REORDER_MOVE_','')))}</button>`).join('')}<button data-route-delete="${p.index}">Remove point</button></div></article>`).join('')||'<p>Add two or more points to form a route.</p>')+card('Native route curve','<div id="route-preview"></div>','wide');
   document.querySelector('#route-preview').insertAdjacentHTML('beforebegin',`<div class="tool-fields">${symmetryChoice('Mirror route',sym.planar)}${symmetryChoice('Rotate copies',sym.axial)}${params(c.params.filter(p=>p.id===sym.rotations))}</div><p>${route.copies.length} physical ${route.copies.length===1?'copy':'copies'} from OpenVSP. Each copy can be shown or inspected below.</p>`);
   bind('routing-add',()=>{const [parent,s]=val('routing-surface').split(':');return mutate({operation:'routing-add',geom:c.id,parent,surface:Number(s)});});document.querySelectorAll('[data-route-insert]').forEach(b=>b.onclick=()=>{const [parent,s]=val('routing-surface').split(':');return mutate({operation:'routing-insert',geom:c.id,index:Number(b.dataset.routeInsert),parent,surface:Number(s)});});document.querySelectorAll('[data-route-parent]').forEach(b=>b.onclick=()=>mutate({operation:'routing-parent',geom:c.id,id:b.dataset.routeParent,parent:val('routing-parent-'+b.dataset.routeParent)}));document.querySelectorAll('[data-route-move]').forEach(b=>b.onclick=()=>mutate({operation:'routing-move',geom:c.id,index:Number(b.dataset.routeMove),direction:b.dataset.direction}));document.querySelectorAll('[data-route-delete]').forEach(b=>b.onclick=()=>mutate({operation:'routing-delete',geom:c.id,index:Number(b.dataset.routeDelete)}));
   if(route.copies.some(copy=>copy.points.length)){
    const host=document.querySelector('#route-preview'),mesh=routingPreview(route,c.name);
    previewCleanup=mountMeshViewer(host,mesh,E);
    const download=document.createElement('button');download.textContent='Download route coordinates';host.prepend(download);
    download.onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({engine:model.version,component:{id:c.id,name:c.name},coordinateFrame:'Native world XYZ',points:route.points.map(p=>({id:p.id,index:p.index,parent:p.parent})),copies:route.copies},null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='routing-coordinates.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
   }
  }else if(typ==='GEAR'){
   const gear=d.gears.find(g=>g.id===c.id),bogieIDs=new Set(gear.bogies.flatMap(b=>b.params.map(p=>p.id)));
   const names=(b,list)=>list.flatMap(n=>b.params.filter(p=>p.name===n));
   const tire=['TireMode','DiameterMode','DiameterIn','DiameterModel','WidthMode','WidthIn','WidthModel','SLRMode','DeflectionPct','StaticRadiusIn','StaticRadiusModel'],layout=['NumAcross','NumTandem','Symmetrical','XContactPt','YContactPt','ZAboveGround'],spacing=['SpacingType','Spacing','SpacingFrac','SpacingGap','SpacingGapFrac','PitchType','Pitch','PitchFrac','PitchGap','PitchGapFrac'];
   root.innerHTML=card('Landing gear setup',`<p>Choose the gear’s units before entering tire dimensions. Inch-based inputs always use inches; model-unit values follow this choice.</p>${params(names(c,['m_ModelLenUnits','GearConfigMode']))}${paramDetails(c.params.filter(p=>!bogieIDs.has(p.id)&&p.rawGroup==='GroundPlane'&&!p.name.includes('CG')),['ShowNominalGroundPlane','AutoPlaneFlag','PlaneSize'])}`)+
    gearCGMarkup(c,h)+
    card('Wheel groups',`${button('bogie-add','Add wheel group',true)}${gear.bogies.map((b,i)=>`<article class="tool-item"><h3>Wheel group ${i+1} · ${E(b.name)}</h3><h4>Wheel layout & contact</h4><div class="tool-fields">${params(names(b,layout))}</div><h4>Tire size & shape</h4><p class="native-tip">Choose each driver, then edit its unlocked value. OpenVSP calculates the other representations.</p><div class="tool-fields">${params(names(b,tire))}</div><details><summary>Across & tandem spacing</summary><div class="tool-fields">${params(names(b,spacing))}</div></details>${suspensionMarkup(b,h)}${tireDetailsMarkup(b,h)}${gearRetractionMarkup(b,c,model,h)}${paramDetails(b.params.filter(p=>![...layout,...tire,...spacing,...tireDetailNames,...suspensionNames].includes(p.name)&&!gearRetractionIDs(b).has(p.id)),[])}<button data-bogie-delete="${b.id}">Remove wheel group</button></article>`).join('')||'<p>Add a wheel group to build landing gear.</p>'}`,'wide')+card('Native gear preview',`<label><input type="checkbox" id="gear-preview-ground" ${gearGroundPreview?'checked':''}> Ground plane in preview</label>${button('gear-drawing-download','Download gear guides')}<div id="specialized-preview"></div>`,'wide')+card('Tire & suspension inspection','<div id="gear-tire-inspection"></div>','wide');
   bind('bogie-add',()=>mutate({operation:'bogie-add',geom:c.id}));document.querySelectorAll('[data-bogie-delete]').forEach(b=>b.onclick=()=>mutate({operation:'bogie-delete',geom:c.id,id:b.dataset.bogieDelete}));
   document.querySelectorAll('[data-bogie-parent]').forEach(el=>el.onclick=()=>mutate({operation:'bogie-attachment',geom:c.id,id:el.dataset.bogieParent,side:el.dataset.side,parent:val('gear-parent-'+el.dataset.bogieParent)}));
   document.querySelector('#gear-preview-ground').onchange=e=>{gearGroundPreview=e.target.checked;mountSpecializedPreview();};
   bind('gear-drawing-download',()=>{const data={engine:model.version,component:{id:c.id,name:c.name},coordinateFrame:'Native world XYZ',bogies:gear.bogies.map(b=>({id:b.id,name:b.name,...b.retraction}))},url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='gear-guides.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
   mountSpecializedPreview();
   mountTireInspection(document.querySelector('#gear-tire-inspection'),gear,c,app,h);
  }else if(typ==='AUXILIARY'){
   const a=d.auxiliary.find(g=>g.id===c.id),type=c.params.find(p=>p.name==='AuxiliaryGeomType'),bogies=[['','Automatic · first wheel group'],...d.gears.filter(g=>g.id===a.parent).flatMap(g=>g.bogies.map((b,i)=>[b.id,`Wheel group ${i+1} · ${b.name}`]))];
   root.innerHTML=card('Auxiliary shape & parent',`<p>Rotor tip paths and thrown blades require a propeller parent. Ground, gear-clearance, tire-spray and tire-failure shapes require a gear parent. Changing parent resets old gear contacts; OpenVSP assigns the first wheel group in the new gear.</p>${select('Auxiliary shape','aux-shape',type.choices.map(o=>[o.value,o.label]),type.value)}${select('Auxiliary parent','aux-parent',model.components.filter(g=>g.id!==c.id).map(g=>[g.id,g.name]),a.parent)}${button('aux-setup','Apply shape & parent',true)}`)+
    auxiliaryMarkup(a,c,model,h)+
    card('Native auxiliary preview','<div id="specialized-preview"></div>','wide');
   const eligibleParents=()=>{const mode=a.modes.find(m=>m.value===num('aux-shape')),blocked=new Set([c.id]);let previous;do{previous=blocked.size;model.components.filter(g=>blocked.has(g.parent)).forEach(g=>blocked.add(g.id));}while(blocked.size!==previous);const old=val('aux-parent'),items=model.components.filter(g=>!blocked.has(g.id)&&(!mode?.parentTypes.length||mode.parentTypes.includes(g.type.toUpperCase())));document.querySelector('#aux-parent').innerHTML=items.map(g=>`<option value="${E(g.id)}" ${g.id===old?'selected':''}>${E(g.name)}</option>`).join('');document.querySelector('#aux-setup').disabled=!items.length;};
   document.querySelector('#aux-shape').onchange=eligibleParents;eligibleParents();bind('aux-setup',()=>mutate({operation:'auxiliary-setup',geom:c.id,parent:val('aux-parent'),type:num('aux-shape')}));
   bindAuxiliary(a,c,h,model);
   mountSpecializedPreview();
  }else if(typ==='STACK'){
   root.innerHTML=card('Native stack presets',`<p>Build a nacelle, inlet, outlet, or flowpath using the engine’s preset. This replaces the current sections; Undo restores them.</p>${select('Stack preset','stack-preset',Object.keys(d.stackPresets).map(k=>[k,nice(k.replace('STACK_PRESET_',''))]))}${button('stack-preset-apply','Apply native stack preset',true)}<p>Use Cross-sections & skinning to adjust its profiles and blending.</p>`);bind('stack-preset-apply',()=>mutate({operation:'stack-preset',geom:c.id,preset:val('stack-preset')}));
  }else root.innerHTML=card('Specialized geometry',`<p>Select a body of revolution, route, landing gear, auxiliary component or stack.</p><p>${E(c.name)} uses ${c.params.length} native parameters. Search its dimensions, placement, and specialized settings in Design.</p>`);
 }
 return true;
 function mountSpecializedPreview(){
  if(previewCleanup){previewCleanup();previewCleanup=null;}
  const showPlane=c.type.toUpperCase()!=='GEAR'||gearGroundPreview||!c.params.find(p=>p.name==='ShowNominalGroundPlane')?.value,shown=showPlane?c:{...c,surfaces:c.surfaces.filter(s=>s.index%Math.max(1,c.mainSurfaceCount)!==0)};
  const gear=c.type.toUpperCase()==='GEAR'?d.gears.find(g=>g.id===c.id):null,parts=gear?gear.bogies.map((b,i)=>({index:i,name:`Wheel group ${i+1} · ${b.retraction.mode===0?'suspension':'retraction & suspension'} guides`,objects:b.retraction.objects})):[];
  const mesh=drawingMesh({parts,warnings:[],showContext:true,filename:c.name,displayNote:'Surfaces are sampled directly from OpenVSP, including physical symmetry copies. Click a displayed element to inspect its native XYZ coordinates.'},shown),host=document.querySelector('#specialized-preview');
  if(mesh.elements.length)previewCleanup=mountMeshViewer(host,mesh,E);else host.innerHTML='<p>No native surface is available yet. Check the shape, parent and contact setup.</p>';
 }
}

function gearCGMarkup(c,h){
 const local=Boolean(c.params.find(p=>p.name==='CGLocalFlag')?.value),frame=local?'Local':'Global';
 const fields=(part,suffix=frame)=>'XYZ'.split('').flatMap(axis=>c.params.filter(p=>p.name===axis+'CG'+part+suffix));
 return h.card('Center of gravity for gear checks',`<p>These inputs supply OpenVSP’s landing-gear checks. Choose the coordinate frame, then enter the nominal CG and its range in gear model units. OpenVSP transforms the other frame and limits the range around the nominal CG.</p>${h.params(c.params.filter(p=>p.name==='CGLocalFlag'))}<h3>Nominal center of gravity</h3><div class="tool-fields">${h.params(fields('Nominal'))}</div><details><summary>CG range</summary><div class="tool-fields">${h.params(fields('Min'))}${h.params(fields('Max'))}</div></details><details><summary>Calculated coordinates in the other frame</summary><div class="tool-fields">${h.params(['Nominal','Min','Max'].flatMap(part=>fields(part,local?'Global':'Local')))}</div></details>`,'wide');
}
