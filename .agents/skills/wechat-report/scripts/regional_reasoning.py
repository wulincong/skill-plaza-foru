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
        if issues or __import__('re').search(r'还需|仍需|进一步|才能|继续对照|当前样本用于|地域规模只回答',row.get('action','')):
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
    def lead(field,fallback):
        rows=[r for r in data.get(field,[]) if r.get('count',0)>0]
        return max(rows,key=lambda r:r['count'])['name'] if rows else fallback
    if key=='geography':
        if len(cities)<2:return {'title':'招聘格局：'+city+'的岗位结构','interpretation':city+'构成本报告的地域观察范围，岗位结构呈现在本地开展招聘的企业与岗位分布。企业覆盖与岗位数量分别体现招聘主体的广度和需求记录的规模，两项指标共同构成本地招聘基础。'}
        a,b=cities[:2]
        return {'title':'招聘格局：'+a['name']+'与'+b['name'],'interpretation':a['name']+'的岗位规模居首，'+b['name']+'位于其后，形成主要招聘节点。头部城市的集聚使岗位机会在地域间呈现梯度；各城市的入门条件覆盖率则揭示相同招聘规模下的入口差别。'}
    if key=='jobtype':return {'title':'招聘入口：'+lead('jobtype','招聘类型')+'数量最多','interpretation':lead('jobtype','招聘类型')+'在发布类型中数量最多，反映了当前招聘信息的主要发布渠道。招聘类型与申请条件属于不同分类：社会招聘包括低经验岗位，校园招聘也有各自的学历门槛，二者共同构成多层次的就业入口。'}
    if key=='education':return {'title':'学历门槛：'+lead('edu','主要学历组')+'岗位居首','interpretation':lead('edu','主要学历组')+'是岗位数量最多的学历组，构成本地招聘的主要学历层次。学历与经验交叉分布进一步区分了同一学历下的履历阶段，说明学历结构与初次就业入口的规模并不完全重合。'}
    if key=='experience':return {'title':'经验要求：'+lead('exp','主要经验组')+'岗位居首','interpretation':lead('exp','主要经验组')+'是岗位数量最多的经验组，体现当前招聘结构的主要履历层次。应届、经验不限与明确年限的岗位分别构成不同入口，交叉分布展示了这些入口对应的学历结构。'}
    if key=='access':return {'title':'学历与经验：单项门槛与联合入口','interpretation':'学历与经验交叉分布呈现同一岗位同时设置的两类门槛。单项学历占比包含不同履历阶段，联合条件下的岗位规模更聚焦于具体申请人群，因而与单看学历或经验得到的机会范围有所不同。'}
    if key=='salary':
        salary=data.get('salary') or {};entry=pool.get('salary') or {}
        lower=entry.get('valid',0)>=30 and entry.get('p75') is not None and salary.get('median') is not None and entry['p75']<salary['median']
        return {'title':'薪酬分布：总体报价与入门区间','interpretation':('总体中位数高于入门样本的上四分位，表明总体报价作为入门参照时已处于入门分布的较高位置。' if lower else '总体报价与入门条件报价覆盖不同的岗位组合，中位数与中间区间呈现各自的典型位置和分散程度。')+'两组分布将产业总体薪酬水平与初次就业入口的报价范围区分开来。'}
    if key=='tracks':return {'title':'岗位结构：'+track+'规模居首','interpretation':track+'是已识别岗位方向中规模最大的类别，体现本次招聘结构的主要工作方向。头部方向与其后类别形成不同规模层次，分类覆盖率则说明这些已识别方向占全部招聘记录的范围。'}
    if key=='track_salary':
        rows=[r for r in data.get('salary_by_track',[]) if r.get('key')!='__other__' and r.get('valid',0)>=30 and r.get('median') is not None]
        if len(rows)<2:
            return {'title':'方向薪酬：岗位规模与报价分布','interpretation':'方向岗位量与有效报价分别呈现机会规模和薪酬位置，中位数描述典型报价，中间区间描述分散程度。两类指标放在相同方向下阅读，能够区分岗位覆盖较广的类别与报价位置不同的类别，而不把岗位量直接解释为薪酬高低。'}
        high=max(rows,key=lambda r:r['median'])['name'] if rows else track
        return {'title':'方向薪酬：'+high+'报价领先','interpretation':high+'在有效薪酬样本充足的方向中，中位数处于最高位置。岗位数量体现机会规模，报价中位数体现典型薪酬位置；两项指标形成的组合展示了不同方向的量价差异，而非单一的岗位排名。'}
    if key=='city_tracks':return {'title':'城市与岗位方向：集聚结构的差别','interpretation':'城市内部的方向份额呈现各地招聘结构，绝对岗位量呈现这些方向的机会规模。二者结合展示共同的主要方向与各自的局部重心，使城市比较从总量排名延伸到工作方向的构成。'}
    if key=='lq':return {'title':'地方专长：相对集中与绝对规模','interpretation':'相对集中度比较城市内部方向份额与全范围同方向份额，呈现地方招聘结构中的相对专长。指数突出与岗位量较大分别体现结构特点和机会基础，图中并列展示两者的差异。'}
    if key=='skills':
        names='、'.join(r['name'] for r in sorted(data.get('keywords',[]),key=lambda r:-r['count'])[:2]) or '高频能力词'
        return {'title':'能力画像：'+names+'提及较多','interpretation':names+'位于岗位描述能力词的前列，是本次能力画像的主要观察对象。技术工具与通用能力共同出现在招聘描述中，形成跨任务的能力组合；提及结构展示企业公开描述的内容构成。'}
    if key=='track_skills':return {'title':'方向能力：共享工具与提及差异','interpretation':'不同岗位方向的能力词提及比例呈现工具组合的差别，多个方向共有的能力词构成共享基础。方向内比例使用各自岗位组作为分母，使规模不同的方向能够在同一统计口径下比较描述内容。'}
    if key=='vocational':
        lead_name=_label([r for r in pool.get('track',[]) if r.get('key')!='__other__' and r.get('count',0)>0],'已识别方向')
        if pool.get('count')==0:return {'title':'入门条件：当前交集无岗位记录','interpretation':'本次筛选范围内，同时满足报告所定义学历与经验条件的岗位记录为空。这一结果对应当前条件交集，其他学历和经验组仍保留在总体结构中，清楚区分了产业招聘规模与本报告入门人群的岗位入口。'}
        return {'title':'入门结构：'+lead_name+'岗位最多','interpretation':lead_name+'在已识别的入门条件岗位中数量最多，是这一人群的主要岗位方向。联合学历与经验后的规模和薪酬分布，呈现更聚焦的机会结构，将产业整体需求与具体申请入口联系起来。'}
    raise ValueError('缺少可复现分析规则：'+key)


def core(data,ids,index):
    cities=_cities(data);tracks=_tracks(data);pool=data.get('voc_pool') or {}
    if index==0 and len(cities)>1 and 'city' in pool and 'count' in pool:
        city=cities[0];total=data['total']['positions'];entry=dict(pool['city']).get(city['name'],0)
        contrast=entry*total-pool['count']*city['count']
        relation='低于' if contrast<0 else '高于' if contrast>0 else '持平于'
        return {'title':city['name']+'招聘规模居首','interpretation':city['name']+'的入门条件覆盖率'+relation+'本次范围的整体水平。招聘量的集聚与入门覆盖存在各自的结构，体现机会密度与申请入口两个层面的地域差别。'}
    if index==0 and data.get('edu'):
        education=max(data['edu'],key=lambda r:r['count'])
        experience=max(data.get('exp',[]) or [{'name':'已列明的经验组','count':0}],key=lambda r:r['count'])
        return {'title':education['name']+'是主要学历组','interpretation':education['name']+'是岗位最多的学历组，'+experience['name']+'在经验条件中居首。这两项分布分别描绘学历层次与履历阶段；报告后文的条件交叉进一步呈现同一岗位上的联合门槛。'}
    if index==1:return section(data,'salary')
    if index==2 and len(tracks)>=2:
        a,b=tracks[:2];relation='明显高于' if a['count']>=2*b['count'] else '高于' if a['count']>b['count'] else '持平于'
        entry={r.get('key'):r['count'] for r in pool.get('track',[])};contrast=''
        if all(r['key'] in entry for r in (a,b)):
            high,low=sorted([a,b],key=lambda r:entry[r['key']]/r['count'],reverse=True)
            if entry[high['key']]*low['count']!=entry[low['key']]*high['count']:contrast=high['name']+'的入门条件覆盖率高于'+low['name']+'，体现两个方向不同的入口结构。'
        return {'title':a['name']+'与'+b['name']+'形成主要方向','interpretation':contrast+'头部方向合计份额呈现招聘任务的主要重心，方向内入门覆盖率则反映机会面向不同申请人群的差别。'}
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
