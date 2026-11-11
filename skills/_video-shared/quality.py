"""Seal reviewed quality results with versioned evidence; does not judge images."""
import argparse
import json
from pathlib import Path
from job_state import identity, snapshot


def evaluate(job, proposal_id, reviews, output):
    proposal = snapshot(job)['proposals'][proposal_id]
    suite_path = Path(__file__).with_name('quality_cases.json')
    cases = {x['id']: x for x in json.loads(suite_path.read_text())['cases']}
    results = []
    seen = set()
    for review in reviews:
        key = review['id']
        if key in seen or key not in cases:
            raise ValueError('Duplicate or unknown quality case')
        seen.add(key)
        if not review.get('reviewer') or not review.get('notes') or not review.get('evidence'):
            raise ValueError('Review needs reviewer, notes and evidence paths')
        if review['status'] not in ('passed', 'failed', 'unverified'):
            raise ValueError('Invalid review status')
        if len(review.get('criteria', [])) != len(cases[key]['criteria']):
            raise ValueError('Assess every criterion in suite order')
        if any(x not in ('passed', 'failed', 'unverified') for x in review['criteria']):
            raise ValueError('Invalid criterion result')
        if review['status'] == 'passed' and any(x != 'passed' for x in review['criteria']):
            raise ValueError('All criteria must pass')
        results.append({**review, 'evidence': [identity(p) for p in review['evidence']]})
    if not set(proposal['cases']) <= seen:
        raise ValueError('Missing required proposal cases')
    result = {'schema_version': 1, 'proposal_id': proposal_id, 'target_identity': proposal['target_identity'],
              'change': proposal['change'], 'suite_identity': identity(suite_path), 'results': results}
    with Path(output).open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job'); parser.add_argument('proposal'); parser.add_argument('reviews')
    parser.add_argument('--out', required=True)
    a = parser.parse_args()
    print(json.dumps(evaluate(a.job, a.proposal, json.loads(Path(a.reviews).read_text(encoding='utf-8-sig')), a.out), indent=2))
