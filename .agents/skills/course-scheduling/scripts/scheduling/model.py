"""排课问题模型：规范化、校验、节次窗口与占用块解析。

problem.json 采用 course-scheduling/1 契约（见技能 references/input-contract.md）。
本模块只做结构性工作，不做求解。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

SCHEMA = 'course-scheduling/1'

WEEKDAY_INDEX = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6, '天': 6}

DEFAULT_WEIGHTS = {
    'teacherCompact': 1.0,
    'afternoonPe': 5.0,
    'categoryStagger': 2.0,
    'roomStability': 1.0,
    'balance': 1.0,
}

PLAN_PROFILES = [
    {'id': 'A', 'name': '教师集中型', 'scale': {
        'teacherCompact': 1.6, 'afternoonPe': 1.0, 'categoryStagger': 0.8,
        'roomStability': 0.8, 'balance': 0.4}},
    {'id': 'B', 'name': '负载均衡型', 'scale': {
        'teacherCompact': 0.3, 'afternoonPe': 1.0, 'categoryStagger': 1.0,
        'roomStability': 1.3, 'balance': 1.6}},
    {'id': 'C', 'name': '均衡折中型', 'scale': {
        'teacherCompact': 1.0, 'afternoonPe': 1.0, 'categoryStagger': 1.0,
        'roomStability': 1.0, 'balance': 1.0}},
]


def normalize_day(day: str, days: list[str]) -> str | None:
    """把 周一/星期一/一/1 等写法规范到 timetable.days 中的名称。"""
    text = str(day).strip()
    if text in days:
        return text
    compact = text.replace('星期', '').replace('周', '').replace('礼', '')
    if compact.isdigit():
        idx = int(compact) - 1
        return days[idx] if 0 <= idx < len(days) else None
    if compact in WEEKDAY_INDEX and WEEKDAY_INDEX[compact] < len(days):
        return days[WEEKDAY_INDEX[compact]]
    return None


def parse_int_range(text: str) -> list[int] | None:
    """解析 “1-4”、“2;3”、“9-12” 一类的节次/周次表达式；无法解析返回 None。"""
    if text is None:
        return None
    text = str(text).strip()
    if not text:
        return None
    values: list[int] = []
    for part in re.split(r'[;；,，、\s]+', text):
        if not part:
            continue
        m = re.fullmatch(r'(\d+)\s*[-—~至]\s*(\d+)', part)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if lo > hi:
                return None
            values.extend(range(lo, hi + 1))
        elif part.isdigit():
            values.append(int(part))
        else:
            return None
    return sorted(set(values)) or None


def parse_time(text: str) -> tuple[int, int] | None:
    m = re.fullmatch(r'(\d{1,2}):(\d{2})', str(text).strip())
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def split_ids(text) -> list[str]:
    """拆分 “数控2401;智造2401” 一类的多值单元格；也接受 JSON 数组。"""
    if text is None:
        return []
    if isinstance(text, list):
        return [str(p).strip() for p in text if str(p).strip()]
    return [p.strip() for p in re.split(r'[;；,，/、\s]+', str(text)) if p.strip()]


@dataclass
class Period:
    id: int
    label: str
    start: tuple[int, int]
    end: tuple[int, int]
    session: str


@dataclass
class Placement:
    task_id: str
    meeting: int          # 任务内第几个教学单元（0 起）
    length: int           # 连排节数
    day: str
    start: int            # 开始节次 id
    room: str
    fixed: bool = False   # 增量模式中沿用原课表、不再挪动的排入
    origin: dict | None = None  # 增量模式中被挪动前的原始时段

    def periods(self) -> list[int]:
        return list(range(self.start, self.start + self.length))


@dataclass
class Meeting:
    index: int
    length: int           # 连排节数；尾节可能小于任务连排要求
    full: bool            # 是否达到任务的连排要求


@dataclass
class Task:
    id: str
    course: str
    classes: list[str]
    teachers: list[str]
    hours_per_week: int
    consecutive: int
    category: str
    room_type: str | None
    min_capacity: int
    equipment: str | None
    min_sets: int
    fixed_room: str | None
    note: str
    total_hours: int | None
    meetings: list[Meeting] = field(default_factory=list)

    def size(self) -> int:
        return 0  # 由 Problem 按班级人数计算


@dataclass
class Block:
    id: str
    name: str
    kind: str             # global / class / teacher / room
    ids: list[str]        # kind != global 时的对象清单
    weeks: list[int] | None   # None 或覆盖全部周 = 模板级（每周生效）
    days: list[str] | None
    periods: list[int] | None
    note: str

    def template_level(self, total_weeks: int) -> bool:
        if not self.weeks:
            return True
        return len(self.weeks) >= total_weeks


class Problem:
    """规范化后的排课问题，附校验错误与警告。"""

    def __init__(self, data: dict):
        self.raw = data
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.meta: dict = data.get('meta') or {}
        self.school = str(self.meta.get('school') or '')
        self.semester = str(self.meta.get('semester') or '')
        self.tasks: dict[str, Task] = {}
        self._load_calendar(data.get('calendar') or {})
        self._load_timetable(data.get('timetable') or {})
        self._load_classes(data.get('classes') or [])
        self._load_teachers(data.get('teachers') or [])
        self._load_rooms(data.get('rooms') or [])
        self._load_tasks(data.get('tasks') or [])
        self._load_blocks(data.get('blocks') or [])
        self.weights = dict(DEFAULT_WEIGHTS)
        for key, value in (data.get('weights') or {}).items():
            if key in self.weights:
                try:
                    self.weights[key] = float(value)
                except (TypeError, ValueError):
                    self.warnings.append(f'权重 {key} 不是数字，使用默认值。')
        self.options = data.get('options') or {}
        self._load_existing(data.get('existing') or {})

    # ---------- 各部分加载与规范化 ----------

    def _load_calendar(self, data: dict):
        self.start_week = str(data.get('startWeek') or '')
        m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', self.start_week)
        if not m:
            self.errors.append('calendar.startWeek 缺失或不是 YYYY-MM-DD（应为第 1 教学周的周一日期）。')
            self.start_week = '2026-09-07'
            self.start_week_date = (2026, 9, 7)
        else:
            self.start_week_date = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        try:
            self.weeks = int(data.get('weeks'))
            if self.weeks <= 0:
                raise ValueError
        except (TypeError, ValueError):
            self.errors.append('calendar.weeks 缺失或不是正整数。')
            self.weeks = 20

    def _load_timetable(self, data: dict):
        self.days = [str(d).strip() for d in (data.get('days') or []) if str(d).strip()]
        if len(self.days) < 1:
            self.errors.append('timetable.days 为空，至少需要 1 个教学日。')
            self.days = ['周一', '周二', '周三', '周四', '周五']
        periods: list[Period] = []
        for row in data.get('periods') or []:
            pid = row.get('id')
            label = str(row.get('label') or f'第{pid}节')
            start = parse_time(row.get('start') or '')
            end = parse_time(row.get('end') or '')
            session = str(row.get('session') or '').strip()
            try:
                pid = int(pid)
            except (TypeError, ValueError):
                self.errors.append(f'作息节次 id 非法：{row!r}')
                continue
            if not start or not end:
                self.errors.append(f'节次 {label} 缺少开始或结束时间。')
                continue
            if (end[0], end[1]) <= (start[0], start[1]):
                self.errors.append(f'节次 {label} 结束时间不晚于开始时间。')
            periods.append(Period(pid, label, start, end, session or '全天'))
        if not periods:
            self.errors.append('timetable.periods 为空，无法排课。')
        self.periods = sorted(periods, key=lambda p: p.id)
        self.period_by_id = {p.id: p for p in self.periods}
        self.period_ids = [p.id for p in self.periods]
        self.sessions: list[str] = []
        for p in self.periods:
            if p.session not in self.sessions:
                self.sessions.append(p.session)
        self.afternoon_sessions = [
            s for s in self.sessions if any(k in s for k in ('下午', '晚'))] or self.sessions[1:]

    def _load_classes(self, rows: list):
        self.classes: dict[str, dict] = {}
        self.class_by_name: dict[str, str] = {}
        for row in rows:
            cid = str(row.get('id') or row.get('name') or '').strip()
            if not cid:
                self.errors.append(f'班级缺少 id：{row!r}')
                continue
            if cid in self.classes:
                self.errors.append(f'班级 id 重复：{cid}。')
                continue
            try:
                size = int(row.get('size') or 0)
            except (TypeError, ValueError):
                size = 0
            if size <= 0:
                self.errors.append(f'班级 {cid} 人数缺失或不是正整数。')
            self.classes[cid] = {
                'id': cid, 'name': str(row.get('name') or cid), 'size': size,
                'program': str(row.get('program') or ''),
            }
            self.class_by_name[self.classes[cid]['name']] = cid

    def _load_teachers(self, rows: list):
        self.teachers: dict[str, dict] = {}
        self.teacher_by_name: dict[str, str] = {}
        for row in rows:
            tid = str(row.get('id') or row.get('name') or '').strip()
            if not tid:
                self.errors.append(f'教师缺少 id：{row!r}')
                continue
            if tid in self.teachers:
                self.errors.append(f'教师 id 重复：{tid}。')
                continue
            pref = str(row.get('preference') or '').strip()
            if pref not in ('', 'compact', 'spread', 'balanced'):
                self.warnings.append(f'教师 {tid} 偏好 {pref} 无法识别，按不限处理。')
                pref = ''
            self.teachers[tid] = {
                'id': tid, 'name': str(row.get('name') or tid),
                'preference': pref or 'balanced',
            }
            self.teacher_by_name[self.teachers[tid]['name']] = tid

    def _load_rooms(self, rows: list):
        self.rooms: dict[str, dict] = {}
        self.room_by_name: dict[str, str] = {}
        for row in rows:
            rid = str(row.get('id') or row.get('name') or '').strip()
            if not rid:
                self.errors.append(f'教室缺少 id：{row!r}')
                continue
            if rid in self.rooms:
                self.errors.append(f'教室 id 重复：{rid}。')
                continue
            try:
                capacity = int(row.get('capacity') or 0)
            except (TypeError, ValueError):
                capacity = 0
            if capacity <= 0:
                self.errors.append(f'教室 {rid} 容量缺失或不是正整数。')
            try:
                sets = int(row.get('sets') or 0)
            except (TypeError, ValueError):
                sets = 0
            self.rooms[rid] = {
                'id': rid, 'type': str(row.get('type') or '普通').strip(),
                'capacity': capacity,
                'equipment': str(row.get('equipment') or '').strip() or None,
                'sets': sets,
                'note': str(row.get('note') or ''),
            }
            self.room_by_name[rid] = rid

    def _load_tasks(self, rows: list):
        """加载教学任务；重复调用为追加（增量模式新增任务），不清空已有任务。"""
        for row in rows:
            tid = str(row.get('id') or '').strip()
            if not tid:
                self.errors.append(f'教学任务缺少 id：{row!r}')
                continue
            if tid in self.tasks:
                self.errors.append(f'教学任务 id 重复：{tid}。')
                continue
            course = str(row.get('course') or '').strip()
            if not course:
                self.errors.append(f'任务 {tid} 缺少课程名称。')
            classes = [self._resolve_class(c) for c in split_ids(str(row.get('classes') or ''))]
            classes = [c for c in classes if c]
            if not classes:
                self.errors.append(f'任务 {tid} 未关联任何有效班级。')
            teachers = [self._resolve_teacher(t) for t in split_ids(str(row.get('teachers') or ''))]
            teachers = [t for t in teachers if t]
            if not teachers:
                self.errors.append(f'任务 {tid} 未关联任何有效教师。')
            try:
                hours = int(row.get('hoursPerWeek') or 0)
            except (TypeError, ValueError):
                hours = 0
            if hours <= 0:
                self.errors.append(f'任务 {tid} 周学时缺失或不是正整数。')
            try:
                consecutive = int(row.get('consecutive') or 1)
            except (TypeError, ValueError):
                consecutive = 1
            if consecutive < 1:
                consecutive = 1
            room = row.get('room') or {}
            task = Task(
                id=tid, course=course or tid, classes=classes, teachers=teachers,
                hours_per_week=max(hours, 0), consecutive=consecutive,
                category=str(row.get('category') or '').strip(),
                room_type=(str(room.get('type') or '').strip() or None),
                min_capacity=int(room.get('minCapacity') or 0),
                equipment=(str(room.get('equipment') or '').strip() or None),
                min_sets=int(room.get('sets') or 0),
                fixed_room=(str(room.get('fixed') or '').strip() or None),
                note=str(row.get('note') or ''),
                total_hours=(int(row['totalHours']) if row.get('totalHours') else None),
            )
            if task.fixed_room and task.fixed_room not in self.rooms:
                self.errors.append(f'任务 {tid} 固定教室 {task.fixed_room} 不在教室清单中。')
            task.meetings = decompose(task)
            for meeting in task.meetings:
                if meeting.length > self.max_run_length() and meeting.full:
                    self.warnings.append(
                        f'任务 {tid} 连排 {meeting.length} 节超过最长可连排节数 {self.max_run_length()}，该单元难以排入。')
            self.tasks[tid] = task

    def _load_blocks(self, rows: list):
        self.blocks: list[Block] = []
        seen: set[str] = set()
        for i, row in enumerate(rows, 1):
            bid = str(row.get('id') or f'B{i}').strip()
            if bid in seen:
                self.errors.append(f'占用约束 id 重复：{bid}。')
                continue
            seen.add(bid)
            scope = row.get('scope') or {}
            kind = 'global'
            ids: list[str] = []
            if scope.get('classes'):
                kind, raw = 'class', scope['classes']
            elif scope.get('teachers'):
                kind, raw = 'teacher', scope['teachers']
            elif scope.get('rooms'):
                kind, raw = 'room', scope['rooms']
            else:
                raw = []
            if kind == 'class':
                ids = [self._resolve_class(c) for c in raw]
                bad = [c for c in raw if self._resolve_class(c) is None]
                if bad:
                    self.errors.append(f'占用约束 {bid} 引用了不存在的班级：{"、".join(map(str, bad))}。')
            elif kind == 'teacher':
                ids = [self._resolve_teacher(t) for t in raw]
                bad = [t for t in raw if self._resolve_teacher(t) is None]
                if bad:
                    self.errors.append(f'占用约束 {bid} 引用了不存在的教师：{"、".join(map(str, bad))}。')
            elif kind == 'room':
                ids = [self._resolve_room(r) for r in raw]
                bad = [r for r in raw if self._resolve_room(r) is None]
                if bad:
                    self.errors.append(f'占用约束 {bid} 引用了不存在的教室：{"、".join(map(str, bad))}。')
            weeks = row.get('weeks')
            if weeks is not None and not isinstance(weeks, list):
                weeks = parse_int_range(str(weeks))
            days = row.get('days')
            if days is not None and not isinstance(days, list):
                days = [normalize_day(d, self.days) for d in split_ids(str(days))]
                days = [d for d in days if d] or None
            if isinstance(days, list):
                days = [normalize_day(d, self.days) for d in days]
                days = [d for d in days if d]
            periods = row.get('periods')
            if periods is not None and not isinstance(periods, list):
                periods = parse_int_range(str(periods))
            if isinstance(periods, list):
                bad = [p for p in periods if p not in self.period_by_id]
                if bad:
                    self.errors.append(f'占用约束 {bid} 引用了不存在的节次：{bad}。')
            if weeks and (min(weeks) < 1 or max(weeks) > self.weeks):
                self.errors.append(f'占用约束 {bid} 周次超出 1–{self.weeks}。')
            self.blocks.append(Block(
                id=bid, name=str(row.get('name') or bid), kind=kind, ids=sorted({i for i in ids if i}),
                weeks=weeks, days=days or None, periods=periods, note=str(row.get('note') or ''),
            ))

    def _load_existing(self, data: dict):
        self.existing_placements: list[dict] = []
        for i, row in enumerate(data.get('placements') or [], 1):
            tid = str(row.get('taskId') or '').strip()
            if tid not in self.tasks:
                self.warnings.append(f'已有课表第 {i} 行任务 {tid} 不在任务清单中，已忽略。')
                continue
            day = normalize_day(str(row.get('day') or ''), self.days)
            try:
                start = int(row.get('startPeriod'))
                length = int(row.get('length') or row.get('periods') or 0)
            except (TypeError, ValueError):
                self.warnings.append(f'已有课表第 {i} 行节次信息不完整，已忽略。')
                continue
            room = self._resolve_room(str(row.get('room') or ''))
            if not day or length <= 0 or not room:
                self.warnings.append(f'已有课表第 {i} 行星期/教室信息不完整，已忽略。')
                continue
            self.existing_placements.append(
                {'taskId': tid, 'day': day, 'start': start, 'length': length, 'room': room})
        self.changes: list[dict] = data.get('changes') or []
        for i, change in enumerate(self.changes, 1):
            if change.get('kind') not in ('cancel', 'unavailable', 'add'):
                self.warnings.append(f'变更第 {i} 项类型无法识别，已忽略：{change.get("kind")}。')

    # ---------- 解析辅助 ----------

    def _resolve_class(self, ref) -> str | None:
        text = str(ref or '').strip()
        if text in self.classes:
            return text
        return self.class_by_name.get(text)

    def _resolve_teacher(self, ref) -> str | None:
        text = str(ref or '').strip()
        if text in self.teachers:
            return text
        return self.teacher_by_name.get(text)

    def _resolve_room(self, ref) -> str | None:
        text = str(ref or '').strip()
        if text in self.rooms:
            return text
        return self.room_by_name.get(text)

    # ---------- 结构查询 ----------

    def session_of(self, period_id: int) -> str:
        return self.period_by_id[period_id].session

    def max_run_length(self) -> int:
        """同一时段内最长的连续节次数（连排不能跨时段，如午休）。"""
        best = 0
        run = 0
        last_session = None
        for p in self.periods:
            if p.session == last_session:
                run += 1
            else:
                last_session = p.session
                run = 1
            best = max(best, run)
        return best

    def runs(self, length: int) -> list[tuple[str, int]]:
        """长度为 length 的所有可连排窗口 (day, start)。"""
        result: list[tuple[str, int]] = []
        by_session: dict[str, list[Period]] = {}
        for p in self.periods:
            by_session.setdefault(p.session, []).append(p)
        for day in self.days:
            for group in by_session.values():
                for i in range(len(group) - length + 1):
                    result.append((day, group[i].id))
        return result

    def class_size(self, class_ids: list[str]) -> int:
        return sum(self.classes[c]['size'] for c in class_ids if c in self.classes)

    def candidate_rooms(self, task: Task) -> list[str]:
        if task.fixed_room:
            return [task.fixed_room] if task.fixed_room in self.rooms else []
        need_size = max(task.min_capacity, self.class_size(task.classes))
        result = []
        for rid, room in self.rooms.items():
            if task.room_type and room['type'] != task.room_type:
                continue
            if room['capacity'] < need_size:
                continue
            if task.equipment:
                if room['equipment'] != task.equipment:
                    continue
                if task.min_sets and room['sets'] < task.min_sets:
                    continue
            elif task.min_sets and room['sets'] and room['sets'] < task.min_sets:
                continue
            result.append(rid)
        return result

    def template_blocks(self) -> dict[str, set]:
        """模板级占用（每周生效）：{kind: {(对象id或*, day, period)}}。"""
        result = {'global': set(), 'class': set(), 'teacher': set(), 'room': set()}
        for block in self.blocks:
            if not block.template_level(self.weeks):
                continue
            days = block.days or self.days
            periods = block.periods or self.period_ids
            targets = (['*'] if block.kind == 'global' else block.ids)
            for target in targets:
                for day in days:
                    for period in periods:
                        result[block.kind].add((target, day, period))
        return result

    def calendar_events(self) -> list[dict]:
        """部分周次的日历事件（轮岗、考试窗口、假期），用于导出与学时影响统计。"""
        events = []
        for block in self.blocks:
            if block.template_level(self.weeks):
                continue
            events.append({
                'id': block.id, 'name': block.name, 'kind': block.kind,
                'ids': block.ids, 'weeks': sorted(block.weeks),
                'days': block.days, 'periods': block.periods, 'note': block.note,
            })
        return events

    def week_date(self, week: int) -> tuple[int, int, int]:
        """第 week 周的周一日期。"""
        import datetime
        base = datetime.date(*self.start_week_date)
        return (base + datetime.timedelta(weeks=week - 1)).timetuple()[:3]

    def fingerprint(self) -> str:
        text = json.dumps(self.raw, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]


def decompose(task: Task) -> list[Meeting]:
    """把周学时拆成教学单元：优先满连排，剩余尾节单独成单元。"""
    meetings: list[Meeting] = []
    remaining = task.hours_per_week
    index = 0
    while remaining >= task.consecutive:
        meetings.append(Meeting(index, task.consecutive, True))
        remaining -= task.consecutive
        index += 1
    if remaining > 0:
        meetings.append(Meeting(index, remaining, False))
    return meetings


def load_problem(path) -> Problem:
    with open(path, 'r', encoding='utf-8-sig') as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError('problem.json 应为 JSON 对象。')
    schema = data.get('schema')
    if schema != SCHEMA:
        data = dict(data)
        data.setdefault('schema', SCHEMA)
    return Problem(data)
