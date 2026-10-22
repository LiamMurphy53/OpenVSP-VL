// Keep the user's place while native edits replace the properties contents.
export function preserveInspectorView(host,context){
 const same=host.dataset.viewContext===context;
 const scroller=host.closest('.inspector')||host;
 const top=scroller.scrollTop,left=scroller.scrollLeft;
 // Modeling tools can scroll the document instead of the editor itself.
 // Replacing a tall editor briefly shrinks the page and clamps that scroll.
 const ancestors=new Set();
 for(let parent=host.parentElement;parent;parent=parent.parentElement)ancestors.add(parent);
 if(document.scrollingElement)ancestors.add(document.scrollingElement);
 const outer=[...ancestors].filter(el=>el!==scroller&&(el.scrollTop||el.scrollLeft)).map(el=>({el,top:el.scrollTop,left:el.scrollLeft}));

 const keys=()=>{const counts=new Map();return [...host.querySelectorAll('details')].map(el=>{
  const base=el.id||el.dataset.group||`${el.parentElement?.id||''}/${el.querySelector(':scope > summary')?.textContent.trim()||''}`;
  const index=counts.get(base)||0;counts.set(base,index+1);return [el,`${base}/${index}`];
 });};
 const active=host.contains(document.activeElement)?document.activeElement:null;
 const slider=active?.matches('[data-custom-slider]')?{
  key:active.closest('[data-slider-key]')?.dataset.sliderKey,
  group:active.closest('[data-group]')?.dataset.group||''
 }:null;
 const nested=new Map(same?[...host.querySelectorAll('[data-scroll-key]')].map(el=>[el.dataset.scrollKey,{top:el.scrollTop,left:el.scrollLeft}]):[]);
 const opened=new Map(same?keys().map(([el,key])=>[key,el.open]):[]);
 return ()=>{
  if(same){
   for(const [el,key] of keys())if(opened.has(key))el.open=opened.get(key);
   if(slider?.key){
    const wrapper=[...host.querySelectorAll('[data-slider-key]')].find(el=>el.dataset.sliderKey===slider.key&&(el.closest('[data-group]')?.dataset.group||'')===slider.group);
    const input=wrapper?.querySelector('[data-custom-slider]');
    if(input&&!input.disabled)input.focus({preventScroll:true});
   }
   for(const el of host.querySelectorAll('[data-scroll-key]')){const saved=nested.get(el.dataset.scrollKey);if(saved){el.scrollTop=saved.top;el.scrollLeft=saved.left;}}
   scroller.scrollTop=top;scroller.scrollLeft=left;
   const restoreOuter=()=>{if(host.isConnected!==false&&host.dataset.viewContext===context)for(const {el,top,left} of outer){el.scrollTop=top;el.scrollLeft=left;}};
   for(const {el,top,left} of outer){el.scrollTop=top;el.scrollLeft=left;}
   // Dock toolbars are reattached by a mutation observer after rendering.
   queueMicrotask(restoreOuter);

  }
  host.dataset.viewContext=context;
 };
}
