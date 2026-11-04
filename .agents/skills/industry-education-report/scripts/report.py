#!/usr/bin/env python3
"""Validate evidence-linked reports, render Markdown, verify delivery integrity."""
import argparse
import datetime
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

QUERY = ROOT.parent / 'talent-data-query/scripts/query.mjs'
RESULT_PATH = re.compile(r'data/(tq-[a-f0-9-]+)/result\.json')

def inspect_source(source):
    """Use the shared skill's offline reader; it owns file and content verification."""
    match = RESULT_PATH.fullmatch(source['url'])
    if not match:
        raise ValueError('invalid talent result path')
    proc = subprocess.run(['node', str(QUERY), 'inspect', '--result', source['url'], '--full'],
                          capture_output=True, text=True, check=False)
    if proc.returncode:
        raise ValueError('shared inspect failed: ' + proc.stdout.strip()[:400])
    result = json.loads(proc.stdout)
    read_at = result['freshness']['dataReadAt']
    if (result['requestId'] != match[1] or result['contentHash'] != source.setdefault('contentHash', result['contentHash'])
            or read_at != source.setdefault('dataReadAt', read_at)):
        raise ValueError('query identity, content hash or read time mismatch')
    checks = result['quality']['checks']
    if (result['status'] not in ('complete', 'empty', 'partial') or not checks
            or not all(item['pass'] for item in checks) or not result['consistency']['completeTransaction']):
        raise ValueError('query failed consistency checks')
    source.setdefault('published', '未标注')
    source.setdefault('accessed', read_at[:10])
    return result

def distribution_detail(metric):
    groups = []
    rows = metric['rows']
    for i, row in enumerate(rows[:20]):
        labels = row.get('labels', {}).values()
        label = ' / '.join(str(v or '缺失') for v in labels) or row.get('label') or row.get('category')
        if not label or 'count' not in row or 'share' not in row:
            return None
        groups.append({'row': i, 'label': label, 'count': row['count'], 'share': row['share']})
    return {'denominator': metric['denominator'], 'returnedGroups': len(rows), 'groups': groups}

def bind_observation(result, observation):
    binding = observation['binding']
    metrics = {item['metricId']: item for item in result['metrics']}
    metric = metrics[binding['metricId']]
    if metric['status'] != 'complete' and not (
        metric['status'] == 'empty' and metric['name'] in ('positions.count', 'companies.count')
    ):
        raise ValueError('metric unavailable')
    field = binding['field']
    detail = None
    if field in ('rows', 'denominator') and metric.get('rows'):
        detail = distribution_detail(metric)
    if detail is not None:
        if observation.setdefault('breakdown', detail) != detail:
            raise ValueError('分组明细与已验结果不一致')
        field = 'denominator'
    elif 'breakdown' in observation or field == 'rows':
        raise ValueError('该指标不含可展示的分组计数，请绑定具体行的数值字段')
    path = field.split('.')
    if path[0] not in ('value', 'rows', 'denominator', 'validN', 'missingN', 'excludedN', 'otherCount'):
        raise ValueError('invalid metric field')
    value = metric
    for key in path:
        if isinstance(value, list):
            if not key.isdecimal():
                raise ValueError('invalid row index')
            value = value[int(key)]
        else:
            value = value[key]
    if type(value) not in (int, float):
        raise ValueError('需要数值字段，如 value.median 或 rows.0.count；每个要引用的分组建一项指标')
    return value

def validate(d):
    errors = []
    def check(ok, message):
        if not ok:
            errors.append(message)
    def fields(obj, names, label):
        for name in names:
            check(name in obj and obj[name] not in ('', None, []) and (not isinstance(obj[name], str) or bool(obj[name].strip())), f'{label}: missing {name}')
    fields(d, ['title','edition','region','industry','period','as_of','status'], 'report')
    check(d.get('status') in ['sample','draft','final'], 'invalid status')
    try:
        datetime.date.fromisoformat(d.get('as_of',''))
    except (ValueError, TypeError):
        errors.append('invalid as_of')
    templates = json.loads((ROOT / 'assets/templates.json').read_text())
    template = templates.get(d.get('edition'))
    check(template is not None, 'invalid edition')
    indexes = {}
    requirements = {
        'sources':['id','title','publisher','url','published','accessed','locator','scope','excerpt'],
        'metrics':['id','label','value','unit','period','region','population','definition','source_ids'],
        'claims':['id','kind','text','limitation'],
        'gaps':['id','description','owner','required_data','impact'],
        'charts':['id','title','metric_ids','note','type']}
    for group, required in requirements.items():
        items = d.get(group)
        check(isinstance(items,list), f'{group} must be array')
        idx = {}
        for obj in items if isinstance(items,list) else []:
            if not isinstance(obj,dict):
                errors.append(f'{group}: object required')
                continue
            if group not in ('metrics', 'sources'):
                fields(obj, required, group)
            key = obj.get('id')
            check(isinstance(key,str) and bool(key), f'{group}: invalid id')
            check(key not in idx, f'{group}: duplicate {key}')
            if isinstance(key,str):
                idx[key] = obj
        indexes[group] = idx
    def refs(obj, field, group):
        values = obj.get(field,[])
        check(isinstance(values,list), f'{obj.get("id")}: {field} must be array')
        if not isinstance(values,list):
            return []
        for key in values:
            check(isinstance(key,str) and key in indexes[group], f'{obj.get("id")}: unresolved {field} {key}')
        return values
    shared = {}
    for s in indexes['sources'].values():
        url = s.get('url', '')
        if isinstance(url,str) and url.startswith('data/'):
            try:
                result = inspect_source(s)
                shared[s['id']] = result
                check(datetime.date.fromisoformat(s['dataReadAt'][:10]) <= datetime.date.fromisoformat(d['as_of']),
                      f'{s["id"]}: query read after report cutoff')
                check(result['status'] != 'partial' or bool(indexes['gaps']), 'partial result requires a gap')
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append(f'{s["id"]}: {exc}')
        else:
            check(isinstance(url,str) and url.startswith(('https://','references/','assets/','uploads/','user:')), f'{s["id"]}: invalid source')
            if isinstance(url,str) and url.startswith('uploads/'):
                material = Path(url).resolve()
                check(material.is_relative_to(Path.cwd() / 'uploads') and material.is_file(),
                      f'{s["id"]}: missing uploaded material')
            check('contentHash' not in s and 'dataReadAt' not in s, f'{s["id"]}: shared source requires result path')
        fields(s, requirements['sources'], 'sources')
        try:
            accessed = datetime.date.fromisoformat(s.get('accessed',''))
            check(accessed <= datetime.date.fromisoformat(d['as_of']), f'{s["id"]}: access after cutoff')
            published = s.get('published','')
            if len(published)>=10 and published[:4].isdigit():
                check(datetime.date.fromisoformat(published[:10]) <= accessed, f'{s["id"]}: publication after access')
        except (ValueError,TypeError):
            errors.append(f'{s["id"]}: invalid accessed date')
    for m in indexes['metrics'].values():
        source_ids = refs(m,'source_ids','sources')
        bound = [sid for sid in source_ids if isinstance(sid,str) and sid in shared]
        if 'binding' in m or (bound and 'derived' not in m):
            try:
                if len(bound) != 1 or 'derived' in m:
                    raise ValueError('expected one shared source for a direct observation')
                if not isinstance(m.get('binding'), dict):
                    raise ValueError('缺少 binding，请填 metricId 和 field（如 value、rows.0.count）')
                expected = bind_observation(shared[bound[0]], m)
                check(m.setdefault('value', expected) == expected, f'{m["id"]}: value differs from query result')
            except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
                errors.append(f'{m["id"]}: invalid query binding ({exc})')
        if 'breakdown' in m and (not bound or 'binding' not in m):
            errors.append(f'{m["id"]}: unbound breakdown')
        fields(m, requirements['metrics'], 'metrics')
        value = m.get('value')
        check(type(value) in (int,float) and math.isfinite(value), f'{m["id"]}: nonfinite/nonnumeric value')
        if 'derived' in m:
            spec = m['derived']
            inputs = spec.get('inputs',[])
            valid = bool(inputs) and all(k in indexes['metrics'] and k != m['id'] for k in inputs)
            check(valid, f'{m["id"]}: invalid derivation inputs')
            if valid:
                ms = [indexes['metrics'][k] for k in inputs]
                check(all(all(x.get(k)==ms[0].get(k) for k in ['unit','region','period','population','price_basis','comparable_group']) for x in ms), f'{m["id"]}: incomparable derivation')
                try:
                    values = [x['value'] for x in ms]
                    op = spec.get('operation')
                    check(all(x.get('comparable_group') and x.get('price_basis') for x in ms), f'{m["id"]}: derivation needs comparable_group and price_basis')
                    check(all(m.get(k)==ms[0].get(k) for k in ['region','period','population','price_basis','comparable_group']), f'{m["id"]}: output scope mismatch')
                    expected_unit = ms[0].get('unit') if op=='sum' else '%' if op=='percent' else '比值'
                    check(m.get('unit')==expected_unit, f'{m["id"]}: output unit mismatch')
                    expected = sum(values) if op=='sum' else values[0]/values[1]*(100 if op=='percent' else 1) if op in ['ratio','percent'] and len(values)==2 else None
                    check(expected is not None and math.isclose(value,expected,rel_tol=0.001,abs_tol=0.01), f'{m["id"]}: derivation mismatch')
                except (ZeroDivisionError,TypeError):
                    errors.append(f'{m["id"]}: invalid arithmetic')
    visiting, visited = set(), set()
    def visit(key):
        if key in visiting:
            errors.append(f'{key}: cyclic derivation')
            return
        if key in visited or key not in indexes['metrics']:
            return
        visiting.add(key)
        for dep in indexes['metrics'][key].get('derived',{}).get('inputs',[]):
            visit(dep)
        visiting.remove(key)
        visited.add(key)
    for key in indexes['metrics']:
        visit(key)
    for c in indexes['claims'].values():
        check(c.get('kind') in ['fact','inference','recommendation'], f'{c["id"]}: invalid kind')
        sr = refs(c,'source_ids','sources')
        mr = refs(c,'metric_ids','metrics')
        check(bool(sr or mr), f'{c["id"]}: unsupported claim')
    sections = d.get('sections',[])
    check(isinstance(sections,list), 'sections must be array')
    if not isinstance(sections,list):
        sections = []
    if template:
        check([x.get('id') for x in sections] == [x['id'] for x in template['sections']], 'template section order/coverage mismatch')
    used_claims, used_gaps, used_metrics = set(), set(), set()
    for s in sections:
        cs = refs(s,'claim_ids','claims')
        gs = refs(s,'gap_ids','gaps')
        check(bool(cs or gs), f'{s.get("id")}: empty section')
        used_claims.update(x for x in cs if isinstance(x,str))
        used_gaps.update(x for x in gs if isinstance(x,str))
    for c in indexes['claims'].values():
        used_metrics.update(x for x in c.get('metric_ids',[]) if isinstance(x,str))
    for c in indexes['charts'].values():
        check(c.get('type')=='table', f'{c["id"]}: unsupported chart type')
        used_metrics.update(refs(c,'metric_ids','metrics'))
    check(bool(indexes['charts']) or (not indexes['metrics'] and indexes['gaps'] and d.get('status') != 'final'),
          'at least one annotated chart/table required when reporting numbers')
    check(set(indexes['claims'])==used_claims, 'orphan claims')
    check(set(indexes['gaps'])==used_gaps, 'orphan gaps')
    check(set(indexes['metrics'])==used_metrics, 'orphan metrics')
    check(not (d.get('status')=='final' and indexes['gaps']), 'final report has unresolved gaps')
    return {'structure_pass':not errors,'registered_gaps':len(indexes['gaps']), 'decision_data_complete':False, 'completeness_review':'requires semantic review; absence of registered gaps does not establish completeness',
            'semantic_review':'required: verify original sources and claim entailment', 'errors':errors}

def scope_text(scope):
    # Earlier working reports sometimes carry the query's region or period object.
    if isinstance(scope, dict):
        if 'from' in scope or 'to' in scope:
            return f"平台更新时间 [{scope.get('from', '不限')}, {scope.get('to', '不限')})"
        if 'note' in scope:
            return str(scope['note'])
        if 'name' in scope:
            return ' '.join(dict.fromkeys(filter(None, (scope.get('province'), scope['name']))))
    return str(scope)

def render(d):
    template = json.loads((ROOT/'assets/templates.json').read_text())[d['edition']]
    indexes = {k:{x['id']:x for x in d[k]} for k in ['claims','gaps','metrics','sources']}
    out = [f'# {d["title"]}', '', f'区域：{scope_text(d["region"])}｜产业：{scope_text(d["industry"])}｜时间窗/基期：{scope_text(d["period"])}｜数据时点：{d["as_of"]}', '',
           f'状态：{d["status"]}；模板：{template["name"]}（研究改编）。',
           '数据完备性：存在缺口，不能直接用于审批。' if d['gaps'] else '数据完备性：无登记缺口；仍需语义审核。','']
    def citation(source, label):
        url = source['url']
        if url.startswith(('data/', 'uploads/', 'user:')):
            return label
        return f'[{label}]({url})'
    for spec,section in zip(template['sections'],d['sections']):
        out += [f'## {spec["title"]}', '']
        for cid in section['claim_ids']:
            c = indexes['claims'][cid]
            sources = list(c.get('source_ids',[]))
            for mid in c.get('metric_ids',[]):
                sources.extend(indexes['metrics'][mid]['source_ids'])
            links = ' '.join(citation(indexes["sources"][sid], sid) for sid in dict.fromkeys(sources))
            out += [f'- **{cid} · {c["kind"]}**：{c["text"]} {links}', f'  - 适用限制：{c["limitation"]}', '']
        for gid in section['gap_ids']:
            g = indexes['gaps'][gid]
            out += [f'- **{gid} · 数据缺口**：{g["description"]}；取数责任：{g["owner"]}；待取：{g["required_data"]}；影响：{g["impact"]}', '']
    def cell(s):
        return str(s).replace('|','\\|').replace('\n',' ')
    if d['charts']:
        out += ['## 图表与统计口径','']
    for chart in d['charts']:
        out += [f'### {chart["id"]} {chart["title"]}', '', '| 指标 | 数值 | 单位 | 时期 | 地域 | 统计对象与定义 | 来源 |','|---|---:|---|---|---|---|---|']
        for mid in chart['metric_ids']:
            m = indexes['metrics'][mid]
            out.append('| '+' | '.join(cell(x) for x in [m['label'],m['value'],m['unit'],scope_text(m['period']),scope_text(m['region']),m['population']+'；'+m['definition'],','.join(m['source_ids'])])+' |')
        out += ['',f'图表说明：{chart["note"]}', '']
    for m in d['metrics']:
        if 'breakdown' not in m:
            continue
        detail = m['breakdown']
        groups = detail['groups']
        out += [f'### {m["label"]} · 分组明细', '',
                '| 分组 | 记录数 | 占比 |', '|---|---:|---:|']
        for row in groups:
            share = '未计算' if row['share'] is None else f"{row['share']:.1%}"
            out.append(f'| {cell(row["label"])} | {row["count"]} | {share} |')
        out += ['', f'分母 {detail["denominator"]} 条。列出结果返回的 {detail["returnedGroups"]} 组中的 {len(groups)} 组。来源 {", ".join(m["source_ids"])} / {m["binding"]["metricId"]}。', '']
    out += ['## 来源附录','']
    for s in d['sources']:
        out += [f'- **{s["id"]}** {citation(s, s["title"])}；发布机构：{s["publisher"]}；发布：{s["published"]}；访问：{s["accessed"]}；定位：{s["locator"]}；范围：{s["scope"]}；证据摘记：{s["excerpt"]}', '']
        if 'contentHash' in s:
            out += [f'  统计结果 {s["url"].split("/")[1]} · {s["dataReadAt"]} · {s["contentHash"]}', '']
            for m in d['metrics']:
                if s['id'] in m['source_ids'] and 'binding' in m:
                    out.append(f'  {m["id"]}：{m["binding"]["metricId"]} / {m["binding"]["field"]}')
            out.append('')
    return '\n'.join(out)+'\n'

def build_delivery(d, validation, review):
    """Publish one complete revision. The previous manifest survives a failed build."""
    if not review.strip():
        raise ValueError('review.md is empty')
    missing = [c['id'] for c in d['claims']
               if not re.search(r'(?<![\w-])' + re.escape(c['id']) + r'(?![\w-])', review, flags=re.ASCII)]
    if missing:
        raise ValueError('review.md 缺少这些结论的复核记录：' + '、'.join(missing))
    output = Path('output')
    if output.is_symlink():
        raise ValueError('output cannot be a symlink')
    try:
        output.mkdir()
        output.chmod(0o2750)
    except FileExistsError:
        if not output.is_dir():
            raise
    folder = Path(tempfile.mkdtemp(prefix='report-', dir=output)).resolve().relative_to(Path.cwd())
    try:
        # Both the sandbox writer and the delivery service belong to the workspace group.
        workspace_group = Path.cwd().stat().st_gid
        if folder.stat().st_gid != workspace_group:
            os.chown(folder, -1, workspace_group)
        folder.chmod(0o2750)
        files = []
        for filename, label, content in [
            ('report.md', '报告正文', render(d)),
            ('report.json', '结构化报告', json.dumps(d, ensure_ascii=False, indent=2)),
            ('validation.json', '结构验收', json.dumps(validation, ensure_ascii=False, indent=2)),
            ('review.md', '证据复核', review),
        ]:
            path = folder / filename
            path.write_text(content, encoding='utf-8')
            path.chmod(0o640)
            files.append({'name': label, 'path': str(path)})
        manifest = folder / 'delivery.tmp'
        manifest.write_text(json.dumps({'files': files}, ensure_ascii=False), encoding='utf-8')
        manifest.chmod(0o640)
        manifest.replace('delivery.json')
    except BaseException:
        shutil.rmtree(folder)
        raise
    return folder

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['validate','render','verify','build'])
    p.add_argument('report',type=Path)
    p.add_argument('rendered',type=Path,nargs='?')
    p.add_argument('--output',type=Path)
    p.add_argument('--review',type=Path,default=Path('review.md'))
    a = p.parse_args()
    try:
        d = json.loads(a.report.read_text())
        result = validate(d)
        if a.command=='validate':
            output = json.dumps(result,ensure_ascii=False,indent=2)+'\n'
        elif not result['structure_pass']:
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 1
        elif a.command=='build':
            print(build_delivery(d, result, a.review.read_text()))
            return 0
        elif a.command=='render':
            output = render(d)
        else:
            if a.rendered is None:
                p.error('verify requires rendered Markdown path')
            ok = a.rendered.read_text()==render(d)
            output = json.dumps({'delivery_matches_validated_report':ok},indent=2)+'\n'
            result['structure_pass'] = ok
        if a.output:
            with a.output.open('x') as f:
                f.write(output)
        else:
            print(output,end='')
        return 0 if result['structure_pass'] else 1
    except (OSError,ValueError,TypeError,KeyError,AttributeError) as e:
        print(f'ERROR: {e}',file=sys.stderr)
        return 2

if __name__=='__main__':
    sys.exit(main())
