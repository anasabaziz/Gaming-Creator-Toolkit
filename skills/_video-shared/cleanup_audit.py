"""Read-only MLT dependency inventory. No deletion or automatic cleanup."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def audit(root, job_record=None):
    root=Path(root).resolve(); projects=[]; errors=[]; sizes=Counter()
    for path in root.rglob('*'):
        if not path.is_file() or path.name=='.env': continue
        try:
            sizes[path.relative_to(root).parts[0]]+=path.stat().st_size
        except OSError as e:
            errors.append({'path':str(path),'error':str(e)});continue
        if path.suffix.lower()!='.mlt':continue
        try:
            tree=ET.parse(path); refs=[]
            xmlroot=tree.getroot().get('root')
            basedir=Path(xmlroot) if xmlroot and Path(xmlroot).is_absolute() else path.parent
            for node in tree.iter('property'):
                if node.get('name') not in ('resource','warp_resource','filename','av.file'):continue
                raw=(node.text or '').strip()
                if not raw or raw in ('0','1') or raw.startswith(('#','color:')):continue
                raw=re.sub(r'^\d+(?:\.\d+)?:((?:[A-Za-z]:[\\/]|/).*)$',r'\1',raw)
                if '://' in raw or '%' in raw:
                    refs.append({'raw':raw,'status':'unresolved-special-resource'});continue
                dep=Path(raw)
                if not dep.is_absolute():dep=basedir/dep
                dep=dep.resolve()
                refs.append({'raw':raw,'path':str(dep),'exists':dep.exists(),'bytes':dep.stat().st_size if dep.is_file() else None})
            projects.append({'project':str(path),'references':refs})
        except (OSError,ET.ParseError) as e:errors.append({'path':str(path),'error':str(e)})
    registered = []
    if job_record:
        from job_state import snapshot, identity
        for key, artifact in snapshot(job_record)['artifacts'].items():
            try:
                status = 'intact' if identity(artifact['path']) == artifact['identity'] else 'changed'
            except OSError:
                status = 'missing'
            registered.append({'id': key, 'path': artifact['path'], 'status': status})
    return {'root':str(root),'projects':projects,'registered_artifacts': registered,'directory_bytes':dict(sizes.most_common()),'errors':errors,
            'limitations':'MLT resources only; not all script dependencies. No file is certified disposable. No files deleted.'}


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('root');ap.add_argument('--out',required=True);ap.add_argument('--job-record')
    a=ap.parse_args();result=audit(a.root, a.job_record)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'report':str(out.resolve()),'projects':len(result['projects']),
        'missing_references':sum(r.get('exists') is False for x in result['projects'] for r in x['references']),
        'errors':len(result['errors']),'directory_bytes':result['directory_bytes']}))
