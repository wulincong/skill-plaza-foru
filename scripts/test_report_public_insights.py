"""Regression cases from real editorial review, without credentials or network."""
import unittest,sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'.agents/skills/wechat-report/scripts'))
from editorial_projects import public_insight_problems
from article_content import build_lead,html_prose,prose_blocks

class PublicInsightTests(unittest.TestCase):
 def setUp(self):
  self.data={'meta':{'region':'广东省','industry':'机器人','generated_at':'2026-11-05T00:00:00Z'},'total':{'positions':100,'companies':20},
   'city_profiles':[{'name':'深圳市','count':70},{'name':'广州市','count':30}],
   'subtrack':[{'key':'a','name':'感知与智能算法','count':40},{'key':'b','name':'电气与自动化','count':20}],
   'salary':{'median':12},'voc_pool':{'salary':{'valid':30,'median':6}},
   'exp':[{'name':'经验不限','count':43}],'jobtype':[{'name':'校招','count':3}]}
 def issues(self,key,text):return public_insight_problems(self.data,{'key':key,'action':text})
 def test_mention_difference_is_not_skill_strength_or_employer_preference(self):
  self.assertFalse(self.issues('track_skills','两类方向对 C++ 的描述提及存在差别，准备时应继续阅读对应职责。'))
  self.assertTrue(self.issues('track_skills','对 C++ 的要求明显高于服务方向，说明企业更看重系统级编程能力。'))
  self.assertTrue(self.issues('skills','沟通在岗位描述中频繁出现，说明协作能力同样重要。'))
 def test_marginal_direction_salary_cannot_become_city_direction_salary(self):
  self.assertTrue(self.issues('track_salary','深圳在智能驾驶方向的报价领先，广州在测试方向机会较多。'))
  self.assertFalse(self.issues('city_tracks','深圳市与广州市的方向份额和绝对岗位量应一起阅读。'))
 def test_cross_tab_does_not_prove_recruiting_adjustment(self):
  self.assertTrue(self.issues('experience','两组的经验分布说明企业会调整学历与经验要求。'))
  self.assertTrue(self.issues('experience','学历与经验门槛相互影响。'))
  self.assertFalse(self.issues('experience','学历与经验共同用于筛选岗位，具体项目要求仍需阅读职责说明。'))
 def test_majority_and_zero_must_match_observed_counts(self):
  self.assertTrue(self.issues('experience','经验不限占比高，说明多数岗位未限定年限。'))
  self.data['exp'][0]['count']=80
  self.assertFalse(self.issues('experience','经验不限占比高，说明多数岗位未限定年限。'))
  self.assertTrue(self.issues('jobtype','校招标签为空白。'))
 def test_article_is_an_independent_short_intro_and_ignores_free_claims(self):
  lead=build_lead(self.data,{'executive':{'claims':[{'interpretation':'图片中的冗长正文不应被复制'}]}})
  report={'articleLead':lead};text=''.join(t for _,t in prose_blocks(report))
  self.assertNotIn('图片中的冗长正文',text)
  self.assertIn('深圳市',text);self.assertIn('100%',text)
  self.assertLess(len(text),800)
  self.assertEqual(len(lead['signals']),3)
  self.assertNotIn('<img',html_prose(report))

if __name__=='__main__':unittest.main()
