"""Small reusable job operations; editorial choices stay in manifests and briefs."""
import argparse
import copy
from fractions import Fraction
from pathlib import Path
import pipeline as p
import job_state as j


def frame_budget(seconds, fps, weights):
    rate = Fraction(str(fps)); duration = Fraction(str(seconds))
    values = [Fraction(str(w)) for w in weights]
    if not 1 <= rate <= 120 or duration <= 0 or not values or min(values) <= 0:
        raise ValueError('Positive duration/weights and fps 1..120 required')
    total = round(duration * rate)
    if total < len(values):
        raise ValueError('Fewer frames than scenes')
    quotas = [(total-len(values))*w/sum(values) for w in values]
    counts = [1 + int(q) for q in quotas]
    for i in sorted(range(len(values)), key=lambda i: quotas[i]-int(quotas[i]), reverse=True)[:total-sum(counts)]:
        counts[i] += 1
    return {'frames': counts, 'total_frames': total, 'actual_seconds': float(total/rate), 'fps': str(rate)}


def coverage_check(output):
    """Optional structured ledger; never infer requirements from game genre."""
    ledger = output.get('feature_coverage', [])
    seen = set()
    for row in ledger:
        if not row.get('feature') or row['feature'] in seen or row.get('origin') not in ('user_required', 'producer_selected') or not row.get('source'):
            raise ValueError('Coverage needs unique feature, origin and source')
        seen.add(row['feature'])
        if row.get('disposition') not in ('kept', 'replaced', 'dropped') or not row.get('reason'):
            raise ValueError('Coverage needs disposition and reason')
        if row['disposition'] == 'dropped':
            if row['origin'] == 'user_required' and not row.get('user_waiver'):
                raise ValueError('Required feature cannot be dropped by replacement authorization')
        elif not row.get('segments') or any(type(i) is not int or not 0 <= i < len(output['segments']) for i in row['segments']):
            raise ValueError('Retained coverage needs current zero-based segment indices')


def coverage_transition(before, after):
    old = before.get('feature_coverage', [])
    new = {r['feature']: r for r in after.get('feature_coverage', [])}
    for row in old:
        current = new.get(row['feature'])
        if not current or current['origin'] != row['origin'] or current['source'] != row['source']:
            raise ValueError('Replacement ledger must retain feature origins and account for every prior feature')
    coverage_check(after)


def dimensions(path, aspect='16/9', exact=None, tolerance=.001):
    from PIL import Image
    with Image.open(path) as image:
        width, height = image.size
    ratio = float(Fraction(str(aspect)))
    if ratio <= 0 or not 0 <= tolerance <= .01:
        raise ValueError('Positive aspect and explicit tolerance 0..1% required')
    error = abs((width/height)/ratio-1)
    passed = [width,height] == list(exact) if exact is not None else error <= tolerance
    return {'dimensions':[width,height], 'requested_exact':exact, 'aspect':aspect,
            'relative_aspect_error':error, 'tolerance':tolerance,
            'status':'passed' if passed else 'failed', 'identity':j.identity(path)}


def preview(manifest, destination, width):
    m = p.read(manifest); p.validate_manifest(m)
    dest = Path(destination)
    if dest.exists() and any(dest.iterdir()):
        raise ValueError('Preview destination must be empty')
    oldw, oldh = m['format']['width'], m['format']['height']
    if type(width) is not int or width <= 0 or width % 2 or width > oldw:
        raise ValueError('Preview width must be positive even and no larger than master')
    scale = width / oldw
    even = lambda n: max(2, round(n*scale/2)*2)
    height = even(oldh)
    if abs((width/height)/(oldw/oldh)-1) > .01:
        raise ValueError('Preview rounding exceeds 1% aspect tolerance')
    m = copy.deepcopy(m); m['format'].update(width=width, height=height)
    m['preview_of'] = p.fingerprint(manifest, True)
    for output in m['outputs']:
        if output.get('label_style'):
            styles = [output['label_style']]
        else:
            styles = []
        for segment in output['segments']:
            layout = segment.get('layout', {})
            if layout.get('type') in ('rows', 'stack'):
                rows = layout.get('rows', layout.get('panels'))
                used = 0
                for ri, row in enumerate(rows):
                    row['height'] = even(row['height']) if ri < len(rows)-1 else height-used
                    used += row['height']
                    if layout['type'] == 'rows':
                        across = 0
                        for pi, panel in enumerate(row['panels']):
                            panel['width'] = even(panel['width']) if pi < len(row['panels'])-1 else width-across
                            across += panel['width']
            styles.extend(segment.get('effects', []))
            if isinstance(segment.get('label'), dict): styles.append(segment['label'])
        for style in styles:
            if 'blur_sigma' in style:
                style['blur_sigma'] *= scale
            for key in ('x','y','width','height','move_y','font_size'):
                if key in style:
                    style[key] = even(style[key]) if key in ('width','height') else round(style[key]*scale)
    # Validates rounding and crop ratios before writing anything. Source crops never scale.
    p.validate_manifest(m)
    p.write(dest/'manifest.json', m)
    return {'manifest': str((dest/'manifest.json').resolve())}


def bootstrap(config):
    root = Path(config['journal']).resolve()
    requirements = config['requirements']
    files = config['instructions']
    for path in files:
        if Path(path).suffix.lower() not in ('.md', '.toml') or not Path(path).is_file():
            raise ValueError('Baseline inputs must be existing Markdown/TOML instruction files; JSON belongs in job data')
    if not files or not config.get('requirements_source') or not requirements or any(not r.get('text') or not r.get('source') for r in requirements):
        raise ValueError('Requirements need text and source')
    if (root/'events.jsonl').exists():
        state = j.snapshot(root)
        if state['requirements'] != requirements:
            raise ValueError('Resume requirements differ; revise explicitly')
    else:
        state = j.update(root, 'init', {'requirements': requirements})
    if 'B1' not in state.get('baselines', {}):
        state = j.update(root, 'baseline', {'id':'B1', 'files':files, 'requirements_source': config['requirements_source']})
    elif [x['source'] for x in state['baselines']['B1']['files']] != [j.identity(f) for f in files]:
        raise ValueError('Resume baseline differs; assess or create a new baseline explicitly')
    return {'journal': str(root), 'baseline': 'B1', 'next': 'Register capability preflight, contract and stage before media commands'}


def deliver(config):
    root, stage_id = config['journal'], config['stage']
    state = j.snapshot(root); stage = state['stages'][stage_id]
    if stage.get('contract') != config['contract'] or set(a['id'] for a in config['artifacts']) != set(stage['artifacts']):
        raise ValueError('Delivery must match stage contract and full artifact set')
    if len(config['artifacts']) != len({a['id'] for a in config['artifacts']}) or not config.get('source'):
        raise ValueError('Delivery needs unique artifact IDs and handoff source')
    # Validate entire batch before registering; partial interrupted registration can resume.
    for art in config['artifacts']:
        actual = j.identity(art['path'])
        if art['id'] in state['artifacts'] and state['artifacts'][art['id']]['identity'] != actual:
            raise ValueError('Existing artifact differs; use a new revision')
    for art in config['artifacts']:
        if art['id'] not in state['artifacts']:
            state = j.update(root, 'artifact', art)
    if not any(d['contract']==config['contract'] for d in state.get('deliveries', [])):
        state = j.update(root, 'delivery', {k:config[k] for k in ('stage','contract','source')})
    return {'delivered': config['contract'], 'verification': 'not_established_by_delivery'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['budget','preview','bootstrap','deliver','handoff','sheets','dimensions'])
    parser.add_argument('config', help='UTF-8 JSON arguments; see workflow.md')
    args = parser.parse_args(); data = p.read(args.config)
    if args.command == 'budget': result = frame_budget(**data)
    elif args.command == 'preview': result = preview(**data)
    elif args.command == 'bootstrap': result = bootstrap(data)
    elif args.command == 'deliver': result = deliver(data)
    elif args.command == 'sheets': result = p.inspect(**data)
    elif args.command == 'dimensions': result = dimensions(**data)
    else:
        import review
        state = j.snapshot(data['journal']); result = review.handoff(state, state['stages'][data['stage']])
    import json
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == '__main__': main()
