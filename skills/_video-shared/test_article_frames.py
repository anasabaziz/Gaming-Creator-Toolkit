"""Isolated synthetic extraction, cache and source-protection checks."""
import json
from pathlib import Path
import tempfile
from article_frames import extract
from pipeline import fingerprint, run, tool, write


def main():
    with tempfile.TemporaryDirectory(prefix='article-frames-') as folder:
        base = Path(folder)
        source = base / 'source.mp4'
        run([tool('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i',
             'testsrc2=size=320x180:rate=10:duration=2', '-c:v', 'libx264', source])
        manifest = base / 'manifest.json'
        write(manifest, {'schema_version': 2, 'source': str(source), 'source_identity': fingerprint(source)})
        requests = base / 'screenshots.json'
        rows = [{'section_id': 'section-1', 'time': .35, 'alt': 'Synthetic test pattern'}]
        write(requests, rows)
        first = extract(manifest, requests, base / 'images')
        assert abs(first[0]['actual_time'] - .4) < .001 and not first[0]['cached']
        assert extract(manifest, requests, base / 'images')[0]['cached']
        rows[0]['time'] = 3
        write(requests, rows)
        try:
            extract(manifest, requests, base / 'images')
            raise AssertionError('Invalid timestamp accepted')
        except ValueError:
            pass
        rows[0]['time'] = .35
        write(requests, rows)
        image = base / 'images' / first[0]['path']
        image.write_bytes(b'modified')
        try:
            extract(manifest, requests, base / 'images')
            raise AssertionError('Modified image accepted')
        except ValueError:
            pass
        source.touch()
        try:
            extract(manifest, requests, base / 'other')
            raise AssertionError('Changed source accepted')
        except ValueError:
            pass
        print('PASS: timestamp selection, native dimensions, cache, invalid time, modified image and source protection')


if __name__ == '__main__':
    main()
