"""Create an allowlisted public ZIP; no upload or repository history is included."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

from check_package import ROOT, audit, public_files


def package(root, destination, release=False):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    result = audit(root, release)
    if result['errors']:
        raise ValueError('\n'.join(result['errors']))
    files = public_files(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, 'gaming-creator-toolkit/' + path.relative_to(root).as_posix())
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(files):
            raise ValueError('ZIP verification failed')
    return {'archive': destination.name, 'files': len(files),
            'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
            'kind': 'release' if release else 'candidate'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', action='store_true', help='Require finalized notice and all release checks')
    args = parser.parse_args()
    version = json.loads((ROOT / 'toolkit.json').read_text(encoding='utf-8'))['version']
    suffix = '' if args.release else '-candidate'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    name = f'gaming-creator-toolkit-{version}{suffix}-{stamp}.zip'
    print(json.dumps(package(ROOT, ROOT / 'dist' / name, args.release), indent=2))
