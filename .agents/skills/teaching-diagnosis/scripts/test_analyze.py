#!/usr/bin/env python3
"""analyze.py 单元测试：python3 -m unittest test_analyze -v（在本目录执行）。"""
import contextlib
import io
import json
import csv
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze  # noqa: E402

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


def run_cli(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = analyze.main(argv)
    return code, buf.getvalue()


def write_csv(path, rows, encoding='utf-8'):
    with open(path, 'w', encoding=encoding, newline='') as fh:
        writer = csv.writer(fh)
        writer.writerows(rows)


def build_xlsx(path, sheets, date_serial=None):
    """构造最小 xlsx：sheets = {名: [[单元格,...],...]}，单元格为纯文本。"""
    sheet_files = {}
    sheet_xml = []
    sheet_names = sorted(sheets)
    for idx, name in enumerate(sheet_names, start=1):
        rows = sheets[name]
        body = []
        for r, row in enumerate(rows, start=1):
            cells = []
            for c, val in enumerate(row, start=1):
                ref = f'{chr(64 + c)}{r}'
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{val}</t></is></c>')
            body.append(f'<row r="{r}">' + ''.join(cells) + '</row>')
        sheet_files[f'xl/worksheets/sheet{idx}.xml'] = (
            f'<?xml version="1.0"?><worksheet xmlns="{NS}"><sheetData>{"".join(body)}</sheetData></worksheet>'
        )
        sheet_xml.append((name, idx))
    workbook_sheets = ''.join(
        f'<sheet name="{name}" sheetId="{idx}" r:id="rId{idx}"/>' for name, idx in sheet_xml
    )
    rels = ''.join(
        f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>'
        for _, idx in sheet_xml
    )
    files = {
        '[Content_Types].xml': '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>',
        '_rels/.rels': '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': f'<?xml version="1.0"?><workbook xmlns="{NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{workbook_sheets}</sheets></workbook>',
        'xl/_rels/workbook.xml.rels': f'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>',
    }
    files.update(sheet_files)
    if date_serial is not None:
        # 附带一个含日期样式（numFmtId=14）单元格的第二工作表，验证序列号→日期
        files['xl/styles.xml'] = (
            '<?xml version="1.0"?><styleSheet xmlns="' + NS + '">'
            '<numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy-m-d"/></numFmts>'
            '<cellXfs count="2"><xf numFmtId="0"/><xf numFmtId="14"/></cellXfs></styleSheet>'
        )
        files['xl/worksheets/sheet10.xml'] = (
            f'<?xml version="1.0"?><worksheet xmlns="{NS}"><sheetData>'
            f'<row r="1"><c r="A1" t="inlineStr"><is><t>日期</t></is></c><c r="B1" t="inlineStr"><is><t>值</t></is></c></row>'
            f'<row r="2"><c r="A2" s="1"><v>{date_serial}</v></c><c r="B2"><v>88</v></c></row>'
            '</sheetData></worksheet>'
        )
    with zipfile.ZipFile(path, 'w') as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return path


class TestReadTable(unittest.TestCase):
    def test_csv_utf8_sig_and_gb18030(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp) / 'a.csv'
            write_csv(p1, [['学号', '姓名'], ['001', '张三']], encoding='utf-8-sig')
            t1 = analyze.read_table(p1)
            self.assertEqual(t1['meta']['encoding'], 'utf-8-sig')
            self.assertEqual(t1['rows'][0]['姓名'], '张三')
            p2 = Path(tmp) / 'b.csv'
            write_csv(p2, [['学号', '姓名'], ['002', '李四']], encoding='gb18030')
            t2 = analyze.read_table(p2)
            self.assertEqual(t2['meta']['encoding'], 'gb18030')
            self.assertEqual(t2['rows'][0]['姓名'], '李四')

    def test_csv_delimiter_tab(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 't.csv'
            p.write_text('学号\t班级\n001\t大数据2401\n', encoding='utf-8')
            t = analyze.read_table(p)
            self.assertEqual(t['rows'][0]['班级'], '大数据2401')

    def test_xlsx_inline_and_sheet_pick(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = build_xlsx(Path(tmp) / 'g.xlsx', {
                '成绩': [['学号', '课程', '成绩'], ['001', '数据库', '88']],
                '备用': [['x'], ['y']],
            })
            t = analyze.read_table(p, sheet='成绩')
            self.assertEqual(t['meta']['sheet'], '成绩')
            self.assertEqual(t['rows'][0]['成绩'], '88')
            with self.assertRaises(analyze.DataError):
                analyze.read_table(p, sheet='不存在')

    def test_xlsx_date_serial(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = build_xlsx(Path(tmp) / 'd.xlsx', {'s': [['a'], ['b']]}, date_serial=45901)  # 2025-09-01
            t = analyze.read_table(p, sheet='s')  # 主表正常
            self.assertEqual(t['rows'][0]['a'], 'b')
            # 直接读日期表（第二个 build 中 sheet10 不在 workbook 登记，走底层函数验证）
            with zipfile.ZipFile(p) as zf:
                ws = analyze.ET.fromstring(zf.read('xl/worksheets/sheet10.xml'))
                cell = None
                for row in ws.iter(f'{analyze.NS}row'):
                    for c in row.findall(f'{analyze.NS}c'):
                        if c.get('r') == 'A2':
                            cell = c
                shared = []
                val = analyze._cell_value(cell, shared, {1})
            self.assertEqual(val, '2025-09-01')


class TestStats(unittest.TestCase):
    def test_pearson_perfect(self):
        xs = [1, 2, 3, 4, 5]
        self.assertAlmostEqual(analyze.pearson(xs, [2 * x + 1 for x in xs]), 1.0)
        self.assertAlmostEqual(analyze.pearson(xs, [-x for x in xs]), -1.0)

    def test_spearman_monotonic_with_ties(self):
        self.assertAlmostEqual(analyze.spearman([1, 2, 3, 4], [1, 2, 3, 4]), 1.0)
        # 平均秩下严格单调但含并列时接近 1
        self.assertGreater(analyze.spearman([1, 2, 3, 4], [10, 10, 20, 30]), 0.94)

    def test_normalize_status(self):
        self.assertEqual(analyze.normalize_status('出勤'), 'present')
        self.assertEqual(analyze.normalize_status('旷课'), 'absent')
        self.assertEqual(analyze.normalize_status('迟到'), 'late')
        self.assertEqual(analyze.normalize_status('病假'), 'excused')
        self.assertEqual(analyze.normalize_status('xx'), 'other')


def make_workspace(tmp):
    """两个班级 12 名学生：缺勤越多成绩越低（r 为负），另含评教与进度表。"""
    root = Path(tmp)
    att_rows = [['学号', '姓名', '班级', '课程', '教师', '日期', '考勤状态']]
    grade_rows = [['学号', '班级', '课程', '成绩']]
    students = [
        # (学号, 班级, 缺勤次数, 成绩)
        ('001', '大数据2401', 0, 92), ('002', '大数据2401', 1, 85), ('003', '大数据2401', 2, 78),
        ('004', '大数据2401', 3, 70), ('005', '大数据2401', 4, 64), ('006', '大数据2401', 5, 55),
        ('007', '大数据2402', 0, 90), ('008', '大数据2402', 0, 86), ('009', '大数据2402', 1, 80),
        ('010', '大数据2402', 1, 74), ('011', '大数据2402', 2, 66), ('012', '大数据2402', 2, 60),
    ]
    for sid, cls, absent, score in students:
        for k in range(10):
            status = '缺勤' if k < absent else '出勤'
            att_rows.append([sid, f'生{sid}', cls, '数据库', '王老师', f'2025-09-{k + 2:02d}', status])
        grade_rows.append([sid, cls, '数据库', str(score)])
    write_csv(root / 'attendance.csv', att_rows)
    write_csv(root / 'grades.csv', grade_rows)
    write_csv(root / 'eval.csv', [['教师', '课程', '评分'], ['王老师', '数据库', '4.2']])
    write_csv(root / 'progress.csv', [['课程', '计划进度', '实际进度'], ['数据库', '第10章', '第8章']])
    config = {
        'cycleId': '2026S1',
        'period': {'label': '2025-2026学年第一学期', 'start': '2025-09-01', 'end': '2026-01-15'},
        'scope': {'classes': ['大数据2401', '大数据2402'], 'major': '大数据技术'},
        'files': {
            'attendance': 'attendance.csv',
            'grades': 'grades.csv',
            'evaluation': 'eval.csv',
            'progress': 'progress.csv',
        },
    }
    (root / 'config.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
    return root


class TestPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = make_workspace(cls.tmp.name)
        cls.cfg = str(cls.root / 'config.json')
        code, _ = run_cli(['metrics', '--config', cls.cfg, '--json', str(cls.root / 'metrics.json')])
        cls.metrics_code = code
        cls.metrics = json.loads((cls.root / 'metrics.json').read_text(encoding='utf-8'))
        code, _ = run_cli(['correlate', '--config', cls.cfg, '--json', str(cls.root / 'corr.json')])
        cls.corr = json.loads((cls.root / 'corr.json').read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_metrics_attendance(self):
        by_class = {g['group']: g for g in self.metrics['attendance']['byClass']}
        self.assertEqual(set(by_class), {'大数据2401', '大数据2402'})
        entry = by_class['大数据2401']
        # 每人 10 条记录 × 6 人 = 60；缺勤合计 0+1+2+3+4+5=15
        self.assertEqual(entry['records'], 60)
        self.assertEqual(entry['students'], 6)
        self.assertAlmostEqual(entry['attendanceRate'], 45 / 60)

    def test_metrics_grades(self):
        by_class = {g['group']: g for g in self.metrics['grades']['byClass']}
        entry = by_class['大数据2401']
        self.assertEqual(entry['n'], 6)
        self.assertAlmostEqual(entry['mean'], sum([92, 85, 78, 70, 64, 55]) / 6)
        self.assertAlmostEqual(entry['passRate'], 5 / 6, places=3)
        self.assertEqual(entry['failCount'], 1)

    def test_metrics_progress_deviation(self):
        entries = self.metrics['progress']['entries']
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['deviationChapters'], -2)

    def test_correlate_negative_and_small_sample(self):
        overall = self.corr['absenceGrade'][0]
        self.assertEqual(overall['n'], 12)
        self.assertLess(overall['pearsonR'], -0.8)
        self.assertFalse(overall['inferenceAllowed'])  # 12 < 30：不得推断
        self.assertIn('样本量', overall['note'])

    def test_risk_and_csv(self):
        code, _ = run_cli(['risk', '--config', self.cfg,
                           '--json', str(self.root / 'risk.json'),
                           '--csv', str(self.root / 'risk.csv'),
                           '--thresholds', str(self._thresholds())])
        self.assertEqual(code, 0)
        risk = json.loads((self.root / 'risk.json').read_text(encoding='utf-8'))
        ids = {item['studentId'] for item in risk['attendanceRisk']}
        self.assertEqual(ids, {'004', '005', '006'})  # 缺勤率 ≥30% 或缺勤 ≥3 次
        acd = {item['studentId'] for item in risk['academicRisk']}
        self.assertIn('006', acd)  # 均分 55 < 60
        text = (self.root / 'risk.csv').read_text(encoding='utf-8-sig')
        self.assertIn('出勤风险', text)
        self.assertIn('006', text)

    def _thresholds(self):
        p = self.root / 'thr.json'
        p.write_text(json.dumps({'absenceRate': 0.3, 'absenceCount': 3, 'meanScore': 60, 'failCourses': 2}), encoding='utf-8')
        return str(p)

    def test_compare_ok_and_control(self):
        prev = json.loads(json.dumps(self.metrics))
        prev['cycleId'] = '2025S2'
        prev['attendance']['byClass'][0]['attendanceRate'] = 0.5
        prev['grades']['byClass'][0]['mean'] = 60.0
        (self.root / 'prev.json').write_text(json.dumps(prev, ensure_ascii=False), encoding='utf-8')
        code, _ = run_cli(['compare', '--current', str(self.root / 'metrics.json'),
                           '--previous', str(self.root / 'prev.json'),
                           '--control', '大数据2402', '--json', str(self.root / 'cmp.json')])
        cmp = json.loads((self.root / 'cmp.json').read_text(encoding='utf-8'))
        self.assertEqual(cmp['status'], 'ok')
        att = next(c for c in cmp['comparable'] if c['metric'] == 'attendance.byClass.attendanceRate' and c['group'] == '大数据2401')
        self.assertAlmostEqual(att['delta'], 45 / 60 - 0.5)
        self.assertFalse(att['control'])
        self.assertIn('controlComparison', cmp)

    def test_compare_caliber_mismatch(self):
        prev = json.loads(json.dumps(self.metrics))
        prev['caliber']['passScore'] = 90
        (self.root / 'prev2.json').write_text(json.dumps(prev, ensure_ascii=False), encoding='utf-8')
        code, out = run_cli(['compare', '--current', str(self.root / 'metrics.json'),
                             '--previous', str(self.root / 'prev2.json'), '--json', str(self.root / 'cmp2.json')])
        cmp = json.loads((self.root / 'cmp2.json').read_text(encoding='utf-8'))
        self.assertEqual(cmp['status'], 'caliber_mismatch')
        self.assertNotIn('comparable', cmp)

    def test_inspect_flags_duplicates(self):
        p = self.root / 'dup.csv'
        write_csv(p, [['学号', '状态'], ['001', '出勤'], ['001', '出勤']])
        code, _ = run_cli(['inspect', str(p), '--json', str(self.root / 'inspect.json')])
        data = json.loads((self.root / 'inspect.json').read_text(encoding='utf-8'))
        self.assertEqual(data['files'][0]['duplicateRows'], 1)

    def test_metrics_requires_core_files(self):
        bad = {'files': {'attendance': 'attendance.csv'}}
        p = self.root / 'bad.json'
        p.write_text(json.dumps(bad), encoding='utf-8')
        code, out = run_cli(['metrics', '--config', str(p)])
        self.assertEqual(code, 2)


if __name__ == '__main__':
    unittest.main()
