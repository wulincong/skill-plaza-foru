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
