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
    region=data['meta']['region'];industry=data['meta']['industry']
    return '报告围绕招聘集中在哪里、岗位需要什么条件、薪酬如何分化以及能力怎样组合展开，连接'+region+industry+'的岗位观察与人才决策。'


def normalize(data,writing,section_ids,pairs):
    import copy
    result=copy.deepcopy(writing);result['reasoningPolicy']=POLICY
    from editorial_prose import polish
    for row in result['sections']:
        for field in ('action','validation','decisionRule'):
            if field in row:row[field]=polish(row[field])
    from editorial_projects import public_insight_problems,examples
    repairs=[]
    for row in result['sections']:
        issues=public_insight_problems(data,row)
        if issues:
            row['action']=examples(data,row['key'])['action']
            if public_insight_problems(data,row):raise ValueError('程序短评未通过本章证据范围检查')
            repairs.append({'key':row['key'],'reasons':issues,'policy':'evidence-scoped-public-insight/1'})
    if repairs:result['editorialRepairs']=repairs
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
    cities=_cities(data);tracks=_tracks(data);pool=data.get('voc_pool') or {}
    city=cities[0]['name'] if cities else data['meta']['region']
    track=tracks[0]['name'] if tracks else '已识别方向'
    if key=='geography':
        if len(cities)<2:return {'title':'招聘格局：本地岗位如何分布','interpretation':'当前样本用于识别本地岗位的分布基础。地域规模只回答机会集中在哪里，岗位是否适合具体求职者，还要继续结合方向、学历经验和实际工作地点判断。'}
        a,b=cities[:2]
        return {'title':'招聘格局：'+a['name']+'与'+b['name'],'interpretation':'两地构成本次样本的主要招聘节点，但岗位数量、报价与学历要求衡量的是不同问题。城市总量适合定位机会密集区，实际投递和企业对接仍应落到同一方向、相近条件的岗位组。'}
    if key=='jobtype':return {'title':'岗位入口：招聘类型与申请条件','interpretation':'招聘类型反映发布时面向的人群标签，学历与经验才是进一步筛选岗位的条件。社会招聘中可能存在低经验岗位，校招标签也不能代替具体条件；观察就业入口需要将这两层信息一起保留。'}
    if key=='education':return {'title':'学历门槛：主要岗位落在哪些组','interpretation':'学历决定可申请范围，经验进一步划分履历阶段。主要学历组内部仍有不同经验要求，条件需要联立，才能识别面向初次就业与已有经历的岗位。'}
    if key=='experience':return {'title':'经验门槛：哪些岗位面向初次就业','interpretation':'经验不限与应届标签提供不同的入口信号，有明确年限的岗位则面向不同履历阶段。学历与经验共同用于筛选，具体项目要求还需落到职责说明。'}
    if key=='access':return {'title':'交叉分析：学历与经验的真实组合','interpretation':'分开看学历或经验容易高估可申请岗位数量，交叉表把两类条件放回同一岗位记录。总体占比衡量入口规模，组内比例衡量同一学历组还附加了怎样的经验门槛，两者可以互相补充。'}
    if key=='salary':
        salary=data.get('salary') or {};entry=pool.get('salary') or {}
        lower=entry.get('valid',0)>=30 and entry.get('p75') is not None and salary.get('median') is not None and entry['p75']<salary['median']
        return {'title':'薪酬结构：总体报价与入门区间','interpretation':('总体中位数已高于入门条件样本的上四分位，直接用总体报价作入门预期，会把参照放到入门分布较高的位置。' if lower else '总体与入门条件样本的薪酬反映不同岗位组合，统一的平均印象难以代表具体入口。')+'比较岗位报价时，应把中位数、中间区间与对应职责一起比较，报价差异不能直接解释为个人能力回报。'}
    if key=='tracks':return {'title':'岗位方向：'+track+'居已识别方向前列','interpretation':'标题规则把岗位划为互斥的工作方向，方向份额回答当前可识别岗位由哪些任务组成。大方向提供较广的岗位基础，小方向可能对应更专门的职责；方向排序应结合分类覆盖率理解。'}
    if key=='track_salary':
        rows=[row for row in data.get('salary_by_track',[]) if row.get('key')!='__other__' and row.get('valid',0)>=30 and row.get('median') is not None]
        high=max(rows,key=lambda row:row['median'])['name'] if rows else track
        return {'title':'量价比较：'+high+'的薪酬位置','interpretation':'岗位规模和薪酬定位不一定同向：前者影响机会覆盖，后者反映该方向样本的报价分布。高薪方向还可能包含不同学历与经验组合，需要与条件一起阅读，不能仅凭报价判断进入难度或扩大培养规模。'}
    if key=='city_tracks':return {'title':'城市与赛道：本地结构有何差别','interpretation':'城市总量定位机会密集区，方向份额揭示本地工作结构。比较共同的大方向与各自的局部特点，可以找到城市规模排名之外的岗位选择线索。'}
    if key=='lq':return {'title':'相对专长：哪些方向在本地更集中','interpretation':'相对集中度将城市内部份额与省级同方向份额比较，帮助发现地方专长。结构突出与岗位量充分是不同条件，需要一起判断调研和对接的优先顺序。'}
    if key=='skills':
        words=sorted(data.get('keywords',[]),key=lambda row:(-row['count'],row['name']));names='、'.join(row['name'] for row in words[:2]) or '高频能力词'
        return {'title':'能力画像：'+names+'的提及情况','interpretation':'技术词提示工作所用的工具，通用能力连接协作与交付。把高频词放回具体岗位职责中阅读，更容易理解企业怎样组合要求，而不是把能力看成孤立清单。'}
    if key=='track_skills':return {'title':'能力组合：共同底座与方向差别','interpretation':'方向内提及比例把能力词放回对应岗位组，用于识别共同基础与专属工具。准备工作能力时，可以保留共享环节，再按目标方向安排工具与任务练习。'}
    if key=='vocational':
        if pool.get('count')==0:return {'title':'入门观察：当前条件交集为空','interpretation':'既定筛选范围内没有与本报告入门条件重合的岗位记录，不能用其他地区或学历人群的数据补足。当前结论仅说明这一条件组合的样本结果，人才决策仍应围绕原定岗位对象展开。'}
        lead=_label([row for row in pool.get('track',[]) if row.get('key')!='__other__' and row.get('count',0)>0],'已识别方向')
        return {'title':'入门机会：'+lead+'的岗位基础','interpretation':'入门样本同时满足学历与经验条件，比单看校招或学历分布更接近条件匹配的岗位清单。不同方向的入口规模与报价可能分化，可据此选择实习与求职观察重点，再对照具体职责判断适用性。'}
    raise ValueError('缺少可复现分析规则：'+key)


def core(data,ids,index):
    cities=_cities(data);tracks=_tracks(data);pool=data.get('voc_pool') or {}
    if index==0 and len(cities)>1 and 'city' in pool and 'count' in pool:
        city=cities[0];total=data['total']['positions'];entry=dict(pool['city']).get(city['name'],0)
        contrast=entry*total-pool['count']*city['count']
        relation='低于' if contrast<0 else '高于' if contrast>0 else '持平于'
        return {'title':'岗位集中与进入条件需要一起看','interpretation':city['name']+'的入门条件覆盖'+relation+'全省基线。城市总量展示机会密度，条件覆盖展示其中可匹配的入口；城市选择与岗位匹配应分开判断，不能用招聘规模替代进入条件。'}
    if index==1:return section(data,'salary')
    if index==2 and len(tracks)>=2:
        a,b=tracks[:2];dominant=a['count']>=2*b['count'];close=a['count']<=1.25*b['count']
        title='已识别方向呈现明显的规模重心' if dominant else '主要已识别方向需要并行观察' if close else '方向规模存在分层，入口仍需细分'
        relation='的规模明显大于' if dominant else '的规模较为接近：' if close else '的规模高于'
        entry={r.get('key'):r['count'] for r in pool.get('track',[])}
        contrast=''
        if all(r['key'] in entry for r in (a,b)):
            high,low=sorted([a,b],key=lambda r:entry[r['key']]/r['count'],reverse=True)
            if entry[high['key']]*low['count']!=entry[low['key']]*high['count']:
                contrast=high['name']+'的入门条件覆盖高于'+low['name']+'，方向规模排序不能代替入口匹配。'
        description=(a['name']+'与'+b['name']+'的规模较为接近。') if close else a['name']+relation+b['name']+'。'
        return {'title':title,'interpretation':description+contrast+'岗位选择应继续对照入口条件与工具组合，人才准备据此区分共同基础和方向要求。'}
    return section(data,('geography','salary','track_skills')[index])


def verify(data,analysis,section_ids=None,pairs=None):
    if analysis.get('reasoningPolicy')!=POLICY:raise ValueError('分析推理版本不符')
    from editorial_projects import public_insight_problems
    for row in analysis['sections']:
        issues=public_insight_problems(data,row)
        if issues:raise ValueError('；'.join(issues))
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
