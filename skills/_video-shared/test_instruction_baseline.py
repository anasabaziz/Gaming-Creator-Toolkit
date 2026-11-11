import tempfile
from pathlib import Path
import unittest
import job_state as j
from test_review import fixture, producer_reviews


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.job, self.evidence, self.art, self.instructions = fixture(Path(self.temp.name))
        producer_reviews(self.job, self.evidence)

    def test_changed_instructions_need_specific_assessment(self):
        self.instructions.write_text('new instructions')
        with self.assertRaisesRegex(ValueError, 'baseline changed'):
            j.update(self.job, 'stage', {'id': 'thumb', 'status': 'completed'})
        j.update(self.job, 'baseline_assessment', {'id': 'A1', 'baseline': 'B1', 'decision': 'retain', 'reason': 'Synthetic no-impact example', 'source': 'test'})
        j.update(self.job, 'stage', {'id': 'thumb', 'status': 'completed'})
        self.instructions.write_text('another change')
        with self.assertRaises(ValueError):
            j.update(self.job, 'stage', {'id': 'thumb', 'status': 'completed'})

    def test_snapshot_damage_cannot_be_waived(self):
        saved = j.snapshot(self.job)['baselines']['B1']['files'][0]['snapshot']['path']
        Path(saved).write_text('damaged')
        with self.assertRaisesRegex(ValueError, 'damaged'):
            j.update(self.job, 'baseline_assessment', {'id': 'A1', 'baseline': 'B1', 'decision': 'retain', 'reason': 'test', 'source': 'test'})

    def test_secret_snapshot_refused(self):
        with self.assertRaises(ValueError):
            j.update(self.job, 'baseline', {'id': 'B2', 'files': ['.env'], 'requirements_source': 'test'})


if __name__ == '__main__':
    unittest.main()
