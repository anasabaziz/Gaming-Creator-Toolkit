from pathlib import Path
import shutil
import tempfile
import unittest
import archive_verify as archive


class ArchiveTests(unittest.TestCase):
    def test_copy_missing_corrupt_and_restoration_unverified(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root / 'source'; source.mkdir(); dest = root / 'archive'; dest.mkdir()
            (source / 'clip.txt').write_text('fixture')
            inv = archive.inventory(source)
            self.assertEqual(archive.verify(inv, dest)['copy_status'], 'failed')
            shutil.copy2(source / 'clip.txt', dest / 'clip.txt')
            result = archive.verify(inv, dest)
            self.assertEqual(result['copy_status'], 'passed')
            self.assertEqual(result['restoration'], 'unverified')
            self.assertEqual(result['independent_backup'], 'unverified')
            (dest / 'clip.txt').write_text('bad')
            self.assertEqual(archive.verify(inv, dest)['copy_status'], 'failed')

    def test_external_mlt_reference_and_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root / 'source'; source.mkdir(); dest = root / 'archive'; dest.mkdir()
            media = root / 'outside.mp4'; media.write_text('synthetic')
            project = source / 'edit.mlt'; project.write_text('<mlt><producer><property name="resource">' + media.as_posix() + '</property></producer></mlt>')
            inv = archive.inventory(source)
            for entry in inv['entries']:
                out = dest / entry['destination']; out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(entry['source']['path'], out)
            result = archive.verify(inv, dest)
            self.assertEqual(result['copy_status'], 'passed')
            self.assertEqual(result['dependency_status'], 'unverified')
            inv['entries'][0]['destination'] = '../escape'
            with self.assertRaises(ValueError):
                archive.verify(inv, dest)

    def test_unresolved_resource_prevents_clean_inventory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'edit.mlt').write_text('<mlt><producer><property name="resource">https://example.invalid/video</property></producer></mlt>')
            self.assertTrue(archive.inventory(root)['issues'])


if __name__ == '__main__':
    unittest.main()
