// Keep the user's place while native edits replace the properties contents.
export function preserveInspectorView(host,context){
 const same=host.dataset.viewContext===context;
 const scroller=host.closest('.inspector')||host;
 const top=scroller.scrollTop,left=scroller.scrollLeft;
 const keys=()=>{const counts=new Map();return [...host.querySelectorAll('details')].map(el=>{
  const base=el.id||el.dataset.group||`${el.parentElement?.id||''}/${el.querySelector(':scope > summary')?.textContent.trim()||''}`;
  const index=counts.get(base)||0;counts.set(base,index+1);return [el,`${base}/${index}`];
 });};
 const opened=new Map(same?keys().map(([el,key])=>[key,el.open]):[]);
 return ()=>{
  if(same){
   for(const [el,key] of keys())if(opened.has(key))el.open=opened.get(key);
   scroller.scrollTop=top;scroller.scrollLeft=left;
  }
  host.dataset.viewContext=context;
 };
}
