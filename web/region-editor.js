import {regionBoundaryControls} from './region-boundary-controls.js?v=20261011-boundaries';
import {partProperties} from './part-properties.js?v=20261011-elements';
import {regionCurveEditor,bindRegionCurves} from './region-curve-editor.js?v=20261010-123';
export function regionEditor(c,d,h){
 const {E,select,field,button,paramDetails,card,nice}=h;
 if(!c)return card('Surface regions','<p>Choose a component first.</p>');
 const regions=d.controls.filter(s=>s.geom===c.id),surfaces=c.surfaces.filter(s=>s.index<c.mainSurfaceCount);
 const choices=surfaces.map((s,i)=>[s.index??i,`Surface ${s.index??i}`]);
 // The main-surface count is supplied by the engine; symmetry copies share a
 // main surface and must not be offered as independent region attachments.
 return card('Native surface regions',`<p>Create lines, rectangles, ellipses, control boundaries, section curves, or intersections on a native surface.</p><div class="tool-fields">${field('Region name','region-name','Surface region','text')}${select('Region type','region-type',Object.keys(d.subsurfaceTypes).filter(t=>t!=='SS_LINE_ARRAY'&&(t!=='SS_CONTROL'||['WING','PROP','PROPELLER'].includes(c.type.toUpperCase()))).map(t=>[t,nice(t.replace('SS_',''))]),'SS_RECTANGLE')}${select('Parent surface','region-surface',choices)}</div>${button('region-add','Add surface region',true)}<p class="native-tip">Boundaries partition native meshes. Inspect their native polygon boundaries in Design. Add structural line arrays in Constraints & laminates.</p>`,'wide')+card('Regions on this component',regions.map(s=>`<article class="tool-item"><h3>${E(s.name)}</h3><div class="inline-fields">${field('Region name','region-name-'+s.id,s.name,'text')}<button data-region-rename="${E(s.id)}">Rename region</button></div>${partProperties(s,d,h,true)}${regionCurveEditor(s,d,h)}${regionBoundaryControls(s,h)}${s.intersectionTarget!==null?`<p>Intersect the parent with another component using the native surface intersection solver. Recompute after changing either component.</p>${select('Intersect with','region-target-'+s.id,h.modelComponents.filter(g=>g.id!==c.id).map(g=>[g.id,g.name]),s.intersectionTarget)}<button data-region-intersect="${E(s.id)}" ${h.modelComponents.length>1?'':'disabled'}>Compute intersection region</button>`:''}<div class="tool-actions"><button data-region-view="${E(s.id)}">View boundary</button><button data-region-move="${E(s.id)}" data-direction="REORDER_MOVE_UP">Move up</button><button data-region-move="${E(s.id)}" data-direction="REORDER_MOVE_DOWN">Move down</button><button data-control-delete="${E(s.id)}">Remove region</button></div></article>`).join('')||'<p>No surface regions yet.</p>','wide');
}
export function bindRegionEditor(c,h){
 if(!c)return;
 const {bind,mutate,val,num}=h,common={geom:c.id};
 bindRegionCurves(h,common);
 document.querySelectorAll('[data-region-property]').forEach(el=>el.onchange=()=>mutate({...common,operation:'subsurface-property',id:el.dataset.regionProperty,role:el.dataset.propertyRole,property:el.value}));
 document.querySelectorAll('[data-region-view]').forEach(b=>b.onclick=()=>h.showRegionBoundary(b.dataset.regionView));
 bind('region-add',()=>mutate({...common,operation:'subsurface-add',name:val('region-name'),type:val('region-type'),surface:num('region-surface')}));
 document.querySelectorAll('[data-region-rename]').forEach(b=>b.onclick=()=>mutate({...common,operation:'subsurface-rename',id:b.dataset.regionRename,name:val('region-name-'+b.dataset.regionRename)}));
 document.querySelectorAll('[data-region-move]').forEach(b=>b.onclick=()=>mutate({...common,operation:'subsurface-reorder',id:b.dataset.regionMove,direction:b.dataset.direction}));
 document.querySelectorAll('[data-region-intersect]').forEach(b=>b.onclick=()=>mutate({...common,operation:'subsurface-intersect',id:b.dataset.regionIntersect,target:val('region-target-'+b.dataset.regionIntersect)}));
}
