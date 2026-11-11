"""Behavioral tests using temporary, fictional workspaces only."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'optional/dashboard'))
import configure
import install
import check_package
import package
import build_workbook
import job_dashboard
from openpyxl import load_workbook


class ToolkitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='creator-toolkit-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "creator's toolkit 日本語"
        self.root.mkdir()
        self.answers = {'schema_version': 1, 'confirmed': True, 'confirmation': 'Synthetic user confirms choices',
                        'enabled_skills': ['gameplay-highlights'],
                        'profiles': {'creator': '# Fictional channel\nOriginal game sound; no branding.',
                                     'workflow': '# Fictional workflow\nHuman review; dashboard disabled.'}}

    def copy_public(self):
        for source in check_package.public_files(ROOT):
            target = self.root / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    def test_setup_requires_confirmation(self):
        self.assertFalse(configure.status(self.root)['ready'])
        self.answers['confirmed'] = False
        with self.assertRaises(ValueError):
            configure.save(self.root, self.answers)
        self.assertFalse((self.root / '.creator-toolkit').exists())

    def test_profile_changes_need_reconfirmation(self):
        self.assertTrue(configure.save(self.root, self.answers)['ready'])
        profile = self.root / '.creator-toolkit/creator-profile.md'
        profile.write_text('Changed preference', encoding='utf-8')
        self.assertFalse(configure.status(self.root, 'gameplay-highlights')['ready'])
        self.assertTrue(configure.save(self.root, self.answers)['ready'])
        self.assertEqual(len(list((self.root / '.creator-toolkit/history').iterdir())), 1)

    def test_unconfigured_template_rejected(self):
        self.answers['profiles']['creator'] = '# Creator — UNCONFIGURED TEMPLATE'
        with self.assertRaises(ValueError):
            configure.save(self.root, self.answers)

    def test_article_only_and_later_workflow(self):
        self.answers['enabled_skills'] = ['gameplay-articles']
        self.answers['profiles'] = {'site': '# Fictional site\nNo website; local articles.', 'workflow': '# Human verification'}
        self.assertTrue(configure.save(self.root, self.answers)['ready'])
        self.assertFalse((self.root / '.creator-toolkit/creator-profile.md').exists())
        self.assertFalse(configure.status(self.root, 'game-thumbnails')['ready'])
        self.answers['enabled_skills'] = ['game-thumbnails']
        self.answers['profiles'] = {'creator': '# Fictional thumbnail style'}
        configure.save(self.root, self.answers)
        self.assertTrue(configure.status(self.root, 'gameplay-articles')['ready'])
        self.assertTrue(configure.status(self.root, 'game-thumbnails')['ready'])

    def test_installer_preserves_profiles_and_reuses_canonical_sources(self):
        self.copy_public()
        configure.save(self.root, self.answers)
        before = (self.root / '.creator-toolkit/config.json').read_bytes()
        self.assertEqual(len(install.install(self.root, 'all')), 10)
        self.assertEqual(len(install.install(self.root, 'all')), 10)
        self.assertEqual(before, (self.root / '.creator-toolkit/config.json').read_bytes())
        adapter = self.root / '.claude/skills/gameplay-highlights/SKILL.md'
        self.assertTrue((adapter.parent / '../../../skills/gameplay-highlights/SKILL.md').resolve().is_file())
        adapter.write_text('Local customization', encoding='utf-8')
        with self.assertRaises(ValueError):
            install.install(self.root, 'claude')
        self.assertEqual(adapter.read_text(encoding='utf-8'), 'Local customization')

    def test_installer_refuses_unmanaged_skill(self):
        self.copy_public()
        target = self.root / '.agents/skills/gameplay-highlights/SKILL.md'
        target.parent.mkdir(parents=True)
        target.write_text('Existing user skill', encoding='utf-8')
        with self.assertRaises(ValueError):
            install.install(self.root, 'codex')

    def test_public_audit_and_archive_exclude_private_runtime(self):
        self.copy_public()
        configure.save(self.root, self.answers)
        sentinel = uuid.uuid4().hex
        for relative in ('.env', 'jobs/private.mp4', 'tracking/records/private.json', 'reference/article.md'):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(sentinel, encoding='utf-8')
        result = check_package.audit(self.root)
        self.assertEqual(result['errors'], [])
        destination = Path(self.temp.name) / 'candidate.zip'
        package.package(self.root, destination)
        with zipfile.ZipFile(destination) as archive:
            self.assertEqual(len(archive.namelist()), len(check_package.public_files(self.root)))
            self.assertFalse(any(sentinel.encode() in archive.read(n) for n in archive.namelist()))

    def test_allowlist_rejects_escape_and_private_folder(self):
        for bad in ('../escape.md', '.creator-toolkit/config.json', 'jobs/source.mp4'):
            (self.root / 'PACKAGE_FILES.json').write_text(json.dumps([bad]), encoding='utf-8')
            with self.assertRaises(ValueError):
                check_package.public_files(self.root)

    def test_release_requires_original_notice_and_platform_evidence(self):
        self.copy_public()
        # Publication does not waive the license or compatibility release gates.
        license_path = self.root / 'LICENSE'
        original_notice = license_path.read_text(encoding='utf-8')
        license_path.write_text('MIT License\n\nCopyright (c) 2026 [ORIGINAL_GITHUB_UPLOADER]\n', encoding='utf-8')
        errors = check_package.audit(self.root, release=True)['errors']
        self.assertTrue(any('license' in e for e in errors))
        license_path.write_text(original_notice, encoding='utf-8')
        errors = check_package.audit(self.root, release=True)['errors']
        self.assertFalse(any('license' in e for e in errors))
        self.assertTrue(any('Release verification pending' in e for e in errors))


class WorkbookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'dashboard.xlsx'
        self.data = {'refreshed': '2026-01-01T00:00:00Z', 'headers': job_dashboard.HEADERS,
                     'rows': [], 'jobs': [], 'manual': job_dashboard.MANUAL}

    def test_empty_workbook_and_no_formulas(self):
        build_workbook.build(self.data, self.path)
        self.assertIn(job_dashboard.HEADERS, job_dashboard.workbook_rows(self.path))
        wb = load_workbook(self.path)
        self.assertEqual(wb.sheetnames, ['Dashboard', 'Deliverables'])
        self.assertEqual(wb['Dashboard']['B9'].value, 0)
        self.assertFalse(any(c.data_type == 'f' for sheet in wb for row in sheet for c in row))
        wb.close()

    def test_literal_feedback_and_human_fields_roundtrip(self):
        self.data['rows'] = [['Synthetic job', 'thumbnail', 'r1', 'running', 'Pending', 'Pending',
                              'Keep files', '=1+1', 'Inspect the entire image', 'Visual check pending',
                              'Present', 'Pending', 'Yes', '', '', 'synthetic-id']]
        build_workbook.build(self.data, self.path)
        wb = load_workbook(self.path)
        detail = wb['Deliverables']
        self.assertEqual(detail['H6'].data_type, 's')
        self.assertEqual(len(detail.data_validations.dataValidation), 3)
        self.assertEqual(detail['E6'].fill.fgColor.rgb[-6:], build_workbook.YELLOW)
        detail['E6'] = job_dashboard.PASS  # Synthetic owner report, never real user decisions.
        wb.save(self.path)
        wb.close()
        row = job_dashboard.workbook_rows(self.path)[-1]
        self.assertEqual(row[4], job_dashboard.PASS)
        self.assertEqual(row[7], '=1+1')
        self.assertEqual(row[-1], 'synthetic-id')

    def test_dashboard_cli_preserves_owner_decision_after_refresh(self):
        from test_review import fixture
        root = Path(self.temp.name)
        job_parent = root / 'jobs/synthetic-game'
        job_parent.mkdir(parents=True)
        fixture(job_parent)
        command = [sys.executable, str(ROOT / 'optional/dashboard/job_dashboard.py'), '--root', str(root)]
        first = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        workbook = root / 'tracking/Creator Job Dashboard.xlsx'
        wb = load_workbook(workbook)
        key = wb['Deliverables']['P6'].value
        wb['Deliverables']['E6'] = job_dashboard.PASS
        wb['Deliverables']['H6'] = 'Synthetic complete inspection for integration test.'
        wb.save(workbook)
        wb.close()
        second = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(second.returncode, 0, second.stderr)
        records = json.loads((root / 'tracking/records/index.json').read_text(encoding='utf-8'))
        self.assertEqual(records[key]['human'], job_dashboard.PASS)
        self.assertEqual(len(records[key]['history']), 1)
        self.assertTrue(list((root / 'tracking/records/attestations').glob('*.xlsx')))
        third = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(third.returncode, 0, third.stderr)
        records = json.loads((root / 'tracking/records/index.json').read_text(encoding='utf-8'))
        self.assertEqual(len(records[key]['history']), 1)


if __name__ == '__main__':
    unittest.main()
