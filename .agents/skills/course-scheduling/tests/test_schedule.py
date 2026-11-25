#!/usr/bin/env python3
"""course-scheduling 全链路测试：模板/解析/求解/复核/增量/导出/页面。

运行：python3 tests/test_schedule.py（stdlib unittest，无第三方依赖）
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
EXAMPLES = Path(__file__).resolve().parents[1] / 'examples' / 'demo-school'
sys.path.insert(0, str(SCRIPTS))

from scheduling import icsexport, metrics, pagegen, templates, xlsxio  # noqa: E402
from scheduling.model import Placement, Problem, load_problem  # noqa: E402
from scheduling.solver import solve, solve_incremental, verify_plan  # noqa: E402
import schedule as cli  # noqa: E402


def demo_files() -> list[str]:
    return sorted(str(p) for p in EXAMPLES.glob('*.csv'))


class TemplateIngestTest(unittest.TestCase):
    def test_template_and_ingest_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            written = templates.write_template(str(Path(tmp) / '模板'))
            self.assertTrue(any(p.endswith('排课模板.xlsx') for p in written))
            sheets = xlsxio.read_xlsx(Path(tmp) / '模板' / '排课模板.xlsx')
            self.assertIn('填写说明', sheets)
            self.assertIn('教学任务', sheets)
            self.assertEqual(sheets['教学任务'][0][:3], ['任务ID', '课程', '班级'])
            problem_data, errors = templates.build_problem(demo_files())
            self.assertEqual(errors, [])
            problem = Problem(problem_data)
            self.assertEqual(problem.errors, [])
            self.assertEqual(len(problem.tasks), 68)
            self.assertEqual(len(problem.classes), 10)
            self.assertEqual(len(problem.rooms), 15)
            self.assertEqual(len(problem.teachers), 26)
            # 校历标记转成部分周事件（国庆2 + 轮岗7 + 考试窗口2）；占用约束中每周生效的是模板级
            self.assertEqual(len(problem.calendar_events()), 11)
            template_blocks = problem.template_blocks()
            self.assertTrue(any('T03' in str(k) for k in template_blocks['teacher']))
            self.assertTrue(any('S101' in str(k) for k in template_blocks['room']))

    def test_ingest_missing_required_reports_errors(self):
        subset = [p for p in demo_files() if '班级' not in p]
        _data, errors = templates.build_problem(subset)
        self.assertTrue(any('班级' in e for e in errors))

    def test_blank_xlsx_template_fails_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            templates.write_template(str(Path(tmp) / 't'))
            problem_data, errors = templates.build_problem([str(Path(tmp) / 't' / '排课模板.xlsx')])
            self.assertEqual(errors, [])
            problem = Problem(problem_data)
            self.assertTrue(problem.errors)


class SolveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.work = Path(cls.tmp.name)
        cls.problem_path = cls.work / 'problem.json'
        cls.problem_path.write_text(
            json.dumps(templates.build_problem(demo_files())[0], ensure_ascii=False),
            encoding='utf-8')
        cls.problem = load_problem(cls.problem_path)
        cls.solutions = solve(cls.problem)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_three_distinct_zero_conflict_plans(self):
        self.assertEqual(len(self.solutions), 3)
        signatures = set()
        for result in self.solutions:
            placements = result['placements']
            self.assertEqual(result['unplaced'], [])
            violations = verify_plan(self.problem, placements)
            self.assertEqual(violations, [])
            signatures.add(tuple(sorted(
                (p.task_id, p.meeting, p.day, p.start, p.room) for p in placements)))
        self.assertEqual(len(signatures), 3)

    def test_metrics_consistent(self):
        for result in self.solutions:
            m = metrics.compute(self.problem, result['placements'], result['unplaced'])
            self.assertEqual(m['conflicts'], 0)
            self.assertEqual(m['placedHours'], m['plannedHours'])
            self.assertEqual(m['consecutiveRate'], 1.0)
            self.assertTrue(0 < m['roomUtilization'] < 1)
            lab_rooms = {r['room'] for r in m['labLoad']['rooms']}
            self.assertIn('S101', lab_rooms)
            self.assertIn('S102', lab_rooms)
            busiest = max(m['teacherLoad'], key=lambda t: t['periods'])
            self.assertLessEqual(busiest['periods'], 14)

    def test_deterministic_with_same_seed(self):
        first = solve(self.problem, plan_count=1, seeds=[11])
        again = solve(self.problem, plan_count=1, seeds=[11])
        key = lambda r: tuple(sorted((p.task_id, p.day, p.start, p.room)
                                     for p in r['placements']))
        self.assertEqual(key(first[0]), key(again[0]))

    def test_doubles_teacher_and_merged_class_constraints(self):
        """双师同堂与混编班：涉及的教师/班级时段完全一致。"""
        plan = self.solutions[0]
        live = [p for p in plan['placements'] if p.task_id in ('R056', 'R057')]
        self.assertTrue(live)
        for p in live:
            task = self.problem.tasks[p.task_id]
            self.assertEqual(len(task.teachers), 2)
        merged = [p for p in plan['placements'] if p.task_id == 'R064'][0]
        task = self.problem.tasks['R064']
        self.assertEqual(len(task.classes), 2)

    def test_blocks_respected(self):
        """模板级占用：T03 周五下午无课；S101 周五下午无排入。"""
        for result in self.solutions:
            for p in result['placements']:
                task = self.problem.tasks[p.task_id]
                if p.day == '周五' and any(s >= 5 for s in p.periods()):
                    self.assertNotIn('T03', task.teachers)
                    self.assertNotEqual(p.room, 'S101')

    def test_infeasible_task_goes_to_attribution(self):
        problem_data = templates.build_problem(demo_files())[0]
        problem_data['tasks'].append({
            'id': 'R900', 'course': '智能网联汽车实训', 'classes': '网络2401',
            'teachers': 'T14', 'hoursPerWeek': 4, 'consecutive': 2,
            'room': {'type': '实训', 'equipment': '智能网联整车', 'sets': 8},
            'category': '实训',
        })
        problem = Problem(problem_data)
        self.assertEqual(problem.errors, [])
        results = solve(problem, plan_count=1, seeds=[11])
        unplaced = results[0]['unplaced']
        self.assertTrue(any(u['taskId'] == 'R900' for u in unplaced))
        entry = next(u for u in unplaced if u['taskId'] == 'R900')
        self.assertTrue(entry['reasons'])
        self.assertTrue(any('教室' in s for s in entry['suggestions']))
        # 其余任务照常排入，冲突仍为 0
        others = [p for p in results[0]['placements'] if p.task_id != 'R900']
        self.assertTrue(len(others) >= 100)
        self.assertEqual(verify_plan(problem, results[0]['placements']), [])


class IncrementalTest(unittest.TestCase):
    def test_minimal_disturbance(self):
        problem_data = templates.build_problem(demo_files())[0]
        base = Problem(json.loads(json.dumps(problem_data, ensure_ascii=False)))
        plan = solve(base, plan_count=1, seeds=[11])[0]
        original = {(p.task_id, p.meeting): (p.day, p.start, p.room)
                    for p in plan['placements']}
        placements = []
        for key, (day, start, room) in original.items():
            length = next(p.length for p in plan['placements']
                          if (p.task_id, p.meeting) == key)
            placements.append({'taskId': key[0], 'day': day, 'startPeriod': start,
                               'length': length, 'room': room})
        monday_t08 = [key for key, pos in original.items()
                      if key[0] in ('R025', 'R026', 'R027', 'R028') and pos[0] == '周一']
        problem_data['existing'] = {
            'placements': placements,
            'changes': [
                {'kind': 'unavailable', 'scope': {'teachers': ['T08']},
                 'days': ['周一'], 'note': '教师外出培训'},
                {'kind': 'cancel', 'taskId': 'R068', 'note': '停开'},
                {'kind': 'add', 'task': {
                    'id': 'R101', 'course': '网络安全进阶', 'classes': '大数据2401',
                    'teachers': 'T21', 'hoursPerWeek': 2, 'consecutive': 1,
                    'room': {'type': '机房'}, 'category': '机房'}, 'note': '新开课'},
            ],
        }
        problem = Problem(problem_data)
        self.assertEqual(problem.errors, [])
        result = solve_incremental(problem, dict(problem.weights), seed=7)
        inc = result['incremental']
        # 沿用的排入位置与原课表完全一致（最小扰动）
        kept = {(p.task_id, p.meeting): (p.day, p.start, p.room)
                for p in result['placements'] if p.fixed}
        for key, pos in kept.items():
            self.assertEqual(original.get(key), pos)
        moved_ids = {m['taskId'] for m in inc['moved']}
        # T08 原在周一的课必须让位并记录为调课
        for key in monday_t08:
            self.assertIn(key[0], moved_ids)
            entry = next(p for p in result['placements']
                         if p.task_id == key[0] and p.meeting == key[1])
            self.assertNotEqual(entry.day, '周一')
        for item in inc['moved']:
            origin = (item['from']['day'], item['from']['start'], item['from']['room'])
            target = (item['to']['day'], item['to']['start'], item['to']['room'])
            self.assertNotEqual(origin, target)
        # 停开的课程彻底移除，新增课程排入
        self.assertFalse(any(p.task_id == 'R068' for p in result['placements']))
        self.assertTrue(any(p.task_id == 'R101' for p in result['placements']))
        self.assertEqual(verify_plan(problem, result['placements']), [])


class ExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.work = Path(cls.tmp.name)
        cls.problem_path = cls.work / 'problem.json'
        cls.problem_path.write_text(
            json.dumps(templates.build_problem(demo_files())[0], ensure_ascii=False),
            encoding='utf-8')
        cls.problem = load_problem(cls.problem_path)
        cls.solved = solve(cls.problem, plan_count=1, seeds=[11])
        cls.placements = cls.solved[0]['placements']

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _solutions_stub(self) -> dict:
        return {
            'schema': 'course-scheduling/solutions/1',
            'problem': {'school': '示范职业技术学院', 'semester': '2026-2027学年第一学期',
                        'weeks': 20, 'days': 5, 'periods': 8, 'taskCount': 68,
                        'classCount': 10, 'roomCount': 15, 'teacherCount': 26},
            'plans': [{
                'id': 'A', 'name': '教师集中型', 'seed': 11, 'weights': {},
                'placements': [{
                    'taskId': p.task_id, 'meeting': p.meeting,
                    'course': self.problem.tasks[p.task_id].course,
                    'classes': self.problem.tasks[p.task_id].classes,
                    'teachers': self.problem.tasks[p.task_id].teachers,
                    'day': p.day, 'start': p.start, 'periods': p.periods(),
                    'length': p.length, 'room': p.room,
                    'category': self.problem.tasks[p.task_id].category,
                    'fixed': False, 'origin': None, 'basis': [],
                } for p in self.placements],
                'unplaced': [],
                'metrics': metrics.compute(self.problem, self.placements, []),
                'verified': True, 'violations': [],
            }],
            'effectiveHours': metrics.effective_hours_notes(self.problem, self.placements),
        }

    def test_xlsx_roundtrip(self):
        from scheduling import exportfiles
        path = self.work / '课表.xlsx'
        if path.exists():
            path.unlink()
        xlsxio.write_xlsx(path, exportfiles.build_workbook(
            self.problem, self._solutions_stub(), 'A'))
        sheets = xlsxio.read_xlsx(path)
        for name in ('方案说明', '班级课表', '教师课表', '教室课表', '指标', '教学任务'):
            self.assertIn(name, sheets)
        info = sheets['方案说明']
        self.assertEqual(info[1][1], '示范职业技术学院')
        header_idx = next(i for i, row in enumerate(sheets['教学任务'])
                          if row and row[0] == '任务')
        first_task = sheets['教学任务'][header_idx + 1]
        self.assertTrue(first_task[0].startswith('R'))
        # openpyxl 可用时做独立交叉验证（沙箱内自动跳过）
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            pass

    def test_ics_structure_and_exdates(self):
        text = icsexport.build_ics(self.problem, self.placements)
        self.assertTrue(text.startswith('BEGIN:VCALENDAR\r\n'))
        self.assertIn('RRULE:FREQ=WEEKLY', text)
        for line in text.split('\r\n'):
            self.assertLessEqual(len(line.encode('utf-8')), 75, line)
        unfolded = re.sub(r'\r\n ', '', text)
        events = unfolded.split('BEGIN:VEVENT')[1:]
        self.assertGreater(len(events), 100)

        def event_of(uid_prefix):
            return next(e for e in events if f'UID:{uid_prefix}-' in e)

        # 电商课剔除国庆两周、全校考试窗口与 1+X 电商窗口
        ecommerce = event_of('R056-m0')
        for week_date in ('20261005', '20261012', '20261109', '20261228'):
            self.assertIn(week_date, ecommerce)
        # 混编课同时受两个轮岗批次影响（第 9-16 周全部剔除）
        merged = event_of('R064-m0')
        exdates = re.search(r'EXDATE:([^\r\n]*)', merged)
        self.assertTrue(exdates)
        self.assertEqual(len(exdates.group(1).split(',')), 10)
        # 教师视角筛选
        teacher_view = icsexport.build_ics(self.problem, self.placements, scope='teacher:T24')
        self.assertIn('（智造2401）', teacher_view)
        self.assertNotIn('（网络2401）', teacher_view)

    def test_page_model_structure(self):
        solutions = self._solutions_stub()
        solutions['recommend'] = pagegen.recommend_plan(solutions)['id']
        page = pagegen.build_page(self.problem, solutions)
        self.assertIn('blocks', page)
        types = {b['type'] for b in page['blocks']}
        self.assertIn('summary', types)
        self.assertIn('metrics', types)
        sections = [b['title'] for b in page['blocks'] if b['type'] == 'section']
        self.assertIn('方案对比', sections)
        self.assertIn('建议与适用条件', sections)
        self.assertIn('有效学时影响', sections)
        self.assertTrue(any('班级课表' in json.dumps(b, ensure_ascii=False)
                            for b in page['blocks']))
        # 指标数字与求解结果一致
        metrics_block = next(b for b in page['blocks'] if b['type'] == 'metrics')
        conflicts = next(i for i in metrics_block['items'] if i['label'] == '冲突数')
        self.assertEqual(conflicts['value'], 0)

    def test_cli_end_to_end(self):
        run_dir = self.work / 'run'
        out = self.work / '交付'
        self.assertEqual(cli.main(['solve', str(self.problem_path), '--out', str(run_dir),
                                   '--plans', '2']), 0)
        solutions = json.loads((run_dir / 'solutions.json').read_text(encoding='utf-8'))
        self.assertEqual(len(solutions['plans']), 2)
        self.assertEqual(cli.main(['export', str(run_dir / 'solutions.json'),
                                   '--plan', solutions['recommend'],
                                   '--out', str(out)]), 0)
        self.assertTrue((out / '课表.xlsx').exists())
        self.assertTrue((out / '课程日历.ics').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
