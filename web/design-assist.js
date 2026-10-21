import {customSliderMarkup,bindCustomSliders} from './custom-sliders.js?v=20261020-release';
import {displayValue,nativeValue,unitSuffix} from './display-units.js?v=20261019';
const sliderRanges={'wing-aspect-ratio':[.2,40],'wing-taper':[.05,2],'wing-sweep':[-70,70],'wing-dihedral':[-45,90],'wing-washout':[-30,30],'wing-thickness':[.1,40],'wing-camber':[0,15],'prop-pitch':[-45,90],'prop-blades':[1,16],'prop-thickness':[.1,40]};
const assistDimension=control=>control.startsWith('body-')?'length':['wing-taper','wing-aspect-ratio','wing-thickness','wing-camber','prop-thickness','prop-blades'].includes(control)?null:'angle';
export function assistSliderParameter(c,control,value,dimension,disabled=false){
 const mixed=value===null;
 if(mixed){const bounds=sliderRanges[control];if(!bounds)return null;value=Math.max(bounds[0],Math.min(bounds[1],0));}
 if(!Number.isFinite(value))return null;
 const bounds=sliderRanges[control]||[.001,Math.max(1,value*2)];
 return {mixed,id:`assist:${c.id}:${control}`,control,name:control,value,type:control==='prop-blades'?1:0,dimension,min:Math.min(bounds[0],value),max:Math.max(bounds[1],value),active:!disabled,customSlider:{key:`assist:${c.id}:${control}`,range:(bounds[1]-bounds[0])/2,adjustable:true}};
}
export function designAssistMarkup(c,E,parameterField){
 const d=c.designAssist;if(!d)return '';
 const field=(control,label,value,dimension,note)=>{
 const disabled=control==='wing-camber'&&!d.camberAvailable||control==='wing-thickness'&&!d.thicknessAvailable;
 const p=assistSliderParameter(c,control,value,dimension,disabled);
 const slider=p?(p.mixed?'<small class="native-tip">Mixed values — drag to set across sections.</small>':'')+customSliderMarkup({...p,label},'assist-'+control,{esc:E,displayValue,parameterDimension:p=>p.dimension,readOnly:p=>!p.active}):'';
 return `<div class="design-assist-control"><label class="tool-field" for="assist-${control}">${E(label)}${dimension?` (${E(unitSuffix(dimension))})`:''}<input id="assist-${control}" data-assist-input="${control}" type="number" step="any" ${control==='wing-camber'&&!d.camberAvailable||control==='wing-thickness'&&!d.thicknessAvailable?'disabled':''} value="${value===null?'':Number(displayValue(value,dimension).toPrecision(12))}" placeholder="${value===null?'Set across sections':''}" aria-label="${E(label)}"><small>${E(control==='wing-camber'&&!d.camberAvailable||control==='wing-thickness'&&!d.thicknessAvailable?'Requires compatible airfoil profiles at every station. Configure profiles in Pro.':note)}</small></label><button data-assist-apply="${control}" ${control==='wing-camber'&&!d.camberAvailable||control==='wing-thickness'&&!d.thicknessAvailable?'disabled':''}>Apply</button>${slider}</div>`;};
 const dimensions=(d.kind==='prop'?[['Design','Diameter','Propeller diameter']]:d.kind==='wing'?[['WingGeom','TotalSpan','Full wingspan'],['WingGeom','TotalArea','Wing area']]:[['Design','Length','Body length']]).map(([group,name,label])=>{const p=c.params.find(p=>p.rawGroup===group&&p.name===name);return p?parameterField({...p,label}):'';}).join('');
 const arParm=c.params.find(p=>p.rawGroup==='WingGeom'&&p.name==='TotalAR');
 const aspect=d.kind==='wing'?field('wing-aspect-ratio','Aspect ratio',d.aspectRatio,null,'Keeps wing area fixed and adjusts span and chords together. Uses projected wingspan squared / wing area.')+(arParm?`<button type="button" class="property-lock" data-property-lock="${E(arParm.id)}" aria-label="${arParm.userLocked?'Unlock':'Lock'} Aspect ratio" aria-pressed="${!!arParm.userLocked}">${arParm.userLocked?'🔒 Unlock aspect ratio':'Lock aspect ratio'}</button>`:''):'';
 const controls=d.kind==='prop'?
  field('prop-pitch','Collective pitch at ¾ radius',d.pitch,'angle','Sets the pitch driver and lets OpenVSP coordinate feather angle and blade geometry.')+
  field('prop-blades','Evenly spaced blade count',d.blades,null,'Sets blade count and uniform spacing together.')+
  field('prop-thickness','Blade thickness (%)',d.thicknessPercent,null,'Sets a uniform thickness/chord distribution across the blade, retaining its radius stations and curve type.'):
  d.kind==='wing'?
  (d.taperAvailable?field('wing-taper','Overall taper ratio',d.taper,null,'Tip chord / root chord. Adjusts existing section proportions while keeping wing area and section spans. Uses span/root/tip section drivers.'):'')+
  field('wing-sweep','Quarter-chord sweep',d.sweep,'angle','Sets sweep and its quarter-chord reference on every wing section.')+
  field('wing-dihedral','Wing dihedral',d.dihedral,'angle','Sets every section to this absolute dihedral angle.')+
  (d.washoutAvailable?field('wing-washout','Tip washout',d.washout,'angle','Positive values reduce tip twist relative to the root. Distributes twist by section span, preserves root twist, and sets absolute quarter-chord twist axes.'): '')+
  field('wing-thickness','Airfoil thickness (%)',d.thicknessPercent,null,'Sets thickness/chord on every wing profile. A value of 12 means 12% thickness.')+
  field('wing-camber','Airfoil camber (%)',d.camberPercent,null,'Sets maximum-camber input and camber/chord across compatible wing profiles.'):
  field('body-width','Maximum section width',d.width,'length','Scales section widths together, preserving their relative sizes. Circular sections change both dimensions.')+
  field('body-height','Maximum section height',d.height,'length','Scales section heights together, preserving their relative sizes. Circular sections change both dimensions.')+
  (d.noseLength===undefined?'':field('body-nose','Nose station length',d.noseLength,'length','Distance from the nose to the first interior section. Repositions interior stations together while holding the last station fixed.')+field('body-tail','Tail station length',d.tailLength,'length','Distance from the last interior section to the tail. Repositions interior stations together while holding the first station fixed.'));
 return `<details class="parameter-group geometry-primary" data-group="design-assist" open><summary>${d.kind==='wing'?'Wing design':d.kind==='prop'?'Propeller design':'Body proportions'}</summary>${aspect}${dimensions}${controls}</details>`;
}
export function bindDesignAssist(host,c,{mutate,toast,isBusy=()=>false,liveEdit}){host.querySelectorAll('[data-assist-apply]').forEach(button=>button.onclick=()=>{const control=button.dataset.assistApply,input=host.querySelector(`[data-assist-input="${control}"]`);if(!input.value.trim()||!Number.isFinite(Number(input.value))){toast('Enter a finite value.');return;}const dimension=assistDimension(control);return mutate({operation:'design-assist',geom:c.id,control,value:nativeValue(Number(input.value),dimension)});});
 const parameters=[...host.querySelectorAll('[data-assist-input]')].map(input=>{const control=input.dataset.assistInput,dimension=assistDimension(control);return assistSliderParameter(c,control,input.value.trim()===''?null:nativeValue(Number(input.value),dimension),dimension,input.disabled);}).filter(Boolean);
 bindCustomSliders(host,parameters,{displayValue,parameterDimension:p=>p.dimension,isBusy,liveEdit:liveEdit?(p,slider,value,finished)=>liveEdit(p.id,slider,{operation:'design-assist',geom:c.id,control:p.control,value:nativeValue(value,p.dimension)},finished):undefined});
}

export function wingMountMarkup(c,components,E){
 const descendant=(candidate)=>{const seen=new Set();let parent=candidate.parent;while(parent&&parent!=='NONE'&&!seen.has(parent)){if(parent===c.id)return true;seen.add(parent);parent=components.find(g=>g.id===parent)?.parent;}return false;};
 const wings=components.filter(g=>g.type.toUpperCase()==='WING'&&g.id!==c.id&&!descendant(g));if(!wings.length)return '';
 const param=(group,name)=>c.params.find(p=>p.rawGroup===group&&p.name===name)?.value;
 const mounted=param('Attach','Trans_Attach_Flag')===5&&wings.some(g=>g.id===c.parent);
 return `<details class="parameter-group geometry-primary" data-group="wing-mount"><summary>Mount on a wing</summary><label class="tool-field">Parent wing<select data-mount-parent aria-label="Mount parent wing">${wings.map(g=>`<option value="${E(g.id)}" ${g.id===c.parent?'selected':''}>${E(g.name)} · ${g.id.slice(0,6)}</option>`).join('')}</select></label><label class="tool-field">Span position (%)<input data-mount-span aria-label="Mount span position (%)" type="number" min="0" max="100" step="any" value="${mounted?100*param('Attach','Eta_Attach_Location'):50}"></label><label class="tool-field"><input data-mount-follow type="checkbox" ${param('Attach','Rots_Attach_Flag')===1?'checked':''}> Follow wing axes</label><p class="native-tip">Places the component origin at the native wing volume center at this span fraction and clears position offsets. 0% is root; 100% is tip on the parent’s original wing surface.</p><button data-mount-apply>Apply wing mount</button></details>`;
}
export function bindWingMount(host,c,{mutate,toast}){const button=host.querySelector('[data-mount-apply]');if(!button)return;button.onclick=()=>{const field=host.querySelector('[data-mount-span]'),value=Number(field.value);if(!field.value.trim()||!Number.isFinite(value)||value<0||value>100){toast('Use a span position from 0 to 100 percent.');return;}return mutate({operation:'design-assist',control:'wing-mount',geom:c.id,parent:host.querySelector('[data-mount-parent]').value,value,followOrientation:host.querySelector('[data-mount-follow]').checked});};}
