"""Lay out vector marks in physical points; measure text with the export engine."""
from collections import Counter
from copy import deepcopy
from functools import lru_cache
from itertools import combinations
import math
import os
from statistics import median
import xml.etree.ElementTree as ET

from pathlib import Path
import subprocess
import gi
gi.require_version("Rsvg", "2.0")
from gi.repository import Rsvg

from figure_data import PAIR_TYPES, TREND_TYPES, require
from province_map import basemap, short_name

NS = "http://www.w3.org/2000/svg"
FONT = "Liberation Sans, WenQuanYi Zen Hei, sans-serif"
INK, BLUE, ORANGE, MUTED = "#202832", "#21658a", "#a64512", "#586671"
PT = 72 / 25.4


def el(parent, tag, **attrs):
    return ET.SubElement(parent, tag, {k.replace("_", "-"): str(v) for k, v in attrs.items()})


def rect(container, x, y, w, h, color, **attrs):
    return el(container, "rect", x=x, y=y, width=w, height=h, fill=color, **attrs)


def line(container, x1, y1, x2, y2, color=INK, weight=.6):
    return el(container, "line", x1=x1, y1=y1, x2=x2, y2=y2, stroke=color, stroke_width=weight)


def text(container, x, y, value, anchor="middle", size=6.5, **attrs):
    t = el(container, "text", x=x, y=y, text_anchor=anchor, font_size=size, fill=INK, **attrs)
    t.text = str(value)
    return t


def view(w, h):
    box = Rsvg.Rectangle()
    box.x, box.y, box.width, box.height = 0, 0, w, h
    return box


@lru_cache(maxsize=2048)
def text_width(s):
    svg = ET.Element("svg", xmlns=NS, width="1000", height="20", attrib={"font-family": FONT})
    text(svg, 1, 10, s, anchor="start", id="measure")
    handle = Rsvg.Handle.new_from_data(ET.tostring(svg, encoding="utf-8"))
    return handle.get_geometry_for_layer("#measure", view(1000, 20))[1].width


def number(v):
    return format(v, ".4g") if v else "0"


def scale_ticks(values, override=None, zero=False, target=4):
    require(values, "no observed values for this panel")
    lo, hi = min(values), max(values)
    if zero:
        lo, hi = min(0, lo), max(0, hi)
    if override is not None:
        require(override[0] <= lo and hi <= override[-1], "fixed ticks would clip data, intervals or baseline")
        require(len(set(map(number, override))) == len(override), "tick labels indistinguishable at current units")
        return override
    if lo == hi:
        pad = abs(lo) * .1 or 1
        lo, hi = (0 if zero and lo == 0 else lo - pad), hi + pad
    step = (hi - lo) / target
    require(math.isfinite(step) and step > 0, "numeric range exceeds plot precision")
    base = 10 ** math.floor(math.log10(step))
    require(base > 0, "numeric range exceeds plot precision")
    step = next(n for n in (1, 2, 2.5, 5, 10) if n >= step / base - 1e-12) * base
    start, stop = math.floor(lo / step), math.ceil(hi / step)
    ticks = [k * step for k in range(start, stop + 1)]
    require(len(set(map(number, ticks))) == len(ticks), "ticks indistinguishable; change units or report a reference offset")
    return ticks


def panel_axes(p):
    kind = p["kind"]
    rows = p.get("rows", [])
    if kind == "barh":
        values = [r["value"] for r in rows if r["value"] is not None]
        return scale_ticks(values, p.get("x_ticks"), zero=True), [r["category"] for r in rows]
    if kind == "histogram":
        bins = p["bins"]
        return scale_ticks([bins[0]["lower"], bins[-1]["upper"]], p.get("x_ticks")), scale_ticks([b["density"] for b in bins], p.get("y_ticks"), zero=True)
    if kind == "matrix":
        return list(dict.fromkeys(r["column"] for r in rows)), list(dict.fromkeys(r["row"] for r in rows))
    if kind == "ecdf":
        return scale_ticks([r["value"] for r in rows if r["value"] is not None], p.get("x_ticks")), [0, .25, .5, .75, 1]
    if kind in {"line", "scatter"}:
        valid = [r for r in rows if r["x"] is not None and r["y"] is not None]
        xs = [r["x"] for r in (rows if kind == "line" else valid)]
        return scale_ticks(xs, p.get("x_ticks")), scale_ticks([r["y"] for r in valid], p.get("y_ticks"))
    if kind in PAIR_TYPES:
        cats = [g["group"] for g in p["groups"]]
        if kind == "paired":
            vals = [v for g in p["groups"] for pair in g["pairs"] for v in pair]
        elif kind == "change-distribution":
            vals = [v for g in p["groups"] for v in g["changes"]]
        else:
            vals = [v for g in p["groups"] for v in [g["median"], *(g["ci95"] or [])[:2]]]
    else:
        key = "category" if kind == "bar" else "group"
        cats = list(dict.fromkeys(r[key] for r in rows))
        vals = [r[k] for r in rows for k in (("value", "lower", "upper") if kind == "interval" else ("value",))]
    return cats, scale_ticks([v for v in vals if v is not None], p.get("y_ticks"), zero=kind in {"bar", "median-change", "change-distribution"})


# The same series receives the same colour and dash pattern in every facet.
SERIES = [(BLUE, ""), (ORANGE, "4 2"), ("#267254", "1 2"), ("#79508a", "5 2 1 2"),
          ("#80592a", "6 2"), ("#2e7480", "3 1 1 1"), ("#9b3858", "2 2"), ("#475362", "7 2 2 2")]


def trend_panels(panel):
    rows = panel["rows"]
    times = sorted({row["x"] for row in rows})
    if "x_ticks" not in panel and len(times) <= 6 and all(float(t).is_integer() for t in times):
        xt = times if len(times) > 1 else [times[0]-1, times[0], times[0]+1]
    else:
        xt = scale_ticks(times, panel.get("x_ticks"))
    yt = scale_ticks([r["y"] for r in rows if r["y"] is not None], panel.get("y_ticks"))
    groups = list(dict.fromkeys(r.get("group") for r in rows))
    by_facet = {}
    for row in rows:
        by_facet.setdefault(row.get("facet"), []).append(row)
    for facet, subset in by_facet.items():
        title = panel["title"] if facet is None else f"{panel['title']} · {facet}"
        yield dict(panel, title=title, rows=subset, axes=(xt, yt), groups=groups, times=times)


def series_mark(parent, x, y, index, legend=False):
    color, dash = SERIES[index]
    if legend:
        sample = line(parent, x-4, y, x+4, y, color, .9)
        if dash:
            sample.set("stroke-dasharray", dash)
    if index % 3 == 0:
        el(parent, "circle", cx=x, cy=y, r=1.6, fill=color)
    elif index % 3 == 1:
        rect(parent, x-1.5, y-1.5, 3, 3, color)
    else:
        el(parent, "path", d=f"M{x},{y-2}l1.9,3.3h-3.8Z", fill=color)


class Panel:
    def __init__(self, parent, p, w, h, letter, chinese):
        self.p, self.g = p, parent
        self.na = "缺失" if chinese else "NA"
        self.xt, self.yt = p["axes"] if p["kind"] in TREND_TYPES else panel_axes(p)
        matrix = p["kind"] == "matrix"
        categorical_y = p["kind"] in {"matrix", "barh"}
        numeric_x = p["kind"] in TREND_TYPES | {"line", "scatter", "ecdf", "barh", "histogram"}
        xt_labels = [number(x) if numeric_x else x for x in self.xt]
        if p["kind"] in TREND_TYPES and all(float(t).is_integer() for t in self.xt):
            xt_labels = [str(int(t)) for t in self.xt]
        if p["kind"] in PAIR_TYPES:
            count = "units" if p["kind"] == "paired" else "complete"
            xt_labels = [f"{g['group']} (n={g[count]})" for g in p["groups"]]
        yt_labels = [y if categorical_y else number(y) for y in self.yt]
        self.left = 16 + max(map(text_width, yt_labels))
        self.right = w - max(6, text_width(xt_labels[-1]) / 2 + 2 if numeric_x else 6)
        self.top = 20 if not matrix else 30
        if p["kind"] in TREND_TYPES and p["groups"] != [None]:
            present = {r["group"] for r in p["rows"] if r["y"] is not None}
            pos, baseline = 2, 21
            for index, group in enumerate(p["groups"]):
                span = text_width(group) + 19
                require(span <= w, "trend legend label too wide")
                if pos + span > w:
                    pos, baseline = 2, baseline + 10
                if group in present:
                    series_mark(parent, pos+4, baseline-2, index, legend=True)
                    text(parent, pos+12, baseline, group, "start")
                pos += span
            self.top = baseline + 9
        self.bottom = h - (35 if p["kind"] == "paired" else 26)
        require(self.right - self.left >= 49 and self.bottom - self.top >= 36,
                "insufficient plotting area; widen figure, increase panel height or use fewer columns")
        if letter:
            text(parent, 1, 9, letter, "start", 8, font_weight="bold")
        text(parent, 12 if letter else 1, 9, p["title"], "start", 7)
        line(parent, self.left, self.bottom, self.right, self.bottom)
        line(parent, self.left, self.bottom, self.left, self.top)
        self.xstep = (self.right - self.left) / len(self.xt)
        self.ystep = (self.bottom - self.top) / len(self.yt)
        for i, label in enumerate(yt_labels):
            y = self.top + (i + .5) * self.ystep if categorical_y else self.y(self.yt[i])
            line(parent, self.left - 2, y, self.left, y)
            text(parent, self.left - 4, y + 2.1, label, "end")
        for i, label in enumerate(xt_labels):
            x = self.x(self.xt[i]) if numeric_x else self.center(i)
            line(parent, x, self.bottom, x, self.bottom + 2)
            text(parent, x, self.bottom + (18 if p["kind"] == "paired" else 10), label)
        text(parent, (self.left + self.right) / 2, h - 3, p["x_label"])
        ym = (self.bottom + self.top) / 2
        text(parent, 5, ym, p["y_label"], transform=f"rotate(-90 5 {ym})")

    def center(self, i):
        return self.left + (i + .5) * self.xstep

    def x(self, v):
        pad = 0 if self.p["kind"] == "barh" else 3
        return self.left + pad + (v - self.xt[0]) / (self.xt[-1] - self.xt[0]) * (self.right - self.left - 2*pad)

    def y(self, v):
        pad = 0 if self.p["kind"] in {"bar", "histogram"} else 3
        return self.bottom - pad - (v - self.yt[0]) / (self.yt[-1] - self.yt[0]) * (self.bottom - self.top - 2 * pad)

    def dot(self, x, v, color=BLUE, radius=2):
        el(self.g, "circle", cx=x, cy=self.y(v), r=radius, fill=color)

    def dots(self, center, values):
        # Pack repeated or close observations at their exact y coordinate.
        placed = []
        for v in sorted(values):
            y = self.y(v)
            offsets = [0]
            for j in range(1, math.ceil(self.xstep / 8)):
                offsets.extend([-j * 4, j * 4])
            offset = next((o for o in offsets if abs(o) + 2 < self.xstep / 2 and
                           all(math.hypot(o - a, y - b) >= 3.8 for a, b in placed if abs(y-b) < 4)), None)
            require(offset is not None, "observations overlap; widen this panel or use an ECDF for dense distributions")
            placed.append((offset, y))
            self.dot(center + offset, v, radius=1.8)
        if values:
            x = center + min(self.xstep * .32, max(a for a, _ in placed) + 6)
            line(self.g, x - 2, self.y(median(values)), x + 2, self.y(median(values)), INK, 1.3)

    def trajectories(self, x, pairs):
        dx = self.xstep * .23
        for px, phase in zip((x - dx, x + dx), self.p["phases"]):
            text(self.g, px, self.bottom + 9, phase, size=5.5)
        # Use the same lateral offset at both visits. Separate coincident endpoints.
        placed = []
        for a, b in pairs:
            ys = tuple(self.y(v) if v is not None else None for v in (a, b))
            offsets = [0]
            for j in range(1, math.ceil(dx / 4)):
                offsets.extend([-j * 4, j * 4])
            offset = next((o for o in offsets if all(
                abs(o-old) >= 4 or all(u is None or v is None or abs(u-v) >= 3.6
                                       for u, v in zip(ys, previous))
                for old, previous in placed)), None)
            require(offset is not None, "coincident paired marks; widen panel or split groups")
            placed.append((offset, ys))
            x1, x2 = x - dx + offset, x + dx + offset
            if a is not None and b is not None:
                line(self.g, x1, self.y(a), x2, self.y(b), "#869ba7", .6)
            if a is not None:
                self.dot(x1, a, radius=1.65)
            if b is not None:
                rect(self.g, x2 - 1.5, self.y(b) - 1.5, 3, 3, ORANGE)

    def interval(self, x, v, limits):
        if v is None:
            return
        if limits:
            y1, y2 = (self.y(k) for k in limits[:2])
            line(self.g, x, y1, x, y2, BLUE, 1)
            for y in (y1, y2):
                line(self.g, x - 3, y, x + 3, y, BLUE, 1)
        self.dot(x, v, INK, 2.5)

    def draw(self):
        p, kind = self.p, self.p["kind"]
        rows = p.get("rows", [])
        if kind in {"bar", "median-change", "change-distribution"} and self.yt[0] < 0 < self.yt[-1]:
            line(self.g, self.left, self.y(0), self.right, self.y(0), "#b4bec2", .5).set("stroke-dasharray", "2 2")
        if kind in PAIR_TYPES:
            for i, group in enumerate(p["groups"]):
                x = self.center(i)
                if kind == "change-distribution":
                    self.dots(x, group["changes"])
                elif kind == "median-change":
                    self.interval(x, group["median"], group["ci95"])
                else:
                    self.trajectories(x, group["pairs"])
            return
        if kind == "barh":
            if self.xt[0] < 0 < self.xt[-1]:
                line(self.g, self.x(0), self.top, self.x(0), self.bottom, "#b4bec2", .5)
            for i, row in enumerate(rows):
                y = self.top + (i + .5) * self.ystep
                v = row["value"]
                if v is None:
                    text(self.g, (self.left + self.right) / 2, y + 2, self.na, size=6)
                elif v == 0:
                    line(self.g, self.x(0), y-3, self.x(0), y+3, BLUE, 1.2)
                else:
                    height = min(15, self.ystep * .58)
                    rect(self.g, min(self.x(0), self.x(v)), y-height/2, abs(self.x(v)-self.x(0)), height, BLUE)
                if v is not None:
                    inside = abs(self.x(v) - self.x(0)) > text_width(number(v)) + 7
                    direction = 1 if v >= 0 else -1
                    offset = -direction if inside else direction
                    if not inside and self.x(v) + offset * (text_width(number(v)) + 3) > self.right:
                        offset = -1
                    if not inside and self.x(v) + offset * (text_width(number(v)) + 3) < self.left:
                        offset = 1
                    mark = text(self.g, self.x(v) + 3 * offset, y + 2, number(v),
                                "start" if offset > 0 else "end", 6)
                    mark.set("class", "bar-value")
                    if inside:
                        mark.set("fill", "#fff")
            return
        if kind == "histogram":
            for b in p["bins"]:
                x1, x2 = self.x(b["lower"]), self.x(b["upper"])
                rect(self.g, x1, self.y(b["density"]), x2-x1, self.y(0)-self.y(b["density"]),
                     BLUE, stroke="white", stroke_width=.45)
            return
        if kind == "ecdf":
            counts = Counter(r["value"] for r in rows if r["value"] is not None)
            total, n, x0 = sum(counts.values()), 0, self.x(self.xt[0])
            points = [(x0, self.y(0))]
            for v in sorted(counts):
                points.append((self.x(v), self.y(n / total)))
                n += counts[v]
                points.append((self.x(v), self.y(n / total)))
            points.append((self.x(self.xt[-1]), self.y(1)))
            el(self.g, "polyline", points=" ".join(f"{x},{y}" for x,y in points),
               fill="none", stroke=BLUE, stroke_width=1.1)
            return
        if kind == "scatter":
            counts = Counter((r["x"], r["y"]) for r in rows if None not in (r["x"], r["y"]))
            for (x, y), count in counts.items():
                radius = 2 * math.sqrt(count)
                require(radius < min(self.right - self.left, self.bottom - self.top) / 5,
                        "many coincident points; aggregate and label frequencies before plotting")
                self.dot(self.x(x), y, radius=radius)
            return
        if kind in TREND_TYPES:
            if all(row["y"] is None for row in rows):
                message = "无有效观测" if self.na == "缺失" else "No observations"
                text(self.g, (self.left+self.right)/2, (self.top+self.bottom)/2, message)
                return
            series = {}
            for row in rows:
                series.setdefault(row.get("group"), {})[row["x"]] = row["y"]
            for index, group in enumerate(p["groups"]):
                observed = series.get(group, {})
                if not observed:
                    continue
                layer = el(self.g, "g", data_series=group or p["title"])
                color, dash = SERIES[index]
                previous = None
                for time in p["times"]:
                    value = observed.get(time)
                    if value is None:
                        previous = None
                        continue
                    point = self.x(time), self.y(value)
                    if previous is not None:
                        segment = line(layer, *previous, *point, color, 1)
                        if dash:
                            segment.set("stroke-dasharray", dash)
                    series_mark(layer, *point, index)
                    previous = point
            return
        if kind == "line":
            previous = None
            for r in rows:
                if r["x"] is None or r["y"] is None:
                    previous = None
                    continue
                x, y = self.x(r["x"]), self.y(r["y"])
                if previous:
                    line(self.g, *previous, x, y, BLUE, 1)
                self.dot(x, r["y"])
                previous = x, y
            return
        if kind == "matrix":
            self.matrix(rows)
            return
        for i, group in enumerate(self.xt):
            x = self.center(i)
            if kind == "distribution":
                self.dots(x, [r["value"] for r in rows if r["group"] == group and r["value"] is not None])
                continue
            row = rows[i]
            v = row["value"]
            if v is None:
                text(self.g, x, self.top + 7, self.na, size=6)
            elif kind == "interval":
                self.interval(x, v, [row["lower"], row["upper"]] if row["lower"] is not None else None)
            elif v == 0:
                line(self.g, x - 3, self.y(0), x + 3, self.y(0), BLUE, 1.2)
            else:
                width = min(28, self.xstep * .58)
                rect(self.g, x - width / 2, min(self.y(0), self.y(v)), width, abs(self.y(v) - self.y(0)), BLUE)
            if kind == "bar" and v is not None:
                end = self.y(v)
                label_y = end - 3 if v >= 0 else end + 7
                inside = label_y < self.top + 5 or label_y > self.bottom
                if inside:
                    label_y = end + 7 if v >= 0 else end - 3
                mark = text(self.g, x, label_y, number(v), size=6)
                mark.set("class", "bar-value")
                if inside and v != 0:
                    mark.set("fill", "#fff")

    def matrix(self, rows):
        vals = [r["value"] for r in rows if r["value"] is not None]
        require(vals, "matrix has no observed cells")
        lo, hi = min(vals), max(vals)
        diverging = self.p["scale"] == "zero-centered"
        if diverging:
            hi = max(abs(lo), abs(hi))
            lo = -hi
        def color(v):
            if diverging:
                end = (170, 74, 20) if v < 0 else (25, 90, 129)
                t = abs(v) / hi if hi else 0
            else:
                end = (25, 90, 129)
                t = (v - lo) / (hi - lo) if hi != lo else .5
            rgb = [round(a + t * (b - a)) for a, b in zip((242, 247, 247), end)]
            channels = [c / 255 for c in rgb]
            linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
            luminance = sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))
            # Choose the greater contrast ratio against black or white text.
            ink = "#000" if (luminance + .05) / .05 >= 1.05 / (luminance + .05) else "#fff"
            return "rgb(%d,%d,%d)" % tuple(rgb), ink
        for i in range(20):
            rect(self.g, self.left + i * 1.7, 19, 1.8, 3.5, color(lo + (hi-lo)*i/19)[0])
        text(self.g, self.left + 37, 22.5, f"{number(lo)} … {number(hi)}", "start", 6)
        cells = {(r["row"], r["column"]): r["value"] for r in rows}
        require(self.ystep >= 9, "matrix cells too short; increase panel height or split rows")
        for j, row in enumerate(self.yt):
            for i, col in enumerate(self.xt):
                v = cells.get((row, col))
                fill, ink = color(v) if v is not None else ("#e1e3e5", INK)
                x, y = self.left + i*self.xstep, self.top + j*self.ystep
                rect(self.g, x, y, self.xstep, self.ystep, fill, stroke="white", stroke_width=.6)
                value_label = self.na if v is None else number(v)
                require(text_width(value_label) + 3 < self.xstep, "matrix cell text exceeds cell width")
                cell = text(self.g, self.center(i), y + self.ystep / 2 + 2, value_label)
                cell.set("fill", ink)


def draw_provinces(parent, panel, width, height, letter, chinese):
    if letter:
        text(parent, 1, 9, letter, "start", 8, font_weight="bold")
    text(parent, 12 if letter else 1, 9, panel["title"], "start", 7)
    rows = {r["code"]: r for r in panel["rows"]}
    observed = [r["value"] for r in rows.values() if r["value"] is not None]
    nonzero = [v for v in observed if v != 0]
    lo, hi = (min(nonzero), max(nonzero)) if nonzero else (0, 0)
    centered = panel["scale"] == "zero-centered"
    if centered:
        hi = max(abs(lo), abs(hi))
        lo = -hi
    missing, zero = "#bfc4c5", "#fff"

    def ramp(value):
        if centered:
            pale, dark = (247, 245, 239), (156, 63, 29) if value < 0 else (28, 87, 132)
            fraction = abs(value) / hi if hi else 0
        else:
            pale, dark = (211, 236, 241), (24, 80, 126)
            fraction = (value-lo) / (hi-lo) if hi != lo else 1
        return "#%02x%02x%02x" % tuple(round(a + (b-a)*fraction) for a,b in zip(pale, dark))

    original = basemap()
    _, _, geo_w, geo_h = map(float, original.get("viewBox").split())
    left_w = width * .64
    factor = min(left_w / geo_w, (height - 23) / geo_h)
    dx = (left_w - geo_w * factor) / 2
    drawing = el(parent, "g", transform=f"translate({dx} 16) scale({factor})",
                 stroke="#64757b", stroke_width=.7, stroke_linejoin="round")
    labels = []
    for shape in original:
        feature = deepcopy(shape)
        code = feature.get("data-code")
        if code:
            row = rows[code]
            v = row["value"]
            feature.set("fill", missing if v is None else zero if v == 0 else ramp(v))
            if code in panel["labels"]:
                px, py = map(float, feature.get("data-pin").split())
                labels.append((dx+px*factor, 16+py*factor, short_name(row["region"])))
            title = el(feature, "title")
            title.text = f"{row['region']} · {v if v is not None else ('缺失' if chinese else 'NA')}"
        drawing.append(feature)
    for x, y, name in labels:
        text(parent, x, y+2, name, size=6, stroke="white", stroke_width=1.5, paint_order="stroke")

    x, y = left_w + 5, 23
    text(parent, x, y, panel["unit"], "start", 7)
    y += 13
    if nonzero:
        if lo != hi:
            bar_w = min(70, width - x - 8)
            for i in range(40):
                rect(parent, x+bar_w*i/40, y, bar_w/40+.1, 5, ramp(lo+(hi-lo)*i/39))
            text(parent, x, y+14, number(lo), "start")
            text(parent, x+bar_w, y+14, number(hi), "end")
            if centered:
                text(parent, x+bar_w/2, y+14, "0")
            y += 26
        else:
            rect(parent, x, y-5, 7, 6, ramp(lo))
            text(parent, x+12, y, number(lo), "start")
            y += 13
    for color, name in [(zero, "0"), (missing, "缺失" if chinese else "Missing")]:
        rect(parent, x, y-5, 7, 6, color, stroke="#69777b", stroke_width=.5)
        text(parent, x+12, y, name, "start")
        y += 12
    coverage = f"有值 {len(observed)} / 34" if chinese else f"Observed {len(observed)} / 34"
    text(parent, x, y+3, coverage, "start")
    text(parent, x, height-3, "M. MaiLin · CC0", "start", 5.5)


def build_svg(spec, panels, description):
    w = spec.get("width_mm", 89)
    h = spec.get("panel_height_mm", 55)
    cols = spec.get("columns", 1)
    panels = [display for panel in panels for display in
              (trend_panels(panel) if panel["kind"] in TREND_TYPES else [panel])]
    nrows = math.ceil(len(panels) / cols)
    width, height = w * PT, h * PT * nrows
    ident = spec["id"]
    svg = ET.Element("svg", {"xmlns": NS, "width": f"{w}mm", "height": f"{h*nrows}mm",
                             "viewBox": f"0 0 {width} {height}", "role": "img",
                             "aria-labelledby": f"{ident}-title {ident}-desc", "font-family": FONT})
    el(svg, "title", id=f"{ident}-title").text = spec["title"]
    el(svg, "desc", id=f"{ident}-desc").text = description
    slot = width / cols
    labels = {}
    bounds = {}
    for i, panel in enumerate(panels):
        row, col = divmod(i, cols)
        left, top = col * slot, row * h * PT
        g = el(svg, "g", transform=f"translate({left+4} {top+3})")
        letter = chr(97+i) if len(panels) > 1 else None
        chinese = spec.get("lang") == "zh"
        if panel["kind"] == "province-map":
            draw_provinces(g, panel, slot-9, h*PT-6, letter, chinese)
        else:
            Panel(g, panel, slot-9, h*PT-6, letter, chinese).draw()
        for element in g.iter("text"):
            key = f"{ident}-t{len(labels)}"
            element.set("id", key)
            labels[key] = element.text
            bounds[key] = (left, top, left + slot, top + h * PT)
    data = ET.tostring(svg, encoding="utf-8")
    handle = Rsvg.Handle.new_from_data(data)
    handle.set_dpi(72)
    viewport = view(width, height)
    boxes = {}
    for key, s in labels.items():
        box = handle.get_geometry_for_layer("#"+key, viewport)[1]
        edges = (box.x, box.y, box.x + box.width, box.y + box.height)
        left, top, right, bottom = bounds[key]
        require(box.width > 0 and box.height > 0 and edges[0] >= left and edges[1] >= top and
                edges[2] <= right and edges[3] <= bottom, f"text outside panel: {s!r}")
        boxes[key] = edges
    for a, b in combinations(boxes, 2):
        ax, ay, ar, ab = boxes[a]
        bx, by, br, bb = boxes[b]
        require(min(ar,br) <= max(ax,bx) or min(ab,bb) <= max(ay,by),
                f"overlapping labels {labels[a]!r}, {labels[b]!r}; reflow, shorten labels or widen figure")
    return data, viewport


def write_pdf(path, viewport):
    subprocess.run(["gjs", str(Path(__file__).with_name("figure_pdf.js")),
                    str(path.with_suffix(".svg")), str(path), str(viewport.width), str(viewport.height)],
                   env={**os.environ, "TZ": "UTC"}, check=True)
