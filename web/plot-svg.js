const E=value=>String(value).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
// These plots display returned samples; they do not implement a solver.
function tickLabels(values,minimum){for(let precision=minimum;precision<=15;precision++){const labels=values.map(x=>String(Number(x.toPrecision(precision))));if(new Set(labels).size===values.length||precision===15)return labels;}}
export function wrapPlotLabel(value,limit=48){
 const lines=[];let line='';
 for(const word of String(value).split(/\s+/).filter(Boolean)){
  const chars=Array.from(word);
  if(line&&Array.from(line).length+1+chars.length>limit){lines.push(line);line='';}
  while(chars.length>limit){if(line){lines.push(line);line='';}lines.push(chars.splice(0,limit).join(''));}
  if(chars.length)line+=(line?' ':'')+chars.join('');
 }
 if(line||!lines.length)lines.push(line);
 return lines;
}
function axisText(lines,x,y,anchor,label){return `<text class="plot-axis-label" x="${x}" y="${y}" text-anchor="${anchor}"><title>${E(label)}</title>${lines.map((line,i)=>`<tspan x="${x}" dy="${i?14:0}">${E(line)}</tspan>`).join('')}</text>`;}
export function plotSVG(xs,ys,xlabel,ylabel,equal=false,reference=null,scatter=false){
 const pts=xs.map((x,i)=>[x,ys[i]]).filter(p=>p.every(Number.isFinite));
 if(!pts.length)return '<p>No numeric samples.</p>';
 const domain=[...pts,...(reference||[])];let xmin=Infinity,xmax=-Infinity,ymin=Infinity,ymax=-Infinity;
 for(const [x,y] of domain){xmin=Math.min(xmin,x);xmax=Math.max(xmax,x);ymin=Math.min(ymin,y);ymax=Math.max(ymax,y);}
 let dx=xmax-xmin||1,dy=ymax-ymin||1;const xc=(xmin+xmax)/2,yc=(ymin+ymax)/2;
 if(equal){dy=Math.max(dy,dx*220/530);dx=Math.max(dx,dy*530/220);}
 dx*=1.1;dy*=1.15;xmin=xc-dx/2;ymin=yc-dy/2;
 const xticks=tickLabels([0,1,2,3,4].map(i=>xmin+dx*i/4),4),yticks=tickLabels([0,1,2,3,4].map(i=>ymin+dy*i/4),3);
 // Reserve space for scientific tick strings and full, wrapped engineering labels.
 const left=Math.max(55,...yticks.map(t=>Array.from(t).length*7+12),Array.from(xticks[0]).length*3.5+4);
 const right=Math.max(35,Array.from(xticks.at(-1)).length*3.5+4),width=left+530+right;
 const xlines=wrapPlotLabel(xlabel),ylines=wrapPlotLabel(ylabel,Math.floor((width-24)/11));
 const top=35+(ylines.length-1)*14,bottom=top+220,height=bottom+55+(xlines.length-1)*14;
 const X=x=>left+(x-xmin)/dx*530,Y=y=>bottom-(y-ymin)/dy*220;
 return `<svg xmlns="http://www.w3.org/2000/svg" class="native-plot" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" style="font:11px system-ui,sans-serif;fill:#53614e;height:auto" role="img" aria-label="${E(ylabel)} versus ${E(xlabel)}"><title>${E(ylabel)} versus ${E(xlabel)}</title><rect x="${left}" y="${top}" width="530" height="220" fill="#f5f7f1"/>${[0,1,2,3,4].map(i=>{const x=xmin+dx*i/4,y=ymin+dy*i/4;return `<path d="M ${X(x)} ${top} V${bottom} M${left} ${Y(y)} H${left+530}" stroke="#dce3d7"/><text x="${X(x)}" y="${bottom+20}" text-anchor="middle">${xticks[i]}</text><text x="${left-7}" y="${Y(y)+4}" text-anchor="end">${yticks[i]}</text>`;}).join('')}${reference?`<polyline points="${reference.map(p=>`${X(p[0])},${Y(p[1])}`).join(' ')}" fill="none" stroke="#c08935" stroke-width="2" stroke-dasharray="6 4"/>`:''}${scatter?'':`<path d="${(()=>{let connected=false;return xs.map((x,i)=>{const y=ys[i];if(!Number.isFinite(x)||!Number.isFinite(y)){connected=false;return '';}const command=connected?'L':'M';connected=true;return `${command} ${X(x)} ${Y(y)}`;}).join(' ');})()}" fill="none" stroke="#387553" stroke-width="2"/>`}${pts.length<80||scatter?pts.map(p=>`<circle cx="${X(p[0])}" cy="${Y(p[1])}" r="${scatter?2:3}" fill="#387553"><title>${E(xlabel)} ${p[0]}, ${E(ylabel)} ${p[1]}</title></circle>`).join(''):''}${axisText(xlines,left+265,bottom+47,'middle',xlabel)}${axisText(ylines,12,18,'start',ylabel)}</svg>`;
}
