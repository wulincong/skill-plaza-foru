#!/usr/bin/env python3
"""Validate evidence-linked reports, render Markdown, verify delivery integrity."""
import argparse
import datetime
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

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
    for s in indexes['sources'].values():
        check(isinstance(s.get('url'),str) and (s['url'].startswith('https://') or s['url'].startswith(('references/','assets/'))), f'{s["id"]}: invalid URL')
        try:
            accessed = datetime.date.fromisoformat(s.get('accessed',''))
            check(accessed <= datetime.date.fromisoformat(d['as_of']), f'{s["id"]}: access after cutoff')
            published = s.get('published','')
            if len(published)>=10 and published[:4].isdigit():
                check(datetime.date.fromisoformat(published[:10]) <= accessed, f'{s["id"]}: publication after access')
        except (ValueError,TypeError):
            errors.append(f'{s["id"]}: invalid accessed date')
    for m in indexes['metrics'].values():
        value = m.get('value')
        check(type(value) in (int,float) and math.isfinite(value), f'{m["id"]}: nonfinite/nonnumeric value')
        refs(m,'source_ids','sources')
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
    check(bool(indexes['charts']), 'at least one annotated chart/table required')
    check(set(indexes['claims'])==used_claims, 'orphan claims')
    check(set(indexes['gaps'])==used_gaps, 'orphan gaps')
    check(set(indexes['metrics'])==used_metrics, 'orphan metrics')
    check(not (d.get('status')=='final' and indexes['gaps']), 'final report has unresolved gaps')
    return {'structure_pass':not errors,'registered_gaps':len(indexes['gaps']), 'decision_data_complete':False, 'completeness_review':'requires semantic review; absence of registered gaps does not establish completeness',
            'semantic_review':'required: verify original sources and claim entailment', 'errors':errors}

def render(d):
    template = json.loads((ROOT/'assets/templates.json').read_text())[d['edition']]
    indexes = {k:{x['id']:x for x in d[k]} for k in ['claims','gaps','metrics','sources']}
    out = [f'# {d["title"]}', '', f'区域：{d["region"]}｜产业：{d["industry"]}｜时间窗/基期：{d["period"]}｜数据时点：{d["as_of"]}', '',
           f'状态：{d["status"]}；模板：{template["name"]}（研究改编）。',
           '数据完备性：存在缺口，不能直接用于审批。' if d['gaps'] else '数据完备性：无登记缺口；仍需语义审核。','']
    for spec,section in zip(template['sections'],d['sections']):
        out += [f'## {spec["title"]}', '']
        for cid in section['claim_ids']:
            c = indexes['claims'][cid]
            sources = list(c.get('source_ids',[]))
            for mid in c.get('metric_ids',[]):
                sources.extend(indexes['metrics'][mid]['source_ids'])
            links = ' '.join(f'[{sid}]({indexes["sources"][sid]["url"]})' for sid in dict.fromkeys(sources))
            out += [f'- **{cid} · {c["kind"]}**：{c["text"]} {links}', f'  - 适用限制：{c["limitation"]}', '']
        for gid in section['gap_ids']:
            g = indexes['gaps'][gid]
            out += [f'- **{gid} · 数据缺口**：{g["description"]}；取数责任：{g["owner"]}；待取：{g["required_data"]}；影响：{g["impact"]}', '']
    def cell(s):
        return str(s).replace('|','\\|').replace('\n',' ')
    out += ['## 图表与统计口径','']
    for chart in d['charts']:
        out += [f'### {chart["id"]} {chart["title"]}', '', '| 指标 | 数值 | 单位 | 时期 | 地域 | 统计对象与定义 | 来源 |','|---|---:|---|---|---|---|---|']
        for mid in chart['metric_ids']:
            m = indexes['metrics'][mid]
            out.append('| '+' | '.join(cell(x) for x in [m['label'],m['value'],m['unit'],m['period'],m['region'],m['population']+'；'+m['definition'],','.join(m['source_ids'])])+' |')
        out += ['',f'图表说明：{chart["note"]}', '']
    out += ['## 来源附录','']
    for s in d['sources']:
        out += [f'- **{s["id"]}** [{s["title"]}]({s["url"]})；发布机构：{s["publisher"]}；发布：{s["published"]}；访问：{s["accessed"]}；定位：{s["locator"]}；范围：{s["scope"]}；证据摘记：{s["excerpt"]}', '']
    return '\n'.join(out)+'\n'

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['validate','render','verify'])
    p.add_argument('report',type=Path)
    p.add_argument('rendered',type=Path,nargs='?')
    p.add_argument('--output',type=Path)
    a = p.parse_args()
    try:
        d = json.loads(a.report.read_text())
        result = validate(d)
        if a.command=='validate':
            output = json.dumps(result,ensure_ascii=False,indent=2)+'\n'
        elif not result['structure_pass']:
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 1
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
