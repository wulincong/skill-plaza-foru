"""Maintenance only: rebuild the curated release from the pinned inputs in resources/README.md."""

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory

import osmium
import shapely as shp

RESOURCES = Path(__file__).resolve().parents[1] / "resources"
CTA = "https://doi.org/10.5281/zenodo.22179207"
CTA_CREDIT = "Cheng Rui、Hu Yunfeng、Xiao Chiwei、Wang Yanjun，CTAmap v2.0（2026 层）"
CTA_LICENSE = "https://creativecommons.org/licenses/by/4.0/"
ADCODE = "six-digit administrative division adcode"
MUNICIPALITIES = {"110000", "120000", "310000", "500000"}
PINNED = {
    "T2026_prefecture.gpkg": "2c935849e66db951eeb7cc368cbb563c",
    "T2026_county.gpkg": "e2a74da75e0901e4fc06daada0dd5180",
    "hong-kong.json": "ab2123b5a48c2e39e29ce594a0c51590cf6081922ab2c5c14ff78338b788f760",
    "taiwan.geojson": "a809e483184d7762918476058cc9d7e10e9720113187afee2a04b4f7ced3103f",
    "macau.osm.pbf": "c165b11d11a27bcd5c1a2d4b2db84f57737bb480572ac5e145db53aa41764f87",
    "carmo.osm": "8532efbaabcf6ffe8fe6a22465cd10dbbc7a74bd6a5a5ac3ef5076b44d26c77d",
}
# Common Chinese short names cannot always be derived by dropping the final administrative suffix.
AUTONOMOUS = [
    "延边",
    "恩施",
    "湘西",
    "阿坝",
    "甘孜",
    "凉山",
    "黔西南",
    "黔东南",
    "黔南",
    "楚雄",
    "红河",
    "文山",
    "西双版纳",
    "大理",
    "德宏",
    "怒江",
    "迪庆",
    "临夏",
    "甘南",
    "海北",
    "黄南",
    "海南",
    "果洛",
    "玉树",
    "海西",
    "昌吉",
    "博尔塔拉",
    "巴音郭楞",
    "克孜勒苏",
    "伊犁",
]


def write_json(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    opts = {"separators": (",", ":")} if compact else {"indent": 2}
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, **opts) + "\n", encoding="utf-8")


def source(credit, url, licence, terms, version, files):
    return {
        "attribution": credit,
        "url": url,
        "license": licence,
        "licenseUrl": terms,
        "snapshot": version,
        "inputs": {key: PINNED[key] for key in files},
    }


def mainland(directory):
    provinces = defaultdict(list)
    sources = {}
    for layer in ("prefecture", "county"):
        file = f"T2026_{layer}.gpkg"
        table = f"T2026_{layer}"
        db = sqlite3.connect(f"file:{directory / file}?mode=ro", uri=True)
        kind_field = "地级类" if layer == "prefecture" else "县级类"
        for province, name, code, kind, blob in db.execute(
            f"SELECT 省级码,地名,区划码,{kind_field},geom FROM {table}"
        ):
            if province in {"710000", "810000", "820000"} or (province in MUNICIPALITIES) != (
                layer == "county"
            ):
                continue
            envelope = (blob[3] >> 1) & 7
            geom = shp.from_wkb(blob[8 + (0, 32, 48, 48, 64)[envelope] :])
            level = "district" if layer == "county" else "direct-county" if kind == "不统计" else "city"
            provinces[province].append(
                (code, name, level, kind if kind != "不统计" else "省直管县级单位", [], geom)
            )
            sources[province] = source(CTA_CREDIT, CTA, "CC BY 4.0", CTA_LICENSE, "2025-12-31", [file])
        db.close()
    return provinces, sources


def sar_taiwan(directory, provinces, sources):
    for province, filename, namekey, codekey, level, kind in [
        ("810000", "hong-kong.json", "地區", "地區號碼", "district", "地方行政区"),
        ("710000", "taiwan.geojson", "name", "code", "county-city", "县市"),
    ]:
        features = json.loads((directory / filename).read_text(encoding="utf-8-sig"))["features"]
        originals = [f["properties"][namekey] for f in features]
        names = subprocess.check_output(
            ["uconv", "-x", "Traditional-Simplified"], text=True, input="\n".join(originals)
        ).splitlines()
        for f, name, original in zip(features, names, originals, strict=True):
            code = f["properties"][codekey]
            provinces[province].append(
                (code, name, level, kind, [original], shp.from_geojson(json.dumps(f["geometry"])))
            )
    sources["810000"] = source(
        "© 香港特别行政区政府民政事务总署，DATA.GOV.HK",
        "https://www.had.gov.hk/psi/hong-kong-administrative-boundaries/hksar_18_district_boundary.json",
        "DATA.GOV.HK 使用条款",
        "https://data.gov.hk/en/terms-and-conditions",
        "2026-11-03 取得",
        ["hong-kong.json"],
    )
    sources["710000"] = source(
        "内政部国土测绘中心，直辖市、县市界线。GeoJSON 转换由 plotdb/pdmaptw 提供",
        "https://data.gov.tw/dataset/7442",
        "政府资料开放授权条款第 1 版",
        "https://data.gov.tw/license",
        "2025-03-18",
        ["taiwan.geojson"],
    )
    sources["710000"]["download"] = (
        "https://github.com/plotdb/pdmaptw/releases/download/v2.4.0/county-2025-03-18.geojson"
    )
    # The Geofabrik extract clips some outer ways of Carmo. Its complete relation v15 is pinned separately.
    ids = {5758865, 5758866, 5758867, 9506156, 9506168, 12107627, 12107628, 12107629}
    features = {}
    factory = osmium.geom.GeoJSONFactory()
    for file in ("macau.osm.pbf", "carmo.osm"):
        for area in osmium.FileProcessor(str(directory / file)).with_areas():
            if not area.is_area() or area.from_way() or area.orig_id() not in ids:
                continue
            rid = area.orig_id()
            level, kind = ("area", "填海区") if rid == 5758867 else ("parish", "堂区")
            names = [area.tags[k] for k in ("name:zh-Hant", "name:pt") if k in area.tags]
            features[rid] = (
                str(rid),
                area.tags["name:zh-Hans"],
                level,
                kind,
                names,
                shp.from_geojson(factory.create_multipolygon(area)),
            )
    if set(features) != ids:
        raise ValueError("incomplete Macau relations")
    provinces["820000"] = list(features.values())
    sources["820000"] = source(
        "© OpenStreetMap contributors，Geofabrik 澳门提取包，派生数据库按 ODbL 1.0 提供",
        "https://download.geofabrik.de/asia/china/macau.html",
        "ODbL 1.0",
        "https://opendatacommons.org/licenses/odbl/1-0/",
        "2026-11-02",
        ["macau.osm.pbf", "carmo.osm"],
    )
    sources["820000"]["relationSupplement"] = "https://api.openstreetmap.org/api/0.6/relation/5758865/full"


def short_names(name):
    short = re.sub(r"(自治区|特别行政区|自治州|地区|自治县|市|县|区|盟|縣|區)$", "", name)
    if name.endswith("自治州"):
        prefixes = [n for n in AUTONOMOUS if name.startswith(n)]
        extra = {"巴音郭楞": "巴州", "博尔塔拉": "博州", "克孜勒苏": "克州"}
        return {short, *prefixes, *(n + "州" for n in prefixes), *(extra[n] for n in prefixes if n in extra)}
    return {short}


def export_pack(target, province, name, units, provenance):
    units = sorted(units)
    codes = [row[0] for row in units]
    if len(set(codes)) != len(codes):
        raise ValueError(f"duplicate source code in {name}")
    raw = []
    for _, name_in_source, _, _, _, original in units:
        shape = (
            original
            if original.is_valid
            else shp.make_valid(original, method="structure", keep_collapsed=False)
        )
        if not shape.is_valid or shape.geom_type not in ("Polygon", "MultiPolygon") or shape.is_empty:
            raise ValueError(f"unusable source geometry: {name_in_source}")
        if abs(original.area - shape.area) > original.area * 0.001:
            raise ValueError(f"material change repairing {name_in_source}")
        raw.append(shape)
    bounds = shp.total_bounds(raw)
    tolerance = min(0.007, max(bounds[2] - bounds[0], bounds[3] - bounds[1]) / 1000)
    # Simplify shared edges together. Keep small components and retry more finely if an area changes materially.
    # Near-coincident unmatched edges must stay in place on either side of a seam.
    simplify_exterior = bool(shp.coverage_is_valid(raw))
    for attempt in range(8):
        simplified = shp.coverage_simplify(raw, tolerance, simplify_boundary=simplify_exterior)
        shapes = shp.set_precision(simplified, 0.000001)
        if all(
            g.is_valid
            and g.geom_type in ("Polygon", "MultiPolygon")
            and not g.is_empty
            and abs(g.area - original.area) <= original.area * 0.015
            for g, original in zip(shapes, raw)
        ):
            break
        tolerance /= 2
    else:
        raise ValueError(f"failed geometry QA for {name}")
    levels = {r[2] for r in units}
    scope_level = (
        "city-and-direct-county"
        if "direct-county" in levels
        else "parish-and-area"
        if "parish" in levels
        else units[0][2]
    )
    system = {"710000": "TW-COUNTYCODE", "810000": "HK-district-letter", "820000": "OSM-relation"}.get(
        province, ADCODE
    )
    scope = {"country": "中国", "province": name, "provinceCode": province, "level": scope_level}
    lookup = defaultdict(set)
    for code, unit, _, _, aliases, _ in units:
        for alias in {unit, *aliases, *(a.replace("臺", "台") for a in aliases)}:
            for key in {alias, *short_names(alias)}:
                if key:
                    lookup[key].add(code)
    unique = {key: next(iter(refs)) for key, refs in sorted(lookup.items()) if len(refs) == 1}
    cities, features = [], []
    for (code, unit, level, kind, _, _), geo in zip(units, shapes):
        if unique.get(unit) != code:
            raise ValueError(f"ambiguous official unit name {unit}")
        cities.append(
            {"code": code, "name": unit, "aliases": [k for k, v in unique.items() if v == code and k != unit]}
        )
        attrs = {
            "adcode": int(code) if system == ADCODE else code,
            "name": unit,
            "level": level,
            "unitType": kind,
            "parent": {"adcode": int(province)},
            "center": list(geo.representative_point().coords[0]),
            "centroid": list(geo.centroid.coords[0]),
        }
        features.append({"type": "Feature", "properties": attrs, "geometry": json.loads(shp.to_geojson(geo))})
    legacy = {"330000": "zhejiang", "440000": "guangdong"}.get(province)
    boundary = f"{legacy}-{province}-city.geojson" if legacy else f"{province}-units.geojson"
    mapping = f"{legacy}-city-codes.json" if legacy else f"{province}-units.json"
    path = target / "boundaries" / boundary
    credit = {k: provenance[k] for k in ("attribution", "url", "license", "licenseUrl", "snapshot")}
    write_json(path, {"type": "FeatureCollection", "source": credit, "features": features}, compact=True)
    meta = dict(
        provenance,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        modification="按省拆分，拓扑简化及坐标取整，保留原始区域标识",
    )
    write_json(
        target / "administrative-codes" / mapping,
        {
            "schemaVersion": 1,
            "scope": dict(scope, codeSystem=system),
            "source": meta,
            "boundaryResource": "../boundaries/" + boundary,
            "cities": cities,
            "cityNameToCode": unique,
        },
    )
    rid = f"cn-{province}-{scope_level}"
    manifest = f"cn/{province}/manifest.json"
    write_json(
        target / "regions" / manifest,
        {
            "schemaVersion": 1,
            "resourceId": rid,
            "scope": scope,
            "codeSystem": system,
            "cityCodeMapping": "../../../administrative-codes/" + mapping,
            "boundaryResource": "../../../boundaries/" + boundary,
            "boundaryFormat": "geojson",
            "source": meta,
        },
    )
    return {
        "id": rid,
        "province": name,
        "provinceCode": province,
        "level": scope_level,
        "codeSystem": system,
        "manifest": manifest,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--out", required=True, type=Path, help="new resources directory")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output directory must be new")
    directory = args.input_dir
    for file, digest in PINNED.items():
        raw = (directory / file).read_bytes()
        actual = (hashlib.md5(raw) if len(digest) == 32 else hashlib.sha256(raw)).hexdigest()
        if actual != digest:
            raise ValueError(f"{file}: source checksum mismatch")
    provinces, sources = mainland(directory)
    sar_taiwan(directory, provinces, sources)
    from province_map import basemap, short_name

    names = {s.get("data-code"): s.get("data-name") for s in basemap() if s.get("data-code")}
    if set(provinces) != set(names):
        raise ValueError("incomplete national coverage")
    with TemporaryDirectory(dir=args.out.parent) as work:
        target = Path(work) / "resources"
        shutil.copytree(RESOURCES, target)
        registry_path = target / "regions/registry.json"
        registry = json.loads(registry_path.read_text())
        registry["regions"] = [
            export_pack(target, c, n, provinces[c], sources[c]) for c, n in sorted(names.items())
        ]
        registry["provinceNameToCode"] = {k: c for c, n in sorted(names.items()) for k in (n, short_name(n))}
        registry["provinceNameToCode"].update(
            {
                "臺灣": "710000",
                "臺灣省": "710000",
                "台灣": "710000",
                "台灣省": "710000",
                "澳門": "820000",
                "澳門特別行政區": "820000",
                "香港特別行政區": "810000",
            }
        )
        write_json(registry_path, registry)
        target.rename(args.out)


if __name__ == "__main__":
    main()
