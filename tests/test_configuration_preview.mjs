import assert from 'node:assert/strict';
import {configurationPreviewMarkup,previewButton,bindConfigurationPreviews,configurationPreviewPayload} from '../web/configuration-preview.js';
const esc=x=>String(x).replaceAll('<','&lt;').replaceAll('"','&quot;');
assert.match(configurationPreviewMarkup({changes:[]},esc),/0 changed/);
const changes=Array.from({length:205},(_,i)=>({label:'<Wing> '+i,before:1,after:2,unit:'native parameter units',status:i===0?'added':'changed'}));
const html=configurationPreviewMarkup({changes},esc);assert.match(html,/&lt;Wing>/);assert.match(html,/First 200/);assert.match(html,/Unavailable|Current/);assert.doesNotMatch(html,/&lt;Wing> 204/);
assert.match(previewButton('preset',{group:'"group',setting:'setting'},esc),/data-group="&quot;group"/);
const output={querySelector:()=>null,isConnected:true,textContent:'',innerHTML:''};const button={dataset:{previewConfiguration:'mode',id:'mode'},parentElement:{querySelector:()=>output},isConnected:true};
let revision='r';const app={esc,model:()=>({revision}),api:async()=>({revision:'r',changes:[]})};
bindConfigurationPreviews({querySelectorAll:()=>[button]},app,'r');await button.onclick();assert.match(output.innerHTML,/0 changed/);assert.equal(button.disabled,false);
revision='new';await button.onclick();assert.match(output.textContent,/aircraft changed/);
app.api=async()=>{throw Error('Locked length');};await button.onclick();assert.equal(output.textContent,'Locked length');assert.equal(button.disabled,false);
console.log('Native configuration preview formatting, limits, stale-result and failure recovery passed.');

assert.equal(JSON.parse(configurationPreviewPayload({changes})).changes.length,205);

// Unsaved preset drafts invalidate both visible and in-flight saved previews.
const field={value:'12',addEventListener(type,fn){this.oninput=fn;}};
const draftOutput={isConnected:true,textContent:'',innerHTML:'',querySelector:()=>null};
const draftButton={dataset:{previewConfiguration:'preset',group:'g',setting:'s'},parentElement:{querySelector:()=>draftOutput},closest:()=>({querySelectorAll:()=>[field]}),isConnected:true};
let resolvePreview,calls=0;
const draftApp={esc,model:()=>({revision:'r'}),api:()=>{calls++;return new Promise(resolve=>{resolvePreview=resolve;});}};
bindConfigurationPreviews({querySelectorAll:()=>[draftButton]},draftApp,'r');
field.value='14';field.oninput();assert.equal(draftButton.disabled,true);assert.match(draftOutput.textContent,/Save edited values/);
await draftButton.onclick();assert.equal(calls,0,'Unsaved values cannot request a saved preset preview');
field.value='12';field.oninput();assert.equal(draftButton.disabled,false);assert.match(draftOutput.textContent,/Preview the saved values again/);
const pending=draftButton.onclick();field.value='16';field.oninput();resolvePreview({revision:'r',changes:[]});await pending;
assert.equal(draftButton.disabled,true);assert.match(draftOutput.textContent,/Save edited values/);assert.equal(draftOutput.innerHTML,'','A completed stale preview cannot replace the draft warning');
field.value='12';field.oninput();const current=draftButton.onclick();resolvePreview({revision:'r',changes:[]});await current;assert.match(draftOutput.innerHTML,/0 changed/);assert.equal(draftButton.disabled,false);
