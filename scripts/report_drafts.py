"""Save a previously verified report as a private WeChat draft, with a durable receipt."""
from contextlib import closing
import hashlib
import html
import io
import json
import ipaddress
import re
import time
from pathlib import Path
import sys

import requests

from report_library import database, STORE, checked_session


class DraftError(RuntimeError):
    def __init__(self,message,uncertain=False,code=None):
        super().__init__(message)
        self.uncertain=uncertain
        self.code=code


def whitelist_message(detail):
    """Only expose a parsed IP, never the raw credential-bearing response/URL."""
    message='微信接口40164：主机出口IP不在公众号白名单'
    match=re.search(r'\binvalid ip\s+([\da-fA-F:.]+)',detail,re.I)
    if match:
        try: return message+'（本次接口回显出口IP：'+str(ipaddress.ip_address(match[1]))+'）'
        except ValueError: pass
    return message


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
        if code=='40164': raise DraftError(whitelist_message(str(result.get('errmsg',''))),code=code)
        if code=='48001': raise DraftError('微信接口48001：公众号尚无该接口权限',code=code)
        raise DraftError('微信接口返回错误码'+code,code=code)
    return result


def text_before_images(report):
    """All report prose precedes images. No internal field paths or query evidence."""
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'.agents/skills/wechat-report/scripts'))
    from article_content import html_prose
    return html_prose(report)


def upload_image_parts(images,folder,limit=960000):
    """Conservative upload budget, preserving every source pixel and its order.

    Long pages are losslessly tiled, preferably at white gaps. The original
    confirmed PNG archive is never modified or downsampled.
    """
    from PIL import Image
    output=[]
    target=folder/'draft-image-parts'
    for source in images:
        if source.stat().st_size<limit:
            output.append(source);continue
        target.mkdir(mode=0o700,exist_ok=True)
        with Image.open(source) as original:
            gray=original.convert('L');number=0
            def write_part(top,bottom):
                nonlocal number
                part=original.crop((0,top,original.width,bottom))
                buffer=io.BytesIO();part.save(buffer,format='PNG',optimize=True)
                if len(buffer.getvalue())<limit:
                    number+=1;file=target/(source.stem+f'_part_{number:03}.png')
                    file.write_bytes(buffer.getvalue());output.append(file);return
                if bottom-top<64:raise DraftError('图片无法在上传预算内完整分段，已停止保存，原成品保留')
                middle=(top+bottom)//2;cut=None;span=(bottom-top)//3
                # Ignore the report's thin coloured page edge, while retaining
                # it in the actual tiles. No rows or pixels are discarded.
                left=min(42,original.width//5);right=max(left+1,original.width-left)
                for distance in range(span):
                    for row in (middle+distance,middle-distance):
                        if row<=top or row>=bottom:continue
                        if gray.crop((left,row,right,row+1)).getextrema()[0]>=248:
                            cut=row;break
                    if cut is not None:break
                cut=cut or middle
                write_part(top,cut);write_part(cut,bottom)
            write_part(0,original.height)
    return output


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
            db.execute('UPDATE sessions SET pending=0,updated_at=? WHERE id=? AND report_id=?',(time.time(),session_id,report_id))
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
        images=sorted((folder/'images').glob('page_*.png'))
        if len(images)!=report['pageCount']: raise DraftError('归档图片不完整')
        if [hashlib.sha256(p.read_bytes()).hexdigest() for p in images]!=report.get('imageHashes'):
            raise DraftError('归档图片与已确认版本不一致，拒绝保存草稿')
        prose=text_before_images(report)
        if len(prose)>=20000 or len(prose.encode())>=1000000:raise DraftError('完整文字超过当前草稿预算，已停止保存，原成品保留')
        upload_images=upload_image_parts(images,folder)
        def access_token(refresh=False):
            try: return token_provider(force_refresh=True) if refresh else token_provider()
            except Exception as exc:
                # The existing token module may include secrets in exception details.
                message=whitelist_message(str(exc)) if '40164' in str(exc) else '公众号调用凭据暂不可用'
                raise DraftError(message,code='40164' if '40164' in str(exc) else None) from None
        token=access_token()

        def post(path,payload=None,image=None):
            nonlocal token
            for attempt in range(2):
                try: return _post(path,token,payload=payload,image=image)
                except DraftError as exc:
                    # An explicit rejected credential is safe to refresh once.
                    # A timeout, unknown create result or any other API error is not.
                    if attempt or exc.uncertain or exc.code not in ('40001','42001'): raise
                    token=access_token(refresh=True)
        urls=[]
        for image in upload_images:
            result=post('media/uploadimg',image=image)
            url=result.get('url','')
            if not url.startswith(('http://mmbiz.qpic.cn/','https://mmbiz.qpic.cn/','http://mmbiz.qlogo.cn/','https://mmbiz.qlogo.cn/','https://mmbiz.qq.com/','http://mmbiz.qq.com/')):
                raise DraftError('微信未返回有效正文图片地址')
            urls.append(url)
        sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'.agents/skills/wechat-report/scripts'))
        from publish_draft import make_card_cover
        cover=folder/'draft-cover.png'
        lead=f"{report['positions']}条在招岗位、{report['companies']}家招聘企业、{report.get('cities',0)}座城市"
        make_card_cover(report['title'],lead,'产业人才数据观察',str(cover))
        media=post('material/add_material?type=image',image=cover).get('media_id')
        if not media: raise DraftError('微信未返回封面素材标识')
        content=prose+''.join('<p style="margin:0;line-height:0"><img style="width:100%;display:block" src="'+html.escape(url,quote=True)+'"></p>' for url in urls)
        if len(content)>=20000 or len(content.encode())>=1000000:raise DraftError('图片链接与完整文字超过当前草稿预算，已停止创建，原成品保留')
        title=report['title']
        while len(title.encode())>64:title=title[:-1]
        phase='draft'
        result=post('draft/add',{'articles':[{'title':title,'author':'','digest':'基于平台岗位记录观察地区与产业人才需求。','content':content,'thumb_media_id':media,'content_source_url':report['webLinks'][0]['url']}]})
        if not result.get('media_id'):raise DraftError('微信未返回草稿标识，保存状态需核对',uncertain=True)
        with database() as db:
            db.execute("UPDATE drafts SET state='saved',media_id=?,error_code=NULL,updated_at=? WHERE report_id=? AND account_hash=?",(result['media_id'],time.time(),report_id,account_hash))
            db.execute('UPDATE sessions SET pending=0,updated_at=? WHERE id=? AND report_id=?',(time.time(),session_id,report_id))
        return {'state':'saved','message':'已存入公众号后台草稿箱：文字总结在前，报告图片在后。未群发或发布。'}
    except Exception as exc:
        state='unknown' if phase=='draft' and (getattr(exc,'uncertain',False) or '超时' in str(exc) or not isinstance(exc,DraftError)) else 'failed'
        message=str(exc) if isinstance(exc,DraftError) else '草稿素材准备失败，请检查服务端运行日志'
        with database() as db:db.execute('UPDATE drafts SET state=?,error_code=?,updated_at=? WHERE report_id=? AND account_hash=?',(state,str(exc),time.time(),report_id,account_hash))
        return {'state':state,'message':message}
