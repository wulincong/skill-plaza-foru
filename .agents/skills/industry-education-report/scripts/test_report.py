"""Regression tests for evidence integrity and misleading completeness signals."""
import copy
import json
from pathlib import Path
import unittest
import report
from unittest.mock import patch

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
    def test_only_affirmative_choice_releases_a_limited_report(self):
        for message, quote in [
            ('不要按现有证据继续，我先补材料','按现有证据继续'),
            ('暂时不按现有证据继续','按现有证据继续'),
            ('我选扩大范围，请扩大到园区','扩大到园区'),
            ('先补充材料，再继续','继续'),
            ('按现有证据继续？','按现有证据继续'),
            ('按现有证据继续，但我改为先补充材料','按现有证据继续'),
        ]:
            with self.subTest(message=message):
                self.assertFalse(report.chose_limited(message,quote,True))
        self.assertTrue(report.chose_limited('按现有证据继续，注明开班未决。','按现有证据继续',True))
        self.assertFalse(report.chose_limited('继续','继续',False))
        self.assertTrue(report.chose_limited('3','3',True,3))
        self.assertFalse(report.chose_limited('2','2',True,3))

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
        self.d['claims'][0]['metric_ids'].append('DERIVED')
        self.assertFalse(report.validate(self.d)['structure_pass'])
    def test_cycle(self):
        m=self.d['metrics'][0]
        m.update(price_basis='不适用',comparable_group='在招岗位',derived={'inputs':[m['id']],'operation':'sum'})
        self.assertFalse(report.validate(self.d)['structure_pass'])
    def test_local_doc_source_url(self):
        self.assertEqual(self.d['sources'][0]['url'],'references/05-数据库字段摸底与口径.md')
        self.assertTrue(report.validate(self.d)['structure_pass'])
    def test_delivery_changes(self):
        original=report.compose_markdown(self.d)
        modified=copy.deepcopy(self.d)
        modified['claims'][0]['text']+='额外结论'
        self.assertNotEqual(original,report.compose_markdown(modified))

    def test_citation_spacing_does_not_change_numbers_or_word_boundaries(self):
        self.assertEqual(report.excerpt_text('新增一个 18 人的班'), report.excerpt_text('新增一个18人的班'))
        self.assertNotEqual(report.excerpt_text('新增一个 1 8 人的班'), report.excerpt_text('新增一个18人的班'))
        self.assertNotEqual(report.excerpt_text('新增一个 20 人的班'), report.excerpt_text('新增一个18人的班'))
        self.assertNotEqual(report.excerpt_text('the rapist'), report.excerpt_text('therapist'))

    def full_report(self):
        source = self.d['sources'][0]['id']
        self.d.update(edition='full', metrics=[], gaps=[], decision={
            'reader':'专业负责人', 'question':'本期能否增班？', 'critical_gap_ids':[],
            'evidence_checks':[{'topic':topic,'status':'supported','reason':'依据排课材料判断本期容量。',
                                'source_ids':[source]} for topic in ['scope','demand','feasibility']]})
        self.d['claims'] = [dict(id='C',kind='inference',text='本期暂缓增班。',basis='唯一场地已排满。',
                                 implication='先核实替代场地。',limitation='只判断本期。',source_ids=[source]),
                            dict(id='A',kind='recommendation',text='核实下期场地。',basis='本期已满。',
                                 implication='形成下期安排。',limitation='不代表批准。',source_ids=[source],
                                 owner='教务处',next_step='核对下期课表',condition='排课前',verification='确认工位与班额')]
        self.d['sections'] = [dict(id=s['id'],claim_ids=['A' if s['id']=='F08' else 'C'],gap_ids=[])
                              for s in report.templates()['full']['sections']]
        return self.d

    def test_full_report_requires_conditions_and_action_not_just_summary(self):
        d = self.full_report()
        self.assertTrue(report.validate(d)['structure_pass'])
        d['sections'][7]['claim_ids'] = ['C']
        self.assertFalse(report.validate(d)['structure_pass'])
        d['sections'][7]['claim_ids'] = ['A']
        del d['claims'][1]['verification']
        self.assertFalse(report.validate(d)['structure_pass'])

    def test_quantified_user_material_is_preserved_as_data(self):
        d = self.full_report()
        d['claims'][0].update(kind='fact',text='实训室有20个工位。')
        self.assertFalse(report.validate(d)['structure_pass'])
        d['metrics'] = [dict(id='M',label='工位数',value=20,unit='个',period='本期',region='本校',
                             population='实训室',definition='材料登记的工位数',source_ids=d['claims'][0]['source_ids'])]
        d['claims'][0]['metric_ids'] = ['M']
        self.assertTrue(report.validate(d)['structure_pass'])

    def test_missing_feasibility_cannot_be_cleared_by_expanding_region(self):
        d = self.full_report()
        d['gaps'] = [dict(id='G',description='校内条件未知',owner='教务处',required_data='排课表',impact='能否增班未决')]
        d['sections'][5]['gap_ids'] = ['G']
        d['decision']['evidence_checks'][2] = dict(topic='feasibility',status='missing',reason='尚未补证',gap_ids=['G'])
        self.assertFalse(report.validate(d)['structure_pass'])
        d['decision']['critical_gap_ids'] = ['G']
        self.assertTrue(report.validate(d)['structure_pass'])
        d['decision']['continue_quote'] = '扩大范围'
        with patch.object(report, 'session_context', return_value=dict(message='扩大范围',offered=True)):
            with self.assertRaisesRegex(ValueError, '重新评估'):
                report.check_release(d)

    def test_old_editions_remain_readable_but_cannot_be_new_builds(self):
        self.assertTrue(report.validate(self.d)['structure_pass'])
        with self.assertRaisesRegex(ValueError, 'edition=full'):
            report.build_delivery(self.d, {}, '审核说明')

if __name__=='__main__':
    unittest.main()
