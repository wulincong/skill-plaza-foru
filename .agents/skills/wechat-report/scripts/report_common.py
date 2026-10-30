# -*- coding: utf-8 -*-
"""
report_common.py — 报告数据的共享推导逻辑（render_report / build_article 共用）
输入: report_data.json 的 dict；输出: 分组赛道、核心结论、文案用数字。
"""
import time

# 细分方向 -> 报告赛道分组（呈现层口径）
TRACK_GROUPS = {
    '大模型/生成式AI': ['大模型算法'],
    '自然语言处理': ['自然语言处理算法'],
    '计算机视觉': ['图像算法'],
    '机器学习/数据挖掘': ['机器学习', '深度学习', '数据挖掘'],
    '自动驾驶/机器人': ['规控算法', 'SLAM算法', '自动驾驶系统工程师'],
    '通用算法工程': ['算法工程师', '算法研究员', '推荐算法', '搜索算法',
                     '语音算法', '风控算法'],
    '数据标注/AI训练': ['数据标注/AI训练师'],
    '其他': ['其他'],
}


def human_cnt(n):
    if n >= 100000000:
        return '%.2f亿' % (n / 100000000)
    if n >= 10000:
        return '%.2f万' % (n / 10000)
    return '%d' % n


def pct_cn(p):
    """百分比 → 中文成数表达（标题用；正文仍用精确数字）"""
    for th, txt in ((90, '近九成'), (80, '超八成'), (75, '近四分之三'),
                    (70, '近七成'), (60, '约六成'), (50, '约一半')):
        if p >= th:
            return txt
    return '占%s%%' % p


def yuan(k):
    """K（千元）→ 万元/元 的口语表达（面向学校读者的薪酬单位）"""
    if k is None:
        return '-'
    if k >= 10:
        return '%s万元' % (('%.2f' % round(k / 10, 2)).rstrip('0').rstrip('.'))
    return '%s元' % int(round(k * 1000))


# 准入矩阵的行列归并（学历6行 × 经验5列；与 fetch 的口径一致）
EDU_ROWS = [('博士及以上', ('博士',)), ('硕士', ('硕士',)), ('本科', ('本科',)),
            ('大专（含高职）', ('大专', '高职')),
            ('中专及以下', ('中专/中技', '高中', '初中及以下')),
            ('学历不限', ('学历不限',))]
EXP_COLS = [('应届/在校', ('应届生/在校',)), ('1年以内', ('1年以内',)),
            ('1-3年', ('1-3年',)), ('3-5年', ('3-5年',)),
            ('5年以上', ('5-10年', '10年以上')), ('经验不限', ('经验不限',))]
VOC_EDU_ROWS = ('大专（含高职）', '中专及以下', '学历不限')
VOC_EXP_COLS = ('应届/在校', '1年以内', '经验不限')


def condense_edu_exp(edu_exp):
    """把明细 (学历,经验,数) 归并成 6×6 准入矩阵；返回 rows/cols/cells"""
    idx = {(e, x): c for e, x, c in edu_exp or []}
    cells = []
    for ri, (er, eds) in enumerate(EDU_ROWS):
        for ci, (xc, exps) in enumerate(EXP_COLS):
            n = sum(idx.get((e, x), 0) for e in eds for x in exps)
            cells.append([ri, ci, n])
    return {'rows': [r for r, _ in EDU_ROWS], 'cols': [c for c, _ in EXP_COLS],
            'cells': cells}


def derive(d):
    """从 report_data.json 推导出呈现层数据，返回 dict"""
    m = d['meta']
    total = d['total']['positions']
    r = {
        'region': m['region'],
        'industry': m['industry'],
        'title': '%s%s产业人才需求观察报告' % (m['region'], m['industry']),
        'total': total,
        'total_h': human_cnt(total),
        'companies_h': human_cnt(d['total']['companies']),
        'cities': d['total']['cities'],
        'days': m['days'],
        'generated_at': m['generated_at'],
    }

    # 赛道分组（互斥主归属口径，占比之和<=100%；"其他"不参与 Top4 叙事）
    sub = {s['name']: s['count'] for s in d.get('subtrack', [])}
    groups = []
    for g, members in TRACK_GROUPS.items():
        c = sum(sub.get(x, 0) for x in members)
        if c > 0:
            groups.append({'name': g, 'count': c, 'pct': round(c / total * 100, 1)})
    if not groups and sub:
        # 关键词样本口径（如机器人）：方向名不走 AI 分组表，按细分方向直接透传
        groups = [{'name': s['name'], 'count': s['count'],
                   'pct': round(s['count'] / total * 100, 1)}
                  for s in d.get('subtrack', []) if s['name'] != '其他' and s['count']]
    groups.sort(key=lambda x: -x['count'])
    r['track_groups'] = groups
    core = [g for g in groups if g['name'] != '其他']
    r['track_core'] = core
    r['top4_pct'] = round(sum(g['pct'] for g in core[:4]), 1) if core else 0

    # 城市
    city = d.get('city', [])
    r['city_top'] = city[:10]
    r['city_top2'] = city[:2]
    r['city_top2_pct'] = d.get('city_top2_pct', 0)
    top5 = sum(c for _, c in city[:5])
    r['city_top5_pct'] = round(top5 / total * 100, 1) if total else 0

    # 细分方向 top
    r['subtrack_top'] = d.get('subtrack', [])[:8]

    # 学历要点
    edu = {e['name']: e for e in d.get('edu', [])}
    r['edu'] = d.get('edu', [])
    ben = edu.get('本科', {}).get('pct', 0)
    shuo = edu.get('硕士', {}).get('pct', 0)
    bo = edu.get('博士', {}).get('pct', 0)
    r['edu_above_benke_pct'] = round(ben + shuo + bo, 1)
    r['edu_buxian_pct'] = edu.get('学历不限', {}).get('pct', 0)
    # 职教视角：大专及以下（大专/高职/中专中技/高中/初中及以下）——中职高职学生的对口空间
    voc_names = ('大专', '高职', '中专/中技', '高中', '初中及以下')
    r['edu_dazhuan_below_pct'] = round(
        sum(e['pct'] for e in d.get('edu', []) if e['name'] in voc_names), 1)
    r['edu_dazhuan_below_cnt'] = sum(
        e['count'] for e in d.get('edu', []) if e['name'] in voc_names)
    r['edu_dazhuan_cnt'] = edu.get('大专', {}).get('count', 0)
    r['edu_dazhuan_pct'] = edu.get('大专', {}).get('pct', 0)
    r['edu_gaozhi_cnt'] = edu.get('高职', {}).get('count', 0)
    r['edu_gaozhi_pct'] = edu.get('高职', {}).get('pct', 0)
    r['edu_zhongzhuan_cnt'] = (edu.get('中专/中技', {}).get('count', 0)
                               + edu.get('高中', {}).get('count', 0))

    # 经验要点
    exp = {e['name']: e for e in d.get('exp', [])}
    r['exp'] = d.get('exp', [])
    r['exp_fresh_pct'] = round(
        exp.get('应届生/在校', {}).get('pct', 0)
        + exp.get('1年以内', {}).get('pct', 0), 1)
    r['exp_1_5_pct'] = round(
        exp.get('1-3年', {}).get('pct', 0)
        + exp.get('3-5年', {}).get('pct', 0), 1)
    r['exp_buxian_pct'] = exp.get('经验不限', {}).get('pct', 0)

    # 岗位性质
    r['jobtype'] = d.get('jobtype', [])
    r['jobtype_soc_pct'] = next(
        (j['pct'] for j in d.get('jobtype', []) if j['name'] == '社招'), 0)

    # 薪酬
    sal = d.get('salary', {})
    r['salary'] = sal
    r['salary_hist'] = d.get('salary_hist', [])
    # 全量保留：速览表按"方向名"取中位数，08屏取薪酬Top8时再切片
    r['salary_by_track'] = d.get('salary_by_track', [])
    r['salary_top_track'] = (d.get('salary_by_track') or [{}])[0]

    # 关键词
    r['keywords'] = d.get('keywords', [])[:15]

    # 城市×赛道交叉矩阵 / LQ 专业化指数 / 能力栈 / 岗位×技能矩阵
    r['city_track'] = d.get('city_track')
    r['city_lq'] = d.get('city_lq')
    r['skill_stacks'] = d.get('skill_stacks', [])
    r['job_skill'] = d.get('job_skill')

    # 职教可进入岗位池（学历×经验行级交叉筛选）与学历×经验交叉矩阵
    r['voc_pool'] = d.get('voc_pool') or {}
    r['edu_exp'] = d.get('edu_exp', [])
    r['access_matrix'] = condense_edu_exp(r['edu_exp'])

    # 月度发布趋势
    r['trend'] = d.get('trend', [])

    # 职教可切入赛道：数据标注/AI训练 的岗位量与占比
    anno = next((g for g in groups if g['name'] == '数据标注/AI训练'), None)
    r['anno_group'] = anno or {'name': '数据标注/AI训练', 'count': 0, 'pct': 0}
    # 入门经验通道：经验不限 + 应届/在校 + 1年以内
    r['exp_entry_pct'] = round(
        exp.get('经验不限', {}).get('pct', 0)
        + exp.get('应届生/在校', {}).get('pct', 0)
        + exp.get('1年以内', {}).get('pct', 0), 1)

    # 数据周期描述
    if m['days'] and m['days'] > 0:
        end = time.strptime(m['generated_at'][:10], '%Y-%m-%d')
        import datetime
        e = datetime.date(*end[:3])
        s = e - datetime.timedelta(days=m['days'])
        r['period'] = '%s.%s – %s.%s' % (
            s.year, '%02d' % s.month, e.year, '%02d' % e.month)
    else:
        r['period'] = '全量数据'
    return r


def _top_n_pct(items, n):
    tot = sum(c for _, c in [(i[0], i[1]) for i in items]) if items else 0
    return round(sum(i[1] for i in items[:n]) / tot * 100, 1) if tot else 0
