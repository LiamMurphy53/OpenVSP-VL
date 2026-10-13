export const sourceTypeLabels={POINT_SOURCE:'Point',LINE_SOURCE:'Line',BOX_SOURCE:'Box',ULINE_SOURCE:'Constant U line',WLINE_SOURCE:'Constant W line'};
const fields={POINT_SOURCE:['length','radius','u','w'],LINE_SOURCE:['length','radius','u','w','length2','radius2','u2','w2'],BOX_SOURCE:['length','radius','u','w','u2','w2'],ULINE_SOURCE:['length','radius','u'],WLINE_SOURCE:['length','radius','w']};
const notes={POINT_SOURCE:'Refinement around one native surface location.',LINE_SOURCE:'Refinement along two native surface locations, with separate endpoint lengths and radii.',BOX_SOURCE:'The original engine forms a spatial refinement box from two native surface locations; one length and radius apply.',ULINE_SOURCE:'Refinement along the native constant-U curve. W and second-point fields are unused.',WLINE_SOURCE:'Refinement along the native constant-W curve. U and second-point fields are unused.'};
export function bindSourceCreation(){
 const select=document.getElementById('source-type');if(!select)return;
 const update=()=>{const active=fields[select.value];for(const key of fields.LINE_SOURCE){const el=document.getElementById('source-'+key);el.closest('label').hidden=!active.includes(key);}document.getElementById('source-creation-note').textContent=notes[select.value];};select.onchange=update;update();
}
export function sourceCreationValues(type,num){return Object.fromEntries(fields[type].map(key=>[key,num('source-'+key)]));}
