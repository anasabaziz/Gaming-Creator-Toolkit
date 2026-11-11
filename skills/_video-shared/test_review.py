"""Synthetic bookkeeping tests; never establish real media review."""
import json
from pathlib import Path
import tempfile
import unittest
import job_state as j
import preflight
import review


def fixture(root):
    job = root / 'job'
    j.update(job, 'init', {'requirements': [{'text': 'Synthetic thumbnail fixture', 'source': 'test'}]})
    instructions = root / 'instructions.md'; instructions.write_text('initial instructions')
    evidence = root / 'evidence.md'; evidence.write_text('Synthetic fixture only; no visual claim')
    art = root / 'image.txt'; art.write_text('synthetic artifact')
    j.update(job, 'baseline', {'id': 'B1', 'files': [str(instructions)], 'requirements_source': 'test'})
    cap = {'status': 'available', 'method': 'synthetic fixture', 'notes': 'not actual perception', 'evidence': [str(evidence)]}
    report = root / 'preflight.json'; report.write_text(json.dumps(preflight.assess({'capabilities': {k: cap for k in ('visual', 'editorial', 'technical')}})))
    j.update(job, 'preflight', {'id': 'P1', 'path': str(report)})
    j.update(job, 'artifact', {'id': 'a1', 'path': str(art)})
    c = {'id': 'C1', 'stage': 'thumb', 'kind': 'thumbnail', 'baseline': 'B1', 'preflight': 'P1', 'artifacts': ['a1'],
         'checks': [{'id': k, 'criterion': 'Synthetic ' + k, 'targets': ['a1']} for k in ('coverage', 'dimensions', 'visual')]}
    j.update(job, 'contract', c)
    j.update(job, 'stage', {'id': 'thumb', 'status': 'running', 'contract': 'C1', 'artifacts': ['a1']})
    return job, evidence, art, instructions


def producer_reviews(job, evidence):
    c = j.snapshot(job)['contracts']['C1']
    for check in c['checks']:
        j.update(job, 'review', {'id': 'R-' + check['id'], 'contract': 'C1', 'check': check['id'], 'role': 'producer',
                 'reviewer': 'synthetic test', 'status': 'passed', 'method': check['methods'][0], 'coverage': 'synthetic fixture',
                 'notes': 'Tests record integrity only', 'evidence': [str(evidence)]})


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.job, self.evidence, self.art, self.instructions = fixture(self.root)

    def complete(self):
        return j.update(self.job, 'stage', {'id': 'thumb', 'status': 'completed'})

    def test_missing_checks_and_good_completion(self):
        with self.assertRaisesRegex(ValueError, 'producer check missing'):
            self.complete()
        producer_reviews(self.job, self.evidence)
        state = self.complete()
        self.assertEqual(state['stages']['thumb']['status'], 'completed')
        self.assertFalse(state.get('review_choices'))
        self.assertFalse(state.get('acceptances'))

    def test_evidence_change_invalidates_completion(self):
        producer_reviews(self.job, self.evidence); self.complete()
        self.evidence.write_text('changed')
        self.assertTrue(j.compact_status(self.job, audit=True)['findings'])
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.complete()
        with self.assertRaisesRegex(ValueError, 'Dependency production checks stale'):
            j.update(self.job, 'stage', {'id': 'downstream', 'status': 'running', 'depends_on': ['thumb']})

    def test_missing_review_cannot_be_replaced_by_text(self):
        with self.assertRaises(ValueError):
            j.update(self.job, 'stage', {'id': 'thumb', 'status': 'completed', 'review': 'checked'})

    def test_optional_choice_is_not_review_or_acceptance(self):
        producer_reviews(self.job, self.evidence); self.complete()
        for choice in ('pending', 'human_sufficient', 'subagent_requested'):
            state = j.update(self.job, 'review_choice', {'stage': 'thumb', 'contract': 'C1', 'choice': choice, 'source': 'synthetic user response'})
            self.assertEqual(state['stages']['thumb']['status'], 'completed')
            self.assertFalse(state.get('acceptances'))
            self.assertTrue(all(r['role'] == 'producer' for r in state['reviews'].values()))
        j.update(self.job, 'acceptance', {'stage': 'thumb', 'contract': 'C1', 'decision': 'accepted', 'acceptor': 'user', 'source': 'explicit test response'})
        self.assertEqual(len(j.snapshot(self.job)['acceptances']), 1)

    def test_unsolicited_reviewer_refused(self):
        with self.assertRaisesRegex(ValueError, 'requested'):
            j.update(self.job, 'review', {'id': 'X', 'contract': 'C1', 'check': 'visual', 'role': 'reviewer', 'reviewer': 'other', 'status': 'passed'})

    def test_omitted_default_check_refused(self):
        c = j.snapshot(self.job)['contracts']['C1']; c['id'] = 'C2'; c['checks'].pop()
        with self.assertRaisesRegex(ValueError, 'missing'):
            j.update(self.job, 'contract', c)

    def test_requirements_changes_invalidate_old_checks(self):
        producer_reviews(self.job, self.evidence)
        j.update(self.job, 'plan', {'requirements': [{'text': 'Different request', 'source': 'user'}]})
        with self.assertRaisesRegex(ValueError, 'Requirements changed'):
            self.complete()

    def test_failed_superseding_check_blocks(self):
        producer_reviews(self.job, self.evidence)
        old = j.snapshot(self.job)['reviews']['R-visual']
        data = {**old, 'id': 'R2', 'status': 'failed', 'supersedes': old['id'], 'evidence': [str(self.evidence)]}
        j.update(self.job, 'review', data)
        with self.assertRaisesRegex(ValueError, 'visual: failed'):
            self.complete()

    def test_wrong_contract_and_changed_artifact(self):
        producer_reviews(self.job, self.evidence)
        with self.assertRaises(ValueError):
            j.update(self.job, 'stage', {'id': 'other', 'status': 'completed', 'contract': 'C1', 'artifacts': ['a1']})
        self.art.write_text('changed')
        with self.assertRaises(ValueError):
            self.complete()

    def test_requested_reviewer_and_explicit_acceptance_condition(self):
        c = j.snapshot(self.job)['contracts']['C1']; c['id'] = 'C2'; c['acceptance_checks'] = ['visual']
        j.update(self.job, 'contract', c)
        j.update(self.job, 'stage', {'id': 'thumb', 'status': 'running', 'contract': 'C2'})
        for check in j.snapshot(self.job)['contracts']['C2']['checks']:
            j.update(self.job, 'review', {'id': 'P-' + check['id'], 'contract': 'C2', 'check': check['id'], 'role': 'producer', 'reviewer': 'fixture', 'status': 'passed', 'method': check['methods'][0], 'coverage': 'fixture', 'notes': 'fixture', 'evidence': [str(self.evidence)]})
        self.complete()
        acceptance = {'stage': 'thumb', 'contract': 'C2', 'decision': 'accepted', 'acceptor': 'user', 'source': 'explicit fixture response'}
        accepted = j.update(self.job, 'acceptance', acceptance)
        self.assertTrue(any('external review required' in p for p in accepted['acceptances'][-1]['outstanding_at_recording']))
        j.update(self.job, 'review_choice', {'stage': 'thumb', 'contract': 'C2', 'choice': 'human_sufficient', 'source': 'explicit fixture response'})
        j.update(self.job, 'review', {'id': 'H1', 'contract': 'C2', 'check': 'visual', 'role': 'reviewer', 'reviewer_type': 'human', 'preflight': 'P1', 'reviewer': 'fixture human', 'status': 'passed', 'method': 'visual_inspection', 'coverage': 'fixture', 'notes': 'synthetic only', 'evidence': [str(self.evidence)]})
        j.update(self.job, 'acceptance', acceptance)

    def test_not_applicable_cannot_bypass_required_visual(self):
        with self.assertRaisesRegex(ValueError, 'exemption'):
            j.update(self.job, 'review', {'id': 'NA', 'contract': 'C1', 'check': 'visual', 'role': 'producer', 'reviewer': 'test', 'status': 'not_applicable', 'method': 'visual_inspection', 'coverage': 'none', 'notes': 'no capability', 'reason': 'cannot inspect', 'evidence': [str(self.evidence)]})

    def test_automated_validation_must_match_artifact(self):
        c = j.snapshot(self.job)['contracts']['C1']; c['id'] = 'C2'
        c['checks'].append({'id': 'technical', 'criterion': 'Synthetic media integrity', 'targets': ['a1']})
        j.update(self.job, 'contract', c)
        project = self.root / 'project.mlt'; project.write_text('fixture')
        validation = self.root / 'validation.json'
        report = {'integrity': {'status': 'passed'}, 'dependencies': {'export': j.identity(self.art), 'project': j.identity(project), 'media': []}}
        validation.write_text(json.dumps(report))
        data = {'id': 'T1', 'contract': 'C2', 'check': 'technical', 'role': 'producer', 'reviewer': 'test', 'status': 'passed', 'method': 'automated_validation', 'coverage': 'fixture', 'notes': 'synthetic only', 'evidence': [str(validation)], 'validation': str(validation)}
        j.update(self.job, 'review', data)
        self.art.write_text('changed')
        with self.assertRaises(ValueError):
            j.update(self.job, 'review', {**data, 'id': 'T2', 'supersedes': 'T1'})


if __name__ == '__main__':
    unittest.main()
