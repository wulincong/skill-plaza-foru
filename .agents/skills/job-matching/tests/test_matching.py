import importlib.util
from pathlib import Path
import unittest
import hashlib
import json
import subprocess
import sys
import tempfile
spec=importlib.util.spec_from_file_location('matching',Path(__file__).parents[1]/'scripts/matching.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class MatchingTests(unittest.TestCase):
 def test_pagination_deduplicates_and_caps_at_100(self):
  calls=[]
  def request(body):
   calls.append(body)
   page=body['current']; rows=[{'positionId':str(i),'positionName':'前端','positionDescription':'Vue'} for i in range((page-1)*10,page*10)]
   return {'code':0,'isSuccess':True,'data':{'records':rows,'total':150,'current':page,'size':10,'pages':15}}
  result=m.query_jobs({'keyword':'前端','city':'广州市'},request)
  self.assertEqual(len(result['records']),100)
  self.assertEqual(len(calls),10)
 def test_form_resume_is_used_even_without_model_resume_argument(self):
  self.assertEqual(m.extract_resume(Path('/tmp'),{}, {'messages':['- 简历摘要：掌握Vue，做过校园项目。']}),'掌握Vue，做过校园项目。')
 def test_optional_city_is_omitted_from_api_body(self):
  calls=[]
  def api(body):
   calls.append(body)
   return {'code':0,'data':{'records':[],'total':0,'pages':0}}
  for filters in ({'keyword':'前端'},{'keyword':'前端','city':'  '}):m.query_jobs(filters,api)
  self.assertTrue(all('city' not in body['model'] for body in calls))
 def test_invalid_enum_fails_before_request(self):
  with self.assertRaises(ValueError):m.query_jobs({'keyword':'前端','city':'广州','industry':'INVENTED'},lambda _:self.fail())
 def test_upstream_failure_is_not_empty(self):
  with self.assertRaises(ValueError):m.query_jobs({'keyword':'前端','city':'广州'},lambda _:{'code':401,'msg':'unauthorized'})
 def test_scoring_is_fixed_and_unknown_not_zero(self):
  self.assertEqual(m.score({'skills':4,'experience':4,'direction':4,'preferences':4}),100)
  self.assertIsNone(m.score({'skills':None,'experience':4,'direction':4,'preferences':4}))

class ReportTests(unittest.TestCase):
 def setUp(self):
  self.source={'records':[{'positionId':str(i),'positionName':'前端'+str(i),'positionDescription':'熟练Vue，具备项目经验','city':'广州市','companyName':'公司','minSalary':'5','maxSalary':'8','url':'https://job.foru-ai.com/#/station/detail/'+str(i)} for i in range(25)],'total':25,'retrievedAt':'2026-11-19','filters':{'keyword':'前端','city':'广州市'},'resume':'掌握Vue，完成交易平台项目'}
  self.plan={'summary':'优先考虑项目匹配的岗位。','assessments':[{'id':str(i),'eligibility':'pass','skills':4,'experience':3,'direction':4,'preferences':4,'reason':'有Vue项目经历'} for i in range(25)]}
  ranked=sorted(self.plan['assessments'],key=lambda a:a['id'])[:20]
  self.plan['details']=[{'id':a['id'],'evidence':[{'jd':'熟练Vue','resume':'掌握Vue','status':'已证明'}],'gaps':'核实经验门槛','advice':'突出项目职责'} for a in ranked]
 def test_report_hides_query_process_and_shows_dimension_comparison(self):
  page=m.build_page(self.plan,self.source)
  public=str(page)
  self.assertNotIn('检索条件',public);self.assertNotIn('接口总计',public);self.assertNotIn('去重候选',public)
  comparison=next(b for b in page['blocks'] if b.get('title')=='岗位量化对比')
  table=comparison['blocks'][0]
  self.assertEqual(table['rows'][0][2:7],[40,22.5,20,10,92])
  self.assertIn('技能（40分）',[x['label'] for x in table['columns']])
 def test_unknown_dimension_stays_unassessed_in_comparison(self):
  # Keep the same recommendation set while making its last-ranked member uncertain.
  self.plan['assessments']=[a for a in self.plan['assessments'] if a['id'] in {d['id'] for d in self.plan['details']}]
  self.source['records']=[r for r in self.source['records'] if r['positionId'] in {a['id'] for a in self.plan['assessments']}]
  self.plan['assessments'][0]['skills']=None
  page=m.build_page(self.plan,self.source)
  comparison=next(b for b in page['blocks'] if b.get('title')=='岗位量化对比')
  row=next(r for r in comparison['blocks'][0]['rows'] if r[1]=='前端0')
  self.assertEqual(row[2],'未评估');self.assertEqual(row[6],'未评估');self.assertEqual(row[7],'3/4')
 def test_report_has_only_top20_and_real_links(self):
  page=m.build_page(self.plan,self.source)
  self.assertEqual(sum(b.get('type')=='section' and '. 前端' in b.get('title','') for b in page['blocks']),20)
  self.assertIn('https://job.foru-ai.com/#/station/detail/',str(page))
 def test_fabricated_jd_or_resume_is_rejected(self):
  for key,value in [('jd','Python'),('resume','三年经验')]:
   original=self.plan['details'][0]['evidence'][0][key]
   self.plan['details'][0]['evidence'][0][key]=value
   with self.assertRaises(ValueError):m.build_page(self.plan,self.source)
   self.plan['details'][0]['evidence'][0][key]=original
 def test_incomplete_candidate_coverage_rejected(self):
  self.plan['assessments'].pop()
  with self.assertRaises(ValueError):m.build_page(self.plan,self.source)
 def test_cli_build_from_other_directory_preserves_ranked_links(self):
  with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as other:
   workspace=Path(root);(workspace/'.job-matching').mkdir()
   self.source['runId']='run';snapshot='.job-matching/source.json'
   file=workspace/snapshot;file.write_text(json.dumps(self.source));digest=hashlib.sha256(file.read_bytes()).hexdigest()
   self.plan.update(snapshot=snapshot,sha256=digest)
   (workspace/'assessment.json').write_text(json.dumps(self.plan))
   (workspace/'.job-request.json').write_text(json.dumps({'runId':'run'}))
   (workspace/'.job-query-state.json').write_text(json.dumps({'runId':'run','status':'ok','snapshot':snapshot,'sha256':digest}))
   result=subprocess.run([sys.executable,str(Path(m.__file__).resolve()),'build',str(workspace/'assessment.json')],cwd=other,capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stdout)
   manifest=json.loads((workspace/'delivery.json').read_text());html=(workspace/manifest['web'][0]['directory']/'index.html').read_text()
   self.assertIn('查看岗位原文',html);self.assertIn('job.foru-ai.com',html)
   self.assertFalse((Path(other)/'delivery.json').exists())
 def test_public_report_redacts_contact_details(self):
  self.source['resume']='掌握Vue，电话13800138000，邮箱student@example.com'
  self.plan['details'][0]['evidence'][0]['resume']=self.source['resume']
  self.plan['details'][0]['advice']='联系13800138000，student@example.com'
  page=str(m.build_page(self.plan,self.source))
  self.assertNotIn('13800138000',page);self.assertNotIn('student@example.com',page)
 def test_previous_run_snapshot_cannot_satisfy_new_request(self):
  with self.assertRaisesRegex(ValueError,'本轮'):
   m.validate_source({'snapshot':'s','sha256':'h'},{'runId':'old'},{'runId':'new'},{'runId':'old','status':'ok','snapshot':'s','sha256':'h'})
 def test_no_resume_cannot_claim_full_score(self):
  self.source['resume']=''
  with self.assertRaisesRegex(ValueError,'无简历'):m.build_page(self.plan,self.source)
 def test_duplicate_page_stops_without_inventing100(self):
  def api(body):return {'code':0,'data':{'records':[{'positionId':'1','positionName':'前端','positionDescription':'Vue'}],'total':100,'pages':10,'current':body['current']}}
  result=m.query_jobs({'keyword':'前端','city':'广州'},api)
  self.assertEqual(len(result['records']),1);self.assertIn('重复',result['warning'])

if __name__=='__main__':unittest.main()

