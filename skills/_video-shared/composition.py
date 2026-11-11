"""Optional multi-source composition. Called by pipeline; no job-specific code."""
import copy
import math
import os
from pathlib import Path
import shutil


def catalog(m):
    sources = {'default': {'path': m['source'], 'identity': m['source_identity'],
                           'audio_stream': m.get('audio_stream')}}
    if 'default' in m.get('sources', {}):
        raise ValueError('default is reserved for the primary source')
    sources.update(m.get('sources', {}))
    return sources


def enabled(m):
    return bool(m.get('sources')) or any(o.get('music') or o.get('label_style') or o.get('label_requirements') is not None or
        any(s.get('effects') or s.get('label') or s.get('source_id') or s.get('audio_gain') is not None
            for s in o['segments']) for o in m['outputs'])


def finite(value, lo, hi, name):
    x = float(value)
    if not math.isfinite(x) or not lo <= x <= hi:
        raise ValueError(f'Invalid {name}: expected {lo}..{hi}')
    return x


def effects_for(o, s, duration):
    effects = copy.deepcopy(s.get('effects', []))
    if s.get('label'):
        label = {**o.get('label_style', {}), **s['label']}
        label.update(kind='label')
        label.setdefault('start', 0)
        label.setdefault('end', duration)
        effects.append(label)
    return effects


def validate(m, p):
    sources = catalog(m)
    infos = {}
    fps = float(p.Fraction(str(m['format']['fps'])))
    output_ids = [o['id'] for o in m['outputs']]
    if len(output_ids) != len(set(output_ids)):
        raise ValueError('Output IDs must be unique')
    for sid, src in sources.items():
        if p.fingerprint(src['path']) != src['identity']:
            raise ValueError(f'Source identity changed: {sid}')
        infos[sid] = p.media_info(src['path'])
    for o in m['outputs']:
        from job_helpers import coverage_check
        coverage_check(o)
        duration = sum(p.frames(s, fps) for s in o['segments']) / fps
        required = o.get('label_requirements')
        if required is not None:
            if len(required) != len(o['segments']):
                raise ValueError('Label requirements need one text or null entry per segment')
            for intended, segment in zip(required, o['segments']):
                label = segment.get('label')
                if intended is None:
                    if label or any(e.get('kind') == 'label' for e in segment.get('effects', [])):
                        raise ValueError('Label-free segment contains a label')
                elif not label or label.get('text') != intended or label.get('start', 0) != 0 or abs(label.get('end', p.frames(segment, fps)/fps)-p.frames(segment, fps)/fps) > 1e-8:
                    raise ValueError('Required label must match and cover the complete segment')
        expected = o.get('target_duration')
        if expected is not None and abs(duration-float(expected)) > 1/fps:
            raise ValueError('Selected ranges do not match target_duration')
        if o.get('music') and o.get('audio', 'preserve') == 'silent':
            raise ValueError('Silent output cannot also request music')
        music = o.get('music')
        if music:
            if not music.get('authorization') or not music.get('credit'):
                raise ValueError('Music requires authorization and credit/license notes')
            if p.fingerprint(music['path'], True) != music['identity']:
                raise ValueError('Music identity changed')
            ap = p.probe(music['path'])
            p.audio_index(ap, music.get('audio_stream'))
            if not any(x['codec_type'] == 'audio' for x in ap['streams']):
                raise ValueError('Music has no audio stream')
            finite(music.get('gain', .25), 0, 4, 'music gain')
            offset = finite(music.get('offset', 0), 0, 86400, 'music offset')
            if not music.get('loop') and offset + duration > float(ap['format']['duration']) + .001:
                raise ValueError('Music is too short; choose another offset or explicitly enable loop')
        previous = {}
        seen_ids = set()
        for s in o['segments']:
            sid = s.get('source_id', 'default')
            if sid not in sources:
                raise ValueError(f'Unknown source_id: {sid}')
            seen_ids.add(sid)
            if o.get('ordering', 'chronological') == 'chronological' and s['in'] < previous.get(sid, -1):
                raise ValueError('Chronological ranges must advance per source')
            previous[sid] = s['out']
            # Reuse all original range, format, layout and authorization checks.
            single = copy.deepcopy(m)
            single.pop('sources', None)
            src = sources[sid]
            single.update(source=src['path'], source_identity=src['identity'], audio_stream=src.get('audio_stream'))
            output = {**o, 'segments': [s], 'ordering': 'custom'}
            output.pop('feature_coverage', None)
            output.pop('target_duration', None)
            single['outputs'] = [output]
            p.validate_basic(single)
            seconds = p.frames(s, fps) / fps
            finite(s.get('audio_gain', 1), 0, 4, 'game audio gain')
            for e in effects_for(o, s, seconds):
                if e.get('kind') not in ('image', 'label'):
                    raise ValueError('Effect kind must be image or label')
                a = finite(e['start'], 0, seconds, 'effect start')
                b = finite(e['end'], 0, seconds, 'effect end')
                if b <= a:
                    raise ValueError('Effect end must follow start')
                if math.ceil(b*fps) <= math.ceil(a*fps):
                    raise ValueError('Effect must contain at least one output frame')
                for key in ('width', 'height'):
                    if not isinstance(e[key], int) or e[key] <= 0 or e[key] > m['format'][key]:
                        raise ValueError('Effect box must fit canvas')
                for key, size in [('x', 'width'), ('y', 'height')]:
                    finite(e[key], 0, m['format'][size]-e[size], 'effect position')
                finite(e.get('fade_in', 0), 0, b-a, 'fade duration')
                finite(e.get('move_y', 0), -m['format']['height'], m['format']['height'], 'movement')
                finite(e.get('blur_sigma', 0), 0, 100, 'blur sigma')
                finite(e.get('blur_ramp', b-a), 1/fps, seconds, 'blur ramp')
                if e['kind'] == 'image':
                    if p.fingerprint(e['path'], True) != e['identity']:
                        raise ValueError('Artwork identity changed; update the reviewed asset identity')
                elif not e.get('text', '').strip():
                    raise ValueError('Label text is required')
                if e.get('font') and p.fingerprint(e['font'], True) != e.get('font_identity'):
                    raise ValueError('Label font identity changed')
        if len(seen_ids) > 1 and (o.get('ordering') != 'custom' or not o.get('ordering_authorization')):
            raise ValueError('Roundups require custom ordering and ordering_authorization')
    return (*infos['default'], fps)


def label_image(effect, job, p):
    from PIL import Image, ImageDraw, ImageFont
    key = p.digest(effect)
    path = job / 'assets-generated' / (key[:24] + '.png')
    def make(tmp):
        font = ImageFont.truetype(effect['font'], effect.get('font_size', 32)) if effect.get('font') else ImageFont.load_default(size=effect.get('font_size', 32))
        im = Image.new('RGBA', (effect['width'], effect['height']), effect.get('background', '#000000B0'))
        draw = ImageDraw.Draw(im)
        box = draw.textbbox((0, 0), effect['text'], font=font)
        if box[2]-box[0] > im.width-16 or box[3]-box[1] > im.height-8:
            raise ValueError('Label text does not fit; enlarge box or reduce font_size')
        draw.text((8-box[0], (im.height-(box[3]-box[1]))/2-box[1]), effect['text'], font=font, fill=effect.get('color', 'white'))
        im.save(tmp)
    p.produce(path, key, make)
    return path


def compose(base, effects, destination, key, duration, fmt, job, p):
    def make(tmp):
        args = [p.tool('ffmpeg'), '-v', 'error', '-n', '-i', base]
        graph = ['[0:v]setpts=PTS-STARTPTS[v0]']
        current = 'v0'
        for i, e in enumerate(effects, 1):
            artwork = label_image(e, job, p) if e['kind'] == 'label' else e['path']
            args += ['-loop', '1', '-framerate', str(fmt['fps']), '-i', artwork]
            a, b = float(e['start']), float(e['end'])
            gate = f'gte(t,{a})*lt(t,{b})'
            sigma = e.get('blur_sigma', 0)
            if sigma:
                progress = f'if(gte(T,{a})*lt(T,{b}),min(1,(T-{a})/{e.get("blur_ramp", b-a)}),0)'
                graph += [f'[{current}]split[clean{i}][blur{i}]',
                          f"[blur{i}]gblur=sigma={sigma}:enable='{gate}'[softall{i}]", f'[softall{i}]split[soft{i}][softcopy{i}]',
                          f"[clean{i}][soft{i}]blend=all_expr='A*(1-({progress}))+B*({progress})':enable='gte(t,{a})*lt(t,{min(b, a+float(e.get('blur_ramp', b-a)))})'[ramp{i}];[ramp{i}][softcopy{i}]overlay=enable='gte(t,{a+float(e.get('blur_ramp', b-a))})*lt(t,{b})'[bg{i}]"]
                current = f'bg{i}'
            chain = f'[{i}:v]format=rgba,scale={e["width"]}:{e["height"]}:force_original_aspect_ratio=decrease,pad={e["width"]}:{e["height"]}:(ow-iw)/2:(oh-ih)/2:color=black@0,setsar=1'
            fade = float(e.get('fade_in', 0))
            if fade:
                chain += f',fade=t=in:st={a}:d={fade}:alpha=1'
            graph.append(chain + f'[art{i}]')
            y = str(e['y'])
            if e.get('move_y'):
                y += f'+{e["move_y"]}*(1-min(1,max(0,(t-{a})/{fade or 0.5})))'
            graph.append(f"[{current}][art{i}]overlay=x={e['x']}:y='{y}':enable='{gate}':eof_action=pass[v{i}]")
            current = f'v{i}'
        graph.append(f'[{current}]format=yuv420p[out]')
        args += ['-filter_complex_threads', '1', '-filter_complex', ';'.join(graph), '-map', '[out]', '-map', '0:a?',
                 '-c:a', 'copy', '-c:v', 'ffv1', '-t', str(duration), '-color_range', 'tv', tmp]
        p.phase_run(args, job, 'effects', scene=Path(base).stem)
    p.produce(destination, key, make)


def render(manifest, p):
    manifest = Path(manifest).resolve(); job = manifest.parent
    m = p.read(manifest); _, _, fps = p.validate_manifest(m)
    fmt = m['format']; sources = catalog(m)
    infos = {sid: p.media_info(src['path']) for sid, src in sources.items()}
    if shutil.disk_usage(job).free < 2*1024**3:
        raise ValueError('Less than 2 GiB free')
    with p.lock(job):
        env = p.environment(job, fmt); results = []
        for o in m['outputs']:
            music = o.get('music')
            audible = o.get('audio', 'preserve') == 'preserve' and any(p.audio_index(infos[s.get('source_id', 'default')][0], sources[s.get('source_id', 'default')].get('audio_stream')) is not None for s in o['segments'])
            audible = bool(audible or music)
            pieces = []; keys = []; review = []; cursor = 0
            for s in o['segments']:
                sid = s.get('source_id', 'default'); src = sources[sid]; probe, video = infos[sid]
                n = p.frames(s, fps); duration = n/fps
                ai = p.audio_index(probe, src.get('audio_stream')) if o.get('audio', 'preserve') == 'preserve' else None
                base_key = p.digest({'source': src['identity'], 'range': [s['in'], s['out']], 'layout': s.get('layout', {'type':'full'}), 'audio': ai, 'audible': audible, 'gain': s.get('audio_gain', 1), 'environment': env})
                base = job / 'media' / (base_key[:24]+'.mkv')
                def trim(tmp):
                    args = [p.tool('ffmpeg'), '-v', 'error', '-n', '-ss', str(s['in']), '-i', src['path']]
                    graph = p.layout_filter(s.get('layout', {'type':'full'}), video['width'], video['height'], fmt['width'], fmt['height'])
                    graph += f';[v]fps={fmt["fps"]}:start_time=0,trim=end_frame={n},setpts=PTS-STARTPTS,format=yuv420p[out]'
                    if audible and ai is None:
                        args += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
                    args += ['-filter_complex_threads', '1', '-filter_complex', graph, '-map', '[out]']
                    if audible:
                        args += ['-map', f'0:{ai}' if ai is not None else '1:a:0', '-af', f'aresample=48000:async=1:first_pts=0,apad,volume={s.get("audio_gain",1)}', '-ac', '2', '-c:a', 'pcm_s16le']
                    else:
                        args += ['-an']
                    p.phase_run(args + ['-t', str(duration), '-c:v', 'ffv1', '-color_range', 'tv', tmp], job, 'extract', o['id'], len(pieces)+1)
                p.produce(base, base_key, trim)
                effects = effects_for(o, s, duration)
                effect_key = p.digest([base_key, effects])
                composed = job / 'media' / (effect_key[:24]+'.mkv') if effects else base
                if effects:
                    compose(base, effects, composed, effect_key, duration, fmt, job, p)
                final_key = effect_key
                if music:
                    final_key = p.digest([effect_key, music, cursor/fps])
                    mixed = job / 'media' / (final_key[:24]+'.mkv')
                    def mix(tmp):
                        args = [p.tool('ffmpeg'), '-v', 'error', '-n', '-i', composed]
                        if music.get('loop'): args += ['-stream_loop', '-1']
                        args += ['-ss', str(float(music.get('offset', 0))+cursor/fps), '-i', music['path']]
                        mi = p.audio_index(p.probe(music['path']), music.get('audio_stream'))
                        graph = f'[1:{mi}]aresample=48000,volume={music.get("gain",.25)},apad[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]'
                        p.phase_run(args + ['-filter_complex', graph, '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'pcm_s16le', '-ac', '2', '-t', str(duration), tmp], job, 'audio_mix', o['id'], len(pieces)+1)
                    p.produce(mixed, final_key, mix); composed = mixed
                for e in effects:
                    a = cursor + math.ceil(float(e['start'])*fps); b = min(cursor+n-1, cursor+math.ceil(float(e['end'])*fps)-1)
                    review.append({'kind': e['kind'], 'text': e.get('text'), 'box': [e['x'],e['y'],e['width'],e['height']], 'frames': sorted(set([max(cursor,a-1), a, (a+b)//2, b, min(cursor+n-1,b+1), min(b,a+round(float(e.get('fade_in',0))*fps))]))})
                pieces.append((composed,n)); keys.append(final_key); cursor += n
                p.write(job/'status.json', {'stage':'composing','output':o['id'],'completed_segments':len(pieces)})
            key = p.digest(keys); folder = job/'renders'/(o['id']+'-'+key[:16]); folder.mkdir(parents=True, exist_ok=True)
            aliases = []
            for i,(media,n) in enumerate(pieces):
                alias = folder/f'segment-{i:03}.mkv'
                def link(tmp):
                    try: os.link(media,tmp)
                    except OSError: shutil.copy2(media,tmp)
                p.produce(alias, keys[i], link)
                if p.fingerprint(alias, True)['sha256'] != p.fingerprint(media, True)['sha256']:
                    raise ValueError('Project media modified')
                aliases.append((alias,n))
            concat = folder/'concat.ffconcat'
            concat.write_text('ffconcat version 1.0\n'+'\n'.join(f"file 'segment-{i:03}.mkv'" for i in range(len(pieces))), encoding='utf-8')
            final = folder/(o['id']+'.mp4')
            def finish(tmp):
                args = [p.tool('ffmpeg'), '-v','error','-n','-f','concat','-safe','1','-i',concat,'-map','0:v','-c:v',fmt.get('encoder','libx264')]
                args += ['-crf','18','-preset','fast'] if fmt.get('encoder','libx264') == 'libx264' else ['-cq','19','-preset','p4']
                args += ['-map','0:a','-c:a','aac','-b:a','192k'] if audible else ['-an']
                p.phase_run(args+['-t',str(cursor/fps),'-r',str(fmt['fps']),'-pix_fmt','yuv420p','-color_range','tv','-movflags','+faststart',tmp], job, 'encode', o['id'])
            p.produce(final,key,finish)
            mlt=folder/(o['id']+'.mlt'); p.produce(mlt,key,lambda tmp:p.project(tmp,aliases,fmt))
            p.write(folder/'effects-review.json', {'checks':review,'status':'requires visual inspection','music_credit':music.get('credit') if music else None})
            if music: (folder/'MUSIC-CREDIT.txt').write_text(music['credit']+'\n',encoding='utf-8')
            results.append({'id':o['id'],'key':key,'mp4':str(final),'project':str(mlt),'frames':cursor,'audio_expected':audible,'segment_frames':[n for _,n in pieces], 'effect_samples':sorted({f for e in review for f in e['frames']}),'media':[p.fingerprint(a,True) for a,_ in aliases]})
        p.write(job/'render-state.json',{'manifest':p.digest(m),'environment':env,'outputs':results})
        p.write(job/'status.json',{'stage':'rendered','outputs':len(results)})
    return {'stage':'rendered','outputs':len(results)}
