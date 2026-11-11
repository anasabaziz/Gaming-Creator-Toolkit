"""Synthetic tests only. Never edits real user review decisions or media."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import job_dashboard as d
from test_review import fixture


def book(path, rows):
    ns = d.NS['s']
    sheet = ET.Element('worksheet', xmlns=ns)
    data = ET.SubElement(sheet, 'sheetData')
    for ri, values in enumerate([d.HEADERS, *rows], 1):
        row = ET.SubElement(data, 'row', r=str(ri))
        for ci, value in enumerate(values):
            c = ET.SubElement(row, 'c', r=chr(65+ci)+str(ri), t='inlineStr')
            ET.SubElement(ET.SubElement(c, 'is'), 't').text = str(value)
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('xl/workbook.xml', '<workbook xmlns="'+ns+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Deliverables" r:id="r1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml', ET.tostring(sheet))


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        base = self.root / 'reports/example'
        base.mkdir(parents=True)
        self.job, self.evidence, self.art, self.instructions = fixture(base)
        self.tracking = self.root / 'tracking'
        self.tracking.mkdir()
        self.config = {'scan_folders': ['reports']}
        self.records = {}
        self.collect()
        self.record = next(iter(self.records.values()))
        self.workbook = self.tracking / 'test.xlsx'

    def collect(self):
        d.collect(self.root, self.records, self.config)

    def edit(self, field, value):
        rows = [d.row_values(r) for r in self.records.values()]
        for r, row in zip(self.records.values(), rows):
            r['exported_row'] = row.copy()
        col = next(k for k, v in d.EDIT.items() if v == field)
        rows[0][col] = value
        book(self.workbook, rows)
        d.import_edits(self.workbook, self.records, self.tracking)
        d.sync_pending(self.records, self.tracking)

    def test_pass_registers_checks_completes_and_is_idempotent(self):
        self.edit('human', d.PASS)
        state = d.job_state.snapshot(self.job)
        self.assertEqual(state['stages']['thumb']['status'], 'completed')
        self.assertEqual(len(state['reviews']), 3)
        self.assertTrue(all(r['role'] == 'human_verifier' for r in state['reviews'].values()))
        self.assertFalse(state.get('acceptances'))
        sequence = len(d.job_state.history(self.job))
        # Retry after a crash before the index's sync receipt was saved.
        self.record['history'][0]['journal_synced'] = False
        d.sync_pending(self.records, self.tracking)
        self.assertEqual(len(d.job_state.snapshot(self.job)['reviews']), 3)
        self.assertLessEqual(len(d.job_state.history(self.job)), sequence+1)

    def test_retraction_does_not_leave_current_pass(self):
        self.edit('human', d.PASS)
        self.edit('human', 'Pending')
        state = d.job_state.snapshot(self.job)
        self.assertEqual(state['stages']['thumb']['status'], 'awaiting_review')
        self.assertTrue(d.review.evaluate(state, state['stages']['thumb']))

    def test_changed_target_does_not_receive_pass(self):
        self.art.write_text('changed bytes')
        self.edit('human', d.PASS)
        self.assertFalse(d.job_state.snapshot(self.job).get('reviews'))
        self.assertIn('missing or changed', self.record['sync'])

    def test_removed_job_retains_history_and_availability(self):
        self.edit('human', d.PASS)
        oldid = self.record['id']
        original = self.root / 'reports'
        original.rename(self.root / 'removed-reports')
        self.collect()
        self.assertIn(oldid, self.records)
        self.assertEqual(self.records[oldid]['human'], d.PASS)
        self.assertIn('Files missing', self.records[oldid]['availability'])

    def test_revised_contract_gets_pending_row(self):
        self.edit('human', d.PASS)
        state = d.job_state.snapshot(self.job)
        contract = copy.deepcopy(state['contracts']['C1'])
        contract['id'] = 'C2'
        contract['checks'][0]['criterion'] = 'New requirement'
        d.job_state.update(self.job, 'contract', contract)
        d.job_state.update(self.job, 'stage', {'id':'thumb','status':'awaiting_review','contract':'C2'})
        self.collect()
        current = [r for r in self.records.values() if r['current']]
        self.assertEqual(len(self.records), 2)
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]['human'], 'Pending')

    def test_sort_preserves_edits_by_id(self):
        state = d.job_state.snapshot(self.job)
        c = copy.deepcopy(state['contracts']['C1'])
        c.update(id='C2',stage='another')
        d.job_state.update(self.job,'contract',c)
        d.job_state.update(self.job,'stage',{'id':'another','status':'awaiting_review','contract':'C2','artifacts':['a1']})
        self.collect()
        rows = [d.row_values(r) for r in self.records.values()]
        for r,row in zip(self.records.values(),rows): r['exported_row']=row.copy()
        rows.reverse()
        target=rows[0][-1]
        rows[0][7]='Sorted feedback'
        book(self.workbook, rows)
        d.import_edits(self.workbook,self.records,self.tracking)
        self.assertEqual(self.records[target]['feedback'],'Sorted feedback')

    def test_invalid_edit_is_rejected_before_any_import(self):
        row=d.row_values(self.record)
        self.record['exported_row']=row.copy()
        row[8]='Altered checklist'; row[4]=d.PASS
        book(self.workbook,[row])
        with self.assertRaisesRegex(ValueError,'Generated cells'):
            d.import_edits(self.workbook,self.records,self.tracking)
        self.assertEqual(self.record['human'],'Pending')

    def test_missing_automated_check_cannot_be_passed_by_human(self):
        state=d.job_state.snapshot(self.job)
        c=copy.deepcopy(state['contracts']['C1']); c['id']='C2'
        c['checks'].append({'id':'technical','criterion':'Automated test','targets':['a1']})
        d.job_state.update(self.job,'contract',c)
        d.job_state.update(self.job,'stage',{'id':'thumb','status':'awaiting_review','contract':'C2'})
        self.collect()
        self.records={k:r for k,r in self.records.items() if r['current']}
        self.record=next(iter(self.records.values()))
        self.edit('human',d.PASS)
        state=d.job_state.snapshot(self.job)
        self.assertNotEqual(state['stages']['thumb']['status'],'completed')
        self.assertFalse(any(r['check']=='technical' for r in state['reviews'].values()))
        self.assertIn('technical',self.record['sync'])

    def test_acceptance_separate_from_review(self):
        self.edit('human',d.PASS)
        self.edit('acceptance','Accepted')
        self.assertEqual(d.job_state.snapshot(self.job)['acceptances'][-1]['decision'],'accepted')

    def test_deferred_acceptance_retries_after_delivery_only(self):
        self.edit('acceptance', 'Accepted')
        event = self.record['history'][0]
        self.assertFalse(event['journal_synced'])
        self.assertEqual(event['sync_status'], 'waiting_for_delivery')
        with patch.object(d, 'sync_event', side_effect=AssertionError('unchanged retry')):
            d.sync_pending(self.records, self.tracking)
        d.job_state.update(self.job, 'delivery', {'stage': 'thumb', 'contract': 'C1', 'source': 'fixture delivery'})
        d.sync_pending(self.records, self.tracking)
        self.assertTrue(event['journal_synced'])
        self.assertEqual(d.job_state.snapshot(self.job)['acceptances'][-1]['decision'], 'accepted')

    def test_sync_failure_waits_for_changed_evidence(self):
        with patch.object(d, 'sync_event', side_effect=ValueError('fixture fault')) as apply:
            self.edit('human', d.PASS)
            d.sync_pending(self.records, self.tracking)
            self.assertEqual(apply.call_count, 1)
        self.evidence.write_text('changed fixture condition')
        with patch.object(d, 'sync_event', side_effect=ValueError('fixture fault')) as apply:
            d.sync_pending(self.records, self.tracking)
            self.assertEqual(apply.call_count, 1)

    def test_legacy_deferred_receipt_is_reopened(self):
        self.edit('acceptance', 'Accepted')
        event = self.record['history'][0]
        event['journal_synced'] = True
        event.pop('sync_status')
        d.job_state.update(self.job, 'delivery', {'stage': 'thumb', 'contract': 'C1', 'source': 'fixture delivery'})
        d.sync_pending(self.records, self.tracking)
        self.assertEqual(event['sync_status'], 'applied')
        self.assertEqual(d.job_state.snapshot(self.job)['acceptances'][-1]['decision'], 'accepted')
    def test_current_conditions_include_later_blocker(self):
        self.edit('human', d.PASS)
        d.job_state.update(self.job, 'plan', {'issues': [{'stage': 'thumb', 'blocking': True}]})
        self.collect()
        self.assertIn('blocking', self.record['other'])

    def test_recovered_original_can_be_excluded(self):
        self.config['excluded_journals'] = [str(self.job)]
        records = {}
        d.collect(self.root, records, self.config)
        self.assertEqual(records, {})

    def test_article_human_checks_supported(self):
        state=d.job_state.snapshot(self.job)
        c={'id':'Article','stage':'article','kind':'article','baseline':'B1','preflight':'P1',
           'artifacts':['a1'],'checks':[{'id':k,'criterion':'Synthetic '+k,'targets':['a1']}
                                      for k in ('claims','package','screenshots','seo')]}
        d.job_state.update(self.job,'contract',c)
        d.job_state.update(self.job,'stage',{'id':'article','status':'awaiting_review','contract':'Article','artifacts':['a1']})
        self.collect()
        self.records={k:r for k,r in self.records.items() if r['stage']=='article'}
        self.record=next(iter(self.records.values()))
        self.edit('human',d.PASS)
        self.assertEqual(d.job_state.snapshot(self.job)['stages']['article']['status'],'completed')

    def test_existing_human_reports_import_without_new_attestation(self):
        self.edit('human',d.PASS)
        imported={}
        d.collect(self.root,imported,self.config)
        row=next(iter(imported.values()))
        self.assertEqual(row['human'],d.HISTORICAL)
        self.assertFalse(row['history'])

    def test_deleted_workbook_row_is_not_silently_lost(self):
        book(self.workbook,[])
        with self.assertRaisesRegex(ValueError,'Rows removed'):
            d.import_edits(self.workbook,self.records,self.tracking)

    def test_modified_evidence_is_not_registered(self):
        row=d.row_values(self.record);self.record['exported_row']=row.copy();row[4]=d.PASS
        book(self.workbook,[row])
        d.import_edits(self.workbook,self.records,self.tracking)
        Path(self.record['history'][0]['workbook']['path']).write_bytes(b'changed')
        d.sync_pending(self.records,self.tracking)
        self.assertFalse(d.job_state.snapshot(self.job).get('reviews'))
        self.assertIn('Sync pending',self.record['sync'])


if __name__ == '__main__':
    unittest.main()
