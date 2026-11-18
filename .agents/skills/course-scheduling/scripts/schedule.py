#!/usr/bin/env python3
"""排课智能体命令行入口。

子命令：template（生成空白模板）/ ingest（模板 CSV·XLSX → problem.json）/
validate / solve（多方案求解）/ page（方案对比 page.json）/ export（课表 xlsx + ics）。
输出 JSON 摘要供会话内智能体解析；校验失败退出码 2。
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scheduling import exportfiles, icsexport, metrics, pagegen, templates, xlsxio
from scheduling.model import PLAN_PROFILES, Problem, load_problem
from scheduling.solver import solve, solve_incremental, verify_plan

SOLUTIONS_SCHEMA = 'course-scheduling/solutions/1'


def _print_json(payload: dict):
    print(json.dumps(payload, ensure_ascii=False))


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _placement_dict(problem: Problem, p) -> dict:
    task = problem.tasks[p.task_id]
    basis = ['HC-01 教师时间不冲突', 'HC-02 班级时间不冲突',
             'HC-03 教室占用不冲突', 'HC-04 教室类型与容量匹配']
    if task.equipment:
        basis.append('HC-05 实训台套数满足')
    if p.length > 1:
        basis.append('HC-06 连排节次连续')
    if problem.blocks:
        basis.append('HC-07 占用时段避让')
    return {
        'taskId': p.task_id, 'meeting': p.meeting, 'course': task.course,
        'classes': task.classes, 'teachers': task.teachers,
        'day': p.day, 'start': p.start, 'periods': p.periods(),
        'length': p.length, 'room': p.room, 'category': task.category,
        'fixed': p.fixed, 'origin': p.origin, 'basis': basis,
    }


def _problem_head(problem: Problem) -> dict:
    return {
        'school': problem.school, 'semester': problem.semester,
        'weeks': problem.weeks, 'days': len(problem.days),
        'periods': len(problem.periods),
        'taskCount': len(problem.tasks), 'classCount': len(problem.classes),
        'roomCount': len(problem.rooms), 'teacherCount': len(problem.teachers),
        'blockCount': len(problem.blocks),
    }


def cmd_template(args):
    written = templates.write_template(args.out)
    _print_json({'ok': True, 'files': written,
                 'note': '模板含 xlsx 与逐表 csv；填写说明在首表。示例数据见技能 examples 目录。'})


def cmd_ingest(args):
    problem_data, errors = templates.build_problem(args.files)
    if errors:
        _print_json({'ok': False, 'errors': errors[:50]})
        return 2
    problem = Problem(problem_data)
    if problem.errors:
        _print_json({'ok': False, 'errors': problem.errors[:50], 'warnings': problem.warnings[:20]})
        return 2
    _write_json(Path(args.out), problem_data)
    head = _problem_head(problem)
    _print_json({'ok': True, 'out': args.out, 'problem': head,
                 'warnings': problem.warnings[:20],
                 'note': '数据已通过校验，可执行 solve。'})
    return 0


def cmd_validate(args):
    try:
        problem = load_problem(args.problem)
    except (OSError, ValueError) as exc:
        _print_json({'ok': False, 'errors': [str(exc)]})
        return 2
    if problem.errors:
        _print_json({'ok': False, 'errors': problem.errors[:50], 'warnings': problem.warnings[:20]})
        return 2
    _print_json({'ok': True, 'problem': _problem_head(problem), 'warnings': problem.warnings[:20]})
    return 0


def cmd_solve(args):
    try:
        problem = load_problem(args.problem)
    except (OSError, ValueError) as exc:
        _print_json({'ok': False, 'errors': [str(exc)]})
        return 2
    if problem.errors:
        _print_json({'ok': False, 'errors': problem.errors[:50]})
        return 2
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    plans_payload = []
    first_placements = []
    if args.incremental:
        result = solve_incremental(problem, dict(problem.weights), seed=args.seed or 7)
        first_placements = result['placements']
        plans_payload.append(_finalize_plan(problem, result, 'A', '最小扰动'))
    else:
        results = solve(problem, plan_count=args.plans, seeds=[args.seed] if args.seed else None)
        if not results:
            _print_json({'ok': False, 'errors': ['求解未产生方案，请检查任务与资源数据。']})
            return 2
        first_placements = results[0]['placements']
        for result in results:
            plans_payload.append(_finalize_plan(problem, result, result['id'], result['name']))

    solutions = {
        'schema': SOLUTIONS_SCHEMA,
        'generatedAt': datetime.datetime.now().isoformat(timespec='seconds'),
        'mode': 'incremental' if args.incremental else 'full',
        'fingerprint': problem.fingerprint(),
        'problem': _problem_head(problem),
        'plans': plans_payload,
        'effectiveHours': metrics.effective_hours_notes(problem, first_placements),
    }
    solutions['recommend'] = pagegen.recommend_plan(solutions)['id']
    _write_json(out_dir / 'solutions.json', solutions)
    _write_json(out_dir / 'problem.json', problem.raw)
    summary = {
        'ok': True, 'out': str(out_dir / 'solutions.json'),
        'mode': solutions['mode'], 'recommend': solutions['recommend'],
        'plans': [{'id': p['id'], 'name': p['name'],
                   'unplaced': p['metrics']['unplacedMeetings'],
                   'placedHours': p['metrics']['placedHours'],
                   'consecutiveRate': p['metrics']['consecutiveRate'],
                   'roomUtilization': p['metrics']['roomUtilization'],
                   'verified': p['verified']}
                  for p in plans_payload],
        'effectiveHours': solutions['effectiveHours'][:8],
    }
    if args.incremental and plans_payload:
        inc = plans_payload[0].get('incremental') or {}
        summary['incremental'] = {'kept': inc.get('kept', 0),
                                  'moved': len(inc.get('moved', [])),
                                  'removed': len(inc.get('removed', [])),
                                  'added': len(inc.get('added', []))}
    _print_json(summary)
    return 0


def _finalize_plan(problem: Problem, result: dict, plan_id: str, name: str) -> dict:
    violations = verify_plan(problem, result['placements'])
    plan_metrics = metrics.compute(problem, result['placements'], result['unplaced'])
    plan = {
        'id': plan_id, 'name': name, 'seed': result['seed'],
        'weights': result['weights'],
        'placements': [_placement_dict(problem, p) for p in result['placements']],
        'unplaced': result['unplaced'],
        'metrics': plan_metrics,
        'verified': not violations,
        'violations': violations,
    }
    if result.get('incremental'):
        plan['incremental'] = result['incremental']
    return plan


def _load_solutions_and_problem(args):
    solutions_path = Path(args.solutions)
    with open(solutions_path, 'r', encoding='utf-8') as fh:
        solutions = json.load(fh)
    problem_path = Path(args.problem) if args.problem else solutions_path.parent / 'problem.json'
    problem = load_problem(problem_path)
    if problem.errors:
        raise ValueError('problem.json 校验失败：' + '；'.join(problem.errors[:5]))
    return problem, solutions


def cmd_page(args):
    problem, solutions = _load_solutions_and_problem(args)
    page = pagegen.build_page(problem, solutions)
    _write_json(Path(args.out), page)
    _print_json({'ok': True, 'out': args.out, 'title': page['title'],
                 'blocks': len(page['blocks']), 'recommend': solutions.get('recommend'),
                 'note': 'page.json 数字取自 solutions.json，可直接交给 report-rendering 渲染。'})
    return 0


def cmd_export(args):
    from scheduling.model import Placement
    problem, solutions = _load_solutions_and_problem(args)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = out_dir / '课表.xlsx'
    if xlsx_path.exists():
        xlsx_path.unlink()
    xlsxio.write_xlsx(xlsx_path, exportfiles.build_workbook(problem, solutions, args.plan))
    rows = next(p for p in solutions['plans'] if p['id'] == args.plan)['placements']
    objects = [Placement(task_id=r['taskId'], meeting=r['meeting'], length=r['length'],
                         day=r['day'], start=r['start'], room=r['room']) for r in rows]
    ics_name = '课程日历.ics' if args.scope == 'all' else '课程日历-筛选.ics'
    ics_path = out_dir / ics_name
    ics_path.write_text(icsexport.build_ics(
        problem, objects, scope=args.scope,
        calendar_name=f'{problem.school} {problem.semester} 课表'.strip()),
        encoding='utf-8')
    _print_json({'ok': True, 'out': str(out_dir), 'files': [str(xlsx_path), str(ics_path)],
                 'summary': exportfiles.export_summary(solutions, args.plan),
                 'note': 'xlsx 含班级/教师/教室三视图与指标；ics 可导入日历应用。'})
    return 0


def cmd_manifest(args):
    import hashlib
    out_dir = Path(args.dir)
    if not out_dir.is_dir():
        _print_json({'ok': False, 'errors': [f'目录不存在：{args.dir}']})
        return 2
    root = Path.cwd().resolve()
    files = []
    for path in sorted(out_dir.iterdir()):
        if not path.is_file() or path.name.startswith('.'):
            continue
        if not path.resolve().is_relative_to(root):
            _print_json({'ok': False, 'errors': [f'{path} 不在当前工作区内']})
            return 2
        name = path.stem
        files.append({
            'name': f'{"课程日历" if path.suffix == ".ics" else name}（{path.suffix.lstrip(".").upper()}）',
            'path': path.resolve().relative_to(root).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    if not files:
        _print_json({'ok': False, 'errors': ['目录中没有可交付文件']})
        return 2
    _write_json(Path(args.out), {'files': files})
    _print_json({'ok': True, 'out': args.out, 'files': [f['path'] for f in files],
                 'note': 'files.json 供 register_delivery.py --files-from 登记下载项。'})
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='schedule.py', description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('template', help='生成空白输入模板')
    p.add_argument('--out', default='模板', help='模板输出目录')
    p.set_defaults(func=cmd_template)

    p = sub.add_parser('ingest', help='模板 CSV/XLSX → problem.json')
    p.add_argument('files', nargs='+', help='上传的模板文件（csv 或 xlsx）')
    p.add_argument('--out', default='problem.json')
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser('validate', help='校验 problem.json')
    p.add_argument('problem')
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser('solve', help='求解生成多套方案')
    p.add_argument('problem')
    p.add_argument('--out', default='run')
    p.add_argument('--plans', type=int, default=None, help='方案数（1-3，默认 3）')
    p.add_argument('--seed', type=int, default=None, help='固定随机种子（默认按方案取 11/23/37）')
    p.add_argument('--incremental', action='store_true', help='增量模式：最小扰动重排')
    p.set_defaults(func=cmd_solve)

    p = sub.add_parser('page', help='生成方案对比 page.json')
    p.add_argument('solutions')
    p.add_argument('--out', default='page.json')
    p.add_argument('--problem', default=None, help='覆盖 solutions 同目录的 problem.json')
    p.set_defaults(func=cmd_page)

    p = sub.add_parser('export', help='导出选定方案的课表 xlsx 与 ics')
    p.add_argument('solutions')
    p.add_argument('--plan', required=True, help='方案 id（如 A/B/C）')
    p.add_argument('--out', default='交付')
    p.add_argument('--scope', default='all', help='all | class:班级ID | teacher:教师ID')
    p.add_argument('--problem', default=None)
    p.set_defaults(func=cmd_export)

    p = sub.add_parser('manifest', help='生成交付文件清单 files.json（配合 register_delivery --files-from）')
    p.add_argument('dir', help='交付目录（如 交付/）')
    p.add_argument('--out', default='files.json')
    p.set_defaults(func=cmd_manifest)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError, KeyError, xlsxio.XlsxError) as exc:
        _print_json({'ok': False, 'errors': [str(exc)]})
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
