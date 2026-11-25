"""courseware-spec/1 -> 可编辑 PPTX（标准库 OOXML 写入器）。

只用 Python 标准库 + Pillow（读图片尺寸/规整格式），不引入 python-pptx：
课件在低权沙箱内构建，零新增系统组件。输出的包结构为 ECMA-376 最小集
（1 母版 + 2 版式 + 主题），幻灯片由普通形状/文本框/表格/图片组成，
教师可在 PowerPoint / WPS 中直接编辑。
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec_model import (  # noqa: E402
    SpecError, appendix_pages, load_spec, slide_source_line, theme_of,
)

try:
    from PIL import Image
except ImportError:  # pragma: no cover - 沙箱与开发机均已内置 Pillow
    Image = None

SLIDE_W, SLIDE_H = 12192000, 6858000  # 16:9
MARGIN = 502920
CONTENT_X, CONTENT_W = MARGIN, SLIDE_W - 2 * MARGIN
TITLE_Y, TITLE_H = 292608, 640080
RULE_Y = 990600
CONTENT_Y = 1120140
FOOTER_Y = 6400800
PT = 12700  # 1pt 对应 EMU
FONT = "微软雅黑"

TYPE_LABEL = {
    "objectives": "学习目标", "intro": "任务导入", "concept": "知识讲解",
    "diagram": "图解", "procedure": "实训演示", "safety-warning": "安全警示",
    "quiz": "课堂测验", "rubric": "考核评分", "summary": "课堂小结",
    "appendix": "附录",
}


def esc(text: str) -> str:
    return (
        str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def color(value: str) -> str:
    return value.lstrip("#").upper()


def _fonts() -> str:
    return f'<a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/>'


def run(text, sz, *, bold=False, color_str="1F2D3D", spacing=None):
    spc = f' spc="{spacing}"' if spacing else ""
    return (
        f'<a:r><a:rPr lang="zh-CN" sz="{int(sz)}"{" b=\"1\"" if bold else ""}{spc} dirty="0">'
        f'<a:solidFill><a:srgbClr val="{color(color_str)}"/></a:solidFill>{_fonts()}</a:rPr>'
        f"<a:t>{esc(text)}</a:t></a:r>"
    )


def paragraph(text="", sz=1600, *, bold=False, color_str="1F2D3D", bullet=None,
              bullet_color=None, align="l", space_before=0, line=150):
    ppr_children = []
    if bullet == "char":
        ppr_children.append(
            f'<a:buClr><a:srgbClr val="{color(bullet_color or "5B6B7F")}"/></a:buClr>'
            '<a:buFont typeface="Arial" pitchFamily="34" charset="0"/><a:buChar char="•"/>'
        )
    elif bullet == "num":
        ppr_children.append(
            f'<a:buClr><a:srgbClr val="{color(bullet_color or "1D5FBF")}"/></a:buClr>'
            '<a:buFont typeface="Arial" pitchFamily="34" charset="0"/>'
            '<a:buAutoNum type="arabicPeriod"/>'
        )
    elif bullet is None:
        ppr_children.append("<a:noBullet/>")
    marL = ' marL="228600" indent="-228600"' if bullet else ""
    spc = f'<a:spcBef><a:spcPts val="{int(space_before)}"/></a:spcBef>' if space_before else ""
    ln = f'<a:lnSpc><a:spcPct val="{int(line * 1000)}"/></a:lnSpc>' if line else ""
    body = run(text, sz, bold=bold, color_str=color_str) if text else ""
    return (
        f'<a:p><a:pPr algn="{align}"{marL}>{ln}{spc}{"".join(ppr_children)}</a:pPr>'
        f"{body}</a:p>"
    )


def textbox(shape_id, name, x, y, cx, cy, paragraphs, *, anchor="t", fill=None,
            line_color=None, line_w=12700, dash=None, radius=None, geom="rect"):
    fill_xml = (
        f'<a:solidFill><a:srgbClr val="{color(fill)}"/></a:solidFill>' if fill else "<a:noFill/>"
    )
    ln = "<a:ln><a:noFill/></a:ln>"
    if line_color:
        dash_xml = f'<a:prstDash val="{dash}"/>' if dash else ""
        ln = (
            f'<a:ln w="{line_w}" cap="flat"><a:solidFill><a:srgbClr val="{color(line_color)}"/>'
            f"</a:solidFill>{dash_xml}</a:ln>"
        )
    av = f'<a:avLst><a:gd name="adj" fmla="val {int(radius)}"/></a:avLst>' if radius is not None else "<a:avLst/>"
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{esc(name)}"/>'
        '<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr>'
        f'<a:xfrm><a:off x="{int(x)}" y="{int(y)}"/><a:ext cx="{int(cx)}" cy="{int(cy)}"/></a:xfrm>'
        f'<a:prstGeom prst="{geom}">{av}</a:prstGeom>{fill_xml}{ln}<a:noEffectLst/></p:spPr>'
        f'<p:txBody><a:bodyPr wrap="square" lIns="91440" tIns="45720" rIns="91440" bIns="45720" '
        f'anchor="{anchor}"/><a:lstStyle/>{"".join(paragraphs)}</p:txBody></p:sp>'
    )


def rect(shape_id, name, x, y, cx, cy, fill, *, geom="rect", radius=None, line_color=None):
    av = f'<a:avLst><a:gd name="adj" fmla="val {int(radius)}"/></a:avLst>' if radius is not None else "<a:avLst/>"
    ln = (
        f'<a:ln><a:solidFill><a:srgbClr val="{color(line_color)}"/></a:solidFill></a:ln>'
        if line_color else "<a:ln><a:noFill/></a:ln>"
    )
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{esc(name)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{int(x)}" y="{int(y)}"/><a:ext cx="{int(cx)}" cy="{int(cy)}"/></a:xfrm>'
        f'<a:prstGeom prst="{geom}">{av}</a:prstGeom>'
        f'<a:solidFill><a:srgbClr val="{color(fill)}"/></a:solidFill>{ln}<a:noEffectLst/></p:spPr>'
        "<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>"
    )


def picture(shape_id, name, x, y, cx, cy, rid):
    return (
        f'<p:pic><p:nvPicPr><p:cNvPr id="{shape_id}" name="{esc(name)}"/>'
        '<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
        f'<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
        f'<p:spPr><a:xfrm><a:off x="{int(x)}" y="{int(y)}"/><a:ext cx="{int(cx)}" cy="{int(cy)}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
    )


def table_frame(shape_id, name, x, y, cx, cy, header, rows, theme):
    weights = []
    for col in range(len(header)):
        longest = max(
            [len(str(header[col]))] + [len(str(row[col])) for row in rows]
        )
        weights.append(max(longest, 4))
    total = sum(weights)
    grid = "".join(
        f'<a:gridCol w="{int(cx * w / total)}"/>' for w in weights
    )
    border = (
        '<a:lnL w="9525" cap="flat"><a:solidFill><a:srgbClr val="D5DEE9"/></a:solidFill></a:lnL>'
        '<a:lnR w="9525" cap="flat"><a:solidFill><a:srgbClr val="D5DEE9"/></a:solidFill></a:lnR>'
        '<a:lnT w="9525" cap="flat"><a:solidFill><a:srgbClr val="D5DEE9"/></a:solidFill></a:lnT>'
        '<a:lnB w="9525" cap="flat"><a:solidFill><a:srgbClr val="D5DEE9"/></a:solidFill></a:lnB>'
    )
    header_cells = "".join(
        '<a:tc><a:txBody><a:bodyPr anchor="ctr"/><a:lstStyle/>'
        + paragraph(str(cell), 1300, bold=True, color_str="FFFFFF", align="ctr", line=120)
        + '</a:txBody><a:tcPr marL="91440" marR="91440" anchor="ctr">'
        f'<a:solidFill><a:srgbClr val="{color(theme["accent"])}"/></a:solidFill>{border}</a:tcPr></a:tc>'
        for cell in header
    )
    body_rows = []
    for ridx, row in enumerate(rows):
        fill = theme["panel"] if ridx % 2 == 0 else theme["bg"]
        cells = "".join(
            '<a:tc><a:txBody><a:bodyPr anchor="ctr"/><a:lstStyle/>'
            + paragraph(str(cell), 1200, color_str=theme["ink"], align="ctr" if len(str(cell)) <= 8 else "l", line=120)
            + '</a:txBody><a:tcPr marL="91440" marR="91440" anchor="ctr">'
            f'<a:solidFill><a:srgbClr val="{color(fill)}"/></a:solidFill>{border}</a:tcPr></a:tc>'
            for cell in row
        )
        body_rows.append(f'<a:tr h="342900">{cells}</a:tr>')
    return (
        '<p:graphicFrame><p:nvGraphicFramePr>'
        f'<p:cNvPr id="{shape_id}" name="{esc(name)}"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>'
        f'<p:xfrm><a:off x="{int(x)}" y="{int(y)}"/><a:ext cx="{int(cx)}" cy="{int(cy)}"/></p:xfrm>'
        '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">'
        f'<a:tbl><a:tblPr firstRow="1" bandRow="1"/><a:tblGrid>{grid}</a:tblGrid>'
        f'<a:tr h="370840">{header_cells}</a:tr>{"".join(body_rows)}</a:tbl>'
        "</a:graphicData></a:graphic></p:graphicFrame>"
    )


# ---------------------------------------------------------------- 布局渲染

def _bullet_metrics(items):
    longest = max(len(i) for i in items)
    if len(items) <= 5 and longest <= 48:
        return 1900
    if len(items) <= 8 and longest <= 60:
        return 1600
    return 1400


def _block_height(block, sz):
    kind = block["kind"]
    if kind == "bullets":
        return int(len(block["items"]) * sz * PT * 1.75 + 91440)
    if kind == "paragraph":
        lines = max(1, len(block["text"]) // 42 + 1)
        return int(lines * sz * PT * 1.7 + 91440)
    if kind == "two-col":
        rows = max(len(block["left"].get("items", [])), len(block["right"].get("items", [])), 1)
        return int(rows * sz * PT * 1.75 + sz * PT * 2.2)
    if kind == "steps":
        return int(len(block["items"]) * sz * PT * 1.9 + 91440)
    if kind == "table":
        return 370840 + len(block["rows"]) * 342900 + 91440
    if kind == "image":
        return 3600000
    if kind == "callout":
        return int(sz * PT * 3.6 + 182880)
    if kind == "gap":
        return int(sz * PT * 2.4 + 91440)
    return 457200


def _measure(blocks, base):
    heights, total = [], 0
    for block in blocks:
        if block["kind"] in ("bullets", "paragraph", "steps"):
            sz = _bullet_metrics(block["items"]) if block["kind"] != "paragraph" else base
            sz = min(sz, base)
        else:
            sz = base
        height = _block_height(block, sz)
        heights.append((sz, height))
        total += height + 91440
    return heights, total


def render_blocks(counter, blocks, theme, *, base=1600, media=None):
    """把内容块自上而下排进内容区；先量高再按剩余空间整体缩字号。"""
    heights, total = _measure(blocks, base)
    avail = FOOTER_Y - CONTENT_Y - 91440
    scale = 1.0
    if total > avail:
        scale = max(0.62, avail / total)
    y = CONTENT_Y
    parts = []
    for block, (sz0, height0) in zip(blocks, heights):
        sz = max(1100, int(sz0 * scale))
        height = int(height0 * scale) if block["kind"] != "image" else height0
        kind = block["kind"]
        if kind == "bullets":
            parts.append(textbox(
                next(counter), "bullets", CONTENT_X, y, CONTENT_W, height,
                [paragraph(item, sz, color_str=theme["ink"], bullet="char", bullet_color=theme["accent"])
                 for item in block["items"]],
            ))
        elif kind == "paragraph":
            parts.append(textbox(
                next(counter), "paragraph", CONTENT_X, y, CONTENT_W, height,
                [paragraph(block["text"], sz, color_str=theme["ink"], line=160)],
            ))
        elif kind == "two-col":
            gap = 228600
            col_w = (CONTENT_W - gap) // 2
            for offset, side in ((0, "left"), (col_w + gap, "right")):
                col = block[side]
                paras = [paragraph(col["title"], sz - 100, bold=True, color_str=theme["accent"], space_before=0)]
                paras += [
                    paragraph(item, sz - 200, color_str=theme["ink"], bullet="char", bullet_color=theme["muted"], space_before=400)
                    for item in col.get("items", [])
                ]
                parts.append(textbox(
                    next(counter), f"col-{side}", CONTENT_X + offset, y, col_w, height, paras,
                    fill=theme["panel"], line_color=theme["line"],
                ))
        elif kind == "steps":
            paras = [
                paragraph(item, sz, color_str=theme["ink"], bullet="num", space_before=600 if i else 0)
                for i, item in enumerate(block["items"])
            ]
            parts.append(textbox(
                next(counter), "steps", CONTENT_X, y, CONTENT_W, height, paras,
                fill=theme["panel"], line_color=theme["line"], radius=6000, geom="roundRect",
            ))
        elif kind == "table":
            parts.append(table_frame(
                next(counter), "table", CONTENT_X, y, CONTENT_W,
                min(height, FOOTER_Y - y - 91440), block["header"], block["rows"], theme,
            ))
        elif kind == "image":
            placed = _place_image(counter, block, y, media, theme)
            if placed:
                xml, height = placed
                parts.append(xml)
            else:
                parts.append(textbox(
                    next(counter), "image-missing", CONTENT_X, y, CONTENT_W, 320040,
                    [paragraph("图片缺失", sz, color_str=theme["muted"])],
                ))
        elif kind == "callout":
            tone = block.get("tone", "info")
            fill = theme["warnSoft"] if tone == "warn" else theme["accentSoft"]
            edge = theme["warn"] if tone == "warn" else theme["accent"]
            paras = [paragraph(block["title"], sz, bold=True, color_str=edge, space_before=0)]
            paras.append(paragraph(block["text"], sz - 200, color_str=theme["ink"], space_before=500, line=150))
            parts.append(textbox(
                next(counter), "callout", CONTENT_X, y, CONTENT_W, height, paras,
                fill=fill, line_color=edge, line_w=19050, radius=8000, geom="roundRect",
            ))
        elif kind == "gap":
            paras = [paragraph("待教师补充", sz, bold=True, color_str=theme["muted"], space_before=0)]
            paras.append(paragraph(block["text"], sz - 200, color_str=theme["muted"], space_before=300))
            parts.append(textbox(
                next(counter), "gap", CONTENT_X, y, CONTENT_W, height, paras,
                line_color=theme["muted"], dash="dash", radius=6000, geom="roundRect",
            ))
        y += height + 91440
    return parts


class _Media:
    """收集图片并规整为 pptx 支持的格式（webp/bmp/tiff 转 PNG）。"""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.items: list[tuple[str, bytes, str]] = []  # (name, data, ext)

    def add(self, path: str) -> tuple[str, int, int]:
        source = (self.workspace / path).resolve()
        raw = source.read_bytes()
        ext = source.suffix.lstrip(".").lower()
        width = height = 0
        if Image is not None:
            with Image.open(io.BytesIO(raw)) as img:
                width, height = img.size
                if img.format not in ("PNG", "JPEG", "GIF"):
                    buffer = io.BytesIO()
                    img.convert("RGBA" if img.mode in ("RGBA", "P", "LA") else "RGB").save(buffer, "PNG")
                    raw, ext = buffer.getvalue(), "png"
        index = len(self.items) + 1
        self.items.append((f"image{index}.{ext}", raw, ext))
        return f"rId{index + 1}", width, height


def _place_image(counter, block, y, media: _Media | None, theme):
    if media is None:
        return None
    try:
        rid, width, height = media.add(block["path"])
    except (OSError, ValueError):
        return None
    max_h = min(3400000, FOOTER_Y - y - 457200)
    max_w = int(CONTENT_W * 0.9)
    if width and height:
        ratio = min(max_w / width, max_h / height)
        cx, cy = int(width * ratio), int(height * ratio)
    else:
        cx, cy = max_w, int(max_h * 0.7)
    x = CONTENT_X + (CONTENT_W - cx) // 2
    caption = block["caption"] + ("（示意图，非设备实图）" if block.get("schematic") else "")
    parts = [picture(next(counter), block["caption"][:28], x, y, cx, cy, rid)]
    parts.append(textbox(
        next(counter), "caption", CONTENT_X, y + cy + 27432, CONTENT_W, 274936,
        [paragraph(caption, 1100, color_str=theme["muted"], align="ctr")],
    ))
    return "".join(parts), cy + 320040


def build_slide(spec, index, slide, theme, media):
    shapes = []
    counter = iter(range(2, 300))
    stype = slide["type"]
    meta = spec["meta"]
    if stype == "cover":
        shapes.append(rect(next(counter), "band", 0, 0, SLIDE_W, 1828800, theme["accent"]))
        paras = []
        eyebrow_text = " · ".join(filter(None, [meta.get("course"), meta.get("unit")]))
        if eyebrow_text:
            paras.append(paragraph(eyebrow_text, 1400, color_str="FFFFFF", space_before=0, align="l"))
        paras.append(paragraph(slide["title"], 3600, bold=True, color_str="FFFFFF", space_before=600))
        if slide.get("subtitle"):
            paras.append(paragraph(slide["subtitle"], 1600, color_str="FFFFFF", space_before=600))
        info = " · ".join(filter(None, [
            f"{meta['hours']} 课时", meta.get("audience"), meta.get("teacher"),
        ]))
        if info:
            paras.append(paragraph(info, 1300, color_str="FFFFFF", space_before=800))
        shapes.append(textbox(next(counter), "cover", MARGIN, 320040, CONTENT_W, 1371600, paras, anchor="ctr"))
        if not meta.get("final"):
            shapes.append(textbox(
                next(counter), "draft", SLIDE_W - 2880360, 274638, 2377440, 292608,
                [paragraph("校订稿 · 待教师确认", 1100, bold=True, color_str=theme["warn"], align="ctr")],
                fill=theme["warnSoft"], line_color=theme["warn"], radius=5000, geom="roundRect",
            ))
    else:
        label = TYPE_LABEL.get(stype, stype)
        eyebrow(counter, shapes, label, theme)
        shapes.append(textbox(
            next(counter), "title", CONTENT_X, TITLE_Y, CONTENT_W, TITLE_H,
            [paragraph(slide["title"], 2600, bold=True, color_str=theme["ink"], space_before=0)],
        ))
        shapes.append(rect(next(counter), "rule", CONTENT_X, RULE_Y, 548640, 28575, theme["accent"]))
        if stype == "safety-warning":
            shapes.append(rect(next(counter), "edge", 0, 0, 158750, SLIDE_H, theme["warn"]))
        shapes += render_blocks(counter, slide.get("blocks", []), theme, media=media)
    # 页脚：出处 + 课标标注 + 页码
    source_line = slide_source_line(spec, slide)
    if source_line:
        shapes.append(textbox(
            next(counter), "source", CONTENT_X, FOOTER_Y, CONTENT_W * 2 // 3, 274638,
            [paragraph(f"来源：{source_line}", 1000, color_str=theme["muted"], space_before=0)],
        ))
    kp_line = spec_knowledge(spec, slide)
    if kp_line:
        shapes.append(textbox(
            next(counter), "standards", CONTENT_X + CONTENT_W * 2 // 3, FOOTER_Y, CONTENT_W // 3, 274638,
            [paragraph(kp_line, 1000, color_str=theme["accent"], align="r", space_before=0)],
        ))
    status = "定稿" if meta.get("final") else "校订稿"
    shapes.append(textbox(
        next(counter), "page", CONTENT_X, 6537744, CONTENT_W, 228600,
        [paragraph(f"{meta.get('course') or meta['title']} · {status} · {index + 1}", 1000,
                   color_str=theme["muted"], align="r", space_before=0)],
    ))
    return shapes


def eyebrow(counter, shapes, label, theme):
    shapes.append(textbox(
        next(counter), "eyebrow", CONTENT_X, 155448, 3200400, 228600,
        [paragraph(label, 1200, bold=True, color_str=theme["accent"], space_before=0)],
    ))


def spec_knowledge(spec, slide):
    bits = []
    for point in slide.get("knowledgePoints", []):
        if point.get("extension"):
            bits.append(f"拓展｜{point['name']}")
        else:
            bits.append(f"课标 {point.get('standardId', '')}｜{point['name']}")
    text = "  ".join(bits)
    return text if len(text) <= 52 else text[:49] + "…"


# ---------------------------------------------------------------- OOXML 包

def theme_xml(theme):
    accents = [theme["accent"], theme["ok"], theme["warn"], theme["muted"], theme["line"], theme["ink"]]
    accent_xml = "".join(f'<a:accent{i + 1}><a:srgbClr val="{color(a)}"/></a:accent{i + 1}>' for i, a in enumerate(accents))
    fills = "".join(
        f'<a:{tag}><a:solidFill><a:srgbClr val="{color(theme["panel"])}"/></a:solidFill></a:{tag}>'
        for tag in ("fill1", "fill2", "fill3")
    )
    lines = "".join(
        f'<a:ln w="{9525 * (i + 1)}" cap="flat" cmpd="sng" algn="ctr">'
        f'<a:solidFill><a:srgbClr val="{color(theme["line"])}"/></a:solidFill><a:prstDash val="solid"/></a:ln>'
        for i in range(3)
    )
    effects = "<a:effectStyle><a:effectLst/></a:effectStyle>" * 3
    bgfills = "".join(
        f'<a:{tag}><a:solidFill><a:srgbClr val="{color(theme["bg"])}"/></a:solidFill></a:{tag}>'
        for tag in ("fill1", "fill2", "fill3")
    )
    return (
        '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Courseware">'
        '<a:themeElements><a:clrScheme name="Courseware">'
        f'<a:dk1><a:srgbClr val="{color(theme["ink"])}"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
        f'<a:dk2><a:srgbClr val="{color(theme["muted"])}"/></a:dk2><a:lt2><a:srgbClr val="{color(theme["bg"])}"/></a:lt2>'
        f"{accent_xml}<a:hlink><a:srgbClr val=\"{color(theme['accent'])}\"/></a:hlink>"
        '<a:folHlink><a:srgbClr val="5B6B7F"/></a:folHlink></a:clrScheme>'
        '<a:fontScheme name="Courseware">'
        f'<a:majorFont><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/><a:cs typeface=""/></a:majorFont>'
        f'<a:minorFont><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/><a:cs typeface=""/></a:minorFont>'
        "</a:fontScheme>"
        f'<a:fmtScheme name="Courseware"><a:fillStyleLst>{fills}</a:fillStyleLst>'
        f"<a:lnStyleLst>{lines}</a:lnStyleLst><a:effectStyleLst>{effects}</a:effectStyleLst>"
        f"<a:bgFillStyleLst>{bgfills}</a:bgFillStyleLst><a:objectDefaults/><a:extraClrSchemeLst/>"
        "</a:fmtScheme></a:themeElements></a:theme>"
    )


MASTER_XML = (
    '<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
    '<p:cSld name="Courseware Master"><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>'
    '<a:effectLst/></p:bgPr></p:bg><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/>'
    '<p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" '
    'accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" '
    'accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
    '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/>'
    '<p:sldLayoutId id="2147483650" r:id="rId2"/></p:sldLayoutIdLst></p:sldMaster>'
)


def layout_xml(kind):
    return (
        '<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        f'type="{kind}" preserve="1"><p:cSld name="{kind}"><p:spTree>'
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
        "</p:spTree></p:cSld></p:sldLayout>"
    )


def slide_xml(shapes, bg):
    return (
        '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        f'<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="{color(bg)}"/></a:solidFill>'
        "<a:effectLst/></p:bgPr></p:bg><p:spTree>"
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        f"{''.join(shapes)}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
    )


def rels_xml(entries):
    items = "".join(
        f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/{kind}" Target="{target}"/>'
        for rid, kind, target in entries
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{items}</Relationships>"
    )


def core_xml(spec):
    meta = spec["meta"]
    title = f"{meta.get('course') or ''} {meta['title']}".strip()
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"<dc:title>{esc(title)}</dc:title>"
        "<dc:creator>FORU 技能广场 · 智能课件生成</dc:creator>"
        "<cp:lastModifiedBy>FORU 技能广场</cp:lastModifiedBy></cp:coreProperties>"
    )


def app_xml(spec):
    slides = list(spec["slides"]) + [
        {"title": title} for title, _ in appendix_pages(spec)
    ]
    count = len(slides)
    titles = "".join(
        f"<vt:lpstr>{esc(slide['title'])}</vt:lpstr>" for slide in slides
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        f"<Slides>{count}</Slides><TitlesOfParts><vt:vector size=\"{count}\" baseType=\"lpstr\">"
        f"{titles}</vt:vector></TitlesOfParts></Properties>"
    )


def content_types_xml(spec, media: _Media, slide_count: int):
    overrides = [
        ('/ppt/presentation.xml', 'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml'),
        ('/ppt/slideMasters/slideMaster1.xml', 'application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml'),
        ('/ppt/theme/theme1.xml', 'application/vnd.openxmlformats-officedocument.theme+xml'),
        ('/docProps/core.xml', 'application/vnd.openxmlformats-package.core-properties+xml'),
        ('/docProps/app.xml', 'application/vnd.openxmlformats-officedocument.extended-properties+xml'),
    ]
    for i in (1, 2):
        overrides.append(
            (f'/ppt/slideLayouts/slideLayout{i}.xml',
             'application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml')
        )
    for i in range(1, slide_count + 1):
        overrides.append(
            (f'/ppt/slides/slide{i}.xml',
             'application/vnd.openxmlformats-officedocument.presentationml.slide+xml')
        )
    defaults = [
        ('rels', 'application/vnd.openxmlformats-package.relationships+xml'),
        ('xml', 'application/xml'),
        ('png', 'image/png'), ('jpeg', 'image/jpeg'), ('jpg', 'image/jpeg'), ('gif', 'image/gif'),
    ]
    used = {item[2] for item in media.items}
    default_xml = "".join(
        f'<Default Extension="{ext}" ContentType="{ctype}"/>'
        for ext, ctype in defaults if ext in used or ext in ("rels", "xml")
    )
    override_xml = "".join(
        f'<Override PartName="{part}" ContentType="{ctype}"/>' for part, ctype in overrides
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">{default_xml}{override_xml}</Types>'
    )


def write_pptx(spec, out_path: Path, workspace: Path):
    theme = theme_of(spec)
    media = _Media(workspace)
    all_slides = list(spec["slides"])
    for title, blocks in appendix_pages(spec):
        all_slides.append({"type": "appendix", "title": title, "blocks": blocks, "sources": []})
    slide_parts = []
    for index, slide in enumerate(all_slides):
        shapes = build_slide(spec, index, slide, theme, media)
        slide_parts.append(slide_xml(shapes, theme["bg"]))
    n = len(slide_parts)
    master_rels = rels_xml([
        ("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml"),
        ("rId2", "slideLayout", "../slideLayouts/slideLayout2.xml"),
        ("rId3", "theme", "../theme/theme1.xml"),
    ])
    layout_rels = rels_xml([("rId1", "slideMaster", "../slideMasters/slideMaster1.xml")])
    pres_rels = [("rId1", "slideMaster", "slideMasters/slideMaster1.xml")]
    pres_rels += [
        (f"rId{i + 2}", "slide", f"slides/slide{i + 1}.xml") for i in range(n)
    ]
    pres_rels.append((f"rId{n + 2}", "theme", "theme/theme1.xml"))
    sld_ids = "".join(f'<p:sldId id="{256 + i}" r:id="rId{i + 2}"/>' for i in range(n))
    presentation = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" saveSubsetFonts="1">'
        f'<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        f"<p:sldIdLst>{sld_ids}</p:sldIdLst>"
        f'<p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}"/><p:notesSz cx="6858000" cy="9144000"/>'
        '<p:defaultTextStyle><a:defPPr><a:defRPr lang="zh-CN"/></a:defPPr></p:defaultTextStyle>'
        "</p:presentation>"
    )
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml(spec, media, n))
        zf.writestr("_rels/.rels", rels_xml([
            ("rId1", "officeDocument", "ppt/presentation.xml"),
            ("rId2", "core-properties", "docProps/core.xml"),
            ("rId3", "extended-properties", "docProps/app.xml"),
        ]))
        zf.writestr("docProps/core.xml", core_xml(spec))
        zf.writestr("docProps/app.xml", app_xml(spec))
        zf.writestr("ppt/presentation.xml", presentation)
        zf.writestr("ppt/_rels/presentation.xml.rels", rels_xml(pres_rels))
        zf.writestr("ppt/slideMasters/slideMaster1.xml", MASTER_XML)
        zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", master_rels)
        for i in (1, 2):
            zf.writestr(f"ppt/slideLayouts/slideLayout{i}.xml", layout_xml("title" if i == 1 else "blank"))
            zf.writestr(f"ppt/slideLayouts/_rels/slideLayout{i}.xml.rels", layout_rels)
        zf.writestr("ppt/theme/theme1.xml", theme_xml(theme))
        for i, part in enumerate(slide_parts, start=1):
            zf.writestr(f"ppt/slides/slide{i}.xml", part)
            entries = [("rId1", "slideLayout", "../slideLayouts/slideLayout2.xml")]
            for mindex, (name, _, _) in enumerate(media.items, start=1):
                entries.append((f"rId{mindex + 1}", "image", f"../media/{name}"))
            zf.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", rels_xml(entries))
        for name, data, _ in media.items:
            zf.writestr(f"ppt/media/{name}", data)
    return n


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="courseware-spec/1 JSON 路径")
    parser.add_argument("-o", "--out", type=Path, default=Path("courseware.pptx"))
    parser.add_argument("--workspace", type=Path, default=None, help="会话工作区根目录（默认 spec 所在目录）")
    args = parser.parse_args(argv)
    workspace = (args.workspace or args.spec.resolve().parent).resolve()
    try:
        spec = load_spec(json.loads(args.spec.read_text(encoding="utf-8")), workspace)
        count = write_pptx(spec, args.out, workspace)
    except (SpecError, json.JSONDecodeError, OSError) as error:
        print(json.dumps({"status": "error", "message": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "ok", "path": str(args.out), "slides": count}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
