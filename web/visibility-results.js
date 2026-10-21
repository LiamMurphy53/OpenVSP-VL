// Present original per-observer arrays without inferring visibility from signed
// distances, converting coordinates, or filling missing native samples.
export function visibilityResults(records,esc,format){
 const value=x=>x===null||x===undefined?'undefined':format(x);
 return records.filter(r=>r.name==='Point_Visibility').map(r=>{
  const indices=[...new Set(r.entries.filter(e=>e.name==='Center').map(e=>e.index))];
  return indices.map(index=>{
   const get=name=>r.entries.find(e=>e.name===name&&e.index===index)?.values;
   const center=get('Center'),dirs=get('Dirs');
   const heading=`<h4>Observation point ${index+1}</h4><p>Center (model length units): ${esc(value(center))}</p>`;
   if(dirs){
    const columns=[['Visible','Line of sight'],['DistVisible','Visibility distance'],['DistMiss','Miss distance'],['DistFOVVisible','FOV visibility distance'],['DistFOVMiss','FOV miss distance'],['BadSum','Native badness']].filter(([key])=>get(key));
    if(!columns.some(([key])=>key==='Visible')||columns.some(([key])=>get(key).length!==dirs.length))return `<section class="guide-result-table">${heading}<p class="status-error">Native visibility arrays have different lengths or lack visibility flags. Inspect the raw result arrays below.</p></section>`;
    return `<section class="guide-result-table">${heading}<p>Distances use model length units and retain their native signs. Visibility comes from the native flag, not the sign of a distance. FOV means field of view.</p><div class="guide-table-scroll" role="region" aria-label="Visibility directions and distances" tabindex="0"><table><thead><tr><th>Direction</th><th>Native direction vector</th>${columns.map(([,label])=>`<th>${esc(label)}</th>`).join('')}</tr></thead><tbody>${dirs.map((direction,i)=>`<tr><td>${i+1}</td><td>${esc(value(direction))}</td>${columns.map(([key])=>{const x=get(key)[i];return `<td>${esc(key==='Visible'?(x===1?'Clear line of sight (1)':x===0?'Occluded (0)':'Native flag '+value(x)):value(x))}</td>`;}).join('')}</tr>`).join('')}</tbody></table></div></section>`;
   }
   const labels=get('Octant_Labels'),fractions=get('Octant_Area_Frac'),poly=get('Poly_Visible')?.[0];
   const domain=poly===1?'visible region':poly===0?'occluded region':'native domain';
   return `<section class="guide-result-table">${heading}<p>Boundary encloses the ${esc(domain)}. Octant fractions describe that domain.</p><p>Over-nose elevation (degrees): ${esc(value(get('Over_Nose')))}. Forward elevation bounds (degrees): ${esc(value(get('Fwd_Bounds')))}.</p>${labels&&fractions&&labels.length===fractions.length?`<div class="guide-table-scroll"><table><thead><tr><th>Native octant</th><th>Solid-angle fraction</th></tr></thead><tbody>${labels.map((label,i)=>`<tr><td>${esc(label)}</td><td>${esc(value(fractions[i]))}</td></tr>`).join('')}</tbody></table></div>`:''}<p class="native-tip">Octant labels follow OpenVSP’s up/down, fore/aft and left/right convention. Boundary coordinates remain in the raw native results.</p></section>`;
  }).join('');
 }).join('');
}
