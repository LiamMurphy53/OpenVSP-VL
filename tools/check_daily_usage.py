"""Local bookkeeping for Codex's agent-followed daily guard; no quota API.

Feed a fresh weekly usage sample on stdin. Exit 0 allows work, exit 2 stops.
Only first-time installation may use --initialize. Missing state fails closed.
"""
import argparse
from datetime import datetime
import fcntl
import json
import math
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

STATE = Path(__file__).resolve().parents[1] / '.workspace/daily-codex-usage.json'


def evaluate(state, sample, now, initialize=False):
    used, reset = sample['usedPercent'], sample['resetsAt']
    if (isinstance(used, bool) or not isinstance(used, (int, float))
            or not math.isfinite(used) or not 0 <= used <= 100
            or isinstance(reset, bool) or not isinstance(reset, int)
            or reset <= now.timestamp()):
        raise ValueError('Unavailable or invalid weekly usage sample')
    day = now.astimezone(ZoneInfo('America/Denver')).date().isoformat()
    if state is None:
        if not initialize:
            raise ValueError('Missing ledger; do not silently grant allowance')
        state = {'version': 1, 'days': {}, 'lastUsedPercent': used,
                 'resetsAt': reset, 'lastDay': day}
    if state['version'] != 1 or day < state['lastDay']:
        raise ValueError('Invalid ledger or clock moved backwards')
    previous = state['lastUsedPercent']
    changed = reset != state['resetsAt'] or used < previous
    if day not in state['days']:
        state['days'][day] = {'baselinePercent': used, 'spentPoints': 0,
                             'stopReason': None}
    entry = state['days'][day]
    if changed and day == state['lastDay']:
        entry['stopReason'] = 'Weekly meter changed/reset; daily spend uncertain'
    elif day == state['lastDay']:
        entry['spentPoints'] += max(0, used - previous)
    if entry['spentPoints'] >= 10:
        entry['stopReason'] = 'Daily allowance reached'
    state.update(lastUsedPercent=used, resetsAt=reset, lastDay=day,
                 lastCheckedAt=now.isoformat())
    result = {'decision': 'STOP' if entry['stopReason'] else 'CONTINUE',
              'day': day, 'timezone': 'America/Denver', 'dailyCapPoints': 10,
              'stopAtReportedPoints': 10, 'spentPoints': entry['spentPoints'],
              'baselinePercent': entry['baselinePercent'],
              'weeklyUsedPercent': used, 'reason': entry['stopReason']}
    return state, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--initialize', action='store_true')
    args = parser.parse_args()
    try:
        sample = json.load(sys.stdin)
        STATE.parent.mkdir(parents=True, exist_ok=True)
        with STATE.with_suffix('.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = json.loads(STATE.read_text()) if STATE.exists() else None
            if args.initialize and state is not None:
                raise ValueError('Ledger already initialized')
            state, result = evaluate(state, sample, datetime.now().astimezone(),
                                     args.initialize)
            temporary = STATE.with_suffix('.tmp')
            temporary.write_text(json.dumps(state, indent=2) + '\n')
            temporary.replace(STATE)
        print(json.dumps(result))
        return 2 if result['decision'] == 'STOP' else 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(json.dumps({'decision': 'STOP', 'reason': str(error)}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
