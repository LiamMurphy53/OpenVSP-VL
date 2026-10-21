"""Workspace-only set identities, stored beside native undo/redo snapshots.

Empty native attribute collections are not serialized, so their API IDs cannot
identify sets after cold loading. No tracking attributes enter the aircraft.
"""
import re
import uuid


def fresh(count):return ['builtin:'+str(i) if i<3 else uuid.uuid4().hex for i in range(count)]


def validate_registry(registry):
    if not isinstance(registry,dict):raise ValueError('Invalid saved set identity registry.')
    for key,values in registry.items():
        if not isinstance(key,str) or not (key=='current' or re.fullmatch('history/[a-f0-9]{32}\\.vsp3',key)) or not isinstance(values,list) or len(values)<3 or values[:3]!=fresh(3) or any(not isinstance(x,str) or not re.fullmatch('[a-f0-9]{32}',x) for x in values[3:]) or len(values)!=len(set(values)):
            raise ValueError('Invalid saved geometry-set identities.')


def annotate(state,registry):
    sets=state.get('tools',{}).get('sets')
    if sets is None:return False
    created='current' not in registry or len(registry['current'])!=len(sets)
    if created:registry['current']=fresh(len(sets))
    for item,identity in zip(sets,registry['current']):item['identity']=identity
    return created


def transfer(count,order,registry):
    old=registry.get('current',fresh(count))
    if order is not None:ids=[*old[:3],*(old[i] for i in order)]
    else:ids=[*old[:count],*fresh(count)[len(old):]]
    registry['current']=ids
