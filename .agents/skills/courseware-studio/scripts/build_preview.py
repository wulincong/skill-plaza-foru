"""courseware-spec/1 -> 自包含网页预览（output/site/index.html）。

单文件 HTML：内联 CSS/JS、无外部字体与脚本，图片复制到同目录 assets/，
适配平台 /p/ 沙箱托管（CSP 仅允许同源静态资源）。幻灯片逐页服务端渲染，
JS 只负责翻页与面板切换；打印时展开全部页面。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec_model import (  # noqa: E402
    SPEC_VERSION, SpecError, appendix_pages, confirmation_state, load_spec,
    source_label, theme_of,
)

TYPE_LABEL = {
    "objectives": "学习目标", "intro": "任务导入", "concept": "知识讲解",
    "diagram": "图解", "procedure": "实训演示", "safety-warning": "安全警示",
    "quiz": "课堂测验", "rubric": "考核评分", "summary": "课堂小结",
    "appendix": "附录",
}

CSS = """
:root{
  --bg:#F4F7FB;--panel:#FFFFFF;--ink:#1F2D3D;--muted:#5B6B7F;--accent:#1D5FBF;
  --accentSoft:#E3EDF9;--warn:#B3541E;--warnSoft:#FBEFE4;--ok:#2E7D4F;--line:#D5DEE9;
  --radius:14px;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",system-ui,sans-serif;
  background:var(--bg);color:var(--ink);min-height:100vh}
.topbar{display:flex;align-items:center;gap:14px;padding:12px 20px;background:var(--panel);
  border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5;flex-wrap:wrap}
.topbar .course{font-weight:700;font-size:15px}
.topbar .meta{color:var(--muted);font-size:13px}
.badge{font-size:12px;padding:3px 10px;border-radius:999px;font-weight:600}
.badge.draft{background:var(--warnSoft);color:var(--warn)}
.badge.final{background:#E5F2EA;color:var(--ok)}
main{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:16px;padding:16px 20px;max-width:1440px;margin:0 auto}
.stage{min-width:0}
.slide-wrap{position:relative}
.slide{aspect-ratio:16/9;background:var(--bg);border:1px solid var(--line);border-radius:var(--radius);
  overflow:hidden;display:none;padding:0}
.slide.active{display:block}
.slide .band{background:var(--accent);color:#fff;padding:34px 44px;min-height:26%}
.slide .band .eyebrow{font-size:13px;opacity:.9;letter-spacing:.04em}
.slide .band h1{font-size:clamp(20px,3vw,34px);margin-top:10px;line-height:1.25}
.slide .band .sub{font-size:14px;margin-top:10px;opacity:.92}
.slide .body{padding:22px 44px 46px}
.slide .eyebrow-tag{color:var(--accent);font-weight:700;font-size:12px;letter-spacing:.06em}
.slide h2{font-size:clamp(17px,2.2vw,24px);margin:2px 0 10px}
.slide .rule{width:44px;height:3px;background:var(--accent);border-radius:2px;margin-bottom:16px}
.slide .foot{position:absolute;left:44px;right:44px;bottom:12px;display:flex;justify-content:space-between;
  gap:16px;font-size:11px;color:var(--muted)}
.slide.safety{border-left:6px solid var(--warn)}
.blocks{display:flex;flex-direction:column;gap:12px}
.b-bullets li{margin:6px 0 6px 1.1em;line-height:1.55}
.b-paragraph{line-height:1.7}
.b-twocol{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.b-twocol .col{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.b-twocol h4{color:var(--accent);font-size:14px;margin-bottom:6px}
.b-twocol li{margin:4px 0 4px 1em;font-size:13.5px}
.b-steps{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 16px}
.b-steps li{margin:7px 0 7px 1.6em;line-height:1.5}
.b-steps ol{padding-left:8px}
table.b-table{border-collapse:collapse;width:100%;font-size:13px}
.b-table th{background:var(--accent);color:#fff;padding:7px 9px;font-weight:600;text-align:center}
.b-table td{border:1px solid var(--line);padding:6px 9px;background:var(--panel)}
.b-table tr:nth-child(even) td{background:var(--bg)}
.b-image{display:flex;flex-direction:column;align-items:center;gap:6px}
.b-image img{max-width:88%;max-height:46vh;border:1px solid var(--line);border-radius:8px;background:#fff}
.b-image figcaption{font-size:12px;color:var(--muted)}
.b-callout{border-radius:10px;padding:12px 16px;line-height:1.55}
.b-callout.warn{background:var(--warnSoft);border:1.5px solid var(--warn)}
.b-callout.info{background:var(--accentSoft);border:1.5px solid var(--accent)}
.b-callout h4{font-size:14px;margin-bottom:4px}
.b-callout.warn h4{color:var(--warn)}
.b-callout.info h4{color:var(--accent)}
.b-gap{border:1.5px dashed var(--muted);border-radius:10px;padding:12px 16px;color:var(--muted)}
.b-gap h4{font-size:13px;margin-bottom:4px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.chip{font-size:11px;padding:2px 9px;border-radius:999px;background:var(--accentSoft);color:var(--accent)}
.chip.ext{background:#F1EAF7;color:#6B4FA0}
.chip.safety{background:var(--warnSoft);color:var(--warn)}
.pager{display:flex;justify-content:space-between;align-items:center;margin-top:10px;gap:10px}
.pager button{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:8px;
  padding:7px 16px;cursor:pointer;font-size:14px}
.pager button:hover{border-color:var(--accent);color:var(--accent)}
.pager .count{font-size:13px;color:var(--muted)}
.thumbs{display:flex;gap:8px;overflow-x:auto;margin-top:12px;padding-bottom:6px}
.thumbs button{flex:0 0 auto;border:1px solid var(--line);background:var(--panel);border-radius:8px;
  padding:6px 10px;font-size:12px;color:var(--muted);cursor:pointer;max-width:150px;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.thumbs button.active{border-color:var(--accent);color:var(--accent);font-weight:600}
.panel{display:flex;flex-direction:column;gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:14px 16px}
.card h3{font-size:13px;color:var(--accent);margin-bottom:8px;letter-spacing:.03em}
.card ul{list-style:none}
.card li{font-size:12.5px;padding:5px 0;border-bottom:1px dashed var(--line);line-height:1.5}
.card li:last-child{border-bottom:none}
.card .src b{color:var(--ink)}
.card .muted{color:var(--muted)}
.card .st{float:right;font-size:11px;padding:1px 8px;border-radius:999px}
.st.ok{background:#E5F2EA;color:var(--ok)}
.st.pend{background:var(--warnSoft);color:var(--warn)}
.hint{font-size:11.5px;color:var(--muted);margin-top:6px}
@media (max-width:960px){main{grid-template-columns:1fr}.panel{flex-direction:row;flex-wrap:wrap}.panel .card{flex:1 1 260px}}
@media print{.pager,.thumbs,.panel,.topbar .badge{display:none}main{display:block}
  .slide{display:block!important;page-break-after:always;border:none}}
"""

JS = """
document.addEventListener('keydown', function (ev) {
  if (ev.key === 'ArrowRight' || ev.key === 'PageDown') { go(current + 1); }
  if (ev.key === 'ArrowLeft' || ev.key === 'PageUp') { go(current - 1); }
});
function go(index) {
  var slides = document.querySelectorAll('.slide');
  var thumbs = document.querySelectorAll('.thumbs button');
  if (index < 0 || index >= slides.length) return;
  slides[current].classList.remove('active');
  thumbs[current].classList.remove('active');
  current = index;
  slides[current].classList.add('active');
  thumbs[current].classList.add('active');
  thumbs[current].scrollIntoView({ block: 'nearest', inline: 'center' });
  document.getElementById('page-now').textContent = current + 1;
  var foot = document.querySelectorAll('.slide')[current].dataset;
  document.getElementById('panel-page').innerHTML = foot.panel || '';
}
var current = 0;
"""


def esc(text) -> str:
    return escape(str(text), quote=True)


def render_block(block, workspace: Path, assets: _Assets) -> str:
    kind = block["kind"]
    if kind == "bullets":
        items = "".join(f"<li>{esc(item)}</li>" for item in block["items"])
        return f'<ul class="b-bullets">{items}</ul>'
    if kind == "paragraph":
        return f'<p class="b-paragraph">{esc(block["text"])}</p>'
    if kind == "two-col":
        cols = ""
        for side in ("left", "right"):
            col = block[side]
            items = "".join(f"<li>{esc(item)}</li>" for item in col.get("items", []))
            cols += (
                f'<div class="col"><h4>{esc(col["title"])}</h4><ul>{items}</ul></div>'
            )
        return f'<div class="b-twocol">{cols}</div>'
    if kind == "steps":
        items = "".join(f"<li>{esc(item)}</li>" for item in block["items"])
        return f'<div class="b-steps"><ol>{items}</ol></div>'
    if kind == "table":
        head = "".join(f"<th>{esc(cell)}</th>" for cell in block["header"])
        rows = "".join(
            "<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>"
            for row in block["rows"]
        )
        return f'<table class="b-table"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'
    if kind == "image":
        src = assets.copy(block["path"], workspace)
        suffix = "（示意图，非设备实图）" if block.get("schematic") else ""
        return (
            f'<figure class="b-image"><img src="{esc(src)}" alt="{esc(block["caption"])}" loading="lazy">'
            f"<figcaption>{esc(block['caption'])}{suffix}</figcaption></figure>"
        )
    if kind == "callout":
        tone = block.get("tone", "info")
        return f'<div class="b-callout {tone}"><h4>{esc(block["title"])}</h4><p>{esc(block["text"])}</p></div>'
    if kind == "gap":
        return f'<div class="b-gap"><h4>待教师补充</h4><p>{esc(block["text"])}</p></div>'
    return ""


class _Assets:
    """把课件引用的图片复制进站点 assets/，返回相对路径。"""

    def __init__(self, site: Path):
        self.site = site
        self.dir = site / "assets"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.count = 0

    def copy(self, path: str, workspace: Path) -> str:
        source = (workspace / path).resolve()
        self.count += 1
        target = self.dir / f"figure{self.count}{source.suffix.lower() or '.png'}"
        shutil.copyfile(source, target)
        return f"assets/{target.name}"


def render_slide(spec, index, slide, assets: _Assets, workspace: Path) -> str:
    meta = spec["meta"]
    stype = slide["type"]
    blocks = "".join(render_block(b, workspace, assets) for b in slide.get("blocks", []))
    chips = ""
    for point in slide.get("knowledgePoints", []):
        if point.get("extension"):
            chips += f'<span class="chip ext">拓展｜{esc(point["name"])}</span>'
        else:
            chips += f'<span class="chip">课标 {esc(point.get("standardId", ""))}｜{esc(point["name"])}</span>'
    if stype == "safety-warning":
        chips = '<span class="chip safety">安全强制位 · 待教师确认</span>' + chips
    panel_bits = []
    if slide.get("sources"):
        items = "".join(
            f'<li class="src"><b>{esc(source_label(spec, src))}</b>'
            + (f'<div class="muted">{esc(src.get("note", ""))}</div>' if src.get("note") else "")
            + "</li>"
            for src in slide["sources"]
        )
        panel_bits.append(f"<ul>{items}</ul>")
    else:
        panel_bits.append('<p class="muted">本页为封面/目录/清单页，不承载课程事实。</p>')
    if slide.get("notes"):
        panel_bits.append(f'<p class="muted">教师备注：{esc(slide["notes"])}</p>')
    panel_html = esc("".join(panel_bits))
    if stype == "cover":
        eyebrow = esc(" · ".join(filter(None, [meta.get("course"), meta.get("unit")])))
        info = esc(" · ".join(filter(None, [f"{meta['hours']} 课时", meta.get("audience"), meta.get("teacher")])))
        sub = f'<p class="sub">{esc(slide["subtitle"])}</p>' if slide.get("subtitle") else ""
        return (
            f'<section class="slide" data-panel="{panel_html}">'
            f'<div class="band"><p class="eyebrow">{eyebrow}</p><h1>{esc(slide["title"])}</h1>{sub}<p class="sub">{info}</p></div>'
            f'<div class="body">{blocks}<div class="chips">{chips}</div></div></section>'
        )
    label = TYPE_LABEL.get(stype, stype)
    src_line = "；".join(source_label(spec, s) for s in slide.get("sources", []))[:80]
    foot = f'<div class="foot"><span>来源：{esc(src_line) if src_line else "—"}</span><span>{index + 1}</span></div>'
    return (
        f'<section class="slide {"safety" if stype == "safety-warning" else ""}" data-panel="{panel_html}">'
        f'<div class="body"><p class="eyebrow-tag">{label}</p><h2>{esc(slide["title"])}</h2><div class="rule"></div>'
        f'<div class="blocks">{blocks}</div><div class="chips">{chips}</div></div>{foot}</section>'
    )


def build_preview(spec, site: Path, workspace: Path) -> int:
    theme = theme_of(spec)
    assets = _Assets(site)
    slides = list(spec["slides"])
    for title, blocks in appendix_pages(spec):
        slides.append({"type": "appendix", "title": title, "blocks": blocks, "sources": []})
    slide_html = []
    for index, slide in enumerate(slides):
        slide_html.append(render_slide(spec, index, slide, assets, workspace))
    thumbs = "".join(
        f'<button data-i="{i}" onclick="go({i})"{" class=active" if i == 0 else ""}>{i + 1} · {esc(s["title"][:14])}</button>'
        for i, s in enumerate(slides)
    )
    meta = spec["meta"]
    status = "定稿" if meta.get("final") else "校订稿 · 待教师确认"
    badge = "final" if meta.get("final") else "draft"

    materials = {m["id"]: m for m in spec["materials"]}
    copyright_items = "".join(
        f'<li><b>{esc(entry["content"])}</b>'
        f'<div class="muted">{esc(materials.get(entry.get("materialId"), {}).get("name", ""))} · {esc(entry["license"])}</div></li>'
        for entry in spec.get("copyright", [])
    ) or '<li class="muted">无外部素材引用。</li>'
    state = confirmation_state(spec)
    confirm_items = "".join(
        f'<li>{esc(item["text"])}<span class="st {"ok" if state.get(item["id"]) == "已确认" else "pend"}">'
        f'{state.get(item["id"], "待确认")}</span></li>'
        for item in spec.get("pendingConfirmations", [])
    ) or '<li class="muted">无待确认事项。</li>'
    resource_items = "".join(
        f'<li><b>{esc(item["name"])}</b><div class="muted">{esc(item["kind"])} · {esc(item["source"])}</div></li>'
        for item in spec.get("resources", [])
    ) or '<li class="muted">无登记资源。</li>'
    material_items = "".join(
        f'<li><b>{esc(m["name"])}</b><div class="muted">{esc(m.get("pages") or "")}</div></li>'
        for m in spec["materials"]
    )

    root_vars = "".join(f"--{key}:#{value};" for key, value in theme.items())

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(meta.get("course") or "")} {esc(meta["title"])} · 课件预览</title>
<style>:root{{{root_vars}}}{CSS}</style>
</head>
<body>
<header class="topbar">
  <span class="course">{esc(meta.get("course") or meta["title"])}</span>
  <span class="meta">{esc(meta["title"])} · {meta["hours"]} 课时{(" · " + meta["audience"]) if meta.get("audience") else ""}</span>
  <span class="badge {badge}">{status}</span>
  <span class="meta" style="margin-left:auto">{SPEC_VERSION}</span>
</header>
<main>
  <section class="stage">
    <div class="slide-wrap">{''.join(slide_html)}</div>
    <div class="pager">
      <button onclick="go(current-1)">← 上一页</button>
      <span class="count"><span id="page-now">1</span> / {len(slides)}</span>
      <button onclick="go(current+1)">下一页 →</button>
    </div>
    <nav class="thumbs">{thumbs}</nav>
  </section>
  <aside class="panel">
    <div class="card"><h3>本页来源与课标</h3><div id="panel-page"></div></div>
    <div class="card"><h3>材料范围</h3><ul>{material_items}</ul></div>
    <div class="card"><h3>版权与授权</h3><ul>{copyright_items}</ul></div>
    <div class="card"><h3>教师待确认清单</h3><ul>{confirm_items}
      <li class="hint">涉及实训安全操作的内容，确认步骤顺序后才能定稿导出。</li></ul></div>
    <div class="card"><h3>资源入库清单</h3><ul>{resource_items}</ul></div>
  </aside>
</main>
<script>{JS}
document.getElementById('panel-page').innerHTML = document.querySelectorAll('.slide')[0].dataset.panel || '';</script>
</body>
</html>
"""
    (site / "index.html").write_text(html, encoding="utf-8")
    return len(slides)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("-o", "--out", type=Path, default=Path("output/site"))
    parser.add_argument("--workspace", type=Path, default=None)
    args = parser.parse_args(argv)
    workspace = (args.workspace or args.spec.resolve().parent).resolve()
    try:
        spec = load_spec(json.loads(args.spec.read_text(encoding="utf-8")), workspace)
        args.out.mkdir(parents=True, exist_ok=True)
        count = build_preview(spec, args.out, workspace)
    except (SpecError, json.JSONDecodeError, OSError) as error:
        print(json.dumps({"status": "error", "message": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "ok", "directory": str(args.out), "slides": count}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
