"""No network or real credentials: check version/consent/idempotency and draft ordering."""
import hashlib
import hmac
import importlib
import json
import os
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
   from unittest.mock import Mock
   token=Mock(return_value='fake')
   self.assertEqual(drafts.save_report('session1',self.id,'account',token)['state'],'failed')
   token.assert_not_called()
   network.assert_not_called()

 def test_shared_prose_deduplicates_actions_and_keeps_references(self):
  report={**self.meta,'analysis':{'sections':[{'key':'salary'}]},'screens':[
   {'title':'封面'},{'title':'薪酬','analysis_key':'salary','paragraphs':['薪酬解释','行动建议：核查同类岗位']},
   {'title':'建议','blocks':[['行动','核查同类岗位']]},
   {'title':'参考文献','paragraphs':['国家统计局公报 https://www.stats.gov.cn/']} ]}
  prose=drafts.text_before_images(report)
  self.assertEqual(prose.count('核查同类岗位'),1)
  self.assertIn('国家统计局公报',prose)

 def test_large_page_is_losslessly_tiled_without_changing_confirmed_archive(self):
  from PIL import Image,ImageDraw
  source=self.store/'large.png'
  original=Image.frombytes('RGB',(480,800),os.urandom(480*800*3))
  draw=ImageDraw.Draw(original)
  for row in (200,400,600):draw.rectangle((0,row,479,row+3),fill='white')
  original.save(source)
  before=hashlib.sha256(source.read_bytes()).hexdigest()
  parts=drafts.upload_image_parts([source],self.store,limit=300000)
  self.assertGreater(len(parts),1)
  joined=Image.new('RGB',original.size);offset=0
  for part in parts:
   self.assertLess(part.stat().st_size,300000)
   with Image.open(part) as image:joined.paste(image,(0,offset));offset+=image.height
  self.assertEqual(offset,original.height)
  self.assertEqual(joined.tobytes(),original.tobytes())
  self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)

 def test_oversized_prose_fails_before_token_or_upload(self):
  self.meta['screens'][1]['paragraphs']=['正文'*11000]
  with lib.database() as db:db.execute('UPDATE reports SET metadata=?',(json.dumps(self.meta),))
  from unittest.mock import Mock
  token=Mock(return_value='fake')
  with patch.object(drafts,'_post') as network:
   self.assertEqual(drafts.save_report('session1',self.id,'account',token)['state'],'failed')
   token.assert_not_called();network.assert_not_called()

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
