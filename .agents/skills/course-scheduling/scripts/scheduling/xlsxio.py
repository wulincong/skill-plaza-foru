"""极简 xlsx 读写：zipfile + ElementTree，覆盖模板与导出所需的单元格能力。

写入支持字符串/数字单元格与列宽；读取支持 sharedStrings、inlineStr、
缓存公式值与数值。超出该范围的复杂工作簿会抛 XlsxError，
此时引导用户改用 CSV 模板。
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS_MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
NS_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS_PKG_REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
NS_TYPES = 'http://schemas.openxmlformats.org/package/2006/content-types'

ILLEGAL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


class XlsxError(Exception):
    pass


def _clean(text) -> str:
    return ILLEGAL_CHARS.sub('', str(text if text is not None else ''))


def _escape(text: str) -> str:
    return (_clean(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def _col_letter(index: int) -> str:
    result = ''
    while index > 0:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result


def sanitize_sheet_name(name: str) -> str:
    cleaned = re.sub(r'[\\/*?:\[\]]', '-', str(name)).strip() or 'Sheet'
    return cleaned[:31]


def write_xlsx(path, sheets: list[dict]):
    """sheets: [{name, rows: [[cell...]], widths: [数字...] }]，cell 为 str/int/float/None。"""
    path = Path(path)
    if path.exists():
        raise XlsxError(f'{path} 已存在；请输出到新文件。')
    files: dict[str, str] = {}

    sheet_tags = []
    rel_tags = []
    content_overrides = []
    for i, sheet in enumerate(sheets, 1):
        name = sanitize_sheet_name(sheet['name'])
        sheet_tags.append(
            f'<sheet name="{_escape(name)}" sheetId="{i}" r:id="rId{i}"/>')
        rel_tags.append(
            f'<Relationship Id="rId{i}" Type="{NS_REL}/worksheet" Target="worksheets/sheet{i}.xml"/>')
        content_overrides.append(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
            f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        files[f'xl/worksheets/sheet{i}.xml'] = _render_sheet(sheet)

    files['[Content_Types].xml'] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Types xmlns="{NS_TYPES}">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        + ''.join(content_overrides) + '</Types>')
    files['_rels/.rels'] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{NS_PKG_REL}">'
        '<Relationship Id="rId1" '
        f'Type="{NS_REL}/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>')
    files['xl/workbook.xml'] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{NS_MAIN}" xmlns:r="{NS_REL}"><sheets>'
        + ''.join(sheet_tags) + '</sheets></workbook>')
    files['xl/_rels/workbook.xml.rels'] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{NS_PKG_REL}">'
        + ''.join(rel_tags)
        + f'<Relationship Id="rId{len(sheets) + 1}" Type="{NS_REL}/styles" Target="styles.xml"/>'
        '</Relationships>')
    files['xl/styles.xml'] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<styleSheet xmlns="{NS_MAIN}">'
        '<fonts count="2"><font><sz val="11"/><name val="等线"/></font>'
        '<font><b/><sz val="11"/><name val="等线"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf/></cellStyleXfs>'
        '<cellXfs count="2"><xf/><xf fontId="1" applyFont="1"/></cellXfs>'
        '</styleSheet>')

    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)


def _render_sheet(sheet: dict) -> str:
    rows = sheet.get('rows') or []
    widths = sheet.get('widths') or []
    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             f'<worksheet xmlns="{NS_MAIN}">']
    if widths:
        cols = ''.join(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>'
                       for i, w in enumerate(widths, 1))
        parts.append(f'<cols>{cols}</cols>')
    parts.append('<sheetData>')
    for r, row in enumerate(rows, 1):
        cells = []
        for c, value in enumerate(row, 1):
            if value is None or value == '':
                continue
            ref = f'{_col_letter(c)}{r}'
            style = ' s="1"' if r == 1 else ''
            if isinstance(value, bool):
                cells.append(f'<c r="{ref}" t="b"{style}><v>{1 if value else 0}</v></c>')
            elif isinstance(value, (int, float)):
                number = repr(value) if isinstance(value, float) else str(value)
                cells.append(f'<c r="{ref}"{style}><v>{number}</v></c>')
            else:
                text = _escape(str(value))
                cells.append(f'<c r="{ref}" t="inlineStr"{style}>'
                             f'<is><t xml:space="preserve">{text}</t></is></c>')
        if cells:
            parts.append(f'<row r="{r}">' + ''.join(cells) + '</row>')
    parts.append('</sheetData></worksheet>')
    return ''.join(parts)


def read_xlsx(path) -> dict[str, list[list]]:
    """返回 {sheet 名: 行列表}；单元格为 str / int / float / ''。"""
    try:
        zf = zipfile.ZipFile(Path(path))
    except zipfile.BadZipFile as exc:
        raise XlsxError(f'{path} 不是有效的 xlsx 文件，请改用 CSV 模板。') from exc
    with zf:
        names = set(zf.namelist())
        if 'xl/workbook.xml' not in names:
            raise XlsxError(f'{path} 缺少工作簿结构，无法读取。')
        shared = _read_shared_strings(zf)
        rel_map = _read_workbook_rels(zf)
        wb = ET.fromstring(zf.read('xl/workbook.xml'))
        result: dict[str, list[list]] = {}
        for sheet in wb.find(f'{{{NS_MAIN}}}sheets'):
            rid = sheet.get(f'{{{NS_REL}}}id')
            target = rel_map.get(rid)
            if not target:
                continue
            part = 'xl/' + target.lstrip('/') if not target.startswith('xl/') else target
            if part not in names:
                continue
            result[sheet.get('name') or f'Sheet{len(result) + 1}'] = _read_sheet(
                zf.read(part), shared)
        return result


def _read_shared_strings(zf) -> list[str]:
    if 'xl/sharedStrings.xml' not in zf.namelist():
        return []
    root = ET.fromstring(zf.read('xl/sharedStrings.xml'))
    values = []
    for si in root.findall(f'{{{NS_MAIN}}}si'):
        values.append(''.join(t.text or '' for t in si.iter(f'{{{NS_MAIN}}}t')))
    return values


def _read_workbook_rels(zf) -> dict[str, str]:
    if 'xl/_rels/workbook.xml.rels' not in zf.namelist():
        return {}
    root = ET.fromstring(zf.read('xl/_rels/workbook.xml.rels'))
    return {rel.get('Id'): rel.get('Target') for rel in root}


def _ref_to_index(ref: str) -> tuple[int, int]:
    m = re.fullmatch(r'([A-Z]+)(\d+)', ref)
    if not m:
        return (0, 0)
    col = 0
    for ch in m.group(1):
        col = col * 26 + (ord(ch) - 64)
    return (int(m.group(2)) - 1, col - 1)


def _convert(text: str):
    if text == '':
        return ''
    try:
        number = float(text)
    except ValueError:
        return text
    if number.is_integer() and '.' not in text and 'e' not in text.lower():
        return int(number)
    return number


def _read_sheet(data: bytes, shared: list[str]) -> list[list]:
    root = ET.fromstring(data)
    grid: dict[tuple[int, int], object] = {}
    max_row = max_col = 0
    for cell in root.iter(f'{{{NS_MAIN}}}c'):
        row, col = _ref_to_index(cell.get('r') or '')
        if row < 0:
            continue
        kind = cell.get('t')
        value = ''
        if kind == 's':
            v = cell.find(f'{{{NS_MAIN}}}v')
            if v is not None and v.text is not None:
                try:
                    value = shared[int(v.text)]
                except (ValueError, IndexError):
                    value = v.text
        elif kind == 'inlineStr':
            is_node = cell.find(f'{{{NS_MAIN}}}is')
            if is_node is not None:
                value = ''.join(t.text or '' for t in is_node.iter(f'{{{NS_MAIN}}}t'))
        elif kind == 'str':
            v = cell.find(f'{{{NS_MAIN}}}v')
            value = v.text if v is not None and v.text is not None else ''
        elif kind == 'b':
            v = cell.find(f'{{{NS_MAIN}}}v')
            value = (v.text == '1') if v is not None else False
        else:
            v = cell.find(f'{{{NS_MAIN}}}v')
            if v is not None and v.text is not None:
                value = _convert(v.text)
        grid[(row, col)] = value
        max_row = max(max_row, row)
        max_col = max(max_col, col)
    rows: list[list] = []
    for r in range(max_row + 1):
        rows.append([grid.get((r, c), '') for c in range(max_col + 1)])
    return rows
