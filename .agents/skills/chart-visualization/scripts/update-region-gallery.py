"""Refresh the embedded offline province selector data in an existing chart gallery."""

import argparse
import json
import math
import re
from pathlib import Path


def svg_ring(points):
    """Use more precision for islands and holes too small for the default screen grid."""
    for digits in (1, 3, 6):
        vertices = []
        for x, y in points:
            point = (round(x, digits), round(y, digits))
            if not vertices or point != vertices[-1]:
                vertices.append(point)
        if len(vertices) < 3:
            continue
        ox, oy = vertices[0]
        area = sum(
            (a - ox) * (d - oy) - (b - oy) * (c - ox)
            for (a, b), (c, d) in zip(vertices, vertices[1:] + vertices[:1])
        )
        if area:

            def fmt(v, digits=digits):
                return f"{v:.{digits}f}".rstrip("0").rstrip(".")

            return "M" + " ".join(f"{fmt(x)},{fmt(y)}" for x, y in vertices) + "Z"
    raise ValueError("degenerate boundary ring in gallery projection")


def preview(root, region):
    mpath = root / "regions" / region["manifest"]
    m = json.loads(mpath.read_text())
    features = json.loads((mpath.parent / m["boundaryResource"]).read_text())["features"]
    geoms = []
    for f in features:
        g = f["geometry"]
        geoms.append(g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]])
    coords = [pt for polys in geoms for poly in polys for ring in poly for pt in ring]
    xs, ys = zip(*coords)
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    c = math.cos(math.radians((y0 + y1) / 2))
    k = min(580 / ((x1 - x0) * c), 390 / (y1 - y0))

    def xy(x, y):
        return (300 + (x - (x0 + x1) / 2) * c * k, 205 - (y - (y0 + y1) / 2) * k)

    units = []
    for f, polys in zip(features, geoms):
        body = []
        for poly in polys:
            for ring in poly:
                body.append(svg_ring([xy(x, y) for x, y in ring[:-1]]))
        props = f["properties"]
        assert body
        units.append([str(props["adcode"]), props["name"], props["unitType"], "".join(body)])
    return {
        "name": region["province"],
        "units": units,
        "credit": m["source"]["attribution"],
        "snapshot": m["source"]["snapshot"],
        "license": m["source"]["license"],
        "url": m["source"]["url"],
        "terms": m["source"]["licenseUrl"],
    }


root = Path(__file__).resolve().parents[1] / "resources"
registry = json.loads((root / "regions/registry.json").read_text())
packages = {r["provinceCode"]: preview(root, r) for r in registry["regions"]}

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("gallery", type=Path, nargs="?", default=root.parent / "examples/chart-gallery.html")
gallery = parser.parse_args().gallery
payload = json.dumps(packages, ensure_ascii=False, separators=(",", ":")).replace("<", r"\u003c")
pattern = r'(<script id="regional-geometry" type="application/json">).*?(</script>)'
updated, n = re.subn(pattern, lambda m: m[1] + payload + m[2], gallery.read_text(), flags=re.DOTALL)
if n != 1:
    raise ValueError("expected exactly one regional atlas data block")
gallery.write_text(updated)
