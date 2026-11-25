#!/usr/bin/env python3
"""assign.py / read_roster.py 回归测试（纯标准库 unittest）。

运行：python3 <技能目录>/scripts/test_assign.py
"""

import json
import random
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ASSIGN = SCRIPTS / "assign.py"
READER = SCRIPTS / "read_roster.py"


def run(args, cwd=None, expect_ok=True):
    argv = [sys.executable] + [str(a) for a in args]
    proc = subprocess.run(argv, capture_output=True, text=True, cwd=cwd)
    if expect_ok and proc.returncode != 0:
        raise AssertionError(f"命令失败：{args}\nstdout: {proc.stdout}\nstderr: {proc.stderr}")
    return proc


def synth_students(n=120, seed=7, with_prefs=True, with_assessment=True):
    rng = random.Random(seed)
    regions = ["粤东", "粤西", "珠三角", "外省"]
    directions = ["智能制造", "新能源汽车", "数字商贸"]
    students = []
    for i in range(n):
        s = {"id": f"S{i + 1:03d}", "name": f"学生{i + 1:03d}",
             "gender": rng.choice(["男", "男", "女"]),
             "region": rng.choice(regions),
             "score": round(rng.gauss(420, 60), 1)}
        if with_assessment:
            base = rng.gauss(0, 1)
            s["assessment"] = {"logic": round(60 + base * 12 + rng.gauss(0, 4), 1),
                               "hands_on": round(62 + base * 10 + rng.gauss(0, 5), 1)}
        if with_prefs:
            prefs = directions[:]
            rng.shuffle(prefs)
            if rng.random() < 0.15:
                prefs = prefs[: rng.choice([1, 2])]
            s["preference"] = prefs
        students.append(s)
    return students


def write_inputs(dir_path, params, students, name_params="params.json", name_students="students.json"):
    (dir_path / name_params).write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")
    (dir_path / name_students).write_text(json.dumps({"students": students}, ensure_ascii=False), encoding="utf-8")
    return dir_path / name_params, dir_path / name_students


def load_result(out_dir):
    return json.loads((out_dir / "result.json").read_text(encoding="utf-8"))


def strip_volatile(result):
    clone = json.loads(json.dumps(result))
    clone["meta"].pop("generatedAt", None)
    return clone


class BalancedModeTests(unittest.TestCase):
    def test_balance_quality_and_determinism(self):
        students = synth_students(160, seed=11)
        params = {"taskTitle": "回归-均衡", "mode": "balanced", "classCount": 4, "capacityPerClass": 45,
                  "seed": 20261118, "dimensions": [{"field": "score", "weight": 0.7}, {"field": "gender", "weight": 0.3}]}
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            pf, sf = write_inputs(work, params, students)
            run([ASSIGN, pf, sf, "--out", work / "o1", "--state", work / "state.json"])
            run([ASSIGN, pf, sf, "--out", work / "o2", "--state", work / "state2.json"])  # 不同状态文件复现
            r1, r2 = load_result(work / "o1"), load_result(work / "o2")
            self.assertEqual(strip_volatile(r1), strip_volatile(r2))
            self.assertEqual(len(r1["assignment"]), 160)
            counts = [c["count"] for c in r1["classes"]]
            self.assertEqual(sum(counts), 160)
            self.assertTrue(all(c <= 45 for c in counts))
            target = 160 / 4
            self.assertTrue(all(abs(c - target) <= 1.0 for c in counts), counts)
            score_dim = next(d for d in r1["balance"]["dimensions"] if d["field"] == "score")
            self.assertLess(score_dim["meanDiff"], 3.0)  # 全局 std≈60，均值差应远小于一个标准差
            gender_dim = next(d for d in r1["balance"]["dimensions"] if d["field"] == "gender")
            self.assertLess(max(gender_dim["maxShareGap"].values()), 0.08)
            # 班内异质：班内 std 不应显著低于全局 std（未出现能力沉淀）
            het = r1["balance"]["heterogeneity"]
            self.assertGreater(het["withinClassStdAvg"], het["globalStd"] * 0.85)

    def test_seed_changes_result(self):
        students = synth_students(100, seed=12)
        results = []
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            for i, seed in enumerate([101, 202]):
                params = {"mode": "balanced", "classCount": 3, "capacityPerClass": 40, "seed": seed}
                pf, sf = write_inputs(work, params, students, f"p{i}.json", f"s{i}.json")
                run([ASSIGN, pf, sf, "--out", work / f"o{i}", "--state", work / f"st{i}.json"])
                results.append({a["studentId"]: a["classId"] for a in load_result(work / f"o{i}")["assignment"]})
        self.assertNotEqual(results[0], results[1])

    def test_constraints(self):
        students = synth_students(90, seed=13)
        students[3]["id"], students[4]["id"] = "TWIN1", "TWIN2"
        students[10]["id"], students[11]["id"] = "AVOID1", "AVOID2"
        params = {"mode": "balanced", "classCount": 3, "capacityPerClass": 35, "seed": 7,
                  "constraints": [
                      {"type": "same-class", "students": ["TWIN1", "TWIN2"], "reason": "双胞胎同班"},
                      {"type": "different-class", "students": ["AVOID1", "AVOID2"], "reason": "需回避"},
                  ]}
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            pf, sf = write_inputs(work, params, students)
            run([ASSIGN, pf, sf, "--out", work / "out", "--state", work / "state.json"])
            result = load_result(work / "out")
            placement = {a["studentId"]: a["classId"] for a in result["assignment"]}
            self.assertEqual(placement["TWIN1"], placement["TWIN2"])
            self.assertNotEqual(placement["AVOID1"], placement["AVOID2"])
            for c in result["constraints"]:
                self.assertTrue(c["satisfied"], c)

    def test_reroll_chain(self):
        students = synth_students(60, seed=14)
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            state = work / "state.json"
            base = {"mode": "balanced", "classCount": 2, "capacityPerClass": 35, "seed": 42}
            p1, sf = write_inputs(work, base, students, "p1.json", "s.json")
            run([ASSIGN, p1, sf, "--out", work / "a1", "--state", state])
            # attempt=2 未先做 attempt=1（新状态文件）→ 拒绝
            p2, _ = write_inputs(work, {**base, "attempt": 2}, students, "p2.json", "s2.json")
            proc = run([ASSIGN, p2, sf, "--out", work / "bad", "--state", work / "empty-state.json"], expect_ok=False)
            self.assertEqual(proc.returncode, 2)
            # 重复 attempt=1 → 拒绝（防重复首解）
            proc = run([ASSIGN, p1, sf, "--out", work / "dup", "--state", state], expect_ok=False)
            self.assertEqual(proc.returncode, 2)
            # 正常重掷一次 → 允许，且结果不同于首解（极大概率）
            run([ASSIGN, p2, sf, "--out", work / "a2", "--state", state])
            r1 = {a["studentId"]: a["classId"] for a in load_result(work / "a1")["assignment"]}
            r2 = {a["studentId"]: a["classId"] for a in load_result(work / "a2")["assignment"]}
            self.assertNotEqual(r1, r2)
            # 第三次重掷 → 拒绝
            p3, _ = write_inputs(work, {**base, "attempt": 2}, students, "p3.json", "s3.json")
            proc = run([ASSIGN, p3, sf, "--out", work / "a3", "--state", state], expect_ok=False)
            self.assertEqual(proc.returncode, 2)
            # 参数变化 → 新任务，attempt=1 重新允许
            p_new, sf_new = write_inputs(work, {**base, "classCount": 3, "capacityPerClass": 24}, students, "pn.json", "sn.json")
            run([ASSIGN, p_new, sf_new, "--out", work / "new", "--state", state])
            # 复现：--fresh-state 相同种子得到一致结果
            run([ASSIGN, p1, sf, "--out", work / "repro", "--state", work / "unused.json", "--fresh-state"])
            self.assertEqual({a["studentId"]: a["classId"] for a in load_result(work / "repro")["assignment"]}, r1)

    def test_log_hash_chain(self):
        students = synth_students(50, seed=15)
        params = {"mode": "balanced", "classCount": 2, "capacityPerClass": 30, "seed": 9}
        import hashlib
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            pf, sf = write_inputs(work, params, students)
            run([ASSIGN, pf, sf, "--out", work / "out", "--state", work / "state.json"])
            prev = hashlib.sha256("genesis".encode()).hexdigest()
            for line in (work / "out" / "audit" / "solver-log.jsonl").read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                self.assertEqual(row["prev"], prev)
                payload = json.dumps({k: v for k, v in row.items() if k not in ("prev", "hash")},
                                     ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                prev = hashlib.sha256((prev + payload).encode()).hexdigest()
                self.assertEqual(row["hash"], prev)
            manifest = json.loads((work / "out" / "audit" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["solverLogHead"], prev)
            self.assertEqual(manifest["attempt"], 1)


class TieredModeTests(unittest.TestCase):
    def test_tiered_assignment_and_preference(self):
        students = synth_students(150, seed=21)
        params = {"mode": "tiered", "classCount": 4, "capacityPerClass": 45, "layerCount": 3,
                  "directions": [{"name": "智能制造", "classCount": 2}, {"name": "新能源汽车", "classCount": 2}]}
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            pf, sf = write_inputs(work, params, students)
            run([ASSIGN, pf, sf, "--out", work / "out", "--state", work / "state.json"])
            result = load_result(work / "out")
            self.assertEqual(len(result["assignment"]), 150)
            counts = {c["id"]: c["count"] for c in result["classes"]}
            self.assertEqual(sum(counts.values()), 150)
            self.assertTrue(all(c <= 45 for c in counts.values()))
            pref = result["preference"]
            self.assertEqual(pref["granted"] + len(pref["unmetDetail"]), 150)
            self.assertGreaterEqual(pref["grantedRate"], 0.5)
            # 志愿统计口径：每个满足者都标注第几志愿
            for a in result["assignment"]:
                if "preferenceGranted" in a:
                    self.assertTrue(a["preferenceGranted"].startswith("第"))
                elif "unmetReason" in a:
                    self.assertTrue(a["unmetReason"])
            # 分层班内画像同质：单一层次的班 std 低于全局；混班只要求总体均值更低
            import math
            def std(vals):
                m = sum(vals) / len(vals)
                return math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))
            global_std = std([s["assessment"]["logic"] for s in students])
            lookup = {s["id"]: s for s in students}
            within = []
            for c in result["classes"]:
                ids = [a["studentId"] for a in result["assignment"] if a["classId"] == c["id"]]
                vals = [lookup[i]["assessment"]["logic"] for i in ids]
                s = std(vals)
                within.append(s)
                if "+" not in (c["layer"] or ""):
                    self.assertLess(s, global_std)
            self.assertLess(sum(within) / len(within), global_std)
            # 名册含层次与志愿列
            roster_files = list((work / "out" / "roster").glob("*.csv"))
            self.assertTrue(roster_files)

    def test_tiered_requires_assessment(self):
        students = synth_students(30, seed=22, with_assessment=False, with_prefs=True)
        params = {"mode": "tiered", "classCount": 2, "capacityPerClass": 20}
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            pf, sf = write_inputs(work, params, students)
            proc = run([ASSIGN, pf, sf, "--out", work / "out", "--state", work / "state.json"], expect_ok=False)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("测评", proc.stderr)


class RosterReaderTests(unittest.TestCase):
    CSV_TEXT = ("学号,姓名,性别,生源地区,成绩,测评-逻辑,测评-实操,志愿1,志愿2\n"
                "2026001,张三,男,粤东,456.5,72,80,智能制造,新能源汽车\n"
                "2026002,李四,女,珠三角,512,88,76,新能源汽车,\n"
                ",王五,m,外省,abc,60,55,数字商贸,智能制造\n")

    def test_csv_reading(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            src = work / "名单.csv"
            src.write_text(self.CSV_TEXT, encoding="utf-8")
            proc = run([READER, src, "--out", work / "students.json"])
            report = json.loads(proc.stdout)
            self.assertEqual(report["rows"], 3)
            self.assertEqual(report["fieldCompleteness"]["id"]["missing"], 1)
            self.assertEqual(report["fieldCompleteness"]["gender"]["missing"], 0)
            students = json.loads((work / "students.json").read_text(encoding="utf-8"))["students"]
            self.assertEqual(students[0]["id"], "2026001")
            self.assertEqual(students[0]["gender"], "男")
            self.assertEqual(students[1]["gender"], "女")
            self.assertEqual(students[2]["gender"], "男")  # m 归一化
            self.assertEqual(students[0]["assessment"], {"逻辑": 72.0, "实操": 80.0})
            self.assertEqual(students[0]["preference"], ["智能制造", "新能源汽车"])
            self.assertEqual(students[1]["preference"], ["新能源汽车"])
            self.assertTrue(any("按行号生成" in a["issue"] for a in report["anomalies"]))
            self.assertTrue(any("成绩不是数字" in a["issue"] for a in report["anomalies"]))

    def test_xlsx_reading(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            src = work / "名单.xlsx"
            make_xlsx(src)
            proc = run([READER, src, "--out", work / "students.json"])
            report = json.loads(proc.stdout)
            self.assertEqual(report["rows"], 3)
            students = json.loads((work / "students.json").read_text(encoding="utf-8"))["students"]
            self.assertEqual(students[0]["id"], "2026101")
            self.assertEqual(students[0]["score"], 430.5)
            self.assertEqual(students[2]["preference"], ["数字媒体", "软件技术"])

    def test_manual_map(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            src = work / "r.csv"
            src.write_text("考生号,称呼,分数\nA1,甲,400\n", encoding="utf-8")
            run([READER, src, "--out", work / "s.json", "--map", "考生号=id", "称呼=name", "分数=score"])
            students = json.loads((work / "s.json").read_text(encoding="utf-8"))["students"]
            self.assertEqual(students[0]["id"], "A1")
            self.assertEqual(students[0]["name"], "甲")
            self.assertEqual(students[0]["score"], 400.0)


def make_xlsx(path: Path):
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
          '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')
    wb = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
          '<sheets><sheet name="新生名单" sheetId="1" r:id="rId1"/></sheets></workbook>')
    wb_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
               '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
               '</Relationships>')
    strings = ["学号", "姓名", "性别", "成绩", "志愿1", "志愿2",
               "2026101", "陈一", "男", "2026102", "林二", "女", "2026103", "黄三", "软件技术", "数字媒体"]
    shared = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="16" uniqueCount="16">'
              + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>")
    rows = [
        [("A1", "s", 0), ("B1", "s", 1), ("C1", "s", 2), ("D1", "s", 3), ("E1", "s", 4), ("F1", "s", 5)],
        [("A2", "s", 6), ("B2", "s", 7), ("C2", "s", 8), ("D2", None, 430.5), ("E2", "s", 14), ("F2", "s", 15)],
        [("A3", "s", 9), ("B3", "s", 10), ("C3", "s", 11), ("D3", None, 505), ("E3", "s", 14), ("F3", None, "")],
        [("A4", "s", 12), ("B4", None, ""), ("C4", None, ""), ("D4", None, 388), ("E4", "s", 15), ("F4", "s", 14)],
    ]

    def cell(ref, t, v):
        if t == "s":
            return f'<c r="{ref}" t="s"><v>{int(v)}</v></c>'
        return f'<c r="{ref}"><v>{v}</v></c>' if v != "" else f'<c r="{ref}"/>'

    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
             + "".join(f'<row r="{i + 1}">' + "".join(cell(ref, t, v) for ref, t, v in row) + "</row>"
                       for i, row in enumerate(rows))
             + "</sheetData></worksheet>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", ct)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", wb)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        zf.writestr("xl/sharedStrings.xml", shared)
        zf.writestr("xl/worksheets/sheet1.xml", sheet)


if __name__ == "__main__":
    unittest.main(verbosity=2)
