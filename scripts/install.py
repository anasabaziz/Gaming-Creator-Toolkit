"""Install project-local discovery adapters; keep canonical skills in one place."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def install(root, platform):
    root = Path(root).resolve()
    platforms = ['codex', 'claude'] if platform == 'all' else [platform]
    names = json.loads((root / 'toolkit.json').read_text(encoding='utf-8'))['skills']
    written = []
    for name in platforms:
        if name not in ('codex', 'claude'):
            raise ValueError('Use the Grok setup guide for its skill library')
        destination = root / ('.agents' if name == 'codex' else '.claude') / 'skills'
        manifest = destination / '.creator-toolkit-install.json'
        previous = json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {}
        planned = {}
        for skill in names:
            source = (root / 'skills' / skill / 'SKILL.md').read_text(encoding='utf-8')
            if not source.startswith('---\n'):
                raise ValueError('Missing skill frontmatter: ' + skill)
            frontmatter = source.split('---', 2)[1]
            body = ('---' + frontmatter + '---\n\n# ' + skill + '\n\n'
                    'Before production, read [first-run customization](../../../setup/onboarding.md) '
                    'and confirm this project\'s relevant local profiles.\n\n'
                    'Read and follow the complete [canonical skill](../../../skills/' + skill + '/SKILL.md). '
                    'Resolve its supporting links relative to that canonical file. '
                    'The complete toolkit must remain in this project; this adapter is not a standalone skill.\n')
            relative = skill + '/SKILL.md'
            target = destination / relative
            if target.is_symlink() or target.parent.is_symlink():
                raise ValueError('Refusing to write through a symlink: ' + relative)
            if target.exists() and digest(target.read_bytes()) != previous.get(relative):
                raise ValueError('Existing skill is not an unchanged managed adapter: ' + relative)
            planned[relative] = body.encode('utf-8')
        if destination.is_symlink() or destination.parent.is_symlink():
            raise ValueError('Refusing a linked adapter directory')
        for relative, data in planned.items():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            written.append(str(target.relative_to(root)))
        manifest.write_text(json.dumps({k: digest(v) for k, v in planned.items()}, indent=2) + '\n', encoding='utf-8')
    return written


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', choices=['codex', 'claude', 'all'], required=True)
    args = parser.parse_args()
    print(json.dumps({'installed': install(ROOT, args.platform), 'profiles_changed': False}, indent=2))
