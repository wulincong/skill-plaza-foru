"""Versioned official context, explicitly separate from the platform sample."""
import hashlib
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent.parent


def reference_sections(data,binding=None):
    file=BASE/'assets/official_context.json'
    payload=json.loads(file.read_text('utf-8'))
    if payload.get('schema')!='wechat-official-context/1':raise ValueError('官方来源目录格式无效')
    sources={source['id']:source for source in payload['sources']}
    rd=sources['nbs-rd-2025'];region=rd['regions'].get(data['meta']['region'])
    refs=[{'id':'1','title':'优才知路平台数据库：'+data['meta']['region']+data['meta']['industry']+'在招岗位统计快照',
           'authors':'平台岗位数据库','date':data['meta']['generated_at'][:10],
           'locator':'本报告所列筛选范围、同事务聚合及指标绑定；内部查询证据留存，未公开岗位明细。'}]
    blocks=[]
    if region:
        refs.append({'id':'2','title':rd['title'],'authors':rd['authors'],'date':rd['published'],
                     'locator':rd['locator'],'url':rd['url']})
        blocks.append(('官方统计背景 [2]',f"{rd['year']}年，{data['meta']['region']}全社会R&D经费为{region['expenditure100mCny']}亿元，投入强度{region['intensityPct']}%；全国投入强度为{rd['national']['intensityPct']}%。"))
        blocks.append(('统计对象','国家统计局数据描述年度全社会研发投入；岗位数据描述本报告筛选范围内的在招岗位。两者分别用于创新环境与岗位结构分析。'))
    from regional_research import ensure_context,prepare
    local=ensure_context(data,binding['_report_root']) if binding and binding.get('_report_root') else prepare(data['meta']['region'],data['meta']['industry'])
    local_blocks=[]
    kinds={'reported_statistics':'公开产业资料','policy_target':'政策目标','policy_framework':'应用支持方向','published_scenario_catalog':'应用场景目录'}
    for source in local['sources']:
        index=str(len(refs)+1)
        refs.append({'id':index,'title':source['title'],'authors':source['publisher'],'date':source['published'],'locator':source['period']+'；'+kinds[source['kind']],'url':source['url']})
        local_blocks.append((kinds[source['kind']]+' ['+index+']',' '.join(source['facts'])))
    if local['sources']:
        focus=next((source['applicationFocus'] for source in local['sources'] if source['kind'] in ('policy_target','policy_framework','published_scenario_catalog')),local['sources'][0]['applicationFocus'])
        local_blocks.append(('与本地岗位的结合',focus))
    if '人工智能' in data['meta']['industry']:
        standard=sources['ai-boundary-2026']
        refs.append({'id':str(len(refs)+1),'title':standard['title'],'authors':standard['authors'],'date':standard['published'],
                     'locator':standard['standard']+'；生效：'+standard['effective']+'。产业边界参考；本文岗位仍按平台产业标签筛选。','url':standard['url']})
    citations=[('['+ref['id']+'] '+ref['title'],ref['authors']+'；'+ref['date']+'。'+ref['locator']+(' 来源：'+ref['url'] if ref.get('url') else '')) for ref in refs]
    return {'schema':'wechat-references/2','registrySha256':hashlib.sha256(file.read_bytes()).hexdigest(),
            'regionalCatalogSha256':local['catalogSha256'],'regionalEvidenceHash':local['evidenceHash'],
            'regionalBlocks':[list(item) for item in local_blocks],
            'regionalSubject':local['subjectRegion'],'regionalContextScope':local['contextScope'],
            'verifiedOn':payload['verifiedOn'],'references':refs,'contextBlocks':[list(item) for item in blocks],
            'referenceBlocks':[list(item) for item in citations]}


def attach(outline,data,binding=None):
    payload=reference_sections(data,binding);outline['research_sources']=payload
    if payload['regionalBlocks']:
        import re
        position=min(2,len(outline['screens']))
        title=payload['regionalSubject']+'产业语境与应用场景'
        if payload['regionalContextScope']=='parent_province':title+='（省级背景）'
        outline['screens'].insert(position,{'type':'notes','no':'地区','title':title,'blocks':payload['regionalBlocks'],'regional_context':True})
        rebound={}
        for path,spec in outline.get('bindings',{}).items():
            match=re.match(r'^/screens/(\d+)(/.*)$',path)
            if match and int(match.group(1))>=position:path='/screens/'+str(int(match.group(1))+1)+match.group(2)
            rebound[path]=spec
        if 'bindings' in outline:outline['bindings']=rebound
    if payload['contextBlocks']:
        outline['screens'].append({'type':'notes','no':'背景','title':'官方研发投入背景','blocks':payload['contextBlocks']})
    outline['screens'].append({'type':'notes','no':'文献','title':'参考文献与资料来源','blocks':payload['referenceBlocks']})
    return outline


def verify(outline,data,binding=None):
    expected=reference_sections(data,binding)
    if outline.get('research_sources')!=expected:raise ValueError('参考文献或官方统计背景与已核验目录不一致')
    notes=[screen for screen in outline['screens'] if screen['title']=='参考文献与资料来源']
    context=[screen for screen in outline['screens'] if screen['title']=='官方研发投入背景']
    if len(notes)!=1 or notes[0]['blocks']!=expected['referenceBlocks']:raise ValueError('报告缺少完整参考文献')
    if expected['contextBlocks'] and (len(context)!=1 or context[0]['blocks']!=expected['contextBlocks']):raise ValueError('官方背景被错误省略或改写')
    local=[screen for screen in outline['screens'] if screen.get('regional_context')]
    if expected['regionalBlocks'] and (len(local)!=1 or local[0]['blocks']!=expected['regionalBlocks']):raise ValueError('本地区文献事实被省略或改写')
