import {analysisInputApplies} from './analysis-input-state.js?v=20261022-sweep-visibility';
// Test the native visibility rule against cases of the matching scalar input
// sweeps. Unrelated stages, preparation fields and assembly members stay separate.
export function studyRuleApplies(rule,axes,stage,kind,prefix,host,member=null){
 const allowed=new Map();
 const scan=r=>{if(r.any)r.any.forEach(scan);else if(r.all)r.all.forEach(scan);else{if(!allowed.has(r.input))allowed.set(r.input,new Set());for(const v of r.values)allowed.get(r.input).add(String(v));}};
 scan(rule);
 const domains=new Map();
 for(const a of axes){
  if(a.kind!==kind||a.stage!==stage||(a.member??null)!==member||(a.index??0)!==0||!allowed.has(a.name)||a.component!=null)continue;
  if(a.valueMode!=='array'&&(a.element??0)!==0)continue;
  const values=(a.values||[]).map(v=>a.valueMode==='array'?v?.[0]:v),relevant=allowed.get(a.name),domain=[];let other=false;
  // Values outside every literal in this rule are equivalent for visibility.
  for(const v of values){const text=String(v);if(relevant.has(text)){if(!domain.includes(text))domain.push(text);}else if(!other){domain.push(text);other=true;}}
  domains.set(`${prefix}-${a.name}-0`,domain);
 }
 const entries=[...domains],selected=new Map();
 const visit=i=>{
  if(i===entries.length)return analysisInputApplies(rule,prefix,{getElementById:id=>selected.has(id)?{value:selected.get(id)}:host.getElementById(id)});
  const [id,values]=entries[i];for(const value of values){selected.set(id,value);if(visit(i+1))return true;}selected.delete(id);return false;
 };
 return visit(0);
}
