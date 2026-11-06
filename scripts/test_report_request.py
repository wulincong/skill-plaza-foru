import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from report_request import classify,region_request,scope_matches,filter_intent_problems

class ScopeTests(unittest.TestCase):
 def test_city_alias_and_parent_not_province(self):
  for text in ['生成广州的人工智能报告','广东省广州市人工智能报告','来一份广州AI报告']:
   with self.subTest(text=text):
    self.assertEqual(region_request(text)['region'],{'level':'city','province':'广东省','name':'广州市'})
    self.assertFalse(scope_matches({'level':'province','name':'广东省'},text))
    self.assertTrue(scope_matches({'level':'city','province':'广东省','name':'广州'},text))
 def test_non_geographic_filter_keeps_original_city(self):
  self.assertEqual(region_request('生成广州AI报告，只看大专学历和三年以内经验')['region']['name'],'广州市')
  self.assertEqual(region_request('原为广东，改为深圳人工智能报告')['region']['name'],'深圳市')
 def test_provinces_and_municipalities(self):
  for name in ['广东省','广西壮族自治区','新疆维吾尔自治区','北京市','上海市','香港特别行政区']:
   with self.subTest(name=name):self.assertEqual(region_request(name+'人工智能报告')['region']['name'],name)
 def test_ambiguities_and_unsupported_county_are_not_widened(self):
  for text in ['吉林人工智能报告','广州和深圳人工智能报告','广州天河区人工智能报告','山东广州人工智能报告']:
   with self.subTest(text=text):self.assertIn(region_request(text)['status'],('ambiguous','unsupported'));self.assertFalse(scope_matches({'level':'province','name':'广东省'},text))
 def test_ordinary_chat_help_negation(self):
  for text in ['人工智能是什么','不要生成广州AI报告','报告是什么意思','/报告生成器']:self.assertEqual(classify(text)['intent'],'none')
  for text in ['报告怎么生成','如何使用 /报告生成','报告帮助']:self.assertEqual(classify(text)['intent'],'help')
 def test_intent_without_magic_phrase(self):
  for text in ['广州AI报告','来一份广州人工智能报告','想看看山东机器人行业的人才需求','帮我分析广州AI的招聘情况']:
   with self.subTest(text=text):self.assertEqual(classify(text)['status'],'ready')
 def test_no_invented_work_experience_or_missing_explicit_education(self):
  text='想看看深圳半导体的招聘情况，只看大专学历'
  self.assertTrue(filter_intent_problems({'education':['DAZHUAN'],'experience':['GRADUATING']},text))
  self.assertTrue(filter_intent_problems({'education':[]},text))
  self.assertEqual(filter_intent_problems({'education':['DAZHUAN'],'experience':[]},text),[])
  self.assertEqual(filter_intent_problems({'education':['DAZHUAN']},'请继续生成'),[])
 def test_executive_same_domain_candidates_get_an_actual_second_dimension(self):
  sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'.agents/skills/wechat-report/scripts'))
  from executive_analysis import default_pairs
  rows=[{'id':fid,'section':domain,'kind':'comparison'} for fid,domain in [('tracks.classified_leaders','tracks'),('tracks.coverage','tracks'),('salary.quantiles','salary'),('education.share','education')]]
  facts={r['id']:r for r in rows}
  for ids in default_pairs({'findings':rows}):self.assertGreaterEqual(len({facts[x]['section'] for x in ids}),2)
 def test_missing_fields_and_unregistered_industry(self):
  self.assertEqual(classify('想要一份人工智能报告')['status'],'clarify')
  self.assertEqual(classify('生成广州报告')['status'],'clarify')
  self.assertEqual(classify('生成广州光伏产业报告')['status'],'ready')

if __name__=='__main__':unittest.main()
