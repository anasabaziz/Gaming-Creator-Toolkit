"""Inventory and verify an explicit archive. Never copies, deletes or uploads."""
import argparse
import hashlib
import json
from pathlib import Path


def inventory(root, extra=(), job_record=None):
    from cleanup_audit import audit
    from job_state import identity, snapshot
    root = Path(root).resolve()
    scan = audit(root)
    paths = {p.resolve() for p in root.rglob('*') if p.is_file() and p.name != '.env' and not p.name.startswith('.env.')}
    issues = list(scan['errors'])
    for project in scan['projects']:
        for ref in project['references']:
            if ref.get('path'):
                paths.add(Path(ref['path']).resolve())
            else:
                issues.append({'project': project['project'], 'unresolved': ref.get('raw')})
    for p in root.rglob('*manifest.json'):
        try:
            manifest = json.loads(p.read_text(encoding='utf-8-sig'))
            source = manifest.get('source')
            if isinstance(source, str):
                paths.add((p.parent / source).resolve())
            for s in manifest.get('sources', {}).values():
                source = s.get('path') or s.get('source')
                if isinstance(source, str):
                    paths.add((p.parent / source).resolve())
            def assets(value):
                if isinstance(value, dict):
                    for key, child in value.items():
                        if key in ('path', 'fontfile', 'font') and isinstance(child, str):
                            paths.add((p.parent / child).resolve())
                        else:
                            assets(child)
                elif isinstance(value, list):
                    for child in value:
                        assets(child)
            assets(manifest.get('outputs', []))
        except (ValueError, OSError, AttributeError) as e:
            issues.append({'manifest': str(p), 'error': type(e).__name__})
    if job_record:
        state = snapshot(job_record)
        def visit(value):
            if isinstance(value, dict):
                if 'sha256' in value and 'path' in value:
                    paths.add(Path(value['path']).resolve())
                for v in value.values():
                    visit(v)
            elif isinstance(value, list):
                for v in value:
                    visit(v)
        visit(state)
        paths.update(Path(job_record).resolve() / n for n in ('job.json', 'events.jsonl'))
    paths.update(Path(p).resolve() for p in extra)
    entries = []
    for p in sorted(paths):
        if p.name == '.env' or p.name.startswith('.env.'):
            issues.append({'path': str(p), 'error': 'credential_file_excluded'})
            continue
        try:
            saved = identity(p)
        except OSError:
            issues.append({'path': str(p), 'error': 'missing_or_unreadable'})
            continue
        try:
            relative = p.relative_to(root).as_posix()
        except ValueError:
            relative = 'external/' + hashlib.sha256(str(p).encode()).hexdigest()[:16] + '/' + p.name
        entries.append({'source': saved, 'destination': relative})
    return {'schema_version': 1, 'kind': 'archive_inventory', 'root': str(root), 'entries': entries, 'issues': issues,
            'limitations': 'Explicit job-tree/MLT/manifest/registered dependencies only. External references may require relinking. Add artwork/fonts/music/profiles/reference library explicitly if outside these records. Review inventory before copying; no copy performed.'}


def verify(manifest, destination):
    from job_state import identity
    from cleanup_audit import audit
    dest = Path(destination).resolve()
    findings = list(manifest['issues'])
    for entry in manifest['entries']:
        path = (dest / entry['destination']).resolve()
        if not path.is_relative_to(dest):
            raise ValueError('Archive destination escapes selected root')
        try:
            got = identity(path)
        except OSError:
            findings.append({'path': str(path), 'error': 'missing'})
            continue
        if any(got[k] != entry['source'][k] for k in ('sha256', 'size')):
            findings.append({'path': str(path), 'error': 'changed'})
    dependencies = []
    scan = audit(dest)
    dependencies.extend(scan['errors'])
    for project in scan['projects']:
        for ref in project['references']:
            if not ref.get('exists') or not ref.get('path') or not Path(ref['path']).resolve().is_relative_to(dest):
                dependencies.append({'project': project['project'], 'reference': ref, 'error': 'not_self_contained'})
    return {'schema_version': 1, 'kind': 'archive_verification', 'destination': str(dest),
            'inventory_digest': hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
            'copy_status': 'passed' if not findings else 'failed', 'findings': findings,
            'dependency_status': 'passed' if not dependencies else 'unverified', 'dependencies': dependencies,
            'restoration': 'unverified', 'independent_backup': 'unverified',
            'limitations': 'Hash agreement is not playback/GUI restoration or proof of independent storage. Record actual restore checks separately.'}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    make = sub.add_parser('inventory'); make.add_argument('root'); make.add_argument('--job-record'); make.add_argument('--extra', action='append', default=[]); make.add_argument('--out', required=True)
    check = sub.add_parser('verify'); check.add_argument('inventory'); check.add_argument('destination'); check.add_argument('--out', required=True)
    a = ap.parse_args()
    result = inventory(a.root, a.extra, a.job_record) if a.command == 'inventory' else verify(json.loads(Path(a.inventory).read_text(encoding='utf-8-sig')), a.destination)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    print(json.dumps({'report': str(out.resolve()), 'kind': result['kind'], 'copy_status': result.get('copy_status'), 'issues': len(result.get('issues', result.get('findings', []))), 'restoration': 'unverified'}))
