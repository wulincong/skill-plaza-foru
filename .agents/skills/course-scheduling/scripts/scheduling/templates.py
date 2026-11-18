"""输入模板与解析：空白模板生成、CSV/XLSX 模板解析为 problem.json。

模板列名支持常用别名（见 ALIASES）；多值单元格用分号分隔。
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from . import xlsxio

SHEETS: dict[str, dict] = {
    '信息': {'columns': ['项目', '内容']},
    '班级': {'columns': ['班级ID', '班级名称', '人数', '专业']},
    '教师': {'columns': ['教师ID', '姓名', '授课偏好']},
    '教室': {'columns': ['教室ID', '类型', '容量', '设备名称', '台套数', '备注']},
    '教学任务': {'columns': ['任务ID', '课程', '班级', '任课教师', '周学时', '连排节数',
                        '教室类型', '最低容量', '设备名称', '台套数要求', '固定教室', '课程类别', '备注']},
    '作息时间': {'columns': ['节次', '名称', '开始时间', '结束时间', '时段']},
    '校历': {'columns': ['周次', '标记', '名称', '范围', '备注']},
    '占用约束': {'columns': ['约束ID', '名称', '对象类型', '对象', '周次', '星期', '节次', '备注']},
    '已有课表': {'columns': ['任务ID', '星期', '开始节次', '节数', '教室']},
    '权重设置': {'columns': ['权重项', '数值']},
}

REQUIRED = ['信息', '班级', '教室', '教学任务', '作息时间', '校历']

FILE_KEYWORDS = {
    '信息': ['信息', '基本信息', '学校', '学期'],
    '班级': ['班级'],
    '教师': ['教师', '师资', '老师'],
    '教室': ['教室', '场地', '资源', '实训室'],
    '教学任务': ['教学任务', '任务', '课程', '开课'],
    '作息时间': ['作息', '时间表', '节次'],
    '校历': ['校历', '教学周', '周历'],
    '占用约束': ['占用', '约束', '不可用', '轮岗', '窗口'],
    '已有课表': ['已有课表', '现有课表', '原课表'],
    '权重设置': ['权重', '设置'],
}

ALIASES: dict[str, dict[str, str]] = {
    '班级': {'班级id': '班级ID', 'id': '班级ID', '班级': '班级ID', '班级名称': '班级名称',
             '名称': '班级名称', '人数': '人数', '班级人数': '人数', '学生数': '人数',
             '专业': '专业', '专业名称': '专业'},
    '教师': {'教师id': '教师ID', 'id': '教师ID', '工号': '教师ID', '姓名': '姓名',
             '教师姓名': '姓名', '授课偏好': '授课偏好', '偏好': '授课偏好',
             '时间偏好': '授课偏好'},
    '教室': {'教室id': '教室ID', 'id': '教室ID', '教室名称': '教室ID', '名称': '教室ID',
             '类型': '类型', '教室类型': '类型', '容量': '容量', '容纳人数': '容量',
             '设备名称': '设备名称', '设备': '设备名称', '台套数': '台套数', '设备台套数': '台套数',
             '备注': '备注'},
    '教学任务': {'任务id': '任务ID', 'id': '任务ID', '任务编号': '任务ID', '课程': '课程',
              '课程名称': '课程', '班级': '班级', '授课班级': '班级', '上课班级': '班级',
              '任课教师': '任课教师', '教师': '任课教师', '授课教师': '任课教师',
              '周学时': '周学时', '每周学时': '周学时', '学时': '周学时',
              '连排节数': '连排节数', '连排': '连排节数', '连堂': '连排节数',
              '教室类型': '教室类型', '需要教室类型': '教室类型',
              '最低容量': '最低容量', '设备名称': '设备名称', '设备': '设备名称',
              '台套数要求': '台套数要求', '台套数': '台套数要求',
              '固定教室': '固定教室', '课程类别': '课程类别', '类别': '课程类别', '备注': '备注'},
    '作息时间': {'节次': '节次', '节次id': '节次', '名称': '名称', '节次名称': '名称',
              '开始时间': '开始时间', '结束时间': '结束时间', '时段': '时段', '上午下午': '时段'},
    '校历': {'周次': '周次', '教学周': '周次', '星期': '星期', '标记': '标记', '类型': '标记',
           '名称': '名称', '事件': '名称', '范围': '范围', '对象': '范围', '备注': '备注'},
    '占用约束': {'约束id': '约束ID', 'id': '约束ID', '名称': '名称', '说明': '名称',
              '对象类型': '对象类型', '类型': '对象类型', '对象': '对象', '范围': '对象',
              '周次': '周次', '教学周': '周次', '星期': '星期', '星期几': '星期', ' day': '星期',
              '节次': '节次', '时段': '节次', '备注': '备注'},
    '已有课表': {'任务id': '任务ID', 'id': '任务ID', '星期': '星期', '星期几': '星期',
              '开始节次': '开始节次', '起始节次': '开始节次', '节数': '节数', '连排节数': '节数',
              '教室': '教室', '上课教室': '教室'},
    '信息': {'项目': '项目', '键': '项目', '内容': '内容', '值': '内容', '数值': '内容'},
    '权重设置': {'权重项': '权重项', '名称': '权重项', '数值': '数值', '值': '数值'},
}

INFO_HINTS = [
    ['学校名称', '（必填）学校或校区名称'],
    ['学期名称', '（必填）如 2026-2027 学年第一学期'],
    ['开学周一', '（必填）第 1 教学周的周一日期，格式 2026-09-07'],
    ['总周数', '（必填）本学期教学周总数，如 20'],
    ['教学日', '（选填）默认 周一至周五；也可写 周一至周六'],
]

FILL_GUIDE = [
    ['本模板各表填写说明：'],
    ['教学任务', '每行一项教学任务；班级与任课教师多值用分号分隔（双师协同、混编班即在此表达）。'],
    ['教室', '实训室填写设备名称与台套数；台套数是排课硬约束上限。'],
    ['校历', '每个教学周一行；假期、1+X 考试窗口、企业轮岗用标记列注明，范围列写 全校 或 班级:某某2401。'],
    ['占用约束', '每周生效的不可用时段（如教师例会、教室检修）填这里；周次留空表示每周。'],
    ['已有课表', '增量模式使用：填现有排入后，配合调停课需求做最小扰动重排。'],
    ['权重设置', '软约束权重可配：教师集中、午后体育、同类错峰、教室稳定、负载均衡，数值越大越优先。'],
    ['完整示例见技能 examples/demo-school 目录，可直接试跑。'],
]


def _norm_header(text: str) -> str:
    return re.sub(r'\s+', '', str(text or '')).replace('（', '(').replace('）', ')')


def normalize_key(sheet: str, value: str) -> str | None:
    key = _norm_header(value).lower()
    if key in ALIASES.get(sheet, {}):
        return ALIASES[sheet][key]
    canonical = {_norm_header(c).lower(): c for c in SHEETS[sheet]['columns']}
    return canonical.get(key)


def template_sheets() -> list[dict]:
    sheets = [{'name': '填写说明', 'rows': [['模板填写说明']] + [[t, *rest] for t, *rest in FILL_GUIDE],
               'widths': [12, 96]}]
    for name, spec in SHEETS.items():
        rows = [spec['columns']]
        if name == '信息':
            rows.extend(INFO_HINTS)
        widths = [max(10, min(22, len(c) * 2 + 4)) for c in spec['columns']]
        sheets.append({'name': name, 'rows': rows, 'widths': widths})
    return sheets


def write_template(out_dir: str):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    xlsxio.write_xlsx(out / '排课模板.xlsx', template_sheets())
    written = [str(out / '排课模板.xlsx')]
    for i, (name, spec) in enumerate(SHEETS.items(), 1):
        path = out / f'{i:02d}-{name}.csv'
        with open(path, 'w', encoding='utf-8-sig', newline='') as fh:
            writer = csv.writer(fh)
            writer.writerow(spec['columns'])
            if name == '信息':
                writer.writerows(INFO_HINTS)
        written.append(str(path))
    return written


def _read_csv(path: Path) -> list[list]:
    raw = path.read_bytes().decode('utf-8-sig', errors='replace')
    header_line = raw.splitlines()[0] if raw.splitlines() else ''
    delimiter = ',' if header_line.count(',') >= header_line.count(';') else ';'
    if header_line.count('\t') > header_line.count(delimiter):
        delimiter = '\t'
    rows = list(csv.reader(io.StringIO(raw), delimiter=delimiter))
    return [[(cell.strip() if isinstance(cell, str) else cell) for cell in row] for row in rows]


def _match_sheet_name(name: str) -> str | None:
    normalized = _norm_header(name)
    for sheet, keywords in FILE_KEYWORDS.items():
        if any(_norm_header(k) in normalized or normalized in _norm_header(k) for k in keywords):
            return sheet
    return None


def collect_tables(paths: list[str]) -> tuple[dict[str, list[list]], list[str]]:
    """把上传的 CSV/XLSX 归并为 {模板表名: 行列表}；返回 (tables, errors)。"""
    tables: dict[str, list[list]] = {}
    errors: list[str] = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            errors.append(f'文件不存在：{raw}')
            continue
        suffix = path.suffix.lower()
        try:
            if suffix == '.xlsx':
                for sheet_name, rows in xlsxio.read_xlsx(path).items():
                    target = _match_sheet_name(sheet_name)
                    if target is None:
                        continue
                    if target in tables:
                        errors.append(f'表“{target}”出现多次（{sheet_name}），仅保留第一份。')
                        continue
                    tables[target] = rows
            elif suffix == '.csv':
                target = _match_sheet_name(path.stem)
                if target is None:
                    errors.append(f'无法识别文件“{path.name}”对应哪张模板表，请按模板命名。')
                    continue
                if target in tables:
                    errors.append(f'表“{target}”出现多次（{path.name}），仅保留第一份。')
                    continue
                tables[target] = _read_csv(path)
            else:
                errors.append(f'不支持的文件类型 {suffix}：{path.name}（请用模板 xlsx 或 csv）。')
        except xlsxio.XlsxError as exc:
            errors.append(str(exc))
    return tables, errors


def _rows_to_dicts(sheet: str, rows: list[list]) -> tuple[list[dict], list[str]]:
    """按表头别名把行转为字典列表。"""
    if not rows:
        return [], []
    header = [normalize_key(sheet, cell) for cell in rows[0]]
    unknown = [str(rows[0][i]) for i, key in enumerate(header) if key is None]
    errors = [f'表“{sheet}”存在无法识别的列：{name}' for name in unknown]
    dicts: list[dict] = []
    for row in rows[1:]:
        if not any(str(cell).strip() for cell in row):
            continue
        entry = {}
        for i, key in enumerate(header):
            if key is None or i >= len(row):
                continue
            value = row[i]
            if isinstance(value, str):
                value = value.strip()
            entry[key] = value
        if any(str(v).strip() for v in entry.values() if v is not None):
            dicts.append(entry)
    return dicts, errors


def _to_int(value, default=None):
    if value is None or value == '':
        return default
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def _scope_from_text(sheet: str, type_text: str, ids_text: str) -> tuple[str, list[str]]:
    kind = {'全校': 'global', '班级': 'class', '教师': 'teacher', '教室': 'room'}.get(
        str(type_text).strip(), None)
    ids = [p for p in re.split(r'[;；,，、\s]+', str(ids_text or '')) if p]
    if kind is None:
        m = re.match(r'(班级|教师|教室)[:：](.+)', str(type_text).strip())
        if m:
            return {'班级': 'class', '教师': 'teacher', '教室': 'room'}[m.group(1)], [
                p for p in re.split(r'[;；,，、\s]+', m.group(2)) if p]
        return ('global' if not ids else 'class'), ids
    return kind, ids


def build_problem(paths: list[str]) -> tuple[dict, list[str]]:
    """从模板文件构建 problem.json 字典；返回 (problem, errors)。"""
    tables, errors = collect_tables(paths)
    for sheet in REQUIRED:
        if sheet not in tables:
            errors.append(f'缺少必填表“{sheet}”，请按模板补齐后重新上传。')
    if errors:
        return {}, errors

    problem: dict = {'schema': 'course-scheduling/1', 'meta': {}, 'calendar': {},
                     'timetable': {}, 'classes': [], 'teachers': [], 'rooms': [],
                     'tasks': [], 'blocks': [], 'weights': {}, 'options': {}}
    parsed = {name: _rows_to_dicts(name, rows) for name, rows in tables.items()}
    for name, (_dicts, row_errors) in parsed.items():
        errors.extend(row_errors)
    info = {str(row.get('项目') or '').strip(): row.get('内容')
            for row in parsed['信息'][0]}
    problem['meta']['school'] = str(info.get('学校名称') or '').strip()
    problem['meta']['semester'] = str(info.get('学期名称') or '').strip()
    problem['calendar']['startWeek'] = str(info.get('开学周一') or '').strip()
    problem['calendar']['weeks'] = _to_int(info.get('总周数'), 20) or 20
    days_text = str(info.get('教学日') or '').strip()
    problem['timetable']['days'] = parse_days(days_text) or ['周一', '周二', '周三', '周四', '周五']

    for row in parsed['班级'][0]:
        problem['classes'].append({
            'id': str(row.get('班级ID') or '').strip(),
            'name': str(row.get('班级名称') or row.get('班级ID') or '').strip(),
            'size': _to_int(row.get('人数'), 0),
            'program': str(row.get('专业') or '').strip(),
        })
    for row in parsed['教师'][0] if '教师' in parsed else []:
        problem['teachers'].append({
            'id': str(row.get('教师ID') or '').strip(),
            'name': str(row.get('姓名') or '').strip(),
            'preference': {'集中': 'compact', '分散': 'spread', '不限': 'balanced', '': 'balanced'}.get(
                str(row.get('授课偏好') or '').strip(), 'balanced'),
        })
    for row in parsed['教室'][0]:
        problem['rooms'].append({
            'id': str(row.get('教室ID') or '').strip(),
            'type': str(row.get('类型') or '普通').strip(),
            'capacity': _to_int(row.get('容量'), 0),
            'equipment': str(row.get('设备名称') or '').strip() or None,
            'sets': _to_int(row.get('台套数'), 0),
            'note': str(row.get('备注') or '').strip(),
        })
    for row in parsed['教学任务'][0]:
        room: dict = {}
        if str(row.get('教室类型') or '').strip():
            room['type'] = str(row.get('教室类型')).strip()
        if _to_int(row.get('最低容量')):
            room['minCapacity'] = _to_int(row.get('最低容量'))
        if str(row.get('设备名称') or '').strip():
            room['equipment'] = str(row.get('设备名称')).strip()
        if _to_int(row.get('台套数要求')):
            room['sets'] = _to_int(row.get('台套数要求'))
        if str(row.get('固定教室') or '').strip():
            room['fixed'] = str(row.get('固定教室')).strip()
        problem['tasks'].append({
            'id': str(row.get('任务ID') or '').strip(),
            'course': str(row.get('课程') or '').strip(),
            'classes': str(row.get('班级') or '').strip(),
            'teachers': str(row.get('任课教师') or '').strip(),
            'hoursPerWeek': _to_int(row.get('周学时'), 0),
            'consecutive': _to_int(row.get('连排节数'), 1) or 1,
            'room': room,
            'category': str(row.get('课程类别') or '').strip(),
            'note': str(row.get('备注') or '').strip(),
        })
    periods = []
    for row in parsed['作息时间'][0]:
        periods.append({
            'id': _to_int(row.get('节次'), len(periods) + 1),
            'label': str(row.get('名称') or f'第{_to_int(row.get("节次"), len(periods) + 1)}节').strip(),
            'start': str(row.get('开始时间') or '').strip(),
            'end': str(row.get('结束时间') or '').strip(),
            'session': str(row.get('时段') or '全天').strip(),
        })
    problem['timetable']['periods'] = periods

    # 校历：周标记 → 部分周占用块（假期/考试窗口/企业轮岗）
    for row in parsed['校历'][0]:
        mark = str(row.get('标记') or '正常').strip()
        if mark in ('', '正常', '教学'):
            continue
        week = _to_int(row.get('周次'))
        if not week:
            continue
        scope_text = str(row.get('范围') or '全校').strip()
        kind, ids = _scope_from_text('校历', scope_text, scope_text)
        scope: dict = {}
        if kind == 'class':
            scope['classes'] = ids
        elif kind == 'teacher':
            scope['teachers'] = ids
        elif kind == 'room':
            scope['rooms'] = ids
        name = str(row.get('名称') or mark).strip()
        problem['blocks'].append({
            'id': f'CAL-{week}-{len(problem["blocks"]) + 1}',
            'name': f'{name}（第{week}周）',
            'scope': scope, 'weeks': [week],
            'note': str(row.get('备注') or '').strip(),
        })

    # 占用约束：不可用时段（周次留空 = 每周生效的模板级硬约束）
    if '占用约束' in parsed:
        for row in parsed['占用约束'][0]:
            if not str(row.get('约束ID') or row.get('名称') or '').strip():
                continue
            kind, ids = _scope_from_text(
                '占用约束', str(row.get('对象类型') or '').strip(), str(row.get('对象') or '').strip())
            scope: dict = {}
            if kind == 'class':
                scope['classes'] = ids
            elif kind == 'teacher':
                scope['teachers'] = ids
            elif kind == 'room':
                scope['rooms'] = ids
            block: dict = {
                'id': str(row.get('约束ID') or '').strip(),
                'name': str(row.get('名称') or row.get('约束ID') or '').strip(),
                'scope': scope,
            }
            weeks = _range_text(row.get('周次'))
            days = [d for d in str(row.get('星期') or '').split(';') if d.strip()]
            periods_text = _range_text(row.get('节次'))
            if weeks:
                block['weeks'] = weeks
            if days:
                block['days'] = days
            if periods_text:
                block['periods'] = periods_text
            block['note'] = str(row.get('备注') or '').strip()
            problem['blocks'].append(block)

    # 已有课表（增量模式）
    if '已有课表' in parsed:
        placements = []
        for row in parsed['已有课表'][0]:
            if not str(row.get('任务ID') or '').strip():
                continue
            placements.append({
                'taskId': str(row.get('任务ID')).strip(),
                'day': str(row.get('星期') or '').strip(),
                'startPeriod': _to_int(row.get('开始节次')),
                'length': _to_int(row.get('节数'), 1),
                'room': str(row.get('教室') or '').strip(),
            })
        if placements:
            problem['existing'] = {'placements': placements, 'changes': []}

    # 权重设置
    weight_alias = {'教师集中': 'teacherCompact', '午后体育': 'afternoonPe',
                    '同类错峰': 'categoryStagger', '教室稳定': 'roomStability',
                    '负载均衡': 'balance'}
    if '权重设置' in parsed:
        for row in parsed['权重设置'][0]:
            key_text = str(row.get('权重项') or '').strip()
            key = weight_alias.get(key_text, key_text if key_text in
                                   ('teacherCompact', 'afternoonPe', 'categoryStagger',
                                    'roomStability', 'balance') else None)
            value = _to_int(row.get('数值'))
            if key and value is not None:
                problem['weights'][key] = value
    return problem, errors


def parse_days(text: str) -> list[str] | None:
    """解析 “周一至周五” / “周一;周三” 一类的教学日设置。"""
    text = str(text or '').strip().replace('周天', '周日')
    if not text:
        return None
    all_days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    m = re.fullmatch(r'周([一二三四五六日])\s*[-—~至]\s*周?([一二三四五六日])', text)
    if m:
        start = '一二三四五六日'.index(m.group(1))
        end = '一二三四五六日'.index(m.group(2))
        return all_days[start:end + 1] if start <= end else None
    days = [d for d in (p.strip() for p in re.split(r'[;；,，、\s]+', text)) if d]
    return days or None


def _range_text(value) -> list[int] | None:
    from .model import parse_int_range
    if value is None or str(value).strip() == '':
        return None
    return parse_int_range(str(value))
