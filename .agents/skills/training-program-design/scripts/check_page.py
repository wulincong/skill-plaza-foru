#!/usr/bin/env python3
"""成品页面校验：图型家族门槛与依据链接完整性。渲染之后、register_delivery 之前必须通过，
任一项不达标不得登记交付。用法：
  python3 check_page.py <工作区根目录> --page work/page.json --web output/public/<站点目录> [--program program.json]
"""
import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from program import CHART_FAMILY, CHART_MIN_FAMILIES, FIGURE_KINDS

# 「指标 M_」「来源 S_」「能力 C-」等编号写法：全页禁止（含附录）
COMBO = re.compile(r'(?:指标|来源|能力|证据|依据)[ \t]*[MSC][-_][A-Za-z0-9_-]+')
# 裸编号（M_XXX / S_XXX / C-XXX）：正文禁止，附录条目标识允许
BARE = re.compile(r'(?<![A-Za-z0-9_-])[MSC][-_][A-Za-z0-9_-]+')
ANCHOR_HREF = re.compile(r'href="#([^"]+)"')
HTML_ID = re.compile(r' id="([^"]+)"')
HTML_LINK = re.compile(r'<a href="#([^"]+)">(.*?)</a>', re.S)
APPENDIX_HEAD = re.compile(r'<h2[^>]*>[^<]*附录')
TAG = re.compile(r'<[^>]+>')
# markdown 链接语法在 page.json 文本里保留，扫描编号前先折叠为链接文字
MD_LINK = re.compile(r'\[([^\]]+)\]\([^)]*\)')


def visible(text):
    return MD_LINK.sub(r'\1', str(text))


class TextRunsParser(HTMLParser):
    """把成品 HTML 切成文本片段（run）：跨元素边界的文字不拼接，
    「A.2 指标」标题与下一条目的 id 不会被判成「指标 M_x」引用。"""

    def __init__(self):
        super().__init__()
        self.runs = []
        self._buffer = []

    def handle_starttag(self, tag, attrs):
        self.flush()

    def handle_endtag(self, tag):
        self.flush()

    def handle_data(self, data):
        self._buffer.append(data)

    def flush(self):
        if self._buffer:
            self.runs.append(''.join(self._buffer))
            self._buffer = []


def html_text_runs(html):
    parser = TextRunsParser()
    parser.feed(html)
    parser.flush()
    return parser.runs


def walk(blocks, in_appendix=False):
    """收集 (文本, 是否附录) 与 figure 块。"""
    texts, figures = [], []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        appendix = in_appendix or (block.get('type') == 'section'
                                   and str(block.get('title', '')).startswith('附录'))
        if block.get('type') == 'figure':
            figures.append(block)
        for key in ('text', 'lead', 'note', 'footer', 'subtitle', 'eyebrow'):
            if block.get(key):
                texts.append((str(block[key]), appendix))
        if block.get('type') == 'sources':
            for item in block.get('items', []):
                for key in ('label', 'text'):
                    if item.get(key):
                        texts.append((str(item[key]), appendix))
        if block.get('type') == 'table':
            for row in block.get('rows', []):
                for cell in row:
                    texts.append((str(cell), appendix))
        if block.get('type') == 'metrics':
            for item in block.get('items', []):
                for key in ('label', 'note'):
                    if item.get(key):
                        texts.append((str(item[key]), appendix))
        if isinstance(block.get('blocks'), list):
            sub_texts, sub_figures = walk(block['blocks'], appendix)
            texts += sub_texts
            figures += sub_figures
    return texts, figures


def check(root, page_rel, web_rel, program_rel):
    errors = []
    page_dir = (root / page_rel).parent
    document = json.loads((root / page_rel).read_text(encoding='utf-8'))
    html_path = root / web_rel / 'index.html'
    if not html_path.is_file():
        return None, [f'成品网页不存在：{web_rel}/index.html，先渲染再校验']
    html = html_path.read_text(encoding='utf-8')

    plan = {}
    program_path = root / program_rel
    if program_path.is_file():
        d = json.loads(program_path.read_text(encoding='utf-8'))
        plan = {e.get('id'): e for e in d.get('chartPlan', []) if isinstance(e, dict)}

    # ---- 图表：实际嵌入的图型（规划与成品一致性 + 家族门槛）----
    texts, figures = walk(document.get('blocks', []))
    panels = []
    figure_ids = []
    for figure in figures:
        spec_path = page_dir / figure['spec']
        if not spec_path.is_file():
            errors.append(f'图稿规格缺失：{figure["spec"]}')
            continue
        spec = json.loads(spec_path.read_text(encoding='utf-8'))
        figure_ids.append(spec.get('id'))
        kinds = [p.get('kind') for p in spec.get('panels', [])]
        unknown = [k for k in kinds if k not in FIGURE_KINDS]
        if unknown:
            errors.append(f'{spec.get("id")}: 面板图型不可执行 {unknown}')
            continue
        values_path = page_dir / figure['bundle'] / 'values.json'
        if values_path.is_file():
            value_kinds = [item.get('kind') for item in json.loads(values_path.read_text(encoding='utf-8'))]
            if value_kinds != kinds:
                errors.append(f'{spec.get("id")}: 数值表图型 {value_kinds} 与规格 {kinds} 不一致')
        entry = plan.get(spec.get('id'))
        if plan:
            if entry is None:
                errors.append(f'图 {spec.get("id")} 不在 chartPlan 中，页面图必须先规划')
            else:
                off_family = {CHART_FAMILY.get(k) for k in kinds} - {CHART_FAMILY.get(entry.get('kind'))}
                if off_family:
                    errors.append(f'{spec.get("id")}: 实际图型家族 {sorted(str(f) for f in off_family)} '
                                  f'与规划 {entry.get("kind")}（{CHART_FAMILY.get(entry.get("kind"))}）不符')
        panels += [CHART_FAMILY[k] for k in kinds if k in CHART_FAMILY]
    if plan and set(plan) - set(figure_ids):
        errors.append(f'规划图未上页：{sorted(set(plan) - set(figure_ids))}')
    families = sorted(set(panels))
    bar_count = sum(1 for f in panels if f == '条形')
    if len(families) < CHART_MIN_FAMILIES:
        errors.append(f'全页仅 {len(families)} 种图型家族（{ "、".join(families) or "无图" }），'
                      f'至少 {CHART_MIN_FAMILIES} 种完全不同的图型（条形家族算一种）')
    if bar_count * 2 > len(panels):
        errors.append(f'条形家族面板 {bar_count}/{len(panels)} 超过全部图的一半')

    # ---- 编号写法：正文依据不许出现编号 ----
    body_text = [(t, a) for t, a in texts if not a]
    for text, _ in texts:
        for hit in COMBO.findall(visible(text)):
            errors.append(f'出现编号引用写法「{hit}…」：依据须为可读名称加锚点链接')
            break
    bare_body = [m.group(0) for text, _ in body_text for m in BARE.finditer(visible(text))]
    if bare_body:
        errors.append(f'正文出现裸编号 {sorted(set(bare_body))[:8]}（编号只允许出现在附录条目标识）')

    # ---- 成品 HTML：编号清零（按文本片段判定）、锚点无死链、链接文字可读 ----
    head = APPENDIX_HEAD.search(html)
    html_body = html[:head.start()] if head else html
    combo_html = [hit for run in html_text_runs(html) for hit in COMBO.findall(visible(run))]
    if combo_html:
        errors.append(f'成品页出现编号引用写法 {sorted(set(combo_html))[:8]}')
    bare_html = sorted({m.group(0) for run in html_text_runs(html_body)
                        for m in BARE.finditer(visible(run))})
    if bare_html:
        errors.append(f'成品页正文出现裸编号 {bare_html[:8]}')
    ids = set(HTML_ID.findall(html))
    hrefs = ANCHOR_HREF.findall(html)
    dead = sorted(set(hrefs) - ids)
    if dead:
        errors.append(f'死链（页面内不存在锚点）：{dead[:8]}')
    bad_text = []
    for anchor, label in HTML_LINK.findall(html):
        clean = TAG.sub('', label).strip()
        if not clean:
            bad_text.append(f'#{anchor} 链接文字为空')
        elif BARE.fullmatch(clean) or COMBO.search(clean):
            bad_text.append(f'#{anchor} 链接文字是编号「{clean}」')
    if bad_text:
        errors.extend(bad_text[:8])

    # 图 id → 面板家族明细（汇总用）
    detail = []
    for figure in figures:
        spec_path = page_dir / figure['spec']
        if spec_path.is_file():
            spec = json.loads(spec_path.read_text(encoding='utf-8'))
            detail.append({'id': spec.get('id'),
                           'kinds': [p.get('kind') for p in spec.get('panels', [])],
                           'families': sorted({str(f) for f in (CHART_FAMILY.get(p.get('kind')) for p in spec.get('panels', []))})})
    summary = {
        'figures': detail,
        'familyCount': len(families), 'families': families,
        'panels': len(panels), 'barPanels': bar_count,
        'internalLinks': len(hrefs), 'deadLinks': len(dead),
        'comboPatterns': len(combo_html), 'bareInBody': len(bare_html) + len(bare_body),
    }
    return summary, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--page', type=Path, default=Path('work/page.json'))
    parser.add_argument('--web', type=Path, required=True)
    parser.add_argument('--program', type=Path, default=Path('program.json'))
    args = parser.parse_args()
    summary, errors = check(args.root, args.page, args.web, args.program)
    if errors:
        print('成品页面校验未通过（不得 register_delivery）：')
        for item in errors:
            print(f'  - {item}')
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print('成品页面校验通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
