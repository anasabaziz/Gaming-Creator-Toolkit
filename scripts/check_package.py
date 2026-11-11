"""Audit the explicit public file list, links, metadata and release conditions."""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = {'.creator-toolkit', '.env', '.git', '.agents', '.claude', '.venv', '__pycache__',
           'jobs', 'media', 'reference', 'tracking', 'reports', 'tmp', 'dist', 'node_modules'}
TEXT = {'.md', '.py', '.json', '.yaml', '.yml', '.txt', '.html', '.svg', '.gitignore'}


def public_files(root):
    root = Path(root).resolve()
    files = json.loads((root / 'PACKAGE_FILES.json').read_text(encoding='utf-8'))
    if not isinstance(files, list) or not files or len(files) != len(set(files)):
        raise ValueError('Package file list must contain unique relative paths')
    selected = []
    for value in files:
        rel = PurePosixPath(value)
        if rel.is_absolute() or '..' in rel.parts or '\\' in value or ':' in value:
            raise ValueError('Unsafe package path: ' + value)
        if set(rel.parts) & PRIVATE or rel.name.startswith('.env'):
            raise ValueError('Private/generated path in public file list: ' + value)
        path = root / value
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('Missing, linked or external package file: ' + value)
        if any(parent.is_symlink() for parent in path.parents if parent != root and parent.is_relative_to(root)):
            raise ValueError('Linked package directory: ' + value)
        selected.append(path)
    return selected


def audit(root, release=False):
    root = Path(root).resolve()
    errors = []
    files = public_files(root)
    public = {p.resolve() for p in files}
    private_path = re.compile(r'[A-Za-z]:[/\\]Users[/\\][^/\\\s"\']+|/(?:Users|home)/[A-Za-z0-9_.-]+/')
    secret = re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{30,}')
    for path in files:
        if path.suffix not in TEXT and path.name not in ('LICENSE', '.gitignore'):
            errors.append('Unexpected public file type: ' + path.name)
            continue
        text = path.read_text(encoding='utf-8')
        if private_path.search(text) or secret.search(text):
            errors.append('Potential private path or credential in ' + str(path.relative_to(root)))
        if path.suffix == '.md':
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
                target = link.split('#', 1)[0].strip('<>')
                if not target or re.match(r'[a-z]+:', target):
                    continue
                resolved = (path.parent / unquote(target)).resolve()
                if not resolved.exists() or not resolved.is_relative_to(root):
                    errors.append(f'Broken/local-external link in {path.relative_to(root)}: {link}')
                elif resolved.is_file() and resolved not in public:
                    errors.append(f'Link targets unpackaged file in {path.relative_to(root)}: {link}')
        if path.name == 'SKILL.md':
            match = re.match(r'---\n(.*?)\n---\n', text, re.S)
            if not match or not re.search(r'^name: ' + re.escape(path.parent.name) + r'\s*$', match[1], re.M) or not re.search(r'^description: .+', match[1], re.M):
                errors.append('Invalid skill metadata: ' + path.parent.name)
    if release:
        if '[ORIGINAL_GITHUB_UPLOADER]' in (root / 'LICENSE').read_text(encoding='utf-8'):
            errors.append('Original GitHub uploader must finalize the license notice')
        status = json.loads((root / 'setup/validation.json').read_text(encoding='utf-8'))
        for key, result in status['release_checks'].items():
            if result.get('status') != 'passed' or not result.get('evidence'):
                errors.append('Release verification pending: ' + key)
    return {'files': len(files), 'errors': errors, 'status': 'passed' if not errors else 'failed'}


def tracked_audit(root):
    """Only inspect Git when this directory is the repository root, never a parent repo."""
    root = Path(root).resolve()
    probe = subprocess.run(['git', '-C', str(root), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    if probe.returncode or Path(probe.stdout.strip()).resolve() != root:
        return {'status': 'not_a_standalone_git_repository', 'unexpected': []}
    result = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'], capture_output=True, check=True)
    tracked = set(result.stdout.decode('utf-8').split('\0')) - {''}
    expected = {p.relative_to(root).as_posix() for p in public_files(root)}
    unexpected = sorted(tracked - expected)
    return {'status': 'failed' if unexpected else 'passed', 'unexpected': unexpected}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', action='store_true')
    parser.add_argument('--git', action='store_true')
    args = parser.parse_args()
    result = audit(ROOT, args.release)
    if args.git:
        result['git'] = tracked_audit(ROOT)
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result['errors'] or result.get('git', {}).get('unexpected') else 0)
