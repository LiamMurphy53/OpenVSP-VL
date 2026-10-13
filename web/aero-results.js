// Present exact native solver samples. No convergence threshold or solver math.
const entry=(r,name)=>r.entries.find(e=>e.name===name&&e.index===0);
const values=(r,name)=>entry(r,name)?.values||[];
const shown=x=>x==null?'undefined':typeof x==='number'&&Number.isFinite(x)?String(Number(x.toPrecision(9))):String(x);
const histories=[['CLtot','Total lift coefficient'],['CDtot','Total drag coefficient'],['CMytot','Pitching moment coefficient'],['log10( L2Residual )','Native log10 L2 residual'],['log10( MaxResidual )','Native log10 maximum residual']];
const rotors=[['Thrust','Thrust'],['Power','Power'],['RPM','RPM'],['CT','Thrust coefficient'],['CP','Power coefficient']];

export function aeroSeries(result){
 const rotor=result.name==='VSPAERO_Rotor';
 const axis=entry(result,rotor?'Time':entry(result,'Time')?'Time':'WakeIter');
 return (rotor?rotors:histories).filter(([name])=>entry(result,name)).map(([name,label])=>({name,label,axisName:axis?.name,axisLabel:axis?.name==='Time'?(rotor?'Native Time field':'Native simulation time'):'Native wake iteration',x:axis?.values||[],y:values(result,name)}));
}

export function aeroResults(results,esc,plotSVG){
 const selected=results.filter(r=>['VSPAERO_History','VSPAERO_Rotor'].includes(r.name));
 if(!selected.length)return '';
 const table=(r,series)=>{
  const columns=[...new Set(series.flatMap(s=>[s.axisName,s.name]).filter(Boolean))];
  const count=Math.max(0,...columns.map(n=>values(r,n).length));
  return `<details><summary>Native samples (${count} rows)</summary><div class="guide-result-table guide-table-scroll"><table><thead><tr><th>Sample</th>${columns.map(n=>`<th>${esc(n)}</th>`).join('')}</tr></thead><tbody>${Array.from({length:count},(_,i)=>`<tr><td>${i+1}</td>${columns.map(n=>`<td>${esc(shown(values(r,n)[i]))}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`;
 };
 const panels=selected.map((r,i)=>{
  const rotor=r.name==='VSPAERO_Rotor',series=aeroSeries(r);
  const title=rotor?`Rotor ${shown(values(r,'Rotor_Num')[0]??r.index+1)} · ${values(r,'Group_Name')[0]||'native rotor'}`:`Solver history ${r.index+1}`;
  const condition=rotor?'Samples from this native rotor group.':[['FC_AoA_','Alpha'],['FC_Beta_','Beta'],['FC_Mach_','Mach']].filter(([n])=>values(r,n).length).map(([n,label])=>`${label} ${shown(values(r,n)[0])}`).join(' · ');
  const plots=series.map(s=>`<section data-native-aero-series="${esc(s.name)}"><h4>${esc(s.label)}</h4>${s.x.length&&s.x.length===s.y.length?plotSVG(s.x,s.y,s.axisLabel,s.label):'<p>Native coordinate and result arrays have different lengths or no coordinate array. Review the exact samples below.</p>'}</section>`).join('');
  return `<details class="aero-history" data-native-aero-result="${esc(r.name)}" data-native-aero-index="${r.index}" ${i===0?'open':''}><summary>${esc(title)}</summary><p>${esc(condition)}</p><div class="aero-history-plots">${plots}</div>${table(r,series)}</details>`;
 }).join('');
 return `<section class="guided-result" data-guided-result="VSPAERO"><h3>Solver histories and rotor performance</h3><p>Inspect the native residual and force histories. Compare wake resolution and longer runs before relying on the solution. A completed run does not establish convergence.</p><p class="native-tip">Residual values are already log10 values reported by OpenVSP. Time histories retain repeated times and undefined samples; gaps are not interpolated. Rotor force and power use the native model’s units.</p>${panels}<p class="native-tip">Displayed values are rounded for reading. Full-precision native arrays remain in the result tables, JSON and CSV.</p></section>`;
}
