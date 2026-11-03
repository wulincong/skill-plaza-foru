"""Exercise the public CLI and inspect actual SVG geometry, PDF and accessible data."""
from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
import xml.etree.ElementTree as ET

from figure_data import median_ci, prepare

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/figure.py"
NS = {"s": "http://www.w3.org/2000/svg"}
BLUE = "#21658a"


def example(name):
    return json.loads((ROOT / f"examples/{name}.json").read_text())


def single(kind, fields, rows, **options):
    p = dict(kind=kind, fields={k: k for k in fields}, title="Measured response", data="obs",
             x_label="Horizontal", y_label="Vertical", **options)
    return dict(schema="figure/1", id="Trial", title="Independent test", caption="Reference run",
                source="Synthetic observations", datasets={"obs": [dict(zip(fields, row)) for row in rows]},
                panels=[p])


class Output(unittest.TestCase):
    def setUp(self):
        stage = TemporaryDirectory()
        self.addCleanup(stage.cleanup)
        self.root = Path(stage.name)
        self.spec = self.root / "input.json"
        self.out = self.root / "bundle"

    def cli(self, command):
        return subprocess.run([sys.executable, str(CLI), command, str(self.spec), "--out", str(self.out)],
                              cwd=self.root, text=True, capture_output=True)

    def render(self, spec):
        self.spec.write_text(json.dumps(spec))
        job = self.cli("render")
        self.assertEqual(job.returncode, 0, job.stderr)
        return ET.parse(self.out / "figure.svg")

    def test_bar_geometry_and_tamper(self):
        self.render(single("barh", ["category", "value"], [("Alpha", 6), ("Beta", 4), ("Gamma", 0)]))
        path = self.out / "figure.svg"
        svg = ET.parse(path)
        bars = svg.findall(f".//s:rect[@fill='{BLUE}']", NS)
        ticks = {t.text: float(t.get("x")) for t in svg.findall(".//s:text", NS) if not t.get("class") and t.text in ("0", "2", "4", "6")}
        unit = (ticks["2"] - ticks["0"]) / 2
        self.assertEqual(len(bars), 2)
        for bar, v in zip(bars, (6, 4)):
            self.assertAlmostEqual(float(bar.get("x")), ticks["0"])
            self.assertAlmostEqual(float(bar.get("width")), v * unit)
        self.assertEqual(self.cli("verify").returncode, 0)
        before = path.read_text()
        path.write_text(before.replace(f'width="{bars[0].get("width")}"', f'width="{2 * unit}"', 1))
        self.assertIn("figure.svg differs", self.cli("verify").stderr)
        self.assertNotEqual(self.cli("render").returncode, 0)
        self.assertNotEqual(path.read_text(), before)

    def test_signed_vertical_bars_start_at_zero(self):
        svg = self.render(single("bar", ["category", "value"], [("R", -3), ("S", 6), ("T", None)]))
        bars = svg.findall(f".//s:rect[@fill='{BLUE}']", NS)
        self.assertEqual(len(bars), 2)
        low, high = bars
        self.assertAlmostEqual(float(low.get("y")), float(high.get("y")) + float(high.get("height")))
        self.assertAlmostEqual(float(high.get("height")), 2 * float(low.get("height")))
        self.assertIn("NA", [t.text for t in svg.findall(".//s:text", NS)])

    def test_numeric_time_spacing_and_observation_gap(self):
        svg = self.render(single("line", ["x", "y"], [(10, 4), (2, 3), (0, 0), (7, None)]))
        points = svg.findall(".//s:circle", NS)
        self.assertEqual(len(points), 3)
        x0, x2, x10 = [float(p.get("cx")) for p in points]
        self.assertAlmostEqual((x10-x0) / (x2-x0), 5)
        segments = svg.findall(f".//s:line[@stroke='{BLUE}']", NS)
        self.assertEqual(len(segments), 1)
        self.assertEqual(float(segments[0].get("x2")), x2)

    def test_grouped_trend_joins_only_the_same_series_and_respects_time_gaps(self):
        spec = single("grouped-line", ["group", "x", "y"],
                      [("B", 7, 11), ("A", 0, 2), ("B", 0, 0), ("B", 2, 5), ("A", 7, 5)])
        svg = self.render(spec)
        a = svg.find(".//s:g[@data-series='A']", NS)
        b = svg.find(".//s:g[@data-series='B']", NS)
        aligned = json.loads((self.out/"values.json").read_text())[0]["rows"]
        self.assertIn({"group":"A", "x":2, "y":None}, aligned)
        self.assertIn("<th>Horizontal</th><th>Vertical</th>", (self.out/"figure.html").read_text())
        self.assertEqual(len(a.findall("s:line", NS)), 0)
        edges = b.findall("s:line", NS)
        self.assertEqual(len(edges), 2)
        dx = [float(e.get("x2")) - float(e.get("x1")) for e in edges]
        self.assertAlmostEqual(dx[1]/dx[0], 5/2)

    def test_facets_share_both_scales_and_styles(self):
        spec = single("faceted-line", ["facet","group","x","y"],
                      [("P","one",1,4),("Q","two",7,30),("Q","one",1,4),("P","one",7,5)])
        spec.update(columns=2, width_mm=160)
        svg = self.render(spec)
        layers = svg.findall(".//s:g[@data-series='one']", NS)
        marks = [layer.find("s:circle", NS) for layer in layers]
        self.assertEqual(len(layers), 2)
        self.assertEqual(marks[0].attrib, marks[1].attrib)
        self.assertIn("a–b", (self.out/"figure.html").read_text())
        self.assertEqual(self.cli("verify").returncode, 0)

    def test_ungrouped_facets_show_a_missing_facet_on_the_common_axes(self):
        spec = single("faceted-line", ["facet","x","y"], [("P",1,0),("Q",1,None)])
        svg = self.render(spec)
        panes = svg.findall("./s:g", NS)
        self.assertEqual(len(panes), 2)
        self.assertEqual(len(panes[0].findall(".//s:circle", NS)), 1)
        self.assertEqual(len(panes[1].findall(".//s:circle", NS)), 0)

    def test_province_geometry_and_value_encoding(self):
        spec = example("provincial-trends")
        spec.update(panels=spec["panels"][-1:], columns=1)
        spec["panels"][0]["scale"] = "zero-centered"
        spec["datasets"]["全国样本"] = [{"编码":k, "岗位数":v} for k,v in
                                     [("香港", 4), (820000, -4), ("台湾省", 0), ("110000", None)]]
        svg = self.render(spec)
        features = {f.get("data-code"): f for f in svg.findall(".//*[@data-code]", NS)}
        self.assertEqual(len(features), 34)
        self.assertEqual(len({features[k].get("fill") for k in ["810000","820000","710000","110000"]}), 4)
        self.assertEqual(features["110000"].get("fill"), features["440000"].get("fill"))
        self.assertIn("香港特别行政区 · 4", features["810000"].findtext("s:title", namespaces=NS))
        self.assertEqual(features["820000"].get("data-name"), "澳门特别行政区")
        self.assertIn("<th>岗位数（千条）</th>", (self.out/"figure.html").read_text())
        text_labels = {t.text for t in svg.findall(".//s:text", NS)}
        self.assertTrue(set(spec["panels"][0]["labels"]).issubset(text_labels))
        table = json.loads((self.out/"values.json").read_text())[0]["rows"]
        self.assertEqual(len(table), 34)
        self.assertEqual(sum(r["value"] is not None for r in table), 3)
        self.assertEqual(self.cli("verify").returncode, 0)

    def test_unequal_histogram_areas_and_cutpoints(self):
        spec = single("histogram", ["value"], [(0,), (.5,), (1,), (2,), (4,), (None,)], edges=[0, 1, 4])
        svg = self.render(spec)
        bins = json.loads((self.out / "values.json").read_text())[0]["bins"]
        self.assertEqual([b["count"] for b in bins], [2, 3])
        self.assertAlmostEqual(sum((b["upper"]-b["lower"]) * b["density"] for b in bins), 1)
        rects = svg.findall(".//s:rect", NS)
        (w1,h1),(w2,h2) = [(float(r.get("width")), float(r.get("height"))) for r in rects]
        self.assertAlmostEqual(w2/w1, 3)
        self.assertAlmostEqual(w2*h2/(w1*h1), 3/2)
        spec["panels"][0]["edges"] = [0, 1]
        with self.assertRaisesRegex(ValueError, "include every"):
            prepare(spec)

    def test_coincident_scatter_points_encode_frequency_by_area(self):
        spec = single("scatter", ["x", "y"], [(1, 2)]*4 + [(2, 1), (None, 5)])
        svg = self.render(spec)
        points = svg.findall(".//s:circle", NS)
        self.assertEqual(len(points), 2)
        self.assertAlmostEqual((float(points[0].get("r")) / float(points[1].get("r"))) ** 2, 4)
        self.assertIn("maximum 4", (self.out / "figure.html").read_text())

    def test_ecdf_ties_and_denominator(self):
        svg = self.render(single("ecdf", ["value"], [(1,), (1,), (2,), (3,), (None,)]))
        coords = [tuple(map(float, pt.split(","))) for pt in svg.find(".//s:polyline", NS).get("points").split()]
        self.assertEqual(len(coords), 8)
        ymin, ymax = coords[0][1], coords[-1][1]
        self.assertEqual(coords[1][0], coords[2][0])
        self.assertAlmostEqual((coords[2][1]-ymin)/(ymax-ymin), .5)

    def test_matrix_absent_and_zero(self):
        svg = self.render(single("matrix", ["row","column","value"], [("A","X",0),("A","Y",-2),("B","Y",1)],
                                 scale="zero-centered"))
        cells = svg.findall(".//s:rect[@stroke='white']", NS)
        self.assertEqual(len(cells), 4)
        self.assertEqual(len({r.get("fill") for r in cells}), 4)
        self.assertEqual(cells[2].get("fill"), "#e1e3e5")
        self.assertIn("-2 … 2", [t.text for t in svg.findall(".//s:text", NS)])

    def test_raw_distribution_and_supplied_intervals(self):
        d = single("distribution", ["group","value"], [("A",4),("A",4),("B",2),("B",None)])
        s = single("interval", ["group","value","lower","upper"], [("A",3,1,5),("B",-1,None,None)],
                   method="Model-based 95% intervals")
        d["datasets"]["est"] = s["datasets"]["obs"]
        d["panels"].append(dict(s["panels"][0], data="est"))
        svg = self.render(d)
        groups = svg.findall("./s:g", NS)
        dots = groups[0].findall("s:circle", NS)
        self.assertEqual(len(dots), 3)
        self.assertEqual(dots[0].get("cy"), dots[1].get("cy"))
        self.assertNotEqual(dots[0].get("cx"), dots[1].get("cx"))
        self.assertEqual(len(groups[1].findall(f"s:line[@stroke='{BLUE}']", NS)), 3)
        self.assertEqual(len(groups[1].findall("s:circle", NS)), 2)

    def test_paired_figure_and_physical_export(self):
        spec = example("paired-recovery")
        svg = self.render(spec)
        a,b,c = json.loads((self.out / "values.json").read_text())
        self.assertEqual([g["complete"] for g in a["groups"]], [7,8])
        self.assertEqual(a["groups"][0]["pairs"][a["groups"][0]["ids"].index("A8")], [65,None])
        self.assertEqual(b["groups"][0]["changes"], [4,1,5,3,3,2,4])
        self.assertNotIn("A8", b["groups"][0]["ids"])
        self.assertEqual([g["median"] for g in c["groups"]], [3,-1])
        self.assertEqual(c["groups"][0]["ci95"][:2], [1,5])
        first = svg.find("./s:g", NS)
        self.assertEqual(len(first.findall("s:line[@stroke='#869ba7']", NS)), 15)
        self.assertEqual(len(first.findall("s:circle", NS)), 16)
        self.assertEqual(len(first.findall("s:rect", NS)), 15)
        html = (self.out / "figure.html").read_text()
        self.assertIn("对象编号", html)
        self.assertIn("A8</td><td>65</td><td>—", html)
        pdf = str(self.out / "figure.pdf")
        info = subprocess.check_output(["pdfinfo", pdf], text=True)
        w,h = map(float, re.search(r"Page size:\s+([\d.]+) x ([\d.]+) pts", info).groups())
        self.assertAlmostEqual(w*25.4/72, 89, places=2)
        self.assertAlmostEqual(h*25.4/72, 156, places=2)
        self.assertEqual(len(subprocess.check_output(["pdfimages","-list",pdf],text=True).splitlines()), 2)
        replay = self.cli("verify")
        self.assertEqual(replay.returncode, 0, replay.stderr)

    def test_scatter_complete_coordinates_and_delivery_integrity(self):
        spec = example("sensor-calibration")
        svg = self.render(spec)
        self.assertEqual(len(svg.find("./s:g", NS).findall("s:circle", NS)), 8)
        for name in ("values.json", "figure.pdf", "figure.html"):
            with self.subTest(name=name):
                path = self.out / name
                saved = path.read_bytes()
                # Substitute a different valid PDF, so the verifier must inspect the PDF objects.
                if name == "figure.pdf":
                    path.write_bytes((ROOT / "examples/paired-recovery.pdf").read_bytes())
                else:
                    path.write_bytes(saved.replace(b"S1", b"S9", 1))
                job = self.cli("verify")
                self.assertNotEqual(job.returncode, 0)
                self.assertIn(name + " differs", job.stderr)
                path.write_bytes(saved)

    def test_common_scale_and_no_clipped_interval(self):
        spec = single("interval", ["group","value","lower","upper"], [("A", 5, 3, 9)], method="95% CI")
        spec["panels"][0]["y_ticks"] = [0, 5, 10]
        spec["panels"].append(dict(spec["panels"][0], title="Second sample", data="other"))
        spec["datasets"]["other"] = [{"group":"B", "value":5, "lower":2, "upper":6}]
        svg = self.render(spec)
        dots = svg.findall("./s:g/s:circle", NS)
        self.assertEqual(dots[0].get("cy"), dots[1].get("cy"))
        spec["panels"][0]["y_ticks"] = [0, 5]
        self.spec.write_text(json.dumps(spec))
        self.assertIn("clip data", self.cli("verify").stderr)

    def test_overlapping_labels_fail_without_partial_delivery(self):
        spec = single("bar", ["category","value"], [(f"Long category title {i}", i) for i in range(10)])
        self.spec.write_text(json.dumps(spec))
        job = self.cli("render")
        self.assertNotEqual(job.returncode, 0)
        self.assertRegex(job.stderr, "overlapping labels|text outside")
        self.assertFalse(self.out.exists())


class Statistics(unittest.TestCase):
    def test_reject_duplicate_province_aliases_city_codes_and_trend_keys(self):
        spec = example("provincial-trends")
        for key in ("duplicate", "city", "trend"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                bad = deepcopy(spec)
                if key == "trend":
                    bad["datasets"]["两行业记录"].append(bad["datasets"]["两行业记录"][0])
                else:
                    bad["datasets"]["全国样本"].append({"编码": "广东" if key == "duplicate" else "440100", "岗位数": 3})
                prepare(bad)

    def test_median_interval_cutoffs(self):
        self.assertIsNone(median_ci([5]*5))
        self.assertEqual(median_ci([1,2,3,4,5,6]), [1,6,0.96875])
        self.assertEqual(median_ci(list(range(10)))[:2], [1,8])

    def test_unidentified_duplicate_or_dependent_pairs_fail(self):
        spec = example("paired-recovery")
        for error in ("id", "duplicate", "group", "independence"):
            with self.subTest(error=error):
                s = deepcopy(spec)
                rows = s["datasets"]["recovery"]
                if error == "id":
                    del rows[0]["试件"]
                elif error == "duplicate":
                    rows.append(rows[0])
                elif error == "group":
                    rows[0]["材料"] = "other"
                else:
                    s["panels"][-1]["independent_units"] = False
                with self.assertRaises(ValueError):
                    prepare(s)

    def test_singletons_never_create_a_ci(self):
        spec = example("paired-recovery")
        rows = spec["datasets"]["recovery"]
        spec["datasets"]["recovery"] = [r for r in rows if r["试件"] in ("A1","A8")]
        panels = prepare(spec)
        self.assertEqual(panels[0]["groups"][0]["units"], 2)
        self.assertEqual(panels[2]["groups"][0]["median"], 4)
        self.assertIsNone(panels[2]["groups"][0]["ci95"])

    def test_invalid_estimates_and_coordinates_fail(self):
        for spec in (single("interval", ["group","value","lower","upper"], [("A",2,3,5)], method="95% CI"),
                     single("matrix", ["row","column","value"], [("A","X",0),("A","X",1)], scale="sequential"),
                     single("scatter", ["x","y"], [(1, float("nan"))]),
                     single("bar", ["category","value"], [("zero",False)])):
            with self.subTest(spec=spec["panels"][0]["kind"]), self.assertRaises(ValueError):
                prepare(spec)


if __name__ == "__main__":
    unittest.main()
