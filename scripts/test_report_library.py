import importlib.util
from pathlib import Path
import tempfile
import unittest
import time
import json
import hashlib
import sys
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('library',ROOT/'report_library.py')
lib=importlib.util.module_from_spec(spec);spec.loader.exec_module(lib)


class CatalogTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();lib.STORE=Path(self.tmp.name)
  self.meta={'id':'r1','title':'广东省人工智能人才需求观察报告','region':'广东省','industry':'人工智能',
             'dataAt':'2026-11-03T09:33:20.062Z','webLinks':[{'name':'报告','url':'https://example.test/report'}],
             'downloads':[],'pageCount':16,'contentHash':'abc'}
  with lib.database() as db:
   db.execute('INSERT INTO reports(id,scope_key,region,industry,profile,title,data_at,created_at,content_hash,metadata) VALUES(?,?,?,?,?,?,?,?,?,?)',
              ('r1','key','广东省','人工智能',lib.PUBLIC_PROFILE,self.meta['title'],self.meta['dataAt'],time.time(),'abc',json.dumps(self.meta)))
 def tearDown(self): self.tmp.cleanup()
 def test_natural_request_hits_same_scope(self):
  self.assertEqual(lib.parse_brief('帮我生成一份广东省人工智能行业的人才需求报告'),('广东省','人工智能'))
  self.assertEqual(lib.lookup({'text':'广东人工智能人才需求报告','sessionId':'s1','maxAgeSeconds':30*86400})['status'],'hit')
 def test_extra_time_or_distinct_region_bypasses(self):
  for text in ['广东省人工智能近一年人才报告','广东省人工智能2025年报告','山东省人工智能报告','广东和山东人工智能报告','广东人工智能面向企业报告','广东深圳人工智能报告','广东人工智能Python岗位报告','广东人工智能报告读者为政府']:
   self.assertEqual(lib.lookup({'text':text})['status'],'miss',text)
 def test_confirmation_bound_to_last_report(self):
  self.assertEqual(lib.consent({'sessionId':'fresh','text':'确定'})['status'],'unhandled')
  lib.lookup({'sessionId':'s1','text':'广东人工智能报告','maxAgeSeconds':30*86400})
  self.assertEqual(lib.consent({'sessionId':'s1','text':'确定'})['reportId'],'r1')
  self.assertEqual(lib.consent({'sessionId':'s1','text':'现在几点'})['status'],'unhandled')
  self.assertEqual(lib.consent({'sessionId':'s1','text':'确定'})['status'],'unhandled')
  self.assertEqual(lib.consent({'sessionId':'s1','text':'保存到公众号草稿箱'})['status'],'confirmed')
  for text in ['可以保存草稿吗','请问怎么保存到草稿箱','如果合适就保存草稿','把上一份报告保存到草稿箱']:
   self.assertEqual(lib.consent({'sessionId':'s1','text':text})['status'],'unhandled',text)
 def test_declining_does_not_authorize_later_yes(self):
  lib.lookup({'sessionId':'s1','text':'广东人工智能报告','maxAgeSeconds':30*86400})
  self.assertEqual(lib.consent({'sessionId':'s1','text':'不需要'})['status'],'declined')
  self.assertEqual(lib.consent({'sessionId':'s1','text':'好的'})['status'],'unhandled')

 def test_natural_affirmatives_are_bound_to_a_pending_report_and_questions_are_not(self):
  for text in ['可以啊','可以的','好呀','保存吧','存一下','好的，保存吧']:
   lib.lookup({'sessionId':'s1','text':'广东人工智能报告','maxAgeSeconds':30*86400})
   self.assertEqual(lib.consent({'sessionId':'s1','text':text})['status'],'confirmed',text)
  self.assertEqual(lib.consent({'sessionId':'s1','text':'可以啊？'})['status'],'unhandled')
  self.assertEqual(lib.consent({'sessionId':'s1','text':'可以啊'})['status'],'unhandled')
 def test_expiry_uses_data_date_not_registration_date(self):
  with lib.database() as db:db.execute("UPDATE reports SET data_at='2020-01-01T00:00:00Z'")
  self.assertEqual(lib.lookup({'text':'广东人工智能报告'})['status'],'miss')
 def test_paths_and_non_default_briefs_are_rejected(self):
  for value in ['../other','a/b','',None]:
   with self.assertRaises(ValueError):lib.checked_session(value)
  self.assertIsNone(lib.parse_brief('广东人工智能今年报告'))

 def test_default_education_audience_keeps_custom_filters_out_of_shared_cache(self):
  data={'meta':{'filters':{'region':{'level':'province','name':'山东省'},'industries':[{'id':'17'}]},'industry':'智能制造','scope_industry':'智能制造','audience':'职业院校'}}
  binding={'_result':{'cohorts':[{'id':'all','resolved':{'industries':{'entities':[{'level':0,'includeDescendants':True,'name':'智能制造'}]}}}]}}
  self.assertTrue(lib.standard_scope(data,binding))
  data['meta']['audience']='企业招聘经理';self.assertFalse(lib.standard_scope(data,binding))
  data['meta']['audience']='职业院校';data['meta']['filters']['education']=['BENKE'];self.assertFalse(lib.standard_scope(data,binding))

 def test_incomplete_default_report_does_not_qualify_for_the_full_report_cache(self):
  registry=json.loads((ROOT.parent/'.agents/skills/wechat-report/assets/industry_profiles.json').read_text())
  sections=registry['profiles']['人工智能']['sections']
  data={'meta':{'industry':'人工智能'},'coverage':[{'section':name,'status':'complete'} for name in sections]}
  self.assertTrue(lib.complete_default_profile(data))
  data['coverage']=[row for row in data['coverage'] if row['section']!='track_skills']
  self.assertFalse(lib.complete_default_profile(data))
  data['meta']['industry']='生物医药'
  self.assertFalse(lib.complete_default_profile(data))

 def test_new_profile_requires_matching_execution_code_and_successful_ordered_stages(self):
  scripts=ROOT.parent/'.agents/skills/wechat-report/scripts';sys.path.insert(0,str(scripts))
  from generate_report import PIPELINE_FILES
  base=Path(self.tmp.name)/'build';report=base/'output/report';report.mkdir(parents=True)
  (base/'report_data.json').write_text('{}');(base/'report_analysis.json').write_text('{}')
  digest=lambda value:hashlib.sha256(value).hexdigest()
  stamp=datetime.now(timezone.utc).isoformat()
  stages=['report_preflight.py','report_analysis.py','gen_outline.py','verify_data.py','render_report.py','verify_data.py','build_article.py','evidence_sheet.py','pack_delivery.py']
  receipt={'schema':'wechat-build/1','startedAt':stamp,'finishedAt':stamp,
   'stages':[{'script':name,'exitCode':0,'durationMs':1} for name in stages],
   'pipelineFiles':{name:digest((scripts/name).read_bytes()) for name in PIPELINE_FILES},
   'reportDataSha256':digest(b'{}'),'analysisSha256':digest(b'{}'),'outlineSha256':'outline','manifestSha256':'manifest'}
  outline={'analysis':{'schema':'wechat-analysis/2','reasoningPolicy':'wechat-analytic-reasoning/2'},'editorialPolicy':'wechat-editorial-prose/1','chart_selection':{'policy':'wechat-chart-selection/2'}}
  quality={'outline_sha256':'outline','manifest_sha256':'manifest'}
  file=report/'build_receipt.json'
  file.write_text(json.dumps(receipt));lib.verify_build_receipt(base,outline,quality)
  for change in [lambda row:row['stages'].pop(),lambda row:row['stages'][1].update(exitCode=1),lambda row:row['pipelineFiles'].update({'chart_recommender.py':'changed'}),lambda row:row.update(analysisSha256='stale')]:
   broken=json.loads(json.dumps(receipt));change(broken);file.write_text(json.dumps(broken))
   with self.assertRaises(ValueError):lib.verify_build_receipt(base,outline,quality)
  file.write_text(json.dumps(receipt));(base/'report_analysis.json').write_text('{"changed":true}')
  with self.assertRaises(ValueError):lib.verify_build_receipt(base,outline,quality)


if __name__=='__main__': unittest.main()
