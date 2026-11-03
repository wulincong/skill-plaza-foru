"""核对文档中的演示汇总、广东示例的图例及两种输出格式。"""

from collections import Counter
import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "examples/java-guangdong-heatmap-no-bubbles"
SVG_NS = {"s": "http://www.w3.org/2000/svg"}


class ChartExamples(unittest.TestCase):
    def test_regional_snapshot_and_local_identifiers(self):
        registry_dir = ROOT / "resources/regions"
        registry = json.loads((registry_dir / "registry.json").read_text())
        by_place, levels = {}, Counter()
        for entry in registry["regions"]:
            path = registry_dir / entry["manifest"]
            manifest = json.loads(path.read_text())
            shapes = json.loads((path.parent / manifest["boundaryResource"]).read_text())
            names = json.loads((path.parent / manifest["cityCodeMapping"]).read_text())["cityNameToCode"]
            features = {str(f["properties"]["adcode"]): f["properties"] for f in shapes["features"]}
            by_place[entry["provinceCode"]] = names, features
            levels.update(row["level"] for row in features.values())
        self.assertEqual(len(by_place), 34)
        self.assertEqual(levels, {"city":333, "direct-county":32, "district":103, "county-city":22,
                                  "parish":7, "area":1})
        self.assertEqual(by_place["420000"][1]["429021"]["level"], "direct-county")
        self.assertEqual(by_place["650000"][1]["659012"]["name"], "白杨市")
        self.assertIn("两江新区", by_place["500000"][0])
        self.assertNotIn("渝北区", by_place["500000"][0])
        self.assertEqual(by_place["810000"][0]["沙田区"], "R")
        self.assertEqual(by_place["820000"][1]["5758867"]["level"], "area")
        tw = by_place["710000"][0]
        self.assertEqual(tw["連江縣"], "09007")
        self.assertNotIn("新竹", tw)
        self.assertNotEqual(tw["新竹县"], tw["新竹市"])

    def test_bar_widths_against_printed_axis(self):
        html = (ROOT / "examples/bar-chart.html").read_text()
        svg = ET.fromstring(re.search(r"<svg\b.*?</svg>", html, re.S)[0])
        axis = svg.find(".//s:g[@text-anchor='middle']", SVG_NS)
        ticks = {int(t.text): float(t.get("x")) for t in axis if t.text.isdigit()}
        bars = svg.findall(".//s:rect", SVG_NS)
        self.assertEqual(len(bars), 2)
        for bar, expected in zip(bars, [6, 4]):
            x, width = float(bar.get("x")), float(bar.get("width"))
            self.assertEqual(x, ticks[0])
            self.assertEqual(x + width, ticks[expected])

    def test_documented_city_totals(self):
        doc = (ROOT / "references/heatmap-chart.md").read_text(encoding="utf-8")
        example = json.loads(doc.split("```json\n", 1)[1].split("\n```", 1)[0])
        rows = {row["code"]: row["count"] for row in example["rows"]}
        self.assertEqual(len(rows), len(example["rows"]))
        self.assertTrue(rows.keys() <= set(example["coveredCodes"]))
        self.assertIn(0, rows.values(), "示例应包含一个明确的零值")
        self.assertTrue(set(example["coveredCodes"]) - rows.keys(), "示例应包含未返回记录的城市")
        self.assertGreaterEqual(example["otherCount"], 0)
        self.assertEqual(sum(rows.values()) + example["otherCount"], example["totalCount"])

    def test_html_embeds_same_map(self):
        svg = ET.parse(MAP.with_suffix(".svg")).getroot()
        html = MAP.with_suffix(".html").read_text(encoding="utf-8")
        figure = ET.fromstring(re.search(r"<figure\b.*?</figure>", html, re.S)[0])
        for key in ("data-chart-skill", "data-chart-id"):
            self.assertEqual(figure.attrib[key], svg.attrib.pop(key))
        inline = figure.find("s:svg", SVG_NS)
        inline.tail = None
        self.assertEqual(ET.tostring(inline), ET.tostring(svg))

    def test_city_fills_match_legend(self):
        svg = ET.parse(MAP.with_suffix(".svg"))
        legend = svg.find(".//s:text[@class='legend-title']/..", SVG_NS)
        self.assertIsNotNone(legend)
        swatches = legend.findall("s:rect", SVG_NS)
        labels = legend.findall("s:text[@class='legend']", SVG_NS)
        self.assertEqual(len(swatches), len(labels))
        colours = {label.text: swatch.attrib["fill"] for label, swatch in zip(labels, swatches)}
        missing = colours.pop("未返回")
        self.assertNotIn(missing, colours.values(), "缺失值不能与数值共用颜色")
        bands = [(tuple(map(int, label.split("–"))), colour) for label, colour in colours.items()]

        paths = svg.findall(".//s:path[@data-adcode]", SVG_NS)
        boundaries = ROOT / "resources/boundaries/guangdong-440000-city.geojson"
        features = json.loads(boundaries.read_text(encoding="utf-8"))["features"]
        self.assertCountEqual([p.attrib["data-adcode"] for p in paths],
                              [str(f["properties"]["adcode"]) for f in features])
        total = 0
        for path in paths:
            label = path.findtext("s:title", namespaces=SVG_NS)
            with self.subTest(city=label):
                if "未返回" in label:
                    self.assertEqual(path.attrib["fill"], missing)
                    continue
                count = int(re.search(r"：(\d+) 条", label)[1])
                expected = [colour for (lo, hi), colour in bands if lo <= count <= hi]
                self.assertEqual(expected, [path.attrib["fill"]])
                total += count
        self.assertEqual(total, 669)


if __name__ == "__main__":
    unittest.main()
