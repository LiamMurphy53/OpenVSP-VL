import {elementFields} from './part-properties.js?v=20261011-elements';
export function regionBoundaryControls(region,h,structural=false){
 const {E,paramDetails}=h,guide=region.boundaryGuide;
 const fields=region.params.filter(p=>!elementFields.includes(p.name)&&(!structural||!['NCurves','ICurve'].includes(p.name)));
 if(!guide)return paramDetails(fields,['MainSurfIndx','Center_U','Center_W','U_Length','W_Length','Theta','Test_Type','Const_Line_Type','Const_Line_Value','Value_01']);
 const primary=guide.primary.map(id=>fields.find(p=>p.id===id)).filter(Boolean),ids=new Set(primary.map(p=>p.id));
 const linked=fields.filter(p=>!ids.has(p.id)&&p.readOnly),rest=fields.filter(p=>!ids.has(p.id)&&!p.readOnly);
 return `<section><h4>Boundary settings</h4>${paramDetails(primary,primary.map(p=>p.name))}<p class="native-tip">${E(guide.note)}</p></section>${linked.length?`<details><summary>Native linked boundary values</summary>${linked.map(p=>`${paramDetails([p],[p.name])}<p class="native-tip">${E(p.readOnlyReason||'Calculated by OpenVSP.')}</p>`).join('')}</details>`:''}${rest.length?`<details><summary>Other region settings (${rest.length})</summary>${paramDetails(rest,rest.map(p=>p.name))}</details>`:''}`;
}
