#!/usr/bin/env python3
"""学勤与教学诊断 · 数据检查与指标计算。

只用 Python 标准库，在广场沙箱内运行。子命令：

  inspect    逐文件质量检查（列、编码、缺失、重复、口径信号）
  metrics    按班级/教师/专业三层计算出勤、成绩、评教、进度指标
  correlate  缺勤-成绩、评教-教学结果的关联（带样本量与小样本标记）
  risk       按阈值生成出勤/学业风险名单（须先经用户授权）
  compare    与上一周期档案做同口径对比（口径不符即拒绝并列）

用法示例（绝对路径调用，不在技能目录内执行）：

  python3 <技能目录>/scripts/analyze.py inspect uploads/考勤.csv uploads/成绩.xlsx --json analysis/inspect.json
  python3 <技能目录>/scripts/analyze.py metrics --config analysis/config.json --json analysis/metrics.json
"""
import argparse
import csv
import io
import json
import math
import re
import sys
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

VERSION = 'teaching-diagnosis/analyze.py v1'

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
RELNS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
BUILTIN_DATE_FMT = set(range(14, 23)) | {45, 46, 47}
EXCEL_EPOCH = date(1899, 12, 30)
DEFAULT_MIN_CORR_N = 30          # 班级内学生数低于此值不给相关推断
DEFAULT_MIN_TEACHER_N = 10       # 教师层关联分析的最小样本
DEFAULT_RISK = {'absenceRate': 0.2, 'absenceCount': 10, 'meanScore': 60.0, 'failCourses': 2}


class DataError(Exception):
    pass


# ---------------------------------------------------------------- 表格读取

def detect_delimiter(text):
    head = '\n'.join(text.splitlines()[:5])
    counts = {d: head.count(d) for d in (',', '\t', ';', '|')}
    best = max(counts, key=lambda d: counts[d])
    return best if counts[best] > 0 else ','


def read_csv(path):
    raw = Path(path).read_bytes()
    text = used = None
    for enc in ('utf-8-sig', 'utf-8', 'gb18030'):
        try:
            text = raw.decode(enc)
            used = enc
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise DataError(f'{path}: 无法按 utf-8 / gb18030 解码，请另存为 UTF-8 或 GBK 编码的 CSV')
    delim = detect_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    columns = [c.strip() for c in (reader.fieldnames or [])]
    rows = []
    for raw_row in reader:
        row = {}
        for key, val in raw_row.items():
            name = (key or '').strip()
            if name:
                row[name] = (val or '').strip()
        rows.append(row)
    notes = []
    if len(columns) != len(set(columns)):
        notes.append('存在重复列名，重复者已加序号后缀')
        seen = {}
        fixed = []
        for name in columns:
            if columns.count(name) > 1:
                seen[name] = seen.get(name, 0) + 1
                fixed.append(f'{name}({seen[name]})' if seen[name] > 1 else name)
            else:
                fixed.append(name)
        columns = fixed
    return {
        'columns': columns,
        'rows': rows,
        'meta': {'format': 'csv', 'encoding': used, 'delimiter': {'\t': 'TAB'}.get(delim, delim)},
        'notes': notes,
    }


def _is_date_code(code):
    code = code.lower()
    return any(tok in code for tok in ('yy', 'm"月"', 'h"时"', 'mm:', 'dd')) and '0.0' not in code


def read_xlsx(path, sheet=None):
    notes = []
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        if 'xl/workbook.xml' not in names:
            raise DataError(f'{path}: 不是有效的 xlsx 工作簿')
        shared = []
        if 'xl/sharedStrings.xml' in names:
            for si in ET.fromstring(zf.read('xl/sharedStrings.xml')).findall(f'{NS}si'):
                shared.append(''.join(t.text or '' for t in si.iter(f'{NS}t')))
        date_styles = set()
        custom_fmt = {}
        if 'xl/styles.xml' in names:
            sroot = ET.fromstring(zf.read('xl/styles.xml'))
            numfmts = sroot.find(f'{NS}numFmts')
            if numfmts is not None:
                for fmt in numfmts.findall(f'{NS}numFmt'):
                    try:
                        custom_fmt[int(fmt.get('numFmtId'))] = fmt.get('formatCode') or ''
                    except ValueError:
                        pass
            cellxfs = sroot.find(f'{NS}cellXfs')
            if cellxfs is not None:
                for idx, xf in enumerate(cellxfs.findall(f'{NS}xf')):
                    try:
                        fid = int(xf.get('numFmtId') or 0)
                    except ValueError:
                        continue
                    code = custom_fmt.get(fid, '')
                    if fid in BUILTIN_DATE_FMT or (code and _is_date_code(code)):
                        date_styles.add(idx)
        rel_map = {}
        if 'xl/_rels/workbook.xml.rels' in names:
            for rel in ET.fromstring(zf.read('xl/_rels/workbook.xml.rels')):
                rel_map[rel.get('Id')] = rel.get('Target') or ''
        wb = ET.fromstring(zf.read('xl/workbook.xml'))
        sheets = []
        for sh in wb.iter(f'{NS}sheet'):
            rid = sh.get(f'{RELNS}id')
            target = rel_map.get(rid, '')
            target = target.lstrip('/')
            if not target.startswith('xl/'):
                target = 'xl/' + target
            sheets.append({'name': sh.get('name') or '', 'path': target})
        if not sheets:
            raise DataError(f'{path}: 工作簿中没有工作表')
        chosen = sheets[0]
        if sheet:
            for item in sheets:
                if item['name'] == sheet:
                    chosen = item
                    break
            else:
                raise DataError(f'{path}: 找不到工作表「{sheet}」，可用：{"、".join(s["name"] for s in sheets)}')
        if chosen['path'] not in names:
            raise DataError(f'{path}: 工作表数据缺失（{chosen["path"]}）')
        ws = ET.fromstring(zf.read(chosen['path']))
        merges = []
        merge_root = ws.find(f'{NS}mergeCells')
        if merge_root is not None:
            for mc in merge_root.findall(f'{NS}mergeCell'):
                merges.append(mc.get('ref') or '')
        grid = {}
        for row in ws.iter(f'{NS}row'):
            ridx = int(row.get('r') or 0)
            for cell in row.findall(f'{NS}c'):
                ref = cell.get('r') or ''
                col_letters = ''.join(ch for ch in ref if ch.isalpha())
                cidx = 0
                for ch in col_letters:
                    cidx = cidx * 26 + (ord(ch.upper()) - 64)
                val = _cell_value(cell, shared, date_styles)
                if val != '':
                    grid[(ridx, cidx)] = val
        for ref in merges:
            span = ref.split(':')
            if len(span) != 2:
                continue
            r1, c1 = _split_ref(span[0])
            r2, c2 = _split_ref(span[1])
            for r in range(r1, r2 + 1):
                for c in range(c1, c2 + 1):
                    if (r, c) != (r1, c1):
                        grid.pop((r, c), None)
        if merges:
            notes.append(f'{len(merges)} 处合并单元格：仅保留左上角取值')
    return _grid_to_rows(grid, notes, {'format': 'xlsx', 'sheet': chosen['name'], 'sheets': [s['name'] for s in sheets]})


def _split_ref(ref):
    letters = ''.join(ch for ch in ref if ch.isalpha())
    digits = ''.join(ch for ch in ref if ch.isdigit())
    cidx = 0
    for ch in letters:
        cidx = cidx * 26 + (ord(ch.upper()) - 64)
    return int(digits or 0), cidx


def _cell_value(cell, shared, date_styles):
    ctype = cell.get('t')
    v = cell.find(f'{NS}v')
    if ctype == 'inlineStr':
        node = cell.find(f'{NS}is')
        return ''.join(t.text or '' for t in node.iter(f'{NS}t')) if node is not None else ''
    if ctype == 's':
        if v is None or v.text is None:
            return ''
        try:
            return shared[int(v.text)]
        except (ValueError, IndexError):
            return v.text
    if ctype == 'e':
        return f'#ERROR:{v.text if v is not None else ""}'
    if ctype == 'b':
        return '是' if (v is not None and v.text != '0') else '否'
    if v is None or v.text is None:
        return ''
    raw = v.text
    try:
        style = cell.get('s')
        if style is not None and int(style) in date_styles:
            serial = float(raw)
            d = EXCEL_EPOCH + timedelta(days=int(serial))
            if date(1990, 1, 1) <= d <= date(2099, 12, 31):
                return d.isoformat()
        num = float(raw)
        return str(int(num)) if num == int(num) else f'{num:g}'
    except ValueError:
        return raw


def _grid_to_rows(grid, notes, meta):
    if not grid:
        raise DataError('工作表为空')
    max_row = max(k[0] for k in grid)
    max_col = max(k[1] for k in grid)
    header_row = None
    fallback_row = None
    for r in range(1, max_row + 1):
        filled = sum(1 for c in range(1, max_col + 1) if grid.get((r, c), '') != '')
        if filled >= 2:
            header_row = r
            break
        if filled == 1 and fallback_row is None:
            fallback_row = r
    if header_row is None:
        header_row = fallback_row  # 单列表：退回首条非空行
    if header_row is None:
        raise DataError('找不到表头行')
    columns = []
    for c in range(1, max_col + 1):
        name = grid.get((header_row, c), '')
        columns.append(name if name else f'列{c}')
    rows = []
    for r in range(header_row + 1, max_row + 1):
        if not any(grid.get((r, c), '') != '' for c in range(1, max_col + 1)):
            continue
        rows.append({columns[c - 1]: grid.get((r, c), '') for c in range(1, max_col + 1)})
    return {'columns': columns, 'rows': rows, 'meta': meta, 'notes': notes}


def read_table(path, sheet=None):
    p = Path(path)
    if not p.is_file():
        raise DataError(f'{path}: 文件不存在')
    suffix = p.suffix.lower()
    if suffix == '.csv':
        return read_csv(p)
    if suffix == '.xlsx':
        return read_xlsx(p, sheet)
    raise DataError(f'{path}: 仅支持 .csv / .xlsx，收到 {suffix or "无扩展名"}')


# ---------------------------------------------------------------- 数值与口径

def parse_number(value):
    """返回 (数值, 是否百分数)；无法解析返回 (None, False)。"""
    if value is None:
        return None, False
    s = str(value).strip().replace('，', ',').replace(',', '')
    if not s:
        return None, False
    percent = s.endswith('%')
    if percent:
        s = s[:-1].strip()
    try:
        num = float(s)
    except ValueError:
        return None, False
    if percent:
        num = num / 100.0
    if math.isnan(num) or math.isinf(num):
        return None, False
    return num, percent


STATUS_MAP = [
    (('出勤', '正常', '到课', '到勤', 'present', '√', '✓', '勤'), 'present'),
    (('缺勤', '旷课', '缺席', 'absent', 'abs', '缺'), 'absent'),
    (('迟到', 'late'), 'late'),
    (('请假', '病假', '事假', '公假', 'excused', 'leave'), 'excused'),
    (('早退', 'early'), 'early'),
]


def normalize_status(value):
    s = str(value or '').strip().lower()
    if not s:
        return ''
    for keys, label in STATUS_MAP:
        if s in keys:
            return label
    for keys, label in STATUS_MAP:
        for k in keys:
            if k in s:
                return label
    return 'other'


ALIASES = {
    'student': ('学号', '学生学号', 'studentno', 'studentid', 'id'),
    'studentName': ('姓名', '学生姓名', 'name'),
    'class': ('班级', '班级名称', '行政班', '班别', 'class'),
    'major': ('专业', '专业名称', 'major'),
    'course': ('课程', '课程名称', '科目', 'course'),
    'teacher': ('教师', '任课教师', '授课教师', '上课教师', '老师', 'teacher'),
    'date': ('日期', '考勤日期', '上课日期', '记录日期', '时间', 'date'),
    'session': ('节次', '课时', '第几节'),
    'status': ('考勤状态', '出勤状态', '考勤结果', '考勤情况', '状态', 'status'),
    'score': ('成绩', '分数', '总评成绩', '期末成绩', '期末成绩分数', '成绩分数', '评分', '得分', '评教分数', '评教得分', '总分', 'score'),
    'term': ('学期', '学年学期', 'term'),
    'count': ('评价人数', '参评人数', '参评学生数', '样本数'),
    'type': ('行为类型', '类型', '行为'),
    'detail': ('行为描述', '描述', '备注', '详情', '内容'),
    'planned': ('计划进度', '计划章节', '应授章节', '计划内容', '应到进度'),
    'actual': ('实际进度', '实际章节', '已授章节', '实际内容', '已讲', '已授'),
    'week': ('周次', '教学周'),
}


def resolve_column(columns, mapping, key, required=False):
    """按 mapping 显式指定 > 别名精确 > 别名包含，返回列名或 None。"""
    want = (mapping or {}).get(key)
    if want:
        for c in columns:
            if c == want:
                return c
        for c in columns:
            if c.strip() == want.strip():
                return c
        raise DataError(f'列映射指定的「{key} → {want}」在表中不存在')
    for alias in ALIASES.get(key, ()):  # 精确
        for c in columns:
            if c.strip().lower() == alias.lower():
                return c
    for alias in ALIASES.get(key, ()):  # 包含
        for c in columns:
            if alias.lower() in c.strip().lower():
                return c
    if required:
        raise DataError(f'未找到「{key}」列，请在 config.columns 中显式指定')
    return None


def load_config(path):
    cfg = json.loads(Path(path).read_text(encoding='utf-8'))
    cfg['_configDir'] = str(Path(path).resolve().parent)
    for role in ('attendance', 'grades'):
        entry = cfg.get('files', {}).get(role)
        if not entry:
            raise DataError(f'config.files 缺少必需的 {role} 数据')
    return cfg


def _resolve_path(cfg, target):
    """相对路径先按当前目录，再按 config 所在目录解析。"""
    p = Path(target)
    if p.is_absolute() or p.exists():
        return str(p)
    alt = Path(cfg.get('_configDir') or '.') / p
    return str(alt) if alt.exists() else str(p)


def open_role(cfg, role):
    entry = cfg.get('files', {}).get(role)
    if not entry:
        return None
    if isinstance(entry, dict):
        path = _resolve_path(cfg, entry['path'])
        table = read_table(path, entry.get('sheet'))
    else:
        path = _resolve_path(cfg, entry)
        table = read_table(path)
    mapping = (cfg.get('columns') or {}).get(role, {})
    return {'path': path, 'table': table, 'mapping': mapping, 'role': role}


def pick(row, table, mapping, key):
    col = resolve_column_cached(table, mapping, key)
    return row.get(col, '') if col else ''


_COL_CACHE = {}


def resolve_column_cached(table, mapping, key):
    cache_key = (id(table), key, json.dumps(mapping, ensure_ascii=False, sort_keys=True))
    if cache_key not in _COL_CACHE:
        _COL_CACHE[cache_key] = resolve_column(table['columns'], mapping, key)
    return _COL_CACHE[cache_key]


# ---------------------------------------------------------------- 统计工具

def mean(nums):
    return sum(nums) / len(nums) if nums else None


def median(nums):
    if not nums:
        return None
    s = sorted(nums)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


def quartiles(nums):
    if len(nums) < 4:
        return None
    s = sorted(nums)
    def q(p):
        idx = p * (len(s) - 1)
        lo = int(math.floor(idx))
        hi = min(lo + 1, len(s) - 1)
        return s[lo] + (s[hi] - s[lo]) * (idx - lo)
    return {'q1': round(q(0.25), 2), 'median': round(q(0.5), 2), 'q3': round(q(0.75), 2)}


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = mean(xs), mean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(d * d for d in dx) * sum(d * d for d in dy))
    if den == 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / den


def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def spearman(xs, ys):
    if len(xs) < 3:
        return None
    return pearson(ranks(xs), ranks(ys))


def round2(v):
    return round(v, 4) if isinstance(v, (int, float)) else v


# ---------------------------------------------------------------- inspect

def cmd_inspect(args):
    result = {'script': VERSION, 'files': []}
    for target in args.files:
        sheet = None
        path = target
        if '::' in target:
            path, sheet = target.split('::', 1)
        info = {'path': path}
        try:
            table = read_table(path, sheet)
        except DataError as exc:
            info['error'] = str(exc)
            result['files'].append(info)
            continue
        info.update(table['meta'])
        info['notes'] = list(table['notes'])
        rows = table['rows']
        info['rows'] = len(rows)
        seen = set()
        dup = 0
        for row in rows:
            sig = tuple(sorted((k, v) for k, v in row.items() if v != ''))
            if sig in seen:
                dup += 1
            seen.add(sig)
        if dup:
            info['duplicateRows'] = dup
            info['notes'].append(f'{dup} 行完全重复，统计前需去重并确认原因')
        cols = []
        for name in table['columns']:
            vals = [r.get(name, '') for r in rows]
            filled = [v for v in vals if v != '']
            numeric = [parse_number(v) for v in filled]
            num_ok = [n for n, _ in numeric if n is not None]
            percent = any(p for _, p in numeric)
            distinct = sorted(set(filled))
            col = {
                'name': name,
                'nonEmpty': len(filled),
                'emptyRate': round2(1 - len(filled) / len(rows)) if rows else None,
                'distinct': len(distinct),
            }
            if filled and len(num_ok) / len(filled) >= 0.8:
                col['numeric'] = True
                col['min'] = round2(min(num_ok))
                col['max'] = round2(max(num_ok))
                if percent:
                    col['percentLike'] = True
                    col['note'] = '列内含百分数，已按百分数解析'
            if filled and len(num_ok) < len(filled) / 5 and len(distinct) <= 8:
                col['samples'] = distinct[:8]
            dates = [v for v in filled if re.match(r'^\d{4}-\d{2}-\d{2}', v)]
            if dates and len(dates) / len(filled) >= 0.8:
                col['dateLike'] = True
                col['min'] = min(dates)
                col['max'] = max(dates)
            cols.append(col)
        info['columns'] = cols
        result['files'].append(info)
    emit(result, args.json)
    for info in result['files']:
        if 'error' in info:
            print(f"[异常] {info['path']}: {info['error']}")
            continue
        print(f"{info['path']} · {info['format']}" + (f"（工作表 {info['sheet']}）" if info.get('sheet') else '') + f" · {info['rows']} 行")
        for col in info['columns']:
            extra = []
            if col.get('numeric'):
                extra.append(f"数值 {col['min']}~{col['max']}")
            if col.get('dateLike'):
                extra.append(f"日期 {col['min']}~{col['max']}")
            if col.get('emptyRate'):
                extra.append(f"空值率 {col['emptyRate']:.0%}")
            print(f"  - {col['name']}" + (f"（{'; '.join(extra)}）" if extra else ''))
        for note in info.get('notes', []):
            print(f"  ! {note}")
    return 0


# ---------------------------------------------------------------- metrics

def cmd_metrics(args):
    cfg = load_config(args.config)
    quality = {'issues': [], 'warnings': []}
    period = cfg.get('period') or {}
    scope = cfg.get('scope') or {}
    caliber = {
        'attendanceDenominator': (cfg.get('caliber') or {}).get('attendanceDenominator', 'all-records'),
        'passScore': (cfg.get('caliber') or {}).get('passScore', 60),
        'scoreAggregate': 'student-course-mean',
    }
    out = {
        'script': VERSION,
        'cycleId': cfg.get('cycleId', ''),
        'period': period,
        'scope': scope,
        'caliber': caliber,
        'quality': quality,
    }

    att = open_role(cfg, 'attendance')
    grades = open_role(cfg, 'grades')
    evaluation = open_role(cfg, 'evaluation')
    progress = open_role(cfg, 'progress')
    behavior = open_role(cfg, 'behavior')

    scope_classes = [str(c) for c in scope.get('classes', []) if str(c)]

    att_stats = {'byClass': [], 'byTeacher': [], 'byMajor': []}
    att_students = {}
    status_unknown = 0
    if att:
        table, mapping = att['table'], att['mapping']
        col = {k: resolve_column(table['columns'], mapping, k) for k in
               ('student', 'studentName', 'class', 'major', 'course', 'teacher', 'date', 'status')}
        if not col['status']:
            raise DataError(f"{att['path']}: 未找到考勤状态列，请在 config.columns.attendance 指定")
        if not col['student'] and not col['studentName']:
            raise DataError(f"{att['path']}: 未找到学号/姓名列")
        buckets = {}
        date_values = []
        for row in table['rows']:
            sid = row.get(col['student'] or '') or row.get(col['studentName'] or '')
            status = normalize_status(row.get(col['status'] or ''))
            if status == 'other':
                status_unknown += 1
            cls = row.get(col['class'] or '') or '未分组'
            keys = {
                'byClass': cls,
                'byMajor': row.get(col['major'] or '') or scope.get('major') or '未分组',
                'byTeacher': row.get(col['teacher'] or '') or (row.get(col['course'] or '') or '未分组'),
            }
            d = row.get(col['date'] or '')
            if re.match(r'^\d{4}-\d{2}-\d{2}', d):
                date_values.append(d)
            if sid:
                att_students.setdefault(sid, set()).add(cls)
            for layer, key in keys.items():
                b = buckets.setdefault(layer, {}).setdefault(key, {'records': 0, 'present': 0, 'absent': 0, 'late': 0, 'excused': 0, 'early': 0, 'students': set()})
                if status and status != 'other':
                    b['records'] += 1
                if status in ('present', 'absent', 'late', 'excused', 'early'):
                    b[status] += 1
                if sid:
                    b['students'].add(sid)
        for layer, groups in buckets.items():
            denom_mode = caliber['attendanceDenominator']
            for key, b in sorted(groups.items()):
                denom = b['records']
                if denom_mode == 'excluding-excused':
                    denom = b['present'] + b['absent'] + b['late'] + b['early']
                rate = round2(b['present'] / denom) if denom else None
                att_stats[layer].append({
                    'group': key,
                    'records': b['records'],
                    'students': len(b['students']),
                    'present': b['present'], 'absent': b['absent'],
                    'late': b['late'], 'excused': b['excused'], 'early': b['early'],
                    'attendanceRate': rate,
                })
        if status_unknown:
            quality['warnings'].append(f'考勤状态有 {status_unknown} 条无法识别（未计入分母），请在数据中统一状态用词')
        if date_values:
            out['attendanceDateRange'] = {'min': min(date_values), 'max': max(date_values)}
            for bound, op in (('start', min), ('end', max)):
                limit = period.get(bound)
                if limit:
                    edge = op(date_values)
                    if (bound == 'start' and edge < limit) or (bound == 'end' and edge > limit):
                        quality['warnings'].append(f'考勤日期 {edge} 超出周期边界 {limit}，需确认是否纳入')
        if scope_classes:
            found = {g['group'] for g in att_stats['byClass']}
            outside = [g for g in found if g not in scope_classes and g != '未分组']
            if outside:
                quality['warnings'].append('考勤中出现范围外班级：' + '、'.join(sorted(outside)[:8]))
    out['attendance'] = att_stats

    grade_stats = {'byClass': [], 'byCourse': [], 'byTeacher': [], 'byMajor': []}
    grade_scores = {}
    grade_students = {}
    if grades:
        table, mapping = grades['table'], grades['mapping']
        col = {k: resolve_column(table['columns'], mapping, k) for k in
               ('student', 'studentName', 'class', 'major', 'course', 'teacher', 'score')}
        if not col['score']:
            raise DataError(f"{grades['path']}: 未找到成绩列，请在 config.columns.grades 指定")
        if not col['student'] and not col['studentName']:
            raise DataError(f"{grades['path']}: 未找到学号/姓名列")
        non_numeric = 0
        sc_by_student_course = {}
        buckets = {}
        for row in table['rows']:
            sid = row.get(col['student'] or '') or row.get(col['studentName'] or '')
            num, _ = parse_number(row.get(col['score'] or ''))
            course = row.get(col['course'] or '') or '未分课程'
            cls = row.get(col['class'] or '') or '未分组'
            if num is None:
                non_numeric += 1
                continue
            if sid:
                sc_by_student_course.setdefault(sid, {}).setdefault(course, []).append(num)
                grade_students.setdefault(sid, set()).add(cls)
            keys = {
                'byClass': cls,
                'byMajor': row.get(col['major'] or '') or scope.get('major') or '未分组',
                'byCourse': course,
                'byTeacher': row.get(col['teacher'] or '') or course,
            }
            for layer, key in keys.items():
                b = buckets.setdefault(layer, {}).setdefault(key, {'scores': [], 'students': set()})
                b['scores'].append(num)
                if sid:
                    b['students'].add(sid)
        if non_numeric:
            quality['warnings'].append(f'成绩列有 {non_numeric} 条非数值（缺考/等级制等），未纳入统计')
        pass_score = caliber['passScore']
        for layer, groups in buckets.items():
            for key, b in sorted(groups.items()):
                scores = b['scores']
                entry = {
                    'group': key,
                    'n': len(scores),
                    'students': len(b['students']),
                    'mean': round2(mean(scores)),
                    'min': round2(min(scores)),
                    'max': round2(max(scores)),
                    'passRate': round2(sum(1 for s in scores if s >= pass_score) / len(scores)) if scores else None,
                    'failCount': sum(1 for s in scores if s < pass_score),
                }
                entry.update(quartiles(scores) or {})
                grade_stats[layer].append(entry)
        for sid, courses in sc_by_student_course.items():
            grade_scores[sid] = round2(mean([mean(v) for v in courses.values()]))
    out['grades'] = grade_stats

    only_att = set(att_students) - set(grade_scores)
    only_gr = set(grade_scores) - set(att_students)
    if att and grades:
        if only_att:
            quality['warnings'].append(f'{len(only_att)} 名学生只在考勤中出现（成绩缺失或学号不一致）')
        if only_gr:
            quality['warnings'].append(f'{len(only_gr)} 名学生只在成绩中出现（考勤缺失或学号不一致）')

    if evaluation:
        table, mapping = evaluation['table'], evaluation['mapping']
        col = {k: resolve_column(table['columns'], mapping, k) for k in ('teacher', 'course', 'class', 'score', 'count')}
        if not col['score']:
            raise DataError(f"{evaluation['path']}: 未找到评教分数列")
        buckets = {}
        non_numeric = 0
        for row in table['rows']:
            num, _ = parse_number(row.get(col['score'] or ''))
            teacher = row.get(col['teacher'] or '') or '未署名'
            course = row.get(col['course'] or '') or ''
            if num is None:
                non_numeric += 1
                continue
            key = teacher
            b = buckets.setdefault(key, {'scores': [], 'courses': set(), 'classes': set()})
            b['scores'].append(num)
            if course:
                b['courses'].add(course)
            if col['class'] and row.get(col['class']):
                b['classes'].add(row.get(col['class']))
        if non_numeric:
            quality['warnings'].append(f'评教分数有 {non_numeric} 条非数值，未纳入统计')
        out['evaluation'] = {
            'byTeacher': [
                {
                    'group': key,
                    'n': len(b['scores']),
                    'students': None,
                    'mean': round2(mean(b['scores'])),
                    'min': round2(min(b['scores'])),
                    'max': round2(max(b['scores'])),
                    'courses': sorted(b['courses']),
                }
                for key, b in sorted(buckets.items())
            ]
        }
    else:
        out['evaluation'] = {'byTeacher': []}

    if progress:
        table, mapping = progress['table'], progress['mapping']
        col = {k: resolve_column(table['columns'], mapping, k) for k in ('course', 'teacher', 'class', 'planned', 'actual', 'week')}
        entries = []
        unparsed = 0
        for row in table['rows']:
            planned = row.get(col['planned'] or '') if col['planned'] else ''
            actual = row.get(col['actual'] or '') if col['actual'] else ''
            p_num = _chapter_number(planned)
            a_num = _chapter_number(actual)
            if p_num is None or a_num is None:
                unparsed += 1
                continue
            entries.append({
                'course': row.get(col['course'] or '') or '未分课程',
                'teacher': row.get(col['teacher'] or '') or '',
                'week': row.get(col['week'] or '') if col['week'] else '',
                'planned': planned,
                'actual': actual,
                'plannedChapter': p_num,
                'actualChapter': a_num,
                'deviationChapters': a_num - p_num,
            })
        if unparsed:
            quality['warnings'].append(f'教学进度有 {unparsed} 条无法解析出章节序号，仅描述不计算')
        out['progress'] = {'entries': entries}
    else:
        out['progress'] = {'entries': []}

    out['students'] = {
        'attendance': len(att_students),
        'grades': len(grade_scores),
        'both': len(set(att_students) & set(grade_scores)),
    }
    emit(out, args.json)
    print(f"指标计算完成：考勤覆盖 {out['students']['attendance']} 人 / 成绩覆盖 {out['students']['grades']} 人 / 双侧对齐 {out['students']['both']} 人")
    for layer in ('byClass', 'byTeacher', 'byMajor'):
        items = att_stats.get(layer, [])
        if items:
            print(f"出勤·{layer}: " + '；'.join(f"{g['group']} {g['attendanceRate']:.1%}(n={g['records']})" for g in items[:6] if g['attendanceRate'] is not None))
    for g in grade_stats['byClass'][:6]:
        print(f"成绩·{g['group']}: 均值 {g['mean']} / 及格率 {g['passRate']}(n={g['n']})")
    for w in quality['warnings']:
        print(f"! {w}")
    for i in quality['issues']:
        print(f"× {i}")
    return 0


def _chapter_number(text):
    m = re.search(r'第?\s*(\d+(?:\.\d+)?)\s*[章节讲单元课时]', str(text or ''))
    if m:
        return float(m.group(1))
    m = re.search(r'^\s*(\d+(?:\.\d+)?)\s*$', str(text or ''))
    if m:
        return float(m.group(1))
    return None


# ---------------------------------------------------------------- correlate

def cmd_correlate(args):
    cfg = load_config(args.config)
    min_n = int((cfg.get('rules') or {}).get('minCorrelationStudents', DEFAULT_MIN_CORR_N))
    min_teacher = int((cfg.get('rules') or {}).get('minTeacherSamples', DEFAULT_MIN_TEACHER_N))
    att = open_role(cfg, 'attendance')
    grades = open_role(cfg, 'grades')
    if not att or not grades:
        raise DataError('缺勤-成绩关联需要考勤与成绩两份数据')
    per_student_absence = {}
    table, mapping = att['table'], att['mapping']
    col = {k: resolve_column(table['columns'], mapping, k) for k in ('student', 'studentName', 'class', 'status')}
    class_of = {}
    for row in table['rows']:
        sid = row.get(col['student'] or '') or row.get(col['studentName'] or '')
        if not sid:
            continue
        st = normalize_status(row.get(col['status'] or ''))
        if not st or st == 'other':
            continue
        rec = per_student_absence.setdefault(sid, {'total': 0, 'absent': 0})
        rec['total'] += 1
        if st == 'absent':
            rec['absent'] += 1
        if col['class'] and row.get(col['class']):
            class_of[sid] = row.get(col['class'])
    gtable, gmapping = grades['table'], grades['mapping']
    gcol = {k: resolve_column(gtable['columns'], gmapping, k) for k in ('student', 'studentName', 'course', 'score')}
    sc_by_student = {}
    for row in gtable['rows']:
        sid = row.get(gcol['student'] or '') or row.get(gcol['studentName'] or '')
        num, _ = parse_number(row.get(gcol['score'] or ''))
        if not sid or num is None:
            continue
        course = row.get(gcol['course'] or '') or '全部课程'
        sc_by_student.setdefault(sid, {}).setdefault(course, []).append(num)
    pairs = []
    by_class = {}
    for sid, rec in per_student_absence.items():
        if sid not in sc_by_student or rec['total'] == 0:
            continue
        absence_rate = rec['absent'] / rec['total']
        score = mean([mean(v) for v in sc_by_student[sid].values()])
        item = (sid, absence_rate, score)
        pairs.append(item)
        cls = class_of.get(sid, '未分组')
        by_class.setdefault(cls, []).append(item)

    def corr_entry(scope, items):
        xs = [a for _, a, _ in items]
        ys = [s for _, _, s in items]
        n = len(items)
        r = pearson(xs, ys)
        rho = spearman(xs, ys)
        allowed = n >= min_n and r is not None
        return {
            'scope': scope,
            'n': n,
            'pearsonR': round2(r) if r is not None else None,
            'spearmanRho': round2(rho) if rho is not None else None,
            'absenceMetric': '缺勤率=缺勤记录/有效考勤记录（按学生汇总）',
            'scoreMetric': '各课程成绩均值（按学生汇总，课程间不加权）',
            'inferenceAllowed': allowed,
            'note': '' if allowed else f'样本量 {n} 低于阈值 {min_n}，只描述现状，不作归因推断',
        }

    results = {'script': VERSION, 'minCorrelationStudents': min_n, 'absenceGrade': [corr_entry('全体', pairs)]}
    for cls, items in sorted(by_class.items()):
        if len(items) >= 5:
            results['absenceGrade'].append(corr_entry(cls, items))
    if cfg.get('files', {}).get('evaluation'):
        ev = open_role(cfg, 'evaluation')
        etable, emapping = ev['table'], ev['mapping']
        ecol = {k: resolve_column(etable['columns'], emapping, k) for k in ('teacher', 'score')}
        ev_by_teacher = {}
        for row in etable['rows']:
            num, _ = parse_number(row.get(ecol['score'] or ''))
            if num is None:
                continue
            ev_by_teacher.setdefault(row.get(ecol['teacher'] or '') or '未署名', []).append(num)
        teacher_scores = {g['group']: g for g in json.loads(json.dumps(_teacher_grade_means(grades)))}
        xs, ys, names = [], [], []
        for teacher, scores in ev_by_teacher.items():
            ref = teacher_scores.get(teacher)
            if ref and ref['n'] >= 3:
                xs.append(mean(scores))
                ys.append(ref['mean'])
                names.append(teacher)
        r = pearson(xs, ys)
        results['evaluationOutcome'] = {
            'n': len(xs),
            'teachers': names,
            'pearsonR': round2(r) if r is not None else None,
            'evaluationMetric': '教师评教均分',
            'outcomeMetric': '教师所授课程成绩均值',
            'inferenceAllowed': len(xs) >= min_teacher and r is not None,
            'note': '' if len(xs) >= min_teacher else f'教师样本 {len(xs)} 少于 {min_teacher}，只描述，不作推断',
        }
    emit(results, args.json)
    for entry in results['absenceGrade']:
        tag = '可推断' if entry['inferenceAllowed'] else '仅描述'
        r = entry['pearsonR']
        print(f"缺勤-成绩 {entry['scope']}: n={entry['n']}" + (f" r={r}" if r is not None else '') + f" [{tag}]")
    if 'evaluationOutcome' in results:
        e = results['evaluationOutcome']
        print(f"评教-成绩(教师层): n={e['n']}" + (f" r={e['pearsonR']}" if e['pearsonR'] is not None else '') + (' [可推断]' if e['inferenceAllowed'] else ' [仅描述]'))
    return 0


def _teacher_grade_means(grades):
    table, mapping = grades['table'], grades['mapping']
    col = {k: resolve_column(table['columns'], mapping, k) for k in ('teacher', 'course', 'score')}
    buckets = {}
    for row in table['rows']:
        num, _ = parse_number(row.get(col['score'] or ''))
        if num is None:
            continue
        key = row.get(col['teacher'] or '') or row.get(col['course'] or '') or '未分组'
        buckets.setdefault(key, []).append(num)
    return [{'group': k, 'n': len(v), 'mean': round2(mean(v))} for k, v in sorted(buckets.items())]


# ---------------------------------------------------------------- risk

def cmd_risk(args):
    cfg = load_config(args.config)
    thresholds = dict(DEFAULT_RISK)
    if args.thresholds:
        thresholds.update(json.loads(Path(args.thresholds).read_text(encoding='utf-8')))
    thresholds.update((cfg.get('thresholds') or {}))
    att = open_role(cfg, 'attendance')
    grades = open_role(cfg, 'grades')
    names = {}
    table, mapping = att['table'], att['mapping']
    col = {k: resolve_column(table['columns'], mapping, k) for k in ('student', 'studentName', 'class', 'status')}
    per_student = {}
    for row in table['rows']:
        sid = row.get(col['student'] or '') or row.get(col['studentName'] or '')
        if not sid:
            continue
        if col['studentName'] and row.get(col['studentName']):
            names[sid] = row.get(col['studentName'])
        st = normalize_status(row.get(col['status'] or ''))
        if not st or st == 'other':
            continue
        rec = per_student.setdefault(sid, {'total': 0, 'absent': 0, 'class': ''})
        rec['total'] += 1
        if st == 'absent':
            rec['absent'] += 1
        if col['class'] and row.get(col['class']):
            rec['class'] = row.get(col['class'])
    gtable, gmapping = grades['table'], grades['mapping']
    gcol = {k: resolve_column(gtable['columns'], gmapping, k) for k in ('student', 'studentName', 'course', 'score')}
    course_scores = {}
    gnames = {}
    for row in gtable['rows']:
        sid = row.get(gcol['student'] or '') or row.get(gcol['studentName'] or '')
        if not sid:
            continue
        if gcol['studentName'] and row.get(gcol['studentName']):
            gnames[sid] = row.get(gcol['studentName'])
        num, _ = parse_number(row.get(gcol['score'] or ''))
        if num is None:
            continue
        course = row.get(gcol['course'] or '') or '未分课程'
        course_scores.setdefault(sid, {}).setdefault(course, []).append(num)
    names.update(gnames)
    attendance_risk, academic_risk = [], []
    for sid, rec in per_student.items():
        rate = rec['absent'] / rec['total'] if rec['total'] else 0
        if rate >= thresholds['absenceRate'] or rec['absent'] >= thresholds['absenceCount']:
            attendance_risk.append({
                'studentId': sid, 'name': names.get(sid, ''), 'class': rec['class'],
                'absenceRate': round2(rate), 'absenceCount': rec['absent'], 'records': rec['total'],
            })
    pass_score = (cfg.get('caliber') or {}).get('passScore', 60)
    for sid, courses in course_scores.items():
        means = {c: mean(v) for c, v in courses.items()}
        avg = mean(list(means.values()))
        fails = [c for c, m in means.items() if m < pass_score]
        if (avg is not None and avg < thresholds['meanScore']) or len(fails) >= thresholds['failCourses']:
            cls = per_student.get(sid, {}).get('class', '')
            academic_risk.append({
                'studentId': sid, 'name': names.get(sid, ''), 'class': cls,
                'meanScore': round2(avg), 'failCourses': sorted(fails),
            })
    attendance_risk.sort(key=lambda x: -x['absenceRate'])
    academic_risk.sort(key=lambda x: (x['meanScore'] if x['meanScore'] is not None else 999))
    result = {
        'script': VERSION,
        'thresholds': thresholds,
        'authorizedChannelOnly': True,
        'attendanceRisk': attendance_risk,
        'academicRisk': academic_risk,
    }
    emit(result, args.json)
    if args.csv:
        _write_risk_csv(args.csv, result)
    print(f"风险名单：出勤风险 {len(attendance_risk)} 人；学业风险 {len(academic_risk)} 人（阈值：缺勤率≥{thresholds['absenceRate']} 或缺勤≥{thresholds['absenceCount']} 次；均分<{thresholds['meanScore']} 或不及格≥{thresholds['failCourses']} 门）")
    print('名单含个体信息，只能作为独立文件交付给授权角色，不得进入报告网页正文。')
    return 0


def _write_risk_csv(path, result):
    with open(path, 'w', encoding='utf-8-sig', newline='') as fh:
        writer = csv.writer(fh)
        writer.writerow(['类别', '学号', '姓名', '班级', '指标'])
        for item in result['attendanceRisk']:
            writer.writerow(['出勤风险', item['studentId'], item['name'], item['class'],
                             f"缺勤率 {item['absenceRate']:.1%}（{item['absenceCount']}/{item['records']}）"])
        for item in result['academicRisk']:
            writer.writerow(['学业风险', item['studentId'], item['name'], item['class'],
                             f"均分 {item['meanScore']}；不及格 {len(item['failCourses'])} 门（{'、'.join(item['failCourses'][:5])}）"])


# ---------------------------------------------------------------- compare

def cmd_compare(args):
    current = json.loads(Path(args.current).read_text(encoding='utf-8'))
    previous = json.loads(Path(args.previous).read_text(encoding='utf-8'))
    controls = [c.strip() for c in (args.control or '').split(',') if c.strip()]
    cal_cur, cal_prev = current.get('caliber', {}), previous.get('caliber', {})
    out = {
        'script': VERSION,
        'currentCycle': current.get('cycleId') or (current.get('period') or {}).get('label', ''),
        'previousCycle': previous.get('cycleId') or (previous.get('period') or {}).get('label', ''),
    }
    if cal_cur != cal_prev:
        out['status'] = 'caliber_mismatch'
        out['reason'] = f'两周期口径不一致（current={cal_cur} / previous={cal_prev}），按口径纪律拒绝并列比较'
        emit(out, args.json)
        print(out['reason'])
        return 0
    out['status'] = 'ok'
    out['caliber'] = cal_cur
    comparable, not_comparable = [], []
    layer_metrics = [
        ('attendance', 'byClass', 'attendanceRate', 'records'),
        ('attendance', 'byMajor', 'attendanceRate', 'records'),
        ('grades', 'byClass', 'mean', 'n'),
        ('grades', 'byClass', 'passRate', 'n'),
        ('grades', 'byMajor', 'mean', 'n'),
        ('grades', 'byCourse', 'mean', 'n'),
        ('evaluation', 'byTeacher', 'mean', 'n'),
    ]
    for section, layer, metric, nkey in layer_metrics:
        cur_groups = {g['group']: g for g in current.get(section, {}).get(layer, [])}
        prev_groups = {g['group']: g for g in previous.get(section, {}).get(layer, [])}
        for key in sorted(set(cur_groups) | set(prev_groups)):
            cur, prev = cur_groups.get(key), prev_groups.get(key)
            label = f'{section}.{layer}.{metric}'
            if cur is None:
                not_comparable.append({'metric': label, 'group': key, 'reason': '仅上一周期存在'})
                continue
            if prev is None:
                not_comparable.append({'metric': label, 'group': key, 'reason': '仅本周期存在'})
                continue
            cv, pv = cur.get(metric), prev.get(metric)
            if cv is None or pv is None:
                not_comparable.append({'metric': label, 'group': key, 'reason': '任一侧数值缺失'})
                continue
            comparable.append({
                'metric': label,
                'group': key,
                'control': key in controls,
                'previous': {'value': pv, 'n': prev.get(nkey)},
                'current': {'value': cv, 'n': cur.get(nkey)},
                'delta': round2(cv - pv),
            })
    if controls:
        for metric in ('attendance.byClass.attendanceRate', 'grades.byClass.mean'):
            ctl = [c for c in comparable if c['metric'] == metric and c['control']]
            itv = [c for c in comparable if c['metric'] == metric and not c['control']]
            if ctl and itv:
                out.setdefault('controlComparison', []).append({
                    'metric': metric,
                    'controlMeanDelta': round2(mean([c['delta'] for c in ctl])),
                    'interventionMeanDelta': round2(mean([c['delta'] for c in itv])),
                    'controlGroups': [c['group'] for c in ctl],
                    'note': '对照组为未纳入干预的班级，差异不等于干预效果，须结合措施内容判断',
                })
    out['comparable'] = comparable
    out['notComparable'] = not_comparable
    emit(out, args.json)
    print(f"同口径对比：{len(comparable)} 项可并列，{len(not_comparable)} 项不可比")
    for c in comparable[:10]:
        print(f"  {c['metric']} · {c['group']}: {c['previous']['value']} → {c['current']['value']}（Δ{c['delta']}，n {c['previous']['n']}→{c['current']['n']}）")
    for nc in not_comparable[:8]:
        print(f"  × {nc['metric']} · {nc['group']}: {nc['reason']}")
    return 0


# ---------------------------------------------------------------- 入口

def emit(payload, out_path):
    payload.setdefault('generatedAt', datetime.now().isoformat(timespec='seconds'))
    if out_path:
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_parser():
    parser = argparse.ArgumentParser(description='学勤与教学诊断数据检查与指标计算')
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('inspect', help='逐文件质量检查')
    p.add_argument('files', nargs='+', help='数据文件路径，xlsx 可用 路径::工作表名 指定')
    p.add_argument('--json', help='结果另存 JSON 的路径')

    p = sub.add_parser('metrics', help='三层指标计算')
    p.add_argument('--config', required=True, help='analysis/config.json')
    p.add_argument('--json')

    p = sub.add_parser('correlate', help='缺勤-成绩 / 评教-结果关联')
    p.add_argument('--config', required=True)
    p.add_argument('--json')

    p = sub.add_parser('risk', help='生成风险名单（须先取得用户授权）')
    p.add_argument('--config', required=True)
    p.add_argument('--thresholds', help='阈值 JSON 文件')
    p.add_argument('--json')
    p.add_argument('--csv', help='名单 CSV 输出路径（utf-8-sig，Excel 可直接打开）')

    p = sub.add_parser('compare', help='与上一周期同口径对比')
    p.add_argument('--current', required=True)
    p.add_argument('--previous', required=True)
    p.add_argument('--control', help='对照班级，逗号分隔')
    p.add_argument('--json')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    handlers = {
        'inspect': cmd_inspect,
        'metrics': cmd_metrics,
        'correlate': cmd_correlate,
        'risk': cmd_risk,
        'compare': cmd_compare,
    }
    try:
        return handlers[args.command](args)
    except DataError as exc:
        print(f'× {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
