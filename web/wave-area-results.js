// Native arrays are plotted unchanged. Coordinate scaling and the inlet/exit
// baseline match the original WaveDragScreen display; no curve fitting here.
const colors=['#285f48','#347ab1','#b06a25','#8a4c9c','#c14f58','#468c8b'];
const ideals=[['none','None'],['searsHaack','Sears–Haack · same volume and length'],['vonKarman','von Kármán · same maximum area'],['lighthill','Lighthill · same maximum area']];
const finite=Number.isFinite;
const text=x=>finite(x)?Number(x.toPrecision(7)):'—';
export function waveSeries(data,index,mode,ideal){
 const c=data.cones[index];if(!c)return [];
 const series=[],add=(label,x,y,color,dashed=false)=>{if(Array.isArray(y)&&y.length===x.length)series.push({label,x,y,color,dashed});};
 if(mode==='total')add('Flow-corrected total',data.xFitNormalized,c.flowFit,colors[0]);
 else{
  const field=mode==='components'?'componentFit':'buildupFit';
  for(const [i,y] of (c[field]||[]).entries())add((mode==='buildup'?'Cumulative · ':'')+(data.components[i]?.name||data.componentIds[i]),data.xFitNormalized,y,colors[(i+1)%colors.length]);
  if(mode==='components')add('Total including inlet/exit baseline',data.xFitNormalized,c.totalFit,colors[0]);
 }
 if(ideal!=='none'&&Array.isArray(c[ideal])){
  const reference=c[ideal].map((y,i)=>{
   if(!finite(y))return null;
   if(mode==='total')return y;
   if(!finite(data.inletArea)||!finite(data.exitArea))return null;
   const x=data.xFitNormalized[i];
   return y+data.inletArea*(1-x)+data.exitArea*x;
  });
  add(ideals.find(x=>x[0]===ideal)?.[1]||ideal,data.xFitNormalized,reference,'#814da4',true);
 }
 return series;
}
export function waveChart(data,index,mode,ideal,points,E){
 const cone=data.cones[index],series=waveSeries(data,index,mode,ideal);if(!cone||!series.length)return '<p>No native area curves are available.</p>';
 const raw=mode==='total'?[cone.flowSlices]:mode==='components'?[...(cone.componentSlices||[]),cone.totalSlices]:(cone.buildupSlices||[]);
 const ys=[0,...series.flatMap(s=>s.y).filter(finite),...(points?raw.flatMap(a=>a||[]).filter(finite):[])],lo=ys.reduce((a,b)=>Math.min(a,b),0),hi=ys.reduce((a,b)=>Math.max(a,b),0),span=hi-lo||1;
 const X=x=>90+x*480,Y=y=>255-(y-lo)/span*215;
 const paths=series.map(s=>{let connected=false;const d=s.x.map((x,i)=>{const y=s.y[i];if(!finite(x)||!finite(y)){connected=false;return '';}const cmd=connected?'L':'M';connected=true;return `${cmd}${X(x)},${Y(y)}`;}).join(' ');return `<path d="${d}" stroke="${s.color}" stroke-width="2" fill="none" ${s.dashed?'stroke-dasharray="7 4"':''}><title>${E(s.label)}</title></path>`;}).join('');
 const samples=points?raw.map((values,j)=>(values||[]).map((y,i)=>finite(y)&&finite(data.xNormalized[i])?`<circle cx="${X(data.xNormalized[i])}" cy="${Y(y)}" r="2.5" fill="${mode==='components'&&j===raw.length-1||mode==='total'?colors[0]:colors[(j+1)%colors.length]}"><title>x/L ${data.xNormalized[i]} · area ${y}</title></circle>`:'').join('')).join(''):'';
 return `<svg data-wave-reference-chart viewBox="0 0 600 315" role="img" aria-label="Native wave area distributions and ideal-body reference" xmlns="http://www.w3.org/2000/svg" style="font:12px sans-serif;background:white;color:#34473e"><path d="M90 30V255H570" stroke="#7b8f80" fill="none"/>${[0,.25,.5,.75,1].map(f=>`<text x="${X(f)}" y="276" text-anchor="middle">${f}</text><text x="82" y="${Y(lo+f*span)+4}" text-anchor="end">${text(lo+f*span)}</text>`).join('')}${paths}${samples}<text x="315" y="305" text-anchor="middle">Normalized axial position (x/L)</text><text x="90" y="20">Area (square model units)</text></svg><ul class="wave-area-legend">${series.map(s=>`<li><span style="display:inline-block;width:1.3rem;border-top:2px ${s.dashed?'dashed':'solid'} ${s.color}"></span> ${E(s.label)}</li>`).join('')}</ul>${cone.referenceWarning?`<p>${E(cone.referenceWarning)}</p>`:''}`;
}
export function waveAreaResults(data,E){
 if(!data?.cones?.length)return '';
 const index=Math.max(0,Math.min(data.cones.length-1,(data.selectedCone||1)-1)),mode=['total','components','buildup'][data.selectedAreaMode]||'total',ideal=ideals[data.selectedIdealBody]?.[0]||'none';
 return `<section class="wave-area-results"><h3>Equivalent-body area distribution</h3><div class="tool-fields"><label for="wave-area-cone">Cone section</label><select id="wave-area-cone" data-wave-area-cone>${data.cones.map((c,i)=>`<option value="${i}" ${i===index?'selected':''}>${c.coneIndex} · θ ${E(text(c.thetaDegrees))}°</option>`).join('')}</select><label for="wave-area-mode">Area display</label><select id="wave-area-mode" data-wave-area-mode>${[['total','Flow-corrected total'],['components','Components'],['buildup','Cumulative buildup']].map(([v,label])=>`<option value="${v}" ${v===mode?'selected':''}>${label}</option>`).join('')}</select><label for="wave-area-ideal">Ideal-body reference</label><select id="wave-area-ideal" data-wave-area-ideal>${ideals.map(([v,label])=>`<option value="${v}" ${v===ideal?'selected':''}>${label}</option>`).join('')}</select><label><input type="checkbox" data-wave-area-points ${data.showPoints?'checked':''}>Show native slice samples</label></div><p class="native-tip">Fits and ideal-body curves come from this run’s OpenVSP engine. Components and buildup include the saved inlet/exit baseline; the total view removes it. Reference curves illustrate area distributions, not a new aircraft geometry or drag calculation.</p><div data-wave-area-chart>${waveChart(data,index,mode,ideal,data.showPoints,E)}</div><p data-wave-area-dimensions></p><div class="tool-actions"><button data-wave-area-svg>Download chart SVG</button><button data-wave-area-csv>Download plotted samples CSV</button><a href="${E(data.downloadURL||'#')}" download="${E(data.file)}">Download full native wave arrays</a></div></section>`;
}
export function waveSliceSeries(data,index,mode){
 const c=data.cones[index];if(!c)return [];
 const fit=waveSeries(data,index,mode,'none');
 const values=mode==='total'?[c.flowSlices]:mode==='components'?[...(c.componentSlices||[]),c.totalSlices]:(c.buildupSlices||[]);
 return values.map((y,i)=>({label:(fit[i]?.label||'Native')+' · native slices',x:data.xNormalized,y})).filter(s=>Array.isArray(s.y)&&s.y.length===s.x.length);
}
export function waveCSV(series){
 const rows=['Series,x/L,Area (square model units)'];
 for(const s of series)for(let i=0;i<s.x.length;i++)rows.push(`"${s.label.replaceAll('"','""')}",${s.x[i]},${s.y[i]===null?'':s.y[i]}`);
 return rows.join('\n')+'\n';
}
export function bindWaveAreaResults(data,E){
 const host=document.querySelector('.wave-area-results');if(!host||!data?.cones?.length)return;
 const cone=host.querySelector('[data-wave-area-cone]'),mode=host.querySelector('[data-wave-area-mode]'),ideal=host.querySelector('[data-wave-area-ideal]'),points=host.querySelector('[data-wave-area-points]');
 const draw=()=>{host.querySelector('[data-wave-area-chart]').innerHTML=waveChart(data,Number(cone.value),mode.value,ideal.value,points.checked,E);const c=data.cones[Number(cone.value)];host.querySelector('[data-wave-area-dimensions]').textContent=`Saved equivalent body: length ${text(c.length)} · volume ${text(c.volume)} · maximum area ${text(c.maxArea)}. Axial range ${text(c.startX)} to ${text(c.endX)} in model units.`;};
 for(const control of [cone,mode,ideal,points])control.onchange=draw;
 const download=(content,type,name)=>{const url=URL.createObjectURL(new Blob([content],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 host.querySelector('[data-wave-area-svg]').onclick=()=>download(host.querySelector('svg')?.outerHTML||'','image/svg+xml','wave-area-distribution.svg');
 host.querySelector('[data-wave-area-csv]').onclick=()=>download(waveCSV([...waveSeries(data,Number(cone.value),mode.value,ideal.value),...(points.checked?waveSliceSeries(data,Number(cone.value),mode.value):[])]),'text/csv','wave-area-distribution.csv');
 draw();
}
