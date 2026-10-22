// Native parameter IDs and driver combinations come from the official engine.
export function wingSection(component,index){
 const sections=component.sections.filter(s=>s.driverControls?.length);
 return sections.find(s=>s.index===index)||sections[0]||null;
}
export function wingPromotedIDs(component,index){
 const s=wingSection(component,index);if(!s)return[];
 return [...s.driverParameterIDs,...s.shapeParameterIDs,...component.params.filter(p=>p.rawGroup==='WingGeom'&&['RelativeDihedralFlag','RelativeTwistFlag'].includes(p.name)).map(p=>p.id)];
}
export function wingControlsMarkup(component,index,{esc,parameterField,streamlined=false}){
 const s=wingSection(component,index);if(!s)return'';
 const byID=new Map(component.params.map(p=>[p.id,p])),driverFields=s.driverControls.map(d=>({...byID.get(d.parameter),label:d.label}));
 const geometry=s.driverParameterIDs.slice(8).map(pid=>byID.get(pid)).concat(s.shapeParameterIDs.map(pid=>byID.get(pid)));
 const label={Sweep:'Sweep',Sweep_Location:'Sweep reference (chord fraction)',Sec_Sweep_Location:'Secondary sweep reference (chord fraction)',Twist:'Twist',Dihedral:'Dihedral',Twist_Location:'Twist axis (chord fraction)'};
 const angles=geometry.filter(p=>['Sweep','Twist','Dihedral'].includes(p.name)),locations=geometry.filter(p=>!angles.includes(p));
 const references=component.params.filter(p=>p.rawGroup==='WingGeom'&&['RelativeDihedralFlag','RelativeTwistFlag'].includes(p.name)).map(p=>({...p,label:p.name==='RelativeTwistFlag'?'Twist reference':'Dihedral reference',choices:[[0,'Absolute'],[1,'Relative to previous section']]}));
 const presets=[['Span, root & tip chords',['Section span','Root chord','Tip chord']],['Span, area & taper',['Section span','Section area','Taper ratio']],['Aspect ratio, area & taper',['Aspect ratio','Section area','Taper ratio']]].map(([label,names])=>[label,names.map(n=>s.driverControls.find(d=>d.label===n)?.value)]).filter(([,values])=>values.every(v=>v!==undefined));
 const active=presets.find(([,values])=>JSON.stringify([...values].sort((a,b)=>a-b))===JSON.stringify([...s.drivers].sort((a,b)=>a-b)));
 const sizing=streamlined?`<label class="tool-field" for="wing-sizing-preset">Size using<select id="wing-sizing-preset">${!active?'<option value="current">Current custom drivers</option>':''}${presets.map(([label,values])=>`<option value="${esc(JSON.stringify(values))}" ${active?.[0]===label?'selected':''}>${esc(label)}</option>`).join('')}</select></label><button id="apply-wing-sizing" disabled>Apply sizing method</button>`:'';
 return `<details class="parameter-group geometry-primary wing-section-editor" data-group="wing-section"><summary>Wing section dimensions</summary><p class="native-tip">Section span runs between neighboring profiles. Choose three independent dimensions; OpenVSP calculates the others.</p><div class="tool-field"><label for="wing-section-choice">Wing section</label><select id="wing-section-choice">${component.sections.filter(s=>s.driverControls?.length).map(section=>`<option value="${section.index}" ${section.index===s.index?'selected':''}>Section ${section.index}${section.alias?' · '+esc(section.alias):''}</option>`).join('')}</select></div>${sizing}<div class="driver-row" ${streamlined?'hidden':''}>${s.drivers.map((value,i)=>`<label class="tool-field">Driver ${i+1}<select aria-label="Wing driver ${i+1}" data-wing-driver="${i}">${s.driverControls.map(d=>`<option value="${d.value}" ${value===d.value?'selected':''}>${esc(d.label)}</option>`).join('')}</select></label>`).join('')}</div><button id="apply-wing-drivers" ${streamlined?'hidden':''}>Apply section drivers</button><p id="wing-driver-status" class="native-tip" role="status" ${streamlined?'hidden':''}></p>${driverFields.filter(p=>!p.displayReadOnly).map(parameterField).join('')}${angles.map(p=>parameterField({...p,label:label[p.name]})).join('')}<details class="wing-secondary-controls" data-group="wing-calculated"><summary>Calculated section dimensions</summary>${driverFields.filter(p=>p.displayReadOnly).map(parameterField).join('')}</details><details class="wing-secondary-controls" data-group="wing-references"><summary>Angle references & locations</summary><p class="native-tip">Reference choices apply across the wing. Locations are native chord fractions.</p>${references.map(parameterField).join('')}${locations.map(p=>parameterField({...p,label:label[p.name]})).join('')}</details></details>`;
}

const blendSelections=new Map();
const blendNames=['InLE','OutLE','InTE','OutTE'].flatMap(edge=>['Mode','Sweep','Dihedral','Strength'].map(suffix=>edge+suffix));
function blendProfiles(c){return c.type.toUpperCase()==='WING'?c.sections.filter(s=>s.surface===0):[];}
function blendFields(c,s){const group=c.params.find(p=>p.id===s.driverParameterIDs?.[0])?.group||c.params.find(p=>p.rawGroup==='XSec'&&p.group===`XSec_${s.index}`)?.group;return c.params.filter(p=>p.rawGroup==='XSec'&&p.group===group&&blendNames.includes(p.name));}
export function wingBlendIDs(c){return blendProfiles(c).flatMap(s=>blendFields(c,s).map(p=>p.id));}
export function wingBlendMarkup(c,{esc,parameterField}){
 const profiles=blendProfiles(c),s=profiles.find(s=>s.index===blendSelections.get(c.id))||profiles[0];if(!s)return '';
 blendSelections.set(c.id,s.index);const fields=blendFields(c,s);
 if(!fields.length)return '';
 return `<details class="parameter-group geometry-primary" data-group="wing-blending"><summary>Wing profile blending</summary><p class="native-tip">Shape how the wing enters and leaves each airfoil profile. Automatic lets OpenVSP choose the tangent. Matching follows a neighboring trapezoid or angle constraint.</p><label class="tool-field">Airfoil profile<select data-wing-blend-profile aria-label="Wing blending airfoil profile">${profiles.map(p=>`<option value="${p.index}" ${p.index===s.index?'selected':''}>${p.index===0?'Root':p.index===profiles.length-1?'Tip':'Profile '+p.index}${p.alias?' · '+esc(p.alias):''}</option>`).join('')}</select></label>${[['InLE','Inboard leading edge'],['OutLE','Outboard leading edge'],['InTE','Inboard trailing edge'],['OutTE','Outboard trailing edge']].map(([edge,label])=>`<details data-group="wing-blend-${edge}" open><summary>${label}</summary>${['Mode','Sweep','Dihedral','Strength'].map(suffix=>fields.find(p=>p.name===edge+suffix)).filter(Boolean).map(parameterField).join('')}</details>`).join('')}</details>`;
}
export function bindWingBlend(host,c,render){const select=host.querySelector('[data-wing-blend-profile]');if(select)select.onchange=()=>{blendSelections.set(c.id,Number(select.value));render();};}
