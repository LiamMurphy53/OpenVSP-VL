// Display the native hierarchy without joining patches or altering normals.
export function surfacePatchResults(results,esc){
 if(!results.some(r=>r.name==='VehicleSurfaces'))return '';
 const refs=new Map(results.map(r=>[r.id,r])),values=(r,k)=>r?.entries.find(e=>e.name===k)?.values||[],one=(r,k)=>values(r,k)[0];
 let html='<section class="guided-result" data-guided-result="SurfacePatches"><h3>Native surface patches</h3><p>Inspect each named patch in the viewer. Coordinates and normals remain at their original native grid points, including collapsed caps and boundaries. Full grids are available in result JSON, sample CSV and the downloadable surface-patches.json file.</p>';
 for(const component of results.filter(r=>r.name==='ComponentSurfaces')){
  html+=`<details><summary>${esc(one(component,'name'))} · ${values(component,'surfaces').length} native surfaces</summary><p>Native component ${esc(one(component,'id'))}</p><div class="guide-table-scroll"><table><thead><tr><th>Surface index</th><th>Patch index</th><th>Grid rows</th><th>Grid columns</th><th>Native record</th></tr></thead><tbody>`;
  for(const sid of values(component,'surfaces')){const surface=refs.get(sid);for(const pid of values(surface,'patches')){const patch=refs.get(pid),x=values(patch,'x');html+=`<tr><td>${esc(one(patch,'surf_index'))}</td><td>${esc(one(patch,'patch_index'))}</td><td>${x.length}</td><td>${x[0]?.length||0}</td><td>${esc(pid)}</td></tr>`;}}
  html+='</tbody></table></div></details>';
 }
 return html+'</section>';
}
