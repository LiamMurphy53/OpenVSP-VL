// Present original reference samples and fixed conditions without new calculations.
export function referenceResults(data,esc,plotSVG){
 if(!['AtmosphereReference','DragEquationReference'].includes(data.analysis))return '';
 const numeric=x=>typeof x==='string'?x:Number.isFinite(x)?String(x):'Undefined native value';
 const readable={Altitude_m:'Altitude (m)',Temperature_K:'Temperature (K)',Pressure_kPa:'Pressure (kPa)',PressureRatio:'Pressure ratio',DensityRatio:'Density ratio',Pres:'Pressure',Pres_Ratio:'Pressure ratio',Rho_Ratio:'Density ratio',Temp:'Temperature'};
 const columnTitle=e=>readable[e.name]||e.name;
 const entries=r=>Object.fromEntries(r.entries.map(e=>[e.name,e]));
 const point=data.results.find(r=>r.name==='AtmosphereAtAltitude');
 let html=point?`<section class="guided-result"><h3>Atmosphere at requested altitude</h3><dl>${point.entries.map(e=>`<div><dt>${esc(columnTitle(e))}</dt><dd>${esc(numeric(e.values[0]))}</dd></div>`).join('')}</dl><p class="native-tip">The requested temperature deviation applies here. The native standard-day table below uses zero deviation.</p></section>`:'';
 const labels={Alt:'Altitude · native table values',D_L:'D/L',T_C:'Thickness / chord',ReyIn:'Reynolds number',LamPerc:'Laminar flow (%)'};
 for(const r of data.results.filter(r=>r!==point)){
  const fields=entries(r),axis=['Alt','D_L','T_C','LamPerc','ReyIn'].find(n=>fields[n]?.values.length>1);
  if(!axis)continue;
  const x=fields[axis],series=r.entries.filter(e=>e.name!==axis&&e.values.length>1),conditions=r.entries.filter(e=>e.values.length===1),columns=[x,...series],count=Math.max(...columns.map(e=>e.values.length));
  const title={Atmosphere:'Native standard-day atmosphere',Body_Form_Factor:'Body form-factor equations',Wing_Form_Factor:'Wing form-factor equations',Friction_Coefficient:axis==='LamPerc'?'Partial-turbulence reference':'Skin-friction equations'}[r.name]||r.name;
  html+=`<section class="guided-result"><h3>${esc(title)}</h3><p>${count} original sample rows. Values use the native reference writer’s grid and conventions.</p>${conditions.length?`<details open><summary>Native fixed reference conditions</summary><dl>${conditions.map(e=>`<div><dt title="${esc(e.description||'')}">${esc(e.name)}</dt><dd>${esc(numeric(e.values[0]))}</dd></div>`).join('')}</dl></details>`:''}<p class="native-tip">These are engineering references. Aircraft geometry is not evaluated here. Undefined native samples remain undefined; plots leave gaps.</p>${series.map(e=>`<details><summary>${esc(columnTitle(e))}</summary>${plotSVG(x.values,e.values,labels[axis],columnTitle(e))}</details>`).join('')}<details><summary>All ${count} native sample rows</summary><div class="guide-table-scroll"><table class="result-table"><thead><tr>${columns.map(e=>`<th title="${esc(e.description||'')}">${esc(e.name===axis?labels[axis]:columnTitle(e))}</th>`).join('')}</tr></thead><tbody>${Array.from({length:count},(_,i)=>`<tr>${columns.map(e=>`<td>${esc(numeric(e.values[i]))}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details><p class="native-tip">Original CSV and full result JSON remain available in this saved run.</p></section>`;
 }
 return html;
}
