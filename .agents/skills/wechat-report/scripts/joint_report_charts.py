"""Multivariate report views derived from complete, same-scope saved aggregates."""
from collections import defaultdict

def requirement_label(value):return '未知枚举' if value.startswith('未知枚举') else value


def city_comparison(data):
    rows=[row for row in data.get('city_profiles',[]) if row.get('valid',0)>=30 and row.get('median') is not None]
    rows=sorted(rows,key=lambda row:(-row['count'],row['name']))[:6]
    return {'kind':'city_combo','caption':'城市联合比较｜薪酬中位数、本科要求比例、岗位规模；n为全部岗位数',
            'data':[[row['name'],row['count'],row['valid'],row['median'],row['bachelorShare']] for row in rows],
            'metrics':['salary_median','bachelor_share','positions'],'unit':'K/月、%、条'} if rows else None


def requirements_flow(data):
    totals=defaultdict(int);pairs=defaultdict(int)
    for education,experience,count in data.get('edu_exp',[]):
        if count<=0:continue
        source='学历｜'+requirement_label(education);target='经验｜'+requirement_label(experience)
        totals[source]+=count;totals[target]+=count
        pairs[(source,target)]+=count
    links=[{'source':source,'target':target,'value':count} for (source,target),count in pairs.items()]
    return {'kind':'requirements_flow','caption':'学历与经验要求的联合构成｜连线为岗位频数，不表示人员流动',
            'nodes':[{'name':name,'value':count} for name,count in totals.items()],'links':links}


def experience_pair(data):
    totals=defaultdict(int);values=defaultdict(int);experience=defaultdict(int)
    for edu,exp,count in data.get('edu_exp',[]):
        edu,exp=requirement_label(edu),requirement_label(exp)
        totals[edu]+=count;values[(edu,exp)]+=count;experience[exp]+=count
    groups=sorted(totals,key=lambda name:(-totals[name],name))[:2]
    if len(groups)<2:return None
    labels=sorted(experience,key=lambda label:(-experience[label],label))[:8]
    return {'kind':'paired_share','caption':'主要学历组内部的经验要求｜分母分别为各自学历组，不能相加',
            'groups':groups,'denominators':[totals[group] for group in groups],
            'data':[[label,*[round(values[(group,label)]/totals[group]*100,2) for group in groups]] for label in labels]}


def access_matrix(data):
    erows=defaultdict(int);xrows=defaultdict(int);values=defaultdict(int)
    for edu,exp,count in data.get('edu_exp',[]):
        edu,exp=requirement_label(edu),requirement_label(exp)
        erows[edu]+=count;xrows[exp]+=count;values[(edu,exp)]+=count
    rows=sorted(erows,key=lambda label:(-erows[label],label));cols=sorted(xrows,key=lambda label:(-xrows[label],label))
    return {'kind':'bubble_matrix','caption':'学历×经验门槛｜圆大小映射岗位数，颜色为该学历组内占比（%）',
            'rows':rows,'cols':cols,'cells':[[i,j,values[(edu,exp)],round(values[(edu,exp)]/erows[edu]*100,2)] for i,edu in enumerate(rows) for j,exp in enumerate(cols)],
            'colorUnit':'%','colorMax':100,'colorMeaning':'组内占比'}


def track_treemap(data):
    salaries={row['key']:row for row in data.get('salary_by_track',[])}
    rows=[]
    for row in data.get('subtrack',[]):
        salary=salaries.get(row['key'],{})
        median=salary.get('median') if salary.get('valid',0)>=30 else None
        rows.append({'name':row['name'],'value':row['count'],'median':median,'valid':salary.get('valid',0),'key':row['key']})
    return {'kind':'track_treemap','caption':'岗位方向规模与薪酬定位｜面积为岗位数，颜色为方向中位数；未分类单列',
            'data':rows,'colorUnit':'K/月'}


def salary_intervals(data,cohorts=False):
    if cohorts:
        salaries=[('全部岗位',data.get('salary') or {}),('职教入门池',(data.get('voc_pool') or {}).get('salary') or {})]
    else:salaries=[(row['name'],row) for row in data.get('salary_by_track',[])]
    rows=[[label,row['valid'],row['p25'],row['median'],row['p75']] for label,row in salaries
          if row.get('valid',0)>=30 and all(row.get(key) is not None for key in ['p25','median','p75'])]
    if not cohorts:rows.sort(key=lambda row:(-row[3],row[0]))
    return {'kind':'quantile_interval','caption':'薪酬分布与样本量｜线段为P25—P75，点为中位数，点大小表示有效样本量',
            'data':rows,'unit':'K/月'} if rows else None


def city_track_matrix(data):
    source=data.get('city_track_rows',[]);city_totals=defaultdict(int);track_totals=defaultdict(int);values=defaultdict(int)
    for row in source:
        track_totals[row['label']]+=row['count']
        if row.get('city') and row.get('province'):
            city=row['province']+'·'+row['city'];city_totals[city]+=row['count'];values[(city,row['label'])]+=row['count']
    total=sum(track_totals.values())
    cities=sorted(city_totals,key=lambda name:(-city_totals[name],name))[:6]
    tracks=sorted(track_totals,key=lambda name:(-track_totals[name],name))[:6]
    cells=[]
    for i,city in enumerate(cities):
        for j,track in enumerate(tracks):
            count=values[(city,track)]
            lq=(count/city_totals[city])/(track_totals[track]/total) if total and track_totals[track] else 0
            cells.append([i,j,count,round(lq,3)])
    return {'kind':'bubble_matrix','caption':'城市×方向结构｜圆大小映射岗位数，颜色为LQ；色阶上限3，空格为零频数',
            'rows':[name.split('·',1)[1] if data['meta']['filters']['region']['level']!='national' else name for name in cities],
            'cols':tracks,'cells':cells,'colorUnit':'LQ','colorMax':3,'colorMeaning':'方向集中度'}


def specialization(data):
    source=data.get('city_track_rows',[]);city_totals=defaultdict(int);track_totals=defaultdict(int)
    for row in source:
        track_totals[row['track']]+=row['count']
        if row.get('city') and row.get('province'):city_totals[(row['province'],row['city'])]+=row['count']
    total=sum(track_totals.values());selected=[]
    for city,cn in sorted(city_totals.items(),key=lambda item:(-item[1],item[0]))[:8]:
        if cn<100:continue
        candidates=[row for row in source if (row.get('province'),row.get('city'))==city and row['track']!='__other__' and row['count']>=30]
        if not candidates:continue
        row=max(candidates,key=lambda row:(row['count']/cn)/(track_totals[row['track']]/total))
        lq=(row['count']/cn)/(track_totals[row['track']]/total)
        name=city[1] if data['meta']['filters']['region']['level']!='national' else '·'.join(city)
        selected.append([name+'｜'+row['label'],round(lq,3),row['count'],cn])
    selected.sort(key=lambda row:(-row[1],row[0]))
    return {'kind':'specialization_dot','caption':'主要城市的相对集中方向｜点大小映射方向岗位数；城市≥100、单元格≥30',
            'data':selected} if selected else None


def skill_network(data):
    rows=data.get('job_skill_rows',[]);track_n={row['label']:row['positions'] for row in rows};word_n=defaultdict(int)
    for row in rows:word_n[row['skill']]+=row['count']
    tracks=sorted(track_n,key=lambda label:(-track_n[label],label))[:5]
    words=sorted(word_n,key=lambda label:(-word_n[label],label))[:5]
    nodes=[{'name':'方向｜'+label,'label':label,'value':track_n[label],'group':0} for label in tracks]
    nodes += [{'name':'技能｜'+label,'label':label,'value':word_n[label],'group':1} for label in words]
    links=[{'source':'方向｜'+row['label'],'target':'技能｜'+row['skill'],'value':row['count']} for row in rows if row['label'] in tracks and row['skill'] in words and row['count']>0]
    return {'kind':'skill_network','caption':'方向与能力词的关联｜边为描述提及频数，多词可重叠，不是人才流量',
            'nodes':nodes,'links':links}


def entry_scatter(data):
    pool=data.get('voc_pool') or {};all_counts={row['name']:row['count'] for row in data.get('subtrack',[])}
    salaries={row['name']:row for row in pool.get('salary_by_track',[])}
    rows=[]
    for row in pool.get('track',[]):
        salary=salaries.get(row['name'],{});denominator=all_counts.get(row['name'],0)
        if not denominator or salary.get('valid',0)<30 or salary.get('median') is None:continue
        rows.append([row['name'],salary['median'],round(row['count']/denominator*100,2),row['count'],salary['valid'],denominator])
    return {'kind':'entry_scatter','caption':'入门池的方向定位｜横轴为池内薪酬中位数，纵轴为本方向入池比例，圆大小表示池内岗位规模',
            'data':sorted(rows,key=lambda row:(-row[3],row[0]))[:8]} if rows else None


PROJECTIONS={'joint_city':city_comparison,'joint_requirements':requirements_flow,'joint_experience':experience_pair,
    'joint_access':access_matrix,'joint_tracks':track_treemap,'joint_salary':lambda data:salary_intervals(data,True),
    'joint_track_salary':salary_intervals,'joint_city_tracks':city_track_matrix,'joint_lq':specialization,
    'joint_skills':skill_network,'joint_entry':entry_scatter}
