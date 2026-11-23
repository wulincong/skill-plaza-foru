#!/usr/bin/env python3
"""Validate training-program contracts, check hour/credit redlines, build deliverables."""
import argparse
import csv
import datetime
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUERY = ROOT.parent / 'talent-data-query/scripts/query.mjs'
RESULT_PATH = re.compile(r'data/(tq-[a-f0-9-]+)/result\.json')
# 本地培养方案语料库（仓库 data/，不进 git；见 references/local-corpus.md）
CORPUS_DIR = ROOT.parents[2] / 'data' / '人才培养方案'
CORPUS_SNAPSHOT = '2026-11-20'
_corpus_rows = None


def corpus_index():
    global _corpus_rows
    if _corpus_rows is None:
        _corpus_rows = {}
        path = CORPUS_DIR / '索引.csv'
        if path.is_file():
            with open(path, encoding='utf-8-sig') as fh:
                for row in csv.DictReader(fh):
                    if row.get('相对路径'):
                        _corpus_rows[row['相对路径']] = row
    return _corpus_rows

CATEGORIES = ('public-required', 'public-elective', 'professional-base', 'professional-core',
              'professional-extension', 'internship', 'comprehensive-practice')
PUBLIC_CATEGORIES = {'public-required', 'public-elective'}
ELECTIVE_CATEGORIES = {'public-elective', 'professional-extension'}
PROFESSIONAL_CATEGORIES = {'professional-base', 'professional-core', 'professional-extension'}
ALL_PRACTICE_CATEGORIES = {'internship', 'comprehensive-practice'}

DEFAULTS = {
    'totalHoursMin': 2500, 'totalHoursMax': 2800,
    'practiceRatioMin': 0.50,
    'publicRatioMin': 0.25,
    'electiveRatioMin': 0.10,
    'coreCoursesMin': 6, 'coreCoursesMax': 8,
    'internshipWeeksMin': 20, 'internshipWeeksMax': 30,
    'weeksPerYear': 40,
    'creditsMin': 120, 'creditsMax': 170,
    'hoursPerCreditMin': 16, 'hoursPerCreditMax': 18,
    'creditTolerance': 2,
}
OVERRIDE_KEYS = set(DEFAULTS) - {'creditTolerance'}

STANDARD_ELEMENTS = ('概述', '专业名称', '入学基本要求', '基本修业年限', '职业面向', '培养目标',
                     '培养规格', '课程设置及学时安排', '师资队伍', '教学条件', '质量保障', '毕业要求')
CATEGORY_NAMES = {
    'public-required': '公共基础必修', 'public-elective': '公共选修',
    'professional-base': '专业基础', 'professional-core': '专业核心',
    'professional-extension': '专业拓展', 'internship': '岗位实习',
    'comprehensive-practice': '综合实践',
}


def excerpt_text(value):
    # Chinese typography often adds spaces around numbers. Preserve digits,
    # punctuation and word boundaries (e.g. "1 8" must not become "18").
    text = ' '.join(str(value).split())
    return re.sub(r'(?<=[\u3400-\u9fff]) (?=[0-9])|(?<=[0-9]) (?=[\u3400-\u9fff])', '', text)


def session_context():
    file = Path('program-input.json')
    return json.loads(file.read_text(encoding='utf-8')) if file.is_file() else None


def inspect_source(source):
    """Use the shared skill's offline reader; it owns file and content verification."""
    match = RESULT_PATH.fullmatch(source['url'])
    if not match:
        raise ValueError('invalid talent result path')
    proc = subprocess.run(['node', str(QUERY), 'inspect', '--result', source['url'], '--full'],
                          capture_output=True, text=True, check=False)
    if proc.returncode:
        raise ValueError('shared inspect failed: ' + proc.stdout.strip()[:400])
    result = json.loads(proc.stdout)
    read_at = result['freshness']['dataReadAt']
    if (result['requestId'] != match[1] or result['contentHash'] != source.setdefault('contentHash', result['contentHash'])
            or read_at != source.setdefault('dataReadAt', read_at)):
        raise ValueError('query identity, content hash or read time mismatch')
    checks = result['quality']['checks']
    if (result['status'] not in ('complete', 'empty', 'partial') or not checks
            or not all(item['pass'] for item in checks) or not result['consistency']['completeTransaction']):
        raise ValueError('query failed consistency checks')
    source.setdefault('published', '未标注')
    source.setdefault('accessed', read_at[:10])
    return result


def distribution_detail(metric):
    groups = []
    rows = metric['rows']
    for i, row in enumerate(rows[:20]):
        labels = row.get('labels', {}).values()
        label = ' / '.join(str(v or '缺失') for v in labels) or row.get('label') or row.get('category')
        if not label or 'count' not in row or 'share' not in row:
            return None
        groups.append({'row': i, 'label': label, 'count': row['count'], 'share': row['share']})
    return {'denominator': metric['denominator'], 'returnedGroups': len(rows), 'groups': groups}


def bind_observation(result, observation):
    binding = observation['binding']
    metrics = {item['metricId']: item for item in result['metrics']}
    metric = metrics[binding['metricId']]
    if metric['status'] != 'complete' and not (
            metric['status'] == 'empty' and metric['name'] in ('positions.count', 'companies.count')):
        raise ValueError('metric unavailable')
    field = binding['field']
    detail = None
    if field in ('rows', 'denominator') and metric.get('rows'):
        detail = distribution_detail(metric)
    if detail is not None:
        observation.setdefault('breakdown', detail)
        field = 'denominator'
    elif 'breakdown' in observation or field == 'rows':
        raise ValueError('该指标不含可展示的分组计数，请绑定具体行的数值字段')
    path = field.split('.')
    if path[0] not in ('value', 'rows', 'denominator', 'validN', 'missingN', 'excludedN', 'otherCount'):
        raise ValueError('invalid metric field')
    value = metric
    for key in path:
        if isinstance(value, list):
            if not key.isdecimal():
                raise ValueError('invalid row index')
            value = value[int(key)]
        else:
            value = value[key]
    if type(value) not in (int, float):
        raise ValueError('需要数值字段，如 value.median 或 rows.0.count；每个要引用的分组建一项指标')
    return value


def text_len(value):
    """有效字数：去空白后的字符数（中文方案的信息密度口径）。"""
    return len(re.sub(r'\s', '', str(value or '')))


def fmt_num(value):
    """数值显示口径：整数加千分位，浮点去尾零；缺失显示 —。"""
    if isinstance(value, bool) or value is None:
        return '—'
    if isinstance(value, int):
        return f'{value:,}'
    if isinstance(value, float):
        return f'{value:g}'


def display_title(title):
    """标题显示口径：去掉文件名残留的扩展名、开头的批次序号与收尾标点。
    如「5-2025级…方案.pdf.」→「2025级…方案」。"""
    text = str(title or '').strip()
    text = re.sub(r'\.(pdf|docx?|txt)$', '', text.rstrip('.。．、 '), flags=re.I).rstrip('.。．、 ')
    text = re.sub(r'^\d{1,3}-', '', text).strip()
    return text or str(title or '').strip()


def metric_link_text(m):
    """指标链接文字（短名称）：名称 数值 单位。地域与时期在所在表格/段落说明一次，
    完整口径在附录 A.2 落点条目——不把长后缀塞进每条链接。"""
    head = f"{m['label']} {fmt_num(m.get('value'))}"
    if m.get('unit'):
        head += f" {m['unit']}"
    return head


def source_ref_text(s):
    """来源链接文字（短名称）：只写标题；定位与出处留在附录条目。"""
    return display_title(s['title'])


def scope_note(index, ids):
    """依据口径说明：引用的指标地域/时期一致时生成一句括注（表内/段内说明一次）。"""
    metrics = [index[i] for i in ids if i in index]
    if not metrics:
        return ''
    regions = {str(m.get('region') or '').strip() for m in metrics} - {''}
    dates = {m.group(0) for m in (re.search(r'\d{4}-\d{2}-\d{2}', str(x.get('period') or ''))
                                  for x in metrics) if m}
    parts = []
    if len(regions) == 1:
        parts.append(next(iter(regions)) + '口径')
    if len(dates) == 1:
        parts.append('查询时点 ' + next(iter(dates)))
    return f"（{'，'.join(parts)}）" if parts else ''


def md_link(text, anchor):
    return f'[{text}](#{anchor})'


# 内容深度下限（对照本地语料同类方案校准；不足即阻断构建）
DEPTH = {
    'courseDescription': 20,     # 每门课程简介
    'coreDescription': 40,       # 专业核心课简介
    'courseContent': 30,         # 每门课典型教学内容/工作任务
    'coreContent': 80,           # 专业核心课典型内容
    'specItems': 5,              # 培养规格每维度条数
    'specItemChars': 12,         # 规格条目字数
    'pedagogy': 150,             # 教学实施 / 考核评价
    'graduationItems': 4,        # 毕业要求条数
    'graduationChars': 80,       # 毕业要求总字数
    'corpusRefs': 3,             # 对标语料份数下限
}

# 图表规划（chartPlan）：先定图、再取数。kind 取 chart-visualization figure/1 可执行集
# （figure_data.ROLES）；专题图（雷达/桑基/堆叠柱等）尚不可执行出图，不入选型。
FIGURE_KINDS = {'bar', 'barh', 'line', 'grouped-line', 'faceted-line', 'province-map', 'scatter',
                'distribution', 'histogram', 'ecdf', 'paired', 'change-distribution',
                'median-change', 'interval', 'matrix'}
# 图型家族判定口径：条形家族（竖柱、横条、分组/多面板柱条）算一种；其余按分析关系各算一种。
CHART_FAMILY = {
    'bar': '条形', 'barh': '条形',
    'line': '折线', 'grouped-line': '折线', 'faceted-line': '折线',
    'province-map': '地图', 'scatter': '散点',
    'distribution': '分布', 'histogram': '分布', 'ecdf': '分布',
    'paired': '配对', 'change-distribution': '配对', 'median-change': '配对',
    'interval': '区间', 'matrix': '矩阵',
}
CHART_MIN_FAMILIES = 3   # 全页至少 3 种不同图型家族（规划与成品两处分别校验）
# 页面锚点/图稿 id 通用格式（report-rendering claim_id 口径）
ANCHOR_ID = re.compile(r'[A-Za-z][A-Za-z0-9_-]*')


def chart_summary(d):
    """图表规划审计摘要：家族清单、家族数、条形占比（写入 validation.json）。"""
    plan = [e for e in (d.get('chartPlan') or []) if isinstance(e, dict) and e.get('kind') in CHART_FAMILY]
    families = [CHART_FAMILY[e['kind']] for e in plan]
    bar = sum(1 for f in families if f == '条形')
    return {'planned': [{'id': e.get('id'), 'kind': e.get('kind'), 'family': CHART_FAMILY[e['kind']],
                         'section': e.get('section'), 'dataOrigin': e.get('dataOrigin')} for e in plan],
            'families': sorted(set(families)), 'familyCount': len(set(families)),
            'barShare': f'{bar}/{len(plan)}'}


def compute_hours(d):
    courses = d['curriculum']['courses']
    total = sum(c['theoryHours'] + c['practiceHours'] for c in courses)
    practice = sum(c['theoryHours'] + c['practiceHours'] if c['category'] in ALL_PRACTICE_CATEGORIES
                   else c['practiceHours'] for c in courses)
    public = sum(c['theoryHours'] + c['practiceHours'] for c in courses if c['category'] in PUBLIC_CATEGORIES)
    elective = sum(c['theoryHours'] + c['practiceHours'] for c in courses if c['category'] in ELECTIVE_CATEGORIES)
    credits = sum(c['credits'] for c in courses)
    core = [c for c in courses if c['category'] == 'professional-core']
    by_category = {}
    for c in courses:
        item = by_category.setdefault(c['category'], {'courses': 0, 'hours': 0, 'credits': 0.0})
        item['courses'] += 1
        item['hours'] += c['theoryHours'] + c['practiceHours']
        item['credits'] += c['credits']
    return {'totalHours': total, 'practiceHours': practice, 'publicHours': public,
            'electiveHours': elective, 'totalCredits': round(credits, 1), 'coreCourses': len(core),
            'practiceRatio': practice / total if total else 0.0,
            'publicRatio': public / total if total else 0.0,
            'electiveRatio': elective / total if total else 0.0,
            'byCategory': {k: {'courses': v['courses'], 'hours': v['hours'],
                               'credits': round(v['credits'], 1)} for k, v in by_category.items()}}


def redline_values(d):
    values = dict(DEFAULTS)
    overrides = d.get('redlineOverrides') or {}
    for key, value in (overrides.get('values') or {}).items():
        if key in OVERRIDE_KEYS:
            values[key] = value
    return values


def validate(d):
    errors = []
    warnings = []
    context = session_context()

    def check(ok, message):
        if not ok:
            errors.append(message)

    def warn(ok, message):
        if not ok:
            warnings.append(message)

    def fields(obj, names, label):
        for name in names:
            check(name in obj and obj[name] not in ('', None, []) and
                  (not isinstance(obj[name], str) or bool(obj[name].strip())), f'{label}: missing {name}')

    def resolvable(ids, group, index):
        for key in ids if isinstance(ids, list) else []:
            check(isinstance(key, str) and key in index[group], f'unresolved {group} reference {key}')

    fields(d, ['schema', 'title', 'status', 'as_of', 'meta', 'sources', 'metrics', 'jobGroups',
               'capabilityDomains', 'standards', 'curriculum', 'schedule', 'assurance',
               'graduation', 'cultivation', 'pedagogy', 'chartPlan'], 'program')
    check(isinstance(d.get('decisions'), list), 'decisions must be array')
    check(d.get('schema') == 'training-program/1', 'invalid schema')
    check(d.get('status') in ('draft', 'final'), 'invalid status')
    try:
        datetime.date.fromisoformat(d.get('as_of', ''))
    except (ValueError, TypeError):
        errors.append('invalid as_of')

    meta = d.get('meta') or {}
    fields(meta, ['majorName', 'majorCode', 'level', 'region', 'industries', 'version'], 'meta')
    check(isinstance(meta.get('majorCode'), str) and re.fullmatch(r'\d{6}', meta.get('majorCode', '')),
          'majorCode must be 6 digits')
    duration = meta.get('duration') or {}
    years = duration.get('years')
    check(isinstance(years, int) and 2 <= years <= 5, 'invalid duration.years')
    based = meta.get('basedOnStandard') or {}
    check(based.get('status') in ('verified', 'pending'), 'invalid basedOnStandard.status')

    # sources & metrics（与产教报告同构：共享统计经 inspect 核验，用户材料核 excerpt）
    index = {'sources': {}, 'metrics': {}}
    for group in ('sources', 'metrics'):
        items = d.get(group)
        check(isinstance(items, list), f'{group} must be array')
        for obj in items if isinstance(items, list) else []:
            check(isinstance(obj, dict) and isinstance(obj.get('id'), str) and bool(obj.get('id')),
                  f'{group}: invalid id')
            # id 前缀约定：来源 S*、指标 M*——成品校验按前缀区分链接文字上限
            prefix = 'S' if group == 'sources' else 'M'
            check(isinstance(obj.get('id'), str) and bool(ANCHOR_ID.fullmatch(obj.get('id') or '')),
                  f'{group}: id 须字母开头、仅含字母数字-_（正文依据要链接到附录锚点）：{obj.get("id")}')
            check(isinstance(obj.get('id'), str) and obj['id'].startswith(prefix),
                  f'{group}: id 须以 {prefix} 开头（S*/M*，能力项 C*）：{obj.get("id")}')
            check(obj.get('id') not in index[group], f'{group}: duplicate {obj.get("id")}')
            if isinstance(obj, dict) and isinstance(obj.get('id'), str):
                index[group][obj['id']] = obj
    shared = {}
    for s in index['sources'].values():
        url = s.get('url', '')
        if isinstance(url, str) and url.startswith('corpus:'):
            # 本地培养方案语料：索引登记 + sha256 复核 + excerpt 摘录原文核对
            rel = url[len('corpus:'):]
            entry = corpus_index().get('人才培养方案/' + rel)
            file = CORPUS_DIR / rel
            if not s.get('publisher'):
                s['publisher'] = '本地培养方案语料库（对标参考）'
            if not s.get('published'):
                s['published'] = '未标注'
            if not s.get('accessed'):
                s['accessed'] = CORPUS_SNAPSHOT
            if entry is None:
                errors.append(f'{s["id"]}: corpus 索引中无此条目，请按 索引.csv 的相对路径（去目录前缀）填写：{rel}')
            elif not file.is_file():
                errors.append(f'{s["id"]}: corpus 文件缺失 {rel}')
            else:
                if hashlib.sha256(file.read_bytes()).hexdigest() != entry.get('sha256'):
                    errors.append(f'{s["id"]}: corpus 文件 sha256 与索引不符')
                excerpt = excerpt_text(s.get('excerpt', ''))
                if not (excerpt and excerpt in excerpt_text(file.read_text(encoding='utf-8', errors='replace'))):
                    errors.append(f'{s["id"]}: excerpt 须摘录语料原文')
                if not s.get('title'):
                    s['title'] = display_title(entry.get('标题') or entry.get('文件名', ''))
        elif isinstance(url, str) and url.startswith('data/'):
            try:
                result = inspect_source(s)
                shared[s['id']] = result
                check(datetime.date.fromisoformat(s['dataReadAt'][:10]) <= datetime.date.fromisoformat(d['as_of']),
                      f'{s["id"]}: query read after program cutoff')
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                errors.append(f'{s["id"]}: {exc}')
        else:
            check(isinstance(url, str) and url.startswith(('https://', 'uploads/', 'user:')), f'{s["id"]}: invalid source')
            if isinstance(url, str) and url.startswith('uploads/'):
                material = Path(url).resolve()
                check(material.is_relative_to(Path.cwd() / 'uploads') and material.is_file(),
                      f'{s["id"]}: missing uploaded material')
                if context is not None:
                    check(url in context.get('uploads', []), f'{s["id"]}: 没有这份用户上传的附件')
                if material.suffix.lower() in ('.txt', '.md') and material.is_file():
                    excerpt = excerpt_text(s.get('excerpt', ''))
                    check(excerpt and excerpt in excerpt_text(material.read_text(encoding='utf-8-sig')),
                          f'{s["id"]}: excerpt 不在上传文件原文中')
            if context is not None and isinstance(url, str) and url.startswith('user:'):
                excerpt = excerpt_text(s.get('excerpt', ''))
                messages = [context.get('message', ''), *context.get('earlierMessages', [])]
                check(excerpt and any(excerpt in excerpt_text(msg) for msg in messages),
                      f'{s["id"]}: excerpt 须引用用户原句')
            check('contentHash' not in s and 'dataReadAt' not in s, f'{s["id"]}: shared source requires result path')
        fields(s, ['id', 'title', 'publisher', 'url', 'published', 'accessed', 'locator', 'scope', 'excerpt'], 'sources')
        try:
            check(datetime.date.fromisoformat(s.get('accessed', '')) <= datetime.date.fromisoformat(d['as_of']),
                  f'{s["id"]}: access after cutoff')
        except (ValueError, TypeError):
            errors.append(f'{s["id"]}: invalid accessed date')
    for m in index['metrics'].values():
        source_ids = m.get('source_ids', [])
        check(isinstance(source_ids, list), f'{m.get("id")}: source_ids must be array')
        resolvable(source_ids, 'sources', index)
        bound = [sid for sid in source_ids if sid in shared]
        if 'binding' in m:
            try:
                if len(bound) != 1:
                    raise ValueError('expected one shared source for a bound metric')
                expected = bind_observation(shared[bound[0]], m)
                check(m.setdefault('value', expected) == expected, f'{m["id"]}: value differs from query result')
            except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
                errors.append(f'{m["id"]}: invalid query binding ({exc})')
        fields(m, ['id', 'label', 'value', 'unit', 'period', 'region', 'population', 'definition', 'source_ids'],
               'metrics')
        value = m.get('value')
        check(type(value) in (int, float) and math.isfinite(value), f'{m.get("id")}: nonfinite value')

    # decisions：用户原话可回查（有会话上下文时）
    decisions = d.get('decisions') if isinstance(d.get('decisions'), list) else []
    decision_ids = set()
    for item in decisions:
        fields(item, ['id', 'question', 'userReply', 'scope'], 'decisions')
        check(item.get('scope') in ('evidence', 'standards', 'curriculum', 'schedule', 'general'),
              f'{item.get("id")}: invalid scope')
        check(item.get('id') not in decision_ids, f'decisions: duplicate {item.get("id")}')
        decision_ids.add(item.get('id'))
        if context is not None and isinstance(item.get('userReply'), str):
            quote = excerpt_text(item['userReply'])
            messages = [context.get('message', ''), *context.get('earlierMessages', [])]
            check(any(quote in excerpt_text(msg) for msg in messages),
                  f'{item.get("id")}: userReply 须引用用户原话')
    evidence_continues = [i for i in decisions if i.get('scope') == 'evidence']
    standards_continues = [i for i in decisions if i.get('scope') == 'standards']

    # jobGroups / capabilityDomains
    caps = {}
    for domain in d.get('capabilityDomains') if isinstance(d.get('capabilityDomains'), list) else []:
        fields(domain, ['id', 'name', 'capabilities'], 'capabilityDomains')
        for cap in domain.get('capabilities', []):
            fields(cap, ['id', 'name', 'evidence'], 'capability')
            check(bool(ANCHOR_ID.fullmatch(str(cap.get('id') or ''))),
                  f'capability id 须字母开头、仅含字母数字-_（正文依据要链接到附录锚点）：{cap.get("id")}')
            check(cap.get('id') not in caps, f'capability duplicate {cap.get("id")}')
            caps[cap.get('id')] = cap
    job_groups = d.get('jobGroups') if isinstance(d.get('jobGroups'), list) else []
    check(len(job_groups) >= 2, f'职业面向岗位群仅 {len(job_groups)} 个，至少 2 个（区分初始岗与发展岗）')
    stages_seen = set()
    for group in job_groups:
        fields(group, ['id', 'name', 'summary', 'positions', 'workTasks'], 'jobGroups')
        check(len(group.get('positions', [])) >= 2,
              f'{group.get("id")}: 岗位群至少 2 个代表岗位')
        for pos in group.get('positions', []):
            fields(pos, ['name', 'stage'], 'position')
            check(pos.get('stage') in ('entry', 'development'), f'position stage invalid: {pos.get("name")}')
            stages_seen.add(pos.get('stage'))
            refs = (pos.get('metricIds') or []) + (pos.get('sourceIds') or [])
            check(bool(refs), f'{group.get("id")}/{pos.get("name")}: 岗位须绑定指标或来源')
            resolvable(pos.get('metricIds') or [], 'metrics', index)
            resolvable(pos.get('sourceIds') or [], 'sources', index)
        for task in group.get('workTasks', []):
            fields(task, ['id', 'name'], 'workTask')
            check(bool(task.get('capabilityIds')), f'{task.get("id")}: 工作任务须连接能力项')
            for cap_id in task.get('capabilityIds') or []:
                check(cap_id in caps, f'{task.get("id")}: unresolved capability {cap_id}')
    check(stages_seen >= {'entry', 'development'}, '职业面向须同时覆盖初始岗（entry）与发展岗（development）')
    for cap_id, cap in caps.items():
        evidence = cap.get('evidence') or {}
        status = evidence.get('status')
        check(status in ('verified', 'user-material', 'insufficient'), f'{cap_id}: invalid evidence.status')
        if status == 'verified':
            refs = (evidence.get('metricIds') or []) + (evidence.get('sourceIds') or [])
            check(bool(refs), f'{cap_id}: verified 能力项缺少绑定')
            resolvable(evidence.get('metricIds') or [], 'metrics', index)
            resolvable(evidence.get('sourceIds') or [], 'sources', index)
        elif status == 'user-material':
            check(bool(evidence.get('sourceIds')), f'{cap_id}: user-material 能力项缺少来源')
            resolvable(evidence.get('sourceIds') or [], 'sources', index)
        elif status == 'insufficient':
            check(bool(evidence_continues), f'{cap_id}: insufficient 能力项缺少用户「按现有证据继续」决策')

    # standards：verified 须原文与来源；pending 只须要素名与继续决策（降级路径无来源可指）
    for item in d.get('standards') if isinstance(d.get('standards'), list) else []:
        fields(item, ['element', 'status'], 'standards')
        check(item.get('element') in STANDARD_ELEMENTS, f'standards: invalid element {item.get("element")}')
        check(item.get('status') in ('verified', 'pending'), f'standards/{item.get("element")}: invalid status')
        if item.get('status') == 'verified':
            check(bool(item.get('content')), f'standards/{item.get("element")}: verified 须摘录原文')
            check(item.get('sourceId') in index['sources'], f'standards/{item.get("element")}: unresolved source')
        else:
            check(bool(standards_continues),
                  f'standards/{item.get("element")}: pending 标准缺少用户继续决策')
    if based.get('status') == 'verified':
        check(based.get('sourceId') in index['sources'], 'basedOnStandard: unresolved sourceId')
        check(any(s.get('status') == 'verified' for s in d.get('standards', [])),
              'basedOnStandard verified 但无任何已核对标准要素')
    else:
        check(bool(standards_continues), '标准未核对须有用户继续决策')

    # cultivation：有已核对标准时 goalBasis 须引标准来源；降级路径（待核对+继续决策）可只引区域证据
    cult = d.get('cultivation') or {}
    fields(cult, ['goal', 'goalBasis', 'spec'], 'cultivation')
    basis = cult.get('goalBasis') or {}
    standards_verified = any(s.get('status') == 'verified' for s in d.get('standards', []) if isinstance(s, dict))
    if basis.get('standardSourceId'):
        check(basis.get('standardSourceId') in index['sources'], 'cultivation.goalBasis: unresolved standard source')
    else:
        check(not standards_verified, 'cultivation.goalBasis: 已核对标准时须引用 standardSourceId')
        check(bool(standards_continues), 'cultivation.goalBasis: 无标准来源须有待核对继续决策')
    check(bool(basis.get('metricIds') or basis.get('sourceIds') or basis.get('standardSourceId')),
          'cultivation.goalBasis: 须引用标准来源或区域证据')
    resolvable(basis.get('metricIds') or [], 'metrics', index)
    resolvable(basis.get('sourceIds') or [], 'sources', index)
    dims = {item.get('dimension') for item in cult.get('spec', [])}
    check(dims <= {'素质', '知识', '能力'} and len(dims) == 3, 'cultivation.spec 须覆盖素质/知识/能力三维')
    for item in cult.get('spec', []):
        check(len(item.get('items', [])) >= DEPTH['specItems'],
              f'培养规格「{item.get("dimension")}」仅 {len(item.get("items", []))} 条，'
              f"至少 {DEPTH['specItems']} 条（对标同类公开方案分维度展开）")
        for entry in item.get('items', []):
            fields(entry, ['text'], 'spec item')
            check(text_len(entry.get('text')) >= DEPTH['specItemChars'],
                  f'培养规格条目过短（不足 {DEPTH["specItemChars"]} 字）：{str(entry.get("text"))[:20]}')
            if entry.get('capabilityId'):
                check(entry['capabilityId'] in caps, f'spec item: unresolved capability {entry["capabilityId"]}')
            if entry.get('sourceIds'):
                resolvable(entry['sourceIds'], 'sources', index)

    # curriculum
    courses = (d.get('curriculum') or {}).get('courses')
    check(isinstance(courses, list) and bool(courses), 'curriculum.courses must be non-empty array')
    course_ids = set()
    for c in courses if isinstance(courses, list) else []:
        fields(c, ['id', 'name', 'category', 'theoryHours', 'practiceHours', 'credits', 'semesters',
                   'assessment', 'rationale'], 'course')
        check(c.get('id') not in course_ids, f'course duplicate {c.get("id")}')
        course_ids.add(c.get('id'))
        check(c.get('category') in CATEGORIES, f'{c.get("id")}: invalid category {c.get("category")}')
        for key in ('theoryHours', 'practiceHours'):
            check(isinstance(c.get(key), int) and c[key] >= 0, f'{c.get("id")}: {key} must be non-negative int')
        check(isinstance(c.get('credits'), (int, float)) and c['credits'] > 0, f'{c.get("id")}: invalid credits')
        check(isinstance(c.get('semesters'), list) and bool(c.get('semesters')) and
              all(isinstance(s, int) and 1 <= s <= (years or 3) * 2 for s in c.get('semesters', [])),
              f'{c.get("id")}: invalid semesters')
        if c.get('category') in ALL_PRACTICE_CATEGORIES:
            check(c.get('theoryHours') == 0, f'{c.get("id")}: 集中实践类别全部计实践学时，theoryHours 须为 0')
        if c.get('category') in PROFESSIONAL_CATEGORIES:
            check(bool(c.get('domains')), f'{c.get("id")}: 专业类课程须绑定能力域')
        for ref in c.get('domains', []) or []:
            check(ref.get('capabilityId') in caps, f'{c.get("id")}: unresolved capability {ref.get("capabilityId")}')
            check(ref.get('level') in ('H', 'M', 'L'), f'{c.get("id")}: invalid support level')
        rationale = c.get('rationale') or {}
        fields(rationale, ['text'], f'{c.get("id")} rationale')
        refs = (rationale.get('metricIds') or []) + (rationale.get('sourceIds') or [])
        check(bool(refs), f'{c.get("id")}: rationale 须绑定指标或来源')
        resolvable(rationale.get('metricIds') or [], 'metrics', index)
        resolvable(rationale.get('sourceIds') or [], 'sources', index)
        # 内容深度：每门课有简介与典型内容，核心课加严
        core = c.get('category') == 'professional-core'
        desc_floor = DEPTH['coreDescription'] if core else DEPTH['courseDescription']
        content_floor = DEPTH['coreContent'] if core else DEPTH['courseContent']
        check(text_len(c.get('description')) >= desc_floor,
              f'{c.get("id")} {c.get("name")}: 课程简介不足 {desc_floor} 字（现为 {text_len(c.get("description"))} 字）')
        check(text_len(c.get('typicalContent')) >= content_floor,
              f'{c.get("id")} {c.get("name")}: 典型教学内容/工作任务不足 {content_floor} 字（现为 {text_len(c.get("typicalContent"))} 字）')
        ratio = (c['theoryHours'] + c['practiceHours']) / c['credits']
        warn(14 <= ratio <= 30, f'{c.get("id")}: 学时学分比 {ratio:.0f}:1 超出常见区间 14–30')
    # 课程类别齐全（附录学时结构表完整的前提）
    present_categories = {c.get('category') for c in courses if isinstance(courses, list)}
    for category in CATEGORIES:
        check(category in present_categories, f'课程体系缺少「{CATEGORY_NAMES[category]}」类别课程')
    # 对标语料门槛：不足不得起草/构建
    corpus_count = sum(1 for s in index['sources'].values()
                       if str(s.get('url', '')).startswith('corpus:'))
    check(corpus_count >= DEPTH['corpusRefs'],
          f'对标语料仅 {corpus_count} 份，不足 {DEPTH["corpusRefs"]} 份：先按索引选样精读同类方案再起草')

    # chartPlan：先规划图表再取数；图型家族硬门槛（成品页面由 scripts/check_page.py 二次校验）
    titles = section_titles(d)
    plan_ids = set()
    plan_kinds = []
    for e in d.get('chartPlan') if isinstance(d.get('chartPlan'), list) else []:
        check(isinstance(e, dict), 'chartPlan: 条目须为对象')
        if not isinstance(e, dict):
            continue
        fields(e, ['id', 'question', 'kind', 'reason', 'section', 'dataOrigin', 'dataRefs'], 'chartPlan')
        check(isinstance(e.get('id'), str) and bool(ANCHOR_ID.fullmatch(e.get('id') or '')),
              f'chartPlan: id 须字母开头、仅含字母数字-_：{e.get("id")}')
        check(e.get('id') not in plan_ids, f'chartPlan: duplicate id {e.get("id")}')
        plan_ids.add(e.get('id'))
        check(e.get('kind') in FIGURE_KINDS,
              f'{e.get("id")}: 图型 {e.get("kind")} 不在 figure/1 可执行集（{ "、".join(sorted(FIGURE_KINDS)) }）')
        if e.get('kind') in CHART_FAMILY:
            plan_kinds.append(e['kind'])
        check(e.get('dataOrigin') in ('program', 'query', 'corpus', 'user'),
              f'{e.get("id")}: dataOrigin 须为 program/query/corpus/user')
        check(e.get('section') in titles,
              f'{e.get("id")}: 插图章节「{e.get("section")}」不在正文章节中，可选：{"、".join(titles)}')
        refs = e.get('dataRefs')
        check(isinstance(refs, dict), f'{e.get("id")}: dataRefs must be object')
        if isinstance(refs, dict):
            if e.get('dataOrigin') == 'query':
                check(bool(refs.get('metricIds')), f'{e.get("id")}: 岗位数据图表须绑定 metricIds（按规划一次取齐）')
                resolvable(refs.get('metricIds') or [], 'metrics', index)
            elif e.get('dataOrigin') == 'corpus':
                sids = refs.get('sourceIds') or []
                resolvable(sids, 'sources', index)
                check(bool(sids) and all(str((index['sources'].get(s) or {}).get('url', '')).startswith('corpus:')
                                          for s in sids),
                      f'{e.get("id")}: 语料对标图表须绑定 corpus: 来源')
            elif e.get('dataOrigin') == 'user':
                check(bool(refs.get('sourceIds')), f'{e.get("id")}: 用户材料图表须绑定 sourceIds')
                resolvable(refs.get('sourceIds') or [], 'sources', index)
            else:
                # 方案自带数据的图由脚本确定性生成图稿规格（charts 子命令），标签/无支撑格/
                # 面板组织等规则才能落到代码与单测；可执行 kind 只开放已实现生成器的两种
                check(e.get('kind') in ('matrix', 'grouped-line'),
                      f'{e.get("id")}: 方案自带数据图表由 program.py charts 生成规格，'
                      'kind 支持 matrix（课程×能力域支撑矩阵）/ grouped-line（逐学期学时占比）')
                check(bool(refs.get('fromProgram')), f'{e.get("id")}: 方案自带数据图表须在 fromProgram 写明取数字段')
    families = [CHART_FAMILY[k] for k in plan_kinds]
    check(len(set(families)) >= CHART_MIN_FAMILIES,
          f'图表规划仅 {len(set(families))} 种图型家族（{ "、".join(sorted(set(families))) or "无" }），'
          f'至少 {CHART_MIN_FAMILIES} 种完全不同的图型（条形家族算一种；构成/趋势/交叉关系选对应图型）')
    bar_count = sum(1 for f in families if f == '条形')
    check(bar_count * 2 <= len(plan_kinds),
          f'条形家族图表 {bar_count}/{len(plan_kinds)} 超过全部图的一半，改用与数据关系匹配的图型')

    # pedagogy：教学实施与考核评价
    pedagogy = d.get('pedagogy') or {}
    for key, label in (('teachingImplementation', '教学实施'), ('assessment', '考核评价')):
        check(text_len(pedagogy.get(key)) >= DEPTH['pedagogy'],
              f'pedagogy.{key}（{label}）不足 {DEPTH["pedagogy"]} 字（现为 {text_len(pedagogy.get(key))} 字），'
              '须写教学模式、方法手段、组织形式 / 课程考核、实践考核与多元评价的实质内容')

    # schedule
    schedule = d.get('schedule') or {}
    semesters = schedule.get('semesters')
    check(isinstance(semesters, list) and bool(semesters), 'schedule.semesters must be non-empty array')
    semester_numbers = []
    for sem in semesters if isinstance(semesters, list) else []:
        fields(sem, ['no', 'weeks', 'activities'], 'semester')
        semester_numbers.append(sem.get('no'))
        activities_total = sum(a.get('weeks', 0) for a in sem.get('activities', []))
        check(activities_total == sem.get('weeks'),
              f'第{sem.get("no")}学期: 活动周数 {activities_total} 与学期周数 {sem.get("weeks")} 不一致')
    check(sorted(x for x in semester_numbers if isinstance(x, int)) == list(range(1, (years or 3) * 2 + 1)),
          'schedule 须覆盖全部学期且编号连续')
    internship = schedule.get('internship') or {}
    check(isinstance(internship.get('weeks'), int) and internship['weeks'] > 0,
          'schedule.internship.weeks required')
    internship_courses = [c for c in courses if c.get('category') == 'internship']
    check(bool(internship_courses), '课程表须包含岗位实习（internship）课程')

    # assurance：supported 须引用用户材料且说明有实质内容
    assurance = d.get('assurance') or {}
    for key, item in assurance.items():
        if isinstance(item, dict):
            check(item.get('status') in ('supported', 'pending'), f'assurance.{key}: invalid status')
            if item.get('status') == 'supported':
                check(bool(item.get('text')) and bool(item.get('sourceIds')),
                      f'assurance.{key}: supported 须有说明与来源')
                check(text_len(item.get('text')) >= 30,
                      f'assurance.{key}: 实施保障说明不足 30 字')
                resolvable(item.get('sourceIds') or [], 'sources', index)
            else:
                warnings.append(f'实施保障「{key}」待补：未获得用户材料')

    # graduation：毕业要求条数与实质内容
    graduation = d.get('graduation') or {}
    requirements = graduation.get('requirements')
    check(isinstance(requirements, list) and len(requirements) >= DEPTH['graduationItems'],
          f'毕业要求仅 {len(requirements) if isinstance(requirements, list) else 0} 条，'
          f"至少 {DEPTH['graduationItems']} 条（思想品德、学分、实习、证书等）")
    if isinstance(requirements, list):
        check(text_len(''.join(str(r) for r in requirements)) >= DEPTH['graduationChars'],
              f'毕业要求总字数不足 {DEPTH["graduationChars"]} 字，逐条写明达标口径')
        for item in requirements:
            check(text_len(item) >= 8, f'毕业要求条目过短：{item}')

    # diff（可选）
    diff = d.get('diff')
    if diff is not None:
        check(diff.get('basis') in index['sources'], 'diff.basis unresolved')
        check(isinstance(diff.get('items'), list) and bool(diff['items']), 'diff.items must be non-empty')
        for item in diff.get('items', []):
            fields(item, ['section', 'old', 'new'], 'diff item')

    # redlineOverrides
    overrides = d.get('redlineOverrides')
    if overrides is not None:
        check(bool(overrides.get('providedBy')), 'redlineOverrides.providedBy required')
        for key in (overrides.get('values') or {}):
            check(key in OVERRIDE_KEYS, f'redlineOverrides: unknown key {key}')

    # 红线（结构错误时 totals 可能不可靠，仍尽力计算）
    computed = compute_hours(d) if isinstance(courses, list) and courses else None
    if computed:
        rv = redline_values(d)
        d['computed'] = computed
        checks = [
            ('R1', '总学时', rv['totalHoursMin'] <= computed['totalHours'] <= rv['totalHoursMax'],
             f"{computed['totalHours']}（要求 {rv['totalHoursMin']}–{rv['totalHoursMax']}）"),
            ('R2', '实践性教学占比', computed['practiceRatio'] >= rv['practiceRatioMin'],
             f"{computed['practiceRatio']:.1%}（要求 ≥{rv['practiceRatioMin']:.0%}）"),
            ('R3', '公共基础课占比', computed['publicRatio'] >= rv['publicRatioMin'],
             f"{computed['publicRatio']:.1%}（要求 ≥{rv['publicRatioMin']:.0%}）"),
            ('R4', '选修课占比', computed['electiveRatio'] >= rv['electiveRatioMin'],
             f"{computed['electiveRatio']:.1%}（要求 ≥{rv['electiveRatioMin']:.0%}）"),
            ('R5', '专业核心课门数', rv['coreCoursesMin'] <= computed['coreCourses'] <= rv['coreCoursesMax'],
             f"{computed['coreCourses']} 门（要求 {rv['coreCoursesMin']}–{rv['coreCoursesMax']}）"),
            ('R6', '岗位实习周数', rv['internshipWeeksMin'] <= internship.get('weeks', 0) <= rv['internshipWeeksMax'],
             f"{internship.get('weeks', 0)} 周（要求 {rv['internshipWeeksMin']}–{rv['internshipWeeksMax']}，约 6 个月可集中或分阶段）"),
            ('R8', '总学分与换算',
             rv['creditsMin'] <= computed['totalCredits'] <= rv['creditsMax']
             and computed['totalCredits'] >= computed['totalHours'] / rv['hoursPerCreditMax'] - rv['creditTolerance']
             and computed['totalCredits'] <= computed['totalHours'] / rv['hoursPerCreditMin'] + rv['creditTolerance'],
             f"{computed['totalCredits']}（要求 {rv['creditsMin']}–{rv['creditsMax']}，且落在 {rv['hoursPerCreditMin']}–{rv['hoursPerCreditMax']} 学时/学分换算区间 ±{rv['creditTolerance']}）"),
        ]
        for year in range((years or 3)):
            pair = [s for s in semesters if isinstance(s, dict) and s.get('no') in (year * 2 + 1, year * 2 + 2)]
            if len(pair) == 2:
                total = sum(s.get('weeks', 0) for s in pair)
                checks.append((f'R7', f'第{year + 1}学年教学活动周数', total == rv['weeksPerYear'],
                               f'{total} 周（要求 {rv["weeksPerYear"]}）'))
        for code, name, passed, actual in checks:
            check(passed, f'红线未达标 {code} {name}：{actual}')
        # R9–R12 已在结构校验中体现；R12 覆盖度
        support = {}
        for c in courses:
            for ref in c.get('domains', []) or []:
                support.setdefault(ref['capabilityId'], []).append(c['name'])
        for cap_id in caps:
            n = len(support.get(cap_id, []))
            check(n >= 1, f'R12: 能力项 {cap_id} 无课程支撑')
            warn(n >= 2, f'R12 建议: 能力项 {cap_id} 仅 1 门课程支撑（通行要求 ≥2 门）')
        # 毕业学分与总学分
        min_credits = graduation.get('minCredits')
        if isinstance(min_credits, (int, float)):
            check(min_credits <= computed['totalCredits'],
                  f'graduation.minCredits {min_credits} 超过课程总学分 {computed["totalCredits"]}')
            warn(min_credits == computed['totalCredits'],
                 f'毕业要求学分 {min_credits} 与课程总学分 {computed["totalCredits"]} 不一致')
        # final 约束：无待核对标准、无证据不足能力项
        if d.get('status') == 'final':
            pending_std = [s for s in d.get('standards', []) if s.get('status') == 'pending']
            check(not pending_std, 'final 方案不得有待核对标准要素')
            insufficient_caps = [c_id for c_id, cap in caps.items()
                                 if (cap.get('evidence') or {}).get('status') == 'insufficient']
            check(not insufficient_caps, 'final 方案不得有证据不足能力项')
    return {'errors': errors, 'warnings': warnings, 'computed': computed}


# ---------------------------------------------------------------- Word 生成

CONTENT_TYPES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>'''

RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''

DOC_RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:eastAsia="SimSun" w:hAnsi="Calibri"/><w:sz w:val="21"/></w:rPr></w:rPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="0"/><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="1"/><w:spacing w:before="200" w:after="100"/></w:pPr><w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="2"/><w:spacing w:before="160" w:after="80"/></w:pPr><w:rPr><w:b/><w:sz w:val="23"/></w:rPr></w:style>
</w:styles>'''


def esc(text):
    return (str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


# 正文里的依据是 [可读名称](#锚点) 链接；Word 里内部锚点显示为可读文字，http(s) 做成真超链接
MD_LINK = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')


def docx_runs(text, hyperlinks, bold=False):
    """把文本转成 run/hyperlink XML 片段；外链登记关系到 hyperlinks 列表。"""
    parts = []
    pos = 0
    for match in MD_LINK.finditer(str(text)):
        if match.start() > pos:
            parts.append(('t', str(text)[pos:match.start()]))
        label, target = match.group(1), match.group(2)
        if re.match(r'https?://', target):
            rid = f'rId{len(hyperlinks) + 10}'
            hyperlinks.append((rid, target))
            parts.append(('a', rid, label))
        else:
            parts.append(('t', label))
        pos = match.end()
    if pos < len(str(text)):
        parts.append(('t', str(text)[pos:]))
    xml = []
    for part in parts:
        if part[0] == 't':
            rpr = '<w:rPr><w:b/></w:rPr>' if bold else ''
            xml.append(f'<w:r>{rpr}<w:t xml:space="preserve">{esc(part[1])}</w:t></w:r>')
        else:
            xml.append(f'<w:hyperlink r:id="{part[1]}"><w:r><w:rPr><w:color w:val="0563C1"/>'
                       f'<w:u w:val="single"/></w:rPr>'
                       f'<w:t xml:space="preserve">{esc(part[2])}</w:t></w:r></w:hyperlink>')
    return ''.join(xml)


def docx_paragraph(text, style=None, hyperlinks=None):
    hyperlinks = hyperlinks if hyperlinks is not None else []
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ''
    return f'<w:p>{ppr}{docx_runs(text, hyperlinks)}</w:p>'


def parse_md_table(markdown_text):
    """mdtable 载荷（markdown 表文本）回解为行，供 Word 表格渲染。"""
    rows = []
    for line in str(markdown_text).splitlines():
        line = line.strip()
        if not line.startswith('|'):
            continue
        cells = [c.strip().replace('\\|', '|') for c in line.strip('|').split('|')]
        if all(re.fullmatch(r':?-{3,}:?', c) for c in cells):
            continue
        rows.append(cells)
    return rows


def docx_table(rows, hyperlinks=None):
    hyperlinks = hyperlinks if hyperlinks is not None else []
    width = max(1, int(9360 / max(1, len(rows[0]))))
    xml = ['<w:tbl><w:tblPr><w:tblBorders>',
           *['<w:{side} w:val="single" w:sz="4" w:color="999999"/>'.format(side=side)
             for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV')],
           '</w:tblBorders></w:tblPr>']
    for i, row in enumerate(rows):
        xml.append('<w:tr>')
        for cell in row:
            xml.append(f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/></w:tcPr>'
                       f'<w:p>{docx_runs(cell, hyperlinks, bold=(i == 0))}</w:p></w:tc>')
        xml.append('</w:tr>')
    xml.append('</w:tbl>')
    return ''.join(xml)


def doc_rels(hyperlinks):
    extra = ''.join(
        f'<Relationship Id="{rid}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
        f'Target="{esc(target)}" TargetMode="External"/>' for rid, target in hyperlinks)
    return DOC_RELS.replace('</Relationships>', extra + '</Relationships>')


def write_docx(path, blocks):
    hyperlinks = []
    body = []
    for block in blocks:
        if block[0] in ('h1', 'h2', 'h3'):
            body.append(docx_paragraph(block[1], style='Heading' + block[0][1], hyperlinks=hyperlinks))
        elif block[0] == 'p':
            body.append(docx_paragraph(block[1], hyperlinks=hyperlinks))
        elif block[0] == 'table':
            body.append(docx_table(block[1], hyperlinks))
        elif block[0] == 'mdtable':
            body.append(docx_table(parse_md_table(block[1]), hyperlinks))
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                f'<w:body>{"".join(body)}'
                '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr>'
                '</w:body></w:document>')
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f'<dc:title>人才培养方案</dc:title><dcterms:created xmlns:dcterms="http://purl.org/dc/terms/">'
            f'{now}</dcterms:created></cp:coreProperties>')
    app = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<Properties xmlns="http://schemas.openxmlformats.org/package/2006/extended-properties">'
           '<Application>training-program-design</Application></Properties>')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', CONTENT_TYPES)
        archive.writestr('_rels/.rels', RELS)
        archive.writestr('docProps/core.xml', core)
        archive.writestr('docProps/app.xml', app)
        archive.writestr('word/_rels/document.xml.rels', doc_rels(hyperlinks))
        archive.writestr('word/styles.xml', STYLES)
        archive.writestr('word/document.xml', document)


# ---------------------------------------------------------------- 正文组稿

def md_table(rows):
    def clean(cell):
        return str(cell).replace('|', '\\|').replace('\n', ' ')
    lines = ['| ' + ' | '.join(clean(c) for c in rows[0]) + ' |',
             '|' + '---|' * len(rows[0])]
    for row in rows[1:]:
        lines.append('| ' + ' | '.join(clean(c) for c in row) + ' |')
    return '\n'.join(lines)


def pct(value):
    return f'{value:.1%}'


def section_titles(d):
    """正文章节标题（chartPlan 插图定位与页组稿共用）。"""
    titles = ['一、专业名称及代码', '二、入学要求', '三、修业年限', '四、职业面向',
              '五、培养目标与培养规格', '六、课程设置及要求', '七、学时安排', '八、教学进程总体安排',
              '九、教学实施与考核评价', '十、实施保障', '十一、毕业要求', '十二、编制说明与决策记录',
              '附录A 证据与口径', '附录B 能力—课程支撑矩阵', '附录C 待核对与未决清单']
    if d.get('diff'):
        titles.append('附录D 新旧版差异')
    return titles


def capability_index(d):
    caps = {}
    for domain in d['capabilityDomains']:
        for cap in domain['capabilities']:
            caps[cap['id']] = {'cap': cap, 'domain': domain['name']}
    return caps


def support_map(d):
    support = {}
    for c in d['curriculum']['courses']:
        for ref in c.get('domains', []) or []:
            support.setdefault(ref['capabilityId'], []).append((c['name'], ref['level']))
    return support


def compose_blocks(d):
    """Shared content model: list of (kind, payload).

    依据一律「可读名称 + 页内锚点链接」（[名称](#锚点)），编号只留在附录条目标识与
    结构化产物；含链接的表用 mdtable（markdown 表文本），网页经 text 块渲染、Word 由
    write_docx 解析。锚点由 page_blocks 在附录 A/B 落地。
    """
    meta = d['meta']
    computed = d['computed']
    caps = capability_index(d)
    source_index = {s['id']: s for s in d['sources']}
    metric_index = {m['id']: m for m in d['metrics']}
    support = support_map(d)
    redlines = validation_rows(d)

    def m_links(ids):
        return '、'.join(md_link(metric_link_text(metric_index[m]), m)
                         for m in ids if m in metric_index) or '—'

    def s_links(ids):
        return '、'.join(md_link(source_ref_text(source_index[s]), s)
                         for s in ids if s in source_index) or '—'

    def c_links(ids):
        return '、'.join(md_link(caps[c]['cap']['name'], c) for c in ids if c in caps) or '—'

    def scoped_table(header, rows, metric_ids):
        """带指标依据的表：口径在表头说明一次，链接文字用短名称。"""
        note = scope_note(metric_index, metric_ids)
        lead = f"依据口径{note}；各指标的完整口径、总体与分母见附录 A.2。" if note \
            else '各指标的口径、总体与分母见附录 A.2。'
        return lead + '\n\n' + md_table([header] + rows)

    basis = d['cultivation']['goalBasis']
    facing_metrics = [m for pos in [p for g in d['jobGroups'] for p in g.get('positions', [])]
                      for m in pos.get('metricIds', [])]
    blocks = [
        ('h1', d['title']),
        ('p', f"版本 {meta['version']} · {d['status']} · 证据截止 {d['as_of']} · {meta['level']}"
              f"{meta['duration']['years']}年制 · 服务区域 {meta['region']}"),
        ('h2', '一、专业名称及代码'),
        ('p', f"{meta['majorName']}（专业代码 {meta['majorCode']}）"),
        ('h2', '二、入学要求'),
        ('p', meta.get('entryRequirement') or '（待确认）'),
        ('h2', '三、修业年限'),
        ('p', f"基本修业年限 {meta['duration']['years']} 年"
              + (f"，最长 {meta['duration'].get('maxYears')} 年" if meta['duration'].get('maxYears') else '')),
        ('h2', '四、职业面向'),
        ('mdtable', scoped_table(
            ['岗位群', '代表岗位', '阶段', '依据'],
            [[group['name'], pos['name'],
              '初始岗' if pos['stage'] == 'entry' else '发展岗',
              '、'.join(x for x in [m_links(pos.get('metricIds', [])), s_links(pos.get('sourceIds', []))]
                        if x != '—') or '—']
             for group in d['jobGroups'] for pos in group.get('positions', [])], facing_metrics)),
        ('h2', '五、培养目标与培养规格'),
        ('p', d['cultivation']['goal']),
        ('p', '目标依据：'
              + (md_link(source_ref_text(source_index[basis['standardSourceId']]), basis['standardSourceId'])
                 if basis.get('standardSourceId') and basis['standardSourceId'] in source_index
                 else '标准原文待核对（已获用户决策按待核对继续），目标在区域岗位证据基础上拟定，待标准原文核对后回填')
              + ''.join(f"、{part}" for part in [
                  f"区域证据 {m_links(basis.get('metricIds', []))}" if basis.get('metricIds') else '',
                  f"校本材料 {s_links(basis.get('sourceIds', []))}" if basis.get('sourceIds') else '',
              ] if part)
              + scope_note(metric_index, basis.get('metricIds', []))),
    ]
    for item in d['cultivation']['spec']:
        blocks.append(('h3', f"培养规格 · {item['dimension']}"))
        blocks.append(('mdtable', md_table([['条目', '关联能力/来源']] + [
            [entry['text'],
             c_links([entry['capabilityId']]) if entry.get('capabilityId')
             else s_links(entry.get('sourceIds', []))]
            for entry in item.get('items', [])])))
    blocks += [
        ('h2', '六、课程设置及要求'),
        ('h3', '6.1 工作任务与职业能力分析'),
        ('mdtable', md_table([['岗位群', '典型工作任务', '支撑能力项']] + [
            [group['name'], task['name'], c_links(task['capabilityIds'])]
            for group in d['jobGroups'] for task in group.get('workTasks', [])])),
        ('h3', '6.2 课程体系'),
        ('table', [['课程', '类别', '理论学时', '实践学时', '学分', '开设学期', '考核']] + [
            [c['name'], CATEGORY_NAMES[c['category']], c['theoryHours'], c['practiceHours'],
             c['credits'], '、'.join(f'第{s}学期' for s in c['semesters']), c['assessment']]
            for c in sorted(d['curriculum']['courses'], key=lambda c: (c['category'], c['semesters']))]),
        ('h3', '6.3 专业核心课程设置理由与证据链'),
        ('mdtable', scoped_table(
            ['核心课程', '设置理由', '证据'],
            [[c['name'], c['rationale']['text'],
              '、'.join(x for x in [m_links(c['rationale'].get('metricIds', [])),
                                    s_links(c['rationale'].get('sourceIds', []))] if x != '—') or '—']
             for c in d['curriculum']['courses'] if c['category'] == 'professional-core'],
            [m for c in d['curriculum']['courses'] if c['category'] == 'professional-core'
             for m in c['rationale'].get('metricIds', [])])),
        ('h3', '6.4 课程简介与典型教学内容'),
        ('table', [['课程', '课程简介', '典型教学内容/工作任务']] + [
            [c['name'], c.get('description', ''), c.get('typicalContent', '')]
            for c in sorted(d['curriculum']['courses'], key=lambda c: (c['category'], c['semesters']))]),
        ('h2', '七、学时安排'),
        ('h3', '7.1 学分学时结构'),
        ('table', [['课程类别', '门数', '学时', '学分']] + [
            [CATEGORY_NAMES[cat], item['courses'], item['hours'], item['credits']]
            for cat, item in sorted(computed['byCategory'].items())] +
            [['合计', len(d['curriculum']['courses']), computed['totalHours'], computed['totalCredits']]]),
        ('h3', '7.2 红线对照'),
        ('table', redlines),
        ('h2', '八、教学进程总体安排'),
        ('h3', '8.1 学期周进程'),
        ('table', [['学期', '周数', '活动安排']] + [
            [f"第{s['no']}学期", s['weeks'],
             '；'.join(f"{a['name']} {a['weeks']}周" for a in s.get('activities', []))]
            for s in d['schedule']['semesters']]),
        ('h3', '8.2 分学期课程安排'),
        ('table', [['学期', '课程']] + [
            [f'第{no}', '、'.join(c['name'] for c in d['curriculum']['courses'] if no in c['semesters'])]
            for no in range(1, meta['duration']['years'] * 2 + 1)]),
        ('h2', '九、教学实施与考核评价'),
        ('h3', '9.1 教学实施'),
        ('p', d['pedagogy'].get('teachingImplementation', '')),
        ('h3', '9.2 考核评价'),
        ('p', d['pedagogy'].get('assessment', '')),
        ('h2', '十、实施保障'),
    ]
    labels = {'faculty': '师资队伍', 'facilities': '教学设施与实训条件', 'cooperation': '校企合作'}
    for key, label in labels.items():
        item = d['assurance'].get(key) or {}
        status = '已依据用户提供材料' if item.get('status') == 'supported' else '待补（未获得用户材料）'
        blocks.append(('h3', f"10.{list(labels).index(key) + 1} {label}"))
        blocks.append(('p', f"{item.get('text') or '待补'}（{status}"
                           + (f"；来源 {s_links(item.get('sourceIds', []))}" if item.get('sourceIds') else '') + '）'))
    blocks += [
        ('h2', '十一、毕业要求'),
        ('p', '；'.join(d['graduation']['requirements'])
              + (f"。毕业最低学分 {d['graduation'].get('minCredits', computed['totalCredits'])}"
                 f"（课程总学分 {computed['totalCredits']}）")),
        ('h2', '十二、编制说明与决策记录'),
        ('p', '本方案建立动态调整机制，随区域产业与岗位证据变化及时优化调整。关键取舍与用户决策记录如下。'),
        ('table', [['决策', '问题', '用户选择']] + [
            [item['id'], item['question'], item['userReply']] for item in d.get('decisions', [])] or
        [['—', '—', '—']]),
        ('h2', '附录A 证据与口径'),
        ('h3', 'A.1 来源'),
        ('table', [['编号', '标题', '出处', '口径', '读取时间']] + [
            [s['id'], s['title'], s['publisher'], s['scope'],
             s.get('dataReadAt', '')[:10] or s['accessed']] for s in d['sources']]),
        ('h3', 'A.2 指标'),
        ('table', [['编号', '指标', '数值', '单位', '地域', '总体', '口径', '来源']] + [
            [m['id'], m['label'], fmt_num(m['value']), m['unit'], m['region'], m['population'],
             m['definition'], '、'.join(m['source_ids'])] for m in d['metrics']]),
        ('h2', '附录B 能力—课程支撑矩阵'),
        ('table', [['能力域', '能力项', '支撑课程（强度）']] + [
            [item['domain'], item['cap']['name'],
             '、'.join(f'{name}（{level}）' for name, level in support.get(cap_id, [])) or '无']
            for cap_id, item in caps.items()]),
        ('h2', '附录C 待核对与未决清单'),
    ]
    pending = [s for s in d['standards'] if s['status'] == 'pending']
    pending_rows = [['类型', '事项', '处理']] + [
        ['标准待核对', f"要素「{s['element']}」", s.get('note') or '已获用户决策按待核对继续'] for s in pending]
    insufficient = [item['cap'] for item in caps.values()
                    if item['cap'].get('evidence', {}).get('status') == 'insufficient']
    pending_rows += [['能力项证据不足', cap['name'], '已获用户决策按现有证据继续（标注待验证）']
                     for cap in insufficient]
    pending_rows += [['警告', w, '建议复核'] for w in (d.get('_warnings') or [])]
    if len(pending_rows) == 1:
        pending_rows.append(['—', '暂无待核对事项', '—'])
    blocks.append(('table', pending_rows))
    diff = d.get('diff')
    if diff:
        blocks += [
            ('h2', '附录D 新旧版差异'),
            ('p', f"对比基准：{md_link(source_ref_text(source_index[diff['basis']]), diff['basis'])}"),
            ('table', [['章节', '旧版', '新版', '理由']] + [
                [item['section'], item['old'], item['new'], item.get('reason', '')]
                for item in diff['items']]),
        ]
    return blocks


def validation_rows(d):
    computed = d.get('computed') or compute_hours(d)
    rv = redline_values(d)
    internship = (d.get('schedule') or {}).get('internship') or {}
    year_rows = []
    years = d['meta']['duration']['years']
    semesters = d['schedule']['semesters']
    for year in range(years):
        pair = [s for s in semesters if s.get('no') in (year * 2 + 1, year * 2 + 2)]
        if len(pair) == 2:
            total = sum(s.get('weeks', 0) for s in pair)
            year_rows.append((f'第{year + 1}学年周数', total, total == rv['weeksPerYear']))
    rows = [
        ('总学时', computed['totalHours'], rv['totalHoursMin'] <= computed['totalHours'] <= rv['totalHoursMax']),
        ('实践性教学占比', pct(computed['practiceRatio']), computed['practiceRatio'] >= rv['practiceRatioMin']),
        ('公共基础课占比', pct(computed['publicRatio']), computed['publicRatio'] >= rv['publicRatioMin']),
        ('选修课占比', pct(computed['electiveRatio']), computed['electiveRatio'] >= rv['electiveRatioMin']),
        ('专业核心课门数', computed['coreCourses'],
         rv['coreCoursesMin'] <= computed['coreCourses'] <= rv['coreCoursesMax']),
        ('岗位实习周数', internship.get('weeks', 0),
         rv['internshipWeeksMin'] <= internship.get('weeks', 0) <= rv['internshipWeeksMax']),
        ('总学分', computed['totalCredits'],
         rv['creditsMin'] <= computed['totalCredits'] <= rv['creditsMax']
         and computed['totalCredits'] >= computed['totalHours'] / rv['hoursPerCreditMax'] - rv['creditTolerance']
         and computed['totalCredits'] <= computed['totalHours'] / rv['hoursPerCreditMin'] + rv['creditTolerance']),
    ] + year_rows
    return [['红线', '实际', '结论']] + [[name, str(actual), '通过' if ok else '不达标']
                                        for name, actual, ok in rows]


def blocks_markdown(blocks):
    """program.md 与 Word 一致只显示可读文字：锚点链接折叠为链接文字，
    文件内不保留 [#锚点] 链接语法（md 无处落地这些锚点，点了是死链）。"""
    out = []
    for kind, payload in blocks:
        if kind == 'h1':
            out.append(f'# {payload}')
        elif kind == 'h2':
            out.append(f'## {payload}')
        elif kind == 'h3':
            out.append(f'### {payload}')
        elif kind == 'p':
            out.append(MD_LINK.sub(r'\1', payload))
        elif kind == 'table':
            out.append(md_table(payload))
        elif kind == 'mdtable':
            out.append(MD_LINK.sub(r'\1', payload))
        out.append('')
    return '\n'.join(out).rstrip() + '\n'


def build_t05(d):
    tasks = []
    for c in d['curriculum']['courses']:
        tasks.append({
            'courseId': c['id'], 'courseName': c['name'], 'category': c['category'],
            'credits': c['credits'], 'theoryHours': c['theoryHours'], 'practiceHours': c['practiceHours'],
            'semesters': c['semesters'], 'assessment': c['assessment'],
            'description': c.get('description', ''), 'typicalContent': c.get('typicalContent', ''),
            'capabilityRefs': c.get('domains', []),
            'evidenceRefs': {'metricIds': c['rationale'].get('metricIds', []),
                             'sourceIds': c['rationale'].get('sourceIds', [])},
            'developmentNotes': c['rationale']['text'],
        })
    used_metrics = {m for t in tasks for m in t['evidenceRefs']['metricIds']}
    used_sources = {s for t in tasks for s in t['evidenceRefs']['sourceIds']}
    package = {
        'schema': 't05-course-development/1',
        'program': {'majorName': d['meta']['majorName'], 'majorCode': d['meta']['majorCode'],
                    'version': d['meta']['version'], 'asOf': d['as_of'], 'status': d['status']},
        'tasks': tasks,
        'evidenceIndex': {
            'metrics': {m['id']: {k: m[k] for k in ('label', 'value', 'unit', 'source_ids')}
                        for m in d['metrics'] if m['id'] in used_metrics},
            'sources': {s['id']: {k: s[k] for k in ('title', 'locator', 'url')}
                        for s in d['sources'] if s['id'] in used_sources},
        },
    }
    lines = [f"# 课程开发任务包 · {d['meta']['majorName']}（{d['meta']['version']}）", '',
             f"共 {len(tasks)} 门课程；方案状态 {d['status']}。证据索引见 t05-package.json。", '',
             '| 课程 | 类别 | 学分 | 理论/实践学时 | 学期 | 能力绑定 |', '|---|---|---|---|---|---|']
    for t in sorted(tasks, key=lambda t: (t['category'], t['semesters'])):
        caps = '、'.join(f"{r['capabilityId']}({r['level']})" for r in t['capabilityRefs']) or '—'
        lines.append(f"| {t['courseName']} | {CATEGORY_NAMES[t['category']]} | {t['credits']} | "
                     f"{t['theoryHours']}/{t['practiceHours']} | {'、'.join(map(str, t['semesters']))} | {caps} |")
    return package, '\n'.join(lines) + '\n'


# ---------------------------------------------------------------- 方案自带数据的图稿规格（确定性生成）

LEVEL_VALUE = {'H': 3, 'M': 2, 'L': 1}
CATEGORY_ORDER = {name: i for i, name in enumerate(CATEGORIES)}


def support_matrix_spec(d, entry):
    """课程×能力域支撑矩阵（按能力域聚合，只呈现专业课程）。
    无支撑是已知取值（0，最浅色），不写 null——「缺失」只留给真正未知的数据；
    行标签用课程全称，列标签为能力域名去掉「能力域」后缀，不截断。"""
    domain_pairs = []
    for domain in d['capabilityDomains']:
        label = str(domain['name']).replace('能力域', '').strip()
        if not label or len(label) > 12:
            raise ValueError(f'能力域名「{domain["name"]}」去后缀后不适合做图签（须 1–12 字），请改短域名')
        domain_pairs.append((domain, label))
    cap_label = {cap['id']: label for domain, label in domain_pairs for cap in domain['capabilities']}
    bound = [c for c in d['curriculum']['courses'] if c.get('domains')]
    unbound = [c['name'] for c in d['curriculum']['courses'] if not c.get('domains')]
    bound.sort(key=lambda c: (CATEGORY_ORDER[c['category']], c['semesters'], c['name']))
    rows = [{'课程': c['name'], '能力域': label, '强度': max(
        (LEVEL_VALUE[r['level']] for r in c['domains'] if cap_label.get(r['capabilityId']) == label), default=0)}
        for c in bound for _, label in domain_pairs]
    chunk = 7
    panels, datasets = [], {}
    for pi in range(0, len(bound), chunk):
        group = bound[pi:pi + chunk]
        key = f'支撑{len(datasets) + 1}'
        keep = {c['name'] for c in group}
        datasets[key] = [r for r in rows if r['课程'] in keep]
        first, last = group[0]['name'], group[-1]['name']
        scope = f'{first}…{last}' if len(group) > 1 else first
        panels.append({'kind': 'matrix', 'title': f'课程：{scope}（{len(group)} 门）', 'data': key,
                       'fields': {'row': '课程', 'column': '能力域', 'value': '强度'},
                       'scale': 'sequential', 'x_label': '能力域', 'y_label': '课程'})
    unbound_note = ('按国家规定设置的公共基础课与未绑定能力域的课程未列入：' + '、'.join(unbound) + '。'
                    if unbound else '')
    caption = ('每格为该课程对该能力域内能力项的最高支撑强度：H=3、M=2、L=1，0=无支撑（最浅色，属正常取值）。'
               '逐能力项的支撑课程与证据见附录B。' + unbound_note + '数据来自本方案课程表。')
    height = 56 + chunk * 10
    return {'schema': 'figure/1', 'id': entry['id'], 'lang': 'zh', 'width_mm': 200,
            'panel_height_mm': height, 'columns': 1,
            'title': '专业课程对能力域的支撑强度', 'caption': caption,
            'source': '本方案课程体系（curriculum.domains 按能力域聚合）',
            'datasets': datasets, 'panels': panels}


def semester_trend_spec(d, entry):
    """逐学期理论/实践学时占比（grouped-line）：学期是有序坐标，看实践占比递进。"""
    total_by_semester = {}
    for c in d['curriculum']['courses']:
        for s in c['semesters']:
            theory, practice = total_by_semester.get(s, (0, 0))
            hours = c['theoryHours'] + c['practiceHours']
            practice_hours = hours if c['category'] in ALL_PRACTICE_CATEGORIES else c['practiceHours']
            theory_hours = 0 if c['category'] in ALL_PRACTICE_CATEGORIES else c['theoryHours']
            total_by_semester[s] = (theory + theory_hours, practice + practice_hours)
    rows = []
    for s in sorted(total_by_semester):
        theory, practice = total_by_semester[s]
        total = theory + practice
        if not total:
            continue
        rows.append({'类型': '理论学时占比', '学期': s, '占比': round(100 * theory / total, 1)})
        rows.append({'类型': '实践学时占比', '学期': s, '占比': round(100 * practice / total, 1)})
    return {'schema': 'figure/1', 'id': entry['id'], 'lang': 'zh', 'width_mm': 183,
            'title': '逐学期理论与实践学时占比',
            'caption': '横轴为学期（有序坐标），纵轴为该学期总学时中的理论/实践占比（%）；'
                       '岗位实习与综合实践学期全部计实践学时。数据来自本方案课程表与教学进程。',
            'source': '本方案课程体系（curriculum.courses + schedule 按学期汇总）',
            'datasets': {'学时占比': rows},
            'panels': [{'kind': 'grouped-line', 'title': '理论与实践学时占比走势', 'data': '学时占比',
                        'fields': {'group': '类型', 'x': '学期', 'y': '占比'},
                        'x_label': '学期', 'y_label': '占比 (%)', 'y_ticks': [0, 25, 50, 75, 100]}]}


PROGRAM_CHART_BUILDERS = {'matrix': support_matrix_spec, 'grouped-line': semester_trend_spec}


def charts(program_path, work=Path('work')):
    """为 dataOrigin=program 的规划图确定性生成图稿规格（模型随后用 chart-visualization 渲染）；
    岗位查询数据的图仍由模型按规划出图。"""
    d = json.loads(Path(program_path).read_text(encoding='utf-8'))
    result = validate(d)
    if result['errors']:
        print('校验未通过，先修复再生成图稿规格：')
        for item in result['errors']:
            print(f'  - {item}')
        return 1
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    written = []
    for entry in d.get('chartPlan') or []:
        if not isinstance(entry, dict) or entry.get('dataOrigin') != 'program':
            continue
        builder = PROGRAM_CHART_BUILDERS.get(entry.get('kind'))
        if builder is None:
            continue
        spec = builder(d, entry)
        path = work / f"{entry['id']}.json"
        path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
        written.append(path)
    if not written:
        print('chartPlan 中没有 dataOrigin=program 的图，无需生成')
        return 0
    for path in written:
        print(f'已生成 {path}')
    print('再用 chart-visualization 逐张 render + verify 后组页')
    return 0


# ---------------------------------------------------------------- 网页组稿（锚点与插图）

NUMERIC_CELL = re.compile(r'-?[\d,]+(\.\d+)?%?')


def table_block(rows, title='数据表'):
    """compose 的行表 → report-rendering 结构化 table 块（无链接的表用）。"""
    header = [str(c) for c in rows[0]]
    columns = []
    for i, label in enumerate(header):
        cells = [str(r[i]).strip() for r in rows[1:] if i < len(r) and str(r[i]).strip() not in ('', '—', '未提供')]
        numeric = i > 0 and bool(cells) and all(NUMERIC_CELL.fullmatch(c) for c in cells)
        columns.append({'label': label, 'numeric': numeric})
    return {'type': 'table', 'title': title, 'pattern': 'detail', 'columns': columns,
            'rows': [['' if c is None else c for c in row] for row in rows]}


def source_item(s):
    item = {
        'id': s['id'],
        'label': f"{s['id']} · {s['title']}",
        'text': f"出处 {s['publisher']}｜{s['scope']}｜读取 {s.get('dataReadAt', '')[:10] or s['accessed']}"
                + (f"｜定位 {s['locator']}" if s.get('locator') else ''),
    }
    if str(s.get('url', '')).startswith(('http://', 'https://')):
        item['url'] = s['url']
    return item


def metric_block(m, source_index):
    src = '、'.join(md_link(source_ref_text(source_index[s]), s) for s in m.get('source_ids', [])
                   if s in source_index) or '—'
    text = (f"**{m['id']} · {m['label']}**：{fmt_num(m.get('value'))}{m.get('unit') or ''}"
            f"｜{m['region']}｜{m['population']}｜时期 {m['period']}｜口径 {m['definition']}｜来源 {src}")
    return {'type': 'text', 'id': m['id'], 'text': text}


def capability_block(cap_id, item, support, metric_index, source_index):
    cap = item['cap']
    evidence = cap.get('evidence') or {}
    status_names = {'verified': '已核验口径', 'user-material': '用户材料支撑', 'insufficient': '证据不足（按现有证据继续，待验证）'}
    refs = '、'.join(x for x in [
        '、'.join(md_link(metric_link_text(metric_index[m]), m) for m in evidence.get('metricIds', [])
                  if m in metric_index),
        '、'.join(md_link(source_ref_text(source_index[s]), s) for s in evidence.get('sourceIds', [])
                  if s in source_index),
    ] if x) or '无绑定'
    sup = '、'.join(f'{name}（{level}）' for name, level in support.get(cap_id, [])) or '无课程支撑'
    text = f"**{cap_id} · {cap['name']}**（{item['domain']}）｜证据 {refs}｜支撑课程 {sup}"
    return {'type': 'text', 'id': cap_id, 'text': text}


def page_blocks(d):
    """网页正文块：正文各章沿用 compose_blocks（依据为锚点链接），附录 A/B 换成带 id 的
    锚点条目（正文链接的落点），chartPlan 各图按规划章节插入 figure 块。"""
    caps = capability_index(d)
    source_index = {s['id']: s for s in d['sources']}
    metric_index = {m['id']: m for m in d['metrics']}
    support = support_map(d)
    top = []
    section = None
    sub = None

    def open_section(title):
        nonlocal section, sub
        section = {'type': 'section', 'title': title, 'blocks': []}
        top.append(section)
        sub = None

    def open_sub(title):
        nonlocal sub
        sub = {'type': 'section', 'title': title, 'blocks': []}
        if section is not None:
            section['blocks'].append(sub)

    def place(block):
        if sub is not None:
            sub['blocks'].append(block)
        elif section is not None:
            section['blocks'].append(block)
        else:
            top.append(block)

    skip_until_h2 = False
    for kind, payload in compose_blocks(d):
        if skip_until_h2 and kind != 'h2':
            continue
        skip_until_h2 = False
        if kind == 'h1':
            continue
        if kind == 'h2':
            open_section(payload)
            if payload == '附录A 证据与口径':
                open_sub('A.1 来源')
                place({'type': 'sources', 'items': [source_item(s) for s in d['sources']]})
                open_sub('A.2 指标')
                for m in d['metrics']:
                    place(metric_block(m, source_index))
                skip_until_h2 = True
            elif payload == '附录B 能力—课程支撑矩阵':
                for cap_id, item in caps.items():
                    place(capability_block(cap_id, item, support, metric_index, source_index))
                skip_until_h2 = True
        elif kind == 'h3':
            open_sub(payload)
        elif kind == 'p':
            place({'type': 'text', 'text': payload})
        elif kind == 'table':
            place(table_block(payload))
        elif kind == 'mdtable':
            place({'type': 'text', 'text': payload})
    for entry in d.get('chartPlan') or []:
        if not isinstance(entry, dict):
            continue
        figure = {'type': 'figure', 'spec': f"{entry['id']}.json", 'bundle': f"figures/{entry['id']}"}
        target = next((s for s in top if s.get('type') == 'section' and s['title'] == entry.get('section')), None)
        if target is not None:
            target['blocks'].append(figure)
        else:
            top.append(figure)
    return top


def page(program_path, work=Path('work')):
    d = json.loads(Path(program_path).read_text(encoding='utf-8'))
    result = validate(d)
    if result['errors']:
        print('校验未通过，先修复再组页：')
        for item in result['errors']:
            print(f'  - {item}')
        return 1
    d['computed'] = result['computed']
    work = Path(work)
    missing = [e['id'] for e in d['chartPlan']
               if not (work / f"{e['id']}.json").is_file()
               or not (work / 'figures' / e['id'] / 'values.json').is_file()]
    if missing:
        print(f'图稿未就绪，先按 chartPlan 用 chart-visualization 出图（render+verify）再组页：{"、".join(missing)}')
        return 1
    mismatched = []
    for e in d['chartPlan']:
        spec = json.loads((work / f"{e['id']}.json").read_text(encoding='utf-8'))
        if spec.get('id') != e['id']:
            mismatched.append(f'{e["id"]}: 图稿规格 id 应为 {e["id"]}，现为 {spec.get("id")}')
        families = {CHART_FAMILY.get(p.get('kind')) for p in spec.get('panels', [])}
        if families - {CHART_FAMILY.get(e['kind'])}:
            mismatched.append(f'{e["id"]}: 图稿面板家族 {sorted(families)} 与规划 {e["kind"]}（{CHART_FAMILY.get(e["kind"])}）不一致')
    if mismatched:
        print('图稿与规划不一致：')
        for item in mismatched:
            print(f'  - {item}')
        return 1
    blocks = page_blocks(d)
    out = work / 'page-body.json'
    out.write_text(json.dumps({'blocks': blocks}, ensure_ascii=False, indent=2), encoding='utf-8')

    def deep_count(items):
        figures, ids = 0, 0
        for b in items:
            if b.get('type') == 'figure':
                figures += 1
            if b.get('id'):
                ids += 1
            ids += sum(1 for it in b.get('items', []) if isinstance(it, dict) and it.get('id'))
            if isinstance(b.get('blocks'), list):
                f, i = deep_count(b['blocks'])
                figures += f
                ids += i
        return figures, ids

    figures, ids = deep_count(blocks)
    print(out)
    print(f"章节块 {sum(1 for b in blocks if b.get('type') == 'section')}，图 {figures}，锚点条目 {ids}")
    return 0


def build(program_path, skip_docx=False):
    d = json.loads(Path(program_path).read_text(encoding='utf-8'))
    result = validate(d)
    if result['errors']:
        print('校验未通过，阻断构建：')
        for item in result['errors']:
            print(f'  - {item}')
        return 1
    d['_warnings'] = result['warnings']
    computed = result['computed']
    d['computed'] = computed
    digest = hashlib.sha256(json.dumps(d, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:10]
    out = Path('output') / f'program-{digest}'
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    docx_written = False
    if not skip_docx:
        try:
            write_docx(out / 'program.docx', compose_blocks(d))
            docx_written = True
        except (OSError, ValueError) as exc:
            result['warnings'].append(f'Word 版生成失败已跳过：{exc}')
    if not docx_written:
        result['warnings'].append('Word 版未生成（环境限制），可编辑版请使用 program.md')

    blocks = compose_blocks(d)
    markdown_text = blocks_markdown(blocks)
    if MD_LINK.search(markdown_text):
        print('program.md 仍含链接语法（md 与 Word 一致只显示可读文字），阻断构建')
        return 1
    (out / 'program.md').write_text(markdown_text, encoding='utf-8')
    (out / 'program.json').write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
    validation = {'program': d['meta']['majorName'], 'version': d['meta']['version'], 'as_of': d['as_of'],
                  'status': d['status'], 'computed': computed,
                  'redlines': validation_rows(d)[1:], 'charts': chart_summary(d),
                  'errors': result['errors'],
                  'warnings': result['warnings']}
    (out / 'validation.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding='utf-8')
    package, overview = build_t05(d)
    (out / 't05-package.json').write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 't05-overview.md').write_text(overview, encoding='utf-8')

    files = [('培养方案正文', 'program.md'), ('结构化方案', 'program.json'),
             ('红线与证据校验', 'validation.json'), ('课程开发任务包', 't05-package.json'),
             ('课程开发任务包总览', 't05-overview.md')]
    if docx_written:
        files.insert(1, ('培养方案Word版', 'program.docx'))
    manifest = {'files': [{'name': name, 'path': f'output/{out.name}/{file}',
                           'sha256': hashlib.sha256((out / file).read_bytes()).hexdigest()}
                          for name, file in files]}
    (out / 'program-files.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(out)
    if result['warnings']:
        print('警告：')
        for item in result['warnings']:
            print(f'  - {item}')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('validate', 'build', 'charts', 'page'):
        p = sub.add_parser(name)
        p.add_argument('program', type=Path)
        if name == 'build':
            p.add_argument('--no-docx', action='store_true')
        if name in ('charts', 'page'):
            p.add_argument('--work', type=Path, default=Path('work'))
    args = parser.parse_args()
    d = json.loads(args.program.read_text(encoding='utf-8'))
    if args.command == 'validate':
        result = validate(d)
        print(json.dumps({'errors': result['errors'], 'warnings': result['warnings'],
                          'computed': result['computed']}, ensure_ascii=False, indent=2))
        return 1 if result['errors'] else 0
    if args.command == 'charts':
        return charts(args.program, work=args.work)
    if args.command == 'page':
        return page(args.program, work=args.work)
    return build(args.program, skip_docx=args.no_docx)


if __name__ == '__main__':
    sys.exit(main())
