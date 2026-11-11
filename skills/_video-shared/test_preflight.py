import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import preflight
import job_state as j
from test_review import fixture, producer_reviews


class PreflightTests(unittest.TestCase):
    def test_no_perception_inferred_from_tools(self):
        with patch('preflight.shutil.which', return_value=None):
            result = preflight.assess({'tools': ['ffmpeg']})
        self.assertEqual(result['probes']['ffmpeg']['status'], 'unavailable')
        self.assertEqual(result['capabilities'], {})

    def test_available_requires_evidence(self):
        with self.assertRaises(ValueError):
            preflight.assess({'capabilities': {'listening': {'status': 'available', 'method': 'claimed', 'notes': 'no evidence'}}})

    def test_unknown_capability_blocks_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); job, evidence, _, _ = fixture(root)
            report = root / 'unknown.json'
            report.write_text(json.dumps(preflight.assess({'capabilities': {'visual': {'status': 'unknown', 'method': 'none', 'notes': 'unavailable in session'}}})))
            j.update(job, 'preflight', {'id': 'P2', 'path': str(report)})
            c = j.snapshot(job)['contracts']['C1']; c['id'] = 'C2'; c['preflight'] = 'P2'
            j.update(job, 'contract', c)
            j.update(job, 'stage', {'id': 'thumb', 'status': 'running', 'contract': 'C2'})
            for check in j.snapshot(job)['contracts']['C2']['checks']:
                with self.assertRaisesRegex(ValueError, 'capability is unavailable'):
                    j.update(job, 'review', {'id': check['id'], 'contract': 'C2', 'check': check['id'], 'role': 'producer', 'reviewer': 'test', 'status': 'passed', 'method': check['methods'][0], 'coverage': 'fixture', 'notes': 'fixture', 'evidence': [str(evidence)]})
            self.assertFalse(j.snapshot(job).get('reviews'))
            with self.assertRaisesRegex(ValueError, 'producer check missing'):
                j.update(job, 'stage', {'id': 'thumb', 'status': 'completed'})


if __name__ == '__main__':
    unittest.main()
