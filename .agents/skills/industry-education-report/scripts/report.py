#!/usr/bin/env python3
"""Validate evidence-linked reports, compose manuscript, verify delivery integrity."""
import argparse
import datetime
import hashlib
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

def session_context():
    file = Path('industry-report-input.json')
    return json.loads(file.read_text()) if file.is_file() else None

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
        'gaps':['id','description','owner','required_data','impact']}
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
    context = session_context()
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
                if context:
                    allowed = url in context['uploads'] and material.is_relative_to(Path.cwd() / 'uploads') and material.is_file()
                    check(allowed, f'{s["id"]}: 没有这份用户上传的附件，粘贴材料应引用 user: 来源')
                    if allowed and material.suffix.lower() in ('.txt', '.md'):
                        excerpt = ' '.join(str(s.get('excerpt','')).split())
                        check(excerpt and excerpt in ' '.join(material.read_text(encoding='utf-8-sig').split()),
                              f'{s["id"]}: excerpt 不在上传文件原文中')
            if context and isinstance(url, str) and url.startswith('user:'):
                excerpt = ' '.join(str(s.get('excerpt', '')).split())
                messages = [context['message'], *context['earlierMessages']]
                check(excerpt and any(excerpt in ' '.join(msg.split()) for msg in messages),
                      f'{s["id"]}: excerpt 须逐字引用用户给出的具体原句或片段')
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
    brief = d.get('edition') == 'decision'
    decision = d.get('decision')
    if brief or decision is not None:
        if isinstance(decision, dict):
            for name in ('reader','question'):
                check(isinstance(decision.get(name),str) and decision[name].strip(), f'decision: missing {name}')
            check(isinstance(decision.get('critical_gap_ids'),list), 'decision: declare critical_gap_ids')
            critical = refs(decision,'critical_gap_ids','gaps')
            check(bool(critical or used_claims), 'decision: no supported answer or identified critical gap')
            if sections:
                check(bool(sections[0].get('claim_ids') or critical), '摘要须回答决策问题或指明关键缺口')
            for section in sections:
                key = section.get('id','')
                if key == 'D02' or 'S02' <= key <= 'S12':
                    for cid in section.get('claim_ids', []):
                        if cid in indexes['claims']:
                            for name in ('basis','implication'):
                                part = indexes['claims'][cid].get(name)
                                check(isinstance(part,str) and part.strip(), f'{cid}: missing {name}')
        else:
            errors.append('decision: reader, question and critical_gap_ids required')
    for c in indexes['claims'].values():
        used_metrics.update(x for x in c.get('metric_ids',[]) if isinstance(x,str))
    check(set(indexes['claims'])==used_claims, 'orphan claims')
    check(set(indexes['gaps'])==used_gaps, 'orphan gaps')
    check(set(indexes['metrics'])==used_metrics, 'orphan metrics')
    blocking = decision.get('critical_gap_ids') if isinstance(decision,dict) else indexes['gaps']
    check(not (d.get('status') == 'final' and blocking), 'final report has unresolved decision gaps')
    result = {'structure_pass': not errors, 'registered_gaps': len(indexes['gaps']),
              'decision_data_complete': False, 'completeness_review': 'requires semantic review; absence of registered gaps does not establish completeness',
              'semantic_review': 'required: verify original sources and claim entailment', 'errors': errors}
    if isinstance(decision, dict):
        result['critical_gap_ids'] = decision.get('critical_gap_ids')
        # Absence of a declared blocker does not certify completeness.
        if not result['critical_gap_ids']:
            result['decision_data_complete'] = None
    return result

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

def compose_markdown(d):
    template = json.loads((ROOT/'assets/templates.json').read_text())[d['edition']]
    indexes = {k:{x['id']:x for x in d[k]} for k in ['claims','gaps','metrics','sources']}
    out = [f'# {d["title"]}', '', f'区域：{scope_text(d["region"])}｜产业：{scope_text(d["industry"])}｜时间窗/基期：{scope_text(d["period"])}｜数据时点：{d["as_of"]}', '',
           f'状态：{d["status"]}；模板：{template["name"]}（研究改编）。',
           '数据完备性：存在缺口，不能直接用于审批。' if d['gaps'] else '数据完备性：无登记缺口；仍需语义审核。','']
    decision = d.get('decision')
    if decision:
        out = [f'# {d["title"]}', '', f'{decision["reader"]} · {decision["question"]}', '',
               f'{scope_text(d["region"])}｜{scope_text(d["industry"])}｜{scope_text(d["period"])}｜截至 {d["as_of"]}', '']
        if decision['critical_gap_ids']:
            out += ['本报告按现有材料作答。以下决定仍需补证：', '']
            for key in decision['critical_gap_ids']:
                out += [f'- {indexes["gaps"][key]["impact"]}', '']
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
            if decision:
                parts = [part.strip() for part in [c['text'], c.get('basis'), c.get('implication')] if part and part.strip()]
                paragraph = ' '.join(part if re.search(r'[。！？.!?；;：:][”’」）)]?$',part) else part + '。' for part in parts)
                kind = {'fact':'事实','inference':'推断','recommendation':'建议'}[c['kind']]
                out += [f'{paragraph} 〔{kind} · {cid} · {links}〕', f'适用条件：{c["limitation"]}', '']
                continue
            out += [f'- **{cid} · {c["kind"]}**：{c["text"]} {links}', f'  - 适用限制：{c["limitation"]}', '']
        for gid in section['gap_ids']:
            g = indexes['gaps'][gid]
            if decision:
                out += [f'{g["description"]}。{g["owner"]}需补充{g["required_data"]}。{g["impact"]} 〔{gid}〕', '']
                continue
            out += [f'- **{gid} · 数据缺口**：{g["description"]}；取数责任：{g["owner"]}；待取：{g["required_data"]}；影响：{g["impact"]}', '']
    def cell(s):
        return str(s).replace('|','\\|').replace('\n',' ')
    if d['metrics']:
        out += ['## 指标与统计口径', '', '| 指标 | 数值 | 单位 | 时期 | 地域 | 统计对象与定义 | 来源 |','|---|---:|---|---|---|---|---|']
        for m in d['metrics']:
            out.append('| '+' | '.join(cell(x) for x in [m['label'],m['value'],m['unit'],scope_text(m['period']),scope_text(m['region']),m['population']+'；'+m['definition'],','.join(m['source_ids'])])+' |')
        out.append('')
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

def decision_scope(d):
    decision = d['decision']
    critical = set(decision['critical_gap_ids'])
    evidence = sorted((s['id'], s['scope'], s['locator'], s['excerpt'], s.get('contentHash','')) for s in d['sources'])
    return (decision['reader'], decision['question'], d['region'], d['industry'], d['period'], evidence,
            sorted((g['id'], g['description'], g['required_data'], g['impact']) for g in d['gaps'] if g['id'] in critical))

def chose_limited(message, quote, offered, option=None):
    """Only an affirmative user choice can release a limited report; citing a phrase cannot."""
    message = message.strip()
    quote = quote.strip()
    if not quote or quote not in message or re.search(r'不要.{0,8}继续|不(?:同意|按|选|希望).{0,10}继续|暂[不缓]|先别|别继续|[?？]', message):
        return False
    if re.search(r'取消(?:刚才|选择|继续)|撤回|等.{0,12}再(?:写|出|继续)|(?:改为|改选|先)(?:先)?(?:补充材料|扩大范围|扩围)|(?:^|[，,。；;：:\s])(?:我(?:选择|选|要)|请)?(?:先|改为|还是|只)?(?:补充材料|扩大范围|扩围|等.{0,12}再(?:写|出|继续))', message):
        return False
    # Permit the named option, optionally followed by the requested limitations.
    # A short free reply such as “继续” only has a definite referent after the offer.
    lead = re.split(r'[，,。；;！!\n]', message, maxsplit=1)[0].strip()
    if offered and type(option) is int and 1 <= option <= 12:
        identifiers = (str(option), chr(64 + option), '选项' + str(option), '第' + str(option) + '项')
        if lead.upper() in identifiers and lead in quote:
            return True
    affirmative = re.fullmatch(r'(?:我(?:选择|选|同意)|请|就)?(按(?:现有证据|已有材料|现有材料)继续)(?:生成|出具|写)?(?:报告|简报)?', lead)
    if affirmative:
        return affirmative.group(1) in quote
    return offered and lead in ('继续','继续生成','继续出稿','同意继续') and lead in quote

def cosmetic_revision(message):
    # Reuse approval for an explicitly editorial request only. A new decision
    # or a request to wait must never inherit permission from an older download.
    edit = r'(?:改|修改|调整|润色)(?:一下)?(?:报告)?(?:标题|措辞|排版|格式)'
    title = r'[^。！？?；;，,\n]{1,100}'
    rename = r'(?:把|将)(?:报告)?标题改(?:成|为)' + title
    return bool(re.fullmatch(r'(?:请|仅|只)?(?:帮我)?(?:' + edit + r'(?:(?:为|成)' + title + ')?|' + rename + r')[。！]?', message.strip()))

def check_release(d, reply_file=None):
    context = session_context()
    decision = d.get('decision')
    if decision is None:
        if context is not None:
            raise ValueError('本轮报告须填写 decision，先判断原范围内证据能否回答核心问题')
        return  # Standalone observation reports predate the decision field.
    if not decision['critical_gap_ids']:
        if context:
            message = context['message']
            chose_partial = chose_limited(message, message, context['offered'], context.get('continueOption'))
            if chose_partial and (context['offered'] or '未决' in message):
                raise ValueError('用户选择保留未决事项；把仍影响本决定的 gaps ID 填入 decision.critical_gap_ids')
            # Changing only the title does not resolve any previously declared blocker.
            if cosmetic_revision(message):
                prior = previous_decision(context)
                if prior and prior['decision']['critical_gap_ids']:
                    raise ValueError('文字修订须保留上一版的关键缺口与用户选择')
        return
    quote = decision.get('continue_quote', '')
    if not isinstance(quote, str) or not quote.strip():
        raise ValueError('关键缺证：说明影响并等待用户选择，不能构建报告')
    if context is not None:
        if chose_limited(context['message'], quote, context['offered'], context.get('continueOption')):
            return
        if not cosmetic_revision(context['message']):
            raise ValueError('关键缺证：需要用户明确选择按现有证据继续，补证或扩围后须重新评估')
    elif reply_file and chose_limited(reply_file.read_text(), quote, True):
        return
    else:
        raise ValueError('关键缺证：请用 --user-reply 提供用户明确继续的实际回复')
    # A cosmetic revision can reuse the last published decision in the same workspace.
    prior = previous_decision(context)
    if prior and prior['decision'].get('continue_quote') == quote and decision_scope(prior) == decision_scope(d):
        return
    raise ValueError('关键缺证：未找到用户对这项决定按现有证据继续的原话；请先等待回复')

def previous_decision(context):
    prior_run = context.get('previousBuildRun')
    if not prior_run or not re.fullmatch(r'[0-9]{8}-[0-9]{6}-[a-z0-9]+', prior_run):
        return None
    manifest = Path(f'industry-build-{prior_run}.json')
    if manifest.is_file():
        for item in json.loads(manifest.read_text()).get('files', []):
            if item.get('name') != '结构化报告' or not re.fullmatch(r'output/report-[\w-]+/report\.json', item['path']):
                continue
            file = Path(item['path']).resolve()
            if file.is_relative_to(Path.cwd() / 'output') and file.is_file():
                content = file.read_bytes()
                if hashlib.sha256(content).hexdigest() == item.get('sha256'):
                    prior = json.loads(content)
                    if isinstance(prior.get('decision'), dict):
                        return prior
    return None

def build_delivery(d, validation, review, reply_file=None):
    """Publish one complete revision. The previous manifest survives a failed build."""
    check_release(d, reply_file)
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
    published = False
    try:
        # Both the sandbox writer and the delivery service belong to the workspace group.
        workspace_group = Path.cwd().stat().st_gid
        if folder.stat().st_gid != workspace_group:
            os.chown(folder, -1, workspace_group)
        folder.chmod(0o2750)
        files = []
        for filename, label, content in [
            ('report.md', '报告正文', compose_markdown(d)),
            ('report.json', '结构化报告', json.dumps(d, ensure_ascii=False, indent=2)),
            ('validation.json', '结构验收', json.dumps(validation, ensure_ascii=False, indent=2)),
            ('review.md', '证据复核', review),
        ]:
            path = folder / filename
            path.write_text(content, encoding='utf-8')
            path.chmod(0o640)
            if path.read_text(encoding='utf-8') != content:
                raise OSError(f'交付文件回读不一致：{filename}')
            files.append({'name': label, 'path': str(path), 'sha256': hashlib.sha256(content.encode('utf-8')).hexdigest()})
        manifest = folder / 'delivery.tmp'
        manifest.write_text(json.dumps({'files': files}, ensure_ascii=False), encoding='utf-8')
        manifest.chmod(0o640)
        context = session_context()
        run_id = context.get('runId') if context else None
        if run_id:
            if not re.fullmatch(r'[0-9]{8}-[0-9]{6}-[a-z0-9]+',run_id):
                raise ValueError('运行编号无效')
            receipt = folder / 'build.tmp'
            receipt.write_bytes(manifest.read_bytes())
            receipt.chmod(0o640)
        manifest.replace('delivery.json')
        published = True
        if run_id:
            receipt.replace(f'industry-build-{run_id}.json')
    except BaseException:
        # Once the public manifest points here, keep the complete revision even if registration failed.
        if not published:
            shutil.rmtree(folder)
        raise
    return folder

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['validate','preview','verify','build'])
    p.add_argument('report',type=Path)
    p.add_argument('manuscript',type=Path,nargs='?')
    p.add_argument('--output',type=Path)
    p.add_argument('--user-reply',type=Path,help='standalone build: file containing the actual user reply')
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
            print(build_delivery(d, result, a.review.read_text(), a.user_reply))
            return 0
        elif a.command=='preview':
            check_release(d, a.user_reply)
            output = compose_markdown(d)
        else:
            if a.manuscript is None:
                p.error('verify requires manuscript Markdown path')
            ok = a.manuscript.read_text()==compose_markdown(d)
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
