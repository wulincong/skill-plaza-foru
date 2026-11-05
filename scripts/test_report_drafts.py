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
from unittest.mock import patch, Mock, call

sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'.agents/skills/wechat-report/scripts'))
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
   self.assertLess(content.index('完整报告'),content.index('<img'))
   self.assertNotIn('报告发现',content)
   self.assertNotIn('报告解释',content)
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

 def test_draft_intro_is_bounded_and_does_not_repeat_report_or_methods(self):
  report={**self.meta,'analysis':{'sections':[{'key':'salary'}]},'screens':[
   {'title':'封面'},{'title':'薪酬','analysis_key':'salary','paragraphs':['薪酬解释','行动建议：核查同类岗位']},
   {'title':'建议','blocks':[['行动','核查同类岗位']]},
   {'title':'参考文献','paragraphs':['国家统计局公报 https://www.stats.gov.cn/']} ]}
  prose=drafts.text_before_images(report)
  self.assertNotIn('核查同类岗位',prose)
  self.assertNotIn('国家统计局公报',prose)
  self.assertIn('完整图片报告',prose)
  self.assertLess(len(prose),3000)

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
  self.meta['articleLead']={'policy':'wechat-article-lead/2','eyebrow':'产业观察','hook':'本地岗位','opening':'正文'*11000,'signals':[],'value':'阅读价值','guide':'完整报告','source':'来源'}
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

 def test_expired_credentials_refresh_once_at_image_cover_or_draft_without_reuploading_completed_steps(self):
  for failing_stage,code in [('media/uploadimg','40001'),('material/add_material?type=image','42001'),('draft/add','42001')]:
   with self.subTest(stage=failing_stage):
    with lib.database() as db:
     db.execute('DELETE FROM drafts');db.execute('UPDATE sessions SET pending=2')
    self.calls=[];attempts=[];rejected=False
    def post(path,token,payload=None,image=None):
     nonlocal rejected
     attempts.append((path,token))
     if path==failing_stage and not rejected:
      rejected=True;raise drafts.DraftError('expired credential',code=code)
     return self.fake_post(path,token,payload,image)
    provider=Mock(side_effect=['old-token','new-token'])
    with patch.object(drafts,'_post',side_effect=post),patch('publish_draft.make_card_cover'):
     result=drafts.save_report('session1',self.id,'account',provider)
    self.assertEqual(result['state'],'saved')
    self.assertEqual(provider.call_args_list,[call(),call(force_refresh=True)])
    self.assertEqual(len(attempts),5)
    first=next(i for i,row in enumerate(attempts) if row[0]==failing_stage)
    self.assertEqual(attempts[first],(failing_stage,'old-token'))
    self.assertEqual(attempts[first+1],(failing_stage,'new-token'))
    self.assertTrue(all(token=='new-token' for _,token in attempts[first+1:]))

 def test_repeated_expired_token_is_bounded_and_a_known_rejection_remains_failed(self):
  self.calls=[]
  def post(path,token,payload=None,image=None):
   if path=='draft/add':raise drafts.DraftError('expired credential',code='40001')
   return self.fake_post(path,token,payload,image)
  provider=Mock(side_effect=['old-token','new-token'])
  with patch.object(drafts,'_post',side_effect=post) as network,patch('publish_draft.make_card_cover'):
   result=drafts.save_report('session1',self.id,'account',provider)
  self.assertEqual(result['state'],'failed')
  self.assertEqual(provider.call_count,2)
  self.assertEqual(sum(c.args[0]=='draft/add' for c in network.call_args_list),2)

 def test_whitelist_permission_and_uncertain_create_errors_are_never_automatically_retried(self):
  for code,uncertain,state in [('40164',False,'failed'),('48001',False,'failed'),('45009',False,'failed'),('42001',True,'unknown')]:
   with self.subTest(code=code,uncertain=uncertain):
    with lib.database() as db:
     db.execute('DELETE FROM drafts');db.execute('UPDATE sessions SET pending=2')
    self.calls=[]
    def post(path,token,payload=None,image=None):
     if path=='draft/add':raise drafts.DraftError('official result',code=code,uncertain=uncertain)
     return self.fake_post(path,token,payload,image)
    provider=Mock(return_value='token')
    with patch.object(drafts,'_post',side_effect=post) as network,patch('publish_draft.make_card_cover'):
     result=drafts.save_report('session1',self.id,'account',provider)
    self.assertEqual(result['state'],state)
    provider.assert_called_once_with()
    self.assertEqual(sum(c.args[0]=='draft/add' for c in network.call_args_list),1)

 def test_api_errors_preserve_code_and_only_show_valid_echoed_ip(self):
  response=Mock();response.json.return_value={'errcode':40164,'errmsg':'invalid ip 203.0.113.7, access_token=do-not-display'}
  with patch.object(drafts.requests,'post',return_value=response):
   with self.assertRaises(drafts.DraftError) as error:drafts._post('draft/add','private-token',{})
  self.assertEqual(error.exception.code,'40164')
  self.assertIn('203.0.113.7',str(error.exception))
  self.assertNotIn('do-not-display',str(error.exception))
  self.assertNotIn('private-token',str(error.exception))
  self.assertEqual(drafts.whitelist_message('invalid ip 999.1.1.1, secret=do-not-display'),'微信接口40164：主机出口IP不在公众号白名单')
  response.json.return_value={'errcode':42001,'errmsg':'access_token=do-not-display'}
  with patch.object(drafts.requests,'post',return_value=response):
   with self.assertRaises(drafts.DraftError) as error:drafts._post('draft/add','private-token',{})
  self.assertEqual(error.exception.code,'42001')
  self.assertNotIn('do-not-display',str(error.exception))

 def test_token_endpoint_whitelist_rejection_shows_current_ip_without_other_response_details(self):
  provider=Mock(side_effect=RuntimeError("获取 access_token 失败：{'errcode':40164,'errmsg':'invalid ip 203.0.113.8, token=do-not-display'}"))
  with patch.object(drafts,'_post') as network:
   result=drafts.save_report('session1',self.id,'account',provider)
  self.assertEqual(result['state'],'failed')
  self.assertIn('203.0.113.8',result['message'])
  self.assertNotIn('do-not-display',result['message'])
  network.assert_not_called()

 def test_create_response_without_media_id_is_unknown_and_cannot_create_again(self):
  self.calls=[]
  def post(path,token,payload=None,image=None):
   if path=='draft/add':return {}
   return self.fake_post(path,token,payload,image)
  with patch.object(drafts,'_post',side_effect=post) as network,patch('publish_draft.make_card_cover'):
   result=drafts.save_report('session1',self.id,'account',lambda:'token')
   self.assertEqual(result['state'],'unknown')
   previous=network.call_count
   self.assertEqual(drafts.save_report('session1',self.id,'account',lambda:'token')['state'],'unknown')
   self.assertEqual(network.call_count,previous)

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
