#!/usr/bin/env python3
"""课程包契约校验与构建（course-package/1）。

用法：
  python3 course.py validate course.json
  python3 course.py build course.json

共享统计工件经 talent-data-query 的 inspect 离线核验；学时汇总、三栏对齐、
双向挂接与权重等硬规则在本脚本校验，通过后 build 写入 output/course-<sha10>/。
"""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

SCHEMA = 'course-package/1'
T05_SCHEMA = 't05-course-development/1'
RESULT_PATH = re.compile(r'^data/(tq-[0-9a-f-]{36})/result\.json$')
QUERY = Path(__file__).resolve().parents[2] / 'talent-data-query' / 'scripts' / 'query.mjs'
TEXT = lambda v: isinstance(v, str) and v.strip()


def fail(messages):
    raise SystemExit('校验未通过：\n' + '\n'.join(f'  - {m}' for m in messages))


def session_context():
    file = Path('course-input.json')
    return json.loads(file.read_text(encoding='utf-8')) if file.is_file() else None


def inspect_source(source):
    """tq 工件的文件与指纹核验交给共享查询技能的离线 inspect。"""
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
    if result['status'] not in ('complete', 'empty', 'partial') or not result['quality']['checks'] \
            or not all(item['pass'] for item in result['quality']['checks']) \
            or not result['consistency']['completeTransaction']:
        raise ValueError('query failed consistency checks')
    source.setdefault('published', '未标注')
    source.setdefault('accessed', read_at[:10])
    return result


def bind_metric(result, metric):
    binding = metric['binding']
    found = {item['metricId']: item for item in result['metrics']}
    if binding['metricId'] not in found:
        raise ValueError(f'工件中找不到指标 {binding["metricId"]}')
    item = found[binding['metricId']]
    if item['status'] != 'complete':
        raise ValueError(f'指标 {binding["metricId"]} 状态为 {item["status"]}，不可绑定数值')
    value = item
    for key in binding['field'].split('.'):
        if isinstance(value, list):
            if not key.isdecimal():
                raise ValueError('invalid row index')
            value = value[int(key)]
        else:
            value = value[key]
    if type(value) not in (int, float):
        raise ValueError('需要数值字段，如 value 或 rows.0.count；每个要引用的分组建一项指标')
    return value


def sample_rows(results):
    rows = []
    for result in results:
        for metric in result['metrics']:
            if metric['name'] == 'description.samples':
                rows.extend(metric.get('rows', []))
    return rows


def validate(d):
    errors, warnings, computed = [], [], []
    course = d

    def check(condition, message):
        if not condition:
            errors.append(message)

    def warn(condition, message):
        if not condition:
            warnings.append(message)

    check(isinstance(d, dict), 'course.json 必须为对象')
    if errors:
        return course, errors, warnings, computed
    check(d.get('schema') == SCHEMA, f'schema 必须为 {SCHEMA}')
    check(d.get('status') in ('draft', 'final'), 'status 必须为 draft/final')
    check(TEXT(d.get('asOf')) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', d['asOf']), 'asOf 为 YYYY-MM-DD')

    meta = d.get('meta')
    check(isinstance(meta, dict), 'meta 必须为对象')
    if isinstance(meta, dict):
        check(TEXT(meta.get('courseName')), 'meta.courseName 必填')
        check(TEXT(meta.get('positioning')), 'meta.positioning（课程定位）必填')
        weeks, total = meta.get('weeks'), meta.get('totalHours')
        check(isinstance(weeks, int) and 16 <= weeks <= 18, 'meta.weeks 必须为 16–18 的整数')
        for key in ('totalHours', 'theoryHours', 'practiceHours'):
            check(isinstance(meta.get(key), int) and meta[key] > 0, f'meta.{key} 必须为正整数')
        if all(isinstance(meta.get(k), int) for k in ('theoryHours', 'practiceHours', 'totalHours')):
            check(meta['theoryHours'] + meta['practiceHours'] == meta['totalHours'],
                  'theoryHours + practiceHours 必须等于 totalHours')
        check(isinstance(meta.get('semester'), int) and 1 <= meta['semester'] <= 8, 'meta.semester 为 1–8')
        check(isinstance(meta.get('credits'), (int, float)) and meta['credits'] > 0, 'meta.credits 必须为正数')
        positions = meta.get('targetPositions')
        check(isinstance(positions, list) and len(positions) >= 1, 'meta.targetPositions 至少一个目标岗位')
        if isinstance(positions, list) and positions:
            for p in positions:
                check(TEXT(p.get('name')) and (p.get('sourceIds') or p.get('metricIds')),
                      f'目标岗位 {p.get("name")} 需要可回溯来源（sourceIds 或 metricIds）')

    # T05 任务包一致性
    package = None
    if isinstance(meta, dict) and TEXT(meta.get('sourcePackage')):
        path = Path(meta['sourcePackage'])
        check(path.is_file(), f'任务包不存在：{meta["sourcePackage"]}')
        if path.is_file():
            package = json.loads(path.read_text(encoding='utf-8'))
            check(package.get('schema') == T05_SCHEMA, f'任务包 schema 必须为 {T05_SCHEMA}')
            check(TEXT(meta.get('courseId')), '使用任务包时 meta.courseId 必填')
            tasks = package.get('tasks', [])
            task = next((t for t in tasks if t.get('courseId') == meta.get('courseId')), None)
            check(task is not None, f'任务包中找不到课程 {meta.get("courseId")}')
            if task:
                check(meta.get('courseName') == task['courseName'], '课程名与任务包不一致')
                for key in ('theoryHours', 'practiceHours', 'credits'):
                    check(meta.get(key) == task.get(key), f'{key} 与任务包不一致（任务包 {task.get(key)}）')
                check(isinstance(meta.get('semester'), int) and meta['semester'] in (task.get('semesters') or []),
                      'semester 必须在任务包学期范围内')
                meta.setdefault('assessmentForm', task.get('assessment'))
                meta.setdefault('major', package.get('program'))
                meta.setdefault('programVersion', package.get('program', {}).get('version'))

    # sources / metrics
    sources, metrics = d.get('sources', []), d.get('metrics', [])
    ids = [s.get('id') for s in sources]
    check(len(ids) == len(set(ids)), 'source id 不得重复')
    by_id = {s['id']: s for s in sources if TEXT(s.get('id'))}
    results = {}
    for s in sources:
        check(TEXT(s.get('id')) and TEXT(s.get('title')), '每个来源需要 id 与 title')
        url = s.get('url', '')
        if url.startswith('data/tq-'):
            check(TEXT(url), '共享统计来源需要 url')
            try:
                results[s['id']] = inspect_source(s)
            except (ValueError, KeyError, IndexError, OSError, subprocess.SubprocessError) as exc:
                errors.append(f'来源 {s["id"]} 工件核验失败：{exc}')
        elif not url.startswith('uploads/') and not TEXT(s.get('excerpt')):
            errors.append(f'来源 {s["id"]} 需要原文摘录或 uploads 路径')
    for m in metrics:
        check(TEXT(m.get('id')) and TEXT(m.get('label')), '每个指标需要 id 与 label')
        check(bool(m.get('source_ids')), f'指标 {m.get("id")} 需要来源')
        if isinstance(m.get('binding'), dict):
            resolved = None
            for result in results.values():
                try:
                    resolved = bind_metric(result, m)
                    break
                except (ValueError, KeyError, IndexError):
                    continue
            check(resolved is not None, f'指标 {m["id"]} 的绑定在已核验工件中不可解析')
            if resolved is not None:
                if m.get('value') is None:
                    m['value'] = resolved
                else:
                    check(m['value'] == resolved, f'指标 {m["id"]} 手填数值与工件不符')

    # 典型工作任务：JD 原文可回溯
    rows = sample_rows(results.values())
    tasks = d.get('workTasks', [])
    check(len(tasks) >= 1, 'workTasks 至少一个典型工作任务')
    for t in tasks:
        check(TEXT(t.get('id')) and TEXT(t.get('name')), 'workTask 需要 id 与 name')
        refs = t.get('jdRefs', [])
        if refs:
            for ref in refs:
                row = next((r for r in rows if r.get('positionId') == ref.get('positionId')
                            and r.get('hash') == ref.get('hash')), None)
                check(row is not None, f'{t.get("id")} 的 JD 引用在工件样本中不存在或指纹不符')
                if row is not None and TEXT(ref.get('quote')):
                    check(ref['quote'] in row['excerpt'], f'{t.get("id")} 的 quote 不是样本原文的逐字摘录')
                check(TEXT(ref.get('quote')), f'{t.get("id")} 的 jdRef 需要逐字摘录 quote')
        else:
            check(bool(t.get('sourceIds')), f'{t.get("id")} 无 JD 引用时必须给用户材料来源')
            warnings.append(f'{t.get("id")} 未挂库内 JD 样本，任务表述仅由材料支撑')

    # 学习单元 / 三栏对齐 / 课时
    units = d.get('learningUnits', [])
    check(len(units) >= 2, 'learningUnits 至少两个学习单元')
    unit_ids = [u.get('id') for u in units]
    check(len(unit_ids) == len(set(unit_ids)), 'unit id 不得重复')
    task_ids = {t.get('id') for t in tasks}
    weeks = meta.get('weeks') if isinstance(meta, dict) else None
    covered_weeks, hours_sum = set(), 0
    for u in units:
        check(TEXT(u.get('id')) and TEXT(u.get('name')), 'unit 需要 id 与 name')
        check(isinstance(u.get('hours'), int) and u['hours'] > 0, f'{u.get("id")} hours 必须为正整数')
        hours_sum += u.get('hours') or 0
        check(bool(u.get('taskIds')), f'{u.get("id")} 必须覆盖至少一个典型工作任务')
        for tid in u.get('taskIds', []):
            check(tid in task_ids, f'{u.get("id")} 引用了不存在的任务 {tid}')
        unit_weeks = u.get('weeks', [])
        check(isinstance(unit_weeks, list) and unit_weeks, f'{u.get("id")} 需要周次列表')
        for w in unit_weeks:
            check(isinstance(w, int) and 1 <= w <= (weeks or 18), f'{u.get("id")} 周次 {w} 超出 1–{weeks}')
            covered_weeks.add(w)
    check(hours_sum == meta.get('totalHours'), f'单元课时合计 {hours_sum} 必须等于 totalHours {meta.get("totalHours")}')
    for tid in task_ids:
        check(any(tid in (u.get('taskIds') or []) for u in units), f'任务 {tid} 未被任何学习单元覆盖')

    outline = d.get('outline', [])
    outline_weeks = [row.get('week') for row in outline]
    expected_weeks = list(range(1, (weeks or 0) + 1))
    check(sorted(w for w in outline_weeks if isinstance(w, int)) == expected_weeks,
          f'outline 必须逐周覆盖 1–{weeks} 各一次')
    check(len(outline_weeks) == len(set(outline_weeks)), 'outline 周次不得重复')
    for row in outline:
        check(row.get('unitId') in unit_ids, f'第 {row.get("week")} 周 unitId 不存在')
        check(TEXT(row.get('content')) and TEXT(row.get('task')) and TEXT(row.get('assessment')),
              f'第 {row.get("week")} 周三栏（内容/任务/评价）非空')

    # 知识点：上挂能力项、下接考核点
    points = d.get('knowledgePoints', [])
    check(len(points) >= 1, 'knowledgePoints 至少一个')
    capability_ids = set()
    if package:
        for t in package.get('tasks', []):
            capability_ids.update(ref.get('capabilityId') for ref in t.get('capabilityRefs', []))
    point_ids = [p.get('id') for p in points]
    check(len(point_ids) == len(set(point_ids)), '知识点 id 不得重复')
    for p in points:
        check(TEXT(p.get('id')) and TEXT(p.get('text')), '知识点需要 id 与 text')
        check(p.get('type') in ('knowledge', 'skill'), f'{p.get("id")} type 必须为 knowledge/skill')
        check(p.get('unitId') in unit_ids, f'{p.get("id")} unitId 不存在')
        check(TEXT(p.get('capabilityId')), f'{p.get("id")} 必须上挂能力项 capabilityId')
        if TEXT(p.get('capabilityId')) and capability_ids and p['capabilityId'] not in capability_ids:
            check(bool(p.get('sourceIds')), f'{p.get("id")} 的能力项不在任务包中，需要用户材料来源')
        ap = p.get('assessmentPoint')
        check(isinstance(ap, dict) and TEXT(ap.get('form')) and TEXT(ap.get('criteria')) and TEXT(ap.get('passStandard')),
              f'{p.get("id")} 必须下接考核点（form/criteria/passStandard 齐全），无考核点的知识点不得进入大纲')
    for u in units:
        check(any(p.get('unitId') == u.get('id') for p in points), f'单元 {u.get("id")} 至少一个知识点')
    if package and isinstance(meta, dict) and TEXT(meta.get('courseId')):
        task = next((t for t in package.get('tasks', []) if t.get('courseId') == meta.get('courseId')), None)
        if task:
            for ref in task.get('capabilityRefs', []):
                if ref.get('level') == 'H':
                    warn(any(p.get('capabilityId') == ref.get('capabilityId') for p in points),
                         f'任务包高支撑能力项 {ref.get("capabilityId")} 未被任何知识点覆盖')

    # 单元教学设计样例与实训任务书：前两个模块成套
    samples = d.get('lessonSamples', [])
    first_two = unit_ids[:2]
    for uid in first_two:
        check(any(s.get('unitId') == uid for s in samples), f'单元 {uid} 缺少单元教学设计样例')
    period = (meta or {}).get('periodMinutes', 45)
    for s in samples:
        check(s.get('unitId') in unit_ids, f'教学设计 {s.get("title")} unitId 不存在')
        stages = s.get('stages', [])
        check(len(stages) >= 3, f'{s.get("title")} 教学环节至少 3 个（导入/展开/收束）')
        check(all(TEXT(st.get('phase')) and isinstance(st.get('minutes'), int) and st['minutes'] > 0
                  and TEXT(st.get('teacher')) and TEXT(st.get('student')) for st in stages),
              f'{s.get("title")} 每个环节需要 phase/minutes/teacher/student')
        warn(sum(st.get('minutes', 0) for st in stages) == s.get('hours', 0) * period,
             f'{s.get("title")} 环节分钟合计与课时（{s.get("hours")}×{period} 分钟）不一致')
    trainings = d.get('trainingTasks', [])
    for uid in first_two:
        check(any(t.get('unitId') == uid for t in trainings), f'单元 {uid} 缺少实训任务书')
    for t in trainings:
        check(TEXT(t.get('id')) and TEXT(t.get('title')) and TEXT(t.get('background')), f'{t.get("id")} 任务书需要标题与背景')
        check(t.get('unitId') in unit_ids, f'{t.get("id")} unitId 不存在')
        check(bool(t.get('requirements')) and bool(t.get('deliverables')), f'{t.get("id")} 需要要求与成果清单')
        scoring = t.get('scoring', [])
        check(bool(scoring), f'{t.get("id")} 需要评分要点')
        check(sum(item.get('weight', 0) for item in scoring) == 100, f'{t.get("id")} 评分权重合计必须为 100')
        check(all(TEXT(item.get('item')) and TEXT(item.get('standard')) for item in scoring), f'{t.get("id")} 评分要点需要条目与标准')
        check(TEXT(t.get('passStandard')), f'{t.get("id")} 必须写合格标准')
        warn(bool(t.get('safetyNotes')), f'{t.get("id")} 未写安全注意事项，涉设备操作时需教师确认')

    # 评价方案
    plan = d.get('assessmentPlan')
    check(isinstance(plan, dict), 'assessmentPlan 必填')
    if isinstance(plan, dict):
        forms = plan.get('forms', [])
        check(bool(forms), '评价方案至少一种考核形式')
        check(sum(f.get('weight', 0) for f in forms) == 100, '考核形式权重合计必须为 100')
        for f in forms:
            check(TEXT(f.get('form')) and TEXT(f.get('method')), '每种考核形式需要名称与评分方法')
            check(bool(f.get('points')), f'{f.get("form")} 必须挂接知识点考核点')
            for pid in f.get('points', []):
                check(pid in point_ids, f'{f.get("form")} 引用了不存在的知识点 {pid}')
        check(TEXT(plan.get('passStandard')), '课程级合格标准必填')

    # 资源缺口
    for g in d.get('resourceGaps', []):
        check(g.get('type') in ('generated', 'manual'), f'资源缺口 {g.get("item")} type 必须为 generated/manual')
        check(TEXT(g.get('item')), '资源缺口需要条目')
        if g.get('type') == 'generated':
            warn(TEXT(g.get('consumer')), f'生成类缺口 {g.get("item")} 建议注明下游技能（如 courseware-studio）')

    # 标准合规逐条核对
    checks = d.get('complianceChecks', [])
    check(len(checks) >= 1, 'complianceChecks 至少一条核对')
    pending = 0
    for c in checks:
        check(TEXT(c.get('item')), '核对条目需要名称')
        check(c.get('status') in ('conform', 'conflict', 'pending'), f'{c.get("item")} status 必须为 conform/conflict/pending')
        if c.get('status') in ('conform', 'conflict'):
            check(TEXT(c.get('standardExcerpt')), f'{c.get("item")} 必须附标准原文摘录')
            check(TEXT(c.get('sourceId')) and c['sourceId'] in by_id, f'{c.get("item")} 来源不可解析')
        if c.get('status') == 'conflict':
            check(TEXT(c.get('suggestion')), f'{c.get("item")} 冲突项必须给处理建议，不静默改写')
        if c.get('status') == 'pending':
            pending += 1
    if pending:
        warnings.append(f'{pending} 条标准核对为 pending，定稿前需用户决策')

    # 决策留痕
    context = session_context()
    corpus = None
    if context:
        corpus = '\n'.join([context.get('message', '')] + [str(m) for m in context.get('earlierMessages', [])])
    for dec in d.get('decisions', []):
        check(TEXT(dec.get('question')) and TEXT(dec.get('userReply')), '决策记录需要问题与用户原话')
        if corpus is not None:
            check(dec.get('userReply') in corpus, f'决策 {dec.get("id")} 的 userReply 不在本会话用户消息中')
    if d.get('status') == 'final':
        check(not d.get('openDecisions'), 'status=final 时 openDecisions 必须为空')
        if pending:
            authorized = any(dec.get('scope') == 'standards' and TEXT(dec.get('userReply'))
                             for dec in d.get('decisions', []))
            check(authorized, f'{pending} 条标准核对 pending 且 status=final，需要 scope=standards 的用户授权决策')
    if context is None:
        warnings.append('未提供 course-input.json，决策原话未回查会话消息')

    computed = {'units': len(units), 'weeks': weeks, 'hoursSum': hours_sum,
                'knowledgePoints': len(points), 'jdSamples': len(rows), 'pendingChecks': pending}
    return course, errors, warnings, computed


def markdown(d):
    meta = d['meta']
    lines = [f'# {meta["courseName"]}课程包', '',
             f'状态：{d["status"]}；证据截止：{d["asOf"]}；{meta["weeks"]} 周 / {meta["totalHours"]} 课时'
             f'（理论 {meta["theoryHours"]} + 实践 {meta["practiceHours"]}），第 {meta["semester"]} 学期，{meta["credits"]} 学分。', '',
             '## 一、课程定位与设计依据', '', meta['positioning'], '',
             f'目标岗位：{"、".join(p["name"] for p in meta.get("targetPositions", []))}。', '',
             '## 二、课程整体设计（模块·任务·评价）', '',
             '| 周次 | 模块 | 内容 | 任务 | 评价 |', '|---|---|---|---|---|']
    unit_name = {u['id']: u['name'] for u in d.get('learningUnits', [])}
    for row in d.get('outline', []):
        lines.append(f'| {row["week"]} | {unit_name.get(row["unitId"], row["unitId"])} | {row["content"]} | {row["task"]} | {row["assessment"]} |')
    lines += ['', '学习单元与典型工作任务的对应：', '']
    for u in d.get('learningUnits', []):
        tasks = '、'.join(t['name'] for t in d['workTasks'] if t['id'] in u.get('taskIds', []))
        lines.append(f'- {u["name"]}（{u["hours"]} 课时，第 {u["weeks"][0]}–{u["weeks"][-1]} 周）：{tasks}')
    lines += ['', '## 三、知识点与技能点清单', '',
              '| 编号 | 类型 | 内容 | 能力项 | 考核点 | 合格标准 |', '|---|---|---|---|---|---|']
    for p in d.get('knowledgePoints', []):
        ap = p['assessmentPoint']
        lines.append(f'| {p["id"]} | {"知识" if p["type"] == "knowledge" else "技能"} | {p["text"]} | {p["capabilityId"]}'
                     f' | {ap["form"]}：{ap["criteria"]} | {ap["passStandard"]} |')
    lines += ['', '## 四、单元教学设计样例（前两个模块）', '']
    for s in d.get('lessonSamples', []):
        lines += [f'### {s["title"]}（{unit_name.get(s["unitId"], s["unitId"])}，{s["hours"]} 课时）', '',
                  '| 环节 | 时长 | 教师活动 | 学生活动 |', '|---|---|---|---|']
        for st in s['stages']:
            lines.append(f'| {st["phase"]} | {st["minutes"]} 分钟 | {st["teacher"]} | {st["student"]} |')
        lines.append('')
    lines += ['## 五、实训任务书', '']
    for t in d.get('trainingTasks', []):
        lines += [f'### {t["title"]}（{unit_name.get(t["unitId"], t["unitId"])}）', '', t['background'], '',
                  '要求：' + '；'.join(t['requirements']) + '。', '', '成果：' + '；'.join(t['deliverables']) + '。', '',
                  '| 评分要点 | 权重 | 标准 |', '|---|---|---|']
        for item in t['scoring']:
            lines.append(f'| {item["item"]} | {item["weight"]}% | {item["standard"]} |')
        lines += ['', f'合格标准：{t["passStandard"]}。', '']
        if t.get('safetyNotes'):
            lines += ['安全注意事项：' + '；'.join(t['safetyNotes']) + '。', '']
    plan = d['assessmentPlan']
    lines += ['## 六、课程评价方案', '', '| 形式 | 权重 | 挂接考核点 | 评分方法 |', '|---|---|---|---|']
    for f in plan['forms']:
        lines.append(f'| {f["form"]} | {f["weight"]}% | {"、".join(f["points"])} | {f["method"]} |')
    lines += ['', f'合格标准：{plan["passStandard"]}。补考：{plan.get("resit", "按学校规定")}。', '',
              '## 七、资源缺口清单', '', '| 缺口 | 类型 | 去向 | 说明 |', '|---|---|---|---|']
    for g in d.get('resourceGaps', []):
        lines.append(f'| {g["item"]} | {"生成（交 " + g.get("consumer", "下游技能") + "）" if g["type"] == "generated" else "人工准备"}'
                     f' | {g.get("consumer", "—")} | {g.get("note", "")} |')
    lines += ['', '## 八、标准合规核对表', '', '| 条目 | 结论 | 原文摘录 | 课程对应 | 建议 |', '|---|---|---|---|---|']
    verdict = {'conform': '符合', 'conflict': '冲突', 'pending': '待核对'}
    for c in d.get('complianceChecks', []):
        lines.append(f'| {c["item"]} | {verdict[c["status"]]} | {c.get("standardExcerpt", "—")}'
                     f' | {c.get("courseRef", "—")} | {c.get("suggestion") or "—"} |')
    lines += ['', '## 九、决策记录与未决事项', '']
    for dec in d.get('decisions', []):
        lines.append(f'- {dec["question"]} → 用户：「{dec["userReply"]}」')
    if d.get('openDecisions'):
        lines += ['', '待课程组决策：']
        lines += [f'- {q["question"]}（选项：{" / ".join(q.get("options", []))}）' for q in d['openDecisions']]
    else:
        lines.append('- 暂无未决事项。')
    lines.append('')
    return '\n'.join(lines)


def build(d, workspace):
    course, errors, warnings, computed = validate(d)
    if errors:
        fail(errors)
    digest = hashlib.sha256(json.dumps(d, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:10]
    out = Path(workspace) / 'output' / f'course-{digest}'
    out.mkdir(parents=True, exist_ok=True)
    files = {
        'course.md': markdown(d) + '\n',
        'course.json': json.dumps(d, ensure_ascii=False, indent=2) + '\n',
        'validation.json': json.dumps({'schema': 'course-validation/1', 'errors': errors, 'warnings': warnings,
                                       'computed': computed}, ensure_ascii=False, indent=2) + '\n',
    }
    manifest = []
    for name, content in files.items():
        (out / name).write_text(content, encoding='utf-8')
        manifest.append({'name': name, 'path': str((out / name).relative_to(workspace)),
                         'sha256': hashlib.sha256((out / name).read_bytes()).hexdigest()})
    (out / 'course-files.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(out)
    for item in warnings:
        print(f'警告：{item}')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('validate', 'build'):
        p = sub.add_parser(name)
        p.add_argument('course', type=Path)
    args = parser.parse_args()
    d = json.loads(args.course.read_text(encoding='utf-8'))
    if args.command == 'validate':
        course, errors, warnings, computed = validate(d)
        print(json.dumps({'errors': errors, 'warnings': warnings, 'computed': computed},
                         ensure_ascii=False, indent=2))
        return 1 if errors else 0
    return build(d, Path.cwd())


if __name__ == '__main__':
    raise SystemExit(main())
