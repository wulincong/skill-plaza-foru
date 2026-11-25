"""方案对比页面模型：从 solutions.json 生成 report-rendering 的 page.json。

数字全部取自求解结果，Agent 只在此基础上润色文字。
"""

from __future__ import annotations

import datetime

from .model import Problem

PLAN_LETTERS = {'A': '方案一', 'B': '方案二', 'C': '方案三'}


def _pct(value) -> str:
    try:
        return f'{float(value) * 100:.0f}%'
    except (TypeError, ValueError):
        return str(value)


def recommend_plan(solutions: dict) -> dict:
    """推荐规则：未排入最少 → 连排达成率最高 → 教室利用率最高。"""
    def rank(plan: dict):
        m = plan['metrics']
        return (m.get('unplacedMeetings', 0), -m.get('consecutiveRate', 0),
                -m.get('roomUtilization', 0))
    return min(solutions['plans'], key=rank)


def _timetable_table(problem: Problem, plan: dict, class_id: str) -> dict:
    grid: dict[tuple[int, str], list[str]] = {}
    for p in plan['placements']:
        task = problem.tasks[p['taskId']]
        if class_id not in task.classes:
            continue
        label = f"{task.course} @{p['room']}"
        for period in p['periods']:
            grid.setdefault((period, p['day']), []).append(label)
    rows = []
    for period in problem.period_ids:
        row = [problem.period_by_id[period].label]
        for day in problem.days:
            cells = grid.get((period, day), [])
            row.append('；'.join(cells) if cells else '')
        rows.append(row)
    return {
        'type': 'table', 'pattern': 'matrix',
        'title': f'{class_id} 班级课表（周模板）',
        'columns': [{'label': '节次', 'row_header': True}] + [{'label': d} for d in problem.days],
        'rows': rows,
        'note': '同一单元格多门课程表示不同教学单元；完整三视图（班级/教师/教室）见导出的课表文件。',
    }


def build_page(problem: Problem, solutions: dict) -> dict:
    plans = solutions['plans']
    best = recommend_plan(solutions)
    head = solutions['problem']
    today = datetime.date.today().isoformat()
    unplaced_total = best['metrics'].get('unplacedMeetings', 0)
    recommend_name = f"{PLAN_LETTERS.get(best['id'], best['id'])}（{best['name']}）"

    blocks: list[dict] = []
    if unplaced_total == 0:
        lead = f'推荐{recommend_name}：全部 {head["taskCount"]} 项教学任务零冲突排入。'
        text = (f'三套方案均满足教师、班级、教室、连排与占用时段等全部硬约束，冲突数为 0。'
                f'推荐方案连排达成率 {_pct(best["metrics"]["consecutiveRate"])}、'
                f'教室利用率 {_pct(best["metrics"]["roomUtilization"])}。')
    else:
        lead = f'推荐{recommend_name}，但有 {unplaced_total} 个教学单元未排入，需先决策放松项。'
        text = ('所有方案冲突数均为 0；未排入课程不出现在课表中，逐条归因见后文，'
                '建议按代价从低到高选择放松项后重排。')
    blocks.append({'type': 'summary', 'lead': lead, 'text': text,
                   'note': '课表为周模板；轮岗、考试窗口与假期对具体周次的影响见“有效学时影响”。'})

    blocks.append({'type': 'metrics', 'items': [
        {'label': '教学任务', 'value': head['taskCount'], 'unit': '项'},
        {'label': '冲突数', 'value': 0, 'unit': '处', 'note': '硬约束由求解保证'},
        {'label': '未排入单元', 'value': unplaced_total, 'unit': '个',
         'tone': 'attention' if unplaced_total else None},
        {'label': '连排达成率', 'value': _pct(best['metrics']['consecutiveRate'])},
        {'label': '教室利用率', 'value': _pct(best['metrics']['roomUtilization'])},
    ]})

    # 方案对比表
    columns = [{'label': '指标', 'row_header': True}] + [
        {'label': f'{PLAN_LETTERS.get(p["id"], p["id"])} {p["name"]}'} for p in plans]
    compare_rows = [
        ['未排入单元', *[p['metrics'].get('unplacedMeetings', 0) for p in plans]],
        ['排入学时', *[p['metrics'].get('placedHours', 0) for p in plans]],
        ['连排达成率', *[_pct(p['metrics'].get('consecutiveRate', 0)) for p in plans]],
        ['教室利用率', *[_pct(p['metrics'].get('roomUtilization', 0)) for p in plans]],
        ['实训室峰值负载', *[p['metrics'].get('labLoad', {}).get('max', 0) for p in plans]],
        ['实训室负载基尼', *[p['metrics'].get('labLoad', {}).get('gini', 0) for p in plans]],
        ['教师最多周课时', *[max((t['periods'] for t in (p['metrics'].get('teacherLoad') or [{'periods': 0}])), default=0) for p in plans]],
    ]
    blocks.append({'type': 'section', 'title': '方案对比', 'blocks': [
        {'type': 'text', 'text': '三套方案使用同一份任务与资源数据、不同软约束侧重：'
         '教师集中型减少教师到校天数，负载均衡型平滑班级与实训室负载，均衡折中型居中。'},
        {'type': 'table', 'pattern': 'comparison', 'title': '核心指标对比',
         'columns': columns, 'rows': compare_rows,
         'source': '求解器指标口径见输出契约；冲突数均为 0。'},
    ]})

    # 各方案要点 + 样例课表
    for plan in plans:
        sample_class = next((c for c in problem.classes
                             if any(c in problem.tasks[p['taskId']].classes
                                    for p in plan['placements'])), None)
        inner = [{'type': 'text', 'text': _plan_summary(problem, plan)}]
        if sample_class:
            inner.append(_timetable_table(problem, plan, sample_class))
        blocks.append({'type': 'section',
                       'title': f'{PLAN_LETTERS.get(plan["id"], plan["id"])} {plan["name"]}',
                       'blocks': inner})

    # 未排入归因
    if unplaced_total:
        rows = []
        for item in best['unplaced']:
            reason = '；'.join(f"{r['constraint']}（{r['count']} 处）" for r in item['reasons'][:2])
            rows.append([item['course'], '、'.join(item['classes']), '、'.join(item['teachers']),
                         f"{item['length']} 节", reason, '；'.join(item['suggestions'][:2])])
        blocks.append({'type': 'section', 'title': '未排入课程归因', 'blocks': [
            {'type': 'text', 'text': f'以下取自推荐方案{recommend_name}的求解结果。'
             '每条列出阻断的约束与建议放松项，按代价从低到高取舍后可重排。'},
            {'type': 'table', 'pattern': 'evidence', 'title': '未排入清单',
             'columns': [{'label': '课程'}, {'label': '班级'}, {'label': '教师'},
                         {'label': '单元'}, {'label': '阻断约束'}, {'label': '建议放松项'}],
             'rows': rows},
        ]})

    # 有效学时影响
    if solutions.get('effectiveHours'):
        rows = [[item['class'], '、'.join(item['events']),
                 '、'.join(f'第{w}周' for w in item['lostWeeks']), item['lostHours']]
                for item in solutions['effectiveHours']]
        blocks.append({'type': 'section', 'title': '有效学时影响', 'blocks': [
            {'type': 'text', 'text': '企业轮岗、技能等级考试窗口与假期会占用部分教学周，'
             '课表周模板不变，受影响周次的课次在日历导出中自动剔除，学时损失汇总如下。'},
            {'type': 'table', 'pattern': 'detail', 'title': '按班级学时损失',
             'columns': [{'label': '班级'}, {'label': '事件'}, {'label': '占用周次'},
                         {'label': '损失学时', 'numeric': True}],
             'rows': rows},
        ]})

    # 收尾：建议与适用条件
    closing = ['这组方案面向学期初整表排课：先确认未排入课程的取舍，再从三套方案中按教师到校成本、'
               '实训室负载的优先级选择；选定后可导出 Excel 课表与 ics 日历。']
    closing.append('学期中调停课建议走增量重排：保留原课表，仅调整受影响课程，变更清单留档可回退。')
    if solutions.get('effectiveHours'):
        closing.append('涉及轮岗批次的班级应在培养方案层面核对学时补偿，排课工具不自动压缩其他课程。')
    blocks.append({'type': 'section', 'title': '建议与适用条件', 'blocks': [
        {'type': 'text', 'text': ' '.join(closing)},
    ]})

    meta = [head['semester'], f'{head["weeks"]} 教学周', f'生成于 {today}']
    return {
        'title': f'{head["school"]}排课方案对比' if head['school'] else '排课方案对比',
        'subtitle': head['semester'],
        'eyebrow': '排课沙盘 · 方案对比',
        'meta': meta,
        'blocks': blocks,
        'footer': '优才知路技能广场 · 排课智能体生成，指标与课表可直接核对',
    }


def _plan_summary(problem: Problem, plan: dict) -> str:
    m = plan['metrics']
    teachers = m.get('teacherLoad', [])
    busiest = max(teachers, key=lambda t: t['periods'], default=None)
    parts = [
        f"排入 {m.get('placedMeetings', 0)} 个教学单元、{m.get('placedHours', 0)} 学时；"
        f"连排达成率 {_pct(m.get('consecutiveRate', 0))}，教室利用率 {_pct(m.get('roomUtilization', 0))}。"
    ]
    lab = m.get('labLoad', {})
    if lab.get('rooms'):
        top = max(lab['rooms'], key=lambda r: r['periods'])
        parts.append(f"实训室负载最高为 {top['room']}（{top['periods']} 节/周），基尼系数 {lab.get('gini', 0)}。")
    if busiest:
        parts.append(f"教师课时最高为 {busiest['name']}（{busiest['periods']} 节/周、{busiest['days']} 天到校）。")
    if m.get('unplacedMeetings'):
        parts.append(f"有 {m['unplacedMeetings']} 个单元未排入，见归因章节。")
    return ''.join(parts)
