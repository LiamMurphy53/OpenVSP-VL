// Attachment coordinates and frame points come from the official engine.
export function attachmentPromotedIDs(component){return component.attachment?.parameters||[];}
export function attachmentControlsMarkup(component,components,{esc,parameterField,displayValue,unitSuffix,visible}){
 const a=component.attachment;if(!a)return '';
 const byID=new Map(component.params.map(p=>[p.id,p])),field=name=>component.params.find(p=>p.rawGroup==='Attach'&&p.name===name);
 const allowed=components.filter(candidate=>{
  const seen=new Set();let current=candidate;
  while(current){if(current.id===component.id||seen.has(current.id))return false;seen.add(current.id);current=components.find(c=>c.id===current.parent);}
  return true;
 });
 const parent=components.find(c=>c.id===a.parent),relative=component.params.find(p=>p.rawGroup==='XForm'&&p.name==='Abs_Or_Relitive_flag')?.value===1;
 const modes=['Trans_Attach_Flag','Rots_Attach_Flag'].map(field).filter(Boolean);
 const selected=new Set(modes.map(p=>p.value));
 const notes=[relative?'Placement offsets and rotations are relative to this attachment frame.':'Global placement preserves the part’s world position when the attachment changes. Choose “Relative to attachment” in Placement to follow it.'];
 if(!parent)notes.push('Choose a parent component to use a surface or volume reference. Without a parent, OpenVSP uses the global frame.');
 else if(a.isJoint)notes.push('This joint parent supplies its native joint frame. OpenVSP locks the attachment selectors and coordinates.');
 else{
  if([...selected].some(v=>v>=2))notes.push(a.parentHasSurface?'Surface and volume coordinates refer to the parent’s first main surface (surface 0).':'This parent has no attachment surface. OpenVSP falls back to its component frame.');
  if(selected.has(5))notes.push(a.parentType==='WING'?'Eta follows the parent wing’s span. M and N locate the point within the section.':'For a parent other than a wing, OpenVSP uses eta as the uniform L coordinate.');
 }
 const groups=a.groups.filter(g=>g.enabled).map(g=>{
  const params=g.parameters.map(id=>byID.get(id)).filter(Boolean),editable=params.filter(p=>p.active!==false&&!p.displayReadOnly),calculated=params.filter(p=>p.active===false||p.displayReadOnly);
  return `<details class="wing-secondary-controls attachment-coordinate-group" data-group="attachment-coordinates-${esc(g.title)}"><summary>${esc(g.title)}</summary>${editable.map(parameterField).join('')}${calculated.length?`<details class="wing-secondary-controls" data-group="attachment-${esc(g.title)}"><summary>Calculated coordinates</summary>${calculated.map(parameterField).join('')}</details>`:''}</details>`;
 }).join('');
 const origin=a.frame.points[0],unit=unitSuffix('length');
 return `<details class="parameter-group geometry-primary" data-group="attachment"><summary>Attach to another component</summary><div class="tool-field"><label for="attachment-parent">Parent component</label><select id="attachment-parent"><option value="" ${!parent?'selected':''}>None · global frame</option>${allowed.map(c=>`<option value="${esc(c.id)}" ${a.parent===c.id?'selected':''}>${esc(c.name)} · ${esc(c.type)}</option>`).join('')}</select></div><button id="apply-attachment-parent" disabled>Apply parent</button><p id="attachment-parent-status" class="native-tip" role="status">${parent?'Attached to '+esc(parent.name)+'.':'No parent component.'}</p>${modes.map(parameterField).join('')}${notes.map(n=>`<p class="native-tip">${esc(n)}</p>`).join('')}<label class="attachment-frame-toggle"><input type="checkbox" id="show-attachment-frame" ${visible?'checked':''}> Show attachment axes in model</label>${groups}<details class="wing-secondary-controls" data-group="attachment-frame"><summary>Attachment frame</summary><p class="native-tip">Frame origin in global coordinates (${esc(unit)}). Axis endpoints use one native model unit. The frame is supplied by OpenVSP before the part’s Placement offsets.</p><table class="result-table"><tbody>${origin.map((v,i)=>`<tr><td>${'XYZ'[i]}</td><td>${Number(displayValue(v,'length').toPrecision(12))} ${esc(unit)}</td></tr>`).join('')}</tbody></table><button id="download-attachment-frame">Download frame data</button></details></details>`;
}
export function drawAttachmentFrame(ctx,project,component,visible){
 const points=component?.attachment?.frame.points;if(!visible||!points)return;
 const origin=project(points[0]);ctx.save();ctx.lineWidth=2.5;ctx.font='bold 12px sans-serif';
 for(let i=1;i<4;i++){
  const end=project(points[i]);ctx.strokeStyle=ctx.fillStyle=['','#bc4f43','#468553','#437cae'][i];
  ctx.beginPath();ctx.moveTo(origin[0],origin[1]);ctx.lineTo(end[0],end[1]);ctx.stroke();ctx.fillText('XYZ'[i-1],end[0]+5,end[1]-5);
 }
 ctx.fillStyle='#314f43';ctx.beginPath();ctx.arc(origin[0],origin[1],3,0,Math.PI*2);ctx.fill();ctx.restore();
}
