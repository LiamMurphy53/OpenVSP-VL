const key='openvsp-studio-layout-v1';
const definitions=[
 {id:'design',host:'#design-page',panes:[['aircraft','.components','Aircraft',210],['model','.viewport','Model',0],['properties','.inspector','Properties',330]]},
 {id:'analysis',host:'#analysis-page',panes:[['setup','.analysis-intro','Analysis setup',420],['results','.analysis-right','Results',0]]},
 {id:'tools',host:'#tools-page',panes:[['navigation','.tool-tabs','Tool tabs',235],['editor','#tool-content','Tool editor',0]]},
 {id:'studies',host:'.study-layout',panes:[['setup','.study-editor','Study setup',470],['results','.study-results','Study results',0]]}
];
export function installWorkspaceLayout(){
 let saved={};try{saved=JSON.parse(localStorage.getItem(key))||{};}catch{}
 let current='design';
 const states=new Map(definitions.map(d=>{
  const ids=d.panes.map(p=>p[0]),old=saved[d.id]||{},order=Array.isArray(old.order)?old.order.filter((x,i,a)=>ids.includes(x)&&a.indexOf(x)===i):[];
  order.push(...ids.filter(x=>!order.includes(x)));
  const hidden=Array.isArray(old.hidden)?old.hidden.filter((x,i,a)=>ids.includes(x)&&a.indexOf(x)===i):[];if(hidden.length===ids.length)hidden.length=0;
  const widths=Object.fromEntries(d.panes.map(([id,,,width])=>[id,Number.isFinite(old.widths?.[id])?Math.max(170,Math.min(700,old.widths[id])):width]));
  return [d.id,{order,hidden,widths,max:null}];
 }));
 const menu=document.querySelector('#panel-menu'),restore=document.querySelector('#restore-layout-pane');
 function persist(){try{localStorage.setItem(key,JSON.stringify(Object.fromEntries([...states].map(([id,s])=>[id,{order:s.order,hidden:s.hidden,widths:s.widths}]))));}catch{}}
 function change(d,fn){fn(states.get(d.id));persist();apply(d);updateMenu();}
 function move(d,id,offset){change(d,s=>{const i=s.order.indexOf(id),j=i+offset;if(j>=0&&j<s.order.length)[s.order[i],s.order[j]]=[s.order[j],s.order[i]];});}
 function toolbar(d,id,label){
  const bar=document.createElement('div');bar.className='pane-toolbar';
  const handle=document.createElement('button');handle.className='pane-handle';handle.textContent='⠿ '+label;handle.title='Drag onto another panel to move. Use Alt + arrow keys to reorder.';handle.setAttribute('aria-label','Move '+label+' panel');
  handle.onpointerdown=e=>{
   if(e.button!==0)return;e.preventDefault();handle.setPointerCapture(e.pointerId);const start=[e.clientX,e.clientY];let target=null,moved=false;
   const clear=()=>document.querySelectorAll('.pane-drop-target').forEach(el=>el.classList.remove('pane-drop-target'));
   handle.onpointermove=m=>{if(Math.hypot(m.clientX-start[0],m.clientY-start[1])<5&&!moved)return;moved=true;clear();const pane=document.elementFromPoint(m.clientX,m.clientY)?.closest('.dock-pane');target=pane?.parentElement.dataset.workspace===d.id&&pane.dataset.pane!==id?pane:null;target?.classList.add('pane-drop-target');};
   const end=m=>{handle.onpointermove=null;clear();if(m.type==='pointerup'&&target&&moved){const to=target.dataset.pane;change(d,s=>{const a=s.order.indexOf(id),b=s.order.indexOf(to);[s.order[a],s.order[b]]=[s.order[b],s.order[a]];});}target=null;};handle.onpointerup=end;handle.onpointercancel=end;handle.onlostpointercapture=end;
  };
  handle.onkeydown=e=>{if(e.altKey&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();move(d,id,['ArrowLeft','ArrowUp'].includes(e.key)?-1:1);}};
  bar.append(handle);
  for(const [text,name,action] of [ ['‹','Move '+label+' panel left',()=>move(d,id,-1)],['›','Move '+label+' panel right',()=>move(d,id,1)],['⛶','Maximize '+label+' panel',()=>change(d,s=>s.max=s.max===id?null:id)],['×','Close '+label+' panel',()=>change(d,s=>{s.hidden.push(id);s.max=null;})] ]){
   const b=document.createElement('button');b.textContent=text;b.setAttribute('aria-label',name);b.title=name;b.onclick=action;bar.append(b);
  }
  return bar;
 }
 function apply(d){
  const host=document.querySelector(d.host);if(!host)return;host.classList.add('dock-host');host.dataset.workspace=d.id;
  const s=states.get(d.id),visible=s.order.filter(id=>!s.hidden.includes(id)&&(!s.max||s.max===id));
  host.classList.toggle('pane-maximized',!!s.max);
  for(const [id,selector,label] of d.panes){
   const pane=host.querySelector(selector);if(!pane)continue;
   pane.classList.add('dock-pane');pane.dataset.pane=id;pane.style.order=s.order.indexOf(id)+1;pane.hidden=!visible.includes(id);
   if(!pane.querySelector(':scope > .pane-toolbar')){
    pane.prepend(toolbar(d,id,label));
    const separator=document.createElement('div');separator.className='pane-resizer';separator.tabIndex=0;separator.setAttribute('role','separator');separator.setAttribute('aria-orientation','vertical');separator.setAttribute('aria-label','Resize '+label+' panel');
    const resizeBy=delta=>{const ids=s.order.filter(x=>!s.hidden.includes(x)),next=host.querySelector('[data-pane="'+ids[ids.indexOf(id)+1]+'"]'),target=pane.classList.contains('pane-flexible')&&next?next:pane,targetID=target.dataset.pane;const value=target.getBoundingClientRect().width+(target===pane?delta:-delta);s.widths[targetID]=Math.max(170,Math.min(700,host.clientWidth*.65,value));target.style.setProperty('--pane-width',s.widths[targetID]+'px');separator.setAttribute('aria-valuenow',Math.round(pane.getBoundingClientRect().width));};
    separator.onkeydown=e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();resizeBy(e.key==='ArrowLeft'?-20:20);persist();}};
    separator.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();separator.setPointerCapture(e.pointerId);let x=e.clientX;separator.onpointermove=m=>{resizeBy(m.clientX-x);x=m.clientX;};const end=()=>{separator.onpointermove=null;persist();};separator.onpointerup=end;separator.onpointercancel=end;separator.onlostpointercapture=end;};pane.append(separator);
   }
   const flexible=d.panes.find(p=>p[3]===0)?.[0],fill=visible.includes(flexible)?flexible:visible.at(-1);
   pane.style.setProperty('--pane-width',(s.widths[id]||420)+'px');pane.classList.toggle('pane-flexible',id===fill||visible.length===1);
   const buttons=pane.querySelector('.pane-toolbar').children;
   buttons[1].disabled=s.order.indexOf(id)===0;buttons[2].disabled=s.order.indexOf(id)===s.order.length-1;buttons[3].setAttribute('aria-label',(s.max===id?'Restore ':'Maximize ')+label+' panel');buttons[3].title=buttons[3].getAttribute('aria-label');buttons[3].textContent=s.max===id?'↙':'⛶';buttons[4].disabled=s.order.length-s.hidden.length<=1;
   const separator=pane.querySelector(':scope > .pane-resizer');separator.hidden=visible.at(-1)===id||visible.length===1;separator.setAttribute('aria-valuemin','170');separator.setAttribute('aria-valuemax',Math.floor(host.clientWidth));separator.setAttribute('aria-valuenow',Math.round(pane.getBoundingClientRect().width));
  }
 }
 function updateMenu(){
  const d=definitions.find(d=>d.id===current),s=states.get(current);menu.replaceChildren();
  for(const [id,,label] of d.panes){const row=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.checked=!s.hidden.includes(id);input.disabled=input.checked&&s.order.length-s.hidden.length<=1;input.onchange=()=>change(d,state=>{state.max=null;state.hidden=input.checked?state.hidden.filter(x=>x!==id):[...state.hidden,id];});row.append(input,document.createTextNode(label));menu.append(row);}
  restore.hidden=!s.max;restore.onclick=()=>change(d,s=>s.max=null);
 }
 document.querySelector('#reset-layout').onclick=()=>{const d=definitions.find(d=>d.id===current);change(d,s=>{s.order=d.panes.map(p=>p[0]);s.hidden=[];s.widths=Object.fromEntries(d.panes.map(([id,,,w])=>[id,w]));s.max=null;});};
 document.querySelectorAll('[data-page]').forEach(button=>button.addEventListener('click',()=>{current=button.dataset.page;apply(definitions.find(d=>d.id===current));updateMenu();}));
 // Editors replace their contents after native edits. Reattach controls without
 // rebuilding inputs or changing any native model data.
 const observer=new MutationObserver(()=>{for(const d of definitions){const host=document.querySelector(d.host);if(host&&d.panes.some(([,selector])=>{const pane=host.querySelector(selector);return pane&&!pane.querySelector(':scope > .pane-toolbar');}))apply(d);}});
 for(const id of ['tools-page','studies-page'])observer.observe(document.getElementById(id),{childList:true,subtree:true});
 for(const d of definitions)apply(d);updateMenu();
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!document.querySelector('dialog[open]')){const d=definitions.find(d=>d.id===current);if(states.get(current).max)change(d,s=>s.max=null);}});
}
