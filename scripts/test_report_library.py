import importlib.util
from pathlib import Path
import tempfile
import unittest
import time
import json

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
 def test_expiry_uses_data_date_not_registration_date(self):
  with lib.database() as db:db.execute("UPDATE reports SET data_at='2020-01-01T00:00:00Z'")
  self.assertEqual(lib.lookup({'text':'广东人工智能报告'})['status'],'miss')
 def test_paths_and_non_default_briefs_are_rejected(self):
  for value in ['../other','a/b','',None]:
   with self.assertRaises(ValueError):lib.checked_session(value)
  self.assertIsNone(lib.parse_brief('广东人工智能今年报告'))


if __name__=='__main__': unittest.main()
