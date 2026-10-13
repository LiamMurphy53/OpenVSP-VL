// Display saved native properties and labels; no atmosphere recalculation.
export function parasiteFlightResults(result,esc){
 const entry=name=>result.entries.find(e=>e.name===name&&e.index===0),value=name=>entry(name)?.values?.[0];
 const fields=[['FC_Alt','Altitude','Alt_Label'],['FC_Vinf','Airspeed','Vinf_Label'],['FC_Mach','Mach',null],['FC_Temp','Temperature','Temp_Label'],['FC_dTemp','Temperature offset','Temp_Label'],['FC_Pres','Pressure','Pres_Label'],['FC_Rho','Density','Rho_Label'],['FC_Sref','Reference area','Sref_Label']];
 const show=x=>x===null||typeof x==='number'&&!Number.isFinite(x)?'Undefined':String(x);
 const available=fields.filter(([key])=>entry(key)?.values?.length);if(!available.length)return '';
 return `<section class="guide-result-table" data-parasite-flight-conditions><h3>Flight conditions used by OpenVSP</h3><p>These are the native properties used for this saved drag calculation. Unit labels come from the result; changing workspace display units does not recalculate this run.</p><div class="guide-table-scroll"><table><thead><tr><th>Property</th><th>Native value</th><th>Native unit label</th></tr></thead><tbody>${available.map(([key,label,units])=>`<tr><th>${esc(label)}</th><td>${esc(show(value(key)))}</td><td>${esc(units?value(units)??'Not supplied':'Dimensionless')}</td></tr>`).join('')}</tbody></table></div><p class="native-tip">Friction methods: ${esc(value('LamCfEqnName')??'Not supplied')} · ${esc(value('TurbCfEqnName')??'Not supplied')}. Values retain the precision saved by the engine.</p></section>`;
}
