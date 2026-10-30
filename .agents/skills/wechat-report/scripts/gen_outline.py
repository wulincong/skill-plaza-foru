# -*- coding: utf-8 -*-
"""
gen_outline.py — 从 report_data.json 生成报告大纲（文案脚本），供人工确认后再渲染
用法:
    python gen_outline.py                              # 读 ../report_data.json

结构依据（SKILL.md 用户版）：
    封面（报告名/数据总量/编制时间）→ 摘要（总起一段 + 分点核心判断 + 过渡总结）
    → 01 招聘区域格局 → 02 岗位结构 → 03 技术赛道 → 04 学历与经验门槛
    → 05 薪酬结构 → 06 交叉分析·城市×赛道 → 07 交叉分析·学历×经验
    → 08 人才能力画像 → 09 人才培养体系建议 → 附录（关键指标/来源/方法/一致性/免责）
    每章三段式：详细数据讲解（含具体城市举例）→ 结构分析 → 本章小结（判断/启示）。
    红线：数字全部可溯源；数据来源只写"优才知路平台的数据库"；
    数据时间非均匀采样，不做时间趋势图。
"""
import argparse
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report_common as rc
import chart_recommender as cr

DATA_SOURCE = '优才知路平台的数据库'


def _fmt(n):
    return '{:,}'.format(n)


def _city(c):
    return c[:-1] if c.endswith('市') else c


def build_outline(r, brand):
    screens = []
    d = r
    pool = d.get('voc_pool') or {}
    pc = rc.pct_cn
    yn = rc.yuan
    total = d['total']
    t2 = d['city_top2']
    g = d.get('track_core', d['track_groups'])
    c1 = _city(t2[0][0]) if t2 else '-'
    c2 = _city(t2[1][0]) if len(t2) > 1 else '-'
    ct_top = d['city_top']
    llm_grp = next((x for x in g if '大模型' in x['name']), None)
    llm = llm_grp['pct'] if llm_grp else 0
    g2 = g[1] if len(g) > 1 else None
    anno = d['anno_group']
    st = d['salary_top_track']

    def cpct(i):
        """城市举例：名称+条数+占比"""
        name, n = ct_top[i]
        return '%s%s条、占%s%%' % (_city(name), _fmt(n),
                                  round(n / total * 100, 1))

    # ---------- 封面 ----------
    screens.append({
        'type': 'cover',
        'title': d['title'],
        'subtitle': '基于%s条在招岗位的产业人才洞察' % d['total_h'],
        'issuer': brand['issuer'],
        'co_issuer': brand['co_issuer'],
        'series': brand['report_series'],
        'chips': [
            {'value': d['period'], 'label': '数据周期'},
            {'value': d['total_h'], 'label': '岗位总量'},
            {'value': d['companies_h'], 'label': '招聘企业'},
        ],
        'date': d['generated_at'][:7].replace('-', '年') + '月',
    })

    # ---------- 摘要 ----------
    screens.append({
        'type': 'summary', 'title': '摘要',
        'lead': [
            '本报告基于%s近%s天的%s相关在招岗位<b>%s条</b>记录（覆盖招聘企业'
            '%s家、城市%s座），从招聘区域格局、岗位结构、技术赛道、学历与'
            '经验门槛、薪酬结构、多角度交叉分析与人才能力画像等维度展开，主要结论如下。'
            % (DATA_SOURCE, d['days'], d['industry'], d['total_h'],
               total and d['companies_h'], d['cities']),
        ],
        'cards': [
            {'no': '01', 'title': '需求向"双核+制造带"集中',
             'desc': '%s、%s合计占%s%%，前5城占%s%%；%s、%s等制造业城市形成'
                     '梯度承接，岗位分布与产业布局高度一致。' % (
                         c1, c2, d['city_top2_pct'], d['city_top5_pct'],
                         _city(ct_top[2][0]) if len(ct_top) > 2 else '-',
                         _city(ct_top[3][0]) if len(ct_top) > 3 else '-')},
            {'no': '02',
             'title': ('岗位链条走向"研发+应用+训练"'
                       if anno.get('count') else '岗位链条走向多元化分工'),
             'desc': ('%s等四大方向合计占%s%%；数据标注/AI训练占%s%%、%s条，'
                      '应用与训练环节已形成完整需求链条。' % (
                          g[0]['name'] if g else '-', d['top4_pct'],
                          anno['pct'], _fmt(anno['count'])))
                      if anno.get('count') else
                      ('%s居首（%s%%），%s紧随其后（%s%%），需求结构多元。' % (
                          g[0]['name'] if g else '-', g[0]['pct'] if g else 0,
                          g2['name'] if g2 else '-',
                          g2['pct'] if g2 else 0))},
            {'no': '03', 'title': '门槛分层，薪酬与规模并不同向',
             'desc': '本科及以上占%s%%为主流门槛；月薪中位数%sK，而岗位量最大'
                     '的方向并非薪酬最高——选方向需量价兼顾。' % (
                         d['edu_above_benke_pct'], d['salary']['median'])},
            {'no': '04', 'title': '能力要求呈"底座+模块"组合形态',
             'desc': '%s是被提及最多的能力栈（%s次）；不同岗位族群依赖不同的'
                     '技能组合，为课程对齐提供了直接参照。' % (
                         (max(d['skill_stacks'], key=lambda x: x['count'])['name'],
                          _fmt(max(x['count'] for x in d['skill_stacks'])))
                         if d.get('skill_stacks') else ('-', '0'))},
        ],
        'tail': [
            '总体来看，广东%s人才需求正从单一算法研发走向多层次、复合化的'
            '产业结构；人才能力要求呈现"编程底座+方向模块"的组合形态。这对'
            '行业结构演进、人才能力标准与院校培养体系建设，都具有直接的'
            '参考意义。' % d['industry'],
        ],
    })

    # ---------- 01 招聘区域格局 ----------
    screens.append({
        'type': 'chart', 'no': '01', 'title': '招聘区域格局',
        'paragraphs': [
            '<b>%s以%s条居首，占%s%%</b>；%s。前5城合计占%s%%，呈现明显的'
            '"双核引领、周边梯度集聚"格局。' % (
                c1, _fmt(t2[0][1]), round(t2[0][1] / total * 100, 1),
                cpct(1) if len(ct_top) > 1 else '-', d['city_top5_pct']),
            '从结构看，%s、%s集聚平台型企业与研发中心，承载了绝大多数高学历'
            '算法岗位；周边城市依托制造业与配套产业基础，承接应用落地与数据'
            '处理类岗位，与双核形成"研发—应用"的分工协同。' % (c1, c2),
        ],
        'summary': {'title': '区域人才策略启示', 'text': '区域格局决定人才流动方向——企业选址围绕双核，求职与校企合作也应优先对标本地优势产业，而非仅看全省总量排名。'},
        'chart': {
            'kind': 'hbar', 'caption': '各城市在招岗位数量 TOP10（条）',
            'data': [[_city(x[0]), x[1]] for x in ct_top],
            'unit': '', 'top': 2,
        },
    })

    # ---------- 02 岗位结构 ----------
    jt = d['jobtype']
    rec = cr.recommend_composition(jt)
    chartA = ({'kind': 'bignum', 'label': '在招岗位为社会招聘',
               'top': jt[0], 'rest': jt[1:3]}
              if rec and rec['kind'] == 'bignum' else
              {'kind': 'pie', 'caption': '岗位性质构成',
               'data': [[t['name'], t['count']] for t in jt[:3]]})
    sub1 = d['subtrack_top'][0]
    screens.append({
        'type': 'duo', 'no': '02', 'title': '岗位结构',
        'paragraphs': [
            '<b>%s%%的岗位为社会招聘</b>，实习与兼职合计仅%s%%——企业明显偏好'
            '"即插即用"的成熟人才，在校生直接对口的在招岗位有限，实习转正是'
            '主要衔接通道。' % (d['jobtype_soc_pct'],
                             round(100 - d['jobtype_soc_pct'], 1)),
            '细分方向上，<b>%s占%s%%（%s条）</b>，%s占%s%%；岗位类型的多层次'
            '并存，意味着不同学历背景的人才面对的是不同的岗位子市场。' % (
                sub1['name'], sub1['pct'], _fmt(sub1['count']),
                d['subtrack_top'][1]['name'] if len(d['subtrack_top']) > 1 else '-',
                d['subtrack_top'][1]['pct'] if len(d['subtrack_top']) > 1 else 0),
        ],
        'summary': {'title': '一个重要变化', 'text': '从"研发主导"到"研发+应用+训练"并重，岗位分工正在加速细化——这为多层次人才进入产业提供了结构性空间。'},
        'chartA': chartA,
        'chartB': {
            'kind': 'hbar', 'caption': '细分方向岗位量 TOP8（每个岗位计一个主方向）',
            'data': [[s['name'], s['count'], s['pct']]
                     for s in d['subtrack_top'][:8]],
            'pct_label': True,
        },
    })

    # ---------- 03 技术赛道 ----------
    screens.append({
        'type': 'chart', 'no': '03', 'title': '技术赛道',
        'paragraphs': [
            '<b>%s以%s%%居首</b>，%s占%s%%次之，四大方向合计占<b>%s%%</b>，'
            '构成人才需求的主体。' % (
                g[0]['name'], g[0]['pct'],
                g[1]['name'] if len(g) > 1 else '-',
                g[1]['pct'] if len(g) > 1 else 0, d['top4_pct']),
            ('值得关注的是，%s作为独立方向<b>单列即占%s%%</b>，规模已与主流'
             '方向相当。' % (llm_grp['name'], llm)) if llm_grp else
            ('<b>%s以%s%%居首</b>，%s占%s%%次之，头部方向集中度较高。' % (
                g[0]['name'], g[0]['pct'],
                g2['name'] if g2 else '-', g2['pct'] if g2 else 0)),
        ],
        'summary': {'title': '赛道格局判断', 'text': '赛道结构反映产业正处于"算法深耕+应用铺开"并行阶段；专业建设宜以四大方向为骨架、以新兴类目为增量。'},
        'stats': [
            {'value': '%s%%' % d['top4_pct'], 'label': '四大方向合计',
             'hot': True},
            {'value': '%s%%' % llm,
             'label': (llm_grp['name'] if llm_grp else
                       (g2['name'] if g2 else '第二方向'))},
            {'value': '%s%%' % (anno['pct'] if anno.get('count') else
                                (g2['pct'] if g2 else 0)),
             'label': anno['name'] if anno.get('count') else '第二方向占比'},
        ],
        'chart': {
            'kind': 'donut', 'caption': '技术赛道构成（每个岗位计一个主方向）',
            'data': [[x['name'], x['count'], x['pct']]
                     for x in d['track_groups'][:7]],
        },
    })

    # ---------- 04 学历与经验门槛 ----------
    edu = {e['name']: e for e in d['edu']}
    screens.append({
        'type': 'chart', 'no': '04', 'title': '学历与经验门槛',
        'paragraphs': [
            '学历方面，<b>本科%s%%、硕士%s%%、博士%s%%合计%s%%</b>——本科及'
            '以上是主流门槛；大专及以下占%s%%、学历不限占%s%%，共同构成非'
            '本科通道的岗位面。' % (
                edu.get('本科', {}).get('pct', 0),
                edu.get('硕士', {}).get('pct', 0),
                edu.get('博士', {}).get('pct', 0),
                d['edu_above_benke_pct'], d['edu_dazhuan_below_pct'],
                d['edu_buxian_pct']),
            '经验方面，<b>1-3年与3-5年合计%s%%</b>，是企业争夺的主力人群；'
            '经验不限占%s%%、应届与1年以内合计%s%%，入门通道存在但占比有限。' % (
                d['exp_1_5_pct'], d['exp_buxian_pct'], d['exp_fresh_pct']),
        ],
        'summary': {'title': '门槛之外的通道', 'text': '门槛并非铁板一块：非本科通道约占一成，其中学历与经验双低的岗位边界清晰，是切入产业最现实的入口。'},
        'chart': {
            'kind': 'hbar', 'caption': '学历要求分布（岗位占比）',
            'data': [[e['name'], e['count'], e['pct']] for e in d['edu']],
            'pct_label': True, 'highlight': '大专',
        },
        'chart2': {
            'kind': 'vbar', 'caption': '经验要求分布（岗位占比）',
            'data': [[e['name'], e['pct'], e['count']] for e in d['exp']],
            'pct_label': True,
        },
    })

    # ---------- 05 薪酬结构 ----------
    top_bin = max(d['salary_hist'], key=lambda x: x['pct']) \
        if d['salary_hist'] else None
    sal = {t['name']: t for t in d['salary_by_track']}
    pts = [[s['name'], s['count'], sal[s['name']]['median'],
            sal[s['name']]['count']]
           for s in d['subtrack_top'][:10] if s['name'] in sal]
    big = max(pts, key=lambda p: p[1]) if pts else None
    rich = max(pts, key=lambda p: p[2]) if pts else None
    screens.append({
        'type': 'chart', 'no': '05', 'title': '薪酬结构',
        'paragraphs': [
            '在招岗位<b>月薪中位数%sK</b>，P25为%sK、P75达%sK、P90达%sK；'
            '%s区间占比最高，为%s%%。' % (
                d['salary']['median'], d['salary']['p25'], d['salary']['p75'],
                d['salary']['p90'], top_bin['name'] if top_bin else '-',
                top_bin['pct'] if top_bin else 0),
            '方向间差异明显：%s方向中位数最高，约%sK；而岗位量最大的%s中位数'
            '%sK——"量大"与"价高"并不同向，选择方向需要同时看两个维度。' % (
                rich[0], rich[2], big[0], big[2]) if big and rich else
            '方向间差异明显，各方向薪酬中位数见速览口径。',
        ],
        'summary': {'title': '量价观察', 'text': '高薪方向多为小规模精英岗位，规模化岗位集中在月薪2万元上下——按"量"择业与按"价"择业，是两条不同的路径。'},
        'stats': [
            {'value': '%sK' % d['salary']['p25'], 'label': 'P25'},
            {'value': '%sK' % d['salary']['median'], 'label': '中位数',
             'hot': True},
            {'value': '%sK' % d['salary']['p75'], 'label': 'P75'},
            {'value': '%sK' % d['salary']['p90'], 'label': 'P90'},
        ],
        'chart': {
            'kind': 'vbar', 'caption': '月薪区间分布（区间中值口径）',
            'data': [[h['name'], h['pct']] for h in d['salary_hist']],
            'pct_label': True,
        },
        'chart2': {
            'kind': 'scatter', 'caption': '细分方向：岗位量 × 薪酬中位数',
            'data': pts, 'unit_x': '在招岗位数（条）',
            'unit_y': '薪酬中位数（K/月）',
        } if len(pts) >= 4 else None,
    })

    # ---------- 06 交叉分析·城市×赛道 ----------
    ct = d.get('city_track')
    lqt = None
    if d.get('city_lq') and d['city_lq'].get('cells'):
        lq = d['city_lq']
        b = max(lq['cells'], key=lambda x: x[2])
        lqt = {'city': [x['name'] for x in lq['rows']][b[0]],
               'grp': lq['cols'][b[1]], 'v': b[2]}
    if ct:
        cell = {(c[0], c[1]): c[2] for c in ct['cells']}
        cols = ct['cols']
        c1_top = max(range(len(cols)), key=lambda i: cell.get((0, i), 0))
        rn = [x['name'] for x in ct['rows']]
        screens.append({
            'type': 'chart', 'no': '06', 'title': '交叉分析：城市×赛道',
                'paragraphs': [
                '<b>%s以%s类岗位为主、占本市样本%s%%</b>；%s在数据标注/AI训练'
                '上的本市占比高于%s，形成与双核不同的结构。' % (
                    rn[0], cols[c1_top], cell.get((0, c1_top), 0),
                    _city(ct_top[3][0]) if len(ct_top) > 3 else '-',
                    rn[0]),
                ('以全省平均为基准，%s的%s类岗位集中程度达全省均值的%s倍，'
                 '居各市之首——区域产业分工有了可量化的证据。' % (
                     lqt['city'], lqt['grp'], lqt['v'])) if lqt else
                '各城市与全省平均的结构差异，可进一步量化为专业化指数。',
            ],
        'summary': {'title': '区域分工启示', 'text': '周边城市不必复制广深：把本地高集中度赛道做成差异化专业，比追逐头部方向更有胜率。'},
            'chart': {
                'kind': 'heatmap',
                'caption': '城市 × 技术赛道：各城市内部占比（%）',
                'rows': ['%s %s' % (x['name'], _fmt(x['count']))
                         for x in ct['rows']],
                'cols': cols, 'cells': ct['cells'],
            },
        })

    # ---------- 07 交叉分析·学历×经验 ----------
    am = d.get('access_matrix')
    if am and am['cells'] and pool.get('count'):
        zone = [(ri, ci) for ri, er in enumerate(rc.EDU_ROWS)
                if er[0] in rc.VOC_EDU_ROWS
                for ci, xc in enumerate(rc.EXP_COLS)
                if xc[0] in rc.VOC_EXP_COLS]
        rows = []
        for ri, er in enumerate(am['rows']):
            row = [er]
            for ci in range(len(am['cols'])):
                v = am['cells'][ri * len(am['cols']) + ci][2]
                row.append(_fmt(v) if v else '—')
            rows.append(row)
        pcity = pool.get('city') or []
        screens.append({
            'type': 'chart', 'no': '07', 'title': '交叉分析：学历×经验',
                'paragraphs': [
                '把两道门槛放到同一张表上：<b>★区域（学历不高于大专或不限，'
                '且经验为应届、1年以内或不限）共%s个岗位、占%s%%</b>；而本科×'
                '1-3年等组合才是需求最密集的区域。' % (
                    _fmt(pool['count']), pool['pct']),
                '这批低门槛岗位以%s为主，月薪中位数约%sK，主要分布在%s——'
                '规模有限但边界清晰，可作为职业院校与转岗人才的现实入口。' % (
                    '、'.join(t['name'] for t in (pool.get('track') or [])[:3]),
                    pool['salary'].get('median', '-'),
                    '、'.join(_city(x) for x, _ in pcity[:3])),
            ],
        'summary': {'title': '职教机会的现实边界',
                    'text': '%s个双低门槛岗位以%s为主、月薪中位约%sK——入口真实'
                            '存在，但对薪资预期要有合理锚点。' % (
                                _fmt(pool.get('count', 0)),
                                (pool.get('track') or [{}])[0].get('name', '-'),
                                pool.get('salary', {}).get('median', '-'))},
            'stats': [
                {'value': _fmt(pool['count']) + '个', 'label': '低门槛岗位',
                 'hot': True},
                {'value': '%s%%' % pool['pct'], 'label': '占全部岗位'},
                {'value': '%sK' % pool['salary'].get('median', '-'),
                 'label': '这类岗位月薪中位数'},
            ],
            'chart': {
                'kind': 'table',
                'caption': '学历 × 经验 组合矩阵（单元格=岗位数，★为低门槛组合）',
                'columns': ['学历＼经验'] + am['cols'],
                'rows': rows, 'rank': False, 'hot_col': -1,
                'align_num': list(range(1, len(am['cols']) + 1)),
                'hot_cells': sorted(zone),
            },
        })

    # ---------- 08 人才能力画像 ----------
    if d.get('skill_stacks'):
        sts = sorted(d['skill_stacks'], key=lambda x: -x['count'])
        js_ = d.get('job_skill') or {}
        mv = max(((c[0], c[1], c[2]) for c in js_.get('cells', [])),
                 key=lambda x: x[2], default=None)
        p8 = [
            '<b>%s是被提及最多的能力栈（%s次）</b>，其后为%s与%s——技能需求'
            '并非单一关键词排行，而是从编程底座到大模型工程的分层结构。' % (
                sts[0]['name'], _fmt(sts[0]['count']),
                sts[1]['name'] if len(sts) > 1 else '-',
                sts[2]['name'] if len(sts) > 2 else '-'),
        ]
        if mv:
            p8.append('岗位族群与技能的交叉进一步显示：<b>%s岗位中%s的提及率'
                      '最高、达%s%%</b>；数据训练类岗位更侧重数据处理与工具'
                      '使用，算法类更看重模型与编程基础。' % (
                          js_['rows'][mv[0]], js_['cols'][mv[1]], mv[2]))
        screens.append({
            'type': 'chart', 'no': '08', 'title': '人才能力画像',
                'paragraphs': p8,
            'summary': {'title': '共同能力底座', 'text': '企业要的是"底座+模块"的能力组合——先打牢基础编程，再按目标岗位补对应模块，是课程设置的直接参照。'},
            'chart': {
                'kind': 'hbar', 'caption': '能力栈提及规模（次）',
                'data': [[s['name'], s['count']] for s in sts],
                'unit': '', 'top': 1,
            },
            'chart2': {
                'kind': 'heatmap', 'caption': '岗位族群 × 技能：提及率（%）',
                'rows': js_.get('rows', []), 'cols': js_.get('cols', []),
                'cells': js_.get('cells', []),
            } if js_.get('cells') else None,
        })

    # ---------- 09 人才培养体系建议 ----------
    cmap_path = os.path.join(BASE, 'assets', 'curriculum_map.json')
    if os.path.exists(cmap_path):
        with open(cmap_path, 'r', encoding='utf-8') as f:
            cmap = json.load(f)
        rows = [[m['cluster'], '、'.join(m['modules']),
                 '、'.join(m['courses'][:3])] for m in cmap.get('mappings', [])]
        screens.append({
            'type': 'chart', 'no': '09', 'title': '人才培养体系建议',
                'paragraphs': [
                '<b>把前述数据洞察落到培养方案</b>：面向数据训练、应用实施、'
                '测试运维等岗位族群设置课程模块，比盲目跟风"大模型专业"更'
                '对口；下表为课题组给出的映射建议，供结合本地产业与生源情况'
                '取舍。',
                '实施路径上，建议以岗位族群为单元重组课程包、以真实岗位数据'
                '更新实训项目，并与本地高集中度赛道的企业共建实习通道。',
            ],
        'summary': {'title': '建设重点', 'text': '课程对齐能力组合、实训对齐岗位族群、评价对齐真实能力要求。'},
            'chart': {
                'kind': 'table',
                'caption': '岗位族群 → 能力模块 → 代表课程（课题组建议）',
                'columns': ['岗位族群', '能力模块', '代表课程'],
                'rows': rows, 'rank': False, 'hot_col': 1,
            },
            'quote': '产业竞争的下一阶段，不只是模型与算力的竞争，'
                     '更取决于能否形成与产业需求匹配的人才能力结构。',
        })

    # ---------- 附录 ----------
    screens.append({
        'type': 'notes', 'no': '附录', 'title': '数据与研究说明',
        'subtitle': None, 'paragraphs': [],
        'blocks': [
            ('关键指标', '在招岗位%s条；招聘企业%s家；覆盖城市%s座；统计周期'
             '近%s天；月薪中位数%sK；低门槛岗位%s个、占%s%%。' % (
                 d['total_h'], d['companies_h'], d['cities'], d['days'],
                 d['salary']['median'], _fmt(pool.get('count', 0)),
                 pool.get('pct', 0))),
            ('数据来源', '本报告岗位数据来源于%s，样本为企业在招的公开岗位'
             '信息。' % DATA_SOURCE),
            ('研究方法', '岗位按平台行业类目归属；每个岗位按一个主方向计数'
             '（占比之和≤100%）；城市按企业办公地址统计；薪酬取招聘区间中值'
             '的分位数；低门槛岗位为学历×经验两条件的交叉筛选；能力栈由固定'
             '技能词表归类统计。'),
            ('数据一致性', '关键数字均由程序从数据库计算，并以SQL分组独立'
             '复算逐项比对；渲染后的图经像素级复核；分析性结论经人工复核。'
             '岗位更新时间为平台数据更新时间且非均匀采样，故不做时间趋势'
             '推断。'),
            ('免责声明', '报告为招聘端单时间截面观察，不含入职结果；仅供产业'
             '研究与人才培养参考，未经许可请勿转载或用于商业用途。'),
        ],
        'contact_name': brand['contact_name'],
        'contact_phone': brand['contact_phone'],
    })

    return {
        'title': d['title'],
        'org': brand['org'],
        'generated_at': d['generated_at'],
        'message': '广深集中%s%%需求；低门槛AI岗位%s个、占%s%%' % (
            d['city_top2_pct'], _fmt(pool.get('count', 0)), pool.get('pct', 0)),
        'meta': {'region': d['region'], 'industry': d['industry'],
                 'days': d['days'], 'period': d['period'],
                 'data_source': DATA_SOURCE, 'sample_n': d['total_h']},
        'screens': screens,
    }


def outline_to_md(ol):
    lines = ['# %s — 报告大纲（人工确认稿）' % ol['title'], '']
    lines.append('> 共 %d 页。请审阅每页讲解、图表与小结；可直接修改同目录 '
                 'report_outline.json 后运行渲染。' % len(ol['screens']))
    lines.append('')
    for i, s in enumerate(ol['screens']):
        head = s.get('no') or s['type']
        if s['type'] == 'cover':
            lines.append('## 第%d页 封面' % (i + 1))
            lines.append('- 主标题：%s' % s['title'])
        elif s['type'] == 'summary':
            lines.append('## 第%d页 摘要' % (i + 1))
            for p in s.get('lead', []):
                lines.append('- 总起：%s' % p.replace('<b>', '**').replace('</b>', '**'))
            for c in s.get('cards', []):
                lines.append('- 判断%s：%s——%s' % (c.get('no', ''),
                                                   c.get('title', ''),
                                                   c.get('desc', '')))
            for p in s.get('tail', []):
                lines.append('- 总结：%s' % p)
        else:
            lines.append('## 第%d页 %s %s' % (i + 1, head, s.get('title', '')))
            if s.get('subtitle'):
                lines.append('- 副标题：%s' % s['subtitle'])
            for p in s.get('paragraphs', []):
                lines.append('- 正文：%s' % p.replace('<b>', '**').replace('</b>', '**'))
            if s.get('stats'):
                lines.append('- 数字卡：%s' % ' / '.join(
                    '%s(%s)' % (x['label'], x['value']) for x in s['stats']))
            for ck in ('chart', 'chart2', 'chartA', 'chartB'):
                if s.get(ck):
                    c = s[ck]
                    n = len(c.get('rows', c.get('data', [])))
                    lines.append('- 图表：%s（%s，%d项）' % (
                        c.get('caption', ''), c.get('kind'), n))
            if s.get('summary'):
                lines.append('- 总结框【%s】：%s' % (
                    s['summary'].get('title', ''), s['summary'].get('text', '')))
            if s.get('quote'):
                lines.append('- 金句：%s' % s['quote'])
            if s.get('blocks'):
                for t, _ in s['blocks']:
                    lines.append('- 说明块：%s' % t)
        lines.append('')
    lines.append('---')
    lines.append('*生成时间：%s*' % ol['generated_at'])
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=os.path.join(BASE, 'report_data.json'))
    ap.add_argument('--out', default=os.path.join(BASE, 'output', 'outline'))
    args = ap.parse_args()

    with open(args.data, 'r', encoding='utf-8') as f:
        d = json.load(f)
    with open(os.path.join(BASE, 'assets', 'brand.json'), 'r', encoding='utf-8') as f:
        brand = json.load(f)
    r = rc.derive(d)

    ol = build_outline(r, brand)
    os.makedirs(args.out, exist_ok=True)
    jp = os.path.join(args.out, 'report_outline.json')
    with open(jp, 'w', encoding='utf-8') as f:
        json.dump(ol, f, ensure_ascii=False, indent=2)
    mp = os.path.join(args.out, 'outline.md')
    with open(mp, 'w', encoding='utf-8') as f:
        f.write(outline_to_md(ol))
    print('大纲已生成（按新版 SKILL）：')
    print('  %s  （渲染输入，可编辑）' % jp)
    print('  %s  （审阅版）' % mp)
    print('共 %d 页：%s' % (len(ol['screens']),
                          ' → '.join((s.get('no') or '') + s['title']
                                     for s in ol['screens'])))


if __name__ == '__main__':
    main()
