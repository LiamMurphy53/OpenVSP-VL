import {elementFields} from './part-properties.js?v=20261011-elements';
// Driver selection and linked values are supplied by the native placement guide.
export function partPlacement(part,h){
 const {E,paramDetails}=h,guide=part.placementGuide;
 const fields=part.params.filter(p=>!elementFields.includes(p.name));
 if(!guide)return paramDetails(fields,['RelCenterLocation','AbsCenterLocation','PerpendicularEdgeType']);
 const primary=guide.primary.map(id=>fields.find(p=>p.id===id)).filter(Boolean),ids=new Set(primary.map(p=>p.id));
 const linked=fields.filter(p=>!ids.has(p.id)&&p.readOnly),rest=fields.filter(p=>!ids.has(p.id)&&!p.readOnly);
 return `${primary.length?`<section><h4>Placement and shape</h4>${paramDetails(primary,primary.map(p=>p.name))}<p class="native-tip">${E(guide.note)}</p></section>`:''}${linked.length?`<details><summary>Native linked values</summary>${linked.map(p=>`${paramDetails([p],[p.name])}<p class="native-tip">${E(p.readOnlyReason||'Calculated by OpenVSP.')}</p>`).join('')}</details>`:''}${rest.length?`<details><summary>Other part settings (${rest.length})</summary>${paramDetails(rest,rest.map(p=>p.name))}</details>`:''}`;
}
