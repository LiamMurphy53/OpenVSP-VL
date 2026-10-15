// Filtering and distance comparisons execute in the official engine.
const drafts=new Map();
const methods=[['KeepPtsInBBox','Keep points inside a box'],['RemovePtsInBBox','Remove points inside a box'],['KeepPtsInRange','Keep points in an axis range'],['RemovePtsInRange','Remove points in an axis range'],['KeepPtsAbove','Keep points above a coordinate'],['KeepPtsBelow','Keep points below a coordinate'],['KeepPtsNearPt','Keep points within a radius'],['RemovePtsNearPt','Remove points within a radius'],['KeepPtsNearGeom','Keep points near a surface'],['RemovePtsNearGeom','Remove points near a surface']];
export function mountCloudFilters(host,cloud,surfaces,h){
 const {field,select,button,num,val,mutate}=h;
 const draft=drafts.get(cloud.id)||{method:'KeepPtsInBBox',axis:0,low:0,high:1,value:0,radius:1,tolerance:.01,minimum:[0,0,0],maximum:[1,1,1],center:[0,0,0],target:surfaces[0]?.[0]||''};drafts.set(cloud.id,draft);
 const coordinates=(label,key)=>`<h4>${label}</h4><div class="tool-fields">${['X','Y','Z'].map((axis,i)=>field(axis+' '+label.toLowerCase(),'cloud-filter-'+key+'-'+i,draft[key][i])).join('')}</div>`;
 const method=draft.method,nearSurface=method.endsWith('NearGeom');
 host.innerHTML=`<p>Coordinates and distances use model units. Changes this cloud; Undo restores its previous points.</p>${select('Point filter','cloud-filter-method',methods,method)}<div data-cloud-filter-fields>${method.endsWith('BBox')?coordinates('Minimum','minimum')+coordinates('Maximum','maximum'):method.endsWith('Range')?select('Filter axis','cloud-filter-axis',[[0,'X'],[1,'Y'],[2,'Z']],draft.axis)+field('Minimum coordinate','cloud-filter-low',draft.low)+field('Maximum coordinate','cloud-filter-high',draft.high):['KeepPtsAbove','KeepPtsBelow'].includes(method)?select('Filter axis','cloud-filter-axis',[[0,'X'],[1,'Y'],[2,'Z']],draft.axis)+field('Coordinate','cloud-filter-value',draft.value):method.endsWith('NearPt')?coordinates('Center','center')+field('Radius','cloud-filter-radius',draft.radius):select('Filter surface','cloud-filter-target',surfaces,draft.target)+field('Maximum distance from surface','cloud-filter-tolerance',draft.tolerance)}</div>${button('cloud-filter-apply','Apply point filter',true)}`;
 const read=()=>{
  for(const key of ['minimum','maximum','center'])if(host.querySelector('#cloud-filter-'+key+'-0'))draft[key]=[0,1,2].map(i=>num('cloud-filter-'+key+'-'+i));
  for(const key of ['axis','low','high','value','radius','tolerance'])if(host.querySelector('#cloud-filter-'+key))draft[key]=num('cloud-filter-'+key);
  if(nearSurface)draft.target=val('cloud-filter-target');
 };
 for(const input of host.querySelectorAll('[data-cloud-filter-fields] input,[data-cloud-filter-fields] select'))input.onchange=()=>{try{read();}catch{}};
 host.querySelector('#cloud-filter-method').onchange=e=>{try{read();}catch{}draft.method=e.target.value;mountCloudFilters(host,cloud,surfaces,h);};
 const apply=host.querySelector('#cloud-filter-apply');apply.disabled=!cloud.points.length||(nearSurface&&!surfaces.length);
 h.bind('cloud-filter-apply',()=>{
  read();const request={operation:'point-cloud-filter',geom:cloud.id,method,...Object.fromEntries(['minimum','maximum','center','axis','low','high','value','radius','tolerance'].map(key=>[key,draft[key]]))};
  if(nearSurface){const [target,surface]=draft.target.split(':');Object.assign(request,{target,surface:Number(surface)});}
  return mutate(request);
 });
}
