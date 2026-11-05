"""Concrete, data-selected project examples and a bounded recovery for writing."""
from editorial_prose import ordered_cities,ordered_tracks

def examples(data,key):
    cities=ordered_cities(data);tracks=ordered_tracks(data)
    places='、'.join(row['name'] for row in cities[:2]) or data['meta']['region']
    direction=tracks[0]['name'] if tracks else data['meta']['industry']
    next_direction=tracks[1]['name'] if len(tracks)>1 else direction
    labels={'geography':'城市分布','jobtype':'招聘类型','education':'学历要求','experience':'经验要求','access':'学历与经验交集','salary':'薪酬分布','tracks':'岗位方向','track_salary':'方向薪酬','city_tracks':'城市方向','lq':'相对集中度','skills':'能力词','track_skills':'方向能力','vocational':'入门条件'}
    text={
      'geography':f'以{places}定位本地机会密集区，再按岗位方向和申请条件缩小清单；企业关联城市与实际工作地点分别确认，避免仅凭城市总量决定求职去向。',
      'jobtype':'把招聘类型作为入口线索，同时保留学历与经验条件。社会招聘和校招标签分别阅读，符合条件的岗位再进入投递清单，能够减少只按标签筛选带来的遗漏。',
      'education':'先看目标岗位接受哪些学历，再联立经验与职责要求。同一学历组中仍有不同的履历门槛，条件匹配与实际能力判断应使用各自的信息。',
      'experience':'初次求职可先观察应届与低经验岗位，再逐条对照职责和项目经历要求。明确的经验年限与实际工作任务一起阅读，比只比较经验分布更有助于准备申请材料。',
      'access':'交叉表能够把分散的学历和经验条件还原为具体入口，优先选择条件同时匹配的组合，再比较方向与报价，比单看某项条件的占比更接近实际岗位筛选。',
      'salary':'薪酬预期先对应可申请的岗位组，再参考中位数与中间区间。总体报价与入门报价分别展示，能够减少用高薪方向或总体均值替代个人起点的误读。',
      'tracks':f'{direction}与{next_direction}分别保留岗位观察清单，方向排序用于理解任务构成；读者还需结合分类覆盖和具体职责，辨认产业内部有哪些不同的工作路径。',
      'track_salary':'把方向岗位量和有效报价放在一起读，高薪但规模较小的方向与规模较大的方向承担不同的就业观察价值；进一步选择应落到相近条件的岗位组。',
      'city_tracks':f'{places}按城市内部方向份额比较，既看共同的大方向，也保留各自的局部特点；城市总量与方向份额共同用于定位可继续研究的岗位清单。',
      'lq':'相对集中程度用来寻找规模排名之外的地方专长，绝对岗位量用来判断观察基础；同时满足结构突出与样本充分的单元，更适合作为深入调研对象。',
      'skills':'先辨认高频技术词与通用能力分别对应什么工作环节，再回到岗位描述看工具怎样组合使用。能力准备围绕完整任务展开，避免把词频直接变成学习顺序。',
      'track_skills':'共同出现的能力可作为跨方向基础，不同方向的专属工具仍需分别准备；对照同一方向中的岗位原文，能够把能力词转化为具体的任务与成果要求。',
      'vocational':'入门条件交集提供了更聚焦的岗位观察范围，但仍需继续对照具体职责与实际工作地点；先明确可申请的入口，再准备能够说明相关任务经历的作品与材料。'}[key]
    if key=='track_salary':
        rows=[row for row in data.get('salary_by_track',[]) if row.get('key')!='__other__' and row.get('valid',0)>=30 and row.get('median') is not None]
        if len(rows)>=2:text=max(rows,key=lambda r:r['median'])['name']+'与'+min(rows,key=lambda r:r['median'])['name']+'分别建立岗位比较清单。方向报价与岗位规模一起阅读，再以学历、经验和职责相近的岗位校准求职预期。'
    if key=='city_tracks':
        parts=[]
        for city in cities[:2]:
            rows=[row for row in data.get('city_track_rows',[]) if row['city']==city['name'] and row.get('track')!='__other__' and row.get('count',0)>0]
            if rows:parts.append(city['name']+'关注'+max(rows,key=lambda r:r['count'])['label'])
        if parts:text='；'.join(parts)+'。这些是城市内部结构的观察重点，进一步比较还应同时看绝对岗位量和具体申请条件。'
    if key=='lq':
        from joint_report_charts import specialization
        rows=(specialization(data) or {}).get('data',[])[:2]
        if rows:text='、'.join(row[0].split('·')[-1].replace('｜','的') for row in rows)+'可作为本地专长的观察线索。相对集中程度与绝对岗位量一起阅读，避免把小样本的高指数理解为普遍需求。'
    if key=='track_skills':
        from joint_findings import skill_contrast
        contrast=skill_contrast(data)
        if contrast:
            _,word,a,b=contrast
            text=a['label']+'与'+b['label']+'对'+word+'的描述提及存在差别。准备方向能力时，可先阅读对应职责和工具组合，提及比例仅提供比较线索，具体熟练程度仍取决于岗位原文。'
    if key=='vocational':
        rows=[r for r in (data.get('voc_pool') or {}).get('track',[]) if r.get('key')!='__other__' and r.get('count',0)>0]
        if rows:text=max(rows,key=lambda r:r['count'])['name']+'提供较多入门条件岗位样本。先对照学历与经验，再以实际职责选择学习和求职准备重点；条件匹配用于建立清单，不能替代企业的具体选拔。'
    label=labels[key]
    return {'action':text,'validation':'阅读'+label+'时保留统计对象、样本范围和对应岗位说明；将结构观察与未测量的能力、录用结果分别判断，后者需要额外证据支持。',
      'decisionRule':'围绕'+label+'选择相近条件的岗位进行比较；当目标人群、工作地点或方向发生变化时重新筛选范围，不把总体结论直接移用到不同对象。'}


def core_examples(data):
    places='、'.join(row['name'] for row in ordered_cities(data)[:2]) or data['meta']['region']
    direction=ordered_tracks(data);lead=direction[0]['name'] if direction else data['meta']['industry']
    return [f'以{places}定位机会密集区，再按学历、经验与方向建立可申请清单，城市选择和条件匹配分别判断。',
      '求职预期对应匹配岗位的薪酬区间，同时阅读职责与申请条件，总体报价和入门报价分别作为参照。',
      f'从{lead}等本地方向辨认工作任务与工具组合，共同基础与专项要求分别准备，再连接到具体岗位。']



def closing_example(data):
    tracks=ordered_tracks(data);lead='、'.join(row['name'] for row in tracks[:2]) or data['meta']['industry']
    return '以'+lead+'等本地方向的岗位职责建立任务样例，先提炼共享的工具流程，再配置专项项目，学习产出包括操作记录、结果文件与业务解释。求职指导使用可申请岗位的薪酬区间；校企合作围绕有明确输入、交付和适用人群的真实任务展开，规模随项目资源与作品表现调整。'


def alignment_problems(data,row):
    key=row['key'];text=row.get('action','');required=[]
    if key=='track_skills':
        from joint_findings import skill_contrast
        contrast=skill_contrast(data)
        if contrast:required=[contrast[1],contrast[2]['label'],contrast[3]['label']]
    elif key=='track_salary':
        quoted=[item for item in data.get('salary_by_track',[]) if item.get('key')!='__other__' and item.get('valid',0)>=30 and item.get('median') is not None]
        if len(quoted)>=2:required=[max(quoted,key=lambda item:item['median'])['name'],min(quoted,key=lambda item:item['median'])['name']]
    elif key=='city_tracks':
        for city in ordered_cities(data)[:2]:
            observed=[item for item in data.get('city_track_rows',[]) if item['city']==city['name'] and item.get('track')!='__other__' and item.get('count',0)>0]
            if observed:required.extend([city['name'],max(observed,key=lambda item:item['count'])['label']])
    elif key=='lq':
        from joint_report_charts import specialization
        candidates=(specialization(data) or {}).get('data',[])[:2]
        for item in candidates:required.extend(item[0].split('·')[-1].split('｜'))
    elif key=='vocational':
        rows=[item for item in (data.get('voc_pool') or {}).get('track',[]) if item.get('key')!='__other__' and item.get('count',0)>0]
        if rows:required=[max(rows,key=lambda item:item['count'])['name']]
    missing=[term for term in dict.fromkeys(required) if term not in text]
    return [key+'建议须回应本章实际比较对象：'+'、'.join(missing)+'；可采用safeExample'] if missing else []


def public_insight_problems(data,row):
    """Do not promote word mentions or marginal aggregates into latent traits."""
    import re
    text=row.get('action','');key=row['key'];issues=[]
    if key not in ('geography','city_tracks','lq'):
        names={r['name'] for r in ordered_cities(data)}
        aliases={name.removesuffix('市') for name in names}
        if any(len(name)>=2 and name in text for name in names|aliases):
            issues.append(key+'短评混入本章未提供的城市交叉比较；只解释本章对应条件与方向')
    for sentence in re.split(r'[。；]',text):
        negated=bool(re.search(r'不能|不等于|不代表|并非|无法|避免(?:据此|直接)?(?:推断|认为)',sentence))
        if not negated and re.search(r'更看重|更重视|高度强调|提示企业.{0,12}(?:重视|看重)|(?:说明|表明).{0,35}(?:更偏向|更看重|更重视)|学历对经验.{0,12}影响|企业.{0,35}(?:进行调整|会调整)',sentence):
            issues.append(key+'把描述结构推成企业偏好或调整机制；只解释已观察的分布与读者意义')
        if key in ('skills','track_skills') and not negated and re.search(r'更强调|更侧重|更突出|要求(?:明显|显著)?高于|实际需求存在',sentence):
            issues.append(key+'把提及比例推成真实要求强度；改为描述提及差别和有条件的准备建议')
        if key=='tracks' and '分别对应' in sentence and not re.search(r'可|建议|例如|样例',sentence):
            issues.append(key+'从方向标题推断了未查询的具体职责；改为方向结构与阅读价值')
        if key in ('education','experience','access') and '相互影响' in sentence and not negated:
            issues.append(key+'把条件交叉分布推成影响机制；改为联合条件的筛选意义')
        if key in ('skills','track_skills') and not negated and re.search(r'(?:提及|频繁出现|反复出现|描述).{0,25}(?:说明|提示|显示|表明).{0,25}重要',sentence):
            issues.append(key+'把描述频次推成重要性测量；改为任务准备的观察线索')
        field={'education':'edu','experience':'exp','jobtype':'jobtype'}.get(key)
        if field and not negated:
            for label in data.get(field,[]):
                if label['count']*2<=data['total']['positions'] and re.search(re.escape(label['name'])+r'.{0,16}(?:多数|过半|超过一半)',sentence):
                    issues.append(key+'多数表述与实际占比不符；使用已给事实而非夸大份额')
    if key=='jobtype':
        for label in data.get('jobtype',[]):
            if label['count']>0 and re.search(re.escape(label['name'])+r'[^。；]{0,8}(?:为零|为空白|没有)',text):
                issues.append('招聘标签并非空样本，短评不能写为零')
    return list(dict.fromkeys(issues))
