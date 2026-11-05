"""Reproducible evidence for an agent-written analysis, before report generation.

Consumes saved aggregates only. It does not query the database or write the
interpretation: the reporting agent must examine the evidence and write it.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from report_runtime import report_root
BASE = report_root(__file__)
VERSION = 'wechat-analysis/1'
LABELS = {
    'overview': '核心发现', 'geography': '地域分布', 'jobtype': '招聘类型',
    'education': '学历要求', 'experience': '经验要求', 'access': '学历与经验交叉',
    'salary': '薪酬结构', 'vocational': '职教入门岗位', 'tracks': '岗位方向',
    'track_salary': '方向薪酬', 'city_tracks': '城市与方向', 'lq': '地域方向集中度',
    'skills': '能力关键词', 'track_skills': '方向与技能',
}
DIMENSIONS = ('overview', 'geography', 'requirements', 'salary', 'vocational',
              'tracks', 'city_tracks', 'lq', 'track_salary', 'skills', 'track_skills')
STATUS_LABELS = {'not_requested': '未请求统计', 'unavailable': '无有效数据',
                 'unsupported': '结果不支持', 'empty': '空样本'}


def fingerprint(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()


def pct(a, b):
    return round(a / b * 100, 2) if b else None


def number(n):
    return format(n, ',') if isinstance(n, int) else format(n, ',.2f').rstrip('0').rstrip('.')


def derive_findings(data):
    """Derived comparisons have explicit objects, denominators and input paths."""
    out = []
    n = data['total']['positions']

    def add(key, section, text, paths, kind='structure', **details):
        out.append(dict(id=key, section=section, text=text, kind=kind,
                        paths=paths, **details))

    add('overview.size', 'overview',
        f"本次筛选包含 {number(n)} 条在招岗位记录，关联 {number(data['total']['companies'])} 家企业；岗位记录数不等于招聘人数。",
        ['/total/positions', '/total/companies'])
    if not n:
        return out

    cities = sorted(data.get('city', []), key=lambda r: (-r[1], r[0]))
    if cities:
        head = cities[:2]
        count = sum(r[1] for r in head)
        text = '、'.join(f'{r[0]} {number(r[1])} 条' for r in head)
        add('geography.concentration', 'geography',
            f'按岗位数排序靠前的城市为{text}，合计占全部岗位记录的 {pct(count, n)}%。',
            ['/city', '/total/positions'], 'comparison', numerator=count, denominator=n)
        if len(cities) > 1:
            a, b = cities[:2]
            add('geography.gap', 'geography',
                f'{a[0]}与{b[0]}相差 {number(a[1]-b[1])} 条岗位记录，占全部样本的比例相差 {pct(a[1]-b[1], n)} 个百分点。',
                ['/city', '/total/positions'], 'comparison', denominator=n)
        missing = n - sum(r[1] for r in cities)
        add('geography.coverage', 'geography',
            f'企业关联地址可归属 {number(len(cities))} 个省市组合，另有 {number(missing)} 条记录无法归属，约占全部样本的 {pct(missing, n)}%；地址层级仍需核对。',
            ['/city', '/total/positions'], denominator=n)

    for field, section in [('jobtype', 'jobtype'), ('edu', 'education'),
                           ('exp', 'experience'), ('subtrack', 'tracks')]:
        rows = sorted(data.get(field, []), key=lambda r: (-r['count'], r['name']))
        if not rows:
            continue
        a = rows[0]
        add(section+'.leading', section,
            f"{a['name']}记录为 {number(a['count'])} 条，占全部岗位记录的 {pct(a['count'], n)}%。",
            ['/'+field, '/total/positions'], numerator=a['count'], denominator=n)
        if len(rows) > 1:
            b = rows[1]
            add(section+'.comparison', section,
                f"按记录数排序，{a['name']}与{b['name']}分别占 {pct(a['count'], n)}% 和 {pct(b['count'], n)}%，相差 {pct(a['count']-b['count'], n)} 个百分点；这是类别分布比较。",
                ['/'+field, '/total/positions'], 'comparison', denominator=n)
        for i, row in enumerate(rows[1:], 1):
            add(section+'.category_'+str(i), section,
                f"{row['name']}类别包含 {number(row['count'])} 条岗位，占全部样本的 {pct(row['count'], n)}%；不同枚举类别按原始标签解释。",
                ['/'+field, '/total/positions'], numerator=row['count'], denominator=n)
        if section == 'tracks':
            other = sum(r['count'] for r in rows if r.get('key') == '__other__')
            add('tracks.coverage', section,
                f'显式方向规则未分类的记录为 {number(other)} 条，占全部岗位的 {pct(other, n)}%；规则归类不等同于官方产业赛道。',
                ['/subtrack', '/total/positions'], denominator=n)

    pairs = sorted(data.get('edu_exp', []), key=lambda r: (-r[2], r[0], r[1]))
    if pairs:
        edu, exp, count = pairs[0]
        edu_n = sum(r[2] for r in pairs if r[0] == edu)
        add('access.leading', 'access',
            f'学历与经验交叉中，{edu}×{exp}组合包含 {number(count)} 条岗位，占全部样本的 {pct(count, n)}%。',
            ['/edu_exp', '/total/positions'], numerator=count, denominator=n)
        add('access.conditional', 'access',
            f'在学历类别为{edu}的 {number(edu_n)} 条岗位中，经验类别为{exp}的记录占 {pct(count, edu_n)}%；该条件比例的分母仅为这一学历类别。',
            ['/edu_exp'], 'comparison', numerator=count, denominator=edu_n)
        for i, (edu, exp, count) in enumerate(pairs[1:5], 1):
            en = sum(r[2] for r in pairs if r[0] == edu)
            add('access.combination_'+str(i), 'access',
                f'{edu}×{exp}包含 {number(count)} 条岗位，占总体 {pct(count, n)}%，占该学历类别 {number(en)} 条记录的 {pct(count, en)}%。',
                ['/edu_exp', '/total/positions'], 'comparison', numerator=count, denominator=en)

    sal = data.get('salary') or {}
    if sal.get('valid') and sal.get('median') is not None:
        add('salary.quantiles', 'salary',
            f"有效薪酬记录为 {number(sal['valid'])} 条，中位数为 {number(sal['median'])} K/月；中间一半样本位于 {number(sal['p25'])} 至 {number(sal['p75'])} K/月，四分位距为 {number(sal['p75']-sal['p25'])} K/月。",
            ['/salary'], 'comparison', denominator=sal['valid'])
        add('salary.coverage', 'salary',
            f"全部岗位中有 {number(sal['valid'])} 条符合薪酬规则，有效率为 {pct(sal['valid'], n)}%；分布以有效薪酬样本为分母。",
            ['/salary', '/total/positions'], denominator=n)
        bins = sorted(data.get('salary_hist', []), key=lambda r: -r['count'])
        if bins:
            a = bins[0]
            add('salary.modal_band', 'salary',
                f"岗位量最多的薪酬档为{a['name']}，包含 {number(a['count'])} 条，占有效薪酬记录的 {pct(a['count'], sal['valid'])}%。",
                ['/salary_hist', '/salary'], denominator=sal['valid'])

    pool = data.get('voc_pool')
    if pool is not None:
        vn = pool['count']
        add('vocational.size', 'vocational',
            f'按已声明学历与经验条件取交集的职教入门岗位池为 {number(vn)} 条，占总体 {pct(vn, n)}%；条件满足不代表已经录用。',
            ['/voc_pool/count', '/total/positions'], numerator=vn, denominator=n)
        vs = pool.get('salary') or {}
        if vs.get('valid') and vs.get('median') is not None and sal.get('valid'):
            add('vocational.salary_comparison', 'vocational',
                f"入门池有效薪酬样本为 {number(vs['valid'])} 条，中位数 {number(vs['median'])} K/月；总体有效样本为 {number(sal['valid'])} 条，中位数 {number(sal['median'])} K/月，两者中位数之差为 {number(vs['median']-sal['median'])} K/月，未控制岗位与经验结构。",
                ['/voc_pool/salary', '/salary'], 'comparison')
        vc = sorted([r for r in pool.get('city', []) if r[0]], key=lambda r: (-r[1], r[0]))
        if vc and vn:
            a = vc[0]
            add('vocational.geography', 'vocational',
                f'入门池中{a[0]}包含 {number(a[1])} 条岗位，占入门池的 {pct(a[1], vn)}%；该比例使用入门池而非总体作分母。',
                ['/voc_pool/city', '/voc_pool/count'], denominator=vn)
            # A nationwide unqualified city name is ambiguous across provinces.
            if data['meta'].get('filters', {}).get('region', {}).get('level') != 'national':
                counts = dict(cities)
                for i, (city, count) in enumerate(vc[:3]):
                    if city not in counts:
                        continue
                    add('vocational.city_comparison_'+str(i), 'vocational',
                        f'{city}占入门岗位池的 {pct(count, vn)}%，占全部岗位的 {pct(counts[city], n)}%；两种地域份额相差 {round(pct(count, vn)-pct(counts[city], n), 2)} 个百分点，分母分别为入门池和全部岗位。',
                        ['/voc_pool/city', '/voc_pool/count', '/city', '/total/positions'], 'comparison')

    salaries = sorted([r for r in data.get('salary_by_track', []) if r.get('valid') and r.get('median') is not None],
                      key=lambda r: (-r['valid'], r['name']))
    for i, row in enumerate(salaries[:2]):
        small = '有效样本较小，仅作描述。' if row['valid'] < 30 else '这是未控制学历与经验的组内摘要。'
        add('track_salary.group_'+str(i), 'track_salary',
            f"{row['name']}有效薪酬样本为 {number(row['valid'])} 条，中位数为 {number(row['median'])} K/月；{small}",
            ['/salary_by_track'], 'comparison' if i else 'structure', sampleN=row['valid'])

    ct = data.get('city_track_rows') or []
    sections = {c['section'] for c in data.get('coverage', [])}
    city_totals, track_totals = {}, {}
    for r in ct:
        track_totals[r['track']] = track_totals.get(r['track'], 0) + r['count']
        if r.get('city') and r.get('province'):
            city = (r['province'], r['city'])
            city_totals[city] = city_totals.get(city, 0) + r['count']
    all_ct = sum(track_totals.values())
    for i, (city, cn) in enumerate(sorted(city_totals.items(), key=lambda item: (-item[1], item[0]))[:2]):
        rows = [r for r in ct if (r.get('province'), r.get('city')) == city]
        a = max(rows, key=lambda r: r['count'])
        label = '·'.join(city)
        local, overall = pct(a['count'], cn), pct(track_totals[a['track']], all_ct)
        if 'city_tracks' in sections:
            add('city_tracks.city_'+str(i), 'city_tracks',
                f"{label}的{a['label']}方向有 {number(a['count'])} 条，占本市 {number(cn)} 条记录的 {local}%；该方向在完整样本中占 {overall}%，两者相差 {round(local-overall, 2)} 个百分点。",
                ['/city_track_rows'], 'comparison', denominator=cn)
        if 'lq' in sections and track_totals[a['track']]:
            lq = (a['count']/cn)/(track_totals[a['track']]/all_ct)
            small = '该单元格样本较小，不作强弱排名。' if a['count'] < 30 else '该指数描述当前结构，不说明动态迁移。'
            add('lq.city_'+str(i), 'lq',
                f"{label}的{a['label']}方向为 {number(a['count'])} 条，区位商为 {round(lq, 3)}，以本市方向占比除以完整样本该方向占比计算；{small}",
                ['/city_track_rows'], 'comparison', sampleN=a['count'])

    described = data.get('skill_described_n') or 0
    words = sorted(data.get('keywords', []), key=lambda r: (-r['count'], r['name']))
    if described and words:
        add('skills.coverage', 'skills',
            f'技能统计有描述样本为 {number(described)} 条，占全部岗位的 {pct(described, n)}%；词表提及不代表能力全部需求。',
            ['/skill_described_n', '/total/positions'], denominator=n)
        for i, row in enumerate(words[:2]):
            add('skills.word_'+str(i), 'skills',
                f"{row['name']}在 {number(row['count'])} 条岗位描述中被提及，占有描述样本的 {pct(row['count'], described)}%，占全部岗位的 {pct(row['count'], n)}%；不同词的记录可以重叠。",
                ['/keywords', '/skill_described_n', '/total/positions'], 'comparison', denominator=described)
    skill_rows = data.get('job_skill_rows') or []
    groups = {}
    for r in skill_rows:
        if r.get('positions'):
            groups.setdefault((r['track'], r['label']), []).append(r)
    for i, (key, rows) in enumerate(sorted(groups.items(), key=lambda item: (-item[1][0]['positions'], item[0]))[:2]):
        a = max(rows, key=lambda r: r['count'])
        if not described:
            break
        add('track_skills.group_'+str(i), 'track_skills',
            f"{key[1]}方向共 {number(a['positions'])} 条岗位，其中 {a['skill']}被 {number(a['count'])} 条提及，方向内提及率为 {pct(a['count'], a['positions'])}%；分母包含该方向缺少描述的记录。",
            ['/job_skill_rows'], 'comparison', denominator=a['positions'])
    from joint_findings import derive as joint_findings
    out.extend(joint_findings(data))
    return out


def coverage_gaps(data):
    states = {c['section']: c['status'] for c in data.get('coverage', [])}
    return [{'section': s, 'status': states.get(s, 'not_requested')}
            for s in DIMENSIONS if states.get(s) != 'complete']


def evidence_pack(data, binding):
    facts = derive_findings(data)
    groups = list(dict.fromkeys(f['section'] for f in facts if f['section'] != 'overview'))
    from analytical_reasoning import POLICY as reasoning_policy
    external={}
    if binding.get('_report_root'):
        from regional_research import ensure_context
        context=ensure_context(data,binding['_report_root'])
        external={'regionalEvidenceHash':context['evidenceHash'],'regionalCatalogSha256':context['catalogSha256']}
    return {'schema': 'wechat-analysis-evidence/1','writingPolicy':reasoning_policy,**external, 'sourceDataSha256': binding['_data_file_sha256'],
            'sourceContentHash': binding['source']['contentHash'], 'findings': facts,
            'requiredSections': groups, 'coverageGaps': coverage_gaps(data)}


def _narrative(value, field, minimum=20, labels=()):
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= 800:
        raise ValueError(field+'需要具体分析文字，不能为空或只填占位句')
    import unicodedata
    checked = unicodedata.normalize("NFKC",value)
    for label in sorted(labels, key=len, reverse=True):
        checked = checked.replace(unicodedata.normalize('NFKC',label), '')
    if re.search(r'(?:百分之[零〇一二三四五六七八九十百千万亿两点]+|[零〇一二三四五六七八九十百千万亿两点]+(?:年|月|日|个百分点|亿元|万元|千元|条岗位|家企业|个岗位|成(?!果|功|品|立|交|员|本|熟|绩)))',checked):
        raise ValueError(field+'含未绑定的中文数值；测量数据由程序插入')
    if re.search(r'待填写|TODO|填写这里|<[^>]+>|\{[A-Za-z_][A-Za-z0-9_.:-]*\}|\b(?:geography|salary|vocational|tracks|track_skills|jobtype|education|experience|access|skills|lq|track_salary|city_tracks)\.[a-z_0-9.]+', value, re.I) or any(char.isnumeric() for char in checked if not '\u4e00' <= char <= '\u9fff'):
        raise ValueError(field+'含占位、HTML或未绑定数字；数字请选用 findingIds 中的事实')
    from analysis_quality import problems as claim_problems
    issues=claim_problems(value,field,semantic=False)
    if issues:raise ValueError('；'.join(issues))
    return value.strip()


def entity_labels(data):
    """Digits in observed labels (ROS2, 3年以内) are not invented measurements."""
    labels = set()
    for field in ('edu', 'exp', 'jobtype', 'subtrack', 'keywords', 'salary_by_track'):
        labels.update(r['name'] for r in data.get(field, []) if isinstance(r.get('name'), str))
    for field in ('city_track_rows', 'job_skill_rows'):
        for row in data.get(field, []):
            labels.update(row[k] for k in ('city', 'label', 'skill') if isinstance(row.get(k), str))
    labels.update(r[0] for r in data.get('city', []))
    numeric={label for label in labels if len(label) >= 2 and re.search(r'\d', label)}
    for label in list(numeric):
        if re.fullmatch(r'(?:1|3|5|10)年(?:以内|以上)',label):
            for digit,word in [('10','十'),('1','一'),('3','三'),('5','五')]:
                if label.startswith(digit+'年'):numeric.add(word+label[len(digit):])
    return numeric


def validate_analysis(data, binding, analysis):
    if not data['total']['positions']:
        raise ValueError('当前范围无岗位记录，应说明空样本，不能生成研究报告')
    if not isinstance(analysis, dict) or analysis.get('schema') not in (VERSION,'wechat-analysis/2'):
        raise ValueError('缺少已完成的真实数据分析；先运行 report_analysis.py 并撰写 report_analysis.json')
    pack = evidence_pack(data, binding)
    for key in ('sourceDataSha256', 'sourceContentHash'):
        if analysis.get(key) != pack[key]:
            raise ValueError('分析稿绑定了其他数据版本：'+key)
    if analysis.get('evidenceHash') != fingerprint(pack):
        raise ValueError('分析证据已改变，需重新核对分析稿')
    facts = {f['id']: f for f in pack['findings']}
    if analysis.get('reasoningPolicy'):
        from analytical_reasoning import verify as verify_reasoning
        from executive_analysis import default_pairs
        verify_reasoning(data,analysis,{key:default_findings(pack,key) for key in pack['requiredSections']},default_pairs(pack))
    if not any(f['kind'] == 'comparison' for f in facts.values()):
        raise ValueError('现有结果只有规模或单项计数，需补充比较或交叉统计后再分析')
    labels = entity_labels(data)
    problems=[]

    def narrative(value, field, minimum=20):
        try:
            checked=_narrative(value, field, minimum, labels)
            if analysis.get('schema')=='wechat-analysis/2':
                from analysis_quality import problems as quality_problems
                problems.extend(quality_problems(checked,field))
            return checked
        except ValueError as exc:
            problems.append(str(exc));return ''

    def selected(item, section=None, minimum=2):
        ids = item.get('findingIds', [])
        allowed = [f for f in facts.values() if section is None or f['section'] == section]
        if not isinstance(ids, list) or any(not isinstance(x, str) for x in ids) or len(set(ids)) != len(ids):
            raise ValueError('分析事实引用须为不重复的 findingIds')
        maximum=12 if section is None and analysis.get('schema')=='wechat-analysis/2' else 5
        if not min(minimum, len(allowed)) <= len(ids) <= maximum or any(x not in facts for x in ids):
            raise ValueError('分析需要相关事实与比较证据，且不能引用不存在的事实')
        if section and any(facts[x]['section'] != section for x in ids):
            raise ValueError('章节引用了其他主题的事实')
        if section and any(f['kind'] == 'comparison' for f in allowed) and not any(facts[x]['kind'] == 'comparison' for x in ids):
            raise ValueError('章节需要使用已有的比较或交叉分析：'+section)

    executive = analysis.get('executive', {})
    selected(executive, minimum=3)
    domains = {f['section'] for f in facts.values()}
    if len({facts[x]['section'] for x in executive['findingIds']}) < min(3, len(domains)):
        raise ValueError('综合判断需结合不同维度，不能只罗列同一主题的事实')
    if analysis.get('schema')=='wechat-analysis/2':
        from executive_analysis import validate as validate_executive
        try:validate_executive(executive,facts,narrative)
        except ValueError as exc:problems.append(str(exc))
    else:narrative(executive.get('synthesis'), '跨维度综合判断', 40)
    insights = analysis.get('sections', [])
    if not isinstance(insights, list) or any(not isinstance(s, dict) for s in insights):
        raise ValueError('sections 必须为分析章节列表')
    keys = [s.get('key') for s in insights]
    if len(set(keys)) != len(keys) or set(keys) != set(pack['requiredSections']):
        missing=set(pack['requiredSections'])-set(keys)
        extra=set(keys)-set(pack['requiredSections'])
        raise ValueError('分析章节不完整；缺少：'+', '.join(sorted(missing))+'；多余：'+', '.join(sorted(extra)))
    seen = set()
    for s in insights:
        from editorial_projects import alignment_problems
        problems.extend(alignment_problems(data,s))
        selected(s, s['key'])
        narrative(s.get('title'), '结论式标题', 4)
        if isinstance(s.get('title'),str) and len(s['title']) > 40:
            problems.append(s['key']+'结论式标题过长，请压缩为可读的页面标题')
        for field in ('interpretation', 'action', 'validation'):
            minimum={'interpretation':40,'action':30,'validation':30}[field] if analysis.get('schema')=='wechat-analysis/2' else 20
            value = narrative(s.get(field), s['key']+'.'+field,minimum)
            normalized = re.sub(r'\W', '', value)
            if normalized and normalized in seen:
                problems.append(s['key']+'不同章节不能复用同一句分析或建议')
            seen.add(normalized)
        if analysis.get('schema')=='wechat-analysis/2':
            narrative(s.get('decisionRule'),s['key']+'.decisionRule',30)
    limitations = analysis.get('limitations')
    if not isinstance(limitations, list) or not limitations:
        raise ValueError('分析需列明准确的统计对象与适用范围')
    for text in limitations:
        narrative(text, '研究边界')
    if analysis.get('coverageGaps') != pack['coverageGaps']:
        problems.append('coverageGaps应原样保留：'+json.dumps(pack['coverageGaps'],ensure_ascii=False))
    if problems:raise ValueError('分析稿需一次性修正以下项目：\n- '+'\n- '.join(problems))
    return pack


def default_findings(pack,key=None):
    """A compact starting selection, always including comparison evidence if present."""
    rows=[f for f in pack['findings'] if key is None or f['section']==key]
    preferred={'geography':['geography.joint_contrast','geography.entry_coverage_0'],
        'jobtype':['jobtype.leading','jobtype.entry_definition'],
        'education':['education.leading','education.experience_contrast'],
        'experience':['experience.leading','experience.education_contrast'],
        'tracks':['tracks.coverage','tracks.classified_leaders'],
        'salary':['salary.quantiles','salary.entry_upper_bound'],
        'track_salary':['track_salary.qualified_extremes','track_salary.entry_tradeoff'],
        'vocational':['vocational.size','vocational.track_tradeoff'],
        'city_tracks':['city_tracks.classified_city_0','city_tracks.classified_city_1'],
        'lq':['lq.specialized_city_0','lq.specialized_city_1'],
        'track_skills':['track_skills.conditional_contrast','track_skills.description_coverage']}
    if key in preferred:
        available={f['id'] for f in rows};choice=[fid for fid in preferred[key] if fid in available]
        if len(choice)>=2:return choice[:4]
    selected=[]
    if key is None:
        domains=set()
        for fact in rows:
            if fact['section'] not in domains and fact['kind']=='comparison':
                selected.append(fact['id']);domains.add(fact['section'])
            if len(selected)>=4:break
    else:
        if rows:selected.append(rows[0]['id'])
        comparison=next((f['id'] for f in rows if f['kind']=='comparison' and f['id'] not in selected),None)
        if comparison:selected.append(comparison)
        elif len(rows)>1:selected.append(rows[1]['id'])
    return selected


def assemble_analysis(data,binding,writing):
    pack=evidence_pack(data,binding)
    if writing.get('schema') not in ('wechat-analysis-writing/1','wechat-analysis-writing/2') or writing.get('evidenceHash')!=fingerprint(pack):
        raise ValueError('分析文案须来自本次writing_draft并保留evidenceHash')
    if writing.get('reasoningPolicy'):
        from analytical_reasoning import normalize
        from executive_analysis import default_pairs
        writing=normalize(data,writing,{key:default_findings(pack,key) for key in pack['requiredSections']},default_pairs(pack))
    result={key:pack[key] for key in ('sourceDataSha256','sourceContentHash')}
    deep=writing.get('schema')=='wechat-analysis-writing/2'
    result.update(schema='wechat-analysis/2' if deep else VERSION,evidenceHash=fingerprint(pack),coverageGaps=pack['coverageGaps'],
                  executive=writing.get('executive',{}),sections=writing.get('sections',[]),limitations=writing.get('limitations',[]))
    if writing.get('reasoningPolicy'):result['reasoningPolicy']=writing['reasoningPolicy']
    if writing.get('editorialRepairs'):result['editorialRepairs']=writing['editorialRepairs']
    result['executive']=dict(result['executive'])
    if deep:result['executive']['findingIds']=list(dict.fromkeys(fid for claim in result['executive'].get('claims',[]) for fid in claim.get('findingIds',[])))
    result['executive'].setdefault('findingIds',default_findings(pack))
    result['sections']=[dict(section,findingIds=section.get('findingIds',default_findings(pack,section.get('key')))) for section in result['sections']]
    validate_analysis(data,binding,result)
    return result


def finding_spec(fact, binding):
    inputs = {str(i): {'path': path} for i, path in enumerate(fact['paths'])}
    ids = []
    for path in fact['paths']:
        matches = [key for key in binding['fields'] if path == key or path.startswith(key+'/')]
        if not matches:
            raise ValueError('分析事实缺少源字段绑定：'+path)
        ids += binding['fields'][max(matches, key=len)]
    return dict(path='', op='finding', findingId=fact['id'], inputs=inputs, metricIds=sorted(set(ids)))


def analysis_payload(item, facts, executive=False, data=None):
    if data is not None:
        from editorial_prose import paragraphs
        return paragraphs(data,item,facts,executive)
    if executive and item.get('claims'):
        from executive_analysis import payload
        ps,summary,_=payload(item,facts)
        return ps,summary
    paragraphs = [facts[x]['text'] for x in item['findingIds']]
    if executive:
        paragraphs.append('综合分析：'+item['synthesis'])
        return paragraphs, None
    paragraphs += ['结构解读与分析推断：'+item['interpretation'], '行动建议：'+item['action']]
    verification=item['validation']
    if item.get('decisionRule'):verification+=' 调整条件：'+item['decisionRule']
    return paragraphs, {'title': '落实与验证', 'text': verification}


def apply_analysis(outline, data, binding, analysis):
    pack = validate_analysis(data, binding, analysis)
    facts = {f['id']: f for f in pack['findings']}
    insight = {s['key']: s for s in analysis['sections']}
    title_keys = {'招聘地域分布': 'geography', '招聘类型': 'jobtype', '学历要求': 'education',
                  '经验要求': 'experience', '学历与经验交叉': 'access', '薪酬结构': 'salary',
                  '岗位方向结构': 'tracks', '方向薪酬比较': 'track_salary',
                  '城市与岗位方向': 'city_tracks', '地域方向集中程度': 'lq',
                  '人才能力关键词': 'skills', '方向与技能组合': 'track_skills',
                  '职教入门岗位观察': 'vocational'}
    refs = outline['bindings']
    modern=analysis.get('reasoningPolicy')=='wechat-analytic-reasoning/2'
    for path in list(refs):
        if '/paragraphs/' in path:
            del refs[path]
    outline['analysis'] = analysis
    outline['schema'] = 'wechat-outline/3'
    for i, screen in enumerate(outline['screens']):
        title = screen['title']
        key = 'overview' if title == '核心发现' else title_keys.get(title)
        if key:
            item = analysis['executive'] if key == 'overview' else insight[key]
            screen['analysis_key'] = key
            if key != 'overview':
                screen['title'] = item['title']
            screen['paragraphs'], summary = analysis_payload(item, facts, key == 'overview', data if modern else None)
            screen.pop('summary', None)
            if summary:
                screen['summary'] = summary
            fact_indices=dict(enumerate(item['findingIds']))
            if modern:
                from editorial_prose import POLICY as EDITORIAL_POLICY,spec
                screen['editorialPolicy']=EDITORIAL_POLICY
                if key=='overview':
                    screen['title']='摘要与核心结论'
                    screen['executive_structure']='summary-integrated-points'
                    refs[f'/screens/{i}/paragraphs/0']=spec(data,item,'summary',binding)
                    for j in range(3):refs[f'/screens/{i}/paragraphs/{j+1}']=spec(data,item,'core',binding,j)
                else:refs[f'/screens/{i}/paragraphs/0']=spec(data,item,'section',binding)
                continue
            if key=='overview' and item.get('claims'):
                from executive_analysis import payload
                _,_,fact_indices=payload(item,facts)
                screen['executive_structure']='total-parts-total'
            for j, fact_id in fact_indices.items():
                refs[f'/screens/{i}/paragraphs/{j}'] = finding_spec(facts[fact_id], binding)
        elif title.startswith('人才培养与合作建议'):
            screen['analysis_key'] = 'recommendations'
            if modern:
                screen['title']='人才培养与合作路径'
                screen['paragraphs']=[analysis['executive']['closing']]
                continue
            start=screen.get('recommendation_start',0)
            stop=screen.get('recommendation_stop',len(analysis['sections']))
            screen['paragraphs'] = [LABELS[s['key']]+'：'+s['action'] for s in analysis['sections'][start:stop]]
        elif screen['type'] == 'notes':
            screen['blocks'] = [b for b in screen['blocks'] if b[0] != '未覆盖项']
            gaps = '；'.join(LABELS.get(g['section'], '学历与经验要求')+'：'+STATUS_LABELS.get(g['status'], g['status'])
                            for g in pack['coverageGaps'])
            screen['blocks'] += [('适用范围', '；'.join(text.rstrip('。；') for text in analysis['limitations']))]
            if gaps:screen['blocks'].append(('统计范围',gaps))
    if modern:
        kept=[];recommendation=False
        for old_index,screen in enumerate(outline['screens']):
            if screen.get('analysis_key')=='recommendations':
                if recommendation:continue
                recommendation=True
            kept.append(old_index)
        indices={old:new for new,old in enumerate(kept)}
        outline['screens']=[outline['screens'][old] for old in kept]
        rebound={}
        for path,specification in refs.items():
            match=re.match(r'^/screens/(\d+)(/.*)$',path)
            if match:
                old=int(match.group(1))
                if old not in indices:continue
                path='/screens/'+str(indices[old])+match.group(2)
            rebound[path]=specification
        outline['bindings']=rebound
        from editorial_prose import POLICY as EDITORIAL_POLICY
        outline['editorialPolicy']=EDITORIAL_POLICY
        from readable_layout import compact
        from article_content import build_lead
        compact(outline,data,binding)
        outline['articleLead']=build_lead(data,analysis)
    return outline


def verify_analysis_outline(data, binding, outline):
    if outline.get('schema') != 'wechat-outline/3':
        raise ValueError('旧大纲需先完成真实分析，再生成 wechat-outline/3 报告')
    analysis = outline.get('analysis')
    pack = validate_analysis(data, binding, analysis)
    facts = {f['id']: f for f in pack['findings']}
    items = {s['key']: s for s in analysis['sections']}
    items['overview'] = analysis['executive']
    seen = []
    recommendations=[]
    modern=analysis.get('reasoningPolicy')=='wechat-analytic-reasoning/2'
    for i, screen in enumerate(outline['screens']):
        key = screen.get('analysis_key')
        if screen.get('analysis_keys'):
            from readable_layout import merged_expected,PAIRS
            ps,summary=merged_expected(screen,items,facts,data)
            keys=screen['analysis_keys'];seen.extend(keys)
            if screen.get('paragraphs')!=ps or screen.get('summary')!=summary or screen['title']!=PAIRS[keys[0]][1]:raise ValueError('合并章节丢失或改写了分析正文')
            from editorial_prose import spec
            for j,section_key in enumerate(keys):
                if outline['bindings'].get(f'/screens/{i}/paragraphs/{j}')!=(spec(data,items[section_key],'section',binding) if j==0 else spec(data,items[section_key],'section-distinct',binding,items[keys[0]])):raise ValueError('合并章节绑定不一致')
            continue
        if key in items:
            seen.append(key)
            item = items[key]
            ps, summary = analysis_payload(item, facts, key == 'overview',data if modern else None)
            if screen.get('paragraphs') != ps or screen.get('summary') != summary:
                raise ValueError('报告未完整保留分析正文：'+key)
            if key != 'overview' and screen['title'] != item['title']:
                raise ValueError('报告标题与分析稿不一致')
            fact_indices=dict(enumerate(item['findingIds']))
            if modern:
                from editorial_prose import spec
                expected={0:spec(data,item,'summary',binding)} if key=='overview' else {0:spec(data,item,'section',binding)}
                if key=='overview':expected.update({j+1:spec(data,item,'core',binding,j) for j in range(3)})
                for j,expected_spec in expected.items():
                    if outline['bindings'].get(f'/screens/{i}/paragraphs/{j}')!=expected_spec:raise ValueError('融合正文与数据绑定不一致')
                continue
            if key=='overview' and item.get('claims'):
                from executive_analysis import payload
                _,_,fact_indices=payload(item,facts)
            for j, fid in fact_indices.items():
                if outline['bindings'].get(f'/screens/{i}/paragraphs/{j}') != finding_spec(facts[fid], binding):
                    raise ValueError('分析事实引用与统计对象不一致')
        elif key == 'recommendations':
            start=screen.get('recommendation_start',0)
            stop=screen.get('recommendation_stop',len(analysis['sections']))
            ps = [analysis['executive']['closing']] if modern else [LABELS[s['key']]+'：'+s['action'] for s in analysis['sections'][start:stop]]
            if screen.get('paragraphs') != ps:
                raise ValueError('报告缺少已分析的行动建议')
            recommendations.extend(ps)
    expected_recommendations=[analysis['executive']['closing']] if modern else [LABELS[s['key']]+'：'+s['action'] for s in analysis['sections']]
    if sorted(seen) != sorted(items) or recommendations!=expected_recommendations:
        raise ValueError('报告缺少分析章节，不能只交付统计骨架')
    if modern:
        from editorial_prose import content_audit
        from article_content import build_lead
        from readable_layout import POLICY as LAYOUT_POLICY
        if outline.get('readableLayout')!=LAYOUT_POLICY or outline.get('articleLead')!=build_lead(data,analysis):raise ValueError('精简结构或公众号导语与证据不一致')
        content_audit(outline)


def main():
    from bound_report import load_data
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=str(BASE/'report_data.json'))
    ap.add_argument('--out', default=str(BASE/'output/analysis'))
    ap.add_argument('--assemble',help='合并智能体文案与受信元数据，校验后写report_analysis.json')
    ap.add_argument('--analysis-out',default=str(BASE/'report_analysis.json'))
    args = ap.parse_args()
    data, binding = load_data(args.data)
    if args.assemble:
        result=assemble_analysis(data,binding,json.loads(Path(args.assemble).read_text('utf-8')))
        Path(args.analysis_out).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
        print(json.dumps({'status':'analysis_ready','analysis':args.analysis_out},ensure_ascii=False))
        return
    pack = evidence_pack(data, binding)
    if not data['total']['positions']:
        raise ValueError('当前范围无岗位记录，请反馈空样本，不生成研究报告')
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out/'analysis_evidence.json').write_text(json.dumps(pack, ensure_ascii=False, indent=2), 'utf-8')
    lines = ['# 数据分析证据', '', '以下是可复核事实，尚未完成解释与建议。请读完整数据后撰写 report_analysis.json。', '']
    for f in pack['findings']:
        lines += ['## '+f['id'], f['text'], '输入字段：'+', '.join(f['paths']), '']
    lines += ['## 未覆盖维度', json.dumps(pack['coverageGaps'], ensure_ascii=False)]
    (out/'analysis_evidence.md').write_text('\n'.join(lines), 'utf-8')
    brief=['# 本次写作简报','',
           '真实事实已由程序计算。先完成下面全部章节的解释、行动、验证，再连续生成图片。不要复制整份分析证据或手工填写来源指纹。',
           '从writing_draft.json复制结构，保留evidenceHash与全部章节key；默认事实已包含比较，可选择证据中的其他同主题findingIds。',
           '解释只回答本样本意味着什么，不能虚构产业原因、学校层次或市场趋势；没有独立证据的因果机制不进入成品结论。文字内不重复测量数字；量化事实由findingIds插入。',
           '每章title控制在简短结论；interpretation/action/validation各写具体内容，避免反复免责声明和通用口号。',
           '文案完成后调用report_analysis.py --assemble report_writing.json；程序补来源与覆盖字段、一次性列出文案错误。通过后调用generate_report.py --workspace ..。','']
    facts={f['id']:f for f in pack['findings']}
    for key in pack['requiredSections']:
        brief += ['## '+key+' · '+LABELS[key]]
        brief += [f"- {fid}: {facts[fid]['text']}" for fid in default_findings(pack,key)]
    brief += ['','## 数据覆盖缺口',json.dumps(pack['coverageGaps'],ensure_ascii=False)]
    (out/'analysis_brief.md').write_text('\n'.join(brief),'utf-8')
    draft = dict(schema=VERSION, sourceDataSha256=pack['sourceDataSha256'],
                 sourceContentHash=pack['sourceContentHash'], evidenceHash=fingerprint(pack),
                 executive={'findingIds': default_findings(pack), 'synthesis': ''},
                 sections=[dict(key=key, title='', findingIds=default_findings(pack,key), interpretation='', action='', validation='')
                           for key in pack['requiredSections']],
                 limitations=[], coverageGaps=pack['coverageGaps'])
    # Never overwrite an agent's existing analysis with an empty scaffold.
    (out/'analysis_draft.json').write_text(json.dumps(draft, ensure_ascii=False, indent=2), 'utf-8')
    writing={key:draft[key] for key in ('evidenceHash','executive','sections','limitations')}
    writing['schema']='wechat-analysis-writing/1'
    if 'city_profiles' in data:
        writing['schema']='wechat-analysis-writing/2'
        for section in writing['sections']:section['decisionRule']=''
        known={f['id']:f for f in pack['findings']}
        from executive_analysis import default_pairs
        pairs=default_pairs(pack)
        writing['executive']={'opening':'','claims':[{'title':'','findingIds':ids,'interpretation':'','implication':''} for ids in pairs],'closing':''}
        from analytical_reasoning import normalize
        writing=normalize(data,writing,{key:default_findings(pack,key) for key in pack['requiredSections']},pairs)
        brief_path=out/'analysis_brief.md'
        brief_path.write_text(brief_path.read_text('utf-8')+'\n\n## 摘要与融合式核心结论\n先写一段摘要，再完成三条claims，每条在同一段内融合数据、解释和决策，不分列分析或论证标签。closing放到最后合作路径页面。findingIds由--assemble汇总，不能把核心发现写成统计清单。各章还必须写decisionRule：不同任务准备度与岗位条件下如何组织课程和实践，不能只写一句免责声明。\n不要从城市学历份额推测企业更重视知识、不要把未分类率归因于产业命名灵活、不要从单次快照判断稳定需求或人才短缺。比较意义应落到名单怎么筛、课程任务怎么拆、薪酬预期怎么校准；可能机制须作为假设并说明替代解释。\n下面为每条分结论默认事实，需先核对再写解释：\n'+'\n'.join(f"- {fid}: {known[fid]['text']}" for ids in pairs for fid in ids),'utf-8')
    (out/'writing_draft.json').write_text(json.dumps(writing,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({'status': 'analysis_required', 'brief':str(out/'analysis_brief.md'),
                      'evidence': str(out/'analysis_evidence.md'),'draft':str(out/'writing_draft.json'),
                      'next': '读简报与统计后完成report_writing.json，--assemble合并校验，直接生成图片'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
