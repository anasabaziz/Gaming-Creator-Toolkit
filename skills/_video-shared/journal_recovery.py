"""Explicit recovery to a new journal; never changes the damaged source or its locks."""
import argparse
import hashlib
import json
from pathlib import Path
import job_state as j


def recover(source, destination, expected_sha256, authorization):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not authorization or destination == source or source in destination.parents:
        raise ValueError('Supply explicit repair authorization and a new destination outside the source journal')
    if destination.exists():
        raise ValueError('Recovery destination must not exist')
    path = source / 'events.jsonl'
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Source journal changed since diagnosis')
    lines = raw.splitlines(keepends=True)
    prefix, events = [], []
    for i, line in enumerate(lines):
        try:
            if not line.endswith(b'\n'):
                raise ValueError('incomplete tail')
            event = json.loads(line)
            if not isinstance(event, dict) or event.get('sequence') != i + 1 or not event.get('id') or not event.get('kind'):
                raise ValueError('invalid event')
        except (ValueError, UnicodeError):
            if i != len(lines) - 1:
                raise ValueError('Damage is not confined to the final event; manual investigation required')
            break
        prefix.append(line)
        events.append(event)
    states = [e['state'] for e in events if 'state' in e]
    if not states or not isinstance(states[-1], dict) or not {'id', 'stages', 'artifacts', 'requirements'} <= set(states[-1]):
        raise ValueError('No usable complete state in the event prefix')
    if path.read_bytes() != raw:
        raise ValueError('Source journal changed during diagnosis')
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'damaged-events.original.jsonl').write_bytes(raw)
    (destination / 'events.jsonl').write_bytes(b''.join(prefix))
    state = j.snapshot(destination)
    for stage in state['stages'].values():
        if stage.get('status') == 'running':
            stage.update(status='blocked', next_action='Reconcile interrupted operation and record resume_change')
    with j.locked(destination) as root:
        j.append(root, 'journal_recovered', {'source': str(source), 'source_sha256': expected_sha256,
                 'authorization': authorization, 'retained_events': len(events),
                 'discarded_tail_bytes': len(raw) - sum(map(len, prefix)),
                 'original_preserved': str(destination / 'damaged-events.original.jsonl')}, state)
    return {'journal': str(destination), 'next_action': 'Reconcile; use this journal explicitly. Preserve original files and dependencies.'}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source'); ap.add_argument('--destination', required=True)
    ap.add_argument('--expected-sha256', required=True); ap.add_argument('--authorization', required=True)
    args = ap.parse_args()
    print(json.dumps(recover(args.source, args.destination, args.expected_sha256, args.authorization)))
