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
        self.assertTrue(problems('方向薪酬差异显著，但不能直接转化为扩招建议。','track_salary.interpretation'))
        self.assertFalse(problems('不同学历组反映招聘条件不同，而非实践深度或能力回报。','experience.interpretation'))
        self.assertTrue(problems('应以上四分位作为上限制定薪酬目标。','salary.action'))
        self.assertFalse(problems('确认未把上四分位当作薪酬封顶。','salary.validation'))
        self.assertFalse(problems('确认上四分位仅作为分布区间边界而非薪酬封顶。','salary.validation'))

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
        del data['voc_pool']
        without_pool=derive(data)
        self.assertFalse(any(row['section']=='vocational' for row in without_pool))
        self.assertFalse(any('entry_coverage' in row['id'] for row in without_pool))
        data['voc_pool']={'count':0}
        zero=derive(data)
        self.assertTrue(any('entry_coverage' in row['id'] for row in zero))
        self.assertFalse(any(row['section']=='jobtype' for row in zero))

    def test_preflight_rejects_missing_city_metrics_before_writing_and_single_city_omits_comparisons(self):
        from report_preflight import check
        from chart_recommender import recommend_multivariate
        data={'meta':{'region':'深圳市','industry':'人工智能','filters':{'region':{'level':'city'}}},'total':{'positions':100}}
        pack={'findings':[{'section':'education'},{'section':'salary'}]}
        with self.assertRaisesRegex(ValueError,'写作前预检'):check(data,pack)
        data['city_profiles']=[{'valid':100,'median':20}]
        self.assertTrue(check(data,pack)['ready'])
        self.assertIsNone(recommend_multivariate('招聘地域分布',data)['spec'])
        self.assertIsNone(recommend_multivariate('地域方向集中程度',data)['spec'])

    def test_missing_core_preferences_fall_back_to_different_domains(self):
        from writing_batches import task
        facts=[{'id':key+str(i),'section':key,'kind':'comparison'} for key in ['geography','education','salary'] for i in range(2)]
        part=task({'requiredSections':[],'findings':facts},{'sections':{},'executive':None})['part']
        lookup={row['id']:row['section'] for row in facts}
        for claim in part['executive']['claims']:
            self.assertEqual(len({lookup[fid] for fid in claim['findingIds']}),2)
        self.assertEqual(len({lookup[fid] for claim in part['executive']['claims'] for fid in claim['findingIds']}),3)

    def test_reasoning_changes_with_salary_distribution_and_respects_city_degree_scope(self):
        from analytical_reasoning import section,opening
        data={'meta':{'region':'深圳市','industry':'人工智能','filters':{'region':{'level':'city'},'education':['SHUOSHI']},'enum_labels':{'education':{'SHUOSHI':'硕士'}}},
              'salary':{'median':10},'voc_pool':{'salary':{'valid':100,'p75':8}}}
        self.assertEqual(section(data,'salary')['title'],'总体中位数超过入门池上四分位')
        data['voc_pool']['salary']['p75']=12
        self.assertEqual(section(data,'salary')['title'],'入门薪酬目标仍需按分布与岗位匹配')
        text=opening(data)
        self.assertIn('硕士学历条件',text)
        self.assertIn('不能把筛选形成的地域范围解释成产业集聚',text)

    def test_canonical_analysis_overrides_model_claims_but_preserves_proposals(self):
        from analytical_reasoning import normalize,verify
        data={'meta':{'region':'广东省','industry':'人工智能','filters':{'region':{'level':'province'}}},'salary':{'median':10}}
        writing={'sections':[{'key':'salary','title':'错误标题','interpretation':'企业存在人才短缺','findingIds':['fake'],'action':'保留行动方案'}],
                 'executive':{'opening':'本地化高度聚集','claims':[{'title':'错误','findingIds':['fake'],'interpretation':'假因果','implication':'保留决策建议'} for _ in range(3)],'closing':'综合步骤'}}
        ids={'salary':['salary.quantiles','salary.coverage']};pairs=[['geography.a','jobtype.a'],['salary.a','education.a'],['tracks.a','skills.a']]
        result=normalize(data,writing,ids,pairs)
        self.assertEqual(result['sections'][0]['action'],'保留行动方案')
        self.assertEqual(writing['sections'][0]['title'],'错误标题')
        verify(data,result,ids,pairs)
        result['sections'][0]['interpretation']='企业存在人才短缺'
        with self.assertRaises(ValueError):verify(data,result,ids,pairs)

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
