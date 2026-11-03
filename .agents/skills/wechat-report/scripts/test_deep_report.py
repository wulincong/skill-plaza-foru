import copy
import json
import tempfile
import unittest
from pathlib import Path
from analysis_quality import problems
from executive_analysis import validate,payload
from deep_outline import verify_policy
from report_references import attach,verify
from prepare_session import prepare
from unittest.mock import patch


class DeepReportTests(unittest.TestCase):
    def test_snapshot_does_not_establish_shortages_time_stability_or_industry_causes(self):
        for text in ['这证明了全省存在严重人才短缺。','当地企业更倾向经验人才，产业优势明显。','本科人才形成稳定需求。']:
            self.assertTrue(problems(text,'分析'))
        self.assertFalse(problems('现有样本不能判断人才短缺，需补充供给与招聘完成情况。','分析'))
        self.assertTrue(problems('城市学历结构反映了任务复杂度与知识基础的分布。','geography.interpretation'))
        self.assertTrue(problems('本科占比体现产业对系统性知识的需求。','education.interpretation'))
        self.assertTrue(problems('条件比例更能反映实际进入机会。','access.interpretation'))
        self.assertTrue(problems('城市分层决定校企对接有效性','分结论标题'))
        self.assertFalse(problems('学历占比不能解释为企业知识偏好，需要核查岗位任务。','education.interpretation'))
        self.assertFalse(problems('校企对接名单需按岗位条件分层，而非推断城市产业阶段或企业重视程度。','geography.interpretation'))

    def test_cross_domain_decision_facts_keep_distinct_denominators(self):
        from joint_findings import derive
        data={'city_profiles':[{'name':'甲市','count':600,'valid':500,'median':20,'bachelorCount':400,'bachelorShare':66.67},
                               {'name':'乙市','count':400,'valid':300,'median':10,'bachelorCount':100,'bachelorShare':25}],
              'total':{'positions':1000},'edu_exp':[['本科','经验不限',20],['本科','五年以内',80],['大专','经验不限',80],['大专','五年以内',20]],
              'subtrack':[{'name':'方向甲','key':'a','count':500},{'name':'方向乙','key':'b','count':200},{'name':'未分类','key':'__other__','count':300}],
              'salary':{'median':15},'voc_pool':{'count':150,'city':[['甲市',60],['乙市',90]],
              'salary':{'valid':140,'median':6,'p75':9},'track':[{'name':'方向甲','key':'a','count':100},{'name':'方向乙','key':'b','count':40}],
              'salary_by_track':[{'name':'方向甲','valid':95,'median':5},{'name':'方向乙','valid':35,'median':25}]}}
        facts={row['id']:row for row in derive(data)}
        self.assertIn('10.0%',facts['geography.entry_coverage_0']['text'])
        self.assertIn('15.0%',facts['geography.entry_coverage_0']['text'])
        self.assertIn('71.43%',facts['tracks.classified_leaders']['text'])
        self.assertIn('50.0%',facts['tracks.classified_leaders']['text'])
        self.assertIn('-6 K/月',facts['salary.entry_upper_bound']['text'])
        self.assertIn('有效 35 条',facts['vocational.track_tradeoff']['text'])
        self.assertIn('/edu_exp',facts['experience.education_contrast']['paths'])

    def test_explicit_revision_archives_prose_preserves_data_and_is_idempotent(self):
        import writing_batches as batches
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'wechat-report';root.mkdir()
            progress=root/'output/analysis/writing_progress.json';progress.parent.mkdir(parents=True)
            progress.write_text(json.dumps({'evidenceHash':'old','sections':{'old':{}},'executive':{}}))
            (root/'report_data.json').write_text('original data')
            (root/'report_writing.json').write_text(json.dumps({'text':'original prose'}))
            (root.parent/'delivery.json').write_text('{}')
            with patch.object(batches,'BASE',root),patch.object(batches,'load_data',return_value=({},{})),patch.object(batches,'evidence_pack',return_value={'new':'facts'}),patch.object(batches,'next_task',return_value={'next':'write'}):
                batches.revise('revision-1')
                self.assertEqual((root/'report_data.json').read_text(),'original data')
                self.assertFalse((root/'report_writing.json').exists())
                self.assertFalse((root.parent/'delivery.json').exists())
                self.assertTrue((root/'output/analysis/revisions/revision-1/report_writing.json').exists())
                state=json.loads(progress.read_text());state['sections']['accepted']={'text':'new analysis'}
                progress.write_text(json.dumps(state));batches.revise('revision-1')
                self.assertIn('accepted',json.loads(progress.read_text())['sections'])

    def test_executive_requires_three_cross_domain_arguments_and_binds_actual_paragraphs(self):
        facts={'a':{'text':'事实甲','section':'geography'},'b':{'text':'事实乙','section':'salary'},'c':{'text':'事实丙','section':'vocational'}}
        claim={'title':'按需求与入口共同筛选合作对象','findingIds':['a','b'],'interpretation':'解释','implication':'任务'}
        executive={'opening':'总体判断','claims':[copy.deepcopy(claim) for _ in range(3)],'closing':'综合启示','findingIds':['a','b']}
        validate(executive,facts,lambda *args:None)
        paragraphs,summary,refs=payload(executive,facts)
        self.assertTrue(paragraphs[0].startswith('总体判断：'))
        self.assertEqual(summary['title'],'综合启示')
        self.assertEqual([paragraphs[index] for index in refs],['事实甲','事实乙']*3)
        bad=copy.deepcopy(executive);bad['claims'][0]['findingIds']=['a']
        with self.assertRaises(ValueError):validate(bad,facts,lambda *args:None)

    def test_bar_policy_blocks_multiple_or_two_variable_columns(self):
        chart={'kind':'city_combo','metrics':['salary_median','bachelor_share','positions']}
        outline={'presentation':'wechat-multivariate/1','analysis':{'schema':'wechat-analysis/2'},'screens':[{'chart':chart}]}
        self.assertTrue(verify_policy(outline))
        outline['screens'].append({'chart':chart})
        with self.assertRaises(ValueError):verify_policy(outline)
        outline['screens']=[{'chart':{'kind':'hbar'}}]
        with self.assertRaises(ValueError):verify_policy(outline)

    def test_official_context_survives_json_roundtrip_and_cannot_be_rewritten(self):
        data={'meta':{'region':'广东省','industry':'人工智能','generated_at':'2026-11-03T13:07:00Z'}}
        outline=attach({'screens':[]},data)
        restored=json.loads(json.dumps(outline,ensure_ascii=False))
        verify(restored,data)
        restored['research_sources']['references'][1]['url']='https://example.test/'
        with self.assertRaises(ValueError):verify(restored,data)

    def test_trusted_init_keeps_only_workspace_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            prepare(directory)
            folder=Path(directory)/'wechat-report'
            self.assertTrue((folder/'assets/brand.json').is_file())
            self.assertFalse((folder/'scripts').exists())
            self.assertFalse((folder/'.venv').exists())
            self.assertFalse((folder/'assets/mp_config.json').exists())


if __name__=='__main__':unittest.main()
