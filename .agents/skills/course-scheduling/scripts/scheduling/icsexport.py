"""ics 日历导出：把周课表模板展开为带 RRULE/EXDATE 的 VEVENT 序列。

时间使用本地浮动时间（不带时区），周课表按校历第 1 周周一起算；
假期、考试窗口、企业轮岗等部分周事件通过 EXDATE 剔除相应次课。
"""

from __future__ import annotations

import datetime

from .model import WEEKDAY_INDEX, Placement, Problem

PRODID = '-//FORU 优才知路//Course Scheduling//CN'


def _fold(line: str) -> list[str]:
    """按 75 字节折叠，不在多字节字符中间断开。"""
    raw = line.encode('utf-8')
    if len(raw) <= 75:
        return [line]
    parts: list[str] = []
    current = ''
    width = 0
    for ch in line:
        size = len(ch.encode('utf-8'))
        limit = 75 if not parts else 74  # 续行以空格开头
        if width + size > limit:
            parts.append(current)
            current = ' ' + ch
            width = 1 + size
        else:
            current += ch
            width += size
    parts.append(current)
    return parts


def _escape(text: str) -> str:
    return (str(text).replace('\\', '\\\\').replace(';', r'\;')
            .replace(',', r'\,').replace('\n', r'\n'))


def _week_monday(problem: Problem, week: int) -> datetime.date:
    base = datetime.date(*problem.start_week_date)
    return base + datetime.timedelta(weeks=week - 1)


def _day_offset(day: str, problem: Problem) -> int:
    index = problem.days.index(day)
    return index if index < 7 else 6


def _blocked_weeks(problem: Problem, placement: Placement) -> set[int]:
    """该次课被部分周事件挡住的周次。"""
    task = problem.tasks[placement.task_id]
    blocked: set[int] = set()
    for event in problem.calendar_events():
        if event['days'] and placement.day not in event['days']:
            continue
        if event['periods'] and not (set(event['periods']) & set(placement.periods())):
            continue
        hit = False
        if event['kind'] == 'global':
            hit = True
        elif event['kind'] == 'class':
            hit = bool(set(event['ids']) & set(task.classes))
        elif event['kind'] == 'teacher':
            hit = bool(set(event['ids']) & set(task.teachers))
        elif event['kind'] == 'room':
            hit = placement.room in event['ids']
        if hit:
            blocked.update(event['weeks'])
    return blocked


def _period_clock(problem: Problem, placement: Placement):
    first = problem.period_by_id[placement.start]
    last = problem.period_by_id[placement.start + placement.length - 1]
    return first.start, last.end


def build_ics(problem: Problem, placements: list[Placement],
              scope: str = 'all', calendar_name: str = '') -> str:
    task_filter = None
    if scope.startswith('class:'):
        task_filter = ('class', scope.split(':', 1)[1])
    elif scope.startswith('teacher:'):
        task_filter = ('teacher', scope.split(':', 1)[1])

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        f'PRODID:{PRODID}',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        f'X-WR-CALNAME:{_escape(calendar_name or f"{problem.school or "课程表"} {problem.semester}".strip())}',
    ]
    for placement in sorted(placements, key=lambda p: (p.day, p.start, p.task_id)):
        task = problem.tasks[placement.task_id]
        if task_filter:
            kind, target = task_filter
            pool = task.classes if kind == 'class' else task.teachers
            if target not in pool:
                continue
        blocked = _blocked_weeks(problem, placement)
        valid_weeks = [w for w in range(1, problem.weeks + 1) if w not in blocked]
        if not valid_weeks:
            continue
        start_clock, end_clock = _period_clock(problem, placement)
        offset = _day_offset(placement.day, problem)
        first_date = _week_monday(problem, valid_weeks[0]) + datetime.timedelta(days=offset)
        last_date = _week_monday(problem, problem.weeks) + datetime.timedelta(days=offset)
        start_dt = datetime.datetime.combine(first_date, datetime.time(*start_clock))
        end_dt = start_dt.replace(hour=end_clock[0], minute=end_clock[1])
        until_dt = datetime.datetime.combine(last_date, datetime.time(*start_clock))
        teachers = '、'.join(problem.teachers[t]['name'] for t in task.teachers)
        classes = '、'.join(task.classes)
        summary = f'{task.course}（{classes}）'
        description = f'教师：{teachers}；教室：{placement.room}；连排 {placement.length} 节；任务 {task.id}'
        if task.note:
            description += f'；{task.note}'
        lines += ['BEGIN:VEVENT',
                  f'UID:{task.id}-m{placement.meeting}-{placement.day}-{placement.start}@course-scheduling.foru',
                  f'DTSTAMP:{stamp}',
                  f'DTSTART:{start_dt.strftime("%Y%m%dT%H%M%S")}',
                  f'DTEND:{end_dt.strftime("%Y%m%dT%H%M%S")}',
                  f'RRULE:FREQ=WEEKLY;UNTIL={until_dt.strftime("%Y%m%dT%H%M%S")}',
                  f'SUMMARY:{_escape(summary)}',
                  f'LOCATION:{_escape(placement.room)}',
                  f'DESCRIPTION:{_escape(description)}']
        # RRULE 从 DTSTART 起每周重复到学期末；中途被挡的周次用 EXDATE 剔除
        exdates = [
            datetime.datetime.combine(
                _week_monday(problem, w) + datetime.timedelta(days=offset),
                datetime.time(*start_clock)).strftime('%Y%m%dT%H%M%S')
            for w in sorted(blocked) if w > valid_weeks[0]]
        if exdates:
            lines.append(f'EXDATE:{",".join(exdates)}')
        lines.append('END:VEVENT')
    lines.append('END:VCALENDAR')

    folded: list[str] = []
    for line in lines:
        folded.extend(_fold(line))
    return '\r\n'.join(folded) + '\r\n'
