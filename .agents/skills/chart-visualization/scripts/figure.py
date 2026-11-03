"""Offline figure/1 command line. Output is published only after preflight succeeds."""
import argparse
from collections import Counter
from html import escape
import json
import os
import re
import subprocess
from pathlib import Path
import sys
import unicodedata
import xml.etree.ElementTree as ET
from tempfile import TemporaryDirectory

from figure_data import PAIR_TYPES, prepare, require


def serialize(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def annotate(p, zh):
    kind = p["kind"]
    if kind in PAIR_TYPES:
        notes = []
        for g in p["groups"]:
            n, total = g["complete"], g["units"]
            notes.append(f"{g['group']} {n}/{total}")
        msg = ("完整配对数/登记对象数为 " if zh else "Complete pairs/enrolled units ") + ", ".join(notes) + ". "
        if kind == "paired":
            return msg + ("每条线连接同一对象，单点表示仅有一次测量。" if zh else
                          "Each line joins one unit. An unconnected point has only one observation.")
        delta = f"{p['phases'][1]} − {p['phases'][0]}. "
        if kind == "change-distribution":
            return msg + delta + ("每点为一个完整配对的变化量，短横线为中位数。" if zh else
                                  "Each dot is one paired difference. Short bars mark medians.")
        return msg + delta + ("点为组内变化中位数，线为双侧至少 95% 的次序统计量区间，假定对象独立。完整对少于 6 时只画点。"
                              if zh else "Points are group medians of paired changes. Whiskers are two-sided, at least 95% order-statistic intervals assuming independent units. Below six pairs only the estimate is shown.")
    rows = p["rows"]
    if kind == "matrix":
        cells = len({r["row"] for r in rows}) * len({r["column"] for r in rows})
        missing = cells - sum(r["value"] is not None for r in rows)
        return f"{cells} 个单元格，{missing} 个缺失。灰色标记缺失，格中数值最多显示四位有效数字。" if zh else f"{cells} cells, {missing} missing. Grey indicates missing cells. Cell values use up to four significant digits."
    keys = ("x", "y") if kind in ("line", "scatter") else ("value",)
    count = sum(all(r[k] is not None for k in keys) for r in rows)
    msg = (f"有效观测 {count}/{len(rows)}。" if zh else f"Observed {count}/{len(rows)}. ")
    if kind == "scatter":
        counts = Counter((r["x"], r["y"]) for r in rows if None not in (r["x"], r["y"]))
        peak = max(counts.values(), default=0)
        if peak > 1:
            return msg + (f"相同坐标合并，点面积正比于观测数，最大为 {peak}。" if zh else
                          f"At identical coordinates marker area scales with multiplicity (maximum {peak}).")
    if kind == "interval":
        without = sum(r["value"] is not None and r["lower"] is None for r in rows)
        return msg + p["method"] + (f"。{without} 个估计未提供区间。" if zh else f". {without} estimates without bounds.")
    if kind == "distribution":
        return msg + ("点为单次观测，短横线为组中位数。" if zh else "Dots show individual observations. Short bars mark group medians.")
    if kind == "histogram":
        return msg + ("柱面积为该区间观测所占比例，各箱左闭右开，最后一箱包含右端点。" if zh else
                      "Bar area is bin probability. Bins include the left edge. The last also includes the right edge.")
    if kind == "ecdf":
        return msg + ("阶梯为观测值小于或等于横轴值的累积比例。" if zh else "Steps show the fraction of observations at or below each value.")
    return msg


def table(headers, rows):
    def cells(values, tag):
        return "".join(f"<{tag}>{escape(str(value)) if value is not None else '—'}</{tag}>" for value in values)
    return ("<table><thead><tr>" + cells(headers, "th") + "</tr></thead><tbody>" +
            "".join("<tr>" + cells(row, "td") + "</tr>" for row in rows) + "</tbody></table>")


def accessible_values(p, zh):
    cn = {"category": "类别", "value": "数值", "group": "组别", "row": "行", "column": "列",
          "lower": "下界", "upper": "上界", "id": "对象编号", "median Δ": "变化中位数",
          "coverage": "名义覆盖率", "n": "完整配对数", "Δ": "变化量"}
    def headings(keys):
        return [cn.get(k, k) for k in keys] if zh else keys

    if p["kind"] not in PAIR_TYPES:
        names = list(p["rows"][0])
        return table(headings(names), ([r[k] for k in names] for r in p["rows"]))
    groups = p["groups"]
    if p["kind"] == "paired":
        return table([*headings(["group", "id"]), *p["phases"]],
                     ([g["group"], sid, *pair] for g in groups for sid, pair in zip(g["ids"], g["pairs"])))
    if p["kind"] == "change-distribution":
        return table(headings(["group", "id", "Δ"]),
                     ([g["group"], sid, v] for g in groups for sid, v in zip(g["ids"], g["changes"])))
    return table(headings(["group", "n", "median Δ", "lower", "upper", "coverage"]),
                 ([g["group"], g["complete"], g["median"], *(g["ci95"] or [None]*3)] for g in groups))


def check_pdf(path, svg):
    fonts = subprocess.check_output(["pdffonts", str(path)], text=True).splitlines()[2:]
    require(fonts and all("TrueType" in row and row.split()[-5] == "yes" and row.split()[-3] == "yes"
                          for row in fonts), "PDF requires embedded TrueType fonts with Unicode mappings; check font fallback")
    exported = subprocess.check_output(["pdftotext", "-raw", str(path), "-"]).decode("utf-8")
    labels = "".join(t.text for t in ET.fromstring(svg).iter("{http://www.w3.org/2000/svg}text"))

    def characters(value):
        return Counter(c for c in unicodedata.normalize("NFKC", value) if not c.isspace())

    require(characters(labels) == characters(exported), "PDF text differs from SVG; check missing glyphs and font coverage")


def generate(spec, out):
    from figure_svg import build_svg, write_pdf

    panels = prepare(spec)
    zh = spec.get("lang") == "zh"
    notes = [annotate(p, zh) for p in panels]
    desc = " ".join([spec["caption"], *[f"{p['title']}. {n}" for p, n in zip(panels, notes)], spec["source"]])
    svg, viewport = build_svg(spec, panels, desc)
    (out / "figure.svg").write_bytes(svg)
    write_pdf(out / "figure.pdf", viewport)
    check_pdf(out / "figure.pdf", svg)
    (out / "values.json").write_text(serialize(panels), encoding="utf-8")
    title = escape(spec["title"])
    kind = "multi-panel"
    if len(panels) == 1:
        name = panels[0]["kind"]
        kind = ("bar" if name == "barh" else name) + "-chart"
    caption = "".join(f"<li><b>{chr(97+i)} · {escape(p['title'])}</b> {escape(n)}</li>"
                      for i, (p, n) in enumerate(zip(panels, notes)))
    tables = "".join(f"<h3>{escape(p['title'])}</h3>{accessible_values(p, zh)}" for p in panels)
    hint = "图幅较宽，可横向滚动查看全图。" if zh else "Scroll horizontally to see the full-width figure."
    html = f"""<!doctype html><html lang="{spec.get('lang', 'en')}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{font:16px/1.55 system-ui,sans-serif;color:#202832;margin:1.2rem auto;padding:0 1rem;max-width:50rem}}
figure{{margin:0}}.chart-viewport{{overflow-x:auto}}svg{{display:block;height:auto}}.pan-hint{{display:none}}
@media(max-width:calc({spec.get('width_mm', 89)}mm + 2rem)){{.pan-hint{{display:block}}}}figcaption{{margin:1rem 0}}ul{{padding-left:1.25em}}
th,td{{text-align:left;padding:.2rem .6rem;border-bottom:1px solid #ddd}}details{{overflow:auto}}</style></head>
<body><figure data-chart-skill="{kind}" data-chart-id="{spec['id']}"><small class="pan-hint">{hint}</small>
<div class="chart-viewport" tabindex="0" role="region" aria-label="{title}">{svg.decode('utf-8')}</div>
<figcaption><b>{title}</b> {escape(spec['caption'])}<ul>{caption}</ul>{'来源' if zh else 'Source'} · {escape(spec['source'])}</figcaption>
<details><summary>{'图表数值' if zh else 'Figure values'}</summary>{tables}</details></figure></body></html>"""
    (out / "figure.html").write_text(html, encoding="utf-8")


def comparable(path):
    if path.suffix != ".pdf":
        return path.read_bytes()
    # Cairo may compress the Info dictionary. Expand objects before ignoring its clock.
    with TemporaryDirectory() as stage:
        expanded = Path(stage) / "expanded.pdf"
        subprocess.run(["mutool", "clean", "-d", str(path), str(expanded)], check=True)
        return re.sub(rb"/CreationDate \(D:[^()]*\)", b"/CreationDate (export time)", expanded.read_bytes(), count=1)


def main():
    parser = argparse.ArgumentParser(description="Render or verify an offline editable scientific figure")
    parser.add_argument("command", choices=("render", "verify"))
    parser.add_argument("spec", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="figure bundle directory")
    args = parser.parse_args()
    if args.command == "render":
        require(not args.out.exists(), "output directory already exists; choose a new path")
    else:
        require(args.out.is_dir(), "bundle directory does not exist")
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    # Stage on the same filesystem. A failed render cannot replace an existing bundle.
    with TemporaryDirectory(dir=args.out.parent) as stage:
        bundle = Path(stage) / "bundle"
        bundle.mkdir()
        generate(spec, bundle)
        if args.command == "render":
            bundle.rename(args.out)
        else:
            for artifact in sorted(bundle.iterdir()):
                actual = args.out / artifact.name
                require(actual.is_file() and comparable(actual) == comparable(artifact),
                        f"{artifact.name} differs from the spec render")
    print(f"{args.command} OK · {args.out}")


if __name__ == "__main__":
    try:
        try:
            import figure_svg
        except (ImportError, ValueError):
            system = Path("/usr/bin/python3")
            if system.exists() and not system.samefile(sys.executable):
                os.execv(str(system), [str(system), __file__, *sys.argv[1:]])
            sys.exit("figure requires Python 3 with PyGObject, librsvg 2.0 and the gjs Cairo PDF backend")
        main()
    except (ValueError, OSError, OverflowError, subprocess.CalledProcessError) as error:
        sys.exit(f"figure: {error}")
