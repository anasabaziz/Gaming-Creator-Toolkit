"""Regression tests for workflow transitions using synthetic files only."""
import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import execution
import job_state as j
import journal_recovery
import pipeline
import review
from test_review import fixture, producer_reviews


class TransitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.job, self.evidence, self.art, _ = fixture(self.root)

    def issues(self):
        s = j.snapshot(self.job)
        return review.evaluate(s, s['stages']['thumb'])

    def human(self, ident='H1'):
        return j.update(self.job, 'review', {'id': ident, 'contract': 'C1', 'check': 'visual',
            'role': 'human_verifier', 'reviewer_type': 'human', 'reviewer': 'fixture human',
            'source': 'Synthetic report', 'status': 'passed', 'method': 'visual_inspection',
            'coverage': 'whole fixture', 'notes': 'synthetic only', 'evidence': [str(self.evidence)]})

    def test_conflicts_are_order_independent_and_require_current_disposition(self):
        producer_reviews(self.job, self.evidence)
        j.update(self.job, 'review', {'id': 'F1', 'contract': 'C1', 'check': 'visual',
            'role': 'producer', 'reviewer': 'fixture', 'status': 'failed', 'method': 'visual_inspection',
            'coverage': 'whole fixture', 'notes': 'fixture defect', 'evidence': [str(self.evidence)], 'supersedes': 'R-visual'})
        self.human()
        state = j.snapshot(self.job)
        self.assertTrue(any('disposition' in x for x in self.issues()))
        reverse = copy.deepcopy(state)
        reverse['reviews'] = {k: state['reviews'][k] for k in ['H1', 'R-coverage', 'R-dimensions', 'R-visual', 'F1']}
        self.assertEqual(review.evaluate(state, state['stages']['thumb']), review.evaluate(reverse, reverse['stages']['thumb']))
        data = {'id': 'D1', 'contract': 'C1', 'check': 'visual', 'reviews': ['F1', 'H1'],
                'decision': 'rebutted', 'selected_review': 'H1', 'reason': 'Synthetic evidence resolves disagreement',
                'source': 'fixture assessment', 'evidence': [str(self.evidence)]}
        j.update(self.job, 'resolution', data)
        self.assertEqual(self.issues(), [])
        # Fresh human finding is not implicitly covered by the old assessment.
        h = j.snapshot(self.job)['reviews']['H1']
        j.update(self.job, 'review', {**h, 'id': 'H2', 'supersedes': 'H1', 'evidence': [str(self.evidence)]})
        self.assertTrue(self.issues())

    def test_optional_reviewer_failure_needs_disposition(self):
        producer_reviews(self.job, self.evidence)
        j.update(self.job, 'delivery', {'stage': 'thumb', 'contract': 'C1', 'source': 'fixture delivery'})
        j.update(self.job, 'review_choice', {'stage': 'thumb', 'contract': 'C1', 'choice': 'human_sufficient', 'source': 'user'})
        j.update(self.job, 'review', {'id': 'F', 'contract': 'C1', 'check': 'visual', 'role': 'reviewer',
            'reviewer_type': 'human', 'preflight': 'P1', 'reviewer': 'fixture', 'status': 'failed',
            'method': 'visual_inspection', 'coverage': 'fixture', 'notes': 'synthetic defect', 'evidence': [str(self.evidence)]})
        self.assertTrue(any('failed' in x for x in self.issues()))

    def test_unverified_capability_still_allows_human_handoff(self):
        producer_reviews(self.job, self.evidence)
        r = j.snapshot(self.job)['reviews']['R-visual']
        j.update(self.job, 'review', {**r, 'id': 'U', 'status': 'unverified', 'supersedes': r['id'], 'evidence': [str(self.evidence)]})
        self.human()
        self.assertEqual(self.issues(), [])

    def test_blockers_reconcile_and_acceptance_use_same_gate(self):
        producer_reviews(self.job, self.evidence)
        j.update(self.job, 'stage', {'id': 'thumb', 'status': 'completed'})
        j.update(self.job, 'plan', {'issues': [{'stage': 'thumb', 'blocking': True, 'resolved': False, 'description': 'new issue'}]})
        self.assertTrue(any('blocking' in x for x in self.issues()))
        self.assertTrue(any('blocking' in str(x) for x in j.reconcile(self.job)['findings']))
        state = j.update(self.job, 'acceptance', {'stage': 'thumb', 'contract': 'C1', 'decision': 'accepted', 'acceptor': 'user', 'source': 'explicit fixture'})
        self.assertTrue(any('blocking' in x for x in state['acceptances'][-1]['outstanding_at_recording']))
        self.assertEqual(state['stages']['thumb']['status'], 'completed')

    def test_recursive_dependencies_and_cycle_detection(self):
        producer_reviews(self.job, self.evidence)
        j.update(self.job, 'stage', {'id': 'thumb', 'status': 'completed'})
        c = copy.deepcopy(j.snapshot(self.job)['contracts']['C1']); c.update(id='C2', stage='child')
        j.update(self.job, 'contract', c)
        j.update(self.job, 'stage', {'id': 'child', 'status': 'running', 'contract': 'C2', 'artifacts': ['a1'], 'depends_on': ['thumb']})
        for r in list(j.snapshot(self.job)['reviews'].values()):
            j.update(self.job, 'review', {**r, 'id': 'child-' + r['id'], 'contract': 'C2', 'evidence': [str(self.evidence)]})
        j.update(self.job, 'stage', {'id': 'child', 'status': 'completed'})
        j.update(self.job, 'plan', {'issues': [{'stage': 'thumb', 'blocking': True}]})
        s = j.snapshot(self.job)
        self.assertTrue(any('Dependency' in x for x in review.evaluate(s, s['stages']['child'])))
        with self.assertRaisesRegex(ValueError, 'Dependency'):
            j.update(self.job, 'stage', {'id': 'grandchild', 'status': 'running', 'depends_on': ['child']})
        with self.assertRaisesRegex(ValueError, 'cycle'):
            j.update(self.job, 'stage', {'id': 'thumb', 'status': 'pending', 'depends_on': ['child']})
        # Previously damaged cyclic state must report, not recurse forever.
        s['stages']['thumb']['depends_on'] = ['child']
        self.assertTrue(any('cycle' in x for x in review.evaluate(s, s['stages']['child'])))

    def test_operation_failure_blocks_and_retry_needs_change(self):
        with patch.dict(os.environ, {'VIDEO_JOB_RECORD': str(self.job), 'VIDEO_JOB_STAGE': 'thumb'}):
            with self.assertRaisesRegex(RuntimeError, 'fixture failure'):
                execution.operation('render', {}, lambda: (_ for _ in ()).throw(RuntimeError('fixture failure')))
            self.assertEqual(j.snapshot(self.job)['stages']['thumb']['status'], 'blocked')
            with self.assertRaisesRegex(ValueError, 'running stage'):
                execution.operation('render', {}, lambda: None)
            with self.assertRaisesRegex(ValueError, 'resume_change'):
                j.update(self.job, 'stage', {'id': 'thumb', 'status': 'running'})
            j.update(self.job, 'stage', {'id': 'thumb', 'status': 'running', 'resume_change': 'Synthetic cause fixed; fixture evidence'})
            execution.operation('render', {}, lambda: {'ok': True})

    def test_multi_target_validation_requires_every_export(self):
        other = self.root / 'second.mp4'; other.write_text('second fixture')
        j.update(self.job, 'artifact', {'id': 'a2', 'path': str(other)})
        c = copy.deepcopy(j.snapshot(self.job)['contracts']['C1']); c.update(id='C2', artifacts=['a1', 'a2'])
        c['checks'].append({'id': 'technical', 'criterion': 'Both exports', 'targets': ['a1', 'a2']})
        j.update(self.job, 'contract', c)
        paths = []
        for i, art in enumerate([self.art, other]):
            project = self.root / f'p{i}.mlt'; project.write_text('fixture project')
            path = self.root / f'v{i}.json'
            path.write_text(json.dumps({'integrity': {'status': 'passed'}, 'dependencies': {'export': j.identity(art), 'project': j.identity(project), 'media': []}}))
            paths.append(str(path))
        r = {'id': 'T', 'contract': 'C2', 'check': 'technical', 'role': 'producer', 'reviewer': 'fixture',
             'status': 'passed', 'method': 'automated_validation', 'coverage': 'all targets', 'notes': 'synthetic only', 'evidence': [str(self.evidence)]}
        with self.assertRaisesRegex(ValueError, 'all review targets'):
            j.update(self.job, 'review', {**r, 'validations': paths[:1]})
        j.update(self.job, 'review', {**r, 'validations': paths})
        other.write_text('changed')
        s = j.snapshot(self.job)
        stage = {**s['stages']['thumb'], 'contract': 'C2', 'artifacts': ['a1', 'a2']}
        self.assertTrue(any('stale' in x for x in review.evaluate(s, stage)))

    def test_terminal_subprocess_failure_blocks_direct_calls(self):
        with patch.dict(os.environ, {'VIDEO_JOB_RECORD': str(self.job), 'VIDEO_JOB_STAGE': 'thumb'}), patch('execution.subprocess.run', return_value=subprocess.CompletedProcess([], 1, b'', b'fixture failure')):
            self.assertEqual(execution.execute(['fixture']).returncode, 1)
            self.assertEqual(j.snapshot(self.job)['stages']['thumb']['status'], 'blocked')
            with self.assertRaisesRegex(ValueError, 'running stage'):
                execution.execute(['fixture'])

    def test_contract_rejects_unchecked_outputs(self):
        c = copy.deepcopy(j.snapshot(self.job)['contracts']['C1']); c.update(id='C2', artifacts=['a1', 'forgotten'])
        with self.assertRaisesRegex(ValueError, 'no check targets'):
            j.update(self.job, 'contract', c)
        c.update(kind='highlight', artifact_roles={'a1': 'video', 'forgotten': 'project'})
        keys = review.catalog()['deliverables']['highlight']
        c['checks'] = [{'id': key, 'criterion': 'fixture', 'targets': ['a1' if key not in ('project', 'project_gui') else 'forgotten']} for key in keys]
        j.update(self.job, 'contract', c)
        c.update(id='C3', artifacts=['a1', 'forgotten', 'video2'])
        c['artifact_roles']['video2'] = 'video'
        with self.assertRaisesRegex(ValueError, 'missing applicable'):
            j.update(self.job, 'contract', c)

    def test_recovery_preserves_original_and_refuses_interior_damage(self):
        path = self.job / 'events.jsonl'
        original = path.read_bytes() + b'{'
        path.write_bytes(original)
        destination = self.root / 'recovered'
        journal_recovery.recover(self.job, destination, hashlib.sha256(original).hexdigest(), 'explicit fixture authorization')
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual((destination / 'damaged-events.original.jsonl').read_bytes(), original)
        self.assertEqual(j.snapshot(destination)['stages']['thumb']['status'], 'blocked')
        with self.assertRaisesRegex(ValueError, 'changed'):
            journal_recovery.recover(self.job, self.root / 'wrong', 'wrong hash', 'fixture')
        broken = original + b'\n{}\n'; path.write_bytes(broken)
        with self.assertRaisesRegex(ValueError, 'final event'):
            journal_recovery.recover(self.job, self.root / 'interior', hashlib.sha256(broken).hexdigest(), 'fixture')

    def test_direct_trailer_derivation_validates_selected_source(self):
        source = self.root / 'source.mp4'; source.write_text('fixture bytes')
        manifest = self.root / 'manifest.json'
        m = {'schema_version': 2, 'source': str(source), 'source_identity': pipeline.fingerprint(source),
             'format': {'width': 320, 'height': 180, 'fps': '30'}, 'outputs': []}
        pipeline.write(manifest, m)
        selections = self.root / 'selections.json'; pipeline.write(selections, [{'in': 1, 'out': 2}])
        media = ({'format': {'duration': '3'}, 'streams': []}, {'width': 320, 'height': 180})
        with patch('pipeline.media_info', return_value=media):
            pipeline.derive(manifest, self.root / 'trailer', 'trailer', selections=selections)
            out = pipeline.read(self.root / 'trailer/manifest.json')['outputs'][0]
            self.assertEqual(out['audio'], 'preserve')
            self.assertEqual(out['segments'], [{'in': 1, 'out': 2}])
            pipeline.write(selections, [{'in': 1, 'out': 4}])
            with self.assertRaisesRegex(ValueError, 'source range'):
                pipeline.derive(manifest, self.root / 'bad', 'trailer', selections=selections)
            self.assertFalse((self.root / 'bad').exists())


if __name__ == '__main__':
    unittest.main()
