import copy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from editorial_prose import paragraphs,content_audit,spec
from bound_report import project
from report_analysis import derive_findings
from executive_analysis import default_pairs
from analytical_reasoning import opening,core
import regional_research as research


def sample():
    return {'meta':{'region':'广东省','industry':'人工智能','filters':{'region':{'level':'province','name':'广东省'}}},
      'total':{'positions':1000,'companies':300},'city':[['甲市',600],['乙市',400]],
      'city_profiles':[{'name':'甲市','count':600,'valid':500,'median':20,'bachelorCount':400,'bachelorShare':66.67},
                       {'name':'乙市','count':400,'valid':300,'median':10,'bachelorCount':100,'bachelorShare':25}],
      'salary':{'valid':900,'median':15,'p25':8,'p75':22},
      'voc_pool':{'count':150,'city':[['甲市',60],['乙市',90]],'salary':{'valid':140,'median':6,'p25':4,'p75':9}},
      'subtrack':[{'name':'视觉应用','key':'vision','count':500},{'name':'数据工程','key':'data','count':200},{'name':'未分类','key':'__other__','count':300}]}


def executive(data):
    facts=derive_findings(data);pairs=default_pairs({'findings':facts})
    return {'opening':opening(data),'claims':[{**core(data,ids,index),'findingIds':ids,'implication':'将本地方向任务组织为课程项目，以操作过程、工具产出与成果说明共同评价学习结果。'} for index,ids in enumerate(pairs)],
            'closing':'围绕目标岗位安排课程模块，按方向组织项目任务，以连续成果连接基础学习和具体岗位实践。'}


class EditorialTests(unittest.TestCase):
    def test_summary_is_one_abstract_and_three_integrated_points(self):
        data=sample();item=executive(data);facts={row['id']:row for row in derive_findings(data)}
        ps,tail=paragraphs(data,item,facts,True)
        self.assertEqual(len(ps),4);self.assertIsNone(tail)
        self.assertTrue(ps[0].startswith('摘要｜'));self.assertIn('1,000',ps[0])
        self.assertIn('600',ps[1]);self.assertIn('10%',ps[1]);self.assertIn('15%',ps[1])
        self.assertIn('15K/月',ps[2]);self.assertIn('6K/月',ps[2]);self.assertIn('4—9K/月',ps[2])
        self.assertIn('视觉应用500条',ps[3]);self.assertIn('50%',ps[3])
        self.assertFalse(any('分析：' in p or '决策启示：' in p for p in ps))
        for index,claim in enumerate(item['claims']):self.assertIn(claim['implication'],ps[index+1])
        content_audit({'screens':[{'analysis_key':'overview','paragraphs':ps}]})

    def test_core_does_not_repeat_its_title_in_the_application_sentence(self):
        data=sample();item=executive(data);title=item['claims'][1]['title']
        item['claims'][1]['implication']=title+'，就业沟通需要对应具体方向和岗位职责，使用作品支持个人定位。'
        ps,_=paragraphs(data,item,{row['id']:row for row in derive_findings(data)},True)
        self.assertEqual(ps[2].count(title),1)

    def test_local_numbers_names_and_interpretation_change_with_region(self):
        original=sample();other=copy.deepcopy(original)
        other['meta']['region']='山东省';other['meta']['filters']['region']['name']='山东省'
        other['city_profiles'][0]['name']='青岛市';other['city_profiles'][0]['count']=400
        other['city_profiles'][1]['name']='济南市';other['city_profiles'][1]['count']=600
        other['voc_pool']['city']=[['青岛市',10],['济南市',140]]
        a=paragraphs(original,executive(original),{r['id']:r for r in derive_findings(original)},True)[0]
        b=paragraphs(other,executive(other),{r['id']:r for r in derive_findings(other)},True)[0]
        self.assertIn('广东省',a[0]);self.assertIn('山东省',b[0]);self.assertNotEqual(a[1],b[1]);self.assertIn('济南市',b[1])
        self.assertIn('高于全省',b[1]);self.assertIn('低于全省',a[1])

    def test_integrated_numeric_projection_rejects_changed_input_fields(self):
        data=sample();item=executive(data)
        fields={p:['metric:'+p] for p in ['/total/positions','/total/companies','/city_profiles','/voc_pool/count','/voc_pool/city']}
        checked=spec(data,item,'core',{'fields':fields},0)
        self.assertIn('600',project(data,checked))
        checked['inputs']['0']['path']='/salary'
        with self.assertRaises(ValueError):project(data,checked)

    def test_process_language_is_rejected_but_original_bibliographic_titles_are_kept(self):
        with self.assertRaises(ValueError):content_audit({'screens':[{'title':'核心结论','paragraphs':['该结论待审核后采用。']}]})
        content_audit({'screens':[{'no':'文献','title':'参考文献','blocks':[['2026年计划草案报告','原始文献名称']]}]})

    def test_retrieval_never_substitutes_another_province_or_industry(self):
        for region in ['广东省','山东省','浙江省','江苏省','湖北省','福建省']:
            result=research.prepare(region,'人工智能')
            self.assertEqual(result['status'],'ready')
            self.assertTrue(all(source['region']==region for source in result['sources']))
        self.assertEqual(research.prepare('山西省','人工智能')['sources'],[])
        self.assertEqual(research.prepare('广东省','生物医药')['sources'],[])
        city=research.prepare('深圳市','人工智能')
        self.assertEqual(city['contextScope'],'parent_province');self.assertEqual(city['subjectRegion'],'广东省')

    def test_catalog_rejects_unobserved_numbers_and_unlabeled_targets(self):
        source=copy.deepcopy(research.catalog_search('广东省','人工智能')['sources'][0])
        source['facts']=['广东省已经有98765个场景。']
        with self.assertRaises(ValueError):research.validate_source(source)
        target=copy.deepcopy(research.catalog_search('江苏省','人工智能')['sources'][0])
        target['facts']=['江苏现有100个工业智能体。']
        with self.assertRaises(ValueError):research.validate_source(target)

    def test_working_snapshot_cannot_rewrite_sources_or_change_region(self):
        with tempfile.TemporaryDirectory() as directory:
            data=sample();first=research.ensure_context(data,directory)
            self.assertEqual(first,research.ensure_context(data,directory))
            file=Path(directory)/'report_research.json';value=json.loads(file.read_text())
            value['sources'][0]['facts']=['广东省30类场景已经带来30万岗位。']
            file.write_text(json.dumps(value))
            with self.assertRaises(ValueError):research.ensure_context(data,directory)
            file.unlink();research.ensure_context(data,directory)
            data['meta']['region']='山东省'
            with self.assertRaises(ValueError):research.ensure_context(data,directory)

    def test_unicode_numbers_cannot_bypass_measurement_binding(self):
        from report_analysis import _narrative
        for text in ['统计对象为二〇二六年十一月四日发布的有效岗位记录，覆盖本次地区研究范围。','当前样本占比百分之十五，应在本地城市中配置对应课程。','统计对象为²⁰²⁶年¹¹月发布的有效岗位记录，覆盖本次地区研究范围。', '当前共有１２３个岗位记录，适合开展本地项目与课程实践。', '当前共有𝟙𝟚𝟛个岗位记录，适合开展本地项目与课程实践。']:
            with self.assertRaises(ValueError):_narrative(text,'研究边界')
        _narrative('围绕ROS2开展工具练习，提交操作记录与可复现成果，形成完整的课程作品。','任务',labels={'ROS2'})

    def test_degree_does_not_determine_technical_task(self):
        from analysis_quality import problems
        for text in ['本科生参与行业数据治理与模型部署，形成项目成果。','算法方向面向硕士，形成模型开发作品。','仅安排本科生进入算法项目，大专生开展基础数据任务。']:
            self.assertTrue(problems(text,'action'),text)
        self.assertFalse(problems('不按学历分配技术任务，按任务准备度与作品表现安排项目。','action'))

    def test_generated_project_examples_are_accepted_and_topic_specific(self):
        from editorial_projects import examples,core_examples
        from report_analysis import _narrative,entity_labels
        from analysis_quality import problems
        from writing_batches import HINTS
        data=sample()
        for key in HINTS:
            for field,text in examples(data,key).items():
                _narrative(text,field,30,entity_labels(data))
                self.assertEqual(problems(text,field),[],(key,field))
        self.assertIn('薪酬区间',core_examples(data)[1])
        data['exp']=[{'name':'5年以内','count':300}]
        _narrative('以五年以内岗位为观察对象，组织可复现的项目作品与过程记录，用于目标岗位沟通。','任务',labels=entity_labels(data))
        from regional_reasoning import limitations
        for text in limitations(data):self.assertFalse(problems(text,'研究边界'))

    def test_entry_direction_advice_keeps_the_vocational_population(self):
        data=sample();data['voc_pool']['track']=[{'key':'vision','name':'视觉应用','count':10},{'key':'data','name':'数据工程','count':100}]
        item=executive(data);text=item['claims'][2]['interpretation']
        self.assertIn('面向职教入门人群',text);self.assertNotIn('面向初次就业的课程',text)

    def test_nearly_double_track_sizes_are_not_described_as_close(self):
        data=sample();data['subtrack'][0]['count']=380;data['subtrack'][1]['count']=200
        item=executive(data)
        self.assertNotIn('规模较为接近',item['claims'][2]['interpretation'])
        self.assertNotIn('规模接近',item['claims'][2]['title'])

    def test_salary_without_entry_uses_qualified_classified_comparisons(self):
        data=sample();data.pop('voc_pool')
        data['salary_by_track']=[{'key':'vision','name':'视觉应用','valid':100,'median':30},{'key':'data','name':'数据工程','valid':100,'median':10}]
        pairs=default_pairs({'findings':derive_findings(data)})
        self.assertEqual(pairs[1],['salary.quantiles','track_salary.qualified_extremes'])

    def test_chapter_recommendation_uses_the_actual_comparison(self):
        from editorial_projects import examples,alignment_problems
        data=sample();data['job_skill_rows']=[{'track':'vision','label':'视觉应用','skill':'视觉工具','count':160,'positions':200}, {'track':'data','label':'数据工程','skill':'视觉工具','count':10,'positions':200}]
        row={'key':'track_skills','action':'围绕本地主要方向设置通用课程，提交作品并组织学习成果评价。'}
        self.assertTrue(alignment_problems(data,row))
        row.update(examples(data,'track_skills'))
        self.assertFalse(alignment_problems(data,row));self.assertIn('视觉工具',row['action']);self.assertIn('数据工程',row['action'])

    def test_unsupported_promise_tails_are_removed_and_rejected_if_standalone(self):
        from editorial_prose import polish
        from analysis_quality import problems
        self.assertEqual(polish('评价操作记录与结果说明，确保与岗位需求匹配。'),'评价操作记录与结果说明。')
        self.assertTrue(problems('确保学习成果具备市场要求的能力。','action'))

    def test_snapshot_cannot_omit_available_local_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            data=sample();value=research.ensure_context(data,directory)
            value['sources']=[]
            value['evidenceHash']=research.digest({'requestedRegion':'广东省','industry':'人工智能','sources':[]})
            (Path(directory)/'report_research.json').write_text(json.dumps(value))
            with self.assertRaises(ValueError):research.ensure_context(data,directory)

    def test_refresh_rejects_a_valid_page_with_wrong_subject_or_missing_evidence(self):
        source=research.catalog_search('广东省','人工智能')['sources'][0]
        class Response:
            url=source['url']
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return '浙江省人工智能相关资料'.encode()
            class headers:
                @staticmethod
                def get_content_charset():return 'utf-8'
        with patch.object(research,'urlopen',return_value=Response()):
            self.assertEqual(research.refresh_source(source)['status'],'unavailable')


if __name__=='__main__':unittest.main()
