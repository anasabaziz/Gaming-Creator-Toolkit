"""Regressions for acceptance, human handoff, helpers and honest progress."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json
import job_state as j
import review
import job_helpers as h
import pipeline as p
from test_review import fixture


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.job,self.evidence,self.art,_=fixture(self.root)

    def deliver(self):
        return j.update(self.job,'delivery',{'stage':'thumb','contract':'C1','source':'Delivered synthetic r1'})

    def test_acceptance_closure_without_verification(self):
        data={'stage':'thumb','contract':'C1','acceptor':'user','source':'Looks good','decision':'accepted'}
        with self.assertRaisesRegex(ValueError,'delivery'):j.update(self.job,'acceptance',data)
        self.deliver()
        state=j.update(self.job,'acceptance',data)
        self.assertTrue(state['acceptances'][-1]['outstanding_at_recording'])
        self.assertEqual(state['stages']['thumb']['status'],'running')
        j.update(self.job,'closure',{**data,'decision':'closed','source':'All jobs completed'})
        self.assertFalse(j.snapshot(self.job).get('reviews'))
        with self.assertRaises(ValueError):j.update(self.job,'stage',{'id':'thumb','status':'completed'})
        self.art.write_text('changed')
        with self.assertRaises(ValueError):j.update(self.job,'acceptance',data)

    def test_revision_does_not_inherit_delivery(self):
        self.deliver()
        c=j.snapshot(self.job)['contracts']['C1'];c['id']='C2';j.update(self.job,'contract',c)
        j.update(self.job,'stage',{'id':'thumb','status':'running','contract':'C2'})
        with self.assertRaisesRegex(ValueError,'delivery'):
            j.update(self.job,'review_choice',{'stage':'thumb','contract':'C2','choice':'human_sufficient','source':'user'})

    def test_status_does_not_hash(self):
        with patch('job_state.identity',side_effect=AssertionError('status hashed media')):
            self.assertEqual(j.compact_status(self.job)['integrity'],'not_checked')

    def test_human_report_only_satisfies_named_check(self):
        data={'id':'H1','contract':'C1','check':'visual','role':'human_verifier','reviewer_type':'human',
              'reviewer':'user','source':'Actual synthetic human report','status':'passed','method':'visual_inspection',
              'coverage':'whole image','notes':'Synthetic evidence only','evidence':[str(self.evidence)]}
        state=j.update(self.job,'review',data)
        issues=review.evaluate(state,state['stages']['thumb'])
        self.assertFalse(any(x.startswith('visual:') for x in issues))
        self.assertTrue(any(x.startswith('coverage:') for x in issues))
        self.art.write_text('new revision')
        self.assertTrue(any('stale' in x for x in review.evaluate(state,state['stages']['thumb'])))

    def test_sparse_audio_and_unknown_capability(self):
        c=j.snapshot(self.job)['contracts']['C1'];c['id']='C2'
        c['checks'].append({'id':'audio','criterion':'Entire soundtrack','targets':['a1']})
        j.update(self.job,'contract',c)
        data={'id':'A1','contract':'C2','check':'audio','role':'producer','reviewer':'test','status':'passed',
              'method':'listening','coverage':'sample','notes':'synthetic','evidence':[str(self.evidence)]}
        with self.assertRaisesRegex(ValueError,'capability'):j.update(self.job,'review',data)
        data.update(role='human_verifier',reviewer_type='human',source='Human listened to a sample',coverage_scope='sample')
        with self.assertRaisesRegex(ValueError,'samples'):j.update(self.job,'review',data)
        data.update(coverage_scope='entire_artifact',coverage='entire synthetic artifact',source='Human reports complete listen')
        j.update(self.job,'review',data)

    def test_helpers_utf8_resume_budget_coverage(self):
        instructions=self.root/'指示.md';instructions.write_text('Café 骷髅',encoding='utf-8')
        config={'journal':str(self.root/'记录'),'instructions':[str(instructions)],'requirements_source':'user',
                'requirements':[{'text':'骷髅','source':'user'}]}
        self.assertEqual(h.bootstrap(config),h.bootstrap(config))
        with self.assertRaises(ValueError):h.bootstrap({**config,'instructions':['bad.json']})
        budget=h.frame_budget(60,'60000/1001',[2,3,4,1])
        self.assertEqual(sum(budget['frames']),3596)
        o={'segments':[{}],'feature_coverage':[{'feature':'upgrade','origin':'user_required','source':'user','disposition':'dropped','reason':'portrait'}]}
        with self.assertRaisesRegex(ValueError,'Required feature'):h.coverage_check(o)
        o['feature_coverage'][0]['origin']='producer_selected';h.coverage_check(o)
        config={'journal':str(self.job),'stage':'thumb','contract':'C1','source':'Delivered', 'artifacts':[{'id':'a1','path':str(self.art)}]}
        h.deliver(config);h.deliver(config)
        self.assertEqual(len(j.snapshot(self.job)['deliveries']),1)

    def test_progress_failure_is_not_completion(self):
        with patch('pipeline.run',side_effect=RuntimeError('synthetic failure')):
            with self.assertRaises(RuntimeError):p.phase_run([],self.root,'encode')
        self.assertEqual(p.read(self.root/'status.json')['state'],'interrupted_or_failed')


if __name__=='__main__':unittest.main()
