"""Extract original-resolution article frames without rendering video outputs."""
import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import uuid
import os
from execution import execute, operation
from pipeline import fingerprint, media_info, read, tool, write, digest
from composition import catalog


def extract(manifest, requests, out):
    m = read(manifest)
    if m.get('schema_version') != 2:
        raise ValueError('Expected schema-v2 source manifest')
    sources = catalog(m)
    checked = {}
    entries = read(requests)
    ids = set()
    for entry in entries:
        source_id = entry.get('source_id', 'default')
        if source_id not in sources:
            raise ValueError('Unknown screenshot source_id')
        if source_id not in checked:
            source = Path(sources[source_id]['path']).resolve()
            identity = fingerprint(source)
            if identity != sources[source_id]['identity']:
                raise ValueError('Source identity changed; reinspect before extraction')
            p, v = media_info(source)
            checked[source_id] = (source, identity, p, v)
        source, identity, p, v = checked[source_id]
        duration = float(v.get('duration', p['format']['duration']))
        sid = entry['section_id']
        t = float(entry['time'])
        if not re.fullmatch(r'section-[1-9][0-9]*', sid) or sid in ids:
            raise ValueError('Section IDs must be unique section-N values')
        if not math.isfinite(t) or not 0 <= t < duration:
            raise ValueError('Screenshot time outside source duration')
        if not entry.get('alt', '').strip():
            raise ValueError('Descriptive alt text is required')
        ids.add(sid)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    ffmpeg = tool('ffmpeg')
    results = []
    for entry in entries:
        source_id = entry.get('source_id', 'default')
        source, identity, p, v = checked[source_id]
        t = float(entry['time'])
        key = digest({'source': identity, 'time': t, 'tool': fingerprint(ffmpeg), 'version': 1})[:20]
        image = out / f"{entry['section_id']}-{key}.png"
        record = image.with_suffix('.json')
        if image.exists() or record.exists():
            if not (image.exists() and record.exists()):
                raise ValueError(f'Incomplete existing artifact: {image}; use a new output directory')
            saved = read(record)
            if saved['image'] != fingerprint(image, True):
                raise ValueError(f'Modified screenshot protected: {image}')
            actual = saved['actual_time']
            cached = True
        else:
            temp = out / f'.{uuid.uuid4().hex}.png'
            try:
                # Normalize timeline origin; select first decoded frame at/after request.
                # Accurate for VFR too; full decoding avoids ambiguous seek timestamps.
                filt = f"setpts=PTS-STARTPTS,select=gte(t\\,{t:.9f}),showinfo"
                run = execute([ffmpeg, '-hide_banner', '-nostdin', '-n', '-i', str(source),
                    '-map', '0:v:0', '-vf', filt, '-frames:v', '1', '-fps_mode', 'vfr', str(temp)])
                log = run.stderr.decode(errors='replace')
                times = re.findall(r'Parsed_showinfo[^\n]*\bn:\s*0\s+pts:.*?pts_time:([0-9.eE+-]+)', log)
                if run.returncode or not temp.exists() or not times:
                    raise RuntimeError('Frame extraction failed: ' + log[-1500:])
                actual = float(times[0])
                from PIL import Image
                with Image.open(temp) as im:
                    if im.size != (int(v['width']), int(v['height'])):
                        raise ValueError('Screenshot dimensions differ from source')
                    im.verify()
                if fingerprint(source) != identity:
                    raise ValueError('Source changed during extraction')
                # rename refuses to overwrite an existing destination on Windows.
                if image.exists():
                    raise ValueError('Screenshot destination appeared during extraction')
                temp.rename(image)
                write(record, {'source_id': source_id, 'source_identity': identity, 'requested_time': t,
                    'actual_time': actual, 'image': fingerprint(image, True)})
                cached = False
            finally:
                if temp.exists():
                    temp.unlink()
        results.append({**entry, 'path': image.name, 'actual_time': actual, 'cached': cached})
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    parser.add_argument('requests')
    parser.add_argument('--out', required=True)
    parser.add_argument('--job-record')
    args = parser.parse_args()
    if args.job_record:
        os.environ['VIDEO_JOB_RECORD'] = str(Path(args.job_record).resolve())
    result = operation('article_frames', {'manifest': fingerprint(args.manifest, True),
        'requests': fingerprint(args.requests, True), 'extractor': fingerprint(__file__, True)},
        lambda: extract(args.manifest, args.requests, args.out))
    print(json.dumps(result, indent=2))
