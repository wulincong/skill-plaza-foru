"""Reader-facing, evidence-bound paragraphs for the regional report edition.

Quantities are always rendered from the saved aggregate. Pi supplies only the
non-numeric interpretation/application text, which is checked independently.
"""
import re

POLICY='wechat-editorial-prose/3'
NUMBERS=('一','二','三')


def number(value):
    if isinstance(value,int):return format(value,',')
    return format(value,',.2f').rstrip('0').rstrip('.')


def percent(count,total):
    return number(round(count/total*100,2)) if total else '0'


def scope_label(data):
    filters=data.get('meta',{}).get('filters',data.get('filters',{}))
    education={'BUXIAN':'学历不限','CHUZHONGJIYIXIA':'初中及以下','GAOZHONG':'高中','ZHONGZHUAN/ZHONGJI':'中专／中技','GAOZHI':'高职','DAZHUAN':'大专','BENKE':'本科','SHUOSHI':'硕士','BOSHI':'博士'}
    experience={'BUXIAN':'经验不限','ON_CAMPUS':'在校生','GRADUATING':'应届生','LESS_THAN_1':'一年以内','LESS_THAN_3':'三年以内','LESS_THAN_5':'五年以内','LESS_THAN_10':'十年以内','MORE_THAN_10':'十年以上'}
    result=[]
    if filters.get('education'):result.append('学历为'+'、'.join(education.get(v,v) for v in filters['education']))
    if filters.get('experience'):result.append('经验标签为'+'、'.join(experience.get(v,v) for v in filters['experience']))
    return '；'.join(result)


def compact_fact(text):
    """Keep measurements; explanatory conventions live once in the methods."""
    text=re.sub(r'；(?:薪酬差和学历份额差|这是类别分布比较|不同枚举类别|规则归类不等同|该条件比例的分母|这是未控制|比较的是招聘条件结构|排除未分类后|条件覆盖率不代表|条件满足不代表|不同词的记录可以重叠|词表提及不代表|这是方向内部比例比较|该指数描述当前结构|该单元格样本较小|地址层级仍需核对|指数描述的是结构|未取得描述|需人工核实).*','。',text)
    text=re.sub(r'。(?:薪酬差和学历份额差|比较的是招聘条件结构|排除未分类后|条件覆盖率不代表|分位数是岗位样本分布|规模、条件覆盖与薪酬需同时比较|招聘类型与条件交集定义不同|计数反映规模|分母包含该方向缺少描述).*','。',text)
    text=re.sub(r'。仅在城市不少于.*','。',text)
    text=re.sub(r'(市|省|自治区)全部\s*([\d,])',r'\1本次样本共\2',text)
    return text.strip().rstrip('。；')+'。'


def ordered_cities(data):
    return sorted((row for row in data.get('city_profiles',[]) if row.get('count',0)>0),key=lambda row:(-row['count'],row['name']))


def ordered_tracks(data):
    return sorted((row for row in data.get('subtrack',[]) if row.get('key')!='__other__' and row.get('count',0)>0),key=lambda row:(-row['count'],row['name']))


def regional_profile(data):
    """Concrete local names and comparisons supplied to every short writing task."""
    cities=ordered_cities(data);tracks=ordered_tracks(data)
    pool=data.get('voc_pool') or {};entry=dict(pool.get('city',[]))
    return {'region':data['meta']['region'],'industry':data['meta']['industry'],
        'scope':data['meta'].get('filters',{}),'positions':data['total']['positions'],
        'companies':data['total'].get('companies'),
        'leadingCities':[{**row,'entryCount':entry.get(row['name'])} for row in cities[:3]],
        'leadingClassifiedTracks':tracks[:3],
        'cityDirectionLeaders':[{ 'city':city['name'],'leaders':sorted([row for row in data.get('city_track_rows',[]) if row['city']==city['name'] and row.get('track')!='__other__'],key=lambda row:-row['count'])[:2]} for city in cities[:3]],
        'directionSkillLeaders':[{ 'direction':track['name'],'skills':sorted([row for row in data.get('job_skill_rows',[]) if row.get('track')==track['key']],key=lambda row:-row['count'])[:3]} for track in tracks[:3]],
        'overallSalary':data.get('salary',{}),'entrySalary':pool.get('salary',{}),
        'entryPositions':pool.get('count'),
        'writingFocus':'围绕招聘格局、岗位入口、薪酬和能力组合，解释本地区数据回答了什么问题；教学实施只在结尾集中讨论。'}


def summary(data,item):
    total=data['total'];meta=data['meta'];cities=ordered_cities(data)
    qualifier=('本次限定'+scope_label(data)+'，以下总量、份额和薪酬均限于这一筛选样本。') if scope_label(data) else ''
    text=f"摘要｜{qualifier}基于优才知路平台的{number(total['positions'])}条在招岗位记录和{number(total.get('companies',0))}家招聘企业，本报告观察{meta['region']}{meta['industry']}的人才需求。"
    if len(cities)>=2:
        text+='岗位主要集中于'+'、'.join(row['name'] for row in cities[:2])+'，合计占样本'+percent(sum(row['count'] for row in cities[:2]),total['positions'])+'%。'
    text+='进一步联立岗位方向、学历经验与薪酬，才能辨认规模排名之外的入口差别。'
    return text


def core_measurements(data,item,index,facts):
    total=data['total']['positions'];pool=data.get('voc_pool') or {}
    cities=ordered_cities(data)
    if index==0 and cities and 'count' in pool and 'city' in pool and len(cities)>1:
        head=cities[0];entry=dict(pool.get('city',[])).get(head['name'],0)
        return (f"{head['name']}有{number(head['count'])}条岗位，占本次样本{percent(head['count'],total)}%；"
            f"其中{number(entry)}条满足本报告入门条件，覆盖率{percent(entry,head['count'])}%，"
            f"本次范围同口径为{percent(pool['count'],total)}%。")
    sal=data.get('salary') or {};entry_sal=pool.get('salary') or {}
    if index==1 and sal.get('median') is not None and entry_sal.get('valid',0)>=30 and entry_sal.get('median') is not None:
        bounds=''
        if entry_sal.get('p25') is not None and entry_sal.get('p75') is not None:
            bounds=f"，中间一半位于{number(entry_sal['p25'])}—{number(entry_sal['p75'])}K/月"
        return (f"全部有效薪酬样本中位数为{number(sal['median'])}K/月；入门条件样本为{number(entry_sal['median'])}K/月{bounds}"
            f"（入门有效样本{number(entry_sal['valid'])}条）。")
    tracks=ordered_tracks(data)
    if index==2 and len(tracks)>=2:
        entry={row.get('key'):row['count'] for row in pool.get('track',[])}
        def measurement(row):
            text=f"{row['name']}{number(row['count'])}条，占全部岗位{percent(row['count'],total)}%"
            if row.get('key') in entry:text+=f"；其中入门条件岗位{number(entry[row['key']])}条，占该方向{percent(entry[row['key']],row['count'])}%"
            return text
        return '。'.join(measurement(row) for row in tracks[:2])+'。已分类方向合计覆盖全部岗位'+percent(sum(row['count'] for row in tracks),total)+'%。'
    return ''.join(compact_fact(facts[fid]['text']) for fid in item['claims'][index]['findingIds'])


def core(data,item,index,facts):
    claim=item['claims'][index]
    text=NUMBERS[index]+'、'+claim['title']+'。'+core_measurements(data,item,index,facts)
    interpretation=claim['interpretation']
    if index==0:interpretation=re.sub(r'宜按匹配条件后的候选量确定项目覆盖，再分配城市对接与课程资源。$','',interpretation)
    if index==1:interpretation=re.sub(r'宜以入门样本的中位数及四分位区间组织就业沟通，再按具体方向和岗位条件说明差别。$','',interpretation)
    if index==2:interpretation=interpretation.removesuffix('课程容量结合匹配岗位和实际项目资源确定，共享流程与专项工具分别组织。')
    text+=interpretation

    return text


def section(data,item,facts,exclude=()):
    texts=list(dict.fromkeys(compact_fact(facts[fid]['text']) for fid in item['findingIds']))
    return ''.join(text for text in texts if text not in exclude)+item['interpretation']


def paragraphs(data,item,facts,executive=False):
    if executive:
        return [summary(data,item)]+[core(data,item,index,facts) for index in range(3)],None
    headings={'geography':'区域人才策略启示','jobtype':'入口观察','education':'门槛解读','experience':'经历要求','access':'交叉分析的价值','salary':'薪酬定位','tracks':'方向格局判断','track_salary':'量价观察','city_tracks':'本地结构','lq':'地方专长','skills':'能力底座','track_skills':'方向差别','vocational':'人才策略启示'}
    return [section(data,item,facts)],{'title':headings[item['key']],'text':item['action']}



def paths(data,item,kind,index=None):
    if kind=='section-distinct':
        return list(dict.fromkeys(paths(data,item,'section')+paths(data,index,'section')))
    if kind=='summary':
        return ['/total/positions','/total/companies']+(['/city_profiles'] if data.get('city_profiles') else [])
    if kind=='core':
        if index==0 and len(ordered_cities(data))>1 and 'city' in (data.get('voc_pool') or {}) and 'count' in (data.get('voc_pool') or {}):
            return ['/total/positions','/city_profiles','/voc_pool/count','/voc_pool/city']
        if index==1 and (data.get('salary') or {}).get('median') is not None and (data.get('voc_pool') or {}).get('salary',{}).get('valid',0)>=30 and (data.get('voc_pool') or {}).get('salary',{}).get('median') is not None:
            return ['/salary','/voc_pool/salary']
        if index==2 and len(ordered_tracks(data))>=2:return ['/subtrack','/total/positions']+(['/voc_pool/track'] if (data.get('voc_pool') or {}).get('track') else [])
    from report_analysis import derive_findings
    facts={row['id']:row for row in derive_findings(data)}
    ids=item['claims'][index]['findingIds'] if kind=='core' else item['findingIds']
    return list(dict.fromkeys(path for fid in ids for path in facts[fid]['paths']))


def spec(data,item,kind,binding,index=None):
    source_paths=paths(data,item,kind,index);ids=[]
    for path in source_paths:
        matches=[candidate for candidate in binding['fields'] if path==candidate or path.startswith(candidate+'/')]
        if not matches:raise ValueError('融合段落缺少源指标：'+path)
        ids.extend(binding['fields'][max(matches,key=len)])
    return {'op':'editorial','path':'','kind':kind,'index':index,'item':item,
        'inputs':{str(i):{'path':path} for i,path in enumerate(source_paths)},'metricIds':sorted(set(ids))}


def project(data,specification):
    from report_analysis import derive_findings
    facts={row['id']:row for row in derive_findings(data)}
    kind=specification['kind'];item=specification['item'];index=specification.get('index')
    expected={str(i):{'path':path} for i,path in enumerate(paths(data,item,kind,index))}
    if specification.get('inputs')!=expected:raise ValueError('融合段落的统计对象或来源字段不一致')
    if kind=='summary':return summary(data,item)
    if kind=='core':return core(data,item,index,facts)
    if kind=='section':return section(data,item,facts)
    if kind=='section-distinct':return section(data,item,facts,[compact_fact(facts[fid]['text']) for fid in index['findingIds']])
    raise ValueError('未知融合段落类型')


PROCESS_WORDS=re.compile(r'待核验|待审核|待核实|待验证|待确认|尚待|审核通过后|核验后再|初稿|草案|占位|待填写|本批次|本轮写作|受信规则|findingIds|evidenceHash|写作规则')


def content_audit(outline):
    issues=[]
    for screen in outline.get('screens',[]):
        strings=[screen.get('title','')]+screen.get('paragraphs',[])+[screen.get('summary',{}).get('title',''),screen.get('summary',{}).get('text','')]
        strings.extend(text for block in screen.get('blocks',[]) for text in block)
        for text in strings if screen.get('no')!='文献' else []:
            if '应用建议' in text or '项目实施与学习评价' in text:issues.append('成品仍含已停用的固定建议标签')
            match=PROCESS_WORDS.search(text)
            if match:issues.append(screen.get('title','')+'含过程性措辞：'+match.group())
        if screen.get('analysis_key')=='overview':
            ps=screen.get('paragraphs',[])
            if len(ps)!=4 or not ps[0].startswith('摘要｜') or any(not ps[i+1].startswith(NUMBERS[i]+'、') for i in range(3)):
                issues.append('摘要页须由一段摘要和三条融合结论组成')
            if any(re.search(r'分析：|决策启示：|论证：',text) for text in ps):issues.append('摘要页仍将数据、分析或结论拆成独立标签')
    if issues:raise ValueError('；'.join(issues))
    return {'policy':POLICY,'allPass':True,'checks':['integrated-summary','no-process-language','bound-quantities']}


def polish(text):
    """Remove unsupported promise tails while retaining the actual recommendation."""
    if not isinstance(text,str):return text
    text=re.sub(r'[，,；;]\s*(?:确保|保障)[^。；;]*','',text)
    return text.strip()
