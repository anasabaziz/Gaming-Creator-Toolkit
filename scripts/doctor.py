"""Read-only capability probes. Tool discovery never proves human/AI perception."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def find_tool(name):
    explicit = os.environ.get('VIDEO_' + name.upper())
    if explicit:
        return shutil.which(explicit) or (explicit if Path(explicit).is_file() else None)
    found = shutil.which(name)
    if found:
        return found
    if os.name == 'nt':
        candidate = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Shotcut' / (name + '.exe')
        if candidate.is_file():
            return str(candidate)
    return None


def inspect():
    result = {'os': platform.system(), 'python': platform.python_version(),
              'python_supported': sys.version_info >= (3, 10), 'tools': {},
              'libraries': {m: importlib.util.find_spec(m) is not None for m in ('PIL', 'openpyxl')},
              'unverified': ['image generation/editing', 'visual perception', 'continuous playback',
                             'full-output audio listening', 'Shotcut GUI opening/seeking'],
              'note': 'Install nothing automatically. Use the shared preflight for actual interaction evidence.'}
    for name in ('ffmpeg', 'ffprobe', 'melt'):
        executable = find_tool(name)
        if not executable:
            result['tools'][name] = {'available': False}
            continue
        try:
            env = dict(os.environ)
            env.setdefault('QT_QPA_PLATFORM', 'offscreen')
            process = subprocess.run([executable, '-version'], capture_output=True, timeout=20, env=env)
            output = (process.stdout + process.stderr).decode(errors='replace')
            result['tools'][name] = {'available': process.returncode == 0, 'version': output.splitlines()[:2]}
        except (OSError, subprocess.TimeoutExpired) as exc:
            result['tools'][name] = {'available': False, 'error': type(exc).__name__}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-video', action='store_true', help='Fail when the full video toolchain is missing')
    args = parser.parse_args()
    result = inspect()
    print(json.dumps(result, indent=2))
    ready = result['python_supported'] and result['libraries']['PIL']
    if args.require_video:
        ready = ready and all(v['available'] for v in result['tools'].values())
    raise SystemExit(0 if ready else 2)
