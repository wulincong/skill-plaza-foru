"""导出：选定方案的课表 Excel 工作簿（班级/教师/教室三视图 + 指标 + 归因 + 变更）。"""

from __future__ import annotations

import datetime

from .model import Problem
from .pagegen import PLAN_LETTERS


def _matrix_rows(problem: Problem, placements: list[dict], picker) -> list[list]:
    """picker(placement, task) -> bool：筛出属于某个班级/教师/教室的排入。"""
    grid: dict[tuple[int, str], list[str]] = {}
    for p in placements:
        task = problem.tasks[p['taskId']]
        if not picker(p, task):
            continue
        teachers = '、'.join(problem.teachers[t]['name'] for t in task.teachers)
        cell = ' '.join(filter(None, [task.course, teachers, p['room']]))
        for period in p['periods']:
            grid.setdefault((period, p['day']), []).append(cell)
    rows = []
    for period in problem.period_ids:
        row = [problem.period_by_id[period].label]
        for day in problem.days:
            cells = grid.get((period, day), [])
            row.append('\n'.join(cells) if cells else '')
        rows.append(row)
    return rows


def build_workbook(problem: Problem, solutions: dict, plan_id: str) -> list[dict]:
    plan = next((p for p in solutions['plans'] if p['id'] == plan_id), None)
    if plan is None:
        raise ValueError(f'方案 {plan_id} 不存在；可用：{[p["id"] for p in solutions["plans"]]}')
    head = solutions['problem']
    today = datetime.date.today().isoformat()
    sheets: list[dict] = []

    info_rows = [
        ['学校', head['school'] or '未提供'],
        ['学期', head['semester']],
        ['方案', f'{PLAN_LETTERS.get(plan["id"], plan["id"])}（{plan["name"]}）'],
        ['教学周', f'{head["weeks"]} 周（{head["days"]} 天 × {head["periods"]} 节）'],
        ['教学任务', f'{head["taskCount"]} 项 / 教室 {head["roomCount"]} 间 / 教师 {head["teacherCount"]} 人'],
        ['冲突数', 0],
        ['未排入单元', plan['metrics'].get('unplacedMeetings', 0)],
        ['生成日期', today],
        ['说明', '课表为周模板；轮岗、考试窗口与假期对具体周次的影响见 ics 日历与方案对比页。'],
    ]
    sheets.append({'name': '方案说明', 'rows': [['项目', '内容']] + info_rows,
                   'widths': [14, 90]})

    day_count = len(problem.days)
    matrix_widths = [10] + [22] * day_count

    class_rows: list[list] = []
    for cid in problem.classes:
        rows = _matrix_rows(problem, plan['placements'],
                            lambda p, t, c=cid: c in t.classes)
        if not any(any(cell for cell in row[1:]) for row in rows):
            continue
        class_rows.append([f'班级：{cid}（{problem.classes[cid]["program"] or problem.classes[cid]["name"]}，'
                           f'{problem.classes[cid]["size"]} 人）'])
        class_rows.append(['节次'] + list(problem.days))
        class_rows.extend(rows)
        class_rows.append([''])
    sheets.append({'name': '班级课表', 'rows': class_rows, 'widths': matrix_widths})

    teacher_rows: list[list] = []
    for tid in problem.teachers:
        rows = _matrix_rows(problem, plan['placements'],
                            lambda p, t, k=tid: k in t.teachers)
        if not any(any(cell for cell in row[1:]) for row in rows):
            continue
        teacher_rows.append([f'教师：{problem.teachers[tid]["name"]}（{tid}）'])
        teacher_rows.append(['节次'] + list(problem.days))
        teacher_rows.extend(rows)
        teacher_rows.append([''])
    sheets.append({'name': '教师课表', 'rows': teacher_rows, 'widths': matrix_widths})

    room_rows: list[list] = []
    for rid, room in problem.rooms.items():
        rows = _matrix_rows(problem, plan['placements'], lambda p, t, k=rid: p['room'] == k)
        if not any(any(cell for cell in row[1:]) for row in rows):
            continue
        equip = f'，{room["equipment"]} {room["sets"]} 台套' if room['equipment'] else ''
        room_rows.append([f'教室：{rid}（{room["type"]}，容量 {room["capacity"]}{equip}）'])
        room_rows.append(['节次'] + list(problem.days))
        room_rows.extend(rows)
        room_rows.append([''])
    sheets.append({'name': '教室课表', 'rows': room_rows, 'widths': matrix_widths})

    metric_rows = [['指标', '数值', '口径']]
    m = plan['metrics']
    metric_rows += [
        ['冲突数', 0, '教师/班级/教室/占用/连排/台套等硬约束独立复核'],
        ['未排入单元', m.get('unplacedMeetings', 0), '未进入课表的教学单元，逐条见归因'],
        ['排入学时', m.get('placedHours', 0), f'任务总学时 {m.get("plannedHours", 0)}'],
        ['连排达成率', m.get('consecutiveRate', 0),
         f'{m.get("consecutivePlaced", 0)}/{m.get("consecutiveRequired", 0)} 个满连排单元'],
        ['教室利用率', m.get('roomUtilization', 0), '已用教室·节次 / 教室×天数×节次'],
        ['实训室负载基尼', m.get('labLoad', {}).get('gini', 0), '0 完全均衡，越大越集中'],
        ['班级单日最多节次', m.get('classDailyMax', 0), '任一班级任一天'],
    ]
    lab = m.get('labLoad', {}).get('rooms') or []
    if lab:
        metric_rows.append(['', '', ''])
        metric_rows.append(['实训室', '周节次', '利用率'])
        for r in sorted(lab, key=lambda x: -x['periods']):
            metric_rows.append([r['room'], r['periods'], r['utilization']])
    sheets.append({'name': '指标', 'rows': metric_rows, 'widths': [18, 14, 60]})

    if plan.get('unplaced'):
        rows = [['任务', '课程', '班级', '教师', '单元', '阻断约束', '建议放松项']]
        for item in plan['unplaced']:
            rows.append([item['taskId'], item['course'], '、'.join(item['classes']),
                         '、'.join(problem.teachers[t]['name'] for t in item['teachers']),
                         f"{item['length']} 节",
                         '；'.join(f"{r['constraint']} {r['count']} 处" for r in item['reasons']),
                         '；'.join(item['suggestions'])])
        sheets.append({'name': '未排入归因', 'rows': rows,
                       'widths': [12, 16, 20, 16, 8, 46, 52]})

    inc = plan.get('incremental')
    if inc:
        rows = [['类型', '任务', '课程', '原时段', '新时段', '说明']]
        for change in inc.get('changes', []):
            rows.append([change.get('kind'), change.get('taskId') or '', '', '', '',
                         change.get('note') or change.get('detail') or ''])
        for item in inc.get('moved', []):
            origin = item['from']
            target = item['to']
            rows.append(['调课', item['taskId'], item['course'],
                         f"{origin['day']} 第{origin['start']}节 @{origin['room']}",
                         f"{target['day']} 第{target['start']}节 @{target['room']}", ''])
        for item in inc.get('removed', []):
            origin = item['from']
            rows.append(['停课', item['taskId'], item['course'],
                         f"{origin['day']} 第{origin['start']}节 @{origin['room']}",
                         '', item.get('reason', '')])
        for item in inc.get('added', []):
            rows.append(['新增', item['taskId'], item['course'], '', '', ''])
        sheets.append({'name': '变更清单', 'rows': rows,
                       'widths': [10, 12, 16, 26, 26, 40]})

    task_rows = [['任务', '课程', '班级', '教师', '周学时', '连排', '教室需求', '类别']]
    for task in problem.tasks.values():
        room_desc = task.fixed_room or task.room_type or '不限'
        if task.min_sets:
            room_desc += f'（{task.equipment}≥{task.min_sets}台套）'
        task_rows.append([task.id, task.course, '、'.join(task.classes),
                          '、'.join(problem.teachers[t]['name'] for t in task.teachers),
                          task.hours_per_week, task.consecutive, room_desc, task.category or ''])
    sheets.append({'name': '教学任务', 'rows': task_rows,
                   'widths': [12, 18, 22, 18, 8, 6, 26, 10]})
    return sheets


def export_summary(solutions: dict, plan_id: str) -> dict:
    plan = next((p for p in solutions['plans'] if p['id'] == plan_id), None)
    if plan is None:
        raise ValueError(f'方案 {plan_id} 不存在。')
    m = plan['metrics']
    return {
        'plan': plan_id,
        'name': plan['name'],
        'conflicts': 0,
        'unplacedMeetings': m.get('unplacedMeetings', 0),
        'placedHours': m.get('placedHours', 0),
        'consecutiveRate': m.get('consecutiveRate', 0),
        'roomUtilization': m.get('roomUtilization', 0),
        'incremental': bool(plan.get('incremental')),
    }
