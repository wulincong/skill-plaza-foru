#!/usr/bin/env python3
"""名单读取与字段规范化（纯标准库，支持 CSV 与 XLSX）。

版本 1.1.0（与 assign.py 的 SOLVER_VERSION 同步）。

用法（在会话工作区运行）：
    python3 <技能目录>/scripts/read_roster.py 名单.xlsx --out students.json
    python3 <技能目录>/scripts/read_roster.py 名单.csv --out students.json --map 学号=id 志愿1=preference

输出 students.json（规范化学生数组）并在 stdout 打印字段完整性报告（JSON）。
列名按同义词自动识别；识别不到的列原样保留在 extra 中，可用 --map 手工指定。
"""

import argparse
import csv
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

COLUMN_SYNONYMS = {
    "id": ["学号", "编号", "学生编号", "学生id", "id", "考号", "准考证号"],
    "name": ["姓名", "学生姓名", "name"],
    "gender": ["性别", "gender"],
    "region": ["生源地区", "生源", "地区", "籍贯", "region"],
    "score": ["成绩", "总分", "分数", "入学成绩", "入学总分", "高考成绩", "score"],
    "preference": ["方向志愿", "志愿", "志愿方向", "preference"],
}
RANKED_PREF = re.compile(r"^(?:第?([一二三四五六1-6])?志愿|志愿([一二三四五六1-6]))$")
PREF_SEPARATORS = re.compile(r"[、,，;；/|\s]+")
ASSESS_PREFIX = re.compile(r"^(?:测评|能力测评|assessment)[:：\-—_]?")
GENDER_KEYS = {"男": "男", "女": "女", "m": "男", "f": "女", "male": "男", "female": "女", "1": "男", "2": "女"}


def normalize_header(h):
    return str(h or "").strip().lower().replace(" ", "").replace("　", "")


def detect_columns(headers):
    mapping, unmapped = {}, []
    rank_cols = []
    for h in headers:
        key = normalize_header(h)
        hit = None
        for field, names in COLUMN_SYNONYMS.items():
            if key in [normalize_header(x) for x in names]:
                hit = field
                break
        if hit:
            if hit in mapping and hit != "preference":
                unmapped.append({"column": h, "reason": f"{hit} 已由列「{mapping[hit]}」占用"})
                continue
            mapping[hit] = h
            continue
        ranked = RANKED_PREF.match(key)
        if ranked:
            rank_cols.append((int("一二三四五六".index(ranked.group(1) or ranked.group(2))) + 1
                              if (ranked.group(1) or ranked.group(2)) in "一二三四五六"
                              else int(ranked.group(1) or ranked.group(2)), h))
            continue
        if ASSESS_PREFIX.match(key):
            mapping[f"assessment:{re.sub(ASSESS_PREFIX, '', key) or h}"] = h
            continue
        unmapped.append({"column": h, "reason": "未识别为已知字段"})
    rank_cols.sort()
    return mapping, unmapped, [h for _rank, h in rank_cols]


def normalize_gender(v):
    if v is None or str(v).strip() == "":
        return None
    key = str(v).strip().lower()
    return GENDER_KEYS.get(key, str(v).strip())


def parse_preference(values):
    """values: 按志愿序排列的原始列值列表（可能来自单列拆分或多列）。"""
    out = []
    for v in values:
        for part in PREF_SEPARATORS.split(str(v or "")):
            if part.strip():
                out.append(part.strip())
    seen, unique = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def read_csv_rows(path: Path):
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    sample = text[:65536]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(text.splitlines(), dialect))
    return [r for r in rows if any(str(c).strip() for c in r)]


def col_index(ref: str) -> int:
    n = 0
    for ch in ref:
        if ch.isalpha():
            n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


def read_xlsx_rows(path: Path, sheet: str | None):
    with zipfile.ZipFile(path) as zf:
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
              "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ElementTree.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iterfind(".//m:t", ns)))
        wb = ElementTree.fromstring(zf.read("xl/workbook.xml"))
        rels = ElementTree.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rel_map = {rel.get("Id"): rel.get("Target") for rel in rels}
        sheets = [(s.get("name"), rel_map.get(s.get("{%s}id" % ns["r"]))) for s in wb.find("m:sheets", ns)]
        if not sheets:
            raise ValueError("工作簿没有工作表")
        target = None
        if sheet:
            hits = [rid for name, rid in sheets if name == sheet]
            if not hits:
                raise ValueError(f"找不到工作表：{sheet}（可用：{'、'.join(n for n, _ in sheets)}）")
            target = hits[0]
        else:
            target = sheets[0][1]
        target = target.replace("/xl/", "xl/") if target.startswith("/xl/") else ("xl/" + target.lstrip("/"))
        if target not in zf.namelist():
            target = "xl/worksheets/" + target.split("/")[-1]
        ws = ElementTree.fromstring(zf.read(target))
        rows = []
        for row in ws.iterfind(".//m:row", ns):
            cells = {}
            for c in row.findall("m:c", ns):
                idx = col_index(c.get("r", "A1"))
                t = c.get("t")
                v = c.find("m:v", ns)
                if t == "inlineStr":
                    is_el = c.find("m:is", ns)
                    cells[idx] = "".join(x.text or "" for x in is_el.iterfind(".//m:t", ns)) if is_el is not None else ""
                elif v is None or v.text is None:
                    cells[idx] = ""
                elif t == "s":
                    cells[idx] = shared[int(v.text)]
                else:
                    cells[idx] = v.text
            if cells:
                width = max(cells) + 1
                rows.append([cells.get(i, "") for i in range(width)])
        return [r for r in rows if any(str(c).strip() for c in r)], [n for n, _ in sheets]


def main():
    ap = argparse.ArgumentParser(description="名单读取与字段规范化")
    ap.add_argument("file", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sheet", help="XLSX 工作表名（默认第一个）")
    ap.add_argument("--map", nargs="*", default=[], metavar="列名=字段",
                    help="手工映射，字段可为 id/name/gender/region/score/preference/assessment:子字段")
    args = ap.parse_args()

    if not args.file.exists():
        print(f"read_roster.py: 文件不存在：{args.file}", file=sys.stderr)
        raise SystemExit(2)
    suffix = args.file.suffix.lower()
    try:
        if suffix == ".xlsx":
            rows, sheet_names = read_xlsx_rows(args.file, args.sheet)
        elif suffix == ".csv":
            rows, sheet_names = read_csv_rows(args.file), None
        else:
            print(f"read_roster.py: 仅支持 .csv 与 .xlsx，收到 {suffix}", file=sys.stderr)
            raise SystemExit(2)
    except (zipfile.BadZipFile, ValueError, ElementTree.ParseError) as exc:
        print(f"read_roster.py: 解析失败：{exc}", file=sys.stderr)
        raise SystemExit(2)

    if not rows:
        print("read_roster.py: 表格没有任何数据行", file=sys.stderr)
        raise SystemExit(2)
    headers = [str(h) for h in rows[0]]
    mapping, unmapped, pref_rank_cols = detect_columns(headers)
    for item in args.map:
        if "=" not in item:
            continue
        column, field = item.split("=", 1)
        column, field = column.strip(), field.strip()
        if column not in headers:
            print(f"read_roster.py: --map 的列「{column}」不存在", file=sys.stderr)
            raise SystemExit(2)
        for key, val in list(mapping.items()):
            if val == column or (key.startswith("assessment:") and field.startswith("assessment:") and key == field):
                del mapping[key]
        mapping[field] = column

    students = []
    anomalies = []
    for row_no, raw in enumerate(rows[1:], start=2):
        cell = {h: (raw[i].strip() if isinstance(raw[i], str) else raw[i]) for i, h in enumerate(headers) if i < len(raw)}
        s = {}
        def take(field):
            column = mapping.get(field)
            return cell.get(column) if column else None
        sid = take("id")
        sid = str(sid).strip() if sid is not None and str(sid).strip() != "" else None
        if sid is None:
            sid = f"R{row_no:04d}"
            anomalies.append({"row": row_no, "issue": "缺少编号，按行号生成占位 id", "id": sid})
        s["id"] = sid
        s["name"] = str(take("name") or "").strip()
        gender_raw = take("gender")
        s["gender"] = normalize_gender(gender_raw)
        if s["gender"] not in ("男", "女", None):
            anomalies.append({"row": row_no, "issue": f"性别取值异常：{gender_raw}", "id": sid})
        s["region"] = str(take("region") or "").strip()
        score_raw = take("score")
        if score_raw is not None and str(score_raw).strip() != "":
            try:
                s["score"] = float(str(score_raw).replace("，", ""))
            except ValueError:
                s["score"] = str(score_raw).strip()
                anomalies.append({"row": row_no, "issue": f"成绩不是数字：{score_raw}", "id": sid})
        assessment = {}
        for key, column in mapping.items():
            if key.startswith("assessment:"):
                sub = key.split(":", 1)[1]
                value = cell.get(column)
                if value is not None and str(value).strip() != "":
                    try:
                        assessment[sub] = float(value)
                    except ValueError:
                        anomalies.append({"row": row_no, "issue": f"测评 {sub} 不是数字：{value}", "id": sid})
        if assessment:
            s["assessment"] = assessment
        pref_values = []
        pref_col = mapping.get("preference")
        if pref_col and pref_col not in pref_rank_cols:
            pref_values.append(cell.get(pref_col))
        pref_values += [cell.get(c) for c in pref_rank_cols]
        prefs = parse_preference(pref_values)
        if prefs:
            s["preference"] = prefs
        extras = {h: cell[h] for h in headers
                  if h not in mapping.values() and h not in pref_rank_cols and cell.get(h) not in (None, "")}
        if extras:
            s["extra"] = extras
        students.append(s)

    fields = ["id", "name", "gender", "region", "score", "assessment", "preference"]
    completeness = {}
    for f in fields:
        present = 0
        for s in students:
            v = s.get(f)
            if f == "assessment":
                present += 1 if isinstance(v, dict) and v else 0
            elif f == "preference":
                present += 1 if isinstance(v, list) and v else 0
            else:
                present += 1 if v is not None and str(v).strip() != "" else 0
        if f == "id":
            present -= sum(1 for a in anomalies if a.get("issue", "").startswith("缺少编号"))
        completeness[f] = {"present": present, "missing": len(students) - present, "total": len(students)}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"students": students}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "file": str(args.file), "sheet": args.sheet or (sheet_names[0] if sheet_names else None),
        "rows": len(students), "columns": {"mapped": mapping, "rankedPreference": pref_rank_cols, "unmapped": unmapped},
        "fieldCompleteness": completeness, "anomalies": anomalies,
        "out": str(args.out),
        "note": "id 缺失的行已按行号生成占位编号；性别统一为 男/女；测评列合并进 assessment；未识别列保留在 extra，可用 --map 指定映射后重跑",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
