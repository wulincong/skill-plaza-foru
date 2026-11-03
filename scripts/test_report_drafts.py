"""No network or real credentials: check version/consent/idempotency and draft ordering."""
import hashlib
import hmac
import importlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import report_library as lib
import report_drafts as drafts


class DraftTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.store=Path(self.tmp.name)
  self.patches=[patch.object(lib,'STORE',self.store),patch.object(drafts,'STORE',self.store)]
  for p in self.patches:p.start();self.addCleanup(p.stop)
  self.id='a'*32;folder=self.store/'reports'/self.id/'images';folder.mkdir(parents=True)
  for i in (1,2):(folder/f'page_{i:02}.png').write_bytes(('image'+str(i)).encode())
  self.meta={'id':self.id,'title':'广东省人工智能人才需求观察报告','positions':10,'companies':4,'cities':2,
             'pageCount':2,'webLinks':[{'url':'https://example.test/report'}],
             'screens':[{'title':'封面'},{'title':'章节','paragraphs':['报告发现','报告解释'],'summary':{'text':'总结'},'blocks':[['来源','已验证数据']]}],
             'imageHashes':[hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob('*.png'))]}
  with lib.database() as db:
   db.execute('INSERT INTO reports(id,scope_key,region,industry,profile,title,data_at,created_at,content_hash,metadata) VALUES(?,?,?,?,?,?,?,?,?,?)',
              (self.id,'scope','广东省','人工智能','profile','report','2026-11-03',time.time(),'hash',json.dumps(self.meta)))
   db.execute('INSERT INTO sessions VALUES(?,?,2,?)',('session1',self.id,time.time()))

 def fake_post(self,path,token,payload=None,image=None):
  self.calls.append(path)
  if path=='media/uploadimg':return {'url':'https://mmbiz.qpic.cn/example.png'}
  if path.startswith('material/'):return {'media_id':'cover'}
  self.payload=payload
  return {'media_id':'draft1'}

 def test_prose_precedes_all_images_and_duplicate_saves_reuse_receipt(self):
  self.calls=[]
  sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'.agents/skills/wechat-report/scripts'))
  with patch.object(drafts,'_post',side_effect=self.fake_post),patch('publish_draft.make_card_cover'):
   result=drafts.save_report('session1',self.id,'account',lambda:'fake-token')
   self.assertEqual(result['state'],'saved')
   content=self.payload['articles'][0]['content']
   self.assertLess(content.index('报告发现'),content.index('<img'))
   self.assertLess(content.index('总结'),content.index('<img'))
   self.assertEqual(content.count('<img'),2)
   calls=len(self.calls)
   self.assertEqual(drafts.save_report('session1',self.id,'account',lambda:'fake-token')['state'],'saved')
   self.assertEqual(len(self.calls),calls)

 def test_only_confirmed_exact_version_can_save(self):
  with lib.database() as db:db.execute('UPDATE sessions SET pending=1')
  with self.assertRaises(drafts.DraftError):drafts.save_report('session1',self.id,'account',lambda:'fake')
  with self.assertRaises(drafts.DraftError):drafts.save_report('other',self.id,'account',lambda:'fake')

 def test_tampered_image_never_uploads(self):
  (self.store/'reports'/self.id/'images/page_01.png').write_bytes(b'changed')
  with patch.object(drafts,'_post') as network:
   self.assertEqual(drafts.save_report('session1',self.id,'account',lambda:'fake')['state'],'failed')
   network.assert_not_called()

 def test_whitelist_failure_never_reports_success(self):
  def unavailable():raise RuntimeError('40164 invalid ip')
  with patch.object(drafts,'_post') as network:
   result=drafts.save_report('session1',self.id,'account',unavailable)
   self.assertEqual(result['state'],'failed');self.assertIn('40164',result['message'])
   network.assert_not_called()

 def test_uncertain_create_is_not_blindly_retried(self):
  self.calls=[]
  def post(path,token,payload=None,image=None):
   if path=='draft/add':raise drafts.DraftError('请求超时，保存状态需核对，不能自动重复创建')
   return self.fake_post(path,token,payload,image)
  with patch.object(drafts,'_post',side_effect=post),patch('publish_draft.make_card_cover'):
   self.assertEqual(drafts.save_report('session1',self.id,'account',lambda:'fake')['state'],'unknown')
   with patch.object(drafts,'_post') as again:
    self.assertEqual(drafts.save_report('session1',self.id,'account',lambda:'fake')['state'],'unknown')
    again.assert_not_called()


if __name__=='__main__':unittest.main()
