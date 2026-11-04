"""Short Pi writing tasks with durable, source-bound progress and local validation.

There is no second model client: Pi writes each small part through its normal
tools. This module computes evidence, validates parts and assembles the result.
"""
import json
import os
from pathlib import Path
import re
from datetime import datetime,timezone
from report_runtime import report_root
from bound_report import load_data
from report_analysis import evidence_pack,fingerprint,default_findings,_narrative,entity_labels,assemble_analysis
from analysis_quality import problems as semantic_problems
from analytical_reasoning import POLICY as REASONING_POLICY,section as section_reasoning,core as core_reasoning,opening as scope_opening

BASE=report_root(__file__)
HINTS={
 'geography':'按本地区不同城市的岗位入口安排课程覆盖和校企合作项目。',
 'jobtype':'区分招聘标签与申请条件，形成适用于目标学生的岗位路径。',
 'education':'把主要学历组的经验条件落实为项目模块，任务难度依据职责。',
 'experience':'围绕真实岗位经验条件，设计可展示的项目经历和成果表达。',
 'access':'用学历与经验交集界定服务对象，区分基础模块与方向实践。',
 'salary':'以入门样本区间开展就业沟通，结合方向与条件说明薪酬定位。',
 'tracks':'把本地已识别的主要方向转化为具体项目和工具产出。',
 'track_salary':'兼顾岗位量、薪酬定位和入口条件，不以高薪直接决定扩招。',
 'city_tracks':'按本地城市和方向组织合作项目，写清实际工作任务。',
 'lq':'结合方向相对集中度与绝对岗位量，安排城市合作项目的覆盖。',
 'skills':'将具体技术词与通用能力组织为项目任务和可展示成果。',
 'track_skills':'按方向内能力差别设置项目分支，不把词频解释为技能深度。',
 'vocational':'兼顾本地入口规模与专项定位，安排不同覆盖面的实践路径。',
}


def atomic(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(payload,ensure_ascii=False,indent=2),'utf-8');os.replace(temporary,path)


def context():
    data,binding=load_data(BASE/'report_data.json');pack=evidence_pack(data,binding)
    state_file=BASE/'output/analysis/writing_progress.json'
    state=json.loads(state_file.read_text('utf-8')) if state_file.exists() else {'schema':'wechat-writing-progress/1','evidenceHash':fingerprint(pack),'sections':{},'executive':None}
    if state.get('evidenceHash')!=fingerprint(pack):raise ValueError('数据证据已更新，不能混用上一次写作进度；请在新版本工作区继续')
    return data,binding,pack,state_file,state


def task(pack,state,data=None):
    keys=[key for key in pack['requiredSections'] if key not in state['sections']]
    facts={row['id']:row for row in pack['findings']}
    common={'schema':'wechat-writing-part/1','evidenceHash':fingerprint(pack)}
    local={}
    if data is not None:
        from editorial_prose import regional_profile
        local={'regionalProfile':regional_profile(data)}
        if (BASE/'report_data.json').exists():
            from regional_research import writing_context
            local['officialRegionalEvidence']=writing_context(data,BASE)
    if data is not None:common['reasoningPolicy']=REASONING_POLICY
    if keys:
        selected=keys[:3];templates=[];evidence=[]
        for key in selected:
            ids=default_findings(pack,key)
            templates.append({'key':key,'title':'','findingIds':ids,'interpretation':'','action':'','validation':'','decisionRule':''})
            if data is not None:templates[-1].update(section_reasoning(data,key))
            from editorial_projects import examples
            evidence.append({'safeExample':examples(data,key),'key':key,'question':HINTS.get(key,''),'facts':[facts[fid] for fid in ids]})
        return {'status':'writing_required',**local,'part':dict(common,task='sections:'+','.join(selected),sections=templates),
                'evidence':evidence,'rules':'结构结论、事实和分析由受信比较规则给定，不改title/findingIds/interpretation。只提交本批每章key、action、validation、decisionRule，各至少三十字，禁止阿拉伯数字。行动写具体课程、工具、工作任务和产出；validation写项目组织和学习成果评价，decisionRule写岗位条件不同怎样分流课程；不按学历或工资直接分配技能层次，不把上四分位当薪酬封顶，不把低词频当能力缺口，不将待核验、待审核、待验证或平台工作流程写入成品；不以企业核实清单代替课程内容，不写泛化到任何省份都能照搬的建议。每批必须使用regionalProfile中的本地城市、方向或工具信息，形成有区别的任务。提交后持续完成下一批。'}
    if not state.get('executive'):
        from executive_analysis import default_pairs
        pairs=default_pairs(pack)
        executive={'opening':'','claims':[{'title':'','findingIds':ids,'interpretation':'','implication':''} for ids in pairs],'closing':''}
        if data is not None:
            executive['opening']=scope_opening(data)
            for index,claim in enumerate(executive['claims']):claim.update(core_reasoning(data,claim['findingIds'],index))
        return {'status':'writing_required',**local,'part':dict(common,task='executive',executive=executive,limitations=(__import__('regional_reasoning').limitations(data) if data is not None else [])),
            'evidence':[[facts[fid] for fid in ids] for ids in pairs],
            'chapterConclusions':[{'key':key,'title':row['title'],'action':row['action']} for key,row in state['sections'].items()],
            'safeImplicationExamples':(__import__('editorial_projects').core_examples(data) if data is not None else []),
            'analysisQuestions':[
              '对本条已给不同维度事实作联合论证；若有城市入门条件覆盖，解释岗位规模排序与条件匹配排序的区别。未给的城市、候选池或企业指标不补零、不猜测；不能直接划分城市培养层次。',
              '对已给薪酬/岗位条件事实解释目标定位与分布差异。若有入门池上四分位，仅用作分布边界，结合入门中位数和匹配岗位，不能以上四分位替代统一起薪目标；不推断经验因果回报。',
              '对本条已给方向/技能或其他真实事实提出有条件的决策顺序。已分类部分可先试点，未分类同步复核；没有提供的维度不写结论，不把所有课程设计推迟到词表完美。'],
            'rules':'三条分结论的title/findingIds/interpretation已经由受信比较规则给定，不改写。只填opening总体判断、三个claims各自的implication、closing综合启示和保留程序给定的limitations。总体判断应突出主要决策矛盾，不能只是免责声明；三条启示分别聚焦城市匹配与合作优先级、薪酬区间与求职预期、方向工具与课程项目，各自回答本条问题；不得全部写成课程建设；摘要页由程序把事实、解释和启示融合成一段，不另写分析标签。综合启示写执行顺序和项目组织，避免反复要求核验数据。研究边界客观说明统计对象与适用范围，不出现待核验、待审核或待验证。禁止阿拉伯数字、统计显著性承诺和按学历/薪酬直接分配技能层次。'}
    return {'status':'analysis_ready','next':'build'}


def next_task():
    data,binding,pack,path,state=context();result=task(pack,state,data)
    from report_preflight import check
    result['preflight']=check(data,pack)
    result['scope']={'region':data['meta']['region'],'industry':data['meta']['industry'],'audience':data['meta'].get('audience'),'readAt':data['meta']['generated_at'],'total':data['total']}
    return result


def revise(run_id):
    """An explicit user revision reopens prose once while retaining genuine data."""
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',run_id):raise ValueError('修订标识无效')
    data,binding=load_data(BASE/'report_data.json');pack=evidence_pack(data,binding)
    state_file=BASE/'output/analysis/writing_progress.json'
    state=json.loads(state_file.read_text('utf-8')) if state_file.exists() else {}
    if state.get('revisionRunId')==run_id:return next_task()
    archive=BASE/'output/analysis/revisions'/run_id
    archive.mkdir(parents=True,exist_ok=True)
    for file in (state_file,BASE/'report_writing.json',BASE/'report_analysis.json'):
        if file.exists():atomic(archive/file.name,json.loads(file.read_text('utf-8')))
    state={'schema':'wechat-writing-progress/1','evidenceHash':fingerprint(pack),
           'sections':{},'executive':None,'revisionRunId':run_id}
    atomic(state_file,state)
    for file in (BASE/'report_writing.json',BASE/'report_analysis.json',BASE.parent/'delivery.json'):
        file.unlink(missing_ok=True)
    return next_task()


def accept_part(file):
    path=Path(file).resolve()
    if not path.is_relative_to(BASE):raise ValueError('写作片段必须位于当前报告工作区')
    if path.stat().st_size>1024*1024:raise ValueError('写作片段过大，请只提交当前短批次')
    part=json.loads(path.read_text('utf-8'))
    data,binding,pack,state_file,state=context();expected=task(pack,state,data)
    if expected['status']=='analysis_ready':return expected
    template=expected['part']
    if any(part.get(key)!=template[key] for key in ('schema','evidenceHash','task','reasoningPolicy')):raise ValueError('请保留当前任务标识与受信分析版本')
    facts={row['id']:row for row in pack['findings']};labels=entity_labels(data);issues=[]
    def narrative(value,field,minimum=20):
        try:
            checked=_narrative(value,field,minimum,labels);issues.extend(semantic_problems(checked,field));return checked
        except ValueError as exc:issues.append(str(exc));return ''
    if template['task'].startswith('sections:'):
        rows=part.get('sections',[])
        if not isinstance(rows,list) or [row.get('key') for row in rows]!=[row['key'] for row in template['sections']]:raise ValueError('请完成当前批次的全部章节，不增删key')
        seen={re.sub(r'\W','',row[field]) for row in state['sections'].values() for field in ('interpretation','action','validation')}
        for row in rows:
            key=row['key'];ids=row.get('findingIds',[]);allowed=[fact for fact in pack['findings'] if fact['section']==key]
            expected_row=next(item for item in template['sections'] if item['key']==key)
            if any(row.get(field)!=expected_row[field] for field in ('title','findingIds','interpretation')):issues.append(key+'结构结论与证据不能改写；只补充行动、验证与调整条件')
            if not isinstance(ids,list) or not min(2,len(allowed))<=len(ids)<=5 or len(set(ids))!=len(ids) or any(fid not in facts or facts[fid]['section']!=key for fid in ids):issues.append(key+'事实引用无效或不足')
            elif any(f['kind']=='comparison' for f in allowed) and not any(facts[fid]['kind']=='comparison' for fid in ids):issues.append(key+'须使用比较事实')
            from editorial_prose import polish
            from editorial_projects import alignment_problems
            for field in ('action','validation','decisionRule'):row[field]=polish(row[field])
            issues.extend(alignment_problems(data,row))
            title=narrative(row.get('title'),key+'.title',4)
            if len(title)>40:issues.append(key+'标题超过四十字')
            for field,minimum in [('interpretation',40),('action',30),('validation',30),('decisionRule',30)]:
                value=narrative(row.get(field),key+'.'+field,minimum)
                normalized=re.sub(r'\W','',value)
                if normalized and normalized in seen:issues.append(key+'.'+field+'复用了另一章节的句子')
                if field!='decisionRule':seen.add(normalized)
        if issues:return recover_or_raise(part,path,data,state_file,state,template,issues)
        state['sections'].update({row['key']:row for row in rows})
    else:
        executive=dict(part.get('executive',{}));executive['findingIds']=list(dict.fromkeys(fid for claim in executive.get('claims',[]) for fid in claim.get('findingIds',[])))
        if executive.get('opening')!=template['executive']['opening']:issues.append('总体判断由当前筛选范围与受信分析生成，不能改写')
        for index,claim in enumerate(executive.get('claims',[])):
            if index>=len(template['executive']['claims']) or any(claim.get(field)!=template['executive']['claims'][index][field] for field in ('title','findingIds','interpretation')):issues.append('核心结构论证不能改写；只补充总体判断、各条决策启示与综合启示')
        if len(executive.get('claims',[]))==3 and not re.search(r'薪酬|区间|求职|就业预期|报价',executive['claims'][1].get('implication','')):issues.append('薪酬结论的启示必须解释匹配岗位的薪酬区间与求职预期')
        from executive_analysis import validate
        validate(executive,facts,narrative)
        from regional_reasoning import limitations as scope_limitations
        limitations=scope_limitations(data);part['limitations']=limitations
        if not isinstance(limitations,list) or len(limitations)<2:issues.append('需至少两条具体研究边界')
        for text in limitations:narrative(text,'研究边界',20)
        if issues:return recover_or_raise(part,path,data,state_file,state,template,issues)
        state['executive']=executive;state['limitations']=limitations
    result=task(pack,state,data)
    if result['status']=='analysis_ready':
        writing={'schema':'wechat-analysis-writing/2','reasoningPolicy':REASONING_POLICY,'evidenceHash':fingerprint(pack),'executive':state['executive'],
                 'sections':[state['sections'][key] for key in pack['requiredSections']],'limitations':state['limitations']}
        analysis=assemble_analysis(data,binding,writing)
        atomic(BASE/'report_writing.json',writing);atomic(BASE/'report_analysis.json',analysis)
    state['updatedAt']=datetime.now(timezone.utc).isoformat();atomic(state_file,state)
    return result


def recover_or_raise(part,path,data,state_file,state,template,issues):
    from editorial_projects import examples,core_examples
    counters=state.setdefault('rejectedParts',{});key=template['task'];counters[key]=counters.get(key,0)+1
    atomic(state_file,state)
    protected_errors=any(term in issue for issue in issues for term in ('不能改写','事实引用无效','须使用比较事实','标题超过','总体判断由'))
    if counters[key] != 2 or protected_errors:
        unique=list(dict.fromkeys(issues))
        raise ValueError('请重新写以下字段，删除学历分配与无依据判断；可直接采用当前任务safeExample。'+ '；'.join(unique)[:4000])
    if key.startswith('sections:'):
        for row in part['sections']:row.update(examples(data,row['key']))
    else:
        for row,text in zip(part['executive']['claims'],core_examples(data)):row['implication']=text
        part['executive']['closing']='先以岗位条件建立适用清单，再以本地方向组织共用模块和专项实践。课程使用真实任务、操作记录与可复现成果评价学习结果，就业沟通采用对应岗位的薪酬区间，合作范围随项目资源和学生准备情况调整。'
    repaired=path.with_name(path.stem+'-editorial-recovery.json');atomic(repaired,part)
    state.setdefault('editorialRecoveries',[]).append({'task':key,'reason':list(dict.fromkeys(issues)),'policy':'data-selected-project-examples/1'})
    atomic(state_file,state)
    return accept_part(repaired)
