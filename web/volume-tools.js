// Render original native volume query inputs; no inverse/conversion math.
let draft={basis:'RST',coordinates:[.5,.5,.5],point:[0,0,0],guess:[.5,.5,.5],useGuess:false,surface:null};
export function volumeQueryMarkup(h,surfaces,selected){
 const {field,select,button}=h;
 const chosen=surfaces.some(([id])=>id===draft.surface)?draft.surface:selected;
 return `<h3>Convert volume coordinates</h3><p>R/S/T uses section volume coordinates; L/M/N uses uniform volume coordinates. Values range from 0 to 1.</p>${select('Volume surface','volume-surface',surfaces,chosen)}${select('Input coordinate system','volume-basis',[['RST','Section volume · R / S / T'],['LMN','Uniform volume · L / M / N']],draft.basis)}<div class="tool-fields">${[...draft.basis].map((label,i)=>field(label,'volume-coordinate-'+i,draft.coordinates[i],{min:0,max:1})).join('')}</div>${button('volume-convert','Convert native volume coordinates')}<h3>Find volume coordinates from a model point</h3><p>Find the nearest volume point, its distance and R/S/T coordinates. Supply a starting guess if needed.</p><div class="tool-fields">${['X','Y','Z'].map((label,i)=>field(label,'volume-point-'+label.toLowerCase(),draft.point[i])).join('')}</div><label class="membership-row"><input id="volume-use-guess" type="checkbox" ${draft.useGuess?'checked':''}>Supply an R/S/T starting guess</label><div id="volume-guess-fields" class="tool-fields" ${draft.useGuess?'':'hidden'}>${['R','S','T'].map((label,i)=>field('Starting '+label,'volume-guess-'+i,draft.guess[i],{min:0,max:1})).join('')}</div>${button('volume-project','Find nearest native volume point')}<p class="native-tip">Model X/Y/Z and distances use native model length units. At singular tips, some native conversions may be undefined; those values stay undefined in the result.</p>`;
}
export function bindVolumeQueries(h,query){
 const {bind,val,num}=h;
 const remember=()=>{draft={surface:val('volume-surface'),basis:val('volume-basis'),coordinates:[0,1,2].map(i=>val('volume-coordinate-'+i)),point:['x','y','z'].map(k=>val('volume-point-'+k)),guess:[0,1,2].map(i=>val('volume-guess-'+i)),useGuess:document.getElementById('volume-use-guess').checked};};
 for(const field of document.querySelectorAll('[id^="volume-"]'))if(field.matches('input,select')){field.addEventListener('input',remember);field.addEventListener('change',remember);}
 const surface=()=>{const [geom,s]=val('volume-surface').split(':');return {geom,surface:Number(s)};};
 const guess=document.getElementById('volume-use-guess');guess.onchange=()=>{document.getElementById('volume-guess-fields').hidden=!guess.checked;};
 document.getElementById('volume-basis').onchange=e=>{[...e.target.value].forEach((label,i)=>{const field=document.querySelector(`label:has(#volume-coordinate-${i})`);field.firstChild.textContent=label;field.querySelector('input[type="number"]').setAttribute('aria-label',label);field.querySelector('input[type="range"]').setAttribute('aria-label',label+' slider');});};
 bind('volume-convert',()=>{remember();return query({operation:'volume-convert',...surface(),basis:val('volume-basis'),coordinates:[0,1,2].map(i=>num('volume-coordinate-'+i))});});
 bind('volume-project',()=>{remember();return query({operation:'volume-project',...surface(),point:['x','y','z'].map(k=>num('volume-point-'+k)),...guess.checked?{guess:[0,1,2].map(i=>num('volume-guess-'+i))}:{}});});
}

export function downloadQueryResult(result){
 const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));
 const link=document.createElement('a');link.href=url;link.download='native-'+result.operation+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
