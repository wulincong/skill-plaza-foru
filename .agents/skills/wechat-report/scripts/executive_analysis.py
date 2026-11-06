"""Total–parts–total executive argument; facts remain independently bound."""
NUMBERS=['一','二','三','四']


def default_pairs(pack):
    facts={row['id']:row for row in pack['findings']}
    candidates=[['geography.joint_contrast','vocational.city_coverage_0'],
                ['salary.entry_upper_bound','vocational.salary_comparison'],
                ['tracks.classified_leaders','track_skills.conditional_contrast','tracks.coverage']]
    if not any(fid in facts for fid in candidates[1]):candidates[1]=['salary.quantiles','track_salary.qualified_extremes']
    pairs=[];used=set()
    priorities=[['geography','jobtype','education'],['salary','track_salary','education'],['tracks','track_skills','skills','experience']]
    for index,ids in enumerate(candidates):
        chosen=[fid for fid in ids if fid in facts]
        domains={facts[fid]['section'] for fid in chosen}
        while len(chosen)<2 or len(domains)<2:
            options=[row for row in pack['findings'] if row['kind']=='comparison' and row['section'] not in domains]
            if not options:options=[row for row in pack['findings'] if row['section'] not in domains]
            if not options:break
            ordered=sorted(options,key=lambda row:(priorities[index].index(row['section']) if row['section'] in priorities[index] else len(priorities[index]),row['section'] in used))
            fact=ordered[0]
            if len(chosen)>=3:chosen.pop();domains={facts[fid]['section'] for fid in chosen}
            chosen.append(fact['id']);domains.add(fact['section'])
        used.update(domains);pairs.append(chosen)
    return pairs


def validate(executive,facts,narrative):
    issues=[]
    claims=executive.get('claims')
    if not isinstance(claims,list) or len(claims)!=3:raise ValueError('核心发现需要三条有证据的分结论')
    narrative(executive.get('opening'),'总体判断',40)
    narrative(executive.get('closing'),'综合启示',40)
    all_ids=[]
    for i,claim in enumerate(claims):
        if not isinstance(claim,dict):raise ValueError('分结论必须为对象')
        narrative(claim.get('title'),f'分结论{i+1}标题',6)
        if isinstance(claim.get('title'),str) and len(claim['title'])>32:issues.append(f'分结论{i+1}标题超过三十二字')
        ids=claim.get('findingIds',[])
        if (not isinstance(ids,list) or not 2<=len(ids)<=3 or len(set(ids))!=len(ids) or any(fid not in facts for fid in ids)):
            issues.append(f'分结论{i+1}需要二至三项存在且不重复的事实');continue
        if len({facts[fid]['section'] for fid in ids})<2:raise ValueError('每条核心结论需联合至少两个分析维度')
        narrative(claim.get('interpretation'),f'分结论{i+1}分析',40)
        narrative(claim.get('implication'),f'分结论{i+1}决策启示',30)
        all_ids.extend(ids)
    if executive.get('findingIds')!=list(dict.fromkeys(all_ids)):
        issues.append('综合事实索引须与三条分结论一致；请使用--assemble自动生成')
    if issues:raise ValueError('；'.join(issues))


def payload(executive,facts):
    paragraphs=['总体判断：'+executive['opening']];references={}
    for i,claim in enumerate(executive['claims']):
        paragraphs.append('结论'+NUMBERS[i]+'｜'+claim['title'])
        for fid in claim['findingIds']:
            references[len(paragraphs)]=fid;paragraphs.append(facts[fid]['text'])
        paragraphs += ['分析：'+claim['interpretation'],'决策启示：'+claim['implication']]
    return paragraphs,{'title':'综合启示','text':executive['closing']},references
