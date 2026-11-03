"""Versioned official context, explicitly separate from the platform sample."""
import hashlib
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent.parent


def reference_sections(data):
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
        blocks.append(('两类证据如何使用','官方统计用于交代跨产业研发环境，平台样本用于观察招聘条件和岗位结构。二者统计对象、年份与分母不同，不能混算，不能据研发投入推断本样本岗位增速、人工智能专项投入或学历的薪酬回报。'))
    if '人工智能' in data['meta']['industry']:
        standard=sources['ai-boundary-2026']
        refs.append({'id':str(len(refs)+1),'title':standard['title'],'authors':standard['authors'],'date':standard['published'],
                     'locator':standard['standard']+'；生效：'+standard['effective']+'。'+standard['scope'],'url':standard['url']})
    citations=[('['+ref['id']+'] '+ref['title'],ref['authors']+'；'+ref['date']+'。'+ref['locator']+(' 来源：'+ref['url'] if ref.get('url') else '')) for ref in refs]
    return {'schema':'wechat-references/1','registrySha256':hashlib.sha256(file.read_bytes()).hexdigest(),
            'verifiedOn':payload['verifiedOn'],'references':refs,'contextBlocks':[list(item) for item in blocks],
            'referenceBlocks':[list(item) for item in citations]}


def attach(outline,data):
    payload=reference_sections(data);outline['research_sources']=payload
    if payload['contextBlocks']:
        outline['screens'].append({'type':'notes','no':'背景','title':'官方背景与岗位样本的证据边界','blocks':payload['contextBlocks']})
    outline['screens'].append({'type':'notes','no':'文献','title':'参考文献与资料来源','blocks':payload['referenceBlocks']})
    return outline


def verify(outline,data):
    expected=reference_sections(data)
    if outline.get('research_sources')!=expected:raise ValueError('参考文献或官方统计背景与已核验目录不一致')
    notes=[screen for screen in outline['screens'] if screen['title']=='参考文献与资料来源']
    context=[screen for screen in outline['screens'] if screen['title']=='官方背景与岗位样本的证据边界']
    if len(notes)!=1 or notes[0]['blocks']!=expected['referenceBlocks']:raise ValueError('报告缺少完整参考文献')
    if expected['contextBlocks'] and (len(context)!=1 or context[0]['blocks']!=expected['contextBlocks']):raise ValueError('官方背景被错误省略或改写')
