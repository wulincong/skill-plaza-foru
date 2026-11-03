"""Comparisons that support decisions across geography, entry access and skills."""


def derive(data):
    if 'city_profiles' not in data:return []
    from report_analysis import number,pct
    out=[]
    def add(key,section,text,paths,**details):
        out.append(dict(id=key,section=section,text=text,kind='comparison',paths=paths,**details))
    cities=sorted([row for row in data['city_profiles'] if row['valid']>=30 and row.get('median') is not None],key=lambda row:-row['count'])
    for i,row in enumerate(cities[:3]):
        add('geography.joint_city_'+str(i),'geography',
            f"{row['name']}有 {number(row['count'])} 条岗位，本科要求 {number(row['bachelorCount'])} 条，占本市 {row['bachelorShare']}%；有效薪酬 {number(row['valid'])} 条，中位数 {number(row['median'])} K/月。",
            ['/city_profiles'])
    if len(cities)>=2:
        a,b=cities[:2]
        add('geography.joint_contrast','geography',
            f"{a['name']}与{b['name']}的薪酬中位数分别为 {number(a['median'])}、{number(b['median'])} K/月，本科要求比例分别为 {a['bachelorShare']}%、{b['bachelorShare']}%；薪酬差和学历份额差是城市样本的并列比较，未控制方向与经验。",
            ['/city_profiles'])
    tracks=[row for row in data.get('salary_by_track',[]) if row.get('key')!='__other__' and row['valid']>=30 and row.get('median') is not None]
    if len(tracks)>=2:
        highest=max(tracks,key=lambda row:row['median']);lowest=min(tracks,key=lambda row:row['median'])
        add('track_salary.qualified_extremes','track_salary',
            f"在有效薪酬样本不少于三十条的已分类方向中，{highest['name']}中位数 {number(highest['median'])} K/月（有效 {number(highest['valid'])} 条），{lowest['name']}为 {number(lowest['median'])} K/月（有效 {number(lowest['valid'])} 条），两者相差 {number(highest['median']-lowest['median'])} K/月。",
            ['/salary_by_track'])
    all_tracks={row['name']:row['count'] for row in data.get('subtrack',[])}
    pool=data.get('voc_pool') or {};entry_salaries={row['name']:row for row in pool.get('salary_by_track',[])}
    pool_cities={row[0]:row[1] for row in pool.get('city',[])}
    city_join_safe=data.get('meta',{}).get('filters',{}).get('region',{}).get('level')!='national'
    for i,row in enumerate(cities[:2] if 'count' in pool and city_join_safe else []):
        entry_n=pool_cities.get(row['name'],0)
        text=(f"{row['name']}全部 {number(row['count'])} 条岗位中，有 {number(entry_n)} 条满足已声明的入门池条件，条件覆盖率为 {pct(entry_n,row['count'])}%；"
              f"{'全省' if data.get('meta',{}).get('filters',{}).get('region',{}).get('level')=='province' else '当前范围'}同口径为 {pct(pool.get('count',0),data['total']['positions'])}%。条件覆盖率不代表应届接收率或录用概率。")
        paths=['/city_profiles','/voc_pool/city','/voc_pool/count','/total/positions']
        add('geography.entry_coverage_'+str(i),'geography',text,paths)
        add('vocational.city_coverage_'+str(i),'vocational',text,paths)
    combined={}
    for edu,exp,count in data.get('edu_exp',[]):
        combined.setdefault(edu,{})[exp]=combined.setdefault(edu,{}).get(exp,0)+count
    major=sorted(combined,key=lambda edu:-sum(combined[edu].values()))[:2]
    if len(major)==2:
        a,b=major;an,bn=sum(combined[a].values()),sum(combined[b].values())
        labels=set(combined[a])|set(combined[b])
        exp=max(labels,key=lambda label:(abs(combined[a].get(label,0)/an-combined[b].get(label,0)/bn),label))
        text=(f"{a}组共 {number(an)} 条、{b}组共 {number(bn)} 条；经验标签“{exp}”在两组内部的比例分别为 "
              f"{pct(combined[a].get(exp,0),an)}%、{pct(combined[b].get(exp,0),bn)}%，相差 {round((combined[a].get(exp,0)/an-combined[b].get(exp,0)/bn)*100,2)} 个百分点。"
              '比较的是招聘条件结构，不是求职者经历、实践深度或能力回报。')
        add('education.experience_contrast','education',text,['/edu_exp'])
        add('experience.education_contrast','experience',text,['/edu_exp'])
    classified=[row for row in data.get('subtrack',[]) if row.get('key')!='__other__']
    classified_n=sum(row['count'] for row in classified)
    if classified_n and len(classified)>=2:
        top=sorted(classified,key=lambda row:-row['count'])[:2]
        add('tracks.classified_leaders','tracks',
            '在已分类记录中，'+'；'.join(f"{row['name']}为 {number(row['count'])} 条，占全部岗位 {pct(row['count'],data['total']['positions'])}%，占已分类记录 {pct(row['count'],classified_n)}%" for row in top)+'。排除未分类后得到的份额不能当作全行业份额。',
            ['/subtrack','/total/positions'])
    overall=data.get('salary') or {};entry=pool.get('salary') or {}
    if entry.get('valid',0)>=30 and overall.get('median') is not None and entry.get('p75') is not None:
        add('salary.entry_upper_bound','salary',
            f"入门池有效薪酬 {number(entry['valid'])} 条，上四分位数为 {number(entry['p75'])} K/月；全部有效岗位中位数为 {number(overall['median'])} K/月，两者相差 {number(entry['p75']-overall['median'])} K/月。分位数是岗位样本分布，不能替代毕业生录用薪酬。",
            ['/salary','/voc_pool/salary'])
    entry_tracks=[row for row in pool.get('track',[]) if row.get('key')!='__other__' and all_tracks.get(row['name']) and entry_salaries.get(row['name'],{}).get('valid',0)>=30]
    if len(entry_tracks)>=2:
        broad=max(entry_tracks,key=lambda row:row['count'])
        high=max(entry_tracks,key=lambda row:(entry_salaries[row['name']].get('median') or 0,row['count']))
        if broad['name']!=high['name']:
            text='；'.join(f"{row['name']}入门池 {number(row['count'])} 条，占本方向 {pct(row['count'],all_tracks[row['name']])}%，池内薪酬中位数 {number(entry_salaries[row['name']]['median'])} K/月（有效 {number(entry_salaries[row['name']]['valid'])} 条）" for row in (broad,high))+'。规模、条件覆盖与薪酬需同时比较，不能仅按最高薪酬选择培养方向。'
            paths=['/voc_pool/track','/voc_pool/salary_by_track','/subtrack']
            add('vocational.track_tradeoff','vocational',text,paths)
            add('track_salary.entry_tradeoff','track_salary',text,paths)
    for i,row in enumerate(sorted(pool.get('track',[]),key=lambda row:-row['count'])[:3]):
        denominator=all_tracks.get(row['name'],0);salary=entry_salaries.get(row['name'],{})
        if not denominator:continue
        text=f"{row['name']}有 {number(row['count'])} 条记录进入入门池，占该方向全部 {number(denominator)} 条岗位的 {pct(row['count'],denominator)}%。"
        if salary.get('valid',0)>=30 and salary.get('median') is not None:
            text+=f"池内该方向有效薪酬 {number(salary['valid'])} 条，中位数 {number(salary['median'])} K/月。"
        add('vocational.track_access_'+str(i),'vocational',text,
            ['/voc_pool/track','/subtrack','/voc_pool/salary_by_track'])
    jobtype={row.get('raw'):row['count'] for row in data.get('jobtype',[])}
    if pool and 'jobtype' in data and data['total']['positions']:
        add('jobtype.entry_definition','jobtype',
            f"校招标签为 {number(jobtype.get('XIAOZHAO',0))} 条，实习标签为 {number(jobtype.get('SHIXI',0))} 条；按学历与经验交集得到的入门池为 {number(pool['count'])} 条。招聘类型与条件交集定义不同，不能把这些数量直接相加或互相替代。",
            ['/jobtype','/voc_pool/count'])
    groups={}
    for row in data.get('job_skill_rows',[]):
        if row['positions']>=100:groups.setdefault(row['skill'],[]).append(row)
    candidates=[]
    for word,rows in groups.items():
        if len(rows)<2 or sum(row['count'] for row in rows)<100:continue
        a=max(rows,key=lambda row:row['count']/row['positions']);b=min(rows,key=lambda row:row['count']/row['positions'])
        candidates.append((a['count']/a['positions']-b['count']/b['positions'],word,a,b))
    if candidates:
        _,word,a,b=max(candidates,key=lambda item:item[0])
        add('track_skills.conditional_contrast','track_skills',
            f"{word}在{a['label']}方向的提及率为 {pct(a['count'],a['positions'])}%（{number(a['count'])}/{number(a['positions'])} 条），在{b['label']}为 {pct(b['count'],b['positions'])}%（{number(b['count'])}/{number(b['positions'])} 条）；这是方向内部比例比较，未提及不等于无需该能力。",
            ['/job_skill_rows'])
    sections={row['section'] for row in data.get('coverage',[])}
    ct=data.get('city_track_rows',[]);city_n={};track_n={}
    for row in ct:
        track_n[row['track']]=track_n.get(row['track'],0)+row['count']
        if row.get('province') and row.get('city'):
            key=(row['province'],row['city']);city_n[key]=city_n.get(key,0)+row['count']
    total_ct=sum(track_n.values())
    if 'city_tracks' in sections:
        for i,(city,cn) in enumerate(sorted(city_n.items(),key=lambda pair:-pair[1])[:2]):
            candidates=[row for row in ct if (row.get('province'),row.get('city'))==city and row['track']!='__other__']
            if not candidates:continue
            row=max(candidates,key=lambda item:item['count']);global_pct=pct(track_n[row['track']],total_ct)
            add('city_tracks.classified_city_'+str(i),'city_tracks',
                f"{'·'.join(city)}已分类方向中，{row['label']}记录最多，为 {number(row['count'])} 条，占本市全部 {number(cn)} 条岗位 {pct(row['count'],cn)}%；同方向占完整样本 {global_pct}%。计数反映规模，城市内份额用于区分相对集中。",
                ['/city_track_rows'])
    if 'lq' in sections and len(city_n)>=2 and data.get('meta',{}).get('filters',{}).get('region',{}).get('level')!='city':
        from joint_report_charts import specialization
        view=specialization(data)
        for i,row in enumerate((view or {}).get('data',[])[:2]):
            add('lq.specialized_city_'+str(i),'lq',
                f"{row[0]}的相对集中度为 {row[1]}，该方向 {number(row[2])} 条、本市全部 {number(row[3])} 条。仅在城市不少于一百条、方向单元不少于三十条的范围选取；指数不是增长率、竞争优势或招聘完成率。",
                ['/city_track_rows'])
    if data.get('job_skill_rows') and data.get('skill_described_n') is not None:
        described=data['skill_described_n'];total=data['total']['positions']
        add('track_skills.description_coverage','track_skills',
            f"本次 {number(total)} 条岗位中，有描述 {number(described)} 条，占 {pct(described,total)}%；未取得描述为 {number(total-described)} 条。有描述不等于职责完整或词义已经人工核实。",
            ['/skill_described_n','/total/positions'])
    return out
