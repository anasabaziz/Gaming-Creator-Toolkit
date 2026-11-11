"""Explicit, private instruction snapshots. Never crawls the workspace."""
import argparse
import json
from pathlib import Path
import re
import uuid


def capture(job, data):
    from job_state import identity
    if not re.fullmatch(r'[A-Za-z0-9_-]+', data['id']):
        raise ValueError('Use a simple baseline ID')
    files = data.get('files', [])
    if not files or not data.get('requirements_source'):
        raise ValueError('Supply explicit instruction files and requirement source')
    sources = []
    for name in files:
        p = Path(name).resolve()
        if p.suffix.lower() not in ('.md', '.toml') or any(x in p.name.lower() for x in ('.env', 'secret', 'credential')):
            raise ValueError('Only explicitly selected instruction Markdown/TOML; no secrets')
        if p.name.lower() == 'config.toml' or p.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Do not snapshot runtime configuration or oversized files')
        sources.append((p, p.read_bytes()))
    folder = Path(job).resolve() / 'instructions' / (data['id'] + '-' + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True, exist_ok=False)
    entries = []
    import hashlib
    for n, (p, content) in enumerate(sources):
        dest = folder / (str(n) + p.suffix)
        with dest.open('xb') as f:
            f.write(content)
        source = {'path': str(p), 'sha256': hashlib.sha256(content).hexdigest(), 'size': len(content)}
        entries.append({'source': source, 'snapshot': identity(dest)})
    return {'id': data['id'], 'files': entries, 'requirements_source': data['requirements_source'],
            'toolkit': [identity(p) for p in Path(__file__).parent.glob('*.py') if not p.name.startswith('test_')] + [identity(Path(__file__).with_name('review_checks.json'))]}


def changes(baseline):
    from job_state import identity
    findings = []
    for entry in baseline['files']:
        for kind in ('snapshot', 'source'):
            saved = entry[kind]
            try:
                actual = identity(saved['path'])
            except OSError:
                actual = None
            if actual != saved:
                findings.append({'path': saved['path'], 'status': 'snapshot_changed' if kind == 'snapshot' else 'instruction_changed', 'current': actual})
    for saved in baseline.get('toolkit', []):
        try:
            actual = identity(saved['path'])
        except OSError:
            actual = None
        if actual != saved:
            findings.append({'path': saved['path'], 'status': 'toolkit_changed', 'current': actual})
    return findings


if __name__ == '__main__':
    from job_state import update
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('job'); ap.add_argument('data')
    a = ap.parse_args()
    data = json.loads(Path(a.data).read_text(encoding='utf-8-sig'))
    update(a.job, 'baseline', data)
    print(json.dumps({'baseline': data['id'], 'status': 'registered'}))
