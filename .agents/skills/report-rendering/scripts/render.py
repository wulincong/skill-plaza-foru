"""Render an agent-prepared page model or Markdown using report UI components."""
import argparse
from html import escape
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlparse

from markdown_it import MarkdownIt

from embed_chart import verified_figure


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN = MarkdownIt('commonmark', {'html': False}).enable('table')
PATTERNS = {'key-value', 'comparison', 'composition', 'time', 'matrix', 'detail', 'action', 'evidence'}


def plain(value):
    return escape(str(value), quote=True)


def markdown(value):
    tokens = MARKDOWN.parse(str(value))
    for token in tokens:
        if token.type in ('heading_open', 'heading_close') and token.tag == 'h1':
            token.tag = 'h2'
        if token.type == 'th_open':
            token.attrSet('scope', 'col')
    result = MARKDOWN.renderer.render(tokens, MARKDOWN.options, {})
    result = result.replace('<table>', '<div class="report-table-scroll" role="region" aria-label="数据表" tabindex="0"><table><caption>数据表</caption>')
    return result.replace('</table>', '</table></div>')


def rich_field(data, key, css=''):
    value = data.get(key)
    if value is None or value == '':
        return ''
    return f'<div class="report-prose {css}">{markdown(value)}</div>'


class Page:
    def __init__(self, base):
        self.base = base
        self.ids = set()

    def claim_id(self, value):
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', value) or value in self.ids:
            raise ValueError(f'页面 ID 无效或重复 {value}')
        self.ids.add(value)
        return value

    def table(self, block):
        pattern = block.get('pattern', 'detail')
        if pattern not in PATTERNS:
            raise ValueError(f'未知表格模式 {pattern}')
        columns = block['columns']
        title = block.get('title', '数据表')
        if not columns:
            raise ValueError('内部表格需要至少一列')
        headers = ''.join(f'<th scope="col" class="{"report-number" if c.get("numeric") else ""}">{plain(c["label"])}</th>' for c in columns)
        rows = []
        for row in block['rows']:
            if len(row) != len(columns):
                raise ValueError(f'{title} 的单元格数与列数不一致')
            cells = []
            for i, (cell, column) in enumerate(zip(row, columns)):
                is_header = column.get('row_header', i == 0)
                tag = 'th' if is_header else 'td'
                scope = ' scope="row"' if is_header else ''
                css = 'report-number' if column.get('numeric') else ''
                value = block.get('missing_label', '未提供') if cell is None else cell
                cells.append(f'<{tag}{scope} class="{css}">{plain(value)}</{tag}>')
            rows.append('<tr>' + ''.join(cells) + '</tr>')
        return (f'<div class="report-table report-table-{pattern}"><div class="report-table-scroll" role="region" aria-label="{plain(title)}" tabindex="0">'
                f'<table><caption>{plain(title)}</caption><thead><tr>{headers}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
                + rich_field(block, 'note', 'report-note') + rich_field(block, 'source', 'report-note') + '</div>')

    def blocks(self, blocks, level=2):
        return ''.join(self.block(block, level) for block in blocks)

    def block(self, block, level):
        kind = block['type']
        ident = ''
        if block.get('id'):
            ident = f' id="{self.claim_id(block["id"])}"'
        heading = ''
        if block.get('title') and kind != 'table':
            heading = f'<h{level}>{plain(block["title"])}</h{level}>'
        body = ''
        if kind == 'section':
            label = rich_field(block, 'label', 'report-eyebrow')
            return f'<section class="report-section"{ident}>{label}{heading}{self.blocks(block["blocks"], min(level + 1, 6))}</section>'
        if kind == 'text':
            body = rich_field(block, 'text')
        elif kind == 'summary':
            body = rich_field(block, 'lead', 'report-lead') + rich_field(block, 'text') + rich_field(block, 'note', 'report-note')
        elif kind == 'metrics':
            items = []
            for item in block['items']:
                tone = ' report-attention' if item.get('tone') == 'attention' else ''
                value = '未提供' if item.get('value') is None else item['value']
                items.append(f'<div class="report-metric{tone}"><span class="report-value">{plain(value)}</span>'
                             f'<span class="report-unit">{plain(item.get("unit", ""))}</span><strong>{plain(item["label"])}</strong>'
                             + rich_field(item, 'note', 'report-note') + '</div>')
            body = '<div class="report-metric-grid">' + ''.join(items) + '</div>'
        elif kind == 'table':
            body = self.table(block)
        elif kind == 'quote':
            body = '<blockquote>' + rich_field(block, 'text') + rich_field(block, 'source', 'report-note') + '</blockquote>'
        elif kind == 'callout':
            tone = 'report-attention' if block.get('tone') == 'attention' else ''
            body = rich_field(block, 'text', tone)
        elif kind == 'actions':
            items = []
            for item in block['items']:
                details = ''.join(f'<div><dt>{label}</dt><dd>{plain(item[key])}</dd></div>' for key, label in
                                  [('owner', '负责人'), ('when', '时间'), ('condition', '完成条件')] if item.get(key))
                items.append(f'<li><h{min(level + 1, 6)}>{plain(item["title"])}</h{min(level + 1, 6)}>'
                             + rich_field(item, 'text') + f'<dl>{details}</dl></li>')
            body = '<ol class="report-action-grid">' + ''.join(items) + '</ol>'
        elif kind == 'sources':
            items = []
            for item in block['items']:
                source_id = f' id="{self.claim_id(item["id"])}"' if item.get('id') else ''
                label = plain(item['label'])
                url = item.get('url', '')
                if urlparse(url).scheme.lower() in ('http', 'https'):
                    label = f'<a href="{plain(url)}">{label}</a>'
                items.append(f'<li{source_id}>{label}' + rich_field(item, 'text', 'report-note') + '</li>')
            body = '<ol class="report-source-list">' + ''.join(items) + '</ol>'
        elif kind == 'figure':
            figure, figure_id = verified_figure(self.base / block['spec'], self.base / block['bundle'])
            self.claim_id(figure_id)
            body = f'<div class="report-chart-scroll" role="region" aria-label="图表" tabindex="0">{figure}</div>'
        else:
            raise ValueError(f'未知内部元素 {kind}，请将内容映射到已有元素或设计 HTML 组件')
        return f'<div class="report-block report-{kind}"{ident}>{heading}{body}</div>'

    def render(self, document):
        title = plain(document['title'])
        meta = ''.join(f'<li>{plain(value)}</li>' for value in document.get('meta', []))
        hero = (rich_field(document, 'eyebrow', 'report-eyebrow') + f'<h1>{title}</h1>'
                + rich_field(document, 'subtitle', 'report-subtitle') + f'<ul class="report-meta">{meta}</ul>')
        body = self.blocks(document['blocks'])
        footer = rich_field(document, 'footer', 'report-note')
        return (f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>'
                '<link rel="stylesheet" href="report.css"><link rel="stylesheet" href="theme.css"></head><body>'
                f'<header class="report-hero">{hero}</header><main class="report-main">{body}</main>'
                f'<footer class="report-footer">{footer}</footer></body></html>')


def read_document(source):
    content = source.read_text(encoding='utf-8-sig')
    if source.suffix.lower() == '.json':
        data = json.loads(content)
        if not isinstance(data, dict) or 'blocks' not in data or 'title' not in data:
            raise ValueError('这是业务 JSON。Agent 请先读取 references/page-model.md，在工作区整理 title 和 blocks；保留原字段含义和内容，无需用户转换输入')
        return data
    heading = re.match(r'\s*# ([^\n]+)\n?', content)
    title = heading.group(1) if heading else source.stem
    body = content[heading.end():] if heading else content
    return {'title': title, 'blocks': [{'type': 'text', 'text': body}]}


def build(source, output, theme=None, theme_css=None):
    document = read_document(source)
    name = theme or document.get('theme', 'paper')
    if name not in ('paper', 'minimal'):
        raise ValueError('内置主题为 paper/minimal，自定义主题使用 --theme-css')
    style = theme_css or ROOT / 'assets/themes' / f'{name}.css'
    html = Page(source.resolve().parent).render(document)
    if output.exists():
        raise ValueError('输出目录已存在，请为本次修订选择新目录')
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.report-', dir=output.parent))
    try:
        (stage / 'index.html').write_text(html, encoding='utf-8')
        shutil.copyfile(ROOT / 'assets/report.css', stage / 'report.css')
        shutil.copyfile(style, stage / 'theme.css')
        stage.chmod(0o755)
        for file in stage.iterdir():
            file.chmod(0o644)
        stage.rename(output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return output / 'index.html'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--theme', choices=['paper', 'minimal'])
    parser.add_argument('--theme-css', type=Path)
    args = parser.parse_args()
    try:
        print(build(args.source, args.out, args.theme, args.theme_css))
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(f'report-rendering: {error}')
