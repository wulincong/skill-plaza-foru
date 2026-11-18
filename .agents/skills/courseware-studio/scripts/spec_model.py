"""courseware-spec/1 共享模型：类型常量、校验与主题。

build_pptx.py / build_preview.py / tests 共用；规则与 references/spec-schema.md
一一对应，改动时同步更新该文档。
"""
from __future__ import annotations

import re
from pathlib import Path

SPEC_VERSION = "courseware-spec/1"

SLIDE_TYPES = (
    "cover", "agenda", "objectives", "intro", "concept", "diagram",
    "procedure", "safety-warning", "quiz", "rubric", "summary",
)
# 封面与目录不承载课程事实，不强制逐页出处；附录页由构建器自动生成
SOURCES_EXEMPT = {"cover", "agenda"}

BLOCK_KINDS = (
    "bullets", "paragraph", "two-col", "steps", "table", "image",
    "callout", "gap",
)
MATERIAL_KINDS = (
    "textbook", "lesson-plan", "training-guide", "standard", "kb-doc",
    "image", "other",
)
RESOURCE_KINDS = ("diagram", "figure", "case", "image", "table")
CONFIRM_ASPECTS = ("safety-order", "coverage", "accuracy")

THEMES = {
    "clean-blue": {
        "bg": "F4F7FB", "panel": "FFFFFF", "ink": "1F2D3D", "muted": "5B6B7F",
        "accent": "1D5FBF", "accentSoft": "E3EDF9", "warn": "B3541E",
        "warnSoft": "FBEFE4", "ok": "2E7D4F", "line": "D5DEE9",
    },
    "warm-orange": {
        "bg": "FBF6F0", "panel": "FFFFFF", "ink": "3A2A1D", "muted": "7A6A58",
        "accent": "C25E1A", "accentSoft": "F8E9DC", "warn": "A83A1A",
        "warnSoft": "F9E6DF", "ok": "2E7D4F", "line": "E6D9CB",
    },
    "ink-green": {
        "bg": "F3F6F3", "panel": "FFFFFF", "ink": "22302A", "muted": "5C6B62",
        "accent": "2F6B4F", "accentSoft": "E2EEE7", "warn": "A8561A",
        "warnSoft": "F8ECE0", "ok": "2E7D4F", "line": "D6DFD8",
    },
    "print-gray": {
        "bg": "FFFFFF", "panel": "F7F7F7", "ink": "202020", "muted": "595959",
        "accent": "404040", "accentSoft": "ECECEC", "warn": "5A3A20",
        "warnSoft": "F0EBE4", "ok": "3A5A40", "line": "CCCCCC",
    },
}


class SpecError(ValueError):
    """spec 不符合 courseware-spec/1；message 面向构建者（模型）可读。"""


def _req(container: dict, key: str, label: str | None = None):
    """取 container[key]；缺失或为 null 时报「xx 缺失」。"""
    value = container.get(key)
    if value is None:
        raise SpecError(f"{label or key} 缺失")
    return value


def _str(value, label, *, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise SpecError(f"{label} 必须是非空字符串")
    return value


def _list(value, label):
    if not isinstance(value, list):
        raise SpecError(f"{label} 必须是数组")
    return value


def _dict(value, label):
    if not isinstance(value, dict):
        raise SpecError(f"{label} 必须是对象")
    return value


def _number(value, label, *, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SpecError(f"{label} 必须是数字")
    if minimum is not None and value < minimum:
        raise SpecError(f"{label} 不能小于 {minimum}")
    return value


def load_spec(data, workspace: Path | None = None):
    """校验并原样返回 spec；workspace 提供时额外核对文件引用存在。"""
    root = _dict(data, "spec")
    if root.get("version") != SPEC_VERSION:
        raise SpecError(f"version 必须是 {SPEC_VERSION}")
    meta = _dict(_req(root, "meta"), "meta")
    _str(_req(meta, "title"), "meta.title")
    _number(_req(meta, "hours"), "meta.hours", minimum=0.5)
    style = meta.get("style") or "clean-blue"
    if style not in THEMES:
        raise SpecError(f"meta.style 只支持 {sorted(THEMES)}")
    meta.setdefault("final", False)
    if not isinstance(meta["final"], bool):
        raise SpecError("meta.final 必须是布尔值")

    standards = _list(root.get("standards", []), "standards")
    standard_ids = set()
    for idx, item in enumerate(standards):
        entry = _dict(item, f"standards[{idx}]")
        sid = _str(_req(entry, "id"), f"standards[{idx}].id")
        if sid in standard_ids:
            raise SpecError(f"课标条目 id 重复：{sid}")
        standard_ids.add(sid)
        _str(_req(entry, "title"), f"standards[{sid}].title")

    materials = _list(_req(root, "materials"), "materials")
    material_ids = set()
    for idx, item in enumerate(materials):
        entry = _dict(item, f"materials[{idx}]")
        mid = _str(_req(entry, "id"), f"materials[{idx}].id")
        if mid in material_ids:
            raise SpecError(f"材料 id 重复：{mid}")
        material_ids.add(mid)
        _str(_req(entry, "name"), f"materials[{mid}].name")
        if entry.get("kind") not in MATERIAL_KINDS:
            raise SpecError(f"materials[{mid}].kind 只支持 {list(MATERIAL_KINDS)}")

    slides = _list(_req(root, "slides"), "slides")
    if not slides:
        raise SpecError("slides 不能为空")
    if _dict(slides[0], "slides[0]").get("type") != "cover":
        raise SpecError("第一页必须是 cover")
    slide_types_seen = set()
    for idx, item in enumerate(slides):
        slide = _dict(item, f"slides[{idx}]")
        stype = slide.get("type")
        if stype not in SLIDE_TYPES:
            raise SpecError(f"slides[{idx}].type 只支持 {list(SLIDE_TYPES)}")
        slide_types_seen.add(stype)
        _str(_req(slide, "title"), f"slides[{idx}]({stype}).title")
        if stype == "cover" and slide.get("blocks"):
            raise SpecError("封面页不接受 blocks；课程、单元与课时信息写在 meta，由封面版式渲染")
        _validate_blocks(slide.get("blocks", []), f"slides[{idx}]", workspace)
        for kp in _list(slide.get("knowledgePoints", []), f"slides[{idx}].knowledgePoints"):
            point = _dict(kp, f"slides[{idx}].knowledgePoints[]")
            _str(_req(point, "name"), f"slides[{idx}].knowledgePoints[].name")
            if point.get("extension"):
                continue
            if point.get("standardId") not in standard_ids:
                raise SpecError(
                    f"slides[{idx}] 知识点「{point.get('name')}」的 standardId 未在 standards 中登记；"
                    "无对应课标条目的内容应标 extension: true"
                )
        for src in _list(slide.get("sources", []), f"slides[{idx}].sources"):
            entry = _dict(src, f"slides[{idx}].sources[]")
            if entry.get("materialId") not in material_ids:
                raise SpecError(f"slides[{idx}].sources[].materialId 未在 materials 中登记")
        if stype not in SOURCES_EXEMPT and not slide.get("sources"):
            raise SpecError(f"slides[{idx}]({stype}) 是事实性页面，必须提供至少一条 sources 出处")
        if stype == "safety-warning":
            safety = _dict(slide.get("safety") or {}, f"slides[{idx}].safety")
            if not safety.get("requiresConfirmation"):
                raise SpecError(f"slides[{idx}] 是 safety-warning，safety.requiresConfirmation 必须为 true")
            if not _list(safety.get("items", []), f"slides[{idx}].safety.items"):
                raise SpecError(f"slides[{idx}].safety.items 必须逐条列出")
        elif slide.get("safety"):
            raise SpecError(f"slides[{idx}] 非安全页不应携带 safety 字段")

    if "safety-warning" in slide_types_seen and not root.get("pendingConfirmations"):
        raise SpecError("包含实训安全页时必须逐条给出 pendingConfirmations")

    for idx, item in enumerate(_list(root.get("pendingConfirmations", []), "pendingConfirmations")):
        entry = _dict(item, f"pendingConfirmations[{idx}]")
        cid = _str(_req(entry, "id"), f"pendingConfirmations[{idx}].id")
        _str(_req(entry, "text"), f"pendingConfirmations[{cid}].text")
        if entry.get("aspect") not in CONFIRM_ASPECTS:
            raise SpecError(f"pendingConfirmations[{cid}].aspect 只支持 {list(CONFIRM_ASPECTS)}")
        for sidx in _list(entry.get("relatedSlides", []), f"pendingConfirmations[{cid}].relatedSlides"):
            if not isinstance(sidx, int) or not (0 <= sidx < len(slides)):
                raise SpecError(f"pendingConfirmations[{cid}].relatedSlides 指向不存在的页 {sidx}")

    confirmed = set()
    for idx, item in enumerate(_list(root.get("confirmations", []), "confirmations")):
        entry = _dict(item, f"confirmations[{idx}]")
        confirmed.add(_str(_req(entry, "id"), f"confirmations[{idx}].id"))
        if entry.get("decision") != "confirmed":
            raise SpecError(f"confirmations[{idx}].decision 必须是 confirmed")
    if meta["final"]:
        pending = {item["id"] for item in root.get("pendingConfirmations", [])}
        missing = pending - confirmed
        if missing:
            raise SpecError(
                f"meta.final 为定稿，但待确认项 {sorted(missing)} 尚无教师确认记录；"
                "未获确认不得定稿导出"
            )

    for idx, item in enumerate(_list(root.get("copyright", []), "copyright")):
        entry = _dict(item, f"copyright[{idx}]")
        if entry.get("materialId") not in material_ids:
            raise SpecError(f"copyright[{idx}].materialId 未在 materials 中登记")
        _str(_req(entry, "content"), f"copyright[{idx}].content")
        _str(_req(entry, "license"), f"copyright[{idx}].license")
        if entry.get("status") not in ("confirmed", "pending"):
            raise SpecError(f"copyright[{idx}].status 只支持 confirmed / pending")

    for idx, item in enumerate(_list(root.get("resources", []), "resources")):
        entry = _dict(item, f"resources[{idx}]")
        _str(_req(entry, "name"), f"resources[{idx}].name")
        if entry.get("kind") not in RESOURCE_KINDS:
            raise SpecError(f"resources[{idx}].kind 只支持 {list(RESOURCE_KINDS)}")
        _str(_req(entry, "source"), f"resources[{idx}].source")

    _check_workspace_files(root, workspace)
    return root


def _validate_blocks(blocks, label, workspace):
    _list(blocks, f"{label}.blocks")
    for bidx, item in enumerate(blocks):
        block = _dict(item, f"{label}.blocks[{bidx}]")
        kind = block.get("kind")
        if kind not in BLOCK_KINDS:
            raise SpecError(f"{label}.blocks[{bidx}].kind 只支持 {list(BLOCK_KINDS)}")
        if kind == "bullets":
            items = _list(_req(block, "items"), f"{label}.blocks[{bidx}].items")
            if not items:
                raise SpecError(f"{label}.blocks[{bidx}].items 不能为空")
            for tidx, text in enumerate(items):
                _str(text, f"{label}.blocks[{bidx}].items[{tidx}]")
        elif kind == "paragraph":
            _str(_req(block, "text"), f"{label}.blocks[{bidx}].text")
        elif kind == "two-col":
            for side in ("left", "right"):
                col = _dict(_req(block, side), f"{label}.blocks[{bidx}].{side}")
                _str(_req(col, "title"), f"{label}.blocks[{bidx}].{side}.title")
                for tidx, text in enumerate(_list(col.get("items", []), f"{label}.blocks[{bidx}].{side}.items")):
                    _str(text, f"{label}.blocks[{bidx}].{side}.items[{tidx}]")
        elif kind == "steps":
            items = _list(_req(block, "items"), f"{label}.blocks[{bidx}].items")
            if len(items) < 2:
                raise SpecError(f"{label}.blocks[{bidx}] 步骤至少两步")
            for tidx, text in enumerate(items):
                _str(text, f"{label}.blocks[{bidx}].items[{tidx}]")
        elif kind == "table":
            header = _list(_req(block, "header"), f"{label}.blocks[{bidx}].header")
            rows = _list(_req(block, "rows"), f"{label}.blocks[{bidx}].rows")
            if not header or not rows:
                raise SpecError(f"{label}.blocks[{bidx}] 表格需要表头和至少一行")
            for ridx, row in enumerate(rows):
                if not isinstance(row, list) or len(row) != len(header):
                    raise SpecError(
                        f"{label}.blocks[{bidx}].rows[{ridx}] 列数（{len(row) if isinstance(row, list) else '?'}）"
                        f"与表头（{len(header)}）不一致"
                    )
        elif kind == "image":
            _str(_req(block, "path"), f"{label}.blocks[{bidx}].path")
            _str(_req(block, "caption"), f"{label}.blocks[{bidx}].caption")
        elif kind == "callout":
            if block.get("tone") not in ("warn", "info"):
                raise SpecError(f"{label}.blocks[{bidx}].tone 只支持 warn / info")
            _str(_req(block, "title"), f"{label}.blocks[{bidx}].title")
            _str(_req(block, "text"), f"{label}.blocks[{bidx}].text")
        elif kind == "gap":
            _str(_req(block, "text"), f"{label}.blocks[{bidx}].text")


def _check_workspace_files(root, workspace: Path | None):
    """workspace 提供时，核对 image.path 与材料 file 均存在（相对会话根）。"""
    if workspace is None:
        return
    for idx, slide in enumerate(root["slides"]):
        for bidx, block in enumerate(slide.get("blocks", [])):
            if block.get("kind") == "image":
                target = (workspace / block["path"]).resolve()
                if not target.is_relative_to(workspace.resolve()) or not target.is_file():
                    raise SpecError(
                        f"slides[{idx}].blocks[{bidx}].path 指向的图片不存在或越界：{block['path']}"
                    )
    for idx, material in enumerate(root["materials"]):
        file = material.get("file")
        if file:
            target = (workspace / file).resolve()
            if not target.is_relative_to(workspace.resolve()) or not target.is_file():
                raise SpecError(f"materials[{idx}].file 不存在或越界：{file}")


def source_label(spec, source) -> str:
    """把一条 sources 渲染成页脚短标注，如「教材 p.58–60」。"""
    materials = {item["id"]: item for item in spec["materials"]}
    material = materials.get(source.get("materialId"), {})
    name = material.get("name", source.get("materialId"))
    name = re.sub(r"^《|》$", "", str(name))
    if len(name) > 18:
        name = name[:17] + "…"
    pages = source.get("pages") or ""
    return f"{name}{(' ' + pages) if pages else ''}".strip()


def slide_source_line(spec, slide) -> str:
    labels = [source_label(spec, src) for src in slide.get("sources", [])]
    if not labels:
        return ""
    text = "；".join(labels)
    return text if len(text) <= 60 else text[:57] + "…"


def knowledge_line(spec, slide) -> str:
    """页内知识点/课标标注：'S1·工具坐标标定 ／ 拓展：现场技巧'。"""
    bits = []
    for point in slide.get("knowledgePoints", []):
        if point.get("extension"):
            bits.append(f"拓展：{point['name']}")
        else:
            bits.append(f"{point.get('standardId', '')}·{point['name']}".lstrip("·"))
    return " ／ ".join(bits)


def theme_of(spec) -> dict:
    return THEMES[(spec["meta"].get("style") or "clean-blue")]


def confirmation_state(spec) -> dict:
    confirmed = {item["id"] for item in spec.get("confirmations", [])}
    return {
        item["id"]: ("已确认" if item["id"] in confirmed else "待确认")
        for item in spec.get("pendingConfirmations", [])
    }


def appendix_pages(spec) -> list:
    """由 spec 派生附录页（材料与出处、版权授权、待确认与资源入库）。

    附录页由构建器自动追加，模型不在 slides 里手写，保证清单与 spec 一致。
    返回 [(标题, blocks)]，块类型复用 courseware-spec/1 的 block 集合。
    """
    materials = {item["id"]: item for item in spec["materials"]}
    pages = []

    rows = []
    for idx, slide in enumerate(spec["slides"], start=1):
        if slide["type"] in SOURCES_EXEMPT:
            continue
        labels = [source_label(spec, src) for src in slide.get("sources", [])]
        rows.append([str(idx), slide["title"][:18], "；".join(labels) or "—"])
    if rows:
        pages.append(("材料与逐页出处总表", [
            {"kind": "table", "header": ["页", "页面", "出处"], "rows": rows},
        ]))

    material_rows = [
        [item["name"][:20],
         {"textbook": "教材", "lesson-plan": "教案", "training-guide": "实训指导书",
          "standard": "课程标准", "kb-doc": "知识库文档", "image": "图片素材",
          "other": "其他"}.get(item["kind"], item["kind"]),
         item.get("pages") or "—"]
        for item in spec["materials"]
    ]
    copyright_rows = [
        [entry["content"][:22], materials.get(entry.get("materialId"), {}).get("name", "")[:14],
         entry["license"], "已确认" if entry.get("status") == "confirmed" else "待教师确认"]
        for entry in spec.get("copyright", [])
    ]
    if material_rows or copyright_rows:
        blocks = []
        if material_rows:
            blocks.append({"kind": "paragraph", "text": "本课件允许使用的材料范围："})
            blocks.append({"kind": "table", "header": ["材料", "类型", "范围/页码"], "rows": material_rows})
        if copyright_rows:
            blocks.append({"kind": "paragraph", "text": "素材来源与授权状态："})
            blocks.append({"kind": "table", "header": ["素材内容", "来源材料", "授权说明", "状态"], "rows": copyright_rows})
        pages.append(("版权与素材授权说明", blocks))

    state = confirmation_state(spec)
    confirm_rows = [
        [item["text"][:34], state.get(item["id"], "待确认")] for item in spec.get("pendingConfirmations", [])
    ]
    resource_rows = [
        [item["name"][:20], item["kind"], item["source"][:24]] for item in spec.get("resources", [])
    ]
    if confirm_rows or resource_rows:
        blocks = []
        if confirm_rows:
            blocks.append({"kind": "paragraph", "text": "教师待确认清单："})
            blocks.append({"kind": "table", "header": ["事项", "状态"], "rows": confirm_rows})
        if resource_rows:
            blocks.append({"kind": "paragraph", "text": "课程资源入库清单："})
            blocks.append({"kind": "table", "header": ["资源", "类型", "来源"], "rows": resource_rows})
        pages.append(("教师确认与资源入库", blocks))
    return pages
