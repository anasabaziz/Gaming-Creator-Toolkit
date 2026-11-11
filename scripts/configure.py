"""Record confirmed, project-local profiles without modifying public templates."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid

ROOT = Path(__file__).resolve().parents[1]
FILES = {p: p + '-profile.md' for p in ('creator', 'site', 'workflow')}
SKILLS = {'gameplay-highlights', 'gameplay-trailers', 'horizontal-to-vertical', 'game-thumbnails', 'gameplay-articles'}


def required(skills):
    needs = {'workflow'}
    if 'gameplay-articles' in skills:
        needs.add('site')
    if set(skills) - {'gameplay-articles'}:
        needs.add('creator')
    return needs


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def status(root, skill=None):
    private = Path(root) / '.creator-toolkit'
    config = private / 'config.json'
    issues = []
    if not config.is_file():
        return {'ready': False, 'issues': ['Customization has not been confirmed.'], 'enabled_skills': []}
    try:
        data = json.loads(config.read_text(encoding='utf-8'))
        enabled = data['enabled_skills']
        if data.get('schema_version') != 1 or data.get('confirmed') is not True or not data.get('confirmation', '').strip():
            issues.append('Configuration lacks a valid confirmation.')
        if not enabled or not set(enabled) <= SKILLS:
            issues.append('Invalid enabled skills.')
        if skill and skill not in enabled:
            issues.append('Requested skill has not been configured: ' + skill)
        for profile in required([skill] if skill else enabled):
            path = private / FILES[profile]
            if not path.is_file() or hash_file(path) != data.get('profile_hashes', {}).get(profile):
                issues.append('Profile missing or changed; reconfirm: ' + profile)
        return {'ready': not issues, 'issues': issues, 'enabled_skills': enabled}
    except (ValueError, KeyError, TypeError, AttributeError):
        return {'ready': False, 'issues': ['Configuration is malformed.'], 'enabled_skills': []}


def save(root, answers):
    root = Path(root).resolve()
    if answers.get('schema_version') != 1 or answers.get('confirmed') is not True:
        raise ValueError('Explicit confirmation and schema_version 1 are required')
    confirmation = answers.get('confirmation')
    if not isinstance(confirmation, str) or not confirmation.strip():
        raise ValueError('Record the actual user confirmation')
    enabled = answers.get('enabled_skills')
    if not isinstance(enabled, list) or not enabled or not set(enabled) <= SKILLS:
        raise ValueError('Supply known enabled_skills')
    profiles = answers.get('profiles', {})
    if not isinstance(profiles, dict) or set(profiles) - set(FILES):
        raise ValueError('Unknown profile fields')
    private = root / '.creator-toolkit'
    if private.is_symlink():
        raise ValueError('Private configuration must be a local directory')
    existing = private / 'config.json'
    old = json.loads(existing.read_text(encoding='utf-8')) if existing.exists() else {}
    enabled = sorted(set(enabled) | set(old.get('enabled_skills', [])))
    content = {}
    for name in required(enabled):
        value = profiles.get(name)
        path = private / FILES[name]
        if value is None and path.exists():
            value = path.read_text(encoding='utf-8')
        if not isinstance(value, str) or not value.strip() or 'UNCONFIGURED TEMPLATE' in value:
            raise ValueError('Filled profile required: ' + name)
        content[name] = value.rstrip() + '\n'
    private.mkdir(exist_ok=True)
    lock = private / '.configure.lock'
    with lock.open('x', encoding='utf-8') as f:
        f.write(str(os.getpid()))
    try:
        if existing.exists():
            archive = private / 'history' / uuid.uuid4().hex
            archive.mkdir(parents=True)
            for path in [existing, *[private / f for f in FILES.values()]]:
                if path.is_file():
                    shutil.copy2(path, archive / path.name)
        hashes = {}
        for name, value in content.items():
            target = private / FILES[name]
            if target.is_symlink():
                raise ValueError('Refusing linked profile')
            temp = private / (name + '.' + uuid.uuid4().hex + '.tmp')
            temp.write_text(value, encoding='utf-8', newline='\n')
            os.replace(temp, target)
            hashes[name] = hash_file(target)
        data = {'schema_version': 1, 'confirmed': True, 'confirmation': confirmation,
                'confirmed_at': datetime.now(timezone.utc).isoformat(),
                'enabled_skills': enabled, 'profile_hashes': hashes}
        temp = private / ('config.' + uuid.uuid4().hex + '.tmp')
        temp.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
        os.replace(temp, existing)
    finally:
        lock.unlink()
    return status(root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('status')
    check.add_argument('--skill', choices=sorted(SKILLS))
    write = commands.add_parser('save')
    write.add_argument('--answers', type=Path, required=True)
    args = parser.parse_args()
    result = status(ROOT, args.skill) if args.command == 'status' else save(ROOT, json.loads(args.answers.read_text(encoding='utf-8-sig')))
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['ready'] else 2)
