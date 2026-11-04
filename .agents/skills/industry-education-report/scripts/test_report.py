"""Regression tests for evidence integrity and misleading completeness signals."""
import copy
import json
from pathlib import Path
import unittest
import report

class ReportTests(unittest.TestCase):
    def setUp(self):
        self.d=json.loads((Path(__file__).resolve().parents[1]/'assets/examples/observation/report.json').read_text())
    def test_valid_sample_is_not_complete(self):
        result=report.validate(self.d)
        self.assertTrue(result['structure_pass'])
        self.assertFalse(result['decision_data_complete'])
    def test_missing_evidence(self):
        self.d['claims'][0]['source_ids']=[]
        self.d['claims'][0]['metric_ids']=[]
        self.assertFalse(report.validate(self.d)['structure_pass'])
    def test_missing_section(self):
        self.d['sections'].pop()
        self.assertFalse(report.validate(self.d)['structure_pass'])
    def test_blank_source(self):
        self.d['sources'][0]['publisher']='  '
        self.assertFalse(report.validate(self.d)['structure_pass'])
    def test_future_access(self):
        self.d['sources'][0]['accessed']='2099-01-01'
        self.assertFalse(report.validate(self.d)['structure_pass'])
    def test_finite(self):
        self.d['metrics'][0]['value']=float('nan')
        self.assertFalse(report.validate(self.d)['structure_pass'])
    def test_final_with_gaps(self):
        self.d['status']='final'
        self.assertFalse(report.validate(self.d)['structure_pass'])
    def test_wrong_derivation_scope(self):
        m=self.d['metrics'][0]
        m.update(price_basis='不适用',comparable_group='在招岗位')
        n=copy.deepcopy(m)
        n.update(id='DERIVED',region='北京市',value=m['value'],derived={'inputs':[m['id']],'operation':'sum'})
        self.d['metrics'].append(n)
        self.d['charts'][0]['metric_ids'].append('DERIVED')
        self.assertFalse(report.validate(self.d)['structure_pass'])
    def test_cycle(self):
        m=self.d['metrics'][0]
        m.update(price_basis='不适用',comparable_group='在招岗位',derived={'inputs':[m['id']],'operation':'sum'})
        self.assertFalse(report.validate(self.d)['structure_pass'])
    def test_local_doc_source_url(self):
        self.assertEqual(self.d['sources'][0]['url'],'references/05-数据库字段摸底与口径.md')
        self.assertTrue(report.validate(self.d)['structure_pass'])
    def test_delivery_changes(self):
        original=report.render(self.d)
        modified=copy.deepcopy(self.d)
        modified['claims'][0]['text']+='额外结论'
        self.assertNotEqual(original,report.render(modified))

if __name__=='__main__':
    unittest.main()
