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

BASE=report_root(__file__)
HINTS={
 'geography':'比较城市薪酬/学历并列结构与本市岗位满足入门筛选条件的比例，说明为什么单凭岗位规模会错排对接优先级。不能由城市薪酬/学历推断任务复杂度、知识基础或培养层次；不能按城市直接分配本科生与专科生。应提出按岗位条件分层核实的企业名单。',
 'jobtype':'比较招聘类型标签与学历经验交集定义。说明为何社招占比不能直接换算为毕业生可投率，给出企业确认实际接收对象的筛选任务。',
 'education':'用主要学历组的经验条件分布说明学历门槛与经验门槛需要联合筛选，不能从学历占比推断企业知识偏好、任务复杂度、实践能力或学历价值。指出按学历单独选岗位的不足，形成学历×经验分层的核实样本表。',
 'experience':'识别经验上界桶、经验不限和应届/在校标签的不同含义。说明如何按学历组比较经验条件，以及企业项目或实训应补哪类工作证据。',
 'access':'总体份额用于安排调查样本，学历组内条件比例用于比较招聘条件，二者都不代表求职者实际进入机会、通过率或录用概率。给出按学历与经验双条件选岗位、再核实应届接收条件的工作流程。',
 'salary':'比较入门池上四分位数和总体中位数，判断统一套用总体中位数是否适合入门目标；再用总体分位跨度说明需要按目标岗位定区间。差异不是经验回报，不据此承诺起薪；避免推动行业薪酬标准等超出当前数据的宏观建议。',
 'tracks':'比较已分类方向在全部样本与已分类子集中的份额，结合未分类率分析排序的适用范围。已分类方向可以先做小范围试点，同时复核未分类岗位；不能因为未分类就暂停一切课程设计，或把未分类当作独立产业方向。',
 'track_salary':'同时看分位区间、有效量和候选入口，高中位数不能直接转化为扩招建议。给出同岗位/经验条件复核后再制定培养目标的决策步骤。',
 'city_tracks':'区分城市总体规模、方向频数和城市内份额。大城市的大计数不等于方向更集中；校企合作对象仍需核查企业与实际工作地，不能从聚合图识别龙头企业。',
 'lq':'结合相对集中度和绝对样本量提出候选调研方向。LQ不表示增长、区位因果优势或人才迁移；说明小样本和城市基数如何改变名单优先级。',
 'skills':'区分通用能力词和具体技术词、提及与能力深度。词表可能重叠，未提及不等于不需要；用工作任务和可评估产出来确定课程，而非只追逐词频。',
 'track_skills':'比较方向内部的能力提及率及分母，解释为何通用模块和方向项目要分别设计。核查缺失描述和词义，若跨方向差别由词表造成则调整课程映射。',
 'vocational':'比较入门候选规模较大的方向与池内薪酬较高的方向，同时看各自条件覆盖率和有效样本量。分析广覆盖路径与小规模专项路径的取舍；不能只因高薪选择扩招或因低薪转向其他方向。筛选满足不是已接收毕业生。',
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


def task(pack,state):
    keys=[key for key in pack['requiredSections'] if key not in state['sections']]
    facts={row['id']:row for row in pack['findings']}
    common={'schema':'wechat-writing-part/1','evidenceHash':fingerprint(pack)}
    if keys:
        selected=keys[:3];templates=[];evidence=[]
        for key in selected:
            ids=default_findings(pack,key)
            templates.append({'key':key,'title':'','findingIds':ids,'interpretation':'','action':'','validation':'','decisionRule':''})
            evidence.append({'key':key,'question':HINTS.get(key,''),'facts':[facts[fid] for fid in ids]})
        return {'status':'writing_required','part':dict(common,task='sections:'+','.join(selected),sections=templates),
                'evidence':evidence,'rules':'只写这一小批；title≤40字，interpretation≥40字，action/validation/decisionRule各≥30字；数字仅在findingIds中引用，禁止花括号占位、统计显著性、人才短缺和未经证实的产业原因。解释写决策关系，行动写对象/任务/产出，调整条件写何时改变建议。保存report_part.json后运行accept，收到下一批后继续直到analysis_ready。'}
    if not state.get('executive'):
        candidates=[['geography.joint_contrast','vocational.city_coverage_0'],['salary.entry_upper_bound','vocational.salary_comparison'],['tracks.classified_leaders','track_skills.conditional_contrast','tracks.coverage']]
        pairs=[]
        for ids in candidates:
            chosen=[fid for fid in ids if fid in facts]
            domains={facts[fid]['section'] for fid in chosen}
            if len(chosen)<2:chosen += [row['id'] for row in pack['findings'] if row['kind']=='comparison' and row['section'] not in domains][:2-len(chosen)]
            pairs.append(chosen)
        executive={'opening':'','claims':[{'title':'','findingIds':ids,'interpretation':'','implication':''} for ids in pairs],'closing':''}
        return {'status':'writing_required','part':dict(common,task='executive',executive=executive,limitations=[]),
            'evidence':[[facts[fid] for fid in ids] for ids in pairs],
            'chapterConclusions':[{'key':key,'title':row['title'],'action':row['action']} for key,row in state['sections'].items()],
            'analysisQuestions':['岗位规模、薪酬与学历并列比较，加上市内入门条件覆盖率，说明为什么城市大不等于入门机会密度高；建议按具体岗位核实，不直接划分城市培养层次。',
              '比较入门池上四分位与总体中位的位置，说明总体中位数能否直接作为入门薪酬目标；不把差异解释成能力、经验或学历的因果回报。',
              '结合已分类方向规模、未分类覆盖边界与方向内技能比例，说明哪些模块可以先试点、哪些需补充复核；不把所有课程设计推迟到词表完美。'],
            'rules':'核心发现必须总分总：总体判断≥40字，三条分结论各联合不同维度的二至三项事实；分结论标题≤32字、分析≥40字、决策启示≥30字，综合启示≥40字，limitations至少两条具体边界。系统自动展开findingIds事实，文案内不得写数字、事实ID或花括号。标题要写证据支持的结构结论，避免决定、保障、有效性等未经结果验证的承诺。不要把岗位量排名写成城市培养层次划分。保存report_part.json后accept，完成即build。'}
    return {'status':'analysis_ready','next':'build'}


def next_task():
    data,binding,pack,path,state=context();result=task(pack,state)
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
    data,binding,pack,state_file,state=context();expected=task(pack,state)
    if expected['status']=='analysis_ready':return expected
    template=expected['part']
    if any(part.get(key)!=template[key] for key in ('schema','evidenceHash','task')):raise ValueError('请保留当前任务的schema、evidenceHash与task')
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
            if not isinstance(ids,list) or not min(2,len(allowed))<=len(ids)<=5 or len(set(ids))!=len(ids) or any(fid not in facts or facts[fid]['section']!=key for fid in ids):issues.append(key+'事实引用无效或不足')
            elif any(f['kind']=='comparison' for f in allowed) and not any(facts[fid]['kind']=='comparison' for fid in ids):issues.append(key+'须使用比较事实')
            title=narrative(row.get('title'),key+'.title',4)
            if len(title)>40:issues.append(key+'标题超过四十字')
            for field,minimum in [('interpretation',40),('action',30),('validation',30),('decisionRule',30)]:
                value=narrative(row.get(field),key+'.'+field,minimum)
                normalized=re.sub(r'\W','',value)
                if normalized and normalized in seen:issues.append(key+'.'+field+'复用了另一章节的句子')
                if field!='decisionRule':seen.add(normalized)
        if issues:raise ValueError('请一次性修正本批次：\n- '+'\n- '.join(issues))
        state['sections'].update({row['key']:row for row in rows})
    else:
        executive=dict(part.get('executive',{}));executive['findingIds']=list(dict.fromkeys(fid for claim in executive.get('claims',[]) for fid in claim.get('findingIds',[])))
        from executive_analysis import validate
        validate(executive,facts,narrative)
        limitations=part.get('limitations',[])
        if not isinstance(limitations,list) or len(limitations)<2:issues.append('需至少两条具体研究边界')
        for text in limitations:narrative(text,'研究边界',20)
        if issues:raise ValueError('请一次性修正核心发现：\n- '+'\n- '.join(issues))
        state['executive']=executive;state['limitations']=limitations
    result=task(pack,state)
    if result['status']=='analysis_ready':
        writing={'schema':'wechat-analysis-writing/2','evidenceHash':fingerprint(pack),'executive':state['executive'],
                 'sections':[state['sections'][key] for key in pack['requiredSections']],'limitations':state['limitations']}
        analysis=assemble_analysis(data,binding,writing)
        atomic(BASE/'report_writing.json',writing);atomic(BASE/'report_analysis.json',analysis)
    state['updatedAt']=datetime.now(timezone.utc).isoformat();atomic(state_file,state)
    return result
