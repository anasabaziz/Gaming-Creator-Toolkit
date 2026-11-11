"""Portable manifest-driven gameplay editing. Python 3.10+, FFmpeg, Pillow.

No imports of legacy job scripts; no shell evaluation or background watchers.
Run --help for commands. See workflow.md for schema and limitations.
"""
import argparse
import contextlib
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from fractions import Fraction
from execution import execute, operation

VERSION = '1.2.0'
METRICS = {'commands': 0, 'cache_hits': 0}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def fingerprint(path, full=False):
    p = Path(path).resolve()
    s = p.stat()
    result = {'path': str(p), 'size': s.st_size, 'mtime_ns': s.st_mtime_ns}
    if full:
        h = hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                h.update(block)
        result['sha256'] = h.hexdigest()
    return result


def tool(name, required=True):
    explicit = os.environ.get('VIDEO_' + name.upper())
    found = explicit or shutil.which(name)
    if not found and os.name == 'nt':
        p = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Shotcut' / (name + '.exe')
        if p.exists():
            found = str(p)
    if not found and required:
        raise ValueError(f'{name} not found; set VIDEO_{name.upper()} or add it to PATH')
    return str(Path(found).resolve()) if found else None


def run(args, progress=None):
    METRICS['commands'] += 1
    is_probe = Path(str(args[0])).stem.lower() == 'ffprobe'
    result = execute(args, timeout=120 if is_probe else None, safe_retry=is_probe, progress=progress)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-5000:] or f'Command failed: {args[0]}')
    return result.stdout


def phase_run(args, job, phase, output=None, scene=None):
    status = {'stage': phase, 'output': output, 'scene': scene,
              'processed_media_seconds': 0, 'elapsed_seconds': 0, 'state': 'running'}
    write(Path(job) / 'status.json', status)
    def progress(values):
        status.update(values)
        write(Path(job) / 'status.json', status)
    try:
        result = run(args, progress=progress)
    except BaseException:
        status['state'] = 'interrupted_or_failed'
        write(Path(job) / 'status.json', status)
        raise
    status['state'] = 'command_finished'
    write(Path(job) / 'status.json', status)
    return result


def probe(path):
    return json.loads(run([tool('ffprobe'), '-v', 'error', '-show_format', '-show_streams', '-of', 'json', path]))


def media_info(path):
    p = probe(path)
    v = next(s for s in p['streams'] if s['codec_type'] == 'video')
    if v.get('color_transfer') in ('smpte2084', 'arib-std-b67'):
        raise ValueError('HDR requires an explicit tested tone-mapping workflow; this pipeline accepts SDR')
    if any(abs(float(s.get('rotation', 0))) > .01 for s in v.get('side_data_list', [])):
        raise ValueError('Rotated source needs explicit normalization first')
    if v.get('sample_aspect_ratio', '1:1') not in ('1:1', '0:1', 'N/A'):
        raise ValueError('Non-square source pixels need explicit normalization first')
    return p, v


def audio_index(p, requested):
    streams = [s['index'] for s in p['streams'] if s['codec_type'] == 'audio']
    if requested is None:
        return streams[0] if streams else None
    if requested not in streams:
        raise ValueError('audio_stream must identify an existing absolute stream index')
    return requested


def frames(segment, fps):
    return round((float(segment['out']) - float(segment['in'])) * fps)


def validate_basic(m):
    if m.get('schema_version') != 2:
        raise ValueError('Expected schema_version 2; import legacy jobs first')
    source = Path(m['source']).resolve()
    if fingerprint(source) != m['source_identity']:
        raise ValueError('Source identity changed; inspect it and explicitly create/revise the manifest')
    p, v = media_info(source)
    fmt = m['format']
    fps = float(Fraction(str(fmt['fps'])))
    if not 1 <= fps <= 120:
        raise ValueError('fps must be between 1 and 120')
    w, h = fmt['width'], fmt['height']
    if any(not isinstance(x, int) or x <= 0 or x % 2 for x in (w, h)):
        raise ValueError('Output dimensions must be positive even integers')
    if fmt.get('encoder', 'libx264') not in ('libx264', 'h264_nvenc'):
        raise ValueError('Supported encoders: libx264, h264_nvenc')
    audio_index(p, m.get('audio_stream'))
    duration = float(p['format']['duration'])
    ids = set()
    if not m.get('outputs'):
        raise ValueError('No outputs: add selected ranges to the manifest')
    for output in m['outputs']:
        from job_helpers import coverage_check
        coverage_check(output)
        ident = output['id']
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', ident) or ident in ids:
            raise ValueError('Output IDs must be unique safe filenames')
        ids.add(ident)
        if output.get('audio', 'preserve') not in ('preserve', 'silent'):
            raise ValueError('audio must be preserve or silent')
        if not output.get('segments'):
            raise ValueError('Output requires at least one segment')
        last = -1.0
        for s in output['segments']:
            a, b = float(s['in']), float(s['out'])
            if not math.isfinite(a + b) or not 0 <= a < b <= duration + .001 or frames(s, fps) < 1:
                raise ValueError('Invalid source range')
            if output.get('kind') == 'trailer' and output.get('ordering', 'chronological') == 'chronological' and a < last - .000001:
                raise ValueError('Chronological trailer ranges must advance without overlap')
            last = b
            layout = s.get('layout', {'type': 'full'})
            if w < h and not m.get('vertical_authorization'):
                raise ValueError('Portrait output requires vertical_authorization from the user request')
            layout_filter(layout, v['width'], v['height'], w, h)
        expected = output.get('target_duration')
        if expected is not None and abs(sum(frames(s, fps) for s in output['segments']) / fps - float(expected)) > 1 / fps:
            raise ValueError('Selected ranges do not match target_duration within one output frame')
    return p, v, fps


def validate_manifest(m):
    from composition import enabled, validate
    if enabled(m):
        return validate(m, SimpleNamespace(**globals()))
    return validate_basic(m)


def rect_filter(rect, sw, sh, dw, dh):
    if len(rect) != 4 or any(not isinstance(n, int) for n in rect):
        raise ValueError('crop must be integer [x,y,width,height]')
    x, y, w, h = rect
    if min(x, y) < 0 or min(w, h) <= 0 or x + w > sw or y + h > sh:
        raise ValueError('Crop outside source bounds')
    if any(n % 2 for n in rect):
        raise ValueError('Crop coordinates/dimensions must be even for chroma alignment')
    if abs((w / h) / (dw / dh) - 1) > .01:
        raise ValueError('Crop and destination aspect ratios differ by more than 1%; would stretch imagery')
    return f'crop={w}:{h}:{x}:{y},scale={dw}:{dh}:in_range=auto:out_range=tv,setsar=1'


def layout_filter(layout, sw, sh, w, h):
    kind = layout.get('type', 'full')
    if kind == 'rows':
        rows = layout['rows']
        if not rows or sum(r['height'] for r in rows) != h:
            raise ValueError('Row heights must fill the canvas')
        count = sum(len(r['panels']) for r in rows)
        if not 1 <= count <= 16:
            raise ValueError('Use 1-16 panels')
        parts = [f'[0:v]split={count}' + ''.join(f'[r{i}]' for i in range(count))]
        idx = 0
        for ri, row in enumerate(rows):
            rh = row['height']
            if not isinstance(rh, int) or rh <= 0 or rh % 2 or sum(x['width'] for x in row['panels']) != w:
                raise ValueError('Even positive row height and panel widths must fill the canvas')
            names = []
            for panel in row['panels']:
                pw = panel['width']
                if not isinstance(pw, int) or pw <= 0 or pw % 2:
                    raise ValueError('Panel width must be positive and even')
                parts.append(f'[r{idx}]' + rect_filter(panel['rect'], sw, sh, pw, rh) + f'[p{idx}]')
                names.append(f'[p{idx}]'); idx += 1
            parts.append(''.join(names) + (f'hstack=inputs={len(names)}' if len(names)>1 else 'null') + f'[row{ri}]')
        parts.append(''.join(f'[row{i}]' for i in range(len(rows))) + (f'vstack=inputs={len(rows)}' if len(rows)>1 else 'null') + '[v]')
        return ';'.join(parts)
    if kind == 'full':
        if abs((sw / sh) / (w / h) - 1) > .01:
            raise ValueError('Full-frame aspect mismatch; specify a reviewed crop or stacked panels')
        return f'[0:v]scale={w}:{h}:in_range=auto:out_range=tv,setsar=1[v]'
    if kind == 'crop':
        return '[0:v]' + rect_filter(layout['rect'], sw, sh, w, h) + '[v]'
    if kind == 'stack':
        panels = layout['panels']
        if not 2 <= len(panels) <= 4 or sum(p['height'] for p in panels) != h:
            raise ValueError('Use 2-4 full-width stacked panels whose heights fill the canvas')
        parts = [f'[0:v]split={len(panels)}' + ''.join(f'[a{i}]' for i in range(len(panels)))]
        for i, panel in enumerate(panels):
            ph = panel['height']
            if not isinstance(ph, int) or ph <= 0 or ph % 2:
                raise ValueError('Panel heights must be positive even integers')
            parts.append(f'[a{i}]' + rect_filter(panel['rect'], sw, sh, w, ph) + f'[p{i}]')
        parts.append(''.join(f'[p{i}]' for i in range(len(panels))) + f'vstack=inputs={len(panels)}[v]')
        return ';'.join(parts)
    raise ValueError('Supported layouts: full, crop, stack, rows; animated crops are not implemented')


@contextlib.contextmanager
def lock(job):
    p = job / '.pipeline.lock'
    try:
        f = p.open('x')
    except FileExistsError:
        raise ValueError('Job locked. Check the recorded PID before removing a stale .pipeline.lock')
    with f:
        f.write(str(os.getpid()))
    try:
        yield
    finally:
        p.unlink()


def cache_valid(path, key):
    side = Path(str(path) + '.cache.json')
    if not path.exists() or not side.exists():
        return False
    record = read(side)
    return record.get('key') == key and record.get('file') == fingerprint(path, True)


def produce(path, key, action):
    if cache_valid(path, key):
        METRICS['cache_hits'] += 1
        return
    if path.exists():
        raise ValueError(f'Existing unverified or modified file protected: {path}. Use a new revision/job.')
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + '.partial-' + uuid.uuid4().hex + path.suffix)
    try:
        action(tmp)
        os.replace(tmp, path)
        write(str(path) + '.cache.json', {'key': key, 'file': fingerprint(path, True)})
    finally:
        if tmp.exists():
            tmp.unlink()


def environment(job, fmt):
    import PIL
    ff, fp, melt = tool('ffmpeg'), tool('ffprobe'), tool('melt', False)
    dep = {'pipeline': VERSION, 'code': fingerprint(__file__, True)['sha256'],
           'composition': fingerprint(Path(__file__).with_name('composition.py'), True)['sha256'],
           'pillow': PIL.__version__,
           'ffmpeg': fingerprint(ff), 'ffprobe': fingerprint(fp), 'format': fmt}
    if melt:
        dep['melt'] = fingerprint(melt)
    if fmt.get('encoder') == 'h264_nvenc':
        smi = shutil.which('nvidia-smi')
        if not smi:
            raise ValueError('NVENC compatibility cache requires nvidia-smi driver identity')
        dep['gpu'] = run([smi, '--query-gpu=name,driver_version', '--format=csv,noheader']).decode().strip()
    key = digest(dep)
    cache_root = Path(os.environ.get('VIDEO_CACHE_DIR', str(job.parent / '.video-workflow-cache'))).resolve()
    sample = cache_root / ('environment-' + key[:16] + '.mp4')
    def encode(tmp):
        run([ff, '-v', 'error', '-n', '-f', 'lavfi', '-i', f'color=size={fmt["width"]}x{fmt["height"]}:rate={fmt["fps"]}',
             '-t', '0.1', '-c:v', fmt.get('encoder', 'libx264'), '-pix_fmt', 'yuv420p', tmp])
        run([ff, '-v', 'error', '-i', tmp, '-f', 'null', '-'])
    produce(sample, key, encode)
    write(job / 'environment.json', {'key': key, 'dependencies': dep, 'sample': str(sample), 'status': 'passed'})
    return key


def project(path, pieces, fmt):
    """Timing-editable Shotcut assembly of lossless, precomposed segment media."""
    fps = Fraction(str(fmt['fps']))
    root = ET.Element('mlt', producer='tractor', version='7.0.0', LC_NUMERIC='C')
    ET.SubElement(root, 'profile', description='Gameplay workflow', width=str(fmt['width']), height=str(fmt['height']),
                  frame_rate_num=str(fps.numerator), frame_rate_den=str(fps.denominator), progressive='1',
                  sample_aspect_num='1', sample_aspect_den='1', display_aspect_num=str(fmt['width']),
                  display_aspect_den=str(fmt['height']), colorspace='709')
    def prop(el, k, val):
        ET.SubElement(el, 'property', name=k).text = str(val)
    for i, (media, count) in enumerate(pieces):
        chain = ET.SubElement(root, 'chain', id=f's{i}')
        prop(chain, 'resource', Path(os.path.relpath(media, path.parent)).as_posix())
        prop(chain, 'mlt_service', 'avformat')
        prop(chain, 'eof', 'pause')
    playlist = ET.SubElement(root, 'playlist', id='video')
    prop(playlist, 'shotcut:name', 'V1')
    for i, (_, count) in enumerate(pieces):
        ET.SubElement(playlist, 'entry', producer=f's{i}', **{'in': '0', 'out': str(count - 1)})
    tractor = ET.SubElement(root, 'tractor', id='tractor', shotcut='1', **{'in': '0', 'out': str(sum(c for _, c in pieces) - 1)})
    prop(tractor, 'shotcut', 1)
    ET.SubElement(tractor, 'track', producer='video')
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


def render_basic(manifest):
    manifest = Path(manifest).resolve()
    job = manifest.parent
    m = read(manifest)
    p, v, fps = validate_manifest(m)
    fmt = m['format']
    # Lossless selected-range intermediates can be large; do not process if headroom is already low.
    if shutil.disk_usage(job).free < 2 * 1024**3:
        raise ValueError('Less than 2 GiB free; free space or select a different job location')
    with lock(job):
        env = environment(job, fmt)
        results = []
        for o in m['outputs']:
            technical_segments = [{k: s[k] for k in ('in', 'out', 'layout') if k in s} for s in o['segments']]
            key = digest({'source': m['source_identity'], 'audio_stream': m.get('audio_stream'),
                          'segments': technical_segments, 'audio': o.get('audio', 'preserve'), 'environment': env})
            folder = job / 'renders' / (o['id'] + '-' + key[:16])
            folder.mkdir(parents=True, exist_ok=True)
            write(job / 'status.json', {'stage': 'rendering', 'output': o['id'], 'revision': key})
            pieces = []
            ai = audio_index(p, m.get('audio_stream')) if o.get('audio', 'preserve') == 'preserve' else None
            for s in o['segments']:
                n = frames(s, fps)
                skey = digest({'segment': {k: s[k] for k in ('in', 'out', 'layout') if k in s}, 'format': fmt,
                               'audio': ai, 'source': m['source_identity'], 'environment': env})
                media = job / 'media' / (skey[:24] + '.mkv')
                graph = layout_filter(s.get('layout', {'type': 'full'}), v['width'], v['height'], fmt['width'], fmt['height'])
                graph += f';[v]fps={fmt["fps"]}:start_time=0,trim=end_frame={n},setpts=PTS-STARTPTS,format=yuv420p[out]'
                def segment(tmp):
                    args = [tool('ffmpeg'), '-v', 'error', '-n', '-ss', str(s['in']), '-i', m['source'], '-filter_complex', graph, '-map', '[out]']
                    if ai is not None:
                        args += ['-map', f'0:{ai}', '-af', 'aresample=48000:async=1:first_pts=0,apad', '-ac', '2', '-c:a', 'pcm_s16le']
                    else:
                        args += ['-an']
                    args += ['-t', str(n / fps), '-c:v', 'ffv1', '-color_range', 'tv', tmp]
                    phase_run(args, job, 'extract', o['id'], len(pieces)+1)
                produce(media, skey, segment)
                pieces.append((media, n))
            # Use simple local numbered filenames in a temporary concat manifest to avoid quoting arbitrary source paths.
            concat = folder / 'concat.ffconcat'
            links = []
            for i, (media, n) in enumerate(pieces):
                alias = folder / f'segment-{i:03}.mkv'
                if not alias.exists():
                    try:
                        os.link(media, alias)
                    except OSError:
                        shutil.copy2(media, alias)
                if fingerprint(alias, True)['sha256'] != fingerprint(media, True)['sha256']:
                    raise ValueError('Segment alias was modified; use a new revision')
                links.append(f"file 'segment-{i:03}.mkv'")
            concat.write_text('ffconcat version 1.0\n' + '\n'.join(links), encoding='utf-8')
            final = folder / (o['id'] + '.mp4')
            def finish(tmp):
                args = [tool('ffmpeg'), '-v', 'error', '-n', '-f', 'concat', '-safe', '1', '-i', concat, '-map', '0:v:0', '-c:v', fmt.get('encoder', 'libx264')]
                args += ['-crf', '18', '-preset', 'fast'] if fmt.get('encoder', 'libx264') == 'libx264' else ['-cq', '19', '-preset', 'p4']
                args += ['-map', '0:a:0', '-c:a', 'aac', '-b:a', '192k'] if ai is not None else ['-an']
                args += ['-t', str(sum(n for _, n in pieces) / fps), '-r', str(fmt['fps']), '-pix_fmt', 'yuv420p', '-color_range', 'tv', '-movflags', '+faststart', tmp]
                phase_run(args, job, 'encode', o['id'])
            produce(final, key, finish)
            mlt = folder / (o['id'] + '.mlt')
            # Relative paths resolve from the final project directory, also for the temporary file.
            produce(mlt, key, lambda tmp: project(tmp, [(folder / f'segment-{i:03}.mkv', n) for i, (_, n) in enumerate(pieces)], fmt))
            results.append({'id': o['id'], 'key': key, 'mp4': str(final), 'project': str(mlt), 'frames': sum(n for _, n in pieces),
                            'audio_expected': ai is not None, 'segment_frames': [n for _, n in pieces],
                            'media': [fingerprint(folder / f'segment-{i:03}.mkv', True) for i in range(len(pieces))]})
        write(job / 'render-state.json', {'manifest': digest(m), 'environment': env, 'outputs': results})
        write(job / 'status.json', {'stage': 'rendered', 'outputs': len(results)})
    return {'stage': 'rendered', 'outputs': len(results)}


def render(manifest):
    from composition import enabled, render as compose_render
    if enabled(read(manifest)):
        return compose_render(manifest, SimpleNamespace(**globals()))
    return render_basic(manifest)


def validation(manifest):
    from PIL import Image, ImageChops, ImageStat
    manifest = Path(manifest).resolve()
    job = manifest.parent
    write(job / 'status.json', {'stage': 'validate', 'state': 'running', 'integrity': 'not_established'})
    m = read(manifest)
    _, _, fps = validate_manifest(m)
    state = read(job / 'render-state.json')
    if state['manifest'] != digest(m):
        raise ValueError('Manifest changed since rendering; run render first')
    with lock(job):
        env = environment(job, m['format'])
        if env != state['environment']:
            raise ValueError('Environment changed; run render to create the appropriate revision')
        results = []
        for o in state['outputs']:
            final, mlt = Path(o['mp4']), Path(o['project'])
            media = [fingerprint(x['path'], True) for x in o['media']]
            if media != o['media']:
                raise ValueError('Referenced project media changed')
            current = {'export': fingerprint(final, True), 'project': fingerprint(mlt, True), 'media': media, 'environment': env}
            integrity_key = digest({'export': current['export'], 'expected': [o['frames'], o['audio_expected'], m['format']], 'environment': env})
            agreement_key = digest(current)
            record_path = final.parent / 'validation.json'
            old = read(record_path) if record_path.exists() else {}
            checks = {}
            if old.get('integrity', {}).get('key') == integrity_key and old['integrity'].get('status') == 'passed':
                checks['integrity'] = old['integrity']; METRICS['cache_hits'] += 1
            else:
                p = probe(final)
                v = next(x for x in p['streams'] if x['codec_type'] == 'video')
                audio = [x for x in p['streams'] if x['codec_type'] == 'audio']
                assert (v['width'], v['height']) == (m['format']['width'], m['format']['height']), 'Dimensions mismatch'
                assert int(v['nb_frames']) == o['frames'], 'Frame count mismatch'
                assert abs(float(Fraction(v['avg_frame_rate'])) - fps) < .001, 'Frame rate mismatch'
                assert abs(float(p['format']['duration']) - o['frames'] / fps) <= max(1 / fps, .03), 'Duration mismatch'
                assert bool(audio) == o['audio_expected'], 'Audio stream mismatch'
                if audio:
                    assert abs(float(v.get('start_time', 0)) - float(audio[0].get('start_time', 0))) < .05, 'Stream start alignment mismatch'
                run([tool('ffmpeg'), '-v', 'error', '-i', final, '-f', 'null', '-'])
                checks['integrity'] = {'key': integrity_key, 'status': 'passed', 'frames': o['frames'], 'decode': 'passed'}
            agreement = old.get('project_agreement', {})
            evidence_ok = bool(agreement.get('evidence')) and all(Path(e['path']).exists() and fingerprint(e['path'], True) == e for e in agreement.get('evidence', []))
            if agreement.get('key') == agreement_key and agreement.get('status') == 'passed' and evidence_ok:
                checks['project_agreement'] = agreement; METRICS['cache_hits'] += 1
            elif tool('melt', False):
                cursor = 0; samples = set(o.get('effect_samples', [])); evidence = []; differences = []
                for n in o['segment_frames']:
                    samples.update((cursor, cursor + n // 2, cursor + n - 1)); cursor += n
                evidence_dir = final.parent / 'checks' / agreement_key[:16]
                evidence_dir.mkdir(parents=True, exist_ok=True)
                for frame in sorted(samples):
                    a = evidence_dir / f'export-{frame}.png'; b = evidence_dir / f'project-{frame}.png'
                    # Evidence is derived; unique validation revision and -y allow recovery of incomplete checks.
                    run([tool('ffmpeg'), '-v', 'error', '-y', '-ss', str(frame / fps), '-i', final, '-frames:v', '1', a])
                    run([tool('melt'), mlt, f'in={frame}', f'out={frame}', '-consumer', f'avformat:{b}', 'vcodec=png', 'an=1', 'real_time=-1'])
                    with Image.open(a) as ia, Image.open(b) as ib:
                        assert ia.size == ib.size, 'Project/export dimensions differ'
                        diff = sum(ImageStat.Stat(ImageChops.difference(ia.convert('RGB'), ib.convert('RGB'))).mean) / 3
                    assert diff <= 12, f'Project/export sample differs at {frame}: {diff:.2f}'
                    differences.append({'frame': frame, 'mean_pixel_difference': diff})
                    evidence.extend([fingerprint(a, True), fingerprint(b, True)])
                checks['project_agreement'] = {'key': agreement_key, 'status': 'passed', 'samples': differences, 'evidence': evidence}
            else:
                checks['project_agreement'] = {'status': 'unverified', 'reason': 'melt unavailable'}
            checks['human_review'] = {'status': 'unverified', 'required': ['sampled visual inspection including every label and reveal', 'continuous playback and full vertical framing when applicable', 'audio listening/perceptual sync', 'Shotcut GUI opening and seeking']}
            checks['dependencies'] = current
            write(record_path, checks)
            results.append({'id': o['id'], 'validation': str(record_path), 'integrity': checks['integrity']['status'], 'project_agreement': checks['project_agreement']['status']})
        write(job / 'validation-summary.json', {'manifest': digest(m), 'outputs': results})
        write(job / 'status.json', {'stage': 'automated_checks_complete', 'human_review': 'unverified'})
    return results


def report(manifest):
    manifest = Path(manifest).resolve(); job = manifest.parent
    m = read(manifest); state = read(job / 'render-state.json')
    if state['manifest'] != digest(m):
        raise ValueError('Render state is stale')
    lines = ['# Gameplay video review', '', 'Projects allow timing edits to lossless precomposed media. Crops/panels are baked into that media; revise the manifest and rerender to change them.', '']
    cards = []
    for o, result in zip(m['outputs'], state['outputs']):
        mp4 = Path(os.path.relpath(result['mp4'], job)).as_posix(); mlt = Path(os.path.relpath(result['project'], job)).as_posix()
        vp = Path(result['mp4']).parent / 'validation.json'
        status = 'Not validated; run validate.'
        if vp.exists():
            r = read(vp)
            deps = r.get('dependencies', {})
            unchanged = (deps.get('export') == fingerprint(result['mp4'], True)
                         and deps.get('project') == fingerprint(result['project'], True)
                         and all(Path(x['path']).exists() and fingerprint(x['path'], True) == x for x in deps.get('media', [])))
            if unchanged:
                status = f"Recorded integrity: {r['integrity']['status']}; project samples: {r['project_agreement']['status']}. Qualitative production checks are unverified unless recorded below."
            else:
                status = 'Validation evidence is stale; run validate. No current pass is claimed.'
        journal = os.environ.get('VIDEO_JOB_RECORD')
        if journal:
            from job_state import snapshot
            from review import artifact_status
            summaries = artifact_status(snapshot(journal), result['mp4'])
            for summary in summaries:
                detail = '; '.join(summary['outstanding']) or 'Producer checks satisfied; optional review and user acceptance are separate.'
                status += ' Job stage ' + summary['stage'] + ': ' + detail
        lines += [f'## {o["id"]}', '', f'[MP4]({mp4}) | [Shotcut project]({mlt})', '', status, '', '| Source ID | Source in | Source out | Reason |', '|---|---:|---:|---|']
        for s in o['segments']:
            lines.append(f'| {s.get("source_id", "default")} | {s["in"]} | {s["out"]} | {s.get("reason", "")} |')
        effect_review = Path(result['mp4']).parent / 'effects-review.json'
        if effect_review.exists():
            lines += ['', f'[Effect and label review inventory]({Path(os.path.relpath(effect_review, job)).as_posix()}) â€” requires visual inspection.']
        if o.get('music'):
            credit = Path(result['mp4']).parent / 'MUSIC-CREDIT.txt'
            lines += ['', f'[Music credit]({Path(os.path.relpath(credit, job)).as_posix()})']
        cards.append(f'<h2>{html.escape(o["id"])}</h2><video controls preload="none" src="{html.escape(mp4, quote=True)}"></video><p>{html.escape(status)}</p><a href="{html.escape(mlt, quote=True)}">Shotcut project</a>')
    (job / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    (job / 'review.html').write_text('<!doctype html><meta charset="utf-8"><title>Gameplay review</title><style>body{font:16px system-ui;max-width:1000px;margin:30px auto}video{width:100%}</style>' + ''.join(cards), encoding='utf-8')
    return {'report': str(job / 'report.md'), 'review': str(job / 'review.html')}


def init(source, job):
    job = Path(job).resolve()
    if job.exists() and any(job.iterdir()):
        raise ValueError('New jobs require an empty directory; existing job files are protected')
    p, v = media_info(source)
    job.mkdir(parents=True, exist_ok=True)
    rate = Fraction(v.get('r_frame_rate') or v['avg_frame_rate'])
    if not 1 <= float(rate) <= 120:
        rate = Fraction(v['avg_frame_rate']).limit_denominator(1001)
    m = {'schema_version': 2, 'source': str(Path(source).resolve()), 'source_identity': fingerprint(source),
         'format': {'width': v['width'] // 2 * 2, 'height': v['height'] // 2 * 2, 'fps': str(rate), 'encoder': 'libx264'},
         'audio_stream': audio_index(p, None), 'outputs': []}
    write(job / 'manifest.json', m); write(job / 'source-info.json', p)
    return m


def legacy(path, job):
    old = read(path)
    if not old.get('clips') and not (old.get('segments') and all('source_in' in s and 'source_out_exclusive' in s for s in old['segments'])):
        raise ValueError('Unsupported legacy layout; translate manually without modifying the original')
    m = init(old['source'], job)
    fmt = old.get('final_settings', old.get('format', {}))
    if isinstance(fmt, dict):
        m['format'].update({k: fmt[k] for k in ('width', 'height', 'fps') if k in fmt})
    if old.get('clips'):
        for c in old['clips']:
            m['outputs'].append({'id': c['id'], 'kind': 'highlight', 'audio': 'preserve',
                                 'segments': [{'in': c['start'], 'out': c['end'], 'reason': c.get('reason', ''), 'evidence': c.get('evidence', '')}]})
    elif old.get('segments') and all('source_in' in s for s in old['segments']):
        m['outputs'] = [{'id': 'trailer', 'kind': 'trailer', 'ordering': 'chronological', 'audio': 'preserve',
                         'segments': [{'in': s['source_in'], 'out': s['source_out_exclusive'], 'reason': s.get('label', '')} for s in old['segments']]}]
    else:
        raise ValueError('Unsupported legacy layout; translate manually without modifying the original')
    m['import_note'] = 'Ranges imported only. Confirm audio, colour, framing and source identity before render; legacy validation is not imported.'
    write(Path(job) / 'manifest.json', m)
    return {'manifest': str(Path(job) / 'manifest.json'), 'note': m['import_note']}


def derive(path, job, mode, selections=None, layout=None, authorization=None, ordering='chronological', replacement_authorization=None, ordering_authorization=None, coverage=None):
    old = read(path)
    source_only = mode == 'trailer' and not old.get('outputs') and selections is not None
    if not source_only:
        validate_manifest(old)
    job = Path(job).resolve()
    if job.exists() and any(job.iterdir()):
        raise ValueError('Destination job must be empty; existing files are protected')
    m = json.loads(json.dumps(old)); m['parent_manifest'] = str(Path(path).resolve())
    if mode == 'trailer':
        chosen = read(selections) if selections else [s for o in old['outputs'] for s in o['segments']]
        if ordering == 'chronological':
            chosen = sorted(chosen, key=lambda s: s['in'])
        audio = old['outputs'][0].get('audio', 'preserve') if old.get('outputs') else 'preserve'
        m['outputs'] = [{'id': 'trailer', 'kind': 'trailer', 'ordering': ordering, 'audio': audio, 'segments': chosen}]
        if ordering_authorization:
            m['outputs'][0]['ordering_authorization'] = ordering_authorization
    else:
        if not layout or not authorization:
            raise ValueError('Vertical derivation requires a reviewed layout JSON and explicit authorization text')
        layouts = read(layout)
        replacements = read(selections) if selections else {}
        coverage_updates = read(coverage) if coverage else {}
        if set(replacements) - {o['id'] for o in m['outputs']}:
            raise ValueError('Replacement selections contain an unknown output ID')
        if replacements and not replacement_authorization:
            raise ValueError('Replacement selections require user or local-profile authorization')
        m['format'].update(width=1080, height=1920); m['vertical_authorization'] = authorization
        for o in m['outputs']:
            if o['id'] in replacements:
                from job_helpers import coverage_transition
                revised = {**o, 'segments': replacements[o['id']], 'feature_coverage': coverage_updates.get(o['id'], [])}
                coverage_transition(o, revised)
                o['feature_coverage'] = revised['feature_coverage']
                before = sum(frames(s, float(Fraction(str(m['format']['fps'])))) for s in o['segments'])
                chosen = replacements[o['id']]
                after = sum(frames(s, float(Fraction(str(m['format']['fps'])))) for s in chosen)
                if before != after or not all(s.get('replacement_reason') for s in chosen):
                    raise ValueError('Replacements must retain frame count and document replacement_reason for each selection')
                m.setdefault('replacement_history', []).append(json.loads(json.dumps({'output':o['id'], 'authorization':replacement_authorization, 'before':o['segments'], 'after':chosen})))
                o['segments'] = chosen
            if len(layouts.get(o['id'], [])) != len(o['segments']):
                raise ValueError('Provide exactly one reviewed layout per segment for each output')
            for i, s in enumerate(o['segments']):
                s['layout'] = layouts[o['id']][i]
            o['id'] += '-vertical'
    validate_manifest(m)
    write(job / 'manifest.json', m)
    return {'manifest': str(job / 'manifest.json')}


def inspect(source, job, start=0, end=None, step=15):
    from PIL import Image, ImageDraw, ImageChops, ImageStat
    p, v = media_info(source)
    end = min(float(end) if end is not None else float(p['format']['duration']), float(p['format']['duration']))
    if step <= 0 or start < 0 or start >= end:
        raise ValueError('Invalid inspection range/step')
    times = []; t = float(start)
    while t < end:
        times.append(t); t += step
    if len(times) > 240:
        raise ValueError('Limit each inspection to 240 samples; increase step or split the range')
    job = Path(job).resolve(); job.mkdir(parents=True, exist_ok=True)
    key = digest({'source': fingerprint(source), 'range': [start, end, step], 'ffmpeg': fingerprint(tool('ffmpeg')), 'version': VERSION})
    folder = job / 'analysis' / key[:16]; folder.mkdir(parents=True, exist_ok=True)
    observed = []; previous = None; images = []
    for i, t in enumerate(times):
        dest = folder / f'{i:04}.jpg'
        produce(dest, digest([key, t]), lambda tmp: run([tool('ffmpeg'), '-v', 'error', '-n', '-ss', str(t), '-i', source, '-frames:v', '1', '-vf', 'scale=384:-2', tmp]))
        with Image.open(dest) as im:
            gray = im.convert('L').resize((96,54)); small = im.copy(); small.thumbnail((384,216))
        score = sum(ImageStat.Stat(ImageChops.difference(gray, previous)).mean) if previous else 0
        observed.append({'time': t, 'frame_difference': score, 'image': str(dest)})
        previous = gray; images.append(small)
    sheets = []
    for offset in range(0, len(images), 16):
        rows = math.ceil(min(16, len(images) - offset) / 4)
        sheet = Image.new('RGB', (1536, rows*240), '#111111'); draw = ImageDraw.Draw(sheet)
        for j, im in enumerate(images[offset:offset+16]):
            x, y = j % 4 * 384, j // 4 * 240
            sheet.paste(im, (x, y+24)); draw.text((x+5,y+4), f'{times[offset+j]:.3f}s', fill='white')
        dest = folder / f'sheet-{offset//16+1}.jpg'; sheet.save(dest); sheets.append(str(dest))
    write(folder / 'scan.json', {'samples': observed, 'limitations': 'Sparse frame differences are candidate signals, not highlight rankings or exhaustive coverage.'})
    return {'sheets': sheets, 'scan': str(folder / 'scan.json'), 'samples': len(times)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job-record', help='Existing whole-job journal directory')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('render','validate','report','run','status'):
        q = sub.add_parser(name); q.add_argument('manifest')
    q = sub.add_parser('init'); q.add_argument('source'); q.add_argument('--job', required=True)
    q = sub.add_parser('import-legacy'); q.add_argument('manifest'); q.add_argument('--job', required=True)
    q = sub.add_parser('inspect'); q.add_argument('source'); q.add_argument('--job', required=True); q.add_argument('--start', type=float, default=0); q.add_argument('--end', type=float); q.add_argument('--step', type=float, default=15)
    q = sub.add_parser('trailer'); q.add_argument('manifest'); q.add_argument('--job', required=True); q.add_argument('--selections'); q.add_argument('--ordering', choices=['chronological','custom'], default='chronological'); q.add_argument('--ordering-authorization')
    q = sub.add_parser('vertical'); q.add_argument('manifest'); q.add_argument('--job', required=True); q.add_argument('--layouts', required=True); q.add_argument('--authorization', required=True); q.add_argument('--selections'); q.add_argument('--replacement-authorization'); q.add_argument('--coverage', help='Feature coverage ledger by original output ID for replacements')
    a = parser.parse_args(); started = time.monotonic()
    if a.job_record:
        os.environ['VIDEO_JOB_RECORD'] = str(Path(a.job_record).resolve())
    def stage(name, callback):
        inputs = {k: v for k, v in vars(a).items() if k != 'job_record'}
        for key in ('manifest', 'selections', 'layouts'):
            if inputs.get(key):
                inputs[key] = fingerprint(inputs[key], True)
        return operation(name, inputs, callback)
    try:
        if a.command == 'init': result = stage('init', lambda: init(a.source, a.job))
        elif a.command == 'import-legacy': result = stage('import-legacy', lambda: legacy(a.manifest, a.job))
        elif a.command == 'inspect': result = stage('inspect', lambda: inspect(a.source, a.job, a.start, a.end, a.step))
        elif a.command == 'trailer': result = stage('trailer', lambda: derive(a.manifest, a.job, 'trailer', selections=a.selections, ordering=a.ordering, ordering_authorization=a.ordering_authorization))
        elif a.command == 'vertical': result = stage('vertical', lambda: derive(a.manifest, a.job, 'vertical', layout=a.layouts, authorization=a.authorization, selections=a.selections, replacement_authorization=a.replacement_authorization, coverage=a.coverage))
        elif a.command == 'render': result = stage('render', lambda: render(a.manifest))
        elif a.command == 'validate': result = stage('validate', lambda: validation(a.manifest))
        elif a.command == 'report': result = stage('report', lambda: report(a.manifest))
        elif a.command == 'status': result = read(Path(a.manifest).parent / 'status.json')
        else:
            stage('render', lambda: render(a.manifest))
            stage('validate', lambda: validation(a.manifest))
            result = stage('report', lambda: report(a.manifest))
        METRICS['elapsed_seconds'] = round(time.monotonic() - started, 3)
        print(json.dumps({'result': result, 'metrics': METRICS}, ensure_ascii=True))
    except Exception as e:
        print(json.dumps({'error': str(e), 'metrics': METRICS}), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
