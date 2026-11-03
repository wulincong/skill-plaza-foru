"""Offline province geometry and region identities for the China statistical map."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

REGIONS = Path(__file__).resolve().parents[1] / "resources/regions"
SOURCE = "Maitian MaiLin (2024), CC0 1.0"


@lru_cache
def basemap():
    registry = json.loads((REGIONS / "registry.json").read_text())
    manifest_path = REGIONS / registry["nationalProvinceMap"]
    manifest = json.loads(manifest_path.read_text())
    data = (manifest_path.parent / manifest["boundaryResource"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != manifest["sha256"]:
        raise ValueError("province boundary checksum mismatch")
    root = ET.fromstring(data)
    for el in root.iter():
        el.tag = el.tag.rsplit("}", 1)[-1]
    return root


def short_name(name):
    return re.sub(r"(壮族自治区|回族自治区|维吾尔自治区|自治区|特别行政区|省|市)$", "", name)


@lru_cache
def aliases():
    result = {}
    for shape in basemap():
        code = shape.get("data-code")
        if code:
            name = shape.get("data-name")
            result.update({code: code, name: code, short_name(name): code})
    return result


def province_code(key):
    code = aliases().get(str(key).strip())
    if code is None:
        raise ValueError(f"unknown provincial region {key!r}; use a six-digit provincial code or name")
    return code


def province_rows(rows):
    regions = {el.get("data-code"): el.get("data-name") for el in basemap() if el.get("data-code")}
    values = {}
    for row in rows:
        code = province_code(row["region"])
        if code in values:
            raise ValueError(f"duplicate province {code} ({regions[code]})")
        values[code] = row["value"]
    return [{"code": code, "region": regions[code], "value": values.get(code)} for code in sorted(regions)]
