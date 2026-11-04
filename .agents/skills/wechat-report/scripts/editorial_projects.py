"""Concrete, data-selected project examples and a bounded recovery for writing."""
from editorial_prose import ordered_cities,ordered_tracks

def examples(data,key):
    cities=ordered_cities(data);tracks=ordered_tracks(data)
    places='、'.join(row['name'] for row in cities[:2]) or data['meta']['region']
    direction=tracks[0]['name'] if tracks else data['meta']['industry']
    next_direction=tracks[1]['name'] if len(tracks)>1 else direction
    if key=='vocational':
        entry=sorted([row for row in (data.get('voc_pool') or {}).get('track',[]) if row.get('key')!='__other__' and row.get('count',0)>0],key=lambda row:-row['count'])
        if entry:direction=entry[0]['name'];next_direction=entry[1]['name'] if len(entry)>1 else direction
    if key=='track_salary':
        quoted=[row for row in data.get('salary_by_track',[]) if row.get('key')!='__other__' and row.get('valid',0)>=30 and row.get('median') is not None]
        if len(quoted)>=2:direction=max(quoted,key=lambda row:row['median'])['name'];next_direction=min(quoted,key=lambda row:row['median'])['name']
    skills=sorted([row for row in data.get('job_skill_rows',[]) if tracks and row.get('track')==tracks[0]['key'] and not any(word in row['skill'] for word in ('沟通','协作','学习能力','责任心','团队','抗压'))],key=lambda row:-row['count'])
    # Observed labels may contain digits. Narrative examples choose text-only labels.
    tools='、'.join(row['skill'] for row in skills[:3] if not any(c.isnumeric() for c in row['skill'])) or '数据整理与结果复现工具'
    project=(f'围绕{direction}设置{tools}实践，提交数据说明、操作记录和可复现成果；'
             f'{next_direction}另设方向任务包，以目标岗位的职责说明组织工具练习和成果汇报。')
    rows={
     'geography':(f'以{places}的企业关联岗位清单建立校企合作候选，先按学生适用条件筛选，再在各城市内部选择方向任务。城市总量用于安排调研覆盖，实际课程容量由匹配后的岗位清单和项目资源共同确定。',
         '由院校教师与合作单位共同选择任务样例，形成场景说明、输入资料、交付要求和评价量规。学生提交作品及操作记录，评价结果回到对应岗位条件，逐步形成可复用的城市项目资源。',
         '学生已具备任务所需工具基础时进入完整场景项目；准备不足时先完成同一任务的拆分练习，再根据作品质量衔接后续实践。城市选择和项目难度分别决策，不按城市名称预设培养层次。'),
     'jobtype':('岗位清单同时保留招聘类型和申请条件，分别建立校招岗位项目与满足入门条件的其他岗位项目。课程使用同一成果标准，区别放在投递场景、简历说明和面向目标岗位的作品展示。',
         '组织学生用真实岗位说明完成投递材料、项目讲解与模拟面谈，教师检查岗位条件是否匹配、作品能否说明任务过程、申请材料是否完整。评价聚焦可展示成果，不把招聘标签当成录用承诺。',
         '目标岗位有明确经验要求时，课程增加连续项目记录和团队交付说明；面向初次就业的岗位则先完成完整基础作品。学生依据适用条件选择清单，项目难度依据作品表现调整。'),
     'education':('学历条件用于判断目标岗位是否适用，不据此指定技术任务。'+project,
         '所有学习者采用相同的任务入口，提交数据处理过程、工具操作与结果解释；教师按作品的正确性、完整性和复现性评价，学习记录用于决定下一阶段训练内容。',
         '按任务准备度设置共同基础与专项实践路径：能独立完成基础作品者进入方向项目，需要支持者增加拆分练习与反馈。学历仍保留在岗位匹配清单中，课程分流依据实际任务表现。'),
     'experience':('将经验要求转化为可展示的连续项目经历：从任务理解、资料整理到工具操作和成果说明逐步完成。'+project,
         '学生以版本记录、问题处理说明和最终作品展示项目过程，教师与项目导师共同评价任务完成度、错误定位和沟通表达。经验标签用于选择目标岗位，项目评价使用可观察的工作成果。',
         '尚不能独立完成完整任务时采用分步练习与协作支持，能够稳定提交可复现成果后进入完整项目。已有相关实践者增加复杂输入和交付约束，学习路径由作品表现调整。'),
     'access':('按学历与经验条件的交集建立适用岗位清单，课程面向同一任务开放。'+project,
         '先完成共同的任务样例与工具练习，再提交个人作品及小组交付说明。教师分别检查条件适用性和任务完成质量，前者服务岗位筛选，后者服务课程分流，避免相互替代。',
         '符合目标岗位申请条件且作品达到要求的学生进入对应合作项目；条件适用但工具准备不足者先补充练习。当前条件不适用时调整岗位清单，保留共享的课程与作品入口。'),
     'salary':('就业沟通采用入门样本的薪酬区间，并将报价对应到具体方向、岗位条件和工作内容。学生比较匹配岗位的薪酬构成与职责，在简历和面谈中用项目成果说明自身任务准备情况。',
         '组织岗位报价阅读与模拟面谈，提交包含薪酬单位、工作条件、职责和个人作品的岗位比较表。教师评价参照对象是否一致、区间表达是否准确，以及求职预期是否对应实际适用岗位。',
         '目标岗位条件与入门样本接近时使用入门区间开展就业沟通；条件差异较大时改用对应方向和岗位组的分布。薪酬目标随匹配岗位调整，项目难度依据任务要求和作品表现决定。'),
     'tracks':(project,'学生提交能够复现的任务流程、工具配置说明和结果展示，教师按方向任务分别评价输入处理、过程正确性与成果解释。共享环节采用共同标准，专项工具采用对应任务的评价量规。','先完成共用流程，再按目标岗位方向进入专项任务；能够独立复现结果者增加真实场景约束，需要支持者保留拆分练习。方向选择参考本地岗位结构，具体项目容量与教学资源相衔接。'),
     'track_salary':(f'以{direction}和{next_direction}分别建立方向岗位卡片，合并展示职责、申请条件、薪酬区间与课程作品要求。覆盖面较广的方向配置共同项目，专项方向配置明确交付物的小规模实践。','通过方向岗位比较与作品讲解评价就业定位，要求学生说明岗位条件、报价口径与自身成果之间的对应关系。课程评价仍以任务正确性和可复现性为主，薪酬水平用于就业沟通。','专项岗位有清晰职责和可用项目资源时安排方向实践；资源不足时保留共同流程训练。就业预期采用对应岗位区间，课程规模同时考虑岗位基础和教学条件，不依据薪酬高低直接扩张。'),
     'city_tracks':(f'在{places}分别从本次城市与方向交叉清单选择合作样例，按已观察的方向组合组织项目。'+project,'合作样例形成明确的场景、输入与输出说明，由教师和项目导师共同评价作品。城市层面记录项目资源与学生适用条件，方向层面评价工具使用、交付完整性和业务解释。','先以各城市交叉清单中有样本支持的方向组织项目，其他方向共享基础任务。新增专项以明确的合作任务为条件，城市课程结构随实际可用项目调整，不预设城市对应的技术层次。'),
     'lq':('合作方向同时参考城市内相对集中程度与绝对岗位量。样本基础充分且任务资源可用的方向组织完整项目，数量较少的专项场景采用案例教学，共享工具流程可跨城市复用。','形成城市与方向项目卡片，记录样本基础、任务资源和可交付成果。学生提交场景分析、工具操作与结果说明，评价项目是否完成真实工作流程，以及结果能否复现。','结构集中但绝对样本较少时控制专项项目规模，采用案例或小组实践；样本与资源均充分时增加完整任务。课程安排随项目资源调整，结构指数用于定位方向而非推断增长。'),
     'skills':(f'把本地高频能力词转化为操作任务，技术练习优先使用{tools}，通用能力贯穿任务分工、过程沟通和成果汇报。'+project,'评价同时查看操作记录、结果文件和成果讲解，技术环节检查正确性与复现性，协作环节检查任务衔接和说明完整性。能力词用于选择练习内容，课程评价依托学生实际作品。','共享工具流程作为共同模块，目标岗位有明确专项要求时增加对应工具任务；提及较少的能力是否加入课程由具体职责决定。学生根据作品表现进入后续项目，避免以词频直接分配课时。'),
     'track_skills':(project,'按方向分别提供输入资料、工具约束与交付要求，检查操作是否正确、结果能否复现、解释是否对应业务问题。共用流程采用共同评价标准，方向工具采用各自任务的检查项目。','完成共享流程后按目标方向进入对应工具任务；工具准备不足者先完成简化输入和分步练习。课程分支依据已观察的方向能力组合与实际任务，不按学历或薪酬预设技术层次。'),
     'vocational':(f'从{direction}的入门条件岗位选择共同实践样例，同时保留{next_direction}的专项任务。学生完成工具练习、过程记录与作品汇报后，按适用条件进入对应岗位项目。','评价入门作品的完整流程、工具操作和结果解释，并对照目标岗位的申请条件组织就业沟通。项目导师记录学生完成任务所需支持，教师据此安排后续练习与方向实践。','符合申请条件但准备不足时先完成共同基础作品；能够独立完成工具任务时进入专项实践。专项项目以可用任务资源为条件，岗位对接保留本次既定筛选范围。')}
    if key=='city_tracks':
        route=[]
        for city in cities[:2]:
            observed=[row for row in data.get('city_track_rows',[]) if row['city']==city['name'] and row.get('track')!='__other__' and row.get('count',0)>0]
            if observed:route.append(city['name']+'以'+max(observed,key=lambda row:row['count'])['label']+'岗位样例组织方向任务')
        if route:rows[key]=('；'.join(route)+'。各任务提交输入说明、工具操作记录和可复现结果，按目标岗位条件选择学生适用的合作项目。',rows[key][1],rows[key][2])
    if key=='lq':
        from joint_report_charts import specialization
        candidates=(specialization(data) or {}).get('data',[])[:2]
        if candidates:
            units='、'.join(item[0].split('·')[-1].replace('｜','的') for item in candidates)
            rows[key]=('以'+units+'作为城市专项项目候选，结合对应方向的绝对岗位量选择合作样例。共享工具流程跨城市复用，专项任务保留明确的输入、操作和交付要求。',rows[key][1],rows[key][2])
    if key=='track_skills':
        from joint_findings import skill_contrast
        contrast=skill_contrast(data)
        if contrast:
            _,word,a,b=contrast
            rows[key]=(a['label']+'方向将'+word+'纳入专项任务，提交操作记录、结果文件和业务解释；'+b['label']+'方向先按具体职责组织任务，涉及'+word+'时再增加对应练习。共享环节使用统一的数据说明与成果表达标准。',
             '共同检查输入说明、操作过程与结果复现，专项任务另设工具使用和业务解释量规。能力词在岗位描述中的提及差异用于选择项目内容，学生的实际能力由作品评价。',
             '目标岗位明确涉及'+word+'时安排对应专项练习，其他岗位保留共享流程与职责对应的工具任务。项目难度根据学生准备情况调整，提及比例较低不等于岗位不需要该能力。')
    if key=='vocational' and (data.get('voc_pool') or {}).get('count')==0:
        rows[key]=('当前岗位筛选范围没有符合职教入门条件的交集，课程面向本次既定人群组织。'+project,'学生以完整作品、操作记录与成果讲解展示任务准备情况，教师按目标岗位职责评价工具使用与结果解释，不引用其他学历或其他地区的入门样本代替。','目标岗位有明确专项要求时安排相应工具与项目实践，需要补充准备时先完成共享流程训练。岗位条件和作品表现分别评价，保持用户给定的人群与地域范围。')
    return dict(zip(('action','validation','decisionRule'),rows[key]))


def core_examples(data):
    places='、'.join(row['name'] for row in ordered_cities(data)[:2]) or data['meta']['region']
    direction=ordered_tracks(data);lead=direction[0]['name'] if direction else data['meta']['industry']
    return [f'以{places}的匹配岗位清单选择合作项目，先确定学生适用条件，再按方向配置实践资源。',
      '求职预期采用匹配岗位的薪酬区间，就业沟通同时说明职责与申请条件，以项目成果支持个人岗位定位。',
      f'以{lead}建设共用任务模块，再按方向工具设置项目分支，用可复现成果连接课程与本地岗位。']


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
