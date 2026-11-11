"""Finalize the original repository uploader's notice before first publication."""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def set_holder(root, username):
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?', username) or '--' in username:
        raise ValueError('Supply the original uploader GitHub username, not an email, URL or organization description')
    path = Path(root) / 'LICENSE'
    original = path.read_text(encoding='utf-8')
    token = '[ORIGINAL_GITHUB_UPLOADER]'
    if token not in original:
        raise ValueError('Copyright notice already finalized. Forks must retain it.')
    path.write_text(original.replace(token, username), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--github-user', required=True)
    args = parser.parse_args()
    set_holder(ROOT, args.github_user)
    print('Original copyright notice finalized. No network request or publication performed.')
