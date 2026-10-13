export const needsSavedSolution=name=>['CpSlicer','VSPAEROReadPreviousAnalysis','FlowPlaneSlicer'].includes(name);

export function savedSolutionMarkup(spec,esc,label){
 if(!needsSavedSolution(spec.name))return'';
 const solutions=spec.savedSolutions||[];
 return `<fieldset class="guide-fields"><legend>Saved aerodynamic solution</legend><label for="analysis-source-run">Source solution</label><select id="analysis-source-run"><option value="">Choose a completed solution…</option>${solutions.map(j=>`<option value="${esc(j.id)}">${esc(label(j.name))} · ${esc(new Date(j.started*1000).toLocaleString())} · ${esc(j.id.slice(0,8))} · model ${esc(j.revision?.slice(0,8))}</option>`).join('')}</select><p class="native-tip">${solutions.length?'Uses the selected solution’s saved aircraft and native pressure database. Later aircraft edits do not affect this operation.':'No completed pressure database is available. Run a VSPAERO flight analysis first, then reload these settings.'}</p></fieldset>`;
}

export function savedSolutionSource(name){
 if(!needsSavedSolution(name))return undefined;
 const value=document.getElementById('analysis-source-run')?.value;
 if(!value||document.getElementById('analysis-source-run').selectedOptions[0]?.disabled)throw Error('Choose an available completed saved aerodynamic solution.');
 return value;
}

export function restoreSavedSolution(id){
 const select=document.getElementById('analysis-source-run');if(!select)return false;
 if(![...select.options].some(o=>o.value===id)){
  const option=document.createElement('option');option.value=id;option.textContent='Unavailable saved solution · '+id;option.disabled=true;select.append(option);select.value=id;return false;
 }
 select.value=id;return true;
}

export function pressureSliceResults(results,esc,plotSVG){
 const slices=results.filter(r=>r.name==='CpSlicer_Case');if(!slices.length)return'';
 const values=(r,name,index=0)=>r.entries.find(e=>e.name===name&&e.index===index)?.values||[];
 const panels=slices.flatMap(r=>{
  const blocks=r.entries.filter(e=>e.name==='Cp');return (blocks.length?blocks:[{index:0,values:[]}]).map(block=>{
  const cp=block.values,x=values(r,'X_Loc',block.index),y=values(r,'Y_Loc',block.index),z=values(r,'Z_Loc',block.index),cut=values(r,'Cut_Type')[0];
  const coordinate=cut===0?y:x,axis=cut===0?'Y':'X';
  const plot=cp.length&&coordinate.length===cp.length?plotSVG(coordinate,cp,'Native '+axis+' coordinate','Native Cp / delta Cp',false,null,true):'<p>This slice has no paired native pressure samples. Review plane positions and the saved solution.</p>';
  const shown=n=>Number.isFinite(n)?String(Number(n.toPrecision(9))):'undefined';
  const metadata=['Case','Mach','Alpha','Beta'].filter(k=>values(r,k,block.index).length).map(k=>`${k}: ${shown(values(r,k,block.index)[0])}`).join(' · ');
  return `<details class="guide-slice-plots" data-native-pressure-record="${esc(r.id)}" data-native-pressure-block="${block.index}" ${r.index===0&&block.index===0?'open':''}><summary>Native pressure slice ${r.index+1} · ${esc(['X','Y','Z'][cut]||'native axis')} = ${esc(shown(values(r,'Cut_Loc')[0]))} · sample block ${block.index} · ${cp.length} samples</summary><p>${esc(metadata)}</p>${plot}<details><summary>Sample locations and pressure</summary><div class="guide-table-scroll"><table><thead><tr><th>Sample</th><th>X</th><th>Y</th><th>Z</th><th>Cp / delta Cp</th></tr></thead><tbody>${cp.map((p,i)=>`<tr><td>${i+1}</td><td>${esc(shown(x[i]))}</td><td>${esc(shown(y[i]))}</td><td>${esc(shown(z[i]))}</td><td>${esc(shown(p))}</td></tr>`).join('')}</tbody></table></div></details></details>`;
 });}).join('');
 return `<section class="guided-result" data-guided-result="CpSlicer"><h3>Native pressure slice samples</h3><p>Samples stay in native order. Thick surfaces report Cp; thin surfaces report delta Cp. Points are plotted without connecting or interpolating separate surface intersections. Full-precision coordinates, case metadata and pressure values remain in JSON and CSV.</p>${panels}</section>`;
}
