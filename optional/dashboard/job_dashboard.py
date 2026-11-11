"""Portable dashboard sync; openpyxl builds the optional workbook. No AI calls or media deletion."""
import argparse
import copy
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'skills/_video-shared'))
import job_state
import review

PASS = 'Passed - all listed checks performed'
HISTORICAL = 'Previously verified (journal)'
MANUAL = {'human': ['Pending', PASS, 'Changes requested'],
          'acceptance': ['Pending', 'Accepted', 'Changes requested'],
          'disposal': ['Keep files', 'Intentionally removed']}
METHODS = {'editorial_inspection', 'visual_inspection', 'continuous_playback',
           'full_interval_inspection', 'listening', 'gui_open_and_seek',
           'metadata_inspection', 'package_inspection'}
HEADERS = ['Job', 'Skill', 'Deliverable revision', 'Production recorded', 'Human review',
           'Acceptance', 'File disposition', 'Feedback', 'Human checklist',
           'Other outstanding conditions', 'Files at last refresh', 'Sync result',
           'Current revision', 'Output folder', 'Journal', 'Record ID']
EDIT = {4: 'human', 5: 'acceptance', 6: 'disposal', 7: 'feedback'}
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(x):
    return review.digest(x)


def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(temp, path)


def human_checks(contract):
    return [c for c in contract.get('checks', [])
            if any(m in METHODS for m in c['methods'])
            and not any(m in ('automated_validation', 'project_comparison') for m in c['methods'])]


def checklist(contract):
    # All human checks, including already passed ones, make the single-cell attestation explicit.
    return '\n'.join(f"{i}. {c['criterion']} [Method: {next(m for m in c['methods'] if m in METHODS)}; "
                     f"entire targets: {', '.join(c['targets'])}]"
                     for i, c in enumerate(human_checks(contract), 1)) or 'No structured human checklist available.'


def recorded_gaps(state, contract):
    stage = state.get('stages', {}).get(contract.get('stage'))
    if not stage:
        return 'Structured stage unavailable'
    gaps = review.evaluate(state, stage)
    return '; '.join(gaps) or 'Current production conditions satisfied at refresh.'


def historical_human_verification(state, contract):
    """Import actual human verification history, never infer it from acceptance."""
    checks = human_checks(contract)
    human_seen = False
    for c in checks:
        selected, problems = review.check_result(state, contract, c)
        if problems or not selected:
            return False
        human_seen |= selected['role'] == 'human_verifier'
    return bool(checks) and human_seen


@job_state.audit_scope
def collect(root, records, config):
    excluded = {str((root / p).resolve()) for p in config.get('excluded_journals', [])}
    for folder in config['scan_folders']:
        for path in sorted((root / folder).rglob('job.json')):
            if str(path.parent.resolve()) in excluded:
                continue
            # Never fall back to a potentially stale summary when the journal is damaged.
            state = job_state.snapshot(path.parent)
            job_id = state['id']
            for r in records.values():
                if r['job_id'] == job_id:
                    r['current'] = False
            stages = state.get('stages', {})
            latest = {}
            for sid in stages:
                family = re.sub(r'-r\d+$', '', sid)
                latest[family] = sid
            for sid, stage in stages.items():
                cid = stage.get('contract')
                contract = state.get('contracts', {}).get(cid, {})
                targets = {a: state['artifacts'][a]['identity'] for a in stage.get('artifacts', [])
                           if a in state['artifacts']}
                binding = {'job': job_id, 'stage': sid, 'contract': contract,
                           'targets': targets, 'requirements': state.get('requirements', [])}
                key = digest(binding)
                name = path.parent.parent.name
                acceptance = [a for a in state.get('acceptances', [])
                              if a['stage'] == sid and a.get('contract') == cid]
                accepted = {'accepted': 'Accepted', 'changes_requested': 'Changes requested'}
                if key not in records:
                    records[key] = {'id': key, 'job_id': job_id, 'job': name, 'stage': sid,
                                    'contract_id': cid, 'binding': binding,
                                    'human': 'Pending', 'acceptance': accepted.get(acceptance[-1]['decision'], 'Pending') if acceptance else 'Pending',
                                    'disposal': 'Keep files', 'feedback': '', 'history': [],
                                    'sync': 'Imported history; no new human attestation', 'created': now()}
                r = records[key]
                r.update(journal=str(path.parent.resolve()), snapshot=state,
                         production=stage['status'], skill=contract.get('kind', 'Legacy'),
                         current=latest[re.sub(r'-r\d+$', '', sid)] == sid,
                         checklist=checklist(contract), other=recorded_gaps(state, contract))
                if not r.get('history') and acceptance:
                    r['acceptance'] = accepted[acceptance[-1]['decision']]
                if not r.get('history') and historical_human_verification(state, contract):
                    r['human'] = HISTORICAL
    for r in records.values():
        targets = r['binding']['targets']
        existing = sum(Path(t['path']).is_file() for t in targets.values())
        r['availability'] = ('No registered outputs' if not targets else
                             'Present (not hash checked)' if existing == len(targets) else
                             f'Files missing ({len(targets)-existing}/{len(targets)})')
        if not Path(r['journal']).exists():
            r['availability'] += '; journal removed'


def row_values(r):
    targets = r['binding']['targets']
    try:
        folder = os.path.commonpath([str(Path(t['path']).parent) for t in targets.values()]) if targets else ''
    except ValueError:  # Media may span several Windows drives.
        folder = str(Path(next(iter(targets.values()))['path']).parent)
    return [r['job'], r['skill'], r['stage'], r['production'], r['human'], r['acceptance'],
            r['disposal'], r['feedback'], r['checklist'], r['other'], r['availability'],
            r['sync'], 'Yes' if r['current'] else 'Historical', folder, r['journal'], r['id']]


def job_metadata(records, config):
    """Retain grouping/date metadata even after the journal is removed."""
    jobs = {}
    for r in records.values():
        meta = dict(r.get('job_metadata', {}))
        override = config.get('job_metadata', {}).get(r['job_id'], {})
        if not meta.get('game'):
            meta['game'] = next((title for fragment, title in config.get('game_names', {}).items()
                                 if fragment in r['job']), 'Unspecified game')
        if not meta.get('request_date'):
            match = re.search(r'\d{4}-\d{2}-\d{2}', r['job'])
            if match:
                meta.update(request_date=match[0], date_source='Dated job record')
            elif Path(r['journal'], 'events.jsonl').exists():
                first = job_state.history(r['journal'])[0]['time']
                meta.update(request_date=datetime.fromtimestamp(first, timezone.utc).date().isoformat(),
                            date_source='Journal start fallback (UTC)')
            else:
                meta.update(request_date='', date_source='Request date unavailable')
        meta.update(override)
        if meta.get('request_date'):
            datetime.strptime(meta['request_date'], '%Y-%m-%d')
        r['job_metadata'] = meta
        jobs[r['job_id']] = {'id': r['job_id'], 'job': r['job'], **meta}
    return sorted(jobs.values(), key=lambda j: (j['game'].casefold(), j['request_date'] or '9999', j['job']))


def workbook_rows(path):
    """Read literal saved cells, including sorted rows, without an Excel dependency."""
    with zipfile.ZipFile(path) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(s.itertext()) for s in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        book = ET.fromstring(z.read('xl/workbook.xml'))
        sheet = next(s for s in book.find('s:sheets', NS) if s.attrib['name'] == 'Deliverables')
        rid = sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target = next(r.attrib['Target'] for r in rels if r.attrib['Id'] == rid)
        target = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        rows = []
        for row in ET.fromstring(z.read(target)).findall('.//s:sheetData/s:row', NS):
            vals = [''] * len(HEADERS)
            for c in row:
                col = re.match('[A-Z]+', c.attrib['r'])[0]
                n = 0
                for ch in col:
                    n = n * 26 + ord(ch) - 64
                if n > len(vals):
                    continue
                formula = c.find('s:f', NS)
                if formula is not None:
                    match = re.fullmatch(r'HYPERLINK\("((?:[^"]|"")*)","(?:[^"]|"")*"\)', formula.text or '', re.I)
                    if n not in (14, 15) or not match:
                        raise ValueError('Only generated folder links may be formulas in Deliverables')
                    vals[n-1] = match[1].replace('""', '"')
                    continue
                v = c.find('s:v', NS)
                val = v.text if v is not None else ''
                if c.attrib.get('t') == 's':
                    val = strings[int(val)]
                elif c.attrib.get('t') == 'inlineStr':
                    inline = c.find('s:is', NS)
                    val = ''.join(inline.itertext()) if inline is not None else ''
                vals[n-1] = val or ''
            rows.append(vals)
        return rows


def import_edits(workbook, records, tracking):
    if not workbook.exists():
        return
    rows = workbook_rows(workbook)
    header = next((i for i, row in enumerate(rows) if row == HEADERS), None)
    if header is None:
        raise ValueError('Deliverables headers changed. Restore the original headers before syncing.')
    seen, changes = set(), []
    for row in rows[header+1:]:
        if not any(row):
            continue
        key = row[-1]
        if key in seen or key not in records:
            raise ValueError('Duplicate or unknown record ID. No edits imported.')
        seen.add(key)
        r = records[key]
        expected = r.get('exported_row', row_values(r))
        if any(row[i] != str(expected[i] or '') for i in range(len(HEADERS)) if i not in EDIT):
            raise ValueError('Generated cells changed for ' + r['stage'] + '. Edit only yellow cells E:H.')
        values = {field: row[i] for i, field in EDIT.items()}
        for field, allowed in MANUAL.items():
            historical_unchanged = field == 'human' and values[field] == r[field] == HISTORICAL
            if values[field] not in allowed and not historical_unchanged:
                raise ValueError('Invalid ' + field + ' value: ' + values[field])
        if any(values[k] != r[k] for k in values):
            changes.append((r, values))
    if seen != set(records):
        raise ValueError('Rows removed from workbook. Restore them; use File disposition for disposal.')
    # Validate every row before persisting any edit. Preserve the actual saved workbook as evidence.
    if changes:
        stamp = uuid.uuid4().hex
        evidence = tracking / 'records' / 'attestations' / (stamp + '.xlsx')
        evidence.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(workbook, evidence)
        for r, values in changes:
            event = {'id': uuid.uuid4().hex, 'record': r['id'], 'recorded_at': now(),
                     'reviewer': 'Local workbook owner', 'before': {k: r[k] for k in values},
                     'after': values, 'binding': r['binding'], 'checklist': r['checklist'],
                     'workbook': job_state.identity(evidence), 'journal_synced': False}
            r.update(values)
            r['history'].append(event)
            write(tracking / 'records' / 'attestations' / (event['id'] + '.json'), event)


def sync_outcome(status, message):
    return {'status': status, 'message': message}


def sync_event(r, event, tracking):
    journal = Path(r['journal'])
    if not (journal / 'events.jsonl').exists():
        return sync_outcome('historical_only', 'Recorded permanently; source journal unavailable')
    state = job_state.snapshot(journal)
    stage = state['stages'].get(r['stage'], {})
    binding = r['binding']
    if (stage.get('contract') != r['contract_id'] or
        state.get('contracts', {}).get(r['contract_id'], {}) != binding['contract'] or
        state.get('requirements', []) != binding['requirements'] or
        {k: state['artifacts'][k]['identity'] for k in stage.get('artifacts', [])} != binding['targets']):
        return sync_outcome('historical_only', 'Recorded permanently; source revision changed (no checks applied)')
    if not all(review.intact(t) for t in binding['targets'].values()):
        return sync_outcome('historical_only', 'Recorded permanently; output files missing or changed (no new checks applied)')
    evidence = tracking / 'records' / 'attestations' / (event['id'] + '.json')
    if not review.intact(event['workbook']):
        raise ValueError('Saved human attestation workbook changed or missing')
    saved_report = read(evidence, {})
    if any(saved_report.get(k) != event.get(k) for k in ('id', 'binding', 'checklist', 'before', 'after', 'workbook')):
        raise ValueError('Saved human attestation report changed or missing')
    source = 'Saved dashboard attestation ' + event['id']
    before, after = event['before'], event['after']
    checks = human_checks(binding['contract'])
    if before['human'] != after['human']:
        for c in checks:
            ident = 'dashboard-' + event['id'] + '-' + c['id']
            state = job_state.snapshot(journal)
            if ident in state.get('reviews', {}):
                continue
            prior = [v for v in state.get('reviews', {}).values()
                     if v['contract'] == r['contract_id'] and v['check'] == c['id'] and v['role'] == 'human_verifier']
            if after['human'] != PASS and not prior:
                continue  # A request for changes does not invent failures for unexamined checks.
            payload = {'id': ident, 'contract': r['contract_id'], 'check': c['id'],
                       'role': 'human_verifier', 'reviewer_type': 'human', 'reviewer': event['reviewer'],
                       'status': 'passed' if after['human'] == PASS else 'unverified',
                       'method': next(m for m in c['methods'] if m in METHODS),
                       'coverage_scope': 'entire_artifact',
                       'coverage': 'Owner attests entire targets: ' + ', '.join(c['targets']),
                       'notes': ('Owner selected: ' + after['human'] + '. Checklist criterion: ' + c['criterion'] +
                                 '. Feedback: ' + (after['feedback'] or '(none)')),
                       'source': source, 'evidence': [str(evidence), event['workbook']['path']]}
            if prior:
                payload['supersedes'] = prior[-1]['id']
            job_state.update(journal, 'review', payload)
        state = job_state.snapshot(journal)
        problems = review.evaluate(state, stage)
        if after['human'] == PASS and not problems:
            job_state.update(journal, 'stage', {'id': r['stage'], 'status': 'completed'})
        elif after['human'] != PASS and stage.get('status') == 'completed':
            job_state.update(journal, 'stage', {'id': r['stage'], 'status': 'awaiting_review'})
    if before['acceptance'] != after['acceptance']:
        state = job_state.snapshot(journal)
        if not any(e['data'].get('source') == source and e['kind'] == 'dashboard_acceptance'
                   for e in job_state.history(journal)):
            job_state.record(journal, 'dashboard_acceptance', {'source': source,
                             'decision': after['acceptance'], 'contract': r['contract_id'],
                             'stage': r['stage'], 'evidence': str(evidence)})
        if after['acceptance'] != 'Pending' and not any(a.get('source') == source for a in state.get('acceptances', [])):
            if not any(d['contract'] == r['contract_id'] for d in state.get('deliveries', [])) and stage.get('status') != 'completed':
                return sync_outcome('waiting_for_delivery', 'Review saved; acceptance retained in dashboard (delivery not registered)')
            job_state.update(journal, 'acceptance', {'stage': r['stage'], 'contract': r['contract_id'],
                'decision': 'accepted' if after['acceptance'] == 'Accepted' else 'changes_requested',
                'acceptor': event['reviewer'], 'source': source})
    state = job_state.snapshot(journal)
    problems = review.evaluate(state, state['stages'][r['stage']])
    if problems:
        return sync_outcome('applied', 'Decision synced; production conditions: ' + '; '.join(problems))
    return sync_outcome('applied', 'Synced to journal; production checks satisfied')


def sync_condition_key(r, event, tracking):
    """Metadata only for retry scheduling; actual registration still verifies hashes."""
    journal = Path(r['journal'])
    try:
        state = job_state.snapshot(journal)
    except (ValueError, OSError):
        state = None
    paths = {str(journal / 'events.jsonl'), event['workbook']['path'],
             str(tracking / 'records/attestations' / (event['id'] + '.json'))}
    def references(value):
        if isinstance(value, dict):
            if isinstance(value.get('path'), str):
                paths.add(value['path'])
            for v in value.values():
                references(v)
        elif isinstance(value, list):
            for v in value:
                references(v)
    references(state)
    metadata = {}
    for path in sorted(paths):
        try:
            s = Path(path).stat()
            metadata[path] = [s.st_size, s.st_mtime_ns, s.st_ctime_ns]
        except OSError:
            metadata[path] = None
    return digest({'state': state, 'metadata': metadata})


def sync_pending(records, tracking):
    for r in records.values():
        for event in r['history']:
            # Repair receipts written by older helpers before deferred outcomes existed.
            if event.get('journal_synced') and not event.get('sync_status') and 'delivery not registered' in str(event.get('result', '')):
                event['journal_synced'] = False
            if event.get('journal_synced'):
                continue
            condition = sync_condition_key(r, event, tracking)
            if event.get('retry_condition') == condition:
                r['sync'] = event.get('result', 'Sync pending; waiting for changed conditions')
                break
            try:
                result = sync_event(r, event, tracking)
                # Missing files/revision are retained historical attestations, never fresh verification.
                event['journal_synced'] = result['status'] in ('applied', 'historical_only')
                event['sync_status'] = result['status']
                event['result'] = result['message']
                r['sync'] = result['message']
                if not event['journal_synced']:
                    event['retry_condition'] = sync_condition_key(r, event, tracking)
                    break
            except (ValueError, OSError, KeyError) as exc:
                r['sync'] = 'Sync pending: ' + str(exc)
                event['sync_status'] = 'waiting_for_change'
                event['result'] = r['sync']
                event['retry_condition'] = sync_condition_key(r, event, tracking)
                break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--no-build', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    os.chdir(root)
    tracking = root / 'tracking'
    tracking.mkdir(exist_ok=True)
    config = read(tracking / 'config.json', {'scan_folders': ['jobs']})
    workbook = tracking / 'Creator Job Dashboard.xlsx'
    index = tracking / 'records' / 'index.json'
    # Do not overwrite a workbook being edited. Atomic replacement remains a second guard.
    if (workbook.with_name('~$' + workbook.name).exists() or
            workbook.with_name('.~lock.' + workbook.name + '#').exists()):
        raise ValueError('Save and close the dashboard in your spreadsheet app before refreshing.')
    lock = tracking / '.dashboard.lock'
    with lock.open('x') as f:
        f.write(str(os.getpid()))
    try:
        records = read(index, {})
        import_edits(workbook, records, tracking)
        write(index, records)  # Persist manual changes before any journal mutation.
        sync_pending(records, tracking)
        write(index, records)
        collect(root, records, config)
        jobs = job_metadata(records, config)
        positions = {j['id']: i for i, j in enumerate(jobs)}
        ordered = sorted(records.values(), key=lambda r: (positions[r['job_id']], r['stage'], r['id']))
        # Keep metadata for every previously seen revision, even after deletion.
        write(index, records)
        data = {'refreshed': now(), 'headers': HEADERS,
                'rows': [row_values(r) for r in ordered],
                'jobs': jobs,
                'manual': MANUAL}
        write(tracking / 'records' / 'workbook-data.json', data)
        if not args.no_build:
            from build_workbook import build
            build(data, workbook)
            for r in records.values():
                r['exported_row'] = row_values(r)
            write(index, records)
        print(f'Tracked {len(data["jobs"])} jobs / {len(records)} revision packages. Workbook: {workbook}')
    finally:
        lock.unlink()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Dashboard refresh stopped: ' + str(exc), file=sys.stderr)
        sys.exit(1)
