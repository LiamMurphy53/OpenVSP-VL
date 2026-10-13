export function bindMeasurementCreation(){
 const kind=document.getElementById('measurement-kind');
 const update=()=>{for(const [ids,visible] of [[['measurement-u','measurement-w'],kind.value!=='rst-probe'],[['measurement-r','measurement-s','measurement-t'],kind.value==='rst-probe'],[['measurement-mid','measurement-mid-u','measurement-mid-w'],kind.value==='protractor'],[['measurement-end','measurement-end-u','measurement-end-w'],['ruler','protractor'].includes(kind.value)]])for(const id of ids){const label=document.getElementById(id).closest('label');label.classList.add('measurement-conditional');label.hidden=!visible;}};kind.onchange=update;update();
}
export function measurementCreationValues(kind,surface,num){
 if(kind==='rst-probe')return Object.fromEntries(['r','s','t'].map(k=>[k,num('measurement-'+k)]));
 const result={u:num('measurement-u'),w:num('measurement-w')};
 if(['ruler','protractor'].includes(kind)){const end=surface('measurement-end');Object.assign(result,{endgeom:end.geom,endsurface:end.surface,endu:num('measurement-end-u'),endw:num('measurement-end-w')});}
 if(kind==='protractor'){const mid=surface('measurement-mid');Object.assign(result,{midgeom:mid.geom,midsurface:mid.surface,midu:num('measurement-mid-u'),midw:num('measurement-mid-w')});}
 return result;
}
