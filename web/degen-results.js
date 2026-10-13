// Format native degenerate records without computing geometry or properties.
export function degenerateResults(results,esc,plotSVG,metadata){
 const mesh=results.find(r=>r.name==='DegenGeomMesh');
 if(mesh){const id=mesh.entries.find(e=>e.name==='Mesh_GeomID')?.values[0];return `<section class="guided-result" data-guided-result="DegenGeomMesh"><h3>Native degenerate geometry mesh</h3><p>Created native geometry: <strong>${esc(metadata?.nativeGeomType||'See saved native result')}</strong> · ${esc(id||'')}</p><p class="native-tip">The viewer uses the native Gmsh export. Its triangles preserve exported coordinates and connectivity. Download ${esc(metadata?.modelFile||'the generated native aircraft')} to retain the engine’s original MeshGeom or NGonMeshGeom. The quadrilateral setting in this OpenVSP release still creates a triangular MeshGeom.</p></section>`;}
 if(!results.some(r=>r.name==='DegenGeom'))return '';
 const byID=new Map(results.map(r=>[r.id,r]));
 const values=(r,key)=>r?.entries.find(e=>e.name===key)?.values||[],one=(r,key)=>values(r,key)[0];
 const display=x=>Array.isArray(x)?x.map(display).join(', '):x===null?'undefined':typeof x==='number'&&Number.isFinite(x)?String(Number(x.toPrecision(9))):String(x??'—');
 const table=(title,r,columns,count)=>`<section class="guide-result-table"><h4>${esc(title)}</h4><div class="guide-table-scroll"><table><thead><tr>${columns.map(([key,label])=>`<th>${esc(label)}</th>`).join('')}</tr></thead><tbody>${Array.from({length:count},(_,i)=>`<tr>${columns.map(([key])=>`<td>${esc(display(values(r,key)[i]))}</td>`).join('')}</tr>`).join('')}</tbody></table></div></section>`;
 const parents=results.filter(r=>r.name==='Degen_DegenGeom'),blanks=results.filter(r=>r.name==='Degen_BlankGeom');
 let html=`<section class="guided-result" data-guided-result="DegenGeom"><h3>Native degenerate geometry records</h3><p>${parents.length} native surface records · ${blanks.length} native blank-point records. Surface, main-surface and symmetry indices below are the engine’s own identifiers.</p><p class="native-tip">The viewer starts with native camber grids for lifting surfaces and plate grids for bodies. Enable full surfaces or other representations by name. Displayed values are rounded; all native arrays remain in JSON, CSV and the saved native files. Point properties remain per record: native zero-valued symmetry copies are preserved and are not combined into totals.</p>`;
 for(const parent of parents){
  const surf=byID.get(one(parent,'surf')),point=byID.get(one(parent,'point')),disk=byID.get(one(parent,'disk')),plates=values(parent,'plates'),sticks=values(parent,'sticks');
  html+=`<details class="degen-record"><summary>${esc(one(parent,'name'))} · ${esc(one(parent,'type'))} · surface ${esc(one(parent,'surf_index'))} · symmetry ${esc(one(parent,'sym_copy_index'))}</summary><p>Main surface ${esc(one(parent,'main_surf_index'))} · native flipped-normal flag ${esc(one(parent,'flip_normal'))} · geometry ${esc(one(parent,'geom_id'))} · native record ${esc(parent.id)}</p><p>Full native surface grid: ${esc(display(one(surf,'nxsecs')))} sections × ${esc(display(one(surf,'num_pnts')))} profile points · ${plates.length} plates · ${sticks.length} sticks.</p>`;
  if(disk)html+=table('Native disk geometry',disk,[['diameter','Diameter'],['pos','Center (X, Y, Z)'],['n','Normal (X, Y, Z)']],1);
  if(point)html+=table('Native point properties',point,[['area','Area'],['areaWet','Wetted area'],['vol','Volume'],['volWet','Wetted volume'],['cgShell','Shell centroid (X, Y, Z)'],['cgSolid','Solid centroid (X, Y, Z)']],1)+table('Native inertia samples',point,[['Ishell','Shell inertia samples'],['Isolid','Solid inertia samples']],Math.max(values(point,'Ishell').length,values(point,'Isolid').length))+'<p class="native-tip">Inertia samples retain their native order; full result fields document the engine’s conventions.</p>';
  for(const [index,rid] of sticks.entries()){
   const stick=byID.get(rid);if(!stick){html+='<p>Native stick record unavailable; inspect saved references.</p>';continue;}
   const u=values(stick,'u');html+=table('Native section stick '+index,stick,[['u','Native U'],['chord','Chord'],['toc','Thickness / chord'],['toc2','Second thickness / chord'],['sectArea','Section area'],['le','Leading edge (X, Y, Z)'],['te','Trailing edge (X, Y, Z)'],['sectNormal','Section normal (X, Y, Z)']],u.length);
   for(const [key,label] of [['chord','Chord'],['toc','Thickness / chord'],['sectArea','Section area']]){const samples=values(stick,key);if(u.length&&u.length===samples.length)html+=`<h4>Stick ${index} · ${esc(label)}</h4>${plotSVG(u,samples,'Native section U',label)}`;}
  }
  html+='</details>';
 }
 for(const blank of blanks)html+=`<details><summary>${esc(one(blank,'name'))} · native blank point</summary>${table('Native blank-point properties',blank,[['geom_id','Native geometry ID'],['X','Coordinate (X, Y, Z)'],['mass','Mass']],1)}</details>`;
 return html+'</section>';
}
