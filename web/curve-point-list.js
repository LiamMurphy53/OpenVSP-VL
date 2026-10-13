export function curvePointListMarkup(section,E,suffix=''){
 const rows=section.controlPoints.map((p,i)=>[section.curveU[i],...p,section.rounding?.[i]||0].join(' ')).join('\n');
 return `<details><summary>Replace control-point list</summary><label class="tool-field">Interpolation<select id="curve-list-type${E(suffix)}" data-curve-list-type aria-label="Control-point list interpolation">${[['LINEAR','Linear'],['PCHIP','PCHIP'],['CEDIT','Cubic Bezier']].map(([value,label],i)=>`<option value="${value}" ${section.curveType===i?'selected':''}>${label}</option>`).join('')}</select></label><label class="tool-field">U X Y Z rounding<textarea id="curve-point-list${E(suffix)}" data-curve-point-list aria-label="Control-point list" rows="8">${E(rows)}</textarea></label><p>One point per row. U must increase from 0 to 1. XYZ coordinates are normalized to the profile dimensions. Cubic Bezier lists include handles and need 3n+1 rows. OpenVSP clears rounding for PCHIP interpolation.</p><p>Replaces all points and resets their fixed-position and smooth-tangent flags. Native symmetry and closure still apply. Undo restores the previous profile.</p><button id="apply-curve-point-list${E(suffix)}" data-curve-list-apply>Replace control-point list</button></details>`;
}
export function bindCurvePointList(host,request,mutate,toast){
 const button=host.querySelector('[data-curve-list-apply]');if(!button)return;
 button.onclick=()=>{
  const lines=host.querySelector('[data-curve-point-list]').value.trim().split(/\n/),rows=lines.map(line=>line.trim().split(/[\s,]+/).map(Number));
  if(rows.some(row=>row.length!==5||row.some(value=>!Number.isFinite(value)))){toast('Use five finite values per row: U X Y Z rounding.');return;}
  return mutate({...request,operation:request.operation||'curve-replace-points',type:host.querySelector('[data-curve-list-type]').value,rows});
 };
}
