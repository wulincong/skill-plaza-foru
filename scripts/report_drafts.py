"""Save a previously verified report as a private WeChat draft, with a durable receipt."""
from contextlib import closing
import hashlib
import html
import json
import time
from pathlib import Path
import sys

import requests

from report_library import database, STORE, checked_session


class DraftError(RuntimeError):
    def __init__(self,message,uncertain=False):
        super().__init__(message)
        self.uncertain=uncertain


def _post(path, token, payload=None, image=None):
    url='https://api.weixin.qq.com/cgi-bin/'+path
    try:
        if image:
            with Path(image).open('rb') as f:
                response=requests.post(url,params={'access_token':token},files={'media':(Path(image).name,f,'image/png')},timeout=(8,90))
        else:
            response=requests.post(url,params={'access_token':token},data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json; charset=utf-8'},timeout=(8,45))
        response.raise_for_status(); result=response.json()
    except requests.Timeout:
        raise DraftError('请求超时，保存状态需核对，不能自动重复创建',uncertain=True) from None
    except (requests.RequestException,ValueError):
        raise DraftError('微信接口连接或返回格式异常',uncertain=True) from None
    if result.get('errcode',0):
        code=str(result['errcode'])
        if code=='40164': raise DraftError('微信接口40164：主机出口IP不在公众号白名单')
        if code=='48001': raise DraftError('微信接口48001：公众号尚无该接口权限')
        raise DraftError('微信接口返回错误码'+code)
    return result


def text_before_images(report):
    """All report prose precedes images. No internal field paths or query evidence."""
    blocks=['<section style="font-size:16px;line-height:1.9;color:#263248">']
    blocks.append('<p><strong>'+html.escape(report['title'])+'</strong></p>')
    for screen in report['screens'][1:]:
        if screen.get('paragraphs') or screen.get('blocks'):
            blocks.append('<h2 style="font-size:18px;color:#1E3A8A">'+html.escape(screen['title'])+'</h2>')
        for paragraph in screen.get('paragraphs',[]):blocks.append('<p>'+html.escape(paragraph)+'</p>')
        if screen.get('summary'):blocks.append('<p>'+html.escape(screen['summary']['text'])+'</p>')
        for title,text in screen.get('blocks',[]):blocks.append('<p><strong>'+html.escape(title)+'：</strong>'+html.escape(text)+'</p>')
    blocks.append('</section>')
    return ''.join(blocks)


def save_report(session_id,report_id,account,token_provider):
    session_id=checked_session(session_id)
    if not report_id or any(ch not in '0123456789abcdef' for ch in report_id) or len(report_id)!=32:
        raise DraftError('报告标识无效')
    account_hash=hashlib.sha256(account.encode()).hexdigest()
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        session=db.execute('SELECT * FROM sessions WHERE id=? AND report_id=?',(session_id,report_id)).fetchone()
        previous=db.execute('SELECT * FROM drafts WHERE report_id=? AND account_hash=?',(report_id,account_hash)).fetchone()
        if previous and previous['state']=='saved':
            return {'state':'saved','message':'这份报告已在公众号草稿箱中，已保留原草稿，没有重复创建。'}
        if not session or session['pending']!=2: raise DraftError('缺少对这份成品的明确保存确认')
        if previous and previous['state'] in ('running','unknown'):
            return {'state':previous['state'],'message':'这份报告的草稿保存正在处理或状态待核对，暂不重复创建。'}
        row=db.execute("SELECT * FROM reports WHERE id=? AND state='ready'",(report_id,)).fetchone()
        if not row: raise DraftError('报告不可用')
        report=json.loads(row['metadata'])
        db.execute('INSERT OR REPLACE INTO drafts VALUES(?,?,?,NULL,NULL,?)',(report_id,account_hash,'running',time.time()))
    folder=STORE/'reports'/report_id
    phase='token'
    try:
        try: token=token_provider()
        except Exception as exc:
            # Existing token module may include request details. Only return a known status.
            message='微信接口40164：主机出口IP不在公众号白名单' if '40164' in str(exc) else '公众号调用凭据暂不可用'
            raise DraftError(message) from None
        images=sorted((folder/'images').glob('page_*.png'))
        if len(images)!=report['pageCount']: raise DraftError('归档图片不完整')
        if [hashlib.sha256(p.read_bytes()).hexdigest() for p in images]!=report.get('imageHashes'):
            raise DraftError('归档图片与已确认版本不一致，拒绝保存草稿')
        urls=[]
        for image in images:
            result=_post('media/uploadimg',token,image=image)
            url=result.get('url','')
            if not url.startswith(('http://mmbiz.qpic.cn/','https://mmbiz.qpic.cn/','http://mmbiz.qlogo.cn/','https://mmbiz.qlogo.cn/','https://mmbiz.qq.com/','http://mmbiz.qq.com/')):
                raise DraftError('微信未返回有效正文图片地址')
            urls.append(url)
        sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'.agents/skills/wechat-report/scripts'))
        from publish_draft import make_card_cover
        cover=folder/'draft-cover.png'
        lead=f"{report['positions']}条在招岗位、{report['companies']}家招聘企业、{report.get('cities',0)}座城市"
        make_card_cover(report['title'],lead,'产业人才数据观察',str(cover))
        media=_post('material/add_material?type=image',token,image=cover).get('media_id')
        if not media: raise DraftError('微信未返回封面素材标识')
        content=text_before_images(report)+''.join('<p><img style="width:100%;display:block" src="'+html.escape(url,quote=True)+'"></p>' for url in urls)
        title=report['title']
        while len(title.encode())>64:title=title[:-1]
        phase='draft'
        result=_post('draft/add',token,{'articles':[{'title':title,'author':'','digest':'基于平台岗位记录观察地区与产业人才需求。','content':content,'thumb_media_id':media,'content_source_url':report['webLinks'][0]['url']}]})
        if not result.get('media_id'):raise DraftError('微信未返回草稿标识')
        with database() as db:
            db.execute("UPDATE drafts SET state='saved',media_id=?,error_code=NULL,updated_at=? WHERE report_id=? AND account_hash=?",(result['media_id'],time.time(),report_id,account_hash))
            db.execute('UPDATE sessions SET pending=0,updated_at=? WHERE id=? AND report_id=?',(time.time(),session_id,report_id))
        return {'state':'saved','message':'已存入公众号后台草稿箱：文字总结在前，报告图片在后。未群发或发布。'}
    except Exception as exc:
        state='unknown' if phase=='draft' and (getattr(exc,'uncertain',False) or '超时' in str(exc) or not isinstance(exc,DraftError)) else 'failed'
        message=str(exc) if isinstance(exc,DraftError) else '草稿素材准备失败，请检查服务端运行日志'
        with database() as db:db.execute('UPDATE drafts SET state=?,error_code=?,updated_at=? WHERE report_id=? AND account_hash=?',(state,str(exc),time.time(),report_id,account_hash))
        return {'state':state,'message':message}
