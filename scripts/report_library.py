"""Server-owned verified report catalog. JSON stdin/stdout; never load secrets for lookup."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import time
import uuid
from datetime import datetime,timezone
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parent.parent
STORE = Path(os.environ.get('REPORT_LIBRARY_ROOT', str(REPO/'web/server/report-library'))).resolve()
POLICY = 'wechat-report-library/1'
DEEP_PROFILE = 'education-multivariate-v2'
PUBLIC_PROFILE = DEEP_PROFILE


def digest(body):
    return hashlib.sha256(body).hexdigest()


@contextmanager
def database():
    STORE.mkdir(mode=0o700, parents=True, exist_ok=True)
    db = sqlite3.connect(STORE/'catalog.sqlite', timeout=20)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS reports (
      id TEXT PRIMARY KEY, scope_key TEXT NOT NULL, region TEXT NOT NULL, industry TEXT NOT NULL,
      profile TEXT NOT NULL, title TEXT NOT NULL, data_at TEXT NOT NULL, created_at REAL NOT NULL,
      content_hash TEXT NOT NULL, metadata TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'ready');
    CREATE INDEX IF NOT EXISTS scope_reports ON reports(scope_key,created_at);
    CREATE TABLE IF NOT EXISTS sessions (
      id TEXT PRIMARY KEY, report_id TEXT NOT NULL, pending INTEGER NOT NULL DEFAULT 1,
      updated_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS drafts (
      report_id TEXT NOT NULL, account_hash TEXT NOT NULL, state TEXT NOT NULL,
      media_id TEXT, error_code TEXT, updated_at REAL NOT NULL,
      PRIMARY KEY(report_id,account_hash));
    ''')
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def scope_key(filters, profile=PUBLIC_PROFILE):
    return digest(json.dumps({'policy':POLICY,'filters':filters,'profile':profile},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode())


def checked_session(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',value):
        raise ValueError('会话标识无效')
    return value


def public_record(row):
    meta=json.loads(row['metadata'])
    return {k:meta[k] for k in ['id','title','region','industry','dataAt','webLinks','downloads','pageCount','contentHash']}


def verify_build_receipt(base,outline,quality):
    """A new quality profile requires execution of the installed pipeline."""
    scripts=REPO/'.agents/skills/wechat-report/scripts'
    sys.path.insert(0,str(scripts))
    from generate_report import PIPELINE_FILES
    receipt=json.loads((base/'output/report/build_receipt.json').read_text('utf-8'))
    if receipt.get('schema')!='wechat-build/1':raise ValueError('缺少受信报告构建回执')
    stages=receipt.get('stages',[])
    names=[row.get('script') for row in stages]
    expected=['report_preflight.py','gen_outline.py','verify_data.py','render_report.py','verify_data.py','build_article.py','evidence_sheet.py','pack_delivery.py']
    if names not in (expected,expected[:1]+['report_analysis.py']+expected[1:]):raise ValueError('构建步骤不完整或顺序不符')
    if any(row.get('exitCode')!=0 or not isinstance(row.get('durationMs'),(int,float)) or row['durationMs']<0 for row in stages):raise ValueError('构建步骤未全部成功')
    expected_files={name:digest((scripts/name).read_bytes()) for name in PIPELINE_FILES}
    if receipt.get('pipelineFiles')!=expected_files:raise ValueError('生成代码版本与当前受信版本不一致，请沿用数据重新构建')
    values={'reportDataSha256':digest((base/'report_data.json').read_bytes()),
            'analysisSha256':digest((base/'report_analysis.json').read_bytes()),
            'outlineSha256':quality['outline_sha256'],'manifestSha256':quality['manifest_sha256']}
    if any(receipt.get(key)!=value for key,value in values.items()):raise ValueError('构建回执与当前数据、分析或图片不一致')
    started=datetime.fromisoformat(receipt['startedAt']);finished=datetime.fromisoformat(receipt['finishedAt'])
    if started.tzinfo is None or finished.tzinfo is None or started>finished or finished.timestamp()>time.time()+300:raise ValueError('构建回执时间无效')
    if (outline.get('analysis',{}).get('schema')!='wechat-analysis/2'
        or outline['analysis'].get('reasoningPolicy')!='wechat-analytic-reasoning/1'
        or outline.get('chart_selection',{}).get('policy')!='wechat-chart-selection/2'):raise ValueError('新版成品缺少总分总论证、受信结构分析或适用图型选择')
    return receipt


def stable_report_id(key,source_hash,outline_hash,image_hashes):
    # Render duration and the newly published URL do not create a new draft.
    return digest(json.dumps([key,source_hash,outline_hash,image_hashes],separators=(',',':')).encode())[:32]


def standard_scope(data,binding):
    filters=data['meta']['filters']
    all_cohort=next((row for row in binding['_result']['cohorts'] if row['id']=='all'),{})
    entities=all_cohort.get('resolved',{}).get('industries',{}).get('entities',[])
    audience=data['meta'].get('audience')
    return (filters.get('region',{}).get('level')=='province' and not filters.get('updatedAt')
            and all(not filters.get(key) for key in ('education','experience','jobType','roles'))
            and all(not value for value in filters.get('title',{}).values())
            and len(filters.get('industries',[]))==1 and len(entities)==1
            and entities[0].get('level')==0 and entities[0].get('includeDescendants') is True
            and data['meta']['industry']==entities[0]['name']==data['meta'].get('scope_industry')
            and audience in ('院校管理者与产教融合负责人','院校与产业研究读者','院校管理者','院校人才培养与校企合作读者','院校与产教融合负责人'))


def register(args):
    workspace=Path(args['workspace']).resolve(strict=True)
    allowed=(REPO/'web/server/workspace').resolve()
    if not workspace.is_relative_to(allowed):
        raise ValueError('仅登记服务端会话工作区中的报告')
    base=workspace/'wechat-report'
    if base.is_symlink(): raise ValueError('报告目录不能是符号链接')
    sys.path.insert(0,str(REPO/'.agents/skills/wechat-report/scripts'))
    from bound_report import load_data,verify_outline
    previous=Path.cwd()
    try:
        os.chdir(base)
        data,binding=load_data(base/'report_data.json')
        outline_file=base/'output/outline/report_outline.json'
        outline=json.loads(outline_file.read_text())
        verify_outline(data,binding,outline)
    finally:
        os.chdir(previous)
    report=base/'output/report'
    mf=report/'manifest.json'; manifest=json.loads(mf.read_text())
    quality=json.loads((report/'quality.json').read_text())
    if (quality.get('all_pass') is not True or quality.get('schema')!='wechat-quality/1'
        or quality.get('manifest_sha256')!=digest(mf.read_bytes())
        or quality.get('outline_sha256')!=digest(outline_file.read_bytes())):
        raise ValueError('报告没有匹配当前版本的最终质检')
    links=args.get('webLinks',[]); downloads=args.get('downloads',[])
    if not links or any(urlsplit(x.get('url','')).scheme not in ('http','https') for x in links+downloads):
        raise ValueError('缺少平台实际发布的报告链接')
    files=[]
    for page in manifest['pages']:
        path=(report/page['file']).resolve()
        if not path.is_relative_to(report.resolve()) or path.is_symlink() or digest(path.read_bytes())!=page.get('sha256'):
            raise ValueError('图片指纹错误，不能入库')
        files.append(path)
    modern=outline.get('presentation')=='wechat-multivariate/1'
    receipt=verify_build_receipt(base,outline,quality) if modern else None
    filters=data['meta']['filters']; profile=DEEP_PROFILE if modern else 'education-general-v1'
    if args.get('profile',profile)!=profile:raise ValueError('不能覆盖报告的实际质量版本')
    standard=standard_scope(data,binding)
    if not standard: profile='custom-scope'
    key=scope_key(filters,profile)
    image_hashes=[digest(p.read_bytes()) for p in files]
    report_id=stable_report_id(key,binding['source']['contentHash'],quality['outline_sha256'],image_hashes) if modern else digest((key+binding['source']['contentHash']+quality['outline_sha256']+quality['manifest_sha256']).encode())[:32]
    meta={'id':report_id,'title':outline['title'],'region':data['meta']['region'],'industry':data['meta']['industry'],
          'dataAt':data['meta']['generated_at'],'webLinks':links,'downloads':downloads,'pageCount':len(files),
          'contentHash':binding['source']['contentHash'],'filters':filters,'profile':profile,
          'analysis':outline['analysis'],'screens':outline['screens'],'positions':data['total']['positions'],
          'companies':data['total']['companies'],'cities':data['total'].get('cities'),
          'imageHashes':image_hashes,
          'sourceRun':args.get('runId'), 'humanReview':'pending',
          'programQuality':'pass','buildReceipt':receipt,'qualityProfile':DEEP_PROFILE if modern else 'education-general-v1'}
    destination=STORE/'reports'/report_id
    with database() as db:
        if not destination.exists():
            temporary=STORE/('pending-'+uuid.uuid4().hex)
            temporary.mkdir(mode=0o700)
            try:
                (temporary/'images').mkdir()
                for i,file in enumerate(files): shutil.copyfile(file,temporary/'images'/f'page_{i+1:02}.png')
                (temporary/'report.json').write_text(json.dumps(meta,ensure_ascii=False))
                destination.parent.mkdir(exist_ok=True)
                temporary.rename(destination)
            finally:
                if temporary.exists(): shutil.rmtree(temporary)
        db.execute('INSERT OR IGNORE INTO reports(id,scope_key,region,industry,profile,title,data_at,created_at,content_hash,metadata) VALUES(?,?,?,?,?,?,?,?,?,?)',
                   (report_id,key,meta['region'],meta['industry'],profile,meta['title'],meta['dataAt'],time.time(),meta['contentHash'],json.dumps(meta,ensure_ascii=False)))
        db.execute('UPDATE reports SET metadata=? WHERE id=?',(json.dumps(meta,ensure_ascii=False),report_id))
        temporary_meta=destination/'report.json.tmp'
        temporary_meta.write_text(json.dumps(meta,ensure_ascii=False),'utf-8');os.replace(temporary_meta,destination/'report.json')
        session=checked_session(args['sessionId'])
        db.execute('INSERT OR REPLACE INTO sessions VALUES(?,?,1,?)',(session,report_id,time.time()))
        row=db.execute('SELECT * FROM reports WHERE id=?',(report_id,)).fetchone()
        return {'status':row['state'],'report':public_record(row)}


PROVINCES=['广东省','山东省','浙江省','江苏省','河南省','河北省','四川省','湖北省','湖南省','福建省','安徽省','陕西省','北京市','上海市','重庆市','天津市']
INDUSTRIES=['人工智能','智能制造','机器人','低空经济','新能源汽车','新一代信息技术','纺织服装','生物医药','新能源']


def parse_brief(text):
    """Conservative fast path only: non-default dates/audiences/personal uploads bypass it."""
    if not re.search(r'报告|人才需求',text) or re.search(r'去年|今年|(?:近|过去)[一二三四五六七八九十两\d]|最近|同比|月份|季度|年度|年报|\d{4}年|重新|最新|刷新|附件|上传|简历|企业内部|面向企业|中职|本科生|高职生',text):
        return None
    region=[p for p in PROVINCES if p in text or p.removesuffix('省').removesuffix('市') in text]
    industry=[p for p in INDUSTRIES if p in text]
    industry=[p for p in industry if not any(p!=q and p in q for q in industry)]
    if len(region)!=1 or len(industry)!=1: return None
    # Only a whole-province, otherwise unqualified request may use the shared fast path.
    # Unknown cities, readers, salary/skill filters and presentation instructions remain for Pi.
    rest=text.replace(region[0],'').replace(region[0].removesuffix('省').removesuffix('市'),'').replace(industry[0],'')
    fillers=['微信公众号','人才需求观察报告','人才需求分析报告','人才需求报告','人才需求','观察报告','分析报告','产业链','帮我','帮忙','我想要','想看','请您','麻烦','提供','生成','制作','针对','关于','一份','一篇','公众号','行业','产业','报告','全省','地区','给我','请','的','来','做','需要','我','想','要']
    for word in sorted(fillers,key=len,reverse=True):rest=rest.replace(word,'')
    if re.sub(r'[\s，。！？、：:,.!?]+','',rest): return None
    return region[0],industry[0]


def lookup(args):
    brief=parse_brief(args.get('text',''))
    if not brief: return {'status':'miss','reason':'not_default_scope'}
    age=min(max(float(args.get('maxAgeSeconds',7*86400)),0),30*86400)
    with database() as db:
        cutoff=datetime.fromtimestamp(time.time()-age,timezone.utc).isoformat().replace('+00:00','Z')
        row=db.execute("SELECT * FROM reports WHERE region=? AND industry=? AND profile=? AND state='ready' AND data_at>=? ORDER BY data_at DESC,created_at DESC LIMIT 1",
                       (*brief,PUBLIC_PROFILE,cutoff)).fetchone()
        if not row: return {'status':'miss','reason':'no_matching_report'}
        report=public_record(row)
        if args.get('sessionId'):
            session=checked_session(args['sessionId'])
            db.execute('INSERT OR REPLACE INTO sessions VALUES(?,?,1,?)',(session,row['id'],time.time()))
        return {'status':'hit','report':report}


YES={'是','是的','好','好的','可以','需要','确定','确认','保存','存草稿','保存草稿','存到草稿箱','存入草稿箱','保存到草稿箱','保存到公众号草稿箱','确认保存'}
YES.update({'嗯','嗯嗯','好啊','好呀','好的呀','可以啊','可以呀','可以的','没问题','确定吧','确认吧','保存吧','存吧','保存一下','存一下','确认保存吧','好的保存吧','好的存吧'})
NO={'不','不需要','不要','取消','暂不保存','不用了','不保存'}


def pending_reply_candidate(text):
    value=re.sub(r'[\s。！!，,]+$','',text.strip())
    return re.sub(r'[，,、\s]+','',value) in YES or value in NO


def consent(args):
    text=re.sub(r'[\s。！!，,]+$','',args.get('text','').strip())
    affirmative=re.sub(r'[，,、\s]+','',text)
    session=checked_session(args['sessionId'])
    with database() as db:
        row=db.execute('SELECT s.*,r.metadata FROM sessions s JOIN reports r ON r.id=s.report_id WHERE s.id=?',(session,)).fetchone()
        if not row: return {'status':'unhandled'}
        explicit=bool(re.fullmatch(r'(?:请帮我|麻烦帮我|麻烦|我想|我要|需要|请|帮我)?(?:把(?:刚才|这份|这个|刚刚)?(?:的)?(?:报告|成品))?(?:保存|存|存入|保存到|存到)(?:到)?(?:公众号|微信)?(?:后台)?(?:的)?草稿(?:箱)?',text))
        if (len(text)<=120 and '草稿' in text and re.search(r'保存|存入|存到',text)
            and not re.search(r'不|取消|别|如果|是否|能否|可否|如何|怎么|吗|么|[?？]|上一|之前|上个|另一',text)):
            explicit=True
        if not explicit and (not row['pending'] or time.time()-row['updated_at']>86400 or affirmative not in YES and text not in NO):
            # A generic yes after another topic must never authorize a draft.
            db.execute('UPDATE sessions SET pending=0 WHERE id=?',(session,))
            return {'status':'unhandled'}
        if text in NO:
            db.execute('UPDATE sessions SET pending=0,updated_at=? WHERE id=?',(time.time(),session))
            return {'status':'declined'}
        db.execute('UPDATE sessions SET pending=2,updated_at=? WHERE id=?',(time.time(),session))
        return {'status':'confirmed','reportId':row['report_id']}


def state(args):
    session=checked_session(args['sessionId'])
    with database() as db:
        row=db.execute('SELECT * FROM sessions WHERE id=?',(session,)).fetchone()
        return {'status':'present' if row else 'absent','pending':bool(row and row['pending'] and time.time()-row['updated_at']<86400)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['register','lookup','consent','state','list'])
    action=parser.parse_args().action
    args=json.loads(sys.stdin.read(1024*1024) or '{}')
    if action=='list':
        with database() as db: result={'reports':[public_record(r) for r in db.execute("SELECT * FROM reports WHERE state='ready' ORDER BY created_at DESC LIMIT 100")]}
    else: result=globals()[action](args)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(json.dumps({'status':'error','message':str(exc)},ensure_ascii=False));sys.exit(1)
