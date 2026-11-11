"""Safe fixed executable probes plus explicit evidence-backed capabilities."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess


def assess(data):
    from job_state import identity
    capabilities = {}
    for key, cap in data.get('capabilities', {}).items():
        if cap.get('status') not in ('available', 'unavailable', 'unknown') or not cap.get('method') or not cap.get('notes'):
            raise ValueError('Capability needs status, method and notes')
        evidence = [identity(p) for p in cap.get('evidence', [])]
        if cap['status'] == 'available' and not evidence:
            raise ValueError('Available capability needs a successful interaction/probe record')
        capabilities[key] = {**cap, 'evidence': evidence}
    probes = {}
    for name in data.get('tools', []):
        if name not in ('ffmpeg', 'ffprobe', 'melt', 'python'):
            raise ValueError('Only fixed safe tool probes are supported')
        executable = shutil.which(name)
        if not executable:
            probes[name] = {'status': 'unavailable'}
            continue
        try:
            result = subprocess.run([executable, '--version' if name == 'python' else '-version'], capture_output=True, timeout=15)
            probes[name] = {'status': 'available' if result.returncode == 0 else 'unavailable',
                            'executable': identity(executable), 'returncode': result.returncode,
                            'version': (result.stdout + result.stderr).decode(errors='replace')[:300]}
        except (OSError, subprocess.TimeoutExpired) as e:
            probes[name] = {'status': 'unavailable', 'error': type(e).__name__}
    return {'schema_version': 1, 'capabilities': capabilities, 'probes': probes,
            'handoffs': data.get('handoffs', []),
            'limitations': 'Tool availability does not establish listening, playback or agent perception. Recheck when session capabilities change.'}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('data'); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    report = assess(json.loads(Path(a.data).read_text(encoding='utf-8-sig')))
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    print(json.dumps({'report': str(out.resolve()), 'capabilities': {k: v['status'] for k, v in report['capabilities'].items()}, 'probes': {k: v['status'] for k, v in report['probes'].items()}}))
