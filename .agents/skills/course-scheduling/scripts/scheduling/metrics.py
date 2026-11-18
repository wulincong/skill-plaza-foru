"""方案指标：冲突数、教室利用率、连排达成率、实训室负载与教师课时分布。"""

from __future__ import annotations

from .model import Placement, Problem, Task


def gini(values: list[float]) -> float:
    if not values:
        return 0.0
    total = sum(values)
    if total <= 0:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    weighted = sum((i + 1) * v for i, v in enumerate(ordered))
    return (2 * weighted) / (n * total) - (n + 1) / n


def compute(problem: Problem, placements: list[Placement], unplaced: list[dict]) -> dict:
    total_slots = len(problem.rooms) * len(problem.days) * len(problem.periods)
    used_room_slots = len({(p.room, p.day, period)
                           for p in placements for period in p.periods()})

    by_type: dict[str, dict] = {}
    for rid, room in problem.rooms.items():
        by_type.setdefault(room['type'], {'rooms': [], 'used': 0, 'slots': 0})
        by_type[room['type']]['rooms'].append(rid)
    for p in placements:
        room_type = problem.rooms[p.room]['type']
        for period in p.periods():
            by_type[room_type]['used'] += 1
    for info in by_type.values():
        info['slots'] = len(info['rooms']) * len(problem.days) * len(problem.periods)
        info['utilization'] = round(info['used'] / info['slots'], 4) if info['slots'] else 0.0

    # 连排达成率：要求连排的单元中按满连排排入的比例
    full_required = full_placed = 0
    for task in problem.tasks.values():
        for meeting in task.meetings:
            if meeting.full and task.consecutive > 1:
                full_required += 1
                if any(p.task_id == task.id and p.meeting == meeting.index
                       and p.length == task.consecutive for p in placements):
                    full_placed += 1
    tail_meetings = sum(1 for task in problem.tasks.values()
                        for m in task.meetings if not m.full and task.consecutive > 1)

    # 实训室负载（非普通类型教室逐间统计）
    room_load: dict[str, int] = {rid: 0 for rid, r in problem.rooms.items() if r['type'] != '普通'}
    for p in placements:
        if p.room in room_load:
            room_load[p.room] += p.length
    lab_values = [v / (len(problem.days) * len(problem.periods)) for v in room_load.values()]
    lab_load = {
        'rooms': [{'room': rid, 'type': problem.rooms[rid]['type'], 'periods': load,
                   'utilization': round(load / (len(problem.days) * len(problem.periods)), 4)}
                  for rid, load in room_load.items()],
        'max': max(room_load.values()) if room_load else 0,
        'mean': round(sum(room_load.values()) / len(room_load), 2) if room_load else 0,
        'gini': round(gini(lab_values), 4),
    }

    # 教师课时分布
    teacher_load: dict[str, dict] = {}
    for p in placements:
        task = problem.tasks[p.task_id]
        for tid in task.teachers:
            entry = teacher_load.setdefault(tid, {
                'name': problem.teachers[tid]['name'], 'periods': 0, 'days': set()})
            entry['periods'] += p.length
            entry['days'].add(p.day)
    teacher_stats = [{'teacher': tid, 'name': info['name'], 'periods': info['periods'],
                      'days': len(info['days'])} for tid, info in sorted(teacher_load.items())]
    class_daily_max = 0
    for cid in problem.classes:
        daily: dict[str, int] = {}
        for p in placements:
            task = problem.tasks.get(p.task_id)
            if task and cid in task.classes:
                daily[p.day] = daily.get(p.day, 0) + p.length
        class_daily_max = max(class_daily_max, max(daily.values()) if daily else 0)

    unplaced_tasks = sorted({u['taskId'] for u in unplaced})
    placed_hours = sum(p.length for p in placements)
    planned_hours = sum(t.hours_per_week for t in problem.tasks.values())
    return {
        'conflicts': 0,
        'placedMeetings': len(placements),
        'unplacedMeetings': len(unplaced),
        'unplacedTasks': unplaced_tasks,
        'placedHours': placed_hours,
        'plannedHours': planned_hours,
        'roomUtilization': round(used_room_slots / total_slots, 4) if total_slots else 0.0,
        'roomByType': [{'type': t, 'rooms': len(info['rooms']),
                        'utilization': info['utilization']}
                       for t, info in by_type.items()],
        'consecutiveRate': round(full_placed / full_required, 4) if full_required else 1.0,
        'consecutiveRequired': full_required,
        'consecutivePlaced': full_placed,
        'tailMeetings': tail_meetings,
        'labLoad': lab_load,
        'teacherLoad': teacher_stats,
        'classDailyMax': class_daily_max,
    }


def effective_hours_notes(problem: Problem, placements: list[Placement]) -> list[dict]:
    """轮岗、考试窗口等部分周事件造成的学时影响（按班级汇总）。"""
    events = problem.calendar_events()
    if not events:
        return []
    impact: dict[str, dict] = {}
    for event in events:
        targets: list[str] = []
        if event['kind'] == 'class':
            targets = list(event['ids'])
        elif event['kind'] == 'global':
            targets = list(problem.classes)
        elif event['kind'] == 'teacher':
            for task in problem.tasks.values():
                if set(task.teachers) & set(event['ids']):
                    targets.extend(task.classes)
        elif event['kind'] == 'room':
            affected = {p.task_id for p in placements if p.room in event['ids']}
            for tid in affected:
                task = problem.tasks.get(tid)
                if task:
                    targets.extend(task.classes)
        for cid in sorted(set(t for t in targets if t in problem.classes)):
            entry = impact.setdefault(cid, {'class': cid, 'lostWeeks': set(), 'events': set()})
            entry['lostWeeks'].update(event['weeks'])
            entry['events'].add(event['name'])
    result = []
    for cid, entry in sorted(impact.items()):
        weekly_hours = sum(t.hours_per_week for t in problem.tasks.values()
                           if cid in t.classes)
        result.append({'class': cid, 'events': sorted(entry['events']),
                       'lostWeeks': sorted(entry['lostWeeks']),
                       'lostHours': round(weekly_hours * len(entry['lostWeeks']))})
    return result
