import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.agents/skills/wechat-report/scripts'))
from editorial_prose import core_heading,core_measurements,summary,paths,PROCESS_WORDS
from regional_reasoning import core,section

class EditorialFindingTests(unittest.TestCase):
 def setUp(self):
  self.data={'meta':{'region':'东莞市','industry':'人工智能'},'total':{'positions':100,'companies':20},
   'city_profiles':[{'name':'东莞市','count':100}], 'edu':[{'name':'本科','count':60},{'name':'大专','count':40}],
   'exp':[{'name':'三年以内','count':70},{'name':'经验不限','count':30}],
   'subtrack':[{'key':'data','name':'数据分析','count':40},{'key':'software','name':'软件开发','count':20}],
   'salary':{'median':12},'voc_pool':{'salary':{'valid':40,'median':7,'p25':5,'p75':9},'track':[]}}
 def test_single_city_conclusion_has_matching_education_evidence(self):
  self.assertIn('本科要求占全部岗位60%',core_heading(self.data,0,''))
  text=core_measurements(self.data,{},0,{})
  self.assertIn('本科要求60条',text);self.assertIn('三年以内70条',text)
  self.assertNotIn('100.0%',text)
  self.assertEqual(paths(self.data,{},'core',0),['/total/positions','/edu','/exp'])
 def test_summary_states_bound_local_distribution(self):
  text=summary(self.data,{})
  self.assertIn('数据分析规模最大，占全部岗位40%',text)
  self.assertIn('12K/月',text);self.assertNotRegex(text,PROCESS_WORDS)
  self.assertTrue({'/subtrack','/salary'}.issubset(paths(self.data,{},'summary')))
 def test_core_headlines_answer_findings_and_not_future_work(self):
  self.assertIn('7K/月，低于总体',core_heading(self.data,1,''))
  self.assertIn('合计占全部岗位60%',core_heading(self.data,2,''))
  for i in range(3):self.assertNotRegex(core(self.data,[],i)['interpretation'],PROCESS_WORDS)
  for key in ['geography','jobtype','education','experience','access','salary','tracks','track_salary','city_tracks','lq','skills','track_skills','vocational']:
   self.assertNotRegex(section(self.data,key)['interpretation'],PROCESS_WORDS)
 def test_salary_leader_requires_two_comparable_groups(self):
  for rows in [[],[{'key':'data','name':'数据分析','valid':50,'median':10}],[{'key':'data','name':'数据分析','valid':5,'median':10},{'key':'software','name':'软件开发','valid':8,'median':20}]]:
   self.data['salary_by_track']=rows
   self.assertNotIn('领先',section(self.data,'track_salary')['title'])
  self.data['salary_by_track']=[{'key':'data','name':'数据分析','valid':50,'median':10},{'key':'software','name':'软件开发','valid':80,'median':20}]
  self.assertIn('软件开发报价领先',section(self.data,'track_salary')['title'])
