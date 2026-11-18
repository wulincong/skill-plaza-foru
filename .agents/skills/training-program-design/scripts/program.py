#!/usr/bin/env python3
"""Validate training-program contracts, check hour/credit redlines, build deliverables."""
import argparse
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
               'graduation', 'cultivation'], 'program')
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
            check(obj.get('id') not in index[group], f'{group}: duplicate {obj.get("id")}')
            if isinstance(obj, dict) and isinstance(obj.get('id'), str):
                index[group][obj['id']] = obj
    shared = {}
    for s in index['sources'].values():
        url = s.get('url', '')
        if isinstance(url, str) and url.startswith('data/'):
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
            check(cap.get('id') not in caps, f'capability duplicate {cap.get("id")}')
            caps[cap.get('id')] = cap
    for group in d.get('jobGroups') if isinstance(d.get('jobGroups'), list) else []:
        fields(group, ['id', 'name', 'summary', 'positions', 'workTasks'], 'jobGroups')
        for pos in group.get('positions', []):
            fields(pos, ['name', 'stage'], 'position')
            check(pos.get('stage') in ('entry', 'development'), f'position stage invalid: {pos.get("name")}')
            refs = (pos.get('metricIds') or []) + (pos.get('sourceIds') or [])
            check(bool(refs), f'{group.get("id")}/{pos.get("name")}: 岗位须绑定指标或来源')
            resolvable(pos.get('metricIds') or [], 'metrics', index)
            resolvable(pos.get('sourceIds') or [], 'sources', index)
        for task in group.get('workTasks', []):
            fields(task, ['id', 'name'], 'workTask')
            check(bool(task.get('capabilityIds')), f'{task.get("id")}: 工作任务须连接能力项')
            for cap_id in task.get('capabilityIds') or []:
                check(cap_id in caps, f'{task.get("id")}: unresolved capability {cap_id}')
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
        for entry in item.get('items', []):
            fields(entry, ['text'], 'spec item')
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
        ratio = (c['theoryHours'] + c['practiceHours']) / c['credits']
        warn(14 <= ratio <= 30, f'{c.get("id")}: 学时学分比 {ratio:.0f}:1 超出常见区间 14–30')

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

    # assurance：supported 须引用用户材料
    assurance = d.get('assurance') or {}
    for key, item in assurance.items():
        if isinstance(item, dict):
            check(item.get('status') in ('supported', 'pending'), f'assurance.{key}: invalid status')
            if item.get('status') == 'supported':
                check(bool(item.get('text')) and bool(item.get('sourceIds')),
                      f'assurance.{key}: supported 须有说明与来源')
                resolvable(item.get('sourceIds') or [], 'sources', index)
            else:
                warnings.append(f'实施保障「{key}」待补：未获得用户材料')

    # graduation
    graduation = d.get('graduation') or {}
    check(isinstance(graduation.get('requirements'), list) and bool(graduation['requirements']),
          'graduation.requirements required')

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


def docx_paragraph(text, style=None, bold=False):
    rpr = '<w:rPr><w:b/></w:rPr>' if bold else ''
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ''
    return f'<w:p>{ppr}<w:r>{rpr}<w:t xml:space="preserve">{esc(text)}</w:t></w:r></w:p>'


def docx_table(rows):
    width = max(1, int(9360 / max(1, len(rows[0]))))
    xml = ['<w:tbl><w:tblPr><w:tblBorders>',
           *['<w:{side} w:val="single" w:sz="4" w:color="999999"/>'.format(side=side)
             for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV')],
           '</w:tblBorders></w:tblPr>']
    for i, row in enumerate(rows):
        xml.append('<w:tr>')
        for cell in row:
            bold = '<w:rPr><w:b/></w:rPr>' if i == 0 else ''
            xml.append(f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/></w:tcPr>'
                       f'<w:p><w:r>{bold}<w:t xml:space="preserve">{esc(cell)}</w:t></w:r></w:p></w:tc>')
        xml.append('</w:tr>')
    xml.append('</w:tbl>')
    return ''.join(xml)


def write_docx(path, blocks):
    body = []
    for block in blocks:
        if block[0] in ('h1', 'h2', 'h3'):
            body.append(docx_paragraph(block[1], style='Heading' + block[0][1]))
        elif block[0] == 'p':
            body.append(docx_paragraph(block[1]))
        elif block[0] == 'table':
            body.append(docx_table(block[1]))
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
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
           '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
           '<Application>training-program-design</Application></Properties>')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', CONTENT_TYPES)
        archive.writestr('_rels/.rels', RELS)
        archive.writestr('docProps/core.xml', core)
        archive.writestr('docProps/app.xml', app)
        archive.writestr('word/_rels/document.xml.rels', DOC_RELS)
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


def compose_blocks(d):
    """Shared content model: list of (kind, payload); payload is rows for tables."""
    meta = d['meta']
    computed = d['computed']
    caps = {}
    for domain in d['capabilityDomains']:
        for cap in domain['capabilities']:
            caps[cap['id']] = {'cap': cap, 'domain': domain['name']}
    source_index = {s['id']: s for s in d['sources']}
    metric_index = {m['id']: m for m in d['metrics']}
    support = {}
    for c in d['curriculum']['courses']:
        for ref in c.get('domains', []) or []:
            support.setdefault(ref['capabilityId'], []).append((c['name'], ref['level']))
    redlines = validation_rows(d)

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
        ('table', [['岗位群', '代表岗位', '阶段', '依据']] + [
            [group['name'], pos['name'],
             '初始岗' if pos['stage'] == 'entry' else '发展岗',
             '、'.join([*[f"指标 {m}" for m in pos.get('metricIds', [])],
                        *[f"来源 {s}" for s in pos.get('sourceIds', [])]]) or '—']
            for group in d['jobGroups'] for pos in group.get('positions', [])]),
        ('h2', '五、培养目标与培养规格'),
        ('p', d['cultivation']['goal']),
        ('p', '目标依据：'
              + (f"标准来源 {d['cultivation']['goalBasis'].get('standardSourceId')}"
                 if d['cultivation']['goalBasis'].get('standardSourceId')
                 else '标准原文待核对（已获用户决策按待核对继续），目标在区域岗位证据基础上拟定，待标准原文核对后回填')
              + (f"、区域证据 {'、'.join(d['cultivation']['goalBasis'].get('metricIds', []))}"
                 if d['cultivation']['goalBasis'].get('metricIds') else '')),
    ]
    for item in d['cultivation']['spec']:
        blocks.append(('h3', f"培养规格 · {item['dimension']}"))
        blocks.append(('table', [['条目', '关联能力/来源']] + [
            [entry['text'],
             f"能力 {entry['capabilityId']}" if entry.get('capabilityId')
             else '、'.join(f"来源 {s}" for s in entry.get('sourceIds', [])) or '—']
            for entry in item.get('items', [])]))
    blocks += [
        ('h2', '六、课程设置及要求'),
        ('h3', '6.1 工作任务与职业能力分析'),
        ('table', [['岗位群', '典型工作任务', '支撑能力项']] + [
            [group['name'], task['name'], '、'.join(task['capabilityIds'])]
            for group in d['jobGroups'] for task in group.get('workTasks', [])]),
        ('h3', '6.2 课程体系'),
        ('table', [['课程', '类别', '理论学时', '实践学时', '学分', '开设学期', '考核']] + [
            [c['name'], CATEGORY_NAMES[c['category']], c['theoryHours'], c['practiceHours'],
             c['credits'], '、'.join(f'第{s}学期' for s in c['semesters']), c['assessment']]
            for c in sorted(d['curriculum']['courses'], key=lambda c: (c['category'], c['semesters']))]),
        ('h3', '6.3 专业核心课程设置理由与证据链'),
        ('table', [['核心课程', '设置理由', '证据']] + [
            [c['name'], c['rationale']['text'],
             '、'.join([*[f"指标 {m}" for m in c['rationale'].get('metricIds', [])],
                        *[f"来源 {s}" for s in c['rationale'].get('sourceIds', [])]])]
            for c in d['curriculum']['courses'] if c['category'] == 'professional-core']),
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
        ('h2', '九、实施保障'),
    ]
    labels = {'faculty': '师资队伍', 'facilities': '教学设施与实训条件', 'cooperation': '校企合作'}
    for key, label in labels.items():
        item = d['assurance'].get(key) or {}
        status = '已依据用户提供材料' if item.get('status') == 'supported' else '待补（未获得用户材料）'
        blocks.append(('h3', f"9.{list(labels).index(key) + 1} {label}"))
        blocks.append(('p', f"{item.get('text') or '待补'}（{status}"
                           + (f"；来源 {'、'.join(item.get('sourceIds', []))}" if item.get('sourceIds') else '') + '）'))
    blocks += [
        ('h2', '十、毕业要求'),
        ('p', '；'.join(d['graduation']['requirements'])
              + (f"。毕业最低学分 {d['graduation'].get('minCredits', computed['totalCredits'])}"
                 f"（课程总学分 {computed['totalCredits']}）")),
        ('h2', '十一、编制说明与决策记录'),
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
            [m['id'], m['label'], m['value'], m['unit'], m['region'], m['population'],
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
            ('p', f"对比基准：{source_index[diff['basis']]['title']}"),
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
    out = []
    for kind, payload in blocks:
        if kind == 'h1':
            out.append(f'# {payload}')
        elif kind == 'h2':
            out.append(f'## {payload}')
        elif kind == 'h3':
            out.append(f'### {payload}')
        elif kind == 'p':
            out.append(payload)
        elif kind == 'table':
            out.append(md_table(payload))
        out.append('')
    return '\n'.join(out).rstrip() + '\n'


def build_t05(d):
    tasks = []
    for c in d['curriculum']['courses']:
        tasks.append({
            'courseId': c['id'], 'courseName': c['name'], 'category': c['category'],
            'credits': c['credits'], 'theoryHours': c['theoryHours'], 'practiceHours': c['practiceHours'],
            'semesters': c['semesters'], 'assessment': c['assessment'],
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
    (out / 'program.md').write_text(blocks_markdown(blocks), encoding='utf-8')
    (out / 'program.json').write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
    validation = {'program': d['meta']['majorName'], 'version': d['meta']['version'], 'as_of': d['as_of'],
                  'status': d['status'], 'computed': computed,
                  'redlines': validation_rows(d)[1:], 'errors': result['errors'],
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
    for name in ('validate', 'build'):
        p = sub.add_parser(name)
        p.add_argument('program', type=Path)
        if name == 'build':
            p.add_argument('--no-docx', action='store_true')
    args = parser.parse_args()
    d = json.loads(args.program.read_text(encoding='utf-8'))
    if args.command == 'validate':
        result = validate(d)
        print(json.dumps({'errors': result['errors'], 'warnings': result['warnings'],
                          'computed': result['computed']}, ensure_ascii=False, indent=2))
        return 1 if result['errors'] else 0
    return build(args.program, skip_docx=args.no_docx)


if __name__ == '__main__':
    sys.exit(main())
