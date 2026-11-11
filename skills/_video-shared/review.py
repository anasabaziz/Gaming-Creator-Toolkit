"""Evidence-bound producer checks; no model calls or reviewer spawning."""
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def intact(saved):
    from job_state import identity
    try:
        return identity(saved['path']) == saved
    except OSError:
        return False


def catalog():
    return json.loads(Path(__file__).with_name('review_checks.json').read_text(encoding='utf-8'))


def contract(state, data):
    """Freeze the applicable checklist. No silent removal of default checks."""
    spec = catalog()
    required = spec['deliverables'][data['kind']]
    checks = data['checks']
    ids = [c['id'] for c in checks]
    if len(ids) != len(set(ids)) or not set(required) <= set(ids):
        raise ValueError('Duplicate checks or missing deliverable checks')
    if not data.get('artifacts') or len(data['artifacts']) != len(set(data['artifacts'])):
        raise ValueError('Contract needs unique planned artifact IDs')
    if data['baseline'] not in state.get('baselines', {}):
        raise ValueError('Register the instruction baseline first')
    if data['preflight'] not in state.get('preflights', {}):
        raise ValueError('Register production capability preflight first')
    if not set(data.get('acceptance_checks', [])) <= set(ids):
        raise ValueError('Acceptance review conditions must reference contract check IDs')
    for c in checks:
        defaults = spec['checks'].get(c['id'], {})
        if not c.get('criterion') or not c.get('targets') or not set(c['targets']) <= set(data['artifacts']):
            raise ValueError('Every check needs a criterion and contract artifact targets')
        c['methods'] = defaults.get('methods', c.get('methods', []))
        c['capability'] = defaults.get('capability', c.get('capability'))
        c['allow_na'] = defaults.get('allow_na', False)
        if not c['methods'] or not c['capability']:
            raise ValueError('Every check needs methods and capability')
    coverage_problems = target_coverage(data)
    if coverage_problems:
        raise ValueError('; '.join(coverage_problems))
    return {**data, 'target_schema': 1, 'catalog_digest': digest(spec), 'requirements_digest': digest(state['requirements'])}


def target_coverage(c):
    """Explicit applicability for new video packages; no output may be forgotten."""
    problems = []
    targets = {a for check in c['checks'] for a in check['targets']}
    roles = c.get('artifact_roles', {})
    video = c['kind'] in ('highlight', 'trailer', 'vertical')
    if video and (set(roles) != set(c['artifacts']) or not {'video', 'project'} <= set(roles.values())):
        return ['Video contracts need artifact_roles for every artifact, including video and project']
    if set(roles) - set(c['artifacts']) or any(r not in ('video', 'project', 'dependency', 'report') for r in roles.values()):
        problems.append('Invalid artifact_roles')
    for a in c['artifacts']:
        if roles.get(a) in ('dependency', 'report'):
            continue
        if a not in targets:
            problems.append('Artifact has no check targets: ' + a)
        if video:
            required = (['coverage', 'technical', 'visual', 'framing' if c['kind'] == 'vertical' else 'playback', 'audio']
                        if roles.get(a) == 'video' else ['project', 'project_gui'])
            for key in required:
                if not any(x['id'] == key and a in x['targets'] for x in c['checks']):
                    problems.append(a + ': missing applicable ' + key + ' check')
    return problems


def seal_review(state, data):
    from job_state import identity
    c = state['contracts'][data['contract']]
    check = next((x for x in c['checks'] if x['id'] == data['check']), None)
    if check is None or data.get('status') not in ('passed', 'failed', 'unverified', 'not_applicable'):
        raise ValueError('Unknown check or invalid result')
    if data.get('role') not in ('producer', 'reviewer', 'human_verifier') or not data.get('reviewer'):
        raise ValueError('Identify producer or requested reviewer')
    if data['role'] == 'producer' and data['status'] == 'passed':
        pf = state['preflights'][c['preflight']]
        cap = pf['report']['capabilities'].get(check['capability'], {})
        if not intact(pf['identity']) or cap.get('status') != 'available' or not cap.get('evidence') or not all(intact(e) for e in cap['evidence']):
            raise ValueError('Producer capability is unavailable or stale')
    if data['role'] == 'human_verifier':
        human_methods = {'editorial_inspection', 'visual_inspection', 'metadata_inspection',
                         'package_inspection', 'continuous_playback', 'full_interval_inspection',
                         'listening', 'gui_open_and_seek'}
        if (data.get('method') not in human_methods or
                any(m in ('automated_validation', 'project_comparison') for m in check['methods'])):
            raise ValueError('Human handoff cannot replace automated validation')
        if not data.get('source') or data.get('reviewer_type') != 'human':
            raise ValueError('Human verification needs the actual human report and identity')
    if data['status'] == 'passed' and (check['id'] in ('playback', 'framing', 'audio') or data.get('method') in ('continuous_playback', 'full_interval_inspection', 'listening')):
        if data.get('coverage_scope') != 'entire_artifact':
            raise ValueError('Full playback/listening checks require entire_artifact coverage; samples are insufficient')
    if data['role'] == 'reviewer':
        choice = state.get('review_choices', {}).get(c['stage'], {})
        if choice.get('choice') not in ('subagent_requested', 'human_sufficient') or choice.get('contract') != data['contract']:
            raise ValueError('Separate review must be requested for this revision')
        expected = 'subagent' if choice['choice'] == 'subagent_requested' else 'human'
        if data.get('reviewer_type') != expected:
            raise ValueError('Reviewer type must match the user choice')
        pf = state.get('preflights', {}).get(data.get('preflight'))
        if not pf or not intact(pf['identity']):
            raise ValueError('Requested reviewer needs a current capability report')
        cap = pf['report']['capabilities'].get(check['capability'], {})
        if data['status'] == 'passed' and (cap.get('status') != 'available' or not cap.get('evidence') or not all(intact(e) for e in cap['evidence'])):
            raise ValueError('Reviewer capability is unavailable or stale')
    if data.get('method') not in check['methods'] or not data.get('coverage') or not data.get('notes'):
        raise ValueError('Review needs an allowed method, coverage and notes')
    if data['status'] == 'not_applicable' and (not check['allow_na'] or not data.get('reason')):
        raise ValueError('Inapplicable check needs permitted exemption and reason')
    evidence = [identity(p) for p in data.get('evidence', [])]
    if data['status'] in ('passed', 'not_applicable') and not evidence:
        raise ValueError('Passing or exemption claims need preserved evidence')
    if data['role'] == 'reviewer':
        evidence.extend([pf['identity'], *cap.get('evidence', [])])
    targets = {k: state['artifacts'][k]['identity'] for k in check['targets']}
    if not all(intact(v) for v in targets.values()):
        raise ValueError('Review targets changed or missing')
    if check['id'] in ('technical', 'project') and data['status'] == 'passed':
        field = 'integrity' if check['id'] == 'technical' else 'project_agreement'
        paths = data.get('validations') or ([data['validation']] if data.get('validation') else [])
        if not isinstance(paths, list) or not paths:
            raise ValueError('Automated media check needs validation.json paths')
        covered = set()
        for path in paths:
            validation_path = Path(path).resolve()
            report = json.loads(validation_path.read_text(encoding='utf-8-sig'))
            if report.get(field, {}).get('status') != 'passed':
                raise ValueError('Automated validation has not passed')
            dependencies = report.get('dependencies', {})
            saved = [dependencies.get('export'), dependencies.get('project'), *dependencies.get('media', [])]
            if not saved[0] or not saved[1]:
                raise ValueError('Validation dependencies missing')
            for dep in saved:
                actual = identity(dep['path'])
                if any(actual[k] != dep.get(k) for k in ('path', 'size', 'sha256')):
                    raise ValueError('Automated validation dependencies changed')
            # Only the export/project itself proves the corresponding target check.
            expected = saved[0 if check['id'] == 'technical' else 1]
            matched = {k for k, v in targets.items() if v['path'] == expected['path'] and v['sha256'] == expected['sha256']}
            if not matched:
                raise ValueError('Validation belongs to different review targets')
            covered.update(matched)
            evidence.append(identity(validation_path))
            evidence.extend(identity(dep['path']) for dep in saved)
            for dep in report.get(field, {}).get('evidence', []):
                actual = identity(dep['path'])
                if actual['sha256'] != dep.get('sha256'):
                    raise ValueError('Project comparison samples changed')
                evidence.append(actual)
        if covered != set(targets):
            raise ValueError('Validation reports do not cover all review targets')
    previous = data.get('supersedes')
    matches = [r for r in state.get('reviews', {}).values() if r['contract'] == data['contract'] and r['check'] == data['check'] and r['role'] == data['role']]
    if matches and previous != matches[-1]['id']:
        raise ValueError('Explicitly supersede the latest review of this check and role')
    if not matches and previous:
        raise ValueError('No prior matching review to supersede')
    return {**data, 'targets': targets, 'evidence': evidence, 'contract_digest': digest(c)}


def acceptance_problems(state, stage):
    issues = evaluate(state, stage)
    c = state['contracts'][stage['contract']]
    for key in c.get('acceptance_checks', []):
        rows = [r for r in state.get('reviews', {}).values() if r['role'] == 'reviewer' and r['contract'] == stage['contract'] and r['check'] == key]
        if not rows or rows[-1]['status'] not in ('passed', 'not_applicable'):
            issues.append(key + ': requested external review required for acceptance')
        elif not all(intact(e) for e in [*rows[-1]['targets'].values(), *rows[-1]['evidence']]):
            issues.append(key + ': external review evidence stale')
    return issues


def latest_reviews(state, cid, check):
    heads = {}
    for r in state.get('reviews', {}).values():
        if r['contract'] == cid and r['check'] == check:
            heads[r['role']] = r
    return heads


def seal_resolution(state, data):
    """An evidence-bound disposition, not an invented review pass."""
    from job_state import identity
    c = state['contracts'][data['contract']]
    heads = latest_reviews(state, c['id'], data['check'])
    if not heads or set(data.get('reviews', [])) != {r['id'] for r in heads.values()}:
        raise ValueError('Disposition must reference all current role findings for this check')
    if data.get('decision') not in ('corrected', 'rebutted', 'out_of_scope', 'unresolved') or not data.get('reason') or not data.get('source'):
        raise ValueError('Disposition needs decision, evidence rationale and source')
    evidence = [identity(p) for p in data.get('evidence', [])]
    if not evidence:
        raise ValueError('Disposition needs preserved evidence')
    selected = heads.get(state['reviews'].get(data.get('selected_review'), {}).get('role'))
    if data['decision'] != 'unresolved' and (not selected or selected['id'] != data.get('selected_review') or selected['role'] not in ('producer', 'human_verifier') or selected['status'] not in ('passed', 'not_applicable')):
        raise ValueError('Resolved findings need a current passing production/human check')
    return {**data, 'evidence': evidence, 'contract_digest': digest(c),
            'reviews_digest': digest(sorted(heads.values(), key=lambda r: r['id']))}


def check_result(state, c, check):
    """Keep role heads independent; an unverified capability can use a human handoff."""
    heads = latest_reviews(state, c['id'], check['id'])
    production = [r for role, r in heads.items() if role in ('producer', 'human_verifier')]
    passing = [r for r in production if r['status'] in ('passed', 'not_applicable')]
    adverse = [r for r in heads.values() if r['status'] == 'failed' or
               (r['role'] == 'human_verifier' and r['status'] == 'unverified' and r.get('supersedes'))]
    resolutions = [r for r in state.get('resolutions', {}).values() if r['contract'] == c['id'] and r['check'] == check['id']]
    if adverse or resolutions:
        current = [r for r in resolutions if r['contract_digest'] == digest(c) and
                   r['reviews_digest'] == digest(sorted(heads.values(), key=lambda r: r['id']))]
        if current:
            resolution = current[-1]
            if resolution['decision'] != 'unresolved' and all(intact(e) for e in resolution['evidence']):
                selected = next((r for r in passing if r['id'] == resolution.get('selected_review')), None)
                if selected:
                    return selected, []
            return None, [check['id'] + ': unresolved or stale finding disposition']
        if adverse:
            return None, [check['id'] + ': ' + ('failed' if any(r['status'] == 'failed' for r in adverse) else 'unverified') + '; explicit finding disposition or superseding check required']
    if passing:
        # Prefer human evidence consistently; never decide across roles by insertion order.
        return next((r for r in passing if r['role'] == 'human_verifier'), passing[0]), []
    return None, [check['id'] + ': ' + ('producer check missing' if not production else 'unverified')]


def dependency_problems(state, stage, trail=()):
    problems = []
    trail = (*trail, stage['id'])
    for dep in stage.get('depends_on', []):
        if dep in trail:
            problems.append('Dependency cycle: ' + ' -> '.join((*trail, dep)))
            continue
        dependency = state.get('stages', {}).get(dep)
        if not dependency or dependency.get('status') != 'completed':
            problems.append('Dependency not completed: ' + dep)
        if dependency:
            nested = evaluate(state, dependency, trail)
            if nested:
                problems.append('Dependency production checks stale: ' + dep + ': ' + '; '.join(nested))
    return problems


def evaluate(state, stage, trail=()):
    from instruction_baseline import changes
    problems = dependency_problems(state, stage, trail)
    if any(x.get('blocking') and not x.get('resolved') and x.get('stage') in (None, stage['id']) for x in state.get('issues', [])):
        problems.append('Resolve blocking stage issues first')
    for key in stage.get('artifacts', []):
        artifact = state.get('artifacts', {}).get(key)
        if not artifact or not intact(artifact['identity']):
            problems.append('Artifact changed or missing: ' + key)
    cid = stage.get('contract')
    c = state.get('contracts', {}).get(cid)
    if not c:
        if state.get('schema_version', 2) == 1 and stage.get('review') and stage.get('artifacts'):
            return problems
        return problems + ['Structured review contract missing']
    if c['stage'] != stage['id'] or set(stage.get('artifacts', [])) != set(c['artifacts']):
        problems.append('Stage artifacts or stage ID do not match contract')
    if c['requirements_digest'] != digest(state['requirements']):
        problems.append('Requirements changed; create a revised contract')
    if c.get('target_schema'):
        problems.extend(target_coverage(c))
    baseline = state['baselines'][c['baseline']]
    delta = changes(baseline)
    if delta:
        assessments = state.get('baseline_assessments', {}).values()
        if any(x['status'] == 'snapshot_changed' for x in delta) or not any(a['baseline'] == c['baseline'] and a['changes_digest'] == digest(delta) for a in assessments):
            problems.append('Instruction baseline changed; assess changes or adopt new baseline')
    preflight = state['preflights'][c['preflight']]
    if not intact(preflight['identity']):
        problems.append('Preflight evidence changed')
    caps = preflight['report']['capabilities']
    for check in c['checks']:
        r, issues = check_result(state, c, check)
        problems.extend(issues)
        if r is None:
            continue
        if r['status'] not in ('passed', 'not_applicable'):
            problems.append(check['id'] + ': ' + r['status'])
        if r['contract_digest'] != digest(c) or not all(intact(v) for v in [*r['targets'].values(), *r['evidence']]):
            problems.append(check['id'] + ': stale review evidence')
        if r['status'] == 'passed' and r['role'] != 'human_verifier':
            cap = caps.get(check['capability'], {})
            if cap.get('status') != 'available' or not all(intact(v) for v in cap.get('evidence', [])):
                problems.append(check['id'] + ': review capability unavailable or stale')
    return problems


def handoff(state, stage):
    """Checklist only: never creates a human report or a pass."""
    c = state['contracts'][stage['contract']]
    return {'contract': c['id'], 'stage': stage['id'],
            'targets': {k: state['artifacts'][k]['identity'] for k in c['artifacts']},
            'outstanding': evaluate(state, stage),
            'checks': [{'id': x['id'], 'criterion': x['criterion'], 'methods': x['methods'],
                        'targets': x['targets']} for x in c['checks']],
            'instructions': 'Report only checks actually performed, method, whole-artifact or partial coverage, observations and exact revision. Acceptance alone is not verification.'}


def artifact_status(state, path):
    resolved = str(Path(path).resolve())
    ids = {k for k, a in state['artifacts'].items() if a['identity']['path'] == resolved}
    rows = []
    for stage in state['stages'].values():
        if ids.intersection(stage.get('artifacts', [])):
            issues = evaluate(state, stage) if stage.get('contract') else ['Legacy review; structured checks unavailable']
            rows.append({'stage': stage['id'], 'status': stage['status'], 'outstanding': issues})
    return rows
