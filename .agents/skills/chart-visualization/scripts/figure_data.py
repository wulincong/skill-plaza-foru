"""Interpret a figure/1 spec into the values actually drawn. Pure Python."""
from bisect import bisect_right
import math
import re
from statistics import median

from province_map import province_code, province_rows


def require(condition, message):
    if not condition:
        raise ValueError(message)


def label(value, name):
    require(isinstance(value, str) and value.strip(), f"{name} requires non-empty text")
    return value


def num(value, name):
    require(type(value) in (int, float) and math.isfinite(value), f"{name} requires a finite number or null")
    return value


def structure(item, required, optional=()):
    require(isinstance(item, dict), "expected an object")
    missing = set(required) - item.keys()
    extra = item.keys() - set(required) - set(optional)
    require(not (missing or extra), f"missing {sorted(missing)}, unknown {sorted(extra)}")


def median_ci(values):
    """Narrowest equal-tail order-statistic CI with at least 95% coverage."""
    n = len(values)
    # For interval [X_(k), X_(n+1-k)], each tail is P(Bin(n, .5) < k).
    total, tail, term, k = 1 << n, 0, 1, 0
    while 40 * (tail + term) <= total:
        tail += term
        term = term * (n - k) // (k + 1)
        k += 1
    if not k:
        return None
    ordered = sorted(values)
    return [ordered[k - 1], ordered[-k], 1 - 2 * tail / total]


PAIR_TYPES = {"paired", "change-distribution", "median-change"}
TREND_TYPES = {"grouped-line", "faceted-line"}
ROLES = {
    "grouped-line": ("group", "x", "y"), "faceted-line": ("facet", "x", "y"),
    "province-map": ("region", "value"),
    "bar": ("category", "value"), "barh": ("category", "value"),
    "histogram": ("value",), "line": ("x", "y"), "scatter": ("x", "y"),
    "ecdf": ("value",), "distribution": ("group", "value"), "interval": ("group", "value", "lower", "upper"),
    "matrix": ("row", "column", "value"),
    **{kind: ("group", "id", "phase", "value") for kind in PAIR_TYPES},
}


def paired_values(rows, phases):
    require(isinstance(phases, list) and len(phases) == 2 and phases[0] != phases[1],
            "phases must name two distinct conditions in order")
    for phase in phases:
        label(phase, "phases")
    require(len({type(row["id"]) for row in rows}) == 1, "use one ID type throughout the dataset")
    subjects = {}
    for row in rows:
        subject, phase = row["id"], row["phase"]
        require(phase in phases, f"unexpected phase {phase!r}")
        group, values = subjects.setdefault(subject, (row["group"], {}))
        require(group == row["group"], f"ID {subject!r} occurs in multiple groups")
        require(phase not in values, f"duplicate observation for {subject!r}, {phase!r}")
        values[phase] = row["value"]
    groups = {}
    for subject, (group, values) in subjects.items():
        groups.setdefault(group, {})[subject] = [values.get(p) for p in phases]
    return groups


def prepare_panel(panel, datasets):
    kind = panel.get("kind") if isinstance(panel, dict) else None
    require(isinstance(kind, str) and kind in ROLES, f"unknown chart kind {kind!r}")
    options = {"histogram": ("edges",), "interval": ("method",), "matrix": ("scale",), "median-change": ("phases", "independent_units")}
    label_keys = ("unit",) if kind == "province-map" else ("x_label", "y_label")
    required = ("kind", "title", "data", "fields", *label_keys)
    options["province-map"] = ("scale",)
    axes = []
    if kind in TREND_TYPES | {"line", "scatter", "histogram", "ecdf", "barh"}:
        axes.append("x_ticks")
    if kind not in {"matrix", "barh", "ecdf", "province-map"}:
        axes.append("y_ticks")
    required += options.get(kind, ("phases",) if kind in PAIR_TYPES else ())
    structure(panel, required, ("labels",) if kind == "province-map" else axes)
    for key in ("title", "data", *label_keys):
        label(panel[key], key)
    data = datasets.get(panel["data"])
    require(isinstance(data, list) and data, f"no rows in {panel['data']!r}")
    fields = panel["fields"]
    structure(fields, ROLES[kind], ("group",) if kind == "faceted-line" else ())
    for name in fields.values():
        label(name, "field name")
    require(len(set(fields.values())) == len(fields), "field roles must use distinct columns")
    rows = []
    for i, raw in enumerate(data, 1):
        row = {}
        for role, name in fields.items():
            require(isinstance(raw, dict) and name in raw, f"row {i} lacks column {name!r}")
            value = raw[name]
            if role in {"value", "x", "y", "lower", "upper"}:
                row[role] = None if value is None else num(value, f"row {i} {name}")
            else:
                row[role] = value if role in ("id", "region") and type(value) is int else label(value, f"row {i} {name}")
        rows.append(row)
    result = {"kind": kind, "title": panel["title"]}
    if kind == "province-map":
        require(panel["scale"] in ("sequential", "zero-centered"), "unknown map scale")
        labels = panel.get("labels", [])
        require(isinstance(labels, list), "map labels must be an array of provincial codes or names")
        codes = [province_code(key) for key in labels]
        require(len(codes) == len(set(codes)), "duplicate province labels")
        return dict(result, unit=panel["unit"], scale=panel["scale"], labels=codes, rows=province_rows(rows))
    result.update(x_label=panel["x_label"], y_label=panel["y_label"])
    for key in axes:
        if key in panel:
            ticks = panel[key]
            require(isinstance(ticks, list) and len(ticks) >= 2, f"{key} requires at least two ticks")
            result[key] = [num(t, key) for t in ticks]
            require(all(b > a for a, b in zip(ticks, ticks[1:])), f"{key} must increase")
    if kind in PAIR_TYPES:
        groups = paired_values(rows, panel["phases"])
        result.update(phases=panel["phases"], groups=[])
        if kind == "median-change":
            require(panel["independent_units"] is True, "median CI requires independent units")
        for group, subjects in groups.items():
            pairs = list(subjects.values())
            complete = {sid: b - a for sid, (a, b) in subjects.items() if a is not None and b is not None}
            changes = list(complete.values())
            record = {"group": group, "units": len(pairs), "complete": len(changes),
                      "ids": list(subjects if kind == "paired" else complete)}
            if kind == "paired":
                record["pairs"] = pairs
            elif kind == "change-distribution":
                record["changes"] = changes
            else:
                record.update(median=median(changes) if changes else None, ci95=median_ci(changes))
            result["groups"].append(record)
        return result
    unique_keys = {"bar": ("category",), "barh": ("category",), "line": ("x",), "interval": ("group",), "matrix": ("row", "column")}
    if kind in TREND_TYPES:
        # Align only the (facet, series) combinations that were actually submitted.
        times = sorted({r["x"] for r in rows if r["x"] is not None})
        roles = [key for key in ("facet", "group") if key in fields]
        series = {}
        for row in rows:
            key = tuple(row[k] for k in roles)
            time = row["x"]
            require(time is not None, "trend requires a time coordinate")
            readings = series.setdefault(key, {})
            require(time not in readings, f"duplicate {kind} coordinate {key}, {time}")
            readings[time] = row["y"]
        require(len({r.get("group") for r in rows}) <= 8, "too many trend groups; use facets or split the figure")
        require(len({r.get("facet") for r in rows}) <= 26, "too many trend facets; split the figure")
        result["fields"] = fields
        result["rows"] = [dict(zip(roles, key), x=t, y=readings.get(t))
                          for key, readings in series.items() for t in times]
        return result
    if kind in unique_keys:
        keys = [tuple(row[key] for key in unique_keys[kind]) for row in rows]
        require(len(keys) == len(set(keys)), f"duplicate {kind} coordinate")
    if kind == "histogram":
        edges = panel["edges"]
        require(isinstance(edges, list) and len(edges) >= 2, "histogram requires at least two bin edges")
        edges = [num(v, "bin edge") for v in edges]
        require(all(b > a for a, b in zip(edges, edges[1:])), "bin edges must increase")
        counts = [0] * (len(edges) - 1)
        for row in rows:
            v = row["value"]
            if v is not None:
                require(edges[0] <= v <= edges[-1], "histogram edges must include every observation")
                counts[min(bisect_right(edges, v) - 1, len(counts)-1)] += 1
        total = sum(counts)
        require(total > 0, "histogram has no observed values")
        result["bins"] = [{"lower": a, "upper": b, "count": n, "density": n / total / (b - a)}
                          for a, b, n in zip(edges, edges[1:], counts)]
    if kind == "line":
        require(all(row["x"] is not None for row in rows), "line requires a position even for a missing observation")
        rows.sort(key=lambda row: row["x"])
    if kind == "interval":
        result["method"] = label(panel["method"], "interval method and level")
        for row in rows:
            v, lo, hi = (row[key] for key in ("value", "lower", "upper"))
            require((lo is None and hi is None) or
                    (None not in (lo, v, hi) and lo <= v <= hi), "interval must bracket estimate")
    if kind == "matrix":
        require(panel["scale"] in ("sequential", "zero-centered"), "unknown matrix scale")
        result["scale"] = panel["scale"]
    result["rows"] = rows
    return result


def prepare(spec):
    structure(spec, ("schema", "id", "title", "caption", "source", "datasets", "panels"),
              ("width_mm", "panel_height_mm", "columns", "lang"))
    require(spec["schema"] == "figure/1", "unsupported schema")
    require(re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", label(spec["id"], "id")), "invalid figure id")
    for key in ("title", "source", "caption"):
        label(spec[key], key)
    require(spec.get("lang", "en") in ("en", "zh"), "lang must be en or zh")
    require(isinstance(spec["datasets"], dict), "datasets must map names to row arrays")
    panels = spec["panels"]
    require(isinstance(panels, list) and 1 <= len(panels) <= 26, "expected 1 to 26 panels")
    width, height, columns = (spec.get(k, v) for k, v in (("width_mm", 89), ("panel_height_mm", 55), ("columns", 1)))
    require(55 <= num(width, "width_mm") <= 300 and 32 <= num(height, "panel_height_mm") <= 200,
            "width_mm outside 55–300 or panel_height_mm outside 32–200")
    prepared = [prepare_panel(panel, spec["datasets"]) for panel in panels]
    slots = sum(len({r["facet"] for r in p["rows"]}) if p["kind"] == "faceted-line" else 1 for p in prepared)
    require(slots <= 26, "at most 26 displayed panels; split the figure")
    require(type(columns) is int and 1 <= columns <= slots, "invalid columns")
    return prepared
