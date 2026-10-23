import assert from 'node:assert/strict';
import {cstEditorMarkup} from '../web/cst-sliders.js';
const helpers={E:String,card:(title,body)=>`<section><h2>${title}</h2>${body}</section>`,field:(name,id,value)=>`<label>${name}<input id="${id}" value="${value}"></label>`,button:(id,name)=>`<button id="${id}">${name}</button>`};
for(const type of ['FUSELAGE','STACK','WING','PROP']){
 const component={id:'component',type},section={surface:0,index:1,cstFitAllowed:true};
 const fit=cstEditorMarkup(component,section,helpers);
 assert.match(fit,/Fit current profile to CST/);assert.match(fit,/id="cst-degree"/);
 const cst={...section,cst:{upper:[.2,.4],lower:[-.2]}};
 const edit=cstEditorMarkup(component,cst,helpers);
 assert.match(edit,/Upper coefficient 1 slider/);assert.match(edit,/Apply coefficients/);
 assert.match(edit,/data-cst-degree="lower" data-direction="demote" disabled/);
 assert.doesNotMatch(edit,/Fit current profile/);
 assert.equal(cstEditorMarkup(component,{...section,cstFitAllowed:false},helpers),'');
 assert.equal(cstEditorMarkup(component,{...cst,generated:true},helpers),'');
 assert.equal(cstEditorMarkup(component,{surface:0,index:1},helpers),'');
}
console.log('CST editor follows native profile eligibility for every section owner and preserves generated-profile guards.');
