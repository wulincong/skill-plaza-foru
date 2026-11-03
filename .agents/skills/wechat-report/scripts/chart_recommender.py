# -*- coding: utf-8 -*-
"""
chart_recommender.py — 图表选择器（FT Visual Vocabulary 规则的代码化）
先判断数据关系/形态，再决定图表类型；gen_outline 在生成图配置前调用。

规则（references/research-benchmarks.md 第二节）:
    * 构成类数据，最大份额 > 85%（极端不均衡）→ bignum 大数字卡，禁饼/环；
    * 构成类 5-7 类 → donut；≤4 类且最大 < 85% → pie；>7 类 → hbar 排序条；
    * 排名 → 排序 hbar（永远按值排序，禁止字母/原始序）；
    * 二维交叉（含 LQ/共现） → heatmap；
    * 二个连续指标 + 类别 → scatter 气泡；
    * 阈值类（>85% 等）来自 FT anti-patterns。
"""
EXTREME_SHARE = 85.0
MULTIVARIATE_POLICY='wechat-chart-selection/2'
MULTIVARIATE_SPECS={
    '招聘地域分布':{'path':'/city_profiles','op':'joint_city'},
    '学历要求':{'path':'/edu_exp','op':'joint_requirements'},
    '经验要求':{'path':'/edu_exp','op':'joint_experience'},
    '学历与经验交叉':{'path':'/edu_exp','op':'joint_access'},
    '薪酬结构':{'path':'/salary','op':'joint_salary','inputs':{'entry':{'path':'/voc_pool/salary'}}},
    '岗位方向结构':{'path':'/subtrack','op':'joint_tracks','inputs':{'salary':{'path':'/salary_by_track'}}},
    '方向薪酬比较':{'path':'/salary_by_track','op':'joint_track_salary'},
    '城市与岗位方向':{'path':'/city_track_rows','op':'joint_city_tracks'},
    '地域方向集中程度':{'path':'/city_track_rows','op':'joint_lq'},
    '人才能力关键词':{'path':'/job_skill_rows','op':'joint_skills'},
    '职教入门岗位观察':{'path':'/voc_pool/track','op':'joint_entry','inputs':{
        'all':{'path':'/subtrack'},'salary':{'path':'/voc_pool/salary_by_track'}}},
}


def recommend_multivariate(topic,data):
    """Choose from real joint structures; omit inapplicable comparisons explicitly."""
    import copy
    spec=MULTIVARIATE_SPECS.get(topic)
    if not spec:return None
    reason='由同口径联合统计选择多指标视图'
    if topic=='招聘地域分布':
        rows=[row for row in data.get('city_profiles',[]) if row.get('valid',0)>=30 and row.get('median') is not None]
        if len(rows)<2:return {'spec':None,'reason':'有效城市不足两个，不绘制跨城薪酬学历比较，不扩大地域范围'}
        reason='以城市联合比较薪酬中位数、学历份额与岗位量；全篇唯一柱状组合图'
    if topic=='经验要求' and len({row[0] for row in data.get('edu_exp',[])})<2:
        return {'spec':None,'reason':'仅有一个学历组，省略学历组间经验对照，保留原始筛选'}
    if topic=='城市与岗位方向' and len({(row.get('province'),row.get('city')) for row in data.get('city_track_rows',[]) if row.get('city')})<2:
        return {'spec':None,'reason':'仅有一个有效城市，省略跨城方向矩阵'}
    if topic=='地域方向集中程度' and data.get('meta',{}).get('filters',{}).get('region',{}).get('level')=='city':
        return {'spec':None,'reason':'样本限定单城，内部城市对比不能识别相对外部地域集中度'}
    return {'spec':copy.deepcopy(spec),'reason':reason}


def recommend_composition(items):
    """构成类：items=[{name,count,pct}] → kind + 附注"""
    if not items:
        return None
    items = sorted(items, key=lambda r: -r['count'])
    total = sum(r['count'] for r in items)
    if total <= 0:
        return None
    top = items[0]
    top_share = top['count'] / total * 100
    n = len(items)
    if top_share > EXTREME_SHARE:
        return {'kind': 'bignum',
                'reason': '最大份额 %.1f%% 超过 %.0f%%，饼/环图标签必然拥挤'
                          % (top_share, EXTREME_SHARE),
                'card': {'value': top, 'rest': items[1:3]}}
    if n > 7:
        return {'kind': 'hbar', 'reason': '类别 %d 个超过环形可读上限 7' % n}
    if n >= 5:
        return {'kind': 'donut', 'reason': '%d 类构成，环形+右侧图例' % n}
    return {'kind': 'pie', 'reason': '≤4 类小构成'}


def check_chart_choice(cfg):
    """渲染前校验图表选择是否违规；返回 [违规说明]"""
    problems = []
    kind = cfg.get('kind')
    data = cfg.get('data') or []
    if kind in ('pie', 'donut'):
        if not data:
            problems.append('%s 无数据' % kind)
            return problems
        total = sum(d[1] for d in data if len(d) > 1 and isinstance(d[1], (int, float)))
        if total:
            top = max(d[1] for d in data) / total * 100
            if top > EXTREME_SHARE:
                problems.append('%.1f%% 极端构成使用 %s（FT 规则：应改大数字卡）'
                                % (top, kind))
        if kind == 'donut' and len(data) > 7:
            problems.append('环形图 %d 类超过 7 类可读上限' % len(data))
    if kind == 'hbar' and data and (cfg.get('sorted') is False or any(a[1] < b[1] for a, b in zip(data, data[1:]))):
        problems.append('条形图未按值排序')
    return problems
