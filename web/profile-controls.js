export function selectedProfile(component,index){return component.sections[index]?.profileControls||component.profileControls;}
let previewPlane='xy';
export function setProfilePreviewPlane(plane){if(['xy','xz','yz'].includes(plane))previewPlane=plane;}
export function profilePromotedIDs(component,index){
 const profile=selectedProfile(component,index);return profile?(profile.edgeEditing?profile.parameters:[...profile.transforms,...(profile.chevrons?.parameters||[]),...(profile.shapeFields||[])]):[];
}

function profilePreview(points){
 const axes={xy:[0,1],xz:[0,2],yz:[1,2]}[previewPlane],plane=previewPlane.toUpperCase().split('').join('/');
 const xy=(points||[]).filter(p=>axes.every(i=>Number.isFinite(p[i]))).map(p=>axes.map(i=>p[i]));if(!xy.length)return '';
 const xs=xy.map(p=>p[0]),ys=xy.map(p=>p[1]),xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);
 const factor=Math.min(256/(xmax-xmin||1),116/(ymax-ymin||1));
 const map=p=>[(p[0]-(xmin+xmax)/2)*factor+140,70-(p[1]-(ymin+ymax)/2)*factor];
 const path=xy.map((p,i)=>(i?'L':'M')+map(p).map(n=>Number(n.toFixed(5))).join(' ')).join(' ');
 return `<label for="profile-preview-plane">Profile preview view</label><select id="profile-preview-plane">${['xy','xz','yz'].map(p=>`<option value="${p}" ${p===previewPlane?'selected':''}>Local ${p.toUpperCase().split('').join('/')}</option>`).join('')}</select><div class="prop-native-plot"><svg role="img" aria-label="Native profile samples in the local ${plane} plane" viewBox="0 0 280 140"><path d="${path}" fill="none" stroke="#28745c" stroke-width="1.8" stroke-linejoin="round"/></svg></div><p class="native-tip">Native profile samples · local ${plane} projection</p>`;
}

export function profileControlsMarkup(component,index,{esc,parameterField}){
 const profile=selectedProfile(component,index);if(!profile)return '';
 const byID=new Map(component.params.map(p=>[p.id,p]));
 const fields=ids=>ids.map(id=>byID.get(id)).filter(Boolean);
 const group=(title,ids,key,note)=>{
  const params=fields(ids),editable=params.filter(p=>!p.displayReadOnly&&p.active!==false),locked=params.filter(p=>p.displayReadOnly||p.active===false);
  return `<details class="wing-secondary-controls" data-group="profile-${key}"><summary>${esc(title)}</summary>${note?`<p class="native-tip">${esc(note)}</p>`:''}${editable.map(parameterField).join('')}${locked.length?`<details data-group="profile-${key}-computed"><summary>Calculated or unused values</summary>${locked.map(parameterField).join('')}</details>`:''}</details>`;
 };
 const selector=component.sections.length?`<div class="tool-field"><label for="design-profile-choice">Profile</label><select id="design-profile-choice">${component.sections.map((s,i)=>s.profileControls?`<option value="${i}" ${i===index?'selected':''}>Surface ${s.surface} · Profile ${s.index}</option>`:'').join('')}</select></div>`:'';
 const note=profile.edgeEditing?'Closure sets the edge gap. Trimming cuts back the original profile. A profile flap changes the section shape; surface-region controls are in Modeling tools.':'Local transforms change this section outline. Edge modifiers are available for wing, blade and body-of-revolution profiles.';
 const transform=group('Profile rotation, scale & alignment',profile.transforms,'transform','Offsets are fractions of profile width. These local transforms apply before section placement.');
 const flapFields=profile.manualFlapBreak?['mode','basis','length','lengthFraction','hinge','parameter','arc','active','deflection'].map(key=>profile.flap[key]):Object.values(profile.flap);
 const flapNote=profile.manualFlapBreak?'Blade flaps need explicit native break settings: choose Plain flap, set the alignment break and a positive hinge transition width, enable blade flap geometry, then change deflection. Match the break on neighboring blade profiles.':'Flap length is measured forward from the trailing edge. Hinge position runs from lower to upper surface through the local profile thickness.';
 const edges=profile.edgeEditing?profile.close.map((close,i)=>`<details class="wing-secondary-controls" data-group="profile-edge-${close.edge}"><summary>${esc(close.label)}</summary>${group('Edge closure',Object.values(close.fields),'close-'+close.edge,'Choose a method, then set the gap as a length or a fraction of chord / width.')}${group('Edge trimming',Object.values(profile.trim[i].fields),'trim-'+close.edge,'Choose whether OpenVSP finds the new edge by distance or by thickness. Other dimensions follow the selected driver.')}</details>`).join('')+group('Trailing-edge profile flap',flapFields,'flap',flapNote):'';
 const c=profile.chevrons,chevrons=c?`<details class="wing-secondary-controls" data-group="profile-chevrons"><summary>Chevrons</summary><p class="native-tip">A repeating 3D pattern around all or part of this profile. Use the X/Z or Y/Z preview to inspect displacement outside its original plane.</p>${parameterField(byID.get(c.mode))}${c.notice?`<p class="coverage-note">${esc(c.notice)}</p>`:''}${group('Pattern & rounding',c.pattern,'chevron-pattern','Plateau fractions control the flat part of each peak and valley. Their combined fraction follows the native limit.')}${group('Outline coverage',c.extent,'chevron-extent','Choose start/end or center/width drivers. Named guides fix a position; Free position enables its fraction. Partial coverage can cross the profile seam. Full coverage keeps an editable start phase.')}${group('Chevron symmetry',c.symmetry,'chevron-symmetry','All matching directions follow Top. Top/bottom follows Top; right/left follows Right.')}${c.directions.map(d=>group(d.label+' displacement',d.parameters,'chevron-'+d.label.toLowerCase(),'Amplitude uses model length. Angle and slew orient the native displacement.')).join('')}</details>`:'';
 return `<details class="parameter-group geometry-primary" data-group="profile-shape"><summary>Profile shape & edges</summary>${selector}${profilePreview(component.sections[index]?.profile||profile.preview)}<p class="native-tip">${esc(note)}</p>${group('Profile dimensions & shape',profile.shapeFields||[],'dimensions','Dimensions and shape controls for the selected profile family.')}${transform}${edges}${chevrons}</details>`;
}
