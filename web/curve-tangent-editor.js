import {customSliderMarkup,bindCustomSliders} from './custom-sliders.js?v=20261021-more';
const units={displayValue:x=>x,parameterDimension:()=>null};
export function tangentSliderParameters(section,control,side){
 const handle=control.handles[side];
 return handle.parameters.map((p,i)=>({...p,id:`tangent-${i}`,name:`Tangent handle ${'XYZ'[i]}`,type:0,value:handle.coordinates[i],customSlider:{key:`tangent:${section.id}:${control.anchor}:${side}:${i}`,range:Math.max(.1,Math.abs(handle.coordinates[i])*.5),adjustable:true}}));
}
export function tangentCoordinates(inputs,handle){
 const xyz=inputs.map((input,i)=>!handle.parameters[i].active?handle.coordinates[i]:Number(input.value));
 if(inputs.some((input,i)=>handle.parameters[i].active&&(!input.value.trim()||!Number.isFinite(xyz[i])||xyz[i]<handle.parameters[i].min||xyz[i]>handle.parameters[i].max)))throw Error('Enter finite coordinates within the native limits.');
 return xyz;
}
// The chosen native handle drives the tangent; no curve equations run here.
const selections=new Map();
export function mountTangentEditor(host,section,mutate,esc,{liveEdit,isBusy=()=>false,toast=()=>{}}={}){
 const controls=section.tangentControls||[];
 if(!controls.length){host.innerHTML='<p class="native-tip">Choose Cubic Bezier interpolation to edit incoming and outgoing tangents.</p>';return;}
 const saved=selections.get(section.id)||{anchor:controls.find(c=>c.anchor>0)?.anchor??0,side:'outgoing'};
 if(!controls.some(c=>c.anchor===saved.anchor))saved.anchor=controls[0].anchor;
 function render(highlight=false){
  const control=controls.find(c=>c.anchor===saved.anchor),sides=Object.keys(control.handles);
  if(!sides.includes(saved.side))saved.side=sides[0];
  selections.set(section.id,saved);
  const handle=control.handles[saved.side],sliderParameters=tangentSliderParameters(section,control,saved.side);
  host.innerHTML=`<h3>Tangent direction</h3><p class="native-tip">Choose the handle that drives the tangent. With Smooth tangent on, OpenVSP aligns the opposite handle while preserving its length. Symmetry may lock coordinates or adjust the applied tangent.</p><div class="tool-fields"><label class="tool-field">Curve anchor<select aria-label="Tangent anchor">${controls.map(c=>`<option value="${c.anchor}" ${c.anchor===saved.anchor?'selected':''}>Anchor ${c.anchor} · U ${esc(Number(c.u.toPrecision(8)))}</option>`).join('')}</select></label><label class="tool-field">Driving handle<select aria-label="Driving tangent">${sides.map(side=>`<option value="${side}" ${side===saved.side?'selected':''}>${side==='incoming'?'Incoming':'Outgoing'} tangent · Point ${control.handles[side].point}</option>`).join('')}</select></label></div><label class="membership-row"><input type="checkbox" aria-label="Smooth selected tangent" ${control.smooth?'checked':''} ${control.smoothActive?'':'disabled'}>Smooth tangent${control.smoothActive?'':' · locked by OpenVSP'}</label><div class="tool-fields">${handle.parameters.map((p,i)=>`<label class="tool-field">Handle ${'XYZ'[i]} (normalized)<input id="tangent-${i}" aria-label="Tangent handle ${'XYZ'[i]}" data-tangent-axis="${i}" type="number" step="any" min="${p.min}" max="${p.max}" value="${esc(handle.coordinates[i])}" ${p.active?'':'disabled title="Locked by OpenVSP"'}>${customSliderMarkup(sliderParameters[i],`tangent-${i}`,{...units,esc,readOnly:p=>!p.active})}</label>`).join('')}</div><div class="tool-actions"><button data-apply-tangent class="primary" disabled>Apply tangent</button></div><p data-tangent-status class="native-tip" role="status">Point ${handle.point} drives the ${saved.side} tangent at anchor ${control.anchor}. Coordinates are normalized to the section dimensions.</p>`;
  host.querySelector('[aria-label="Tangent anchor"]').onchange=e=>{saved.anchor=Number(e.target.value);render(true);};
  host.querySelector('[aria-label="Driving tangent"]').onchange=e=>{saved.side=e.target.value;render(true);};
  host.querySelector('[aria-label="Smooth selected tangent"]').onchange=e=>mutate({operation:'curve-smooth',point:control.anchor,smooth:e.target.checked});
  const inputs=[...host.querySelectorAll('[data-tangent-axis]')],button=host.querySelector('[data-apply-tangent]'),status=host.querySelector('[data-tangent-status]');
  function values(){return inputs.map((input,i)=>!handle.parameters[i].active?handle.coordinates[i]:Number(input.value));}
  function validate(){const xyz=values(),invalid=inputs.some((input,i)=>handle.parameters[i].active&&(!input.value.trim()||!Number.isFinite(xyz[i])||xyz[i]<handle.parameters[i].min||xyz[i]>handle.parameters[i].max));button.disabled=invalid||xyz.every((v,i)=>v===handle.coordinates[i]);status.textContent=invalid?'Enter finite coordinates within the native limits.':`Point ${handle.point} drives the ${saved.side} tangent at anchor ${control.anchor}. Coordinates are normalized to the section dimensions.`;return !invalid;}
  inputs.forEach(input=>{input.oninput=validate;input.onkeydown=e=>{if(e.key==='Enter'&&!button.disabled){e.preventDefault();button.click();}};});
  bindCustomSliders(host,sliderParameters,{...units,isBusy,liveEdit:(p,slider,value,finished)=>{
   try{
    const request={operation:'curve-tangent',anchor:control.anchor,side:saved.side,xyz:tangentCoordinates(inputs,handle)};
    validate();
    return liveEdit?liveEdit(p.customSlider.key,slider,request,finished):finished?mutate(request):undefined;
   }catch(error){toast(error.message);}
  }});
  button.onclick=async()=>{if(!validate())return;button.disabled=true;try{await mutate({operation:'curve-tangent',anchor:control.anchor,side:saved.side,xyz:values()});}finally{if(button.isConnected)validate();}};
  if(highlight)document.getElementById('curve-handle-editor')?.dispatchEvent(new CustomEvent('curve-select-point',{detail:handle.point}));
 }
 document.getElementById('curve-handle-editor')?.addEventListener('curve-selected-point',e=>{for(const control of controls)for(const [side,handle] of Object.entries(control.handles))if(handle.point===e.detail){saved.anchor=control.anchor;saved.side=side;render();return;}});
 render();
}
