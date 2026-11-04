"""Bounded regional evidence retrieval from a reviewed primary-source catalog.

Default report runs search the catalog and reuse its seven-day verified evidence
snapshot. The explicit refresh command fetches only selected official URLs;
search snippets, unrelated provinces and unverified quantitative claims cannot
be promoted to report evidence.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor,wait
from datetime import datetime,timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
import unicodedata
from urllib.parse import urlsplit
from urllib.request import Request,urlopen

CATALOG=Path(__file__).resolve().parent.parent/'assets/regional_sources.json'
POLICY='wechat-regional-research/1'
PARENTS={'深圳市':'广东省'}


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def normalized(text):return re.sub(r'\s+','',unicodedata.normalize('NFKC',text))


def checked_url(url):
    parsed=urlsplit(url)
    if parsed.scheme not in ('http','https') or parsed.username or parsed.password or not parsed.hostname or not parsed.hostname.endswith('.gov.cn'):
        raise ValueError('只接受目录中的政府公开文献地址')
    return url


def validate_source(source):
    checked_url(source['url'])
    if source['kind'] not in ('reported_statistics','policy_target','policy_framework','published_scenario_catalog'):
        raise ValueError('资料必须区分实际统计、政策目标和公开目录')
    proof=source['verification'];evidence=proof['evidenceText']
    if hashlib.sha256(evidence.encode()).hexdigest()!=proof['evidenceSha256']:raise ValueError('资料摘录指纹不一致')
    if any(normalized(anchor) not in normalized(evidence) for anchor in source['anchors']):raise ValueError('关键证据未包含在已核对摘录中')
    numerals={number for value in [*source['anchors'],source['published'],source['period']] for number in re.findall(r'\d+(?:\.\d+)?',normalized(value))}
    for fact in source['facts']:
        if not set(re.findall(r'\d+(?:\.\d+)?',normalized(fact))).issubset(numerals):raise ValueError('文献事实含未核对数字：'+source['id'])
        if source['kind']=='policy_target' and not re.search(r'目标|提出|规划|任务',fact):raise ValueError('政策目标缺少明确的目标语气')
    return True


def catalog_search(region,industry,query='',limit=2):
    payload=json.loads(CATALOG.read_text('utf-8'))
    if payload.get('schema')!='wechat-regional-source-catalog/1':raise ValueError('地区来源目录格式错误')
    subject=PARENTS.get(region,region)
    candidates=[]
    for source in payload['sources']:
        if source['region']!=subject or industry not in source['industries']:continue
        validate_source(source)
        words=[word for word in re.split(r'[\s，,、]+',query) if len(word)>=2]
        hay=source['title']+' '+source['applicationFocus']
        relevance=sum(word in hay for word in words)
        candidates.append((relevance,source['kind']=='reported_statistics',source['published'],source))
    selected=[entry[-1] for entry in sorted(candidates,key=lambda entry:entry[:3],reverse=True)[:limit]]
    return {'schema':POLICY,'requestedRegion':region,'subjectRegion':subject,'industry':industry,
        'contextScope':'parent_province' if region!=subject else 'same_region',
        'catalogSha256':hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
        'status':'found' if selected else 'no_local_sources','sources':selected,
        'cacheMaxAgeSeconds':payload['cacheMaxAgeSeconds']}


class PageText(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.skip=0;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','noscript','svg'):self.skip+=1
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript','svg'):self.skip=max(0,self.skip-1)
    def handle_data(self,text):
        if not self.skip and text.strip():self.parts.append(text.strip())


def refresh_source(source,timeout=6):
    started=time.monotonic()
    try:
        url=checked_url(source['url'])
        with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=timeout) as response:
            checked_url(response.url)
            raw=response.read(2_000_001)
            if len(raw)>2_000_000:raise ValueError('公开页面超过抓取预算')
            charset=response.headers.get_content_charset() or 'utf-8'
        if raw.startswith(b'%PDF'):
            with tempfile.TemporaryDirectory(prefix='regional-source-') as folder:
                pdf=Path(folder)/'source.pdf';pdf.write_bytes(raw)
                text=subprocess.check_output(['pdftotext','-layout',str(pdf),'-'],timeout=4).decode('utf-8')
        else:
            text=raw.decode(charset,errors='replace');parser=PageText();parser.feed(text);text=' '.join(parser.parts)
        if source['region'][:2] not in normalized(text):raise ValueError('正文缺少本地区主题')
        if any(normalized(anchor) not in normalized(text) for anchor in source['anchors']):raise ValueError('正文关键数据或政策对象与目录不一致')
        return {'id':source['id'],'status':'verified','seconds':round(time.monotonic()-started,3),'textSha256':hashlib.sha256(text.encode()).hexdigest(),'checkedAtUTC':datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        return {'id':source['id'],'status':'unavailable','seconds':round(time.monotonic()-started,3),'failure':type(exc).__name__}


def prepare(region,industry,refresh=False,budget_seconds=12):
    started=time.monotonic();result=catalog_search(region,industry)
    now=datetime.now(timezone.utc);accepted=[];observations=[]
    if refresh and result['sources']:
        executor=ThreadPoolExecutor(max_workers=2)
        futures={executor.submit(refresh_source,source,min(6,budget_seconds)):source for source in result['sources']}
        complete,pending=wait(futures,timeout=budget_seconds)
        observations=[future.result() for future in complete]
        observations.extend({'id':futures[future]['id'],'status':'budget_exceeded'} for future in pending)
        for future in pending:future.cancel()
        executor.shutdown(wait=False,cancel_futures=True)
    live={row['id']:row for row in observations}
    for source in result['sources']:
        age=(now-datetime.fromisoformat(source['verification']['verifiedAtUTC'])).total_seconds()
        fresh=live.get(source['id'],{}).get('status')=='verified'
        if fresh or 0<=age<=result['cacheMaxAgeSeconds']:
            source=dict(source,retrieval='live_official_page' if fresh else 'verified_catalog_snapshot')
            if fresh:source['liveVerification']=live[source['id']]
            accepted.append(source)
    result.update(sources=accepted,status='ready' if accepted else 'no_verified_local_sources',
        createdAtUTC=now.isoformat(),retrievalSeconds=round(time.monotonic()-started,4),observations=observations,
        evidenceHash=digest({'requestedRegion':region,'industry':industry,'sources':[{key:s[key] for key in ('id','region','kind','period','facts','applicationFocus','verification')} for s in accepted]}))
    return result


def scope(data):return {'region':data['meta']['region'],'industry':data['meta']['industry'],'filters':data['meta'].get('filters',{})}


def ensure_context(data,folder):
    file=Path(folder)/'report_research.json';wanted=scope(data)
    if file.exists():
        result=json.loads(file.read_text('utf-8'))
        if result.get('scope')!=wanted:raise ValueError('本地文献资料绑定了其他地域或筛选范围')
        if result.get('catalogSha256')!=hashlib.sha256(CATALOG.read_bytes()).hexdigest():raise ValueError('地区文献目录已更新，请重开本次报告写作')
        canonical=catalog_search(wanted['region'],wanted['industry'])
        known={source['id']:source for source in canonical['sources']}
        if result.get('subjectRegion')!=canonical['subjectRegion'] or result.get('contextScope')!=canonical['contextScope']:raise ValueError('本地文献的地区对象不一致')
        for source in result.get('sources',[]):
            validate_source(source)
            expected=known.get(source['id'])
            if not expected or any(source.get(key)!=value for key,value in expected.items()):raise ValueError('文献事实或出处被工作区改写')
        if result.get('schema')!=POLICY or result.get('cacheMaxAgeSeconds')!=canonical['cacheMaxAgeSeconds']:raise ValueError('本地资料策略或有效期被改写')
        created=datetime.fromisoformat(result['createdAtUTC'])
        catalog_time=datetime.fromisoformat(json.loads(CATALOG.read_text('utf-8'))['verifiedAtUTC'])
        if created.tzinfo is None or created<catalog_time or created.timestamp()>time.time()+300:raise ValueError('本地资料快照时间与已核对目录不一致')
        required={key for key,source in known.items() if 0 <= (created-datetime.fromisoformat(source['verification']['verifiedAtUTC'])).total_seconds() <= result['cacheMaxAgeSeconds']}
        actual=[source['id'] for source in result.get('sources',[])]
        if len(actual)!=len(set(actual)) or not required.issubset(actual):raise ValueError('工作区遗漏或重复了本地区已验证文献')
        expected_hash=digest({'requestedRegion':wanted['region'],'industry':wanted['industry'],'sources':[{key:s[key] for key in ('id','region','kind','period','facts','applicationFocus','verification')} for s in result.get('sources',[])]})
        if expected_hash!=result.get('evidenceHash'):raise ValueError('文献证据指纹不一致')
        return result
    result=prepare(wanted['region'],wanted['industry']);result['scope']=wanted
    file.parent.mkdir(parents=True,exist_ok=True)
    temporary=file.with_suffix('.tmp');temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8');temporary.replace(file)
    return result


def writing_context(data,folder):
    result=ensure_context(data,folder)
    return {'status':result['status'],'evidenceHash':result['evidenceHash'],'subjectRegion':result['subjectRegion'],'contextScope':result['contextScope'],
        'sources':[{key:source[key] for key in ('id','region','title','publisher','published','period','kind','url','facts','applicationFocus')} for source in result['sources']],
        'use':'facts是已对照原文的事实，applicationFocus是报告编写者的应用构想而非政府原文结论。事实和政策目标分别表述；地区文献用于课程场景和产业背景，不用产业规模推算招聘人数，不把省级背景写成城市统计。'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['search','prepare','refresh'])
    parser.add_argument('--region',required=True);parser.add_argument('--industry',required=True)
    parser.add_argument('--query',default='');parser.add_argument('--budget-seconds',type=float,default=12)
    parser.add_argument('--out');args=parser.parse_args()
    if args.action=='search':result=catalog_search(args.region,args.industry,args.query)
    else:result=prepare(args.region,args.industry,args.action=='refresh',min(12,max(1,args.budget_seconds)))
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.out:Path(args.out).write_text(text,'utf-8')
    print(text)


if __name__=='__main__':main()
