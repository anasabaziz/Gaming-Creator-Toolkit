"""Integration checks using isolated synthetic media; no user recordings modified."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import array

spec = importlib.util.spec_from_file_location('pipeline', Path(__file__).with_name('pipeline.py'))
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (Path.cwd() / 'tmp').mkdir(exist_ok=True)
        cls.root = Path(tempfile.mkdtemp(prefix='video-workflow-test-', dir=Path.cwd() / 'tmp'))
        cls.source = cls.root / "source with spaces and ' apostrophe.mkv"
        p.run([p.tool('ffmpeg'), '-v', 'error', '-n', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=30',
               '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-f', 'lavfi', '-i', 'sine=frequency=880:sample_rate=48000',
               '-t', '4', '-map', '0:v', '-map', '1:a', '-map', '2:a', '-c:v', 'ffv1', '-c:a', 'pcm_s16le', cls.source])

    def test_recording_only_trailer(self):
        parent = self.root / 'source-only'
        p.init(self.source, parent)
        selections = self.root / 'direct-selections.json'
        p.write(selections, [{'in': .2, 'out': 1.2, 'reason': 'Synthetic source-only selection'}])
        destination = self.root / 'direct-trailer'
        p.derive(parent / 'manifest.json', destination, 'trailer', selections=selections)
        manifest = destination / 'manifest.json'
        p.render(manifest)
        self.assertEqual(p.validation(manifest)[0]['integrity'], 'passed')

    def test_workflows(self):
        job = self.root / 'highlights'; m = p.init(self.source, job); m['audio_stream'] = 2
        m['outputs'] = [dict(id='C01', kind='highlight', segments=[{'in': 0, 'out': 1, 'reason': 'first'}]),
                        dict(id='C02', kind='highlight', segments=[{'in': 2, 'out': 3, 'reason': 'second'}])]
        manifest = job / 'manifest.json'; p.write(manifest, m)
        p.render(manifest); checks = p.validation(manifest); p.report(manifest)
        self.assertEqual([x['integrity'] for x in checks], ['passed', 'passed'])
        self.assertTrue(all(x['project_agreement'] == 'passed' for x in checks))
        old_state = p.read(job / 'render-state.json')
        # The second audio track is 880 Hz; verify selection rather than just stream presence.
        raw = p.run([p.tool('ffmpeg'), '-v','error','-i',old_state['outputs'][0]['mp4'],'-t','0.5','-vn','-ac','1','-ar','48000','-f','s16le','-'])
        pcm = array.array('h',raw)
        crossings = sum(a <= 0 < b for a,b in zip(pcm,pcm[1:]))
        self.assertTrue(420 <= crossings <= 460, crossings)
        mtimes = [Path(x['mp4']).stat().st_mtime_ns for x in old_state['outputs']]
        hits = p.METRICS['cache_hits']; p.render(manifest); p.validation(manifest)
        self.assertGreater(p.METRICS['cache_hits'], hits)
        self.assertEqual(mtimes, [Path(x['mp4']).stat().st_mtime_ns for x in old_state['outputs']])
        m['outputs'][0]['segments'][0]['reason'] = 'Improved wording without changing edit'
        p.write(manifest,m);p.render(manifest)
        self.assertEqual(old_state['outputs'][0]['mp4'],p.read(job/'render-state.json')['outputs'][0]['mp4'])
        # Changed selection creates a revision while retaining the unaffected output and old deliverable.
        m['outputs'][0]['segments'][0]['out'] = .8; p.write(manifest, m); p.render(manifest)
        new_state = p.read(job / 'render-state.json')
        self.assertNotEqual(new_state['outputs'][0]['mp4'], old_state['outputs'][0]['mp4'])
        self.assertEqual(new_state['outputs'][1]['mp4'], old_state['outputs'][1]['mp4'])
        self.assertTrue(Path(old_state['outputs'][0]['mp4']).exists())
        # Chronological trailer reuses source ranges; explicit reverse order is rejected.
        trailer = self.root / 'trailer'; p.derive(manifest, trailer, 'trailer')
        tm = trailer / 'manifest.json'; p.render(tm); p.validation(tm)
        bad = p.read(tm); bad['outputs'][0]['segments'].reverse()
        with self.assertRaisesRegex(ValueError, 'Chronological'):
            p.validate_manifest(bad)
        # Single portrait crop and synchronized stacked panels, preserving timing.
        for name, layout in [('crop', {'type':'crop','rect':[108,0,102,180]}),
                             ('stack', {'type':'stack','panels':[{'rect':[60,0,202,180],'height':960},{'rect':[100,0,202,180],'height':960}]})]:
            layouts = self.root / (name + '.json')
            p.write(layouts, {'trailer':[layout, layout]})
            dest = self.root / name
            p.derive(tm, dest, 'vertical', layout=layouts, authorization='Integration test requested portrait layout')
            vm = dest / 'manifest.json'; vertical = p.read(vm)
            # Smaller test output with geometrically equivalent panel heights.
            vertical['format'].update(width=180,height=320)
            if name == 'stack':
                for s in vertical['outputs'][0]['segments']:
                    for panel in s['layout']['panels']: panel['height'] = 160
            p.write(vm, vertical); p.render(vm); p.validation(vm)
            self.assertEqual(p.read(dest/'render-state.json')['outputs'][0]['frames'], p.read(trailer/'render-state.json')['outputs'][0]['frames'])
        # Missing review evidence must be regenerated, not treated as a cache hit.
        record = Path(p.read(trailer/'render-state.json')['outputs'][0]['mp4']).parent/'validation.json'
        evidence = Path(p.read(record)['project_agreement']['evidence'][0]['path']); evidence.unlink()
        p.validation(tm); self.assertTrue(evidence.exists())
        # Modified export is protected rather than silently overwritten.
        modified = Path(new_state['outputs'][0]['mp4'])
        with modified.open('ab') as f: f.write(b'tampered')
        with self.assertRaisesRegex(ValueError, 'protected'):
            p.render(manifest)

    def test_vfr_and_interrupted_resume(self):
        source=self.root/'variable-frame-rate.mkv'
        p.run([p.tool('ffmpeg'),'-v','error','-n','-i',self.source,'-vf',"select='if(lt(t,2),not(mod(n,2)),1)'",'-fps_mode','vfr','-an','-c:v','ffv1',source])
        job=self.root/'vfr';m=p.init(source,job);m['format']['fps']='30'
        m['outputs']=[{'id':'vfr','segments':[{'in':.2,'out':1.2},{'in':2.2,'out':3.2}]}]
        manifest=job/'manifest.json';p.write(manifest,m)
        original=p.run
        def fail_final(args, **kwargs):
            if 'concat' in args: raise RuntimeError('Simulated interruption before final encode')
            return original(args, **kwargs)
        with patch.object(p,'run',fail_final):
            with self.assertRaisesRegex(RuntimeError,'Simulated'):p.render(manifest)
        media=list((job/'media').glob('*.mkv'));self.assertEqual(len(media),2)
        saved=[x.stat().st_mtime_ns for x in media]
        p.render(manifest);p.validation(manifest)
        self.assertEqual(saved,[x.stat().st_mtime_ns for x in media])
        state=p.read(job/'render-state.json');self.assertEqual(state['outputs'][0]['frames'],60)

    def test_safety_and_inspection(self):
        result = p.inspect(self.source, self.root/'inspection', 0, 3, 1)
        self.assertEqual(result['samples'], 3)
        self.assertTrue(Path(result['sheets'][0]).exists())
        with self.assertRaises(ValueError): p.layout_filter({'type':'crop','rect':[300,0,100,180]},320,180,100,180)
        with self.assertRaises(ValueError): p.layout_filter({'type':'full'},320,180,180,320)
        job = self.root/'silent'; m=p.init(self.source,job)
        m['outputs']=[{'id':'silent','audio':'silent','segments':[{'in':0,'out':.5}]}]
        manifest=job/'manifest.json';p.write(manifest,m);p.render(manifest);p.validation(manifest)
        self.assertFalse(p.read(job/'render-state.json')['outputs'][0]['audio_expected'])
        with p.lock(job):
            with self.assertRaises(ValueError):
                with p.lock(job): pass
        m['source_identity']['size'] += 1
        with self.assertRaisesRegex(ValueError,'identity changed'): p.validate_manifest(m)
        protected=self.root/'existing-legacy-job';protected.mkdir();(protected/'source-info.json').write_text('preserve me')
        with self.assertRaisesRegex(ValueError,'protected'):p.init(self.source,protected)
        self.assertEqual((protected/'source-info.json').read_text(),'preserve me')
        # Import legacy selections into a separate job without touching original records.
        old=self.root/'legacy.json';p.write(old,{'source':str(self.source),'clips':[{'id':'C01','start':0,'end':1}]})
        before=old.read_bytes();p.legacy(old,self.root/'imported');self.assertEqual(old.read_bytes(),before)
        self.assertEqual(p.read(self.root/'imported/manifest.json')['outputs'][0]['segments'][0]['out'],1)


class JournalReportTests(unittest.TestCase):
    def test_report_uses_journal_and_detects_changed_evidence(self):
        import os
        from test_review import fixture, producer_reviews
        import job_state as j
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); journal, evidence, art, _ = fixture(root)
            producer_reviews(journal, evidence)
            j.update(journal, 'stage', {'id': 'thumb', 'status': 'completed'})
            video = root / 'report-fixture'; video.mkdir()
            m = {'outputs': [{'id': 'fixture', 'segments': []}]}
            manifest = video / 'manifest.json'; p.write(manifest, m)
            p.write(video / 'render-state.json', {'manifest': p.digest(m), 'outputs': [{'mp4': str(art), 'project': str(art)}]})
            with patch.dict(os.environ, {'VIDEO_JOB_RECORD': str(journal)}):
                p.report(manifest)
                self.assertIn('Producer checks satisfied', (video / 'report.md').read_text())
                evidence.write_text('modified')
                p.report(manifest)
                self.assertIn('stale review evidence', (video / 'report.md').read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
