"""Local structural interpretations recomputed from the saved regional sample."""
POLICY='wechat-analytic-reasoning/2'


def _cities(data):
    from editorial_prose import ordered_cities
    return ordered_cities(data)


def _tracks(data):
    from editorial_prose import ordered_tracks
    return ordered_tracks(data)


def _label(rows,fallback):
    return max(rows,key=lambda row:row.get('count',0)).get('name',fallback) if rows else fallback


def opening(data):
    meta=data.get('meta',{});filters=meta.get('filters',{});region=meta.get('region','本地区')
    limited=filters.get('region',{}).get('level')=='city' or any(filters.get(key) for key in ('education','experience','jobType','roles','updatedAt')) or any(filters.get('title',{}).values())
    names='、'.join(row['name'] for row in _tracks(data)[:2])
    if limited:
        labels=meta.get('enum_labels',{}).get('education',{})
        degree='、'.join(labels.get(value,value) for value in filters.get('education',[]))
        scope='在'+region+'范围内，按'+(degree+'学历条件' if degree else '既定岗位条件')
        return '报告'+scope+'组织岗位对接与人才培养建议。分析重点是把目标岗位条件、薪酬定位和工作任务联立起来，形成面向该人群的课程与实践安排；结论适用于当前筛选范围。'
    if names:return '在已识别方向中，'+names+'提供了较多可分析岗位。本报告据此比较城市入口、薪酬定位与方向任务，为'+region+'院校安排分层课程、实践项目和校企合作顺序提供依据。'
    return '报告围绕'+region+'岗位的地域分布、学历经验条件与薪酬分布，区分广覆盖课程和面向特定岗位的项目路径，为院校组织课程、实习与校企合作提供依据。'


def normalize(data,writing,section_ids,pairs):
    import copy
    result=copy.deepcopy(writing);result['reasoningPolicy']=POLICY
    from editorial_prose import polish
    for row in result['sections']:
        for field in ('action','validation','decisionRule'):
            if field in row:row[field]=polish(row[field])
    for claim in result['executive'].get('claims',[]):
        if 'implication' in claim:claim['implication']=polish(claim['implication'])
    if 'closing' in result['executive']:result['executive']['closing']=polish(result['executive']['closing'])
    for row in result['sections']:
        if row['key'] not in section_ids:raise ValueError('分析章节不支持：'+row['key'])
        row.update(section(data,row['key']),findingIds=section_ids[row['key']])
    result['limitations']=limitations(data)
    executive=result['executive'];claims=executive.get('claims')
    if not isinstance(claims,list) or len(claims)!=3:raise ValueError('核心结构论证需要三条分结论')
    executive['opening']=opening(data)
    for index,row in enumerate(claims):row.update(core(data,pairs[index],index),findingIds=pairs[index])
    return result


def section(data,key):
    cities=_cities(data);tracks=_tracks(data);pool=data.get('voc_pool')
    city=cities[0]['name'] if cities else data.get('meta',{}).get('region','本地区')
    track=tracks[0]['name'] if tracks else '已识别方向'
    if key=='geography':
        if len(cities)<2:return {'title':'本地岗位应按工作条件和方向分层','interpretation':'本次样本用于观察当前地域内部的岗位分布。课程和企业项目宜按岗位条件与方向任务拆分，在同一地域内形成不同学习路径，并采用目标岗位的薪酬分布安排就业沟通。'}
        a,b=cities[:2]
        return {'title':a['name']+'、'+b['name']+'应先匹配岗位条件','interpretation':'两地的岗位数量、薪酬定位与学历结构呈现不同组合。院校宜先按学生适用条件建立岗位层，再在各城市内部选择方向项目，使对接规模与可匹配的岗位入口相衔接。'}
    if key=='jobtype':return {'title':_label(data.get('jobtype',[]),'现有招聘类型')+'标签与入门条件应分别观察','interpretation':'招聘类型描述岗位发布方式，学历与经验描述岗位申请条件。面向学生的岗位清单宜将两者并列保留，按条件交集识别培养对象，而不以校招标签数量单独估计可对接岗位。'}
    if key in ('education','experience','access'):
        groups={}
        for edu,exp,count in data.get('edu_exp',[]):groups[edu]=groups.get(edu,0)+count
        top=sorted(groups,key=lambda label:(-groups[label],label));names='、'.join(top[:2]) or '主要学历组'
        if key=='education':return {'title':names+'岗位还需联立经验要求','interpretation':names+'是当前样本中的主要学历观察组。组内经验条件决定了岗位清单仍需进一步分层，课程安排宜兼顾面向初次就业的基础项目和面向经验岗位的进阶任务，项目难度依据具体职责确定。'}
        if key=='experience':return {'title':_label(data.get('exp',[]),'主要经验类别')+'岗位应放回学历组内比较','interpretation':'经验标签在不同学历组中的分布，为安排实践项目提供了分层线索。适合把目标岗位任务拆成连续的项目产出，以工作样例、过程记录和成果说明连接在校学习与岗位要求。'}
        return {'title':'学历与经验交集界定课程服务对象','interpretation':'总体组合份额说明岗位入口的规模，学历组内比例说明该组附加的经验条件。两类信息共同支持按学生适用条件组织岗位清单，并为不同入口配置对应的项目经历和学习成果。'}
    if key=='salary':
        salary=data.get('salary') or {};entry=(pool or {}).get('salary') or {}
        if entry.get('valid',0)>=30 and salary.get('median') is not None and entry.get('p75') is not None:
            lower=entry['p75']<salary['median']
            return {'title':'入门就业预期应采用匹配岗位的薪酬区间' if lower else '入门薪酬目标仍需按分布与岗位匹配','interpretation':('把总体中位数统一用于入门就业沟通，会使参照落在入门岗位分布较高的位置。' if lower else '总体与入门样本的薪酬分布存在交叠，单点薪酬仍不足以覆盖不同岗位。')+'宜以入门样本的中位数及四分位区间组织就业沟通，再按具体方向和岗位条件说明差别。'}
        return {'title':'薪酬沟通宜采用区间与对应岗位','interpretation':'有效薪酬样本呈现岗位报价分布，而不同岗位的职责与条件各有差异。就业指导宜同时展示中位数和中间区间，并将薪酬参照对应到目标岗位，避免用统一报价替代分层匹配。'}
    if key=='tracks':return {'title':track+'为方向课程提供本地样本','interpretation':'方向计数呈现规则能够识别的岗位结构。宜从岗位量较大的方向建立课程项目组合，用岗位描述中的工具、场景与交付物组织学习任务，同时保留分类覆盖率，限定方向排序的适用范围。'}
    if key=='track_salary':
        rows=[row for row in data.get('salary_by_track',[]) if row.get('key')!='__other__' and row.get('valid',0)>=30 and row.get('median') is not None]
        high=max(rows,key=lambda row:row['median'])['name'] if rows else track
        return {'title':high+'薪酬定位需与方向规模同看','interpretation':'岗位量决定项目覆盖的广度，薪酬分布提供另一层就业定位。院校宜把广覆盖方向与面向明确职责的专项课程组合起来，并为专项项目列明入门条件和学习成果，形成不同层次的实践路径。'}
    if key=='city_tracks':return {'title':city+'的方向结构支持分城市组织项目','interpretation':'城市内方向份额呈现本地岗位结构，绝对岗位量则影响项目对接的规模。校企合作可据此按城市组织方向任务包，再把相近的工艺、工具和交付要求组成可复用的课程项目。'}
    if key=='lq':return {'title':'相对集中程度与岗位量共同定位合作方向','interpretation':'相对集中度识别某方向在城市内部是否更集中，绝对数量衡量对应样本基础。适合将方向集中且岗位量充分的单元作为合作项目候选，把小样本单元保留为专项场景，不把结构指数解释为需求增长。'}
    if key=='skills':
        words=sorted(data.get('keywords',[]),key=lambda row:(-row['count'],row['name']));names='、'.join(row['name'] for row in words[:2]) or '高频能力词'
        return {'title':names+'构成本次能力观察重点','interpretation':'高频能力词提供了组织任务与成果表达的线索。通用能力可纳入项目协作和成果汇报，技术词对应具体工具与操作产出；课程内容按岗位任务组合，而不把词频直接换算为课时比例。'}
    if key=='track_skills':return {'title':'方向内能力差异支持项目分流','interpretation':'同一能力词在不同方向中的提及比例，为区分项目任务提供了依据。共享的工作流程适合组织为通用模块，方向专属工具与交付物适合设置为分流项目，使学习产出与目标岗位的要求相对应。'}
    if key=='vocational':
        if pool is not None and pool.get('count')==0:return {'title':'当前筛选范围未出现对应入门岗位','interpretation':'本次条件交集为空，说明当前岗位范围与入门条件没有重合。报告据此保留既定筛选对象，课程与就业安排应面向当前人群已有的岗位条件，不把其他地区或其他学历人群的统计代入。'}
        lead=_label([row for row in (pool or {}).get('track',[]) if row.get('key')!='__other__' and row.get('count',0)>0],'当前已识别方向')
        return {'title':lead+'提供本地入门项目候选','interpretation':'入口岗位较多的方向适合组织覆盖面较广的基础项目，入口较少但职责明确的方向适合小规模专项训练。课程安排宜同时考虑条件覆盖、岗位量与薪酬区间，形成分层的实践和就业路径。'}
    raise ValueError('缺少可复现分析规则：'+key)


def core(data,ids,index):
    if index==0 and any(fid.startswith('vocational.city_coverage') for fid in ids):
        cities=_cities(data);pool=data.get('voc_pool') or {};total=data.get('total',{}).get('positions',0)
        if data.get('meta',{}).get('filters',{}).get('region',{}).get('level')=='province' and cities and total and 'count' in pool:
            city=cities[0];entry=dict(pool.get('city',[])).get(city['name'],0);contrast=entry*total-pool['count']*city['count']
            relation='低于' if contrast<0 else '高于' if contrast>0 else '与省级基线相同'
            title=city['name']+'入门条件覆盖'+(relation+'全省基线' if contrast else relation)
            text=('岗位集中与入门条件覆盖并不等价，按城市总量分配对接资源会扩大不匹配的岗位清单。' if contrast<0 else '岗位规模和入门条件共同支持在该城市组织对接项目，但仍需按方向安排适用的学习任务。')
            return {'title':title,'interpretation':text+'宜按匹配条件后的候选量确定项目覆盖，再分配城市对接与课程资源。'}
        return {'title':'地域规模与岗位条件共同界定对接对象','interpretation':'城市分布与岗位条件描述不同层面的结构。对接安排宜以当前人群的条件交集为基础，再按工作任务划分城市项目，使课程覆盖范围与本地可观察的岗位入口相衔接。'}
    if index==1 and 'salary.entry_upper_bound' in ids:return section(data,'salary')
    if index==2 and 'tracks.classified_leaders' in ids:
        rows=_tracks(data);name=rows[0]['name'] if rows else '主要方向'
        if len(rows)>=2:
            second=rows[1]['name'];dominant=rows[0]['count']>=2*rows[1]['count'];close=rows[0]['count']<=1.25*rows[1]['count']
            title=(name+'宜承担已识别方向的广覆盖项目' if dominant else '主要已识别方向宜并行配置课程项目' if close else '已识别方向宜按规模与条件配置项目')
            text=(name+'的样本规模集中度较高，可先组织覆盖面较广的共用任务；'+second+'保留专项项目。' if dominant else name+'与'+second+'的样本规模较为接近，单设一个方向会遗漏另一类可观察任务，宜分别保留方向任务，并结合服务人群安排先后。' if close else name+'的样本量高于'+second+'，两类方向宜分别保留与岗位规模相衔接的项目路径，再按服务人群和适用条件分配课程资源。')
            entry={row.get('key'):row['count'] for row in (data.get('voc_pool') or {}).get('track',[])}
            if all(row.get('key') in entry for row in rows[:2]):
                ranked=sorted(rows[:2],key=lambda row:entry[row['key']]/row['count'],reverse=True)
                if entry[ranked[0]['key']]*ranked[1]['count'] != entry[ranked[1]['key']]*ranked[0]['count']:
                    if close:title='规模接近的方向应按职教入门条件分流'
                    text+=ranked[0]['name']+'的入门条件覆盖高于'+ranked[1]['name']+'，面向职教入门人群的课程宜优先使用前者的适用岗位样例，后者保留面向明确条件的专项路径。'
            return {'title':title,'interpretation':text+'课程容量结合匹配岗位和实际项目资源确定，共享流程与专项工具分别组织。'}
        return {'title':name+'提供已识别方向的课程样例','interpretation':'当前可识别方向为课程任务选择提供观察基础。宜从职责明确的样例组织工具练习、过程记录与成果解释，项目规模结合适用条件和教学资源确定。'}
    return section(data,('geography','salary','track_skills')[index])


def verify(data,analysis,section_ids=None,pairs=None):
    if analysis.get('reasoningPolicy')!=POLICY:raise ValueError('分析推理版本不符')
    for row in analysis['sections']:
        expected=section(data,row['key'])
        if any(row.get(key)!=value for key,value in expected.items()):raise ValueError('结构分析与本地数据规则不一致：'+row['key'])
        if section_ids is not None and row['findingIds']!=section_ids[row['key']]:raise ValueError('结构分析与事实选择不一致')
    claims=analysis.get('executive',{}).get('claims')
    if not isinstance(claims,list) or len(claims)!=3:raise ValueError('核心结构论证需要三条分结论')
    if analysis['executive'].get('opening')!=opening(data):raise ValueError('摘要与当前地域范围不一致')
    for index,row in enumerate(claims):
        expected=core(data,row['findingIds'],index)
        if any(row.get(key)!=value for key,value in expected.items()):raise ValueError('核心结构论证与本地数据规则不一致')
        if pairs is not None and row['findingIds']!=pairs[index]:raise ValueError('核心结构论证与事实选择不一致')


def limitations(data):
    return ['本报告按企业关联地区及既定岗位条件筛选平台在招记录；企业关联地址用于地域分组，不直接等同于岗位实际工作地点。',
      '统计反映平台可观察的岗位发布结构，企业数与岗位记录数分别计数；不能据此推算全地区就业总量、人才缺口或实际录用概率。',
      '薪酬为招聘报价的有效样本分布，能力词为岗位描述中的提及情况；方向按统一规则识别，未分类岗位保留在总体分母中。']
