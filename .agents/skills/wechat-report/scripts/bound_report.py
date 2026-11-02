"""Report-side projections and evidence binding. No database/query implementation."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

# Typed facts keep both the wording's subject and its input fields stable.
CLAIMS = {
    'overview': ('本次样本覆盖 {n} 条在招岗位记录，关联 {c} 家企业。', {'n': '/total/positions', 'c': '/total/companies'}),
    'cities': ('完整样本可归属 {n} 个省市组合；图表展示数量靠前的城市。', {'n': '/total/cities'}),
    'categories': ('各类别统计使用同一组 {n} 条岗位记录，缺失与未知类别单独保留。', {'n': '/total/positions'}),
    'salary': ('共有 {n} 条记录符合薪酬有效性规则，中位数为 {m} K/月。', {'n': '/salary/valid', 'm': '/salary/median'}),
    'skills': ('技能统计基于 {n} 条有描述的岗位记录；同一岗位可提及多个词。', {'n': '/skill_described_n'}),
    'vocational': ('学历与经验条件同时满足所列规则的岗位有 {n} 条，占总体 {p}%。', {'n': '/voc_pool/count', 'p': '/voc_pool/pct'}),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pointer(obj, path):
    for key in path.strip('/').split('/') if path else []:
        key = key.replace('~1', '/').replace('~0', '~')
        obj = obj[int(key)] if isinstance(obj, list) else obj[key]
    return obj


def load_data(path, demo=False):
    path = Path(path).resolve()
    data = json.loads(path.read_text('utf-8'))
    if data.get('schema') != 'wechat-report-data/2':
        if demo:
            data.setdefault('meta', {})['demo'] = True
            return data, None
        raise ValueError('真实报告只接受共享查询适配结果；离线样例须显式 --demo')
    binding_path = path.with_name('report_binding.json' if path.name == 'report_data.json' else path.name + '.binding.json')
    binding = json.loads(binding_path.read_text('utf-8'))
    if binding.get('schema') != 'wechat-report-binding/1' or digest(path.read_bytes()) != binding['reportDataSha256']:
        raise ValueError('报告数据与绑定指纹不一致')
    source = (path.parent / binding['source']['result']).resolve()
    manifest_path = (path.parent / binding['source']['manifest']).resolve()
    root = Path.cwd().resolve()
    if not source.is_relative_to(root) or not manifest_path.is_relative_to(root):
        raise ValueError('来源工件必须位于当前会话工作区')
    if digest(manifest_path.read_bytes()) != binding['source']['manifestSha256']:
        raise ValueError('来源清单已改变')
    manifest = json.loads(manifest_path.read_text('utf-8'))
    required = {'result.json', 'evidence.json', 'summary.md'}
    if not required.issubset({f['name'] for f in manifest['files']}):
        raise ValueError('来源清单不完整')
    for f in manifest['files']:
        target = (manifest_path.parent / f['name']).resolve()
        if target.parent != manifest_path.parent or digest(target.read_bytes()) != f['sha256'] or target.stat().st_size != f['bytes']:
            raise ValueError('来源工件缺失或指纹不一致')
    result = json.loads(source.read_text('utf-8'))
    if result['contentHash'] != binding['source']['contentHash'] or manifest['contentHash'] != result['contentHash']:
        raise ValueError('来源内容指纹不一致')
    adapter = Path(__file__).with_name('adapt_query_result.mjs')
    checked = subprocess.run(['node', str(adapter), str(source), json.dumps(binding.get('options', {}), ensure_ascii=False)], check=True, capture_output=True, text=True)
    rebuilt = json.loads(checked.stdout)
    if rebuilt['data'] != data or rebuilt['fieldMetrics'] != binding['fields']:
        raise ValueError('报告数据或字段映射不符合共享结果')
    binding['_result'] = result
    binding['_source'] = source
    binding['_data_file_sha256'] = digest(path.read_bytes())
    return data, binding


def project(data, spec):
    value = pointer(data, spec['path'])
    op = spec.get('op', 'value')
    limit = spec.get('limit', 10)
    if op == 'number':
        return '未提供' if value is None else format(value, ',')
    if op == 'name_count':
        return [[r['name'], r['count']] for r in value[:limit]]
    if op == 'pairs':
        return value[:limit]
    if op == 'city_track_table':
        return [[r.get('city') or '城市缺失', r['label'], r['count']] for r in sorted(value, key=lambda r: -r['count'])[:limit]]
    if op == 'track_salary_table':
        return [[r['name'], r['valid'], r['median'] if r['median'] is not None else '未提供'] for r in sorted(value, key=lambda r: -r['count'])[:limit]]
    if op == 'requirements_table':
        return sorted(value, key=lambda r: -r[2])[:limit]
    if op == 'skill_matrix':
        tracks = list(dict.fromkeys(r['label'] for r in value))[:6]
        words = {}
        for r in value:
            words[r['skill']] = words.get(r['skill'], 0) + r['count']
        cols = sorted(words, key=lambda w: -words[w])[:8]
        lookup = {(r['label'], r['skill']): r for r in value}
        return {'kind': 'heatmap', 'caption': '方向内技能提及率（%）', 'rows': tracks, 'cols': cols, 'cells': [[i, j, round((lookup.get((t, w), {}).get('share') or 0)*100, 2)] for i, t in enumerate(tracks) for j, w in enumerate(cols)]}
    if op == 'lq_table':
        totals, tracks, cells = {}, {}, {}
        for r in value:
            tracks[r['track']] = tracks.get(r['track'], 0)+r['count']
            if r.get('city') and r.get('province'):
                city = r['province']+'·'+r['city']
                totals[city] = totals.get(city, 0)+r['count']
                key = (city, r['track'], r['label'])
                cells[key] = cells.get(key, 0)+r['count']
        n = sum(tracks.values())
        rows = [[city, label, round((v/totals[city])/(tracks[track]/n), 3)] for (city, track, label), v in cells.items() if n and totals[city] and tracks[track]]
        return sorted(rows, key=lambda r: -r[2])[:limit]
    if op == 'template':
        return spec['template'].format(**{k: project(data, s) for k, s in spec['inputs'].items()})
    if op == 'claim':
        template, fields = CLAIMS[spec['claim']]
        if {key: v['path'] for key, v in spec['inputs'].items()} != fields:
            raise ValueError('量化事实的对象与输入指标不匹配')
        return template.format(**{key: project(data, dict(path=path, op='number')) for key, path in fields.items()})
    if op != 'value':
        raise ValueError('未知报告投影 '+op)
    return value


def verify_outline(data, binding, outline):
    if outline.get('source_data_sha256') != binding['_data_file_sha256'] or outline.get('source_content_hash') != binding['source']['contentHash']:
        raise ValueError('大纲绑定了其他数据版本')
    refs = outline.get('bindings', {})
    if not refs:
        raise ValueError('大纲没有指标绑定')
    ids = {m['metricId'] for m in binding['_result']['metrics']}
    for path, spec in refs.items():
        if pointer(outline, path) != project(data, spec):
            raise ValueError('大纲内容与指标不符：'+path)
        if not spec.get('metricIds') or not set(spec['metricIds']).issubset(ids):
            raise ValueError('大纲指标引用无效：'+path)
        source_paths = [spec['path']]+[v['path'] for v in spec.get('inputs', {}).values()]
        expected = []
        for source_path in source_paths:
            matches = [k for k in binding['fields'] if source_path == k or source_path.startswith(k+'/')]
            if matches:
                expected += binding['fields'][max(matches, key=len)]
        if sorted(set(expected) or {'all/positions.count'}) != sorted(spec['metricIds']):
            raise ValueError('指标引用与来源字段不一致：'+path)
    # Every quantitative paragraph/stat/chart must carry a specific projection.
    for i, screen in enumerate(outline['screens']):
        for j, text in enumerate(screen.get('paragraphs', [])):
            if re.search(r'\d', text):
                ref = refs.get('/screens/%d/paragraphs/%d' % (i, j))
                if not ref or ref.get('op') != 'claim':
                    raise ValueError('量化正文缺少类型明确的事实引用')
        for key in ('chart', 'chart2', 'chartA', 'chartB'):
            c = screen.get(key)
            if c and not any(p == '/screens/%d/%s' % (i, key) or p.startswith('/screens/%d/%s/' % (i, key)) for p in refs):
                raise ValueError('图表缺少指标引用')
    return True
