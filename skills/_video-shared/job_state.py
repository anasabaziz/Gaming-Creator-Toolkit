"""Durable workflow journal. No media processing or automatic skill edits."""
import argparse
from contextvars import ContextVar
from functools import wraps
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


_audit_cache = ContextVar('audit_cache', default=None)


def audit_scope(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        token = _audit_cache.set({})
        try:
            return fn(*args, **kwargs)
        finally:
            _audit_cache.reset(token)
    return wrapped


def identity(path):
    p = Path(path).resolve()
    cache = _audit_cache.get()
    stat = p.stat()
    key = (str(p), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino)
    if cache is not None and key in cache:
        return dict(cache[key])
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    after = p.stat()
    if (after.st_size, after.st_mtime_ns, after.st_ctime_ns, after.st_ino) != key[1:]:
        raise ValueError('File changed during integrity check: ' + str(p))
    result = {'path': str(p), 'sha256': h.hexdigest(), 'size': stat.st_size}
    if cache is not None:
        cache[key] = result
    return dict(result)


@contextmanager
def locked(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock = root / '.job.lock'
    with lock.open('x') as f:
        f.write(str(os.getpid()))
    try:
        yield root
    finally:
        lock.unlink()


def history(root):
    path = Path(root) / 'events.jsonl'
    if not path.exists():
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Incomplete journal tail; preserve and investigate before further writes')
    events = [json.loads(line) for line in raw.splitlines()]
    if any(e['sequence'] != i for i, e in enumerate(events, 1)):
        raise ValueError('Journal sequence damaged; preserve and investigate')
    return events


def snapshot(root):
    state = None
    for event in history(root):
        if 'state' in event:
            state = event['state']
    if state is None:
        raise ValueError('Initialize the job first')
    return state


def save_snapshot(root, state):
    temp = root / ('job.' + uuid.uuid4().hex + '.tmp')
    with temp.open('w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, root / 'job.json')


def append(root, kind, data, state=None):
    events = history(root)
    event = {'id': uuid.uuid4().hex, 'sequence': len(events) + 1,
             'time': time.time(), 'kind': kind, 'data': data}
    if state is not None:
        event['state'] = state
    with (root / 'events.jsonl').open('a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(event) + '\n')
        f.flush()
        os.fsync(f.fileno())
    if state is not None:
        save_snapshot(root, state)
    return event


def record(root, kind, data):
    with locked(root) as root:
        snapshot(root)
        return append(root, kind, data)


def update(root, action, data):
    with locked(root) as root:
        if action == 'init':
            if (root / 'events.jsonl').exists() or (root / 'job.json').exists():
                raise ValueError('Existing job protected')
            state = {'schema_version': 2, 'id': uuid.uuid4().hex, 'requirements': [],
                     'stages': {}, 'decisions': [], 'artifacts': {}, 'issues': [],
                     'next_action': '', 'proposals': {}}
        else:
            state = snapshot(root)
        if action in ('init', 'plan'):
            if set(data) - {'requirements', 'decisions', 'issues', 'next_action'}:
                raise ValueError('Unsupported plan fields')
            for req in data.get('requirements', []):
                if not req.get('text') or not req.get('source'):
                    raise ValueError('Requirements need text and source')
            state.update(data)
        elif action in ('baseline', 'baseline_assessment', 'preflight', 'contract', 'review', 'resolution', 'archive'):
            import review
            collections = {'baseline': 'baselines', 'baseline_assessment': 'baseline_assessments',
                           'preflight': 'preflights', 'contract': 'contracts', 'review': 'reviews', 'resolution': 'resolutions', 'archive': 'archives'}
            collection = state.setdefault(collections[action], {})
            if not data.get('id') or data['id'] in collection:
                raise ValueError('Record IDs must be present and immutable')
            if action == 'baseline':
                from instruction_baseline import capture
                data = capture(root, data)
            elif action == 'baseline_assessment':
                from instruction_baseline import changes
                delta = changes(state['baselines'][data['baseline']])
                if not data.get('reason') or not data.get('source') or data.get('decision') != 'retain':
                    raise ValueError('Retaining old baseline needs reason and instruction/evidence source; adoption uses a new baseline/contract')
                if any(x['status'] == 'snapshot_changed' for x in delta):
                    raise ValueError('Cannot waive damaged instruction snapshots')
                data = {**data, 'changes_digest': review.digest(delta), 'changes': delta}
            elif action == 'preflight':
                report = json.loads(Path(data['path']).read_text(encoding='utf-8-sig'))
                if report.get('schema_version') != 1 or not isinstance(report.get('capabilities'), dict):
                    raise ValueError('Invalid preflight report')
                for cap in report['capabilities'].values():
                    if cap.get('status') not in ('available', 'unavailable', 'unknown'):
                        raise ValueError('Invalid capability status')
                    if cap['status'] == 'available' and (not cap.get('method') or not cap.get('notes') or not cap.get('evidence') or not all(review.intact(e) for e in cap['evidence'])):
                        raise ValueError('Available capability needs intact evidence and method')
                data = {**data, 'report': report, 'identity': identity(data['path'])}
            elif action == 'contract':
                data = review.contract(state, data)
            elif action == 'review':
                data = review.seal_review(state, data)
            elif action == 'resolution':
                data = review.seal_resolution(state, data)
            elif action == 'archive':
                report = json.loads(Path(data['path']).read_text(encoding='utf-8-sig'))
                if report.get('kind') not in ('archive_inventory', 'archive_verification'):
                    raise ValueError('Expected archive inventory or verification report')
                data = {**data, 'identity': identity(data['path']), 'report': report}
            collection[data['id']] = data
        elif action in ('delivery', 'review_choice', 'acceptance', 'closure'):
            import review
            stage = state['stages'][data['stage']]
            cid = stage.get('contract')
            if not cid or data.get('contract') != cid:
                raise ValueError('Identify the current exact contract revision')
            contract = state['contracts'][cid]
            if set(stage.get('artifacts', [])) != set(contract['artifacts']) or contract['stage'] != data['stage']:
                raise ValueError('Stage artifacts do not match contract')
            targets = {k: state['artifacts'][k]['identity'] for k in stage['artifacts']}
            if not targets or not all(review.intact(v) for v in targets.values()):
                raise ValueError('Delivered artifacts changed or missing')
            delivered = any(d['contract'] == cid and d['targets'] == targets for d in state.get('deliveries', []))
            # Completed legacy records remain usable; new incomplete revisions need explicit delivery.
            if action != 'delivery' and not delivered and stage['status'] != 'completed':
                raise ValueError('Register exact artifact delivery first')
            if action == 'delivery':
                if not data.get('source'):
                    raise ValueError('Delivery needs its user-facing handoff source')
                state.setdefault('deliveries', []).append({**data, 'targets': targets})
            elif action == 'closure':
                if data.get('decision') != 'closed' or not data.get('source') or not data.get('acceptor'):
                    raise ValueError('Closure needs explicit user statement and identity')
                state.setdefault('closures', []).append({**data, 'targets': targets,
                    'outstanding_at_recording': review.acceptance_problems(state, stage)})
            elif action == 'review_choice':
                if data.get('choice') not in ('pending', 'subagent_requested', 'human_sufficient') or not data.get('source'):
                    raise ValueError('Record the post-delivery question or explicit user choice')
                state.setdefault('review_choices', {})[data['stage']] = data
            else:
                if data.get('decision') not in ('accepted', 'changes_requested') or not data.get('source') or not data.get('acceptor'):
                    raise ValueError('Acceptance needs explicit user response and acceptor identity')
                if not all(review.intact(state['artifacts'][k]['identity']) for k in stage['artifacts']):
                    raise ValueError('Acceptance artifacts changed')
                state.setdefault('acceptances', []).append({**data, 'artifacts': list(stage['artifacts']),
                    'targets': targets, 'outstanding_at_recording': review.acceptance_problems(state, stage)})
        elif action == 'stage':
            if data['status'] not in ('pending', 'running', 'awaiting_review', 'blocked', 'completed'):
                raise ValueError('Invalid stage status')
            previous = state['stages'].get(data['id'], {})
            if previous.get('status') == 'blocked' and data['status'] == 'running' and not data.get('resume_change'):
                raise ValueError('Blocked retry needs resume_change describing the resolved cause and evidence/source')
            data = {**previous, **data}
            prospective = {**state['stages'], data['id']: data}
            def visit(key, trail=()):
                if key in trail:
                    raise ValueError('Dependency cycle: ' + ' -> '.join((*trail, key)))
                for dep in prospective.get(key, {}).get('depends_on', []):
                    visit(dep, (*trail, key))
            visit(data['id'])
            if data['status'] in ('running', 'completed'):
                from review import dependency_problems
                problems = dependency_problems(state, data)
                if problems:
                    raise ValueError('; '.join(problems))
            if data['status'] == 'completed':
                if not data.get('artifacts'):
                    raise ValueError('Completion needs artifact IDs and review evidence')
                if state['schema_version'] >= 2 or data.get('contract'):
                    from review import evaluate
                    problems = evaluate(state, data)
                    if problems:
                        raise ValueError('Completion refused: ' + '; '.join(problems))
                elif not data.get('review'):
                    raise ValueError('Legacy completion needs review evidence')
                else:
                    from review import evaluate
                    problems = evaluate(state, data)
                    if problems:
                        raise ValueError('Completion refused: ' + '; '.join(problems))
            state['stages'][data['id']] = data
        elif action == 'artifact':
            if data['id'] in state['artifacts']:
                raise ValueError('Artifact ID immutable; register a new revision ID')
            state['artifacts'][data['id']] = {**data, 'identity': identity(data['path'])}
        elif action == 'propose':
            required = ('id', 'failure_events', 'target', 'rationale', 'change', 'cases')
            if any(not data.get(k) for k in required):
                raise ValueError('Proposal needs failure events, target, exact change, rationale and cases')
            if data['id'] in state['proposals']:
                raise ValueError('Proposal ID already exists')
            known = {e['id'] for e in history(root)}
            if not set(data['failure_events']) <= known:
                raise ValueError('Unknown failure event')
            state['proposals'][data['id']] = {**data, 'status': 'proposed', 'target_identity': identity(data['target'])}
        elif action == 'decide':
            proposal = state['proposals'][data['id']]
            if proposal['status'] != 'proposed':
                raise ValueError('Decision already recorded; create a new proposal')
            if data['decision'] not in ('accepted', 'rejected') or not data.get('reviewer') or not data.get('reason'):
                raise ValueError('Decision needs reviewer and reason')
            if data['decision'] == 'accepted':
                evaluation = json.loads(Path(data['evaluation']).read_text(encoding='utf-8'))
                if evaluation['proposal_id'] != data['id'] or evaluation['target_identity'] != proposal['target_identity']:
                    raise ValueError('Evaluation belongs to another proposal/revision')
                if evaluation['change'] != proposal['change']:
                    raise ValueError('Evaluation tested a different proposed change')
                for saved in [evaluation['suite_identity']] + [e for r in evaluation['results'] for e in r['evidence']]:
                    if identity(saved['path']) != saved:
                        raise ValueError('Evaluation evidence changed')
                if identity(proposal['target']) != proposal['target_identity']:
                    raise ValueError('Target changed since proposal')
                passed = {x['id'] for x in evaluation['results'] if x['status'] == 'passed' and x.get('evidence') and x.get('reviewer') and x.get('criteria') and all(c == 'passed' for c in x['criteria'])}
                if not set(proposal['cases']) <= passed:
                    raise ValueError('Required quality cases have not passed review')
                data['evaluation_identity'] = identity(data['evaluation'])
            proposal.update({'status': data['decision'], 'decision': data})
        else:
            raise ValueError('Unknown action')
        append(root, action, data, state)
        return state


@audit_scope
def reconcile(root):
    state = snapshot(root)
    findings = []
    for key, artifact in state['artifacts'].items():
        try:
            valid = identity(artifact['path']) == artifact['identity']
        except OSError:
            valid = False
        if not valid:
            findings.append({'artifact': key, 'status': 'missing_or_changed'})
    for key, stage in state['stages'].items():
        if stage['status'] == 'running':
            findings.append({'stage': key, 'status': 'completion_unknown'})
        elif stage['status'] == 'completed' and any(x.get('artifact') in stage.get('artifacts', []) for x in findings):
            findings.append({'stage': key, 'status': 'completion_stale'})
        if stage.get('contract') or stage.get('status') == 'completed':
            from review import evaluate
            problems = evaluate(state, stage)
            if problems:
                findings.append({'stage': key, 'status': 'checks_outstanding', 'details': problems})
    from instruction_baseline import changes
    for key, baseline in state.get('baselines', {}).items():
        delta = changes(baseline)
        if delta:
            findings.append({'baseline': key, 'status': 'baseline_changed', 'details': delta})
    return {'state': state, 'findings': findings}


def compact_status(root, audit=False):
    result = reconcile(root) if audit else {'state': snapshot(root), 'findings': []}
    state = result['state']
    return {'id': state['id'], 'schema_version': state['schema_version'],
            'stages': {k: {'status': v['status'], 'contract': v.get('contract'), 'artifacts': v.get('artifacts', [])} for k, v in state['stages'].items()},
            'review_choices': state.get('review_choices', {}), 'acceptances': state.get('acceptances', []),
            'reviewer_findings': [{'id': r['id'], 'contract': r['contract'], 'check': r['check'], 'status': r['status']} for r in state.get('reviews', {}).values() if r['role'] == 'reviewer'],
            'archives': {k: {'kind': v['report']['kind'], 'copy_status': v['report'].get('copy_status'), 'restoration': v['report'].get('restoration', 'unverified')} for k, v in state.get('archives', {}).items()},
            'integrity': 'audited' if audit else 'not_checked',
            'deliveries': state.get('deliveries', []), 'closures': state.get('closures', []),
            'verification': 'see_findings' if audit else 'not_checked',
            'findings': result['findings'], 'next_action': state['next_action']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'plan', 'stage', 'artifact', 'propose', 'decide', 'event', 'status', 'reconcile',
                                         'baseline', 'baseline_assessment', 'preflight', 'contract', 'review', 'resolution', 'review_choice', 'acceptance', 'delivery', 'closure', 'archive'])
    parser.add_argument('job')
    parser.add_argument('--data', help='UTF-8 JSON file; never inline credentials')
    parser.add_argument('--full', action='store_true', help='Return full state instead of compact status')
    args = parser.parse_args()
    data = json.loads(Path(args.data).read_text(encoding='utf-8-sig')) if args.data else {}
    result = ((snapshot(args.job) if args.full else compact_status(args.job)) if args.action == 'status' else reconcile(args.job) if args.action == 'reconcile'
              else record(args.job, 'editorial', data) if args.action == 'event' else update(args.job, args.action, data))
    if args.action not in ('status', 'reconcile') and not args.full:
        result = {'action': args.action, 'id': data.get('id'), 'status': 'recorded'}
    print(json.dumps(result, indent=2))
