"""Reproducible structural interpretations, separate from agent action proposals.

These rules compare saved aggregates. They do not infer skill difficulty,
graduate placement, causal returns or future growth from recruitment labels.
"""
POLICY='wechat-analytic-reasoning/1'


def opening(data):
    meta=data['meta'];filters=meta.get('filters',{});limited=filters.get('region',{}).get('level')=='city' or any(filters.get(key) for key in ('education','experience','jobType','roles','updatedAt')) or any(filters.get('title',{}).values())
    if limited:
        education=filters.get('education',[]);labels=meta.get('enum_labels',{}).get('education',{})
        degree='、'.join(labels.get(value,'限定类别') for value in education)
        scope=meta['region']+'、'+meta['industry']+('及'+degree+'学历条件' if degree else '的已声明岗位条件')
        return '本报告限于'+scope+'下的在招岗位样本，不用于描述未纳入筛选的其他地区或人群。合作与培养决策应联立招聘条件、薪酬分布与方向任务，先形成目标岗位核实清单，再通过企业反馈和学生产出验证培养试点，不能把筛选形成的地域范围解释成产业集聚。'
    if 'voc_pool' in data:
        return '本次岗位样本支持把人才培养决策分为目标岗位核实、入门薪酬校准与方向项目试点。岗位总量不能替代入门条件覆盖，整体薪酬不能替代目标岗位分布，方向排序还受分类覆盖与能力词口径约束。资源安排应先明确目标学生和岗位条件，再用企业反馈与可评估产出调整合作和培养路径。'
    return '本次报告以岗位条件、薪酬分布和方向任务作为相互补充的决策线索，不以单一规模或词频排名决定培养资源。应先保留筛选范围形成岗位核实清单，再通过企业反馈与学生产出验证培养试点；未取得的目标人群子样本不能由整体统计替代。'


def normalize(data,writing,section_ids,pairs):
    """Trusted fields are recomputed; the agent owns proposals and validation."""
    import copy
    result=copy.deepcopy(writing);result['reasoningPolicy']=POLICY
    for row in result['sections']:
        if row['key'] not in section_ids:raise ValueError('分析章节不支持：'+row['key'])
        row.update(section(data,row['key']),findingIds=section_ids[row['key']])
    executive=result['executive'];claims=executive.get('claims')
    if not isinstance(claims,list) or len(claims)!=3:raise ValueError('核心结构论证需要三条分结论')
    executive['opening']=opening(data)
    for index,row in enumerate(claims):row.update(core(data,pairs[index],index),findingIds=pairs[index])
    return result

BASE={
 'jobtype':('招聘标签与条件交集不能互相替代','招聘类型描述发布标签，学历与经验交集描述另一套筛选条件。两者的数量差异首先说明统计对象不同，不能相加，也不能据此认定企业怎样接收毕业生。对接名单应先保留两种标记，再逐岗核实实际接收对象，避免用某一种标签替代真实岗位要求。'),
 'education':('学历与经验门槛需要联合匹配','学历份额描述招聘条件的分布，不能测量知识偏好、任务难度或学生能力。同一学历类别还包含不同经验要求，单独按学历形成推荐名单，会把条件不同的岗位混在一起。适合采用学历与经验联立的岗位分层，再依据职责和企业确认结果决定具体培养任务。'),
 'experience':('经验标签应与学历组共同解读','经验上界桶、经验不限以及应届或在校标签的含义不同，不宜把标签直接换成学生应有的工作年限。学历组内部的经验分布用于识别招聘条件差异，不能证明实践能力差异。企业项目与实训应围绕经过核实的岗位任务和可评估产出设计，不按学历直接分配技能层次。'),
 'access':('先区分比例分母，再联立进入条件','总体份额回答某条件组合在岗位样本中有多常见，学历组内比例回答该组岗位还附加了哪些经验条件。前者适合安排调查样本，后者适合比较条件结构；二者均不代表学生通过率。推荐岗位时应联立全部条件，并单独核实应届接收、实际职责及条件能否调整。'),
 'tracks':('方向排序需同时呈现分类覆盖边界','已分类子集内部的份额与完整样本份额回答不同问题。若存在未分类记录，方向排序只覆盖已识别部分，不能把未分类当作独立产业方向，也不宜把子集份额外推到全行业。可在已核实方向先做小规模课程试点，同时复核未分类岗位，比较重新归类后优先级是否改变。'),
 'track_salary':('方向薪酬需与样本量和入口条件同看','薪酬较高、岗位较多以及满足入门条件的比例较高，并不是同一个方向选择标准。方向间中位数未控制岗位与经验结构，不能据此决定扩招，也不能将薪酬高低直接解释为技能难度。应先按具体岗位职责核实培养要求，再结合有效样本量、分位区间和候选入口安排试点。'),
 'city_tracks':('城市岗位计数与方向集中度应分开用','岗位计数适合定位调研工作量，城市内份额与全样本份额的比较适合识别方向结构。大城市拥有较多记录不自动意味着某方向更集中。方向线索可以指导抽取岗位样本，但企业实际工作地、岗位职责和合作能力仍需核查，不能从聚合图直接确定合作企业或龙头名单。'),
 'skills':('能力词频用于核实顺序，不直接分配课时','描述中的通用能力词与技术词可以共同出现，提及率不是互斥构成，也不能直接测量技能深度或学生能力缺口。高频词可用于确定优先核实的工作任务，课程学时和考核要求则应依据企业任务与学生产出测评。通用能力可嵌入项目评价，具体技术应落实到可检查的岗位任务。'),
 'track_skills':('方向内提及率用于分流，不能反推能力缺口','不同方向内部的能力提及率可以支持分别建立岗位任务调查样本，但不能把词频差异解释为能力深度差异。低提及不等于不需要，也不意味着应补更多课时。通用模块与方向项目可分别组织，是否增加内容应由职责核实和学生产出测评决定，并复核词义及描述完整性。'),
}


def section(data,key):
    if key=='education' and len({row[1] for row in data.get('edu_exp',[])})==1:
        return {'title':'限定经验样本中的学历结构不能外推','interpretation':'当前只观测到一个经验标签，学历分布应在这一经验条件下解释，不能外推为学历群体完整的经验结构。学历份额仍不测量任务难度或学生能力。对接时应保留原有条件，核实具体岗位职责与接收对象，再决定哪些学习任务适用于目标学生，不按学历名称直接划分技能层次。'}
    if key=='experience' and len({row[0] for row in data.get('edu_exp',[])})==1:
        return {'title':'当前学历样本的经验标签需独立核实','interpretation':'当前仅观测到一个学历类别，经验分布应在该学历样本内解释，不用于不同学历层次比较。经验上界桶、经验不限与应届在校标签也不能直接换成学生应有的实践深度。应保留筛选范围，逐岗核实经验要求对应的工作任务，再以项目产出评估是否满足实际条件。'}
    if key=='city_tracks' and len(data.get('city_profiles',[]))<2:
        return {'title':'单城方向份额只用于同城结构观察','interpretation':'当前仅有一个有效城市，方向计数与份额用于观察本范围内部结构，不形成跨城集中度排序，也不扩大地域。方向线索可用于抽取同城岗位样本，但企业实际工作地、职责与合作能力仍需逐项核实。不能把聚合方向份额当成企业排名或校企合作资格。'}
    if key in BASE:return dict(zip(('title','interpretation'),BASE[key]))
    if key=='geography':
        profiles=data.get('city_profiles',[]);pool=data.get('voc_pool')
        if len(profiles)<2:
            return {'title':'限定地域内仍需核实具体岗位条件','interpretation':'当前城市样本不足以形成跨城比较，因此不按城市排名安排培养资源，也不扩大地域范围。可以保留本范围内的岗位规模、薪酬和学历条件观察，但这些汇总不能替代具体岗位职责。校企对接应从符合目标条件的岗位样本出发，逐一核实工作地、接收对象与实践任务。'}
        text='城市薪酬和学历份额是并列比较，未控制方向与经验，不能解释为学历回报、任务难度或城市培养层次。'
        if pool is not None:
            text+='岗位总量与满足入门筛选的条件覆盖率回答不同问题，面向入门学生的调研资源不能只按城市总量分配。应先比较目标岗位条件，再抽取岗位形成企业核实清单；条件覆盖率不是录用概率。'
        else:text+='本次没有可比入门子样本，不以缺失值补作零覆盖率。对接资源应按本次明确的学历经验条件与具体岗位职责分层配置，再核实企业实际接收对象。'
        return {'title':'城市规模、薪酬与条件覆盖需要联合判断','interpretation':text}
    if key=='salary':
        all_salary=data.get('salary') or {};entry=(data.get('voc_pool') or {}).get('salary') or {}
        if entry.get('valid',0)>=30 and all_salary.get('median') is not None and entry.get('p75') is not None:
            if entry['p75']<all_salary['median']:
                opening='总体中位数超过入门池上四分位，直接套用为统一入门目标，会把期望放在该池分布较高的位置。'
                title='总体中位数超过入门池上四分位'
            else:
                opening='总体中位数没有超过入门池上四分位，但这并不意味着任一单点适用于所有入门岗位。'
                title='入门薪酬目标仍需按分布与岗位匹配'
            return {'title':title,'interpretation':opening+'应结合入门池中位数、分位区间和匹配岗位校准预期；上四分位是区间边界，不是薪酬封顶。组差未控制岗位与经验结构，不能解释为能力回报，也不能代替毕业生实际录用薪酬。'}
        return {'title':'薪酬分位区间比单点更适合校准预期','interpretation':'总体分位数用于观察岗位薪酬的分布范围，不能为特定学生或岗位承诺起薪。本次缺少足够的可比入门薪酬样本，不以总体中位数替代该人群分布。应按目标岗位职责与条件重新匹配薪酬参照，并把有效样本量和分位跨度同时列入就业沟通。'}
    if key=='vocational':
        pool=data.get('voc_pool') or {}
        if pool.get('count')==0:
            return {'title':'当前筛选与入门条件交集为空','interpretation':'当前样本与已声明入门条件的交集为零，这只说明本次筛选组合下没有对应记录，不能解释为整个地区没有入门需求。应保持用户的地域、产业与学历经验范围，说明候选池不适用于本次人群；后续如需研究其他对象，应另建独立样本而非直接放宽当前口径。'}
        return {'title':'广覆盖入口与小规模专项需要不同路径','interpretation':'候选规模较大的方向与池内薪酬较高的方向可能不同，培养路径需要同时考虑方向入口比例、有效样本量和薪酬定位。广覆盖课程试点与小规模专项项目承担不同目标，不宜只按最高中位数配置资源。候选条件满足仍不等于企业已经接收毕业生，岗位任务与学生基础必须再验证。'}
    if key=='lq':
        from joint_report_charts import specialization
        rows=(specialization(data) or {}).get('data',[])
        if len(rows)>=2 and rows[0][2]<rows[1][2]:
            opening='集中度指数排序与绝对岗位量排序不一致，指数更高的候选方向具有更小的样本基础。'
        else:opening='集中度与绝对岗位量需要分别判断，指数排序只能作为候选调研线索。'
        return {'title':'相对集中度还需通过绝对样本量筛选','interpretation':opening+'对小样本候选适合先深访核实，对样本较多且任务相近的方向再评估扩大调研。LQ不反映需求增长、因果区位优势或录用结果，不能直接转化为招生规模或人才迁移判断。'}
    raise ValueError('缺少可复现分析规则：'+key)


def core(data,ids,index):
    if index==0 and any(fid.startswith('vocational.city_coverage') for fid in ids):
        cities=sorted([row for row in data.get('city_profiles',[]) if row.get('valid',0)>=30 and row.get('median') is not None],key=lambda row:-row['count'])
        pool=data.get('voc_pool') or {};total=data.get('total',{}).get('positions',0)
        if data.get('meta',{}).get('filters',{}).get('region',{}).get('level')=='province' and cities and total and cities[0]['count'] and 'count' in pool:
            city=cities[0];entry=dict(pool.get('city',[])).get(city['name'],0)
            comparison=entry*total-pool['count']*city['count']
            if comparison<0:
                return {'title':city['name']+'入门条件覆盖低于全省基线',
                    'interpretation':'重点城市的薪酬、学历结构与入门条件覆盖给出了不同的定位线索。本地条件覆盖低于全省基线，意味着按原始岗位量等比例安排面向入门学生的核实工作，会包含更高比例的不满足当前筛选条件的记录。应先形成匹配条件的候选清单，再比较方向与职责，按候选量和核实成本安排对接；这不等于企业实际接收或录用概率更低，也不用于给城市划定培养层次。'}
            if comparison>0:
                return {'title':city['name']+'入门条件覆盖高于全省基线',
                    'interpretation':'重点城市的条件覆盖高于全省基线，为按本次筛选形成候选清单提供了更明确的筛选线索，但不能据此把薪酬、学历结构和实际录用混成同一种优势。可以先按候选量和方向组织企业核实，再用职责、接收对象和学生产出检验试点。筛选通过仍不等于企业接收，资源扩展须以实际核实结果为条件。'}
            return {'title':city['name']+'入门条件覆盖与省级基线相同',
                'interpretation':'重点城市的条件覆盖与省级基线相同，城市岗位总量仍影响候选绝对数量，但没有提供更高覆盖率的证据。宜按候选量组织调查，再按方向和职责拆分核实清单；薪酬与学历份额是另一层定位信息，不能替代目标人群条件。企业接收对象和学生能力仍需独立验证，不把城市标签作为培养层次依据。'}
        return {'title':'岗位规模与入门条件覆盖应分开排序','interpretation':'城市薪酬学历差异与本市入门条件覆盖描述不同结构。岗位量适合安排调查规模，条件覆盖更接近目标岗位筛选的覆盖范围，二者不能互相替代。对接优先级应先明确目标人群，再按岗位条件抽样核实，而非按城市标签直接划分学生层次。'}
    if index==1 and 'salary.entry_upper_bound' in ids:
        row=section(data,'salary');return {'title':row['title'],'interpretation':row['interpretation']}
    if index==2 and 'track_skills.conditional_contrast' in ids:
        return {'title':'方向试点与分类复核可以并行推进','interpretation':'方向规模需要同时报告全部样本与已分类子集的分母，方向内能力比例则用于比较各自岗位描述。两类证据支持先建立分方向任务样本，开展已核实课程试点，同时复核未分类岗位。课程资源不宜仅按总体词频分配，也不应等到分类完全覆盖后才开始验证。'}
    rows=[
      ('地域与条件线索需落实到具体岗位','地域规模用于识别本次范围内的岗位分布，招聘标签或学历经验条件用于观察另一层筛选结构。两类线索需保留各自分母，不能直接替代企业实际接收对象。合作调研应从符合当前条件的岗位出发，再核实工作地、职责与接收对象，不把地域汇总当作企业名单。'),
      ('薪酬定位需要与岗位门槛联合判断','薪酬分位数与岗位条件分别约束目标定位，方向摘要也不能代替同岗位、同经验条件下的比较。应将整体分布作为调查参照，再依据目标岗位职责与条件形成可比样本。缺少相应子样本时，不推算目标人群起薪，也不以薪酬高低直接确定培养层次。'),
      ('培养试点需要明确样本与任务边界','不同分析维度为培养试点提供相互补充的线索，统计份额不能替代岗位任务要求。可以先选择证据明确的岗位建立任务样本，设计小范围可评估项目，同时补充尚未核实的职责与能力信息。是否扩展试点应依据企业反馈和学生产出，而非单项频数排名。')]
    return dict(zip(('title','interpretation'),rows[index]))


def verify(data,analysis,section_ids=None,pairs=None):
    if analysis.get('reasoningPolicy')!=POLICY:raise ValueError('分析推理版本不符')
    for row in analysis['sections']:
        expected=section(data,row['key'])
        if any(row.get(key)!=value for key,value in expected.items()):raise ValueError('结构分析与受信规则不一致：'+row['key'])
        if section_ids is not None and row['findingIds']!=section_ids[row['key']]:raise ValueError('结构分析与受信事实选择不一致')
    claims=analysis.get('executive',{}).get('claims')
    if not isinstance(claims,list) or len(claims)!=3:raise ValueError('核心结构论证需要三条分结论')
    if analysis['executive'].get('opening')!=opening(data):raise ValueError('总体判断与当前筛选范围不一致')
    for index,row in enumerate(claims):
        expected=core(data,row['findingIds'],index)
        if any(row.get(key)!=value for key,value in expected.items()):raise ValueError('核心结构论证与受信规则不一致')
        if pairs is not None and row['findingIds']!=pairs[index]:raise ValueError('核心结构论证与受信事实选择不一致')
