"""Build an evidence-bound outline from shared query aggregates."""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from bound_report import load_data, project, CLAIMS

from report_runtime import report_root
BASE = report_root(__file__)


def _build_skeleton(data, brand, binding=None):
    title = data['meta']['region']+data['meta']['industry']+'产业人才需求观察报告'
    ol = {'schema': 'wechat-outline/2', 'title': title, 'org': brand['org'],
          'generated_at': data['meta']['generated_at'], 'screens': [], 'bindings': {},
          'meta': {'data_source': '优才知路平台数据库', 'sample_n': data['total']['positions'],
                   'period': '平台在招记录；范围见附录'}}
    if binding:
        ol.update(source_data_sha256=binding['_data_file_sha256'],
                  source_content_hash=binding['source']['contentHash'])
    else:
        ol['demo'] = True

    def screen(**values):
        ol['screens'].append(values)
        return len(ol['screens'])-1

    def metric_ids(spec):
        paths = [spec['path']] + [v['path'] for v in spec.get('inputs', {}).values()]
        ids = []
        for path in paths:
            fields = binding['fields'] if binding else {}
            matches = [k for k in fields if path == k or path.startswith(k+'/')]
            if matches:
                ids += fields[max(matches, key=len)]
        return sorted(set(ids)) or ['all/positions.count']

    def bind(i, key, spec):
        spec = dict(spec, metricIds=metric_ids(spec))
        target = ol['screens'][i]
        parts = key.split('/')
        for part in parts[:-1]:
            target = target[int(part)] if isinstance(target, list) else target[part]
        if isinstance(target, list):
            target[int(parts[-1])] = project(data, spec)
        else:
            target[parts[-1]] = project(data, spec)
        ol['bindings']['/screens/%d/%s' % (i, key)] = spec

    def paragraph(i, text, inputs):
        s = ol['screens'][i]
        s.setdefault('paragraphs', []).append('')
        claim = next((key for key, (template, _) in CLAIMS.items() if template == text), None)
        if not claim:
            raise ValueError('量化句式需要注册为可校验的事实投影')
        bind(i, 'paragraphs/%d' % (len(s['paragraphs'])-1),
             {'path': '', 'op': 'claim', 'claim': claim, 'inputs': inputs})

    def value(path, op='number'):
        return {'path': path, 'op': op}

    def chart(title, caption, path, op='name_count', kind='hbar', columns=None):
        i = screen(type='chart', no='%02d' % len(ol['screens']), title=title,
                   paragraphs=[], chart={'kind': kind, 'caption': caption})
        field = 'rows' if kind == 'table' else 'data'
        if columns:
            ol['screens'][i]['chart']['columns'] = columns
        bind(i, 'chart/'+field, {'path': path, 'op': op, 'limit': 10})
        return i

    filters=data['meta'].get('filters',{})
    restrictions=[]
    for field,label in [('education','学历'),('experience','经验'),('jobType','招聘类型')]:
        if filters.get(field):
            names=data['meta'].get('enum_labels',{}).get(field,{})
            restrictions.append('、'.join(names.get(value,'限定类别') for value in filters[field])+label+'限定')
    if filters.get('roles') or any(filters.get('title',{}).values()):restrictions.append('岗位条件限定')
    if filters.get('updatedAt'):restrictions.append('时间范围限定')
    subtitle='平台岗位记录的结构观察'+('｜'+'；'.join(restrictions) if restrictions else '')
    i = screen(type='cover', title=title, issuer=brand['issuer'],
               co_issuer=brand['co_issuer'], series=brand['report_series'],
               subtitle=subtitle if binding else '离线演示样例',
               chips=[{'value': '', 'label': '条在招岗位记录'},
                      {'value': '', 'label': '家关联企业'}])
    bind(i, 'chips/0/value', value('/total/positions'))
    bind(i, 'chips/1/value', value('/total/companies'))
    i = screen(type='chart', no='01', title='核心发现', paragraphs=[])
    paragraph(i, '本次样本覆盖 {n} 条在招岗位记录，关联 {c} 家企业。',
              {'n': value('/total/positions'), 'c': value('/total/companies')})
    ol['screens'][i]['summary'] = {'title': '研究关注点',
        'text': '结合地域分布、招聘门槛和声明薪酬识别需求结构，为专业定位与校企合作提供参考。'}
    if not data['total']['positions']:
        ol['screens'][i]['summary']['text'] = '当前筛选范围没有在招岗位记录，请核对范围后再确定研究主题。'

    if data.get('city'):
        i = chart('招聘地域分布', '企业关联地址的城市岗位数', '/city', 'pairs')
        if len(data['city'])>=3:
            bind(i,'chart2',{'path':'/city','op':'city_concentration','inputs':{'total':value('/total/positions')}})
        paragraph(i, '完整样本可归属 {n} 个省市组合；图表展示数量靠前的城市。',
                  {'n': value('/total/cities')})
    for key, title1 in [('jobtype', '招聘类型'), ('edu', '学历要求'), ('exp', '经验要求')]:
        if data.get(key):
            if key == 'jobtype':
                i = screen(type='chart', no='%02d' % len(ol['screens']), title=title1, paragraphs=[])
                bind(i, 'chart', {'path': '/jobtype', 'op': 'composition'})
            else:
                i = chart(title1, title1+'岗位记录数', '/'+key)
            paragraph(i, '各类别统计使用同一组 {n} 条岗位记录，缺失与未知类别单独保留。',
                      {'n': value('/total/positions')})
    if data.get('edu_exp'):
        i=screen(type='chart',no='%02d'%len(ol['screens']),title='学历与经验交叉',paragraphs=[])
        bind(i,'chart',{'path':'/edu_exp','op':'requirements_composition'})
    salary = data.get('salary') or {}
    if salary.get('valid'):
        i = chart('薪酬结构', '薪酬分档岗位数（不等宽分档，非密度；K = 千元）', '/salary_hist', kind='vbar')
        paragraph(i, '共有 {n} 条记录符合薪酬有效性规则，中位数为 {m} K/月。',
                  {'n': value('/salary/valid'), 'm': value('/salary/median')})
        ol['screens'][i]['summary'] = {'title': '培养与岗位定位',
            'text': '薪酬可辅助识别不同方向的招聘定位，实际收入仍取决于岗位职责、经验和录用条件。'}
        from report_charts import salary_cohorts
        if salary_cohorts(data):
            bind(i,'chart2',{'path':'/salary','op':'salary_cohorts','inputs':{'entry':{'path':'/voc_pool/salary','op':'value'}}})
    if data.get('subtrack'):
        chart('岗位方向结构', '按显式有序规则的互斥归类', '/subtrack')
    if any(r.get('valid') for r in data.get('salary_by_track', [])):
        if any(r.get('valid', 0) >= 30 for r in data['salary_by_track']):
            chart('方向薪酬比较', '方向薪酬：线段为中间一半，圆点为中位数（有效样本≥30）',
                  '/salary_by_track', 'salary_ranges', 'range_dot')
        else:
            chart('方向薪酬比较', '有效样本较小，仅供描述', '/salary_by_track',
                  'track_salary_table', 'table', ['岗位方向', '有效薪酬记录', '中位数K/月'])
    sections = {c['section'] for c in data.get('coverage', [])}
    if data.get('city_track_rows'):
        if 'city_tracks' in sections:
            chart('城市与岗位方向', '城市×方向岗位记录数', '/city_track_rows',
                  'city_track_table', 'table', ['企业地址城市', '岗位方向', '岗位记录数'])
        if 'lq' in sections:
            chart('地域方向集中程度', '本市方向占比相对样本方向占比', '/city_track_rows',
                  'lq_table', 'table', ['企业地址城市', '岗位方向', 'LQ'])
    if data.get('skill_described_n') and data.get('keywords'):
        i = chart('人才能力关键词', '岗位描述中的技能词提及数', '/keywords')
        paragraph(i, '技能统计基于 {n} 条有描述的岗位记录；同一岗位可提及多个词。',
                  {'n': value('/skill_described_n')})
    if data.get('job_skill_rows') and data.get('skill_described_n'):
        i = screen(type='chart', no='%02d' % len(ol['screens']), title='方向与技能组合', paragraphs=[])
        bind(i, 'chart', {'path': '/job_skill_rows', 'op': 'skill_matrix'})
    pool = data.get('voc_pool')
    if pool is not None:
        i = screen(type='chart', no='%02d' % len(ol['screens']), title='职教入门岗位观察', paragraphs=[])
        paragraph(i, '学历与经验条件同时满足所列规则的岗位有 {n} 条，占总体 {p}%。',
                  {'n': value('/voc_pool/count'), 'p': value('/voc_pool/pct')})
        ol['screens'][i]['summary'] = {'title': '课程与实践对接',
            'text': '岗位池反映所列学历与经验条件的交集，院校还需结合职责、技能与学生基础设计实践任务。'}
        if pool.get('track'):
            ol['screens'][i]['chart'] = {'kind': 'hbar', 'caption': '职教入门池的岗位方向'}
            bind(i, 'chart/data', {'path': '/voc_pool/track', 'op': 'name_count', 'limit': 10})
        from report_charts import cohort_cities
        if cohort_cities(data):
            bind(i,'chart2',{'path':'/city','op':'cohort_cities','inputs':{
                'total':value('/total/positions'),'entryCount':value('/voc_pool/count'),
                'entryCities':{'path':'/voc_pool/city','op':'value'}}})
    if binding:
        # Keep every agent-written action while preventing one exceptionally long image.
        from report_analysis import evidence_pack
        count=len(evidence_pack(data,binding)['requiredSections'])
        for start in range(0,count,6):
            screen(type='chart',no='%02d'%len(ol['screens']),title='人才培养与合作建议'+('（续）' if start else ''),
                   recommendation_start=start,recommendation_stop=min(start+6,count),paragraphs=[])
    else:
        screen(type='chart',no='%02d'%len(ol['screens']),title='人才培养与合作建议',
               paragraphs=['将样本中数量较多的岗位方向转化为典型工作任务，结合企业访谈验证课程与实训项目。',
                           '把学历、经验与技能要求分别纳入培养方案，优先选择条件清楚的企业开展项目合作。'])
    gaps = [c['section']+'：'+c['status'] for c in data.get('coverage', []) if c['status'] not in ('complete', 'empty')]
    scope = '地区：'+data['meta']['region']+'；产业/岗位：'+data['meta'].get('scope_industry', data['meta']['industry'])
    f = data['meta'].get('filters', {})
    for key, field, title1 in [('education', 'edu', '学历'), ('experience', 'exp', '经验'), ('jobType', 'jobtype', '招聘类型')]:
        if f.get(key):
            labels = data['meta'].get('enum_labels', {}).get(key, {}) or {r.get('raw'): r['name'] for r in data.get(field, [])}
            scope += '；'+title1+'：'+'、'.join(labels.get(v, '限定类别（无对应样本）') for v in f[key])
    if f.get('title'):
        for key, title1 in [('any', '名称任一包含'), ('all', '名称同时包含'), ('exclude', '名称排除')]:
            if f['title'].get(key):
                scope += '；'+title1+'：'+'、'.join(f['title'][key])
    period = f.get('updatedAt', {})
    scope += '；平台更新时间：'+('至'.join([period.get('from', '不限起点'), period.get('to', '不限终点（上界不含）')]) if period else '未限制')
    read_at = data['meta']['generated_at']
    if binding:
        instant = datetime.fromisoformat(read_at.replace('Z', '+00:00'))
        read_at = instant.astimezone(timezone(timedelta(hours=8))).strftime('%Y年%m月%d日 %H:%M（北京时间）')
    blocks = [('数据来源', '优才知路平台数据库。统计单位为岗位记录，地址来自企业关联地址。'),
              ('筛选范围', scope),
              ('薪酬方法', ('两端为有效数值，最低薪酬为正且不大于最高薪酬，最高不超过100 K/月；以区间中点计算加权线性分位数。' if binding and salary else '历史样例算法；不代表当前实时薪酬统计方法。' if salary else '本次没有可用薪酬统计。')),
              ('方向与技能', ('方向采用显式首个命中规则。' if data.get('subtrack') else '本次未完成岗位方向统计。')+
               ('技能为描述子串提及，多个词可重叠。' if data.get('skill_described_n') else '本次无可用技能提及统计。')),
              ('数据日期', read_at+'。该时间为统计读取时间，岗位发布时间未作限定。' if not period else read_at+'。时间筛选针对平台更新时间。'),
              ('未覆盖项', '；'.join(gaps) if gaps else '本次声明的统计章节已完成。')]
    if binding and pool is not None:
        cohort = next((c for c in binding['_result']['cohorts'] if c['id'] == 'vocational'), None)
        if cohort:
            labels = data['meta'].get('enum_labels', {})
            rules = []
            for key, title1 in [('education', '学历'), ('experience', '经验')]:
                values = cohort['filters'].get(key, [])
                names = [labels.get(key, {}).get(v, v) for v in values]
                rules.append(title1+'类别选取'+('、'.join(names) if names else '全部类别'))
            blocks.insert(2, ('职教入门岗位筛选', '；'.join(rules)+'。两项条件须同时满足。'))
    if not binding:
        blocks.insert(0, ('样例说明', '本报告为离线演示，不代表当前真实查询。'))
    screen(type='notes', no='附录', title='数据与研究方法', blocks=blocks)
    return ol


def build_outline(data, brand, binding=None, analysis=None):
    if binding:
        from report_analysis import apply_analysis, validate_analysis
        validate_analysis(data, binding, analysis)
        skeleton=_build_skeleton(data,brand,binding)
        if analysis.get('schema')=='wechat-analysis/2':
            from deep_outline import upgrade
            skeleton=upgrade(skeleton,data,binding)
        result=apply_analysis(skeleton,data,binding,analysis)
        if analysis.get('schema')=='wechat-analysis/2':
            from report_references import attach
            result=attach(result,data,binding)
        return result
    return _build_skeleton(data, brand)


def outline_to_md(ol):
    lines = ['# '+ol['title'], '', '> 内部排版数据；不向用户请求大纲确认。', '']
    for s in ol['screens']:
        lines += ['## '+s['title'], '']+s.get('paragraphs', [])
        if s.get('summary'):
            lines += ['', s['summary']['title']+'：'+s['summary']['text']]
        if s.get('chart'):
            chart = s['chart']
            lines += ['', '**图表**：'+chart.get('caption', ''),
                      '```json', json.dumps(chart, ensure_ascii=False, indent=2), '```']
        for t, text in s.get('blocks', []):
            lines += ['', '**'+t+'**：'+text]
        lines += ['']
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=str(BASE/'report_data.json'))
    ap.add_argument('--out', default=str(BASE/'output/outline'))
    ap.add_argument('--analysis', default=str(BASE/'report_analysis.json'))
    ap.add_argument('--demo', action='store_true')
    args = ap.parse_args()
    data, binding = load_data(args.data, args.demo)
    brand = json.loads((BASE/'assets/brand.json').read_text('utf-8'))
    analysis = None
    if binding:
        if not Path(args.analysis).is_file():
            raise ValueError('必须先完成真实数据分析：运行 report_analysis.py，阅读证据并撰写 report_analysis.json')
        analysis = json.loads(Path(args.analysis).read_text('utf-8'))
    ol = build_outline(data, brand, binding, analysis)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out/'report_outline.json').write_text(json.dumps(ol, ensure_ascii=False, indent=2), 'utf-8')
    (out/'outline.md').write_text(outline_to_md(ol), 'utf-8')
    print(json.dumps({'outline': str(out/'report_outline.json'), 'pages': len(ol['screens'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
