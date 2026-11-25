"""求解器：最受限优先贪心 + 保可行局部搜索。

硬约束由构造保证：任何时刻课表状态无冲突；排不进的教学单元进入归因，
绝不输出带冲突的课表。软约束以加权代价驱动局部搜索。
"""

from __future__ import annotations

import random
import time

from .model import (PLAN_PROFILES, Block, Meeting, Placement, Problem, Task,
                    decompose)

HARD_LABELS = {
    'teacher': 'HC-01 教师时间不冲突',
    'class': 'HC-02 班级时间不冲突',
    'room': 'HC-03 教室占用不冲突',
    'fit': 'HC-04 教室类型与容量匹配',
    'sets': 'HC-05 实训台套数满足',
    'run': 'HC-06 连排节次连续',
    'block': 'HC-07 占用时段避让',
}

MOVE_DAY_COST = 100.0
MOVE_PERIOD_COST = 10.0
MOVE_ROOM_COST = 1.0


class PlanState:
    """一套课表的可行状态与占用索引。"""

    def __init__(self, problem: Problem):
        self.problem = problem
        self.placements: list[Placement] = []
        self.class_busy: dict[str, dict[tuple[str, int], int]] = {}
        self.teacher_busy: dict[str, dict[tuple[str, int], int]] = {}
        self.room_busy: dict[str, dict[tuple[str, int], int]] = {}
        self.blocked = problem.template_blocks()
        # 软代价缓存
        self.class_room: dict[tuple[str, str, int], str] = {}
        self.cat_slot: dict[tuple[str, int, str], int] = {}
        self.teacher_days: dict[str, set[str]] = {}

    # ---------- 占用维护 ----------

    def _map(self, kind: str) -> dict:
        return {'class': self.class_busy, 'teacher': self.teacher_busy,
                'room': self.room_busy}[kind]

    def _targets(self, placement: Placement, task: Task):
        for cid in task.classes:
            yield 'class', cid
        for tid in task.teachers:
            yield 'teacher', tid
        yield 'room', placement.room

    def add(self, placement: Placement, index: int):
        task = self.problem.tasks[placement.task_id]
        for kind, target in self._targets(placement, task):
            busy = self._map(kind)
            for period in placement.periods():
                busy.setdefault(target, {})[(placement.day, period)] = index
        for cid in task.classes:
            for period in placement.periods():
                self.class_room[(cid, placement.day, period)] = placement.room
        if task.category:
            for period in placement.periods():
                key = (placement.day, period, task.category)
                self.cat_slot[key] = self.cat_slot.get(key, 0) + 1
        for tid in task.teachers:
            self.teacher_days.setdefault(tid, set()).add(placement.day)

    def remove(self, index: int):
        placement = self.placements[index]
        task = self.problem.tasks[placement.task_id]
        for kind, target in self._targets(placement, task):
            busy = self._map(kind)
            for period in placement.periods():
                busy.get(target, {}).pop((placement.day, period), None)
        for cid in task.classes:
            for period in placement.periods():
                self.class_room.pop((cid, placement.day, period), None)
        if task.category:
            for period in placement.periods():
                key = (placement.day, period, task.category)
                if self.cat_slot.get(key, 0) <= 1:
                    self.cat_slot.pop(key, None)
                else:
                    self.cat_slot[key] -= 1
        for tid in task.teachers:
            self.teacher_days[tid] = {
                day for (day, _period) in self.teacher_busy.get(tid, {})}

    def conflict_reason(self, task: Task, day: str, start: int, length: int, room: str) -> str | None:
        """返回首个违反的硬约束类型；可行返回 None。"""
        for cid in task.classes:
            slot = self.class_busy.get(cid, {})
            blocked = self.blocked['class']
            for period in range(start, start + length):
                if (day, period) in slot:
                    return 'class'
                if (cid, day, period) in blocked or ('*', day, period) in self.blocked['global']:
                    return 'block'
        for tid in task.teachers:
            slot = self.teacher_busy.get(tid, {})
            blocked = self.blocked['teacher']
            for period in range(start, start + length):
                if (day, period) in slot:
                    return 'teacher'
                if (tid, day, period) in blocked:
                    return 'block'
        slot = self.room_busy.get(room, {})
        blocked = self.blocked['room']
        for period in range(start, start + length):
            if (day, period) in slot:
                return 'room'
            if (room, day, period) in blocked:
                return 'block'
        return None


def candidate_windows(problem: Problem, length: int) -> list[tuple[str, int]]:
    return problem.runs(length)


def solve_plan(problem: Problem, weights: dict[str, float], seed: int,
               iterations: int = 2600, time_budget: float = 12.0,
               fixed: list[Placement] | None = None,
               queue_override: list[tuple[Task, Meeting]] | None = None,
               origin_index: dict | None = None) -> dict:
    """求一套方案。fixed 为增量模式沿用的排入；queue_override 指定待排清单。"""
    rng = random.Random(seed)
    state = PlanState(problem)

    for placement in (fixed or []):
        state.placements.append(placement)
        state.add(placement, len(state.placements) - 1)

    queue = queue_override if queue_override is not None else build_queue(problem)
    unplaced: list[dict] = []

    for task, meeting in queue:
        placed = _place_meeting(state, task, meeting, weights, rng, origin_index)
        if placed is None:
            unplaced.append(_attribute(state, problem, task, meeting))

    deadline = time.monotonic() + time_budget
    _local_search(state, weights, rng, iterations, deadline)

    return {
        'placements': state.placements,
        'unplaced': unplaced,
        'weights': dict(weights),
        'seed': seed,
    }


def build_queue(problem: Problem, extra_tasks: list[Task] | None = None) -> list[tuple[Task, Meeting]]:
    """最受限优先：连排长、教师负载高、专用教室稀缺、班级规模大的任务先排。"""
    tasks = list(problem.tasks.values()) + list(extra_tasks or [])
    teacher_load: dict[str, int] = {}
    for task in tasks:
        for tid in task.teachers:
            teacher_load[tid] = teacher_load.get(tid, 0) + task.hours_per_week
    type_count: dict[str, int] = {}
    for task in tasks:
        if task.room_type:
            type_count[task.room_type] = type_count.get(task.room_type, 0) + 1
    scarcity = {t: 1.0 / max(len(problem.candidate_rooms(fake_task(problem, t))), 1)
                for t in type_count}

    def difficulty(task: Task) -> tuple:
        room_score = scarcity.get(task.room_type or '', 0.0)
        teacher_score = sum(teacher_load.get(tid, 0) for tid in task.teachers)
        return (task.consecutive, room_score, teacher_score, task.hours_per_week, task.id)

    queue: list[tuple[Task, Meeting]] = []
    for task in sorted(tasks, key=difficulty, reverse=True):
        for meeting in sorted(task.meetings, key=lambda m: m.length, reverse=True):
            queue.append((task, meeting))
    return queue


def fake_task(problem: Problem, room_type: str) -> Task:
    return Task(id='__probe__', course='', classes=[], teachers=[],
                hours_per_week=0, consecutive=1, category='',
                room_type=room_type, min_capacity=0, equipment=None,
                min_sets=0, fixed_room=None, note='', total_hours=None)


def _soft_cost_delta(state: PlanState, weights: dict[str, float],
                     task: Task, length: int, day: str, start: int, room: str) -> float:
    """把 (task, day, start, room) 放入空位的近似软代价（贪心用）。"""
    cost = 0.0
    periods = list(range(start, start + length))
    # 教室稳定：同班同天尽量同教室
    for cid in task.classes:
        rooms_used = {room}
        for period in periods:
            other = state.class_room.get((cid, day, period))
            if other:
                rooms_used.add(other)
        cost += weights['roomStability'] * (len(rooms_used) - 1)
    # 午后体育
    if task.category == '体育' and any(
            state.problem.session_of(p) in state.problem.afternoon_sessions for p in periods):
        cost += weights['afternoonPe']
    # 同类错峰
    if task.category:
        for period in periods:
            same = state.cat_slot.get((day, period, task.category), 0)
            cost += weights['categoryStagger'] * same
    # 教师集中偏好：占新的一天付出代价
    for tid in task.teachers:
        if state.problem.teachers[tid]['preference'] == 'compact':
            cost += weights['teacherCompact'] * (0.0 if day in state.teacher_days.get(tid, ()) else 1.0)
    # 增量扰动：偏离原时段的代价
    return cost


def _place_meeting(state: PlanState, task: Task, meeting: Meeting,
                   weights: dict[str, float], rng: random.Random,
                   origin_index: dict | None) -> Placement | None:
    rooms = state.problem.candidate_rooms(task)
    if not rooms:
        return None
    best: tuple[float, str, int, str] | None = None
    for day, start in candidate_windows(state.problem, meeting.length):
        for room in rooms:
            if state.conflict_reason(task, day, start, meeting.length, room) is not None:
                continue
            cost = _soft_cost_delta(state, weights, task, meeting.length, day, start, room)
            origin = origin_index.get((task.id, meeting.index)) if origin_index else None
            if origin:
                if day != origin.get('day'):
                    cost += MOVE_DAY_COST
                elif start != origin.get('start'):
                    cost += MOVE_PERIOD_COST
                if room != origin.get('room'):
                    cost += MOVE_ROOM_COST
            jitter = rng.random() * 0.01
            key = (cost + jitter, day, start, room)
            if best is None or key < best:
                best = key
    if best is None:
        return None
    _, day, start, room = best
    placement = Placement(task_id=task.id, meeting=meeting.index,
                          length=meeting.length, day=day, start=start, room=room)
    if origin_index:
        placement.origin = origin_index.get((task.id, meeting.index))
    state.placements.append(placement)
    state.add(placement, len(state.placements) - 1)
    return placement


def _attribute(state: PlanState, problem: Problem, task: Task, meeting: Meeting) -> dict:
    """归因：统计全部候选窗口被哪类硬约束阻断，并给出放松建议。"""
    rooms = problem.candidate_rooms(task)
    reasons: dict[str, int] = {}
    examples: dict[str, list[str]] = {}

    def tally(reason: str, detail: str):
        reasons[reason] = reasons.get(reason, 0) + 1
        if len(examples.setdefault(reason, [])) < 3:
            examples[reason].append(detail)

    windows = candidate_windows(problem, meeting.length)
    if not rooms:
        need = task.room_type or '不限'
        tally('fit', f'无满足 类型{need}·容量≥{max(task.min_capacity, problem.class_size(task.classes))}'
                     + (f'·{task.equipment}台套≥{task.min_sets}' if task.equipment else '') + ' 的教室')
    for day, start in windows:
        for room in rooms:
            reason = state.conflict_reason(task, day, start, meeting.length, room)
            if reason is None:
                continue  # 不会发生：调用前已确认无解
            label = {'class': 'class', 'teacher': 'teacher', 'room': 'room', 'block': 'block'}.get(reason, reason)
            tally(label, f'{day}第{start}-{start + meeting.length - 1}节@{room}')
    if not windows:
        tally('run', f'连排 {meeting.length} 节超过作息最长可连排 {problem.max_run_length()} 节')

    suggestions = _suggest(problem, task, meeting, reasons, rooms)
    return {
        'taskId': task.id, 'meeting': meeting.index, 'course': task.course,
        'classes': task.classes, 'teachers': task.teachers,
        'length': meeting.length, 'full': meeting.full,
        'reasons': [{'constraint': HARD_LABELS.get(k, k), 'count': v,
                     'detail': '；'.join(examples.get(k, []))}
                    for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])],
        'suggestions': suggestions,
    }


def _suggest(problem: Problem, task: Task, meeting: Meeting,
             reasons: dict[str, int], rooms: list[str]) -> list[str]:
    tips: list[str] = []
    if not rooms:
        need = task.room_type or '不限类型'
        tips.append(f'放宽教室要求：当前无 类型{need}、容量≥{max(task.min_capacity, problem.class_size(task.classes))}'
                    + (f'、{task.equipment}台套≥{task.min_sets}' if task.equipment else '')
                    + ' 的可用教室，可降低台套或容量要求、改用其他类型教室或新增资源。')
    if reasons.get('run'):
        tips.append(f'拆分连排：{task.consecutive} 节连排超过时段上限 {problem.max_run_length()} 节，'
                    f'建议改为 {problem.max_run_length()} 节以内的连排或拆成多个单元。')
    if reasons.get('teacher'):
        busy = '、'.join(problem.teachers[t]['name'] for t in task.teachers)
        tips.append(f'协调教师时段：{busy} 在候选时段已有其他安排，可调整其承担任务、更换教师或放宽教师不可用约束。')
    if reasons.get('class'):
        ids = '、'.join(task.classes)
        tips.append(f'核减班级负荷：{ids} 周学时已接近可用时段上限，可减少周学时、调整混编拆分或压缩其他课程。')
    if reasons.get('room') and rooms:
        tips.append('增补实训资源：目标教室在候选时段已满，可错峰安排、增加同类教室或调整固定教室要求。')
    if reasons.get('block'):
        names = [b.name for b in problem.blocks if b.template_level(problem.weeks)]
        if names:
            tips.append('核对占用约束：' + '、'.join(names[:3]) + ' 等每周占用压缩了可用窗口，可调整批次或占用范围。')
    if meeting.full is False and task.consecutive > 1 and not tips:
        tips.append(f'尾节说明：周学时 {task.hours_per_week} 按连排 {task.consecutive} 拆分后剩余 {meeting.length} 节单节课，属正常尾节。')
    return tips[:4]


# ---------- 局部搜索 ----------

def total_cost(state: PlanState, weights: dict[str, float]) -> float:
    problem = state.problem
    cost = 0.0
    # 教师：集中偏好少占天，分散偏好压低单日峰值，默认轻度集中
    for tid, pref in ((t, problem.teachers[t]['preference']) for t in problem.teachers):
        days: dict[str, int] = {}
        for (day, _period), _idx in state.teacher_busy.get(tid, {}).items():
            days[day] = days.get(day, 0) + 1
        if not days:
            continue
        max_daily = max(days.values())
        if pref == 'compact':
            cost += weights['teacherCompact'] * len(days)
        elif pref == 'spread':
            cost += weights['teacherCompact'] * max_daily
        else:
            cost += weights['teacherCompact'] * (0.3 * len(days) + 0.2 * max_daily)
    # 午后体育
    for placement in state.placements:
        task = problem.tasks[placement.task_id]
        if task.category == '体育' and any(
                problem.session_of(p) in problem.afternoon_sessions for p in placement.periods()):
            cost += weights['afternoonPe']
    # 同类错峰：同一 (day, period) 同类别课程数 - 1
    category_count: dict[tuple[str, int, str], int] = {}
    for placement in state.placements:
        task = problem.tasks[placement.task_id]
        if not task.category:
            continue
        for period in placement.periods():
            key = (placement.day, period, task.category)
            category_count[key] = category_count.get(key, 0) + 1
    cost += weights['categoryStagger'] * sum(c - 1 for c in category_count.values() if c > 1)
    # 教室稳定：每班每天不同教室数 - 1
    class_day_rooms: dict[tuple[str, str], set[str]] = {}
    for placement in state.placements:
        task = problem.tasks[placement.task_id]
        for cid in task.classes:
            for period in placement.periods():
                class_day_rooms.setdefault((cid, placement.day), set()).add(placement.room)
    cost += weights['roomStability'] * sum(len(v) - 1 for v in class_day_rooms.values() if len(v) > 1)
    # 均衡：班级与教师的每日节次离散度
    for busy_map in (state.class_busy, state.teacher_busy):
        for target, slots in busy_map.items():
            days: dict[str, int] = {}
            for (day, _period) in slots:
                days[day] = days.get(day, 0) + 1
            if len(days) < 2:
                continue
            mean = sum(days.values()) / len(days)
            cost += weights['balance'] * 0.2 * sum((v - mean) ** 2 for v in days.values())
    # 增量扰动
    for placement in state.placements:
        if not placement.origin:
            continue
        if placement.day != placement.origin.get('day'):
            cost += MOVE_DAY_COST
        elif placement.start != placement.origin.get('start'):
            cost += MOVE_PERIOD_COST
        if placement.room != placement.origin.get('room'):
            cost += MOVE_ROOM_COST
    return cost


def _local_search(state: PlanState, weights: dict[str, float], rng: random.Random,
                  iterations: int, deadline: float):
    movable = [i for i, p in enumerate(state.placements) if not p.fixed]
    if not movable:
        return
    best_cost = total_cost(state, weights)
    for _ in range(iterations):
        if time.monotonic() > deadline:
            break
        idx = movable[rng.randrange(len(movable))]
        placement = state.placements[idx]
        task = state.problem.tasks[placement.task_id]
        meeting = task.meetings[placement.meeting]
        rooms = state.problem.candidate_rooms(task)
        state.remove(idx)
        candidates: list[tuple[str, int, str]] = []
        for day, start in candidate_windows(state.problem, placement.length):
            for room in rooms:
                if state.conflict_reason(task, day, start, placement.length, room) is None:
                    candidates.append((day, start, room))
        if not candidates:
            state.add(placement, idx)
            continue
        day, start, room = candidates[rng.randrange(len(candidates))]
        old = (placement.day, placement.start, placement.room)
        placement.day, placement.start, placement.room = day, start, room
        state.add(placement, idx)
        new_cost = total_cost(state, weights)
        if new_cost <= best_cost:
            best_cost = new_cost
        else:
            state.remove(idx)
            placement.day, placement.start, placement.room = old
            state.add(placement, idx)


# ---------- 方案组 ----------

def solve(problem: Problem, plan_count: int | None = None,
          seeds: list[int] | None = None, iterations: int | None = None,
          time_budget: float | None = None) -> list[dict]:
    """生成多套方案并去重。"""
    plan_count = plan_count or int(problem.options.get('planCount') or 3)
    plan_count = max(1, min(3, plan_count))
    seeds = seeds or [int(s) for s in (problem.options.get('seeds') or [11, 23, 37])]
    iterations = iterations or int(problem.options.get('iterations') or 2600)
    time_budget = time_budget or float(problem.options.get('timeBudgetSec') or 12.0)
    plans: list[dict] = []
    seen: set[tuple] = set()
    for i, profile in enumerate(PLAN_PROFILES[:plan_count]):
        weights = {k: problem.weights.get(k, 1.0) * scale
                   for k, scale in profile['scale'].items()}
        seed = seeds[i % len(seeds)]
        for attempt in range(5):
            result = solve_plan(problem, weights, seed + attempt * 101,
                                iterations=iterations, time_budget=time_budget)
            signature = tuple(sorted(
                (p.task_id, p.meeting, p.day, p.start, p.room) for p in result['placements']))
            if signature not in seen:
                seen.add(signature)
                plans.append({**result, 'id': profile['id'], 'name': profile['name'],
                              'seed': seed + attempt * 101})
                break
        else:
            continue
    return plans


# ---------- 独立复核 ----------

def verify_plan(problem: Problem, placements: list[Placement]) -> list[str]:
    """从零复核硬约束，返回违规清单（应为空）。"""
    violations: list[str] = []
    class_busy: dict[tuple[str, int, str], str] = {}
    teacher_busy: dict[tuple[str, int, str], str] = {}
    room_busy: dict[tuple[str, int, str], str] = {}
    blocked = problem.template_blocks()
    placed_units: set[tuple[str, int]] = set()

    for placement in placements:
        task = problem.tasks.get(placement.task_id)
        if task is None:
            violations.append(f'未知任务 {placement.task_id}。')
            continue
        # 连排：节次存在且同时段连续
        ids = problem.period_ids
        if placement.start not in problem.period_by_id:
            violations.append(f'{task.id} 起始节次 {placement.start} 不存在。')
            continue
        positions = [ids.index(p) for p in placement.periods()
                     if p in problem.period_by_id]
        if len(positions) != placement.length or positions != list(
                range(positions[0], positions[0] + placement.length)):
            violations.append(f'{task.id} 第{placement.meeting}单元节次不连续。')
            continue
        sessions = {problem.session_of(p) for p in placement.periods()}
        if len(sessions) != 1:
            violations.append(f'{task.id} 第{placement.meeting}单元连排跨时段（如午休）。')
        # 教室匹配
        room = problem.rooms.get(placement.room)
        if room is None:
            violations.append(f'{task.id} 使用未知教室 {placement.room}。')
            continue
        need_size = max(task.min_capacity, problem.class_size(task.classes))
        if room['capacity'] < need_size:
            violations.append(f'{task.id} 教室 {placement.room} 容量不足（{room["capacity"]}<{need_size}）。')
        if task.room_type and room['type'] != task.room_type:
            violations.append(f'{task.id} 教室 {placement.room} 类型不符（需 {task.room_type}）。')
        if task.fixed_room and placement.room != task.fixed_room:
            violations.append(f'{task.id} 未使用固定教室 {task.fixed_room}。')
        if task.equipment:
            if room['equipment'] != task.equipment:
                violations.append(f'{task.id} 教室 {placement.room} 设备不符。')
            elif task.min_sets and room['sets'] < task.min_sets:
                violations.append(f'{task.id} 教室 {placement.room} 台套数不足。')
        for period in placement.periods():
            for cid in task.classes:
                key = (cid, placement.day, period)
                if key in class_busy:
                    violations.append(f'班级冲突：{cid} {placement.day}第{period}节（{class_busy[key]} 与 {task.id}）。')
                class_busy[key] = task.id
                if (cid, placement.day, period) in blocked['class'] or ('*', placement.day, period) in blocked['global']:
                    violations.append(f'占用冲突：{cid} {placement.day}第{period}节 被 {task.id} 占用。')
            for tid in task.teachers:
                key = (tid, placement.day, period)
                if key in teacher_busy:
                    violations.append(f'教师冲突：{tid} {placement.day}第{period}节（{teacher_busy[key]} 与 {task.id}）。')
                teacher_busy[key] = task.id
                if (tid, placement.day, period) in blocked['teacher']:
                    violations.append(f'占用冲突：{tid} {placement.day}第{period}节。')
            key = (placement.room, placement.day, period)
            if key in room_busy:
                violations.append(f'教室冲突：{placement.room} {placement.day}第{period}节（{room_busy[key]} 与 {task.id}）。')
            room_busy[key] = task.id
            if (placement.room, placement.day, period) in blocked['room']:
                violations.append(f'占用冲突：{placement.room} {placement.day}第{period}节。')
        # 教学单元不得重复排入，长度须与拆分一致
        unit = (task.id, placement.meeting)
        if unit in placed_units:
            violations.append(f'{task.id} 第{placement.meeting}单元重复排入。')
        placed_units.add(unit)
        expected = task.meetings[placement.meeting].length if placement.meeting < len(task.meetings) else None
        if expected is not None and placement.length != expected:
            violations.append(f'{task.id} 第{placement.meeting}单元长度 {placement.length} 与拆分 {expected} 不符。')
    return violations


# ---------- 增量模式 ----------

def apply_changes(problem: Problem) -> tuple[list[Placement], list[Task], list[dict], list[dict]]:
    """把已有课表与变更请求整理为（固定排入, 新增任务, 变更记录, 待重排来源）。

    返回：
      fixed_placements  沿用原课表且仍可行的排入（fixed=True）
      new_tasks         变更新增的任务
      change_log        变更记录（取消/新增/占用调整）
      displaced         因不可用或冲突需要重排的 (task, meeting, origin)
    """
    cancelled = {str(c.get('taskId') or '') for c in problem.changes if c.get('kind') == 'cancel'}
    new_tasks: list[Task] = []
    change_log: list[dict] = []
    extra_blocks: list[Block] = []
    for change in problem.changes:
        kind = change.get('kind')
        if kind == 'cancel':
            change_log.append({'kind': '停开', 'taskId': change.get('taskId'),
                               'note': change.get('note') or ''})
        elif kind == 'add':
            change_log.append({'kind': '新增', 'taskId': change.get('task', {}).get('id'),
                               'note': change.get('note') or ''})
        elif kind == 'unavailable':
            change_log.append({'kind': '临时不可用', 'detail': change.get('note') or change.get('detail') or '',
                               'scope': change.get('scope')})
    # 新增任务：合并进 problem.tasks 之后统一建队列
    for change in problem.changes:
        if change.get('kind') != 'add':
            continue
        row = dict(change.get('task') or {})
        row.setdefault('id', f'NEW-{len(new_tasks) + 1}')
        problem._load_tasks([row])
        task = problem.tasks.get(row['id'])
        if task:
            new_tasks.append(task)

    # 占用调整：转成模板级或日历级 block 追加
    for change in problem.changes:
        if change.get('kind') != 'unavailable':
            continue
        scope = change.get('scope') or {}
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
        resolve = {'class': problem._resolve_class, 'teacher': problem._resolve_teacher,
                   'room': problem._resolve_room}[kind] if kind != 'global' else (lambda x: None)
        ids = [resolve(x) for x in raw] if kind != 'global' else []
        days = change.get('days') or None
        if isinstance(days, list):
            days = [d for d in (problem_days_normalize(problem, d) for d in days) if d]
        periods = change.get('periods') or None
        if isinstance(periods, list):
            periods = [p for p in periods if p in problem.period_by_id]
        weeks = change.get('weeks') or None
        extra_blocks.append(Block(id=f'CHG-{len(extra_blocks) + 1}', name=change.get('note') or '临时不可用',
                                  kind=kind, ids=[i for i in ids if i], weeks=weeks,
                                  days=days, periods=periods, note=''))
    problem.blocks.extend(extra_blocks)

    # 逐条核对已有排入：停开的跳过；违反硬约束的转待重排
    fixed_placements: list[Placement] = []
    displaced: list[tuple[Task, Meeting, dict]] = []
    probe = PlanState(problem)
    used: dict[tuple[str, int], int] = {}
    for row in problem.existing_placements:
        task = problem.tasks[row['taskId']]
        if task.id in cancelled:
            continue
        meeting = _match_meeting(task, row['length'], used)
        origin = {'day': row['day'], 'start': row['start'], 'room': row['room']}
        placement = Placement(task_id=task.id, meeting=meeting.index, length=meeting.length,
                              day=row['day'], start=row['start'], room=row['room'],
                              fixed=False, origin=origin)
        reason = None
        if row['length'] != meeting.length or row['start'] not in problem.period_by_id:
            reason = '节次信息与任务连排要求不符'
        else:
            probe.placements.append(placement)
            probe.add(placement, len(probe.placements) - 1)
            conflict = _any_violation(probe, placement)
            if conflict:
                probe.remove(len(probe.placements) - 1)
                probe.placements.pop()
                reason = conflict
        if reason:
            displaced.append((task, meeting, origin))
        else:
            placement.fixed = True
            fixed_placements.append(placement)
        used[(task.id, meeting.index)] = 1

    # 未出现在已有课表中的单元也进入待重排（新增或漏排）
    seen_units = {(p.task_id, p.meeting) for p in fixed_placements}
    seen_units |= {(t.id, m.index) for t, m, _o in displaced}
    for task in problem.tasks.values():
        if task.id in cancelled or task in new_tasks:
            continue
        for meeting in task.meetings:
            if (task.id, meeting.index) not in seen_units:
                displaced.append((task, meeting, None))
    return fixed_placements, new_tasks, change_log, displaced


def problem_days_normalize(problem: Problem, day) -> str | None:
    from .model import normalize_day
    return normalize_day(str(day), problem.days)


def _match_meeting(task: Task, length: int, used: dict) -> Meeting:
    """为已有排入行匹配任务内的教学单元（优先长度一致且未用）。"""
    for meeting in task.meetings:
        if meeting.length == length and (task.id, meeting.index) not in used:
            return meeting
    for meeting in task.meetings:
        if (task.id, meeting.index) not in used:
            return meeting
    return task.meetings[0]


def _any_violation(state: PlanState, placement: Placement) -> str | None:
    task = state.problem.tasks[placement.task_id]
    reason = state.conflict_reason(task, placement.day, placement.start,
                                   placement.length, placement.room)
    if reason:
        return {'class': '与班级其他安排冲突', 'teacher': '与教师其他安排冲突',
                'room': '与教室其他安排冲突', 'block': '落入不可用或占用时段'}.get(reason, reason)
    return None


def solve_incremental(problem: Problem, weights: dict[str, float], seed: int,
                      iterations: int = 2000, time_budget: float = 10.0) -> dict:
    fixed_placements, new_tasks, change_log, displaced = apply_changes(problem)
    origin_index = {(task.id, meeting.index): origin
                    for task, meeting, origin in displaced if origin}
    queue = [(task, meeting) for task, meeting, _origin in
             sorted(displaced, key=lambda tm: (tm[0].consecutive, tm[0].hours_per_week),
                    reverse=True)]
    queue = queue + [(t, m) for t in new_tasks for m in t.meetings]
    result = solve_plan(problem, weights, seed, iterations=iterations,
                        time_budget=time_budget, fixed=fixed_placements,
                        queue_override=queue, origin_index=origin_index)

    moved, removed = [], []
    for task, meeting, origin in displaced:
        if origin is None:
            continue
        entry = next((p for p in result['placements']
                      if p.task_id == task.id and p.meeting == meeting.index), None)
        if entry is None:
            removed.append({'taskId': task.id, 'course': task.course,
                            'from': origin, 'reason': '无法在现有约束下重新排入'})
        elif (entry.day, entry.start, entry.room) != (origin['day'], origin['start'], origin['room']):
            moved.append({'taskId': task.id, 'course': task.course,
                          'from': origin,
                          'to': {'day': entry.day, 'start': entry.start, 'room': entry.room}})
    added = [{'taskId': t.id, 'course': t.course} for t in new_tasks
             if any(p.task_id == t.id for p in result['placements'])]
    result['incremental'] = {
        'changes': change_log,
        'kept': sum(1 for p in result['placements'] if p.fixed),
        'moved': moved,
        'removed': removed,
        'added': added,
    }
    return result
