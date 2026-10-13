const key='openvsp-studio-properties-mode-v1';
let mode='streamlined';
try{if(localStorage.getItem(key)==='pro')mode='pro';}catch{}
export const propertiesMode=()=>mode;
export function propertiesModeMarkup(){return `<div class="properties-mode" role="group" aria-label="Properties mode"><button type="button" data-properties-mode="streamlined" aria-pressed="${mode==='streamlined'}">Streamlined</button><button type="button" data-properties-mode="pro" aria-pressed="${mode==='pro'}">Pro</button></div>`;}
export function bindPropertiesMode(host,changed){host.querySelectorAll('[data-properties-mode]').forEach(button=>button.onclick=()=>{const next=button.dataset.propertiesMode;if(next===mode)return;mode=next;try{localStorage.setItem(key,mode);}catch{}changed();});}
export function applyPropertiesMode(host,searching){host.dataset.propertiesMode=mode;const advanced=host.querySelector('#parameter-groups'),title=host.querySelector('#advanced-parameter-title');if(advanced)advanced.hidden=mode==='streamlined'&&!searching;if(title){title.hidden=mode==='streamlined'||searching;title.textContent='Native settings';}if(advanced&&title){if(mode==='pro'){const anchor=host.querySelector('#family-workflows');anchor.before(title,advanced);}else{host.querySelector('#section-controls').after(title,advanced);}}}
