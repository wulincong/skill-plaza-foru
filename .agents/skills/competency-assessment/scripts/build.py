"""Validate JD-derived competency evidence and render a materials-based assessment."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('job_matching_shared',ROOT.parent/'job-matching/scripts/matching.py')
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)
require=shared.require
LEVELS={0:'明确尚未掌握',1:'理解概念',2:'在指导下完成',3:'独立完成',4:'处理复杂问题并优化'}


def text(value, name):
    require(isinstance(value,str) and bool(value.strip()),'缺少'+name)
    return value


def student_materials(source):
    return '\n'.join(str(source.get(key) or '') for key in ('resume','studentMaterials')).strip()


def checked_quote(value, source):
    require(isinstance(value,str) and 0<len(value.strip())<=300,'引文应为不超过300字的相关原话')
    return shared.source_quote(value,source)


def validate(plan,source):
    records={r['positionId']:r for r in source['records']}
    mode=plan.get('mode');require(mode in ('direction','position'),'测评模式必须为direction或position')
    selected=plan.get('selectedJobs');require(isinstance(selected,list) and 1<=len(selected)<=10,'请选择1–10个相关岗位')
    ids=[r.get('id') for r in selected]
    require(all(isinstance(i,str) and i in records for i in ids) and len(ids)==len(set(ids)),'岗位必须来自本轮候选且不重复')
    require(mode!='position' or len(ids)==1,'具体岗位模式只能选择一个岗位')
    for row in selected:text(row.get('reason'),'岗位代表性说明')
    text(plan.get('targetRole'),'目标岗位');text(plan.get('summary'),'评测结论')
    if source.get('filters'):
        require(plan['targetRole']==source['filters']['keyword'],'报告目标岗位须与本轮查询一致')
    scope=source.get('assessmentScope')
    if scope:
        require(mode==scope['mode'],'测评模式须遵循用户选择')
        if mode=='position':require(bool(scope['positionId']) and ids==[scope['positionId']],'具体岗位须由用户选定对应ID')
    materials=student_materials(source);require(bool(materials) and source.get('hasAbilityMaterials',bool(source.get('resume','').strip())),'请先补充学生经历、技能或简历材料，再生成测评')
    def sources(items, capability=False):
        require(isinstance(items,list) and bool(items),'每项判断须有JD依据')
        for item in items:
            require(item.get('positionId') in ids,'依据须来自选定JD')
            item['quote']=checked_quote(item.get('quote'),records[item['positionId']]['positionDescription'])
            if capability:
                require(item.get('basis') in ('explicit','inferred'),'区分JD明示和AI推导')
                if item['basis']=='inferred':text(item.get('reason'),'能力推导理由')
    qualifications=plan.get('qualifications')
    require(isinstance(qualifications,list),'资格条件须独立列出，未明确时用空列表')
    for q in qualifications:
        text(q.get('name'),'资格名称');text(q.get('reason'),'资格判断理由')
        require(q.get('status') in ('符合','不符合','待确认'),'资格状态无效')
        sources(q.get('sources'))
        if q.get('studentQuote'):q['studentQuote']=checked_quote(q['studentQuote'],materials)
        else:require(q['status']=='待确认','无学生证据时资格只能待确认')
    rows=plan.get('competencies');require(isinstance(rows,list) and 1<=len(rows)<=20,'能力指标应有1–20项')
    identifiers=[]
    for row in rows:
        identifiers.append(text(row.get('id'),'指标ID'))
        for key in ('name','dimension','explanation'):text(row.get(key),key)
        require(type(row.get('weight')) is int and 1<=row['weight']<=100,'权重应为1–100的整数')
        require(type(row.get('requiredLevel')) is int and 1<=row['requiredLevel']<=4,'要求等级应为1–4')
        require('observedLevel' in row,'材料等级不可遗漏，未知请显式填null')
        observed=row.get('observedLevel')
        require(observed is None or (type(observed) is int and 0<=observed<=4),'材料支持等级应为0–4或null')
        sources(row.get('sources'),True)
        evidence=row.get('evidence');require(isinstance(evidence,list),'学生证据应为列表')
        for item in evidence:
            text(item.get('kind'),'材料类型');item['quote']=checked_quote(item.get('quote'),materials)
        require(observed is None or bool(evidence),'非空等级必须有学生原话依据')
        action=row.get('improvement');require(isinstance(action,dict),'每项能力须给出验证或提升任务')
        for key in ('task','deliverable','check','priority'):text(action.get(key),key)
    require(len(identifiers)==len(set(identifiers)),'指标ID不得重复')
    require(sum(r['weight'] for r in rows)==100,'能力权重之和必须为100')
    known=[r for r in rows if r.get('observedLevel') is not None]
    coverage=sum(r['weight'] for r in known)
    score=round(sum(min(r['observedLevel']/r['requiredLevel'],1)*r['weight'] for r in known)) if len(known)==len(rows) else None
    return {'score':score,'coverage':coverage,'assessed':len(known),'total':len(rows)}


def section(title,blocks):return {'type':'section','title':title,'blocks':blocks}

def build_page(plan,source):
    metrics=validate(plan,source);rows=plan['competencies'];records={r['positionId']:r for r in source['records']}
    blocks=[{'type':'summary','lead':'先看你的岗位准备情况','text':plan['summary']},
        {'type':'metrics','items':[
            {'label':'综合符合度','value':metrics['score'] if metrics['score'] is not None else '未评估','unit':'/100' if metrics['score'] is not None else ''},
            {'label':'已评估指标','value':f"{metrics['assessed']}/{metrics['total']}",'unit':'项'},
            {'label':'材料可评估覆盖','value':metrics['coverage'],'unit':'%','note':'按能力权重计算，表示信息覆盖，不代表真实性认证'},
        ]}]
    blocks.append({'type':'callout','text':'这是基于提交材料的胜任力初评。等级与权重由AI依据JD形成分析量表，未经企业确认；项目自述未经实操验证。未知不补零，任一指标未知时不生成完整综合分，分数不代表录用概率。'})
    if plan['mode']=='direction' and len(plan['selectedJobs'])<5:
        blocks.append({'type':'callout','text':f"本次仅有{len(plan['selectedJobs'])}份相关岗位说明作为依据，结论适用于这些岗位，不能代表整个岗位方向。"})
    if source.get('warning'):blocks.append({'type':'callout','text':'岗位资料覆盖存在限制，结论仅适用于列出的岗位原文。'})
    if plan['qualifications']:
        blocks.append(section('任职门槛核验',[{'type':'table','columns':[{'label':x} for x in ('条件','判断','依据与待确认事项')],
            'rows':[[q['name'],q['status'],q['reason']] for q in plan['qualifications']]}]))
    else:blocks.append(section('任职门槛核验',[{'type':'text','text':'所选JD未形成可单独核验的任职门槛；不据此推断企业没有门槛。'}]))
    blocks.append(section('能力画像与要求对比',[{'type':'table','columns':[{'label':x} for x in ('能力维度','能力指标','权重','要求等级','材料支持等级','判断')],
        'rows':[[r['dimension'],r['name'],str(r['weight'])+'%',r['requiredLevel'],r['observedLevel'] if r['observedLevel'] is not None else '未知',
        '信息不足' if r['observedLevel'] is None else '达到分析要求' if r['observedLevel']>=r['requiredLevel'] else '有证据支持的差距'] for r in rows],
        'note':'0明确尚未掌握；1理解概念；2在指导下完成；3独立完成；4处理复杂问题并优化。材料支持等级依据自述与成果描述，不等于实测等级。'}]))
    for title,group in (
        ('已有材料支持的优势',[r for r in rows if r['observedLevel'] is not None and r['observedLevel']>=r['requiredLevel']]),
        ('有证据支持的能力差距',[r for r in rows if r['observedLevel'] is not None and r['observedLevel']<r['requiredLevel']]),
        ('待补充证据的能力',[r for r in rows if r['observedLevel'] is None])):
        if not group:continue
        details=[]
        for row in group:
            evidence=[]
            for item in row['sources']:
                job=records[item['positionId']];basis='JD明示' if item['basis']=='explicit' else 'AI推导'
                evidence.append(f"- **{basis}**：{shared.escaped(job['positionName'])}：“{shared.escaped(item['quote'])}”。"+((' 推导理由：'+item['reason']) if item['basis']=='inferred' else ''))
            evidence.extend('- **学生材料 · '+shared.escaped(e['kind'])+'**：“'+shared.escaped(e['quote'])+'”。' for e in row['evidence'])
            if not row['evidence']:evidence.append('- 学生材料未提供对应证据，不能据此判定不会。')
            details.append(section(row['name'],[{'type':'text','text':row['explanation']},{'type':'text','text':'\n'.join(evidence)}]))
        blocks.append(section(title,details))
    blocks.append(section('提升与验证行动',[{'type':'actions','items':[{'title':r['name']+' · '+r['improvement']['priority'],
        'text':r['improvement']['task']+'\n\n**交付成果**：'+r['improvement']['deliverable']+'\n\n**验收方式**：'+r['improvement']['check']} for r in rows]}]))
    if plan['qualifications']:
        blocks.append(section('门槛判断的原文依据',[{'type':'text','text':'\n'.join(
            '- **'+shared.escaped(q['name'])+'**：'+ '；'.join('JD：“'+shared.escaped(s['quote'])+'”' for s in q['sources'])+
            ('；学生材料：“'+shared.escaped(q['studentQuote'])+'”' if q.get('studentQuote') else '；个人条件待确认') for q in plan['qualifications'])}]))
    blocks.append(section('岗位原文与适用范围',[{'type':'sources','items':[{'label':records[item['id']]['positionName']+' · '+(records[item['id']].get('companyName') or '企业未说明'),
        'text':item['reason'],'url':records[item['id']]['url']} for item in plan['selectedJobs']]},
        {'type':'text','text':'岗位方向初评依据所列代表JD，不是全市场统计；具体岗位初评只适用于所列岗位。职责、硬条件或个人材料改变后需重新评估。建议先验证关键能力，再决定投递与学习优先级。'}]))

    return shared.redact_public({'title':plan['targetRole']+' · 岗位胜任力测评报告','theme':'minimal','blocks':blocks,
        'footer':'资料日期：'+source['retrievedAt'][:10]+' · 来源：优才知路招聘平台与学生提交材料。分享前请确认经历摘录适合公开。'},student_materials(source))


def load_source(workspace,data):
    path=(workspace/data['snapshot']).resolve()
    require(path.is_relative_to(workspace/'.job-matching') and path.suffix=='.json','候选来源路径无效')
    require(hashlib.sha256(path.read_bytes()).hexdigest()==data['sha256'],'候选来源已改变')
    source=json.loads(path.read_text())
    context=json.loads((workspace/'.job-request.json').read_text())
    state=json.loads((workspace/'.job-query-state.json').read_text())
    shared.validate_source(data,source,context,state)
    return source


def main():
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['preview','build']);parser.add_argument('input',type=Path);args=parser.parse_args()
    try:
        path=args.input.resolve();workspace=path.parent
        require(not workspace.is_relative_to(ROOT.parent),'不能在技能安装目录生成报告')
        plan=json.loads(path.read_text());source=load_source(workspace,plan)
        if args.operation=='preview':print(json.dumps({'status':'ok',**validate(plan,source)},ensure_ascii=False));return 0
        page=build_page(plan,source);model=workspace/'competency-page.json';model.write_text(json.dumps(page,ensure_ascii=False))
        renderer=ROOT.parent/'report-rendering/scripts';out=workspace/'output/public'/('competency-'+uuid.uuid4().hex[:12])
        subprocess.run([sys.executable,str(renderer/'render.py'),str(model),'--out',str(out)],check=True,cwd=workspace)
        subprocess.run([sys.executable,str(renderer/'register_delivery.py'),str(out),'--name','岗位胜任力测评报告'],check=True,cwd=workspace)
        print(json.dumps({'status':'ok','directory':str(out.relative_to(workspace))}));return 0
    except Exception as exc:
        print(json.dumps({'status':'error','message':str(exc)},ensure_ascii=False));return 1

if __name__=='__main__':sys.exit(main())
