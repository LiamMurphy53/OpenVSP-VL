// One applicability rule for both the displayed guide and submitted inputs.
export function analysisInputApplies(rule,prefix,host){
 if(rule.any)return rule.any.some(r=>analysisInputApplies(r,prefix,host));
 if(rule.all)return rule.all.every(r=>analysisInputApplies(r,prefix,host));
 const controller=host.getElementById(`${prefix}-${rule.input}-0`);
 return !!controller&&rule.values.some(value=>String(value)===controller.value);
}
export function editableAnalysisInputs(spec,prefix,host){
 return (spec?.inputs||[]).filter(e=>e.editable&&(!e.applicableWhen||analysisInputApplies(e.applicableWhen,prefix,host)));
}
