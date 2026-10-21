"""Per-field native defaults remain inherited even when other inputs freeze."""
def prepare(stage):
    follows=stage.get('followDefaults',[])
    if not isinstance(follows,list) or len(follows)>1000:raise ValueError('Choose known study inputs to inherit.')
    seen=set()
    for field in follows:
        if not isinstance(field,dict) or field.get('scope') not in ('inputs','geometryInputs') or not isinstance(field.get('name'),str) or type(field.get('index',0))!=int:raise ValueError('Choose known study inputs to inherit.')
        key=(field['scope'],field['name'],field.get('index',0))
        if key in seen:raise ValueError('Choose each inherited study input once.')
        seen.add(key)
    for scope in ('inputs','geometryInputs'):
        entries=stage.get(scope,[])
        if not isinstance(entries,list) or any(not isinstance(e,dict) for e in entries):raise ValueError('Use known native study inputs.')
        stage[scope]=[e for e in entries if (scope,e.get('name'),e.get('index',0)) not in seen]


def validate(stage,spec):
    known={'inputs':spec['inputs'],'geometryInputs':spec.get('geometryInputs',spec.get('geometrySchema',{}).get('inputs',[]))}
    for field in stage.get('followDefaults',[]):
        if not any(e['name']==field['name'] and e['index']==field.get('index',0) and e.get('editable') is not False for e in known[field['scope']]):raise ValueError('An inherited study input is unavailable. Choose a current native input.')
