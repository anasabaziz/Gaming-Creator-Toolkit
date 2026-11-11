"""Isolated recovery and review-gate tests; no user media."""
import errno
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import execution
import job_state as j
import quality


class WorkflowTests(unittest.TestCase):
    def test_legacy_state_remains_readable_and_completable(self):
        state = j.snapshot(self.root)
        state['schema_version'] = 1
        with j.locked(self.root) as root:
            j.append(root, 'legacy_fixture', {}, state)
        artifact = self.root / 'legacy.txt'; artifact.write_text('old artifact')
        j.update(self.root, 'artifact', {'id': 'old', 'path': str(artifact)})
        j.update(self.root, 'stage', {'id': 'old-stage', 'status': 'completed', 'artifacts': ['old'], 'review': 'historical free-text review'})
        self.assertEqual(j.compact_status(self.root)['schema_version'], 1)
        self.assertEqual(j.snapshot(self.root)['stages']['old-stage']['review'], 'historical free-text review')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        j.update(self.root, 'init', {'next_action': 'review'})

    def test_recovery_and_artifact_protection(self):
        artifact = self.root / 'output.txt'; artifact.write_text('original')
        j.update(self.root, 'artifact', {'id': 'r1', 'path': str(artifact)})
        j.update(self.root, 'stage', {'id': 'video', 'status': 'running'})
        (self.root / 'job.json').write_text('interrupted summary')
        self.assertEqual(j.snapshot(self.root)['next_action'], 'review')
        self.assertEqual(j.reconcile(self.root)['findings'][0]['status'], 'completion_unknown')
        artifact.write_text('modified')
        with self.assertRaises(ValueError):
            j.update(self.root, 'stage', {'id': 'video', 'status': 'completed', 'artifacts': ['r1'], 'review': 'checked'})
        with self.assertRaises(ValueError):
            j.update(self.root, 'artifact', {'id': 'r1', 'path': str(artifact)})

    def test_lock_and_truncated_journal(self):
        with j.locked(self.root):
            with self.assertRaises(FileExistsError):
                j.record(self.root, 'test', {})
        with (self.root / 'events.jsonl').open('ab') as f:
            f.write(b'{')
        with self.assertRaises(ValueError):
            j.snapshot(self.root)

    def test_dependencies_and_failed_reviews(self):
        j.update(self.root, 'stage', {'id': 'trailer', 'status': 'pending', 'depends_on': ['highlights']})
        with self.assertRaises(ValueError):
            j.update(self.root, 'stage', {'id': 'trailer', 'status': 'running'})
        target = self.root / 'skill.md'; target.write_text('before')
        event = j.record(self.root, 'feedback', {'failure': 'test'})
        j.update(self.root, 'propose', {'id': 'P2', 'failure_events': [event['id']], 'target': str(target), 'rationale': 'test', 'change': 'proposed', 'cases': ['highlight-payoff']})
        with self.assertRaises(ValueError):
            quality.evaluate(self.root, 'P2', [{'id': 'highlight-payoff', 'status': 'passed', 'criteria': ['failed', 'passed'], 'reviewer': 'test', 'notes': 'test', 'evidence': [str(target)]}], self.root / 'eval.json')

    def test_bounded_retry(self):
        from test_review import fixture
        self.root, _, _, _ = fixture(self.root)
        ok = subprocess.CompletedProcess(['probe'], 0, b'ok', b'')
        with patch.dict(os.environ, {'VIDEO_JOB_RECORD': str(self.root), 'VIDEO_JOB_STAGE': 'thumb'}), patch('execution.subprocess.run', side_effect=[OSError(errno.EAGAIN, 'busy'), ok]) as run, patch('execution.time.sleep'):
            self.assertEqual(execution.execute(['probe'], safe_retry=True).stdout, b'ok')
            self.assertEqual(run.call_count, 2)
        self.assertTrue(any(e['kind'] == 'tool_failed' for e in j.history(self.root)))
        with patch('execution.subprocess.run', side_effect=OSError(errno.EAGAIN, 'busy')) as run, patch('execution.time.sleep'):
            with self.assertRaises(OSError):
                execution.execute(['render'])
            self.assertEqual(run.call_count, 1)

    def test_real_timeout_and_nonzero(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            execution.execute([sys.executable, '-c', 'import time; time.sleep(10)'], timeout=.1)
        with patch('execution.subprocess.run', return_value=subprocess.CompletedProcess([], 1, b'', b'invalid')) as run:
            self.assertEqual(execution.execute(['probe'], safe_retry=True).returncode, 1)
            self.assertEqual(run.call_count, 1)

    def test_review_gate_and_stale_evidence(self):
        target = self.root / 'skill.md'; target.write_text('before')
        evidence = self.root / 'review.md'; evidence.write_text('reviewed candidate response')
        event = j.record(self.root, 'feedback', {'failure': 'missing payoff'})
        j.update(self.root, 'propose', {'id': 'P1', 'failure_events': [event['id']], 'target': str(target), 'rationale': 'retain result', 'change': {'before': 'before', 'after': 'after'}, 'cases': ['highlight-payoff']})
        out = self.root / 'eval.json'
        review = {'id': 'highlight-payoff', 'status': 'passed', 'criteria': ['passed', 'passed'], 'reviewer': 'test reviewer', 'notes': 'synthetic gate test only', 'evidence': [str(evidence)]}
        quality.evaluate(self.root, 'P1', [review], out)
        evidence.write_text('changed')
        decision = {'id': 'P1', 'decision': 'accepted', 'reviewer': 'test', 'reason': 'test', 'evaluation': str(out)}
        with self.assertRaises(ValueError):
            j.update(self.root, 'decide', decision)
        evidence.write_text('reviewed candidate response')
        j.update(self.root, 'decide', decision)
        self.assertEqual(target.read_text(), 'before')
        with self.assertRaises(ValueError):
            j.update(self.root, 'decide', decision)


if __name__ == '__main__':
    unittest.main()
