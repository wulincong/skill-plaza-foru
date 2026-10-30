# -*- coding: utf-8 -*-
"""
fetch_data.py — 从岗位数据库聚合报告统计数据（含数据溯源快照）
用法:
    python fetch_data.py --scope gd_ai                # 广东省 + 人工智能岗位（默认）
    python fetch_data.py --region 河北省 --industry 1242

V3 架构（Evidence "reports as code" 思想）:
    一次行级扫描取回 城市类别/岗位类别/学历/经验/性质/薪资/描述，
    Python 聚合出全部维度（含交叉）；SQL GROUP BY 只做交叉验证——
    同一个数字两种算法必须一致，对账写入 provenance。

新增口径:
    * LQ 专业化指数：LQ = (某市某赛道占本市比) / (该赛道占全省比)，>1 即高于全省平均；
    * 能力栈：36 技能词归入 5 个栈（词频加总口径，未去重）；
    * 岗位×技能矩阵：Top 细分方向 × 高频技能，单元格=该方向提到该词的岗位占比；
    * 职教可进入岗位池：学历∈{大专,高职,中专/中技,高中,初中及以下,不限} ×
      经验∈{应届/在校,1年以内,不限} 行级筛选（与 V2 一致）。
    * update_time 含批量同步伪影，trend 仅留档、禁止进报告。
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from collections import Counter

import pymysql

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_PATH = os.path.join(BASE, 'position_type_dict.json')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report_common as rc  # noqa: E402

GD_CITIES = ['广州市', '深圳市', '东莞市', '佛山市', '珠海市', '惠州市', '中山市',
             '江门市', '汕头市', '湛江市', '肇庆市', '揭阳市', '茂名市', '梅州市',
             '清远市', '韶关市', '潮州市', '河源市', '汕尾市', '阳江市', '云浮市']

EDU_MAP = {
    'BUXIAN': '学历不限', 'CHUZHONGJIYIXIA': '初中及以下', 'GAOZHONG': '高中',
    'ZHONGZHUAN/ZHONGJI': '中专/中技', 'GAOZHI': '高职', 'DAZHUAN': '大专',
    'BENKE': '本科', 'SHUOSHI': '硕士', 'BOSHI': '博士',
}
EDU_ORDER = ['博士', '硕士', '本科', '大专', '高职', '中专/中技', '高中', '初中及以下', '学历不限']
EDU_MATRIX_ORDER = ['博士', '硕士', '本科', '大专', '中专/中技', '学历不限']

EXP_MAP = {
    'BUXIAN': '经验不限', 'ON_CAMPUS': '应届生/在校', 'GRADUATING': '应届生/在校',
    'LESS_THAN_1': '1年以内', 'LESS_THAN_3': '1-3年', 'LESS_THAN_5': '3-5年',
    'LESS_THAN_10': '5-10年', 'MORE_THAN_10': '10年以上', 'WEWER23': '其他',
}
EXP_ORDER = ['应届生/在校', '1年以内', '1-3年', '3-5年', '5-10年', '10年以上',
             '经验不限', '其他']
EXP_MATRIX_ORDER = ['应届生/在校', '1年以内', '1-3年', '3-5年', '经验不限']

TYPE_MAP = {'SHEZHAO': '社招', 'XIAOZHAO': '校招', 'SHIXI': '实习', 'JIANZHI': '兼职'}

VOC_EDU_KEYS = ('DAZHUAN', 'GAOZHI', 'ZHONGZHUAN/ZHONGJI', 'GAOZHONG',
                'CHUZHONGJIYIXIA', 'BUXIAN')
VOC_EXP_KEYS = ('ON_CAMPUS', 'GRADUATING', 'LESS_THAN_1', 'BUXIAN')
VOC_EDU_NAMES = ('大专', '高职', '中专/中技', '高中', '初中及以下', '学历不限')
VOC_EXP_NAMES = ('应届生/在校', '1年以内', '经验不限')

PRIORITY = ['大模型算法', '自然语言处理算法', '图像算法', '机器学习', '深度学习',
            '数据挖掘', '规控算法', 'SLAM算法', '自动驾驶系统工程师',
            '推荐算法', '搜索算法', '语音算法', '风控算法', '算法研究员',
            '算法工程师', '数据标注/AI训练师']

SKILL_WORDS = ['Python', 'PyTorch', 'TensorFlow', '大模型', 'LLM', 'RAG', 'Agent',
               'PLC', '伺服', '运动控制', '机器视觉', 'AGV', '人形机器人', '具身', 'ROS2',
               '智能体', '深度学习', '机器学习', '计算机视觉', 'NLP', '自然语言',
               'CUDA', '分布式', 'Spark', 'Hadoop', 'SQL', 'C++', 'Linux',
               '数据挖掘', '推荐系统', '自动驾驶', '语音识别', '图像处理',
               'Prompt', '微调', '向量数据库', '多模态', 'AIGC', '强化学习',
               '数据分析', '算法优化', '目标检测', 'SLAM', 'ROS', '大语言模型']

# 能力栈：技能词 → 5 个能力模块（词频加总口径）
SKILL_STACKS = {
    '编程与系统底座': ['Python', 'C++', 'Linux', 'SQL', 'CUDA', '分布式', 'Spark',
                   'Hadoop'],
    '算法基础': ['机器学习', '深度学习', '数据挖掘', '强化学习', '计算机视觉',
              '自然语言', 'NLP', '目标检测', '图像处理'],
    '深度学习框架': ['PyTorch', 'TensorFlow'],
    '大模型工程': ['大模型', '大语言模型', 'LLM', '微调', 'RAG', 'Agent', '智能体',
               '多模态', 'AIGC', 'Prompt', '向量数据库'],
    '领域应用': ['自动驾驶', '推荐系统', '语音识别', '算法优化', '数据分析'],
}


def load_dict():
    with open(DICT_PATH, 'r', encoding='utf-8') as f:
        rows = json.load(f)
    return {r[0]: {'id': r[0], 'name': r[1], 'pid': r[2], 'level': r[4]} for r in rows}


def subtree_ids(tree, root):
    ids = {root}
    changed = True
    while changed:
        changed = False
        for n in tree.values():
            if n['pid'] in ids and n['id'] not in ids:
                ids.add(n['id'])
                changed = True
    return sorted(ids)


def human_cnt(n):
    if n >= 100000000:
        return '%.2f亿' % (n / 100000000)
    if n >= 10000:
        return '%.2f万' % (n / 10000)
    return str(n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scope', default='gd_ai', help='gd_ai=广东省+人工智能')
    ap.add_argument('--region', default='广东省')
    ap.add_argument('--industry', type=int, default=1242, help='c_position_type 行业根节点 id')
    ap.add_argument('--days', type=int, default=365, help='统计时间窗（天），0=全部')
    ap.add_argument('--name-kw', default='',
                    help='岗位名称关键词样本口径（如：机器人）。给定后按名称圈样本，'
                         '不再按行业类目树过滤，方向归类改用机器人方向表')
    ap.add_argument('--out', default=os.path.join(BASE, 'report_data.json'))
    args = ap.parse_args()

    cfgpath = os.path.join(BASE, 'db_config.json')
    if not os.path.exists(cfgpath):
        print('缺少 db_config.json，先运行 db_setup.py')
        sys.exit(1)
    with open(cfgpath, 'r', encoding='utf-8') as f:
        cfg = json.load(f)

    tree = load_dict()
    if args.industry not in tree:
        print('industry id %d 不在字典里' % args.industry)
        sys.exit(1)
    ind_ids = subtree_ids(tree, args.industry)
    ind_name = tree[args.industry]['name']
    if args.name_kw:
        ind_ids = []
        ind_name = args.name_kw
    likes = ' OR '.join(["p.position_type LIKE '%%,%d,%%'" % i for i in ind_ids])

    if args.scope == 'gd_ai':
        where_region = ("(a.province LIKE '%%广东%%' OR a.city IN (%s))"
                        % ','.join("'%s'" % c for c in GD_CITIES))
        region_label = '广东省'
    else:
        where_region = '1=1'
        region_label = '全国'

    days_cond = ''
    if args.days and args.days > 0:
        days_cond = " AND p.update_time >= DATE_SUB(NOW(), INTERVAL %d DAY)" % args.days

    if args.name_kw:
        base_where = ("p.publish_state='PUBLISHING' AND p.deleted=b'0' %s "
                      "AND p.name LIKE '%%%s%%'" % (days_cond, args.name_kw))
    else:
        base_where = ("p.publish_state='PUBLISHING' AND p.deleted=b'0' %s AND (%s)"
                      % (days_cond, likes))

    conn = pymysql.connect(host=cfg['host'], port=cfg['port'], user=cfg['user'],
                           password=cfg['password'], database=cfg['database'],
                           charset='utf8mb4', connect_timeout=10,
                           read_timeout=1800, write_timeout=60)

    qlog = []
    checks = []

    def q(sql):
        t0 = time.time()
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
        sec = time.time() - t0
        qlog.append({'sql': sql.replace('\n', ' '), 'rows': len(rows),
                     'seconds': round(sec, 1)})
        print('[%5.1fs] rows=%d  %s' % (sec, len(rows),
                                        sql[:70].replace('\n', ' ')))
        return rows

    def check(name, expect, actual, tol=0):
        ok = abs(float(expect) - float(actual)) <= tol
        checks.append({'name': name, 'expect': expect, 'actual': actual,
                       'pass': bool(ok)})
        return ok

    join = ('FROM c_company_position p '
            'JOIN c_company_address a ON p.company_address_id = a.id '
            'WHERE %s AND %s' % (base_where, where_region))

    level2 = [n['id'] for n in tree.values() if n['pid'] == args.industry]
    l3name = {n['id']: n['name'] for n in tree.values() if n['pid'] in level2}
    GROUP_OF = {}
    for g, members in rc.TRACK_GROUPS.items():
        for m in members:
            GROUP_OF[m] = g

    def pick_name(pt):
        ids = [int(x) for x in (pt or '').split(',') if x.strip().isdigit()]
        names = set(l3name[i] for i in ids if i in l3name)
        return next((n for n in PRIORITY if n in names), None)

    # 机器人方向表（--name-kw 模式）：按岗位名称关键词互斥归属，具体在前
    ROBOT_DIRS = [
        ('人形机器人/具身智能', ['人形', '具身']),
        ('工业机器人', ['工业机器人', '焊接机器人', '打磨机器人', '分拣机器人',
                    '码垛机器人', '喷涂机器人', '装配机器人', '搬运机器人',
                    '协作机器人', 'SCARA', 'Scara', 'scara', 'Delta机器人']),
        ('移动机器人(AMR/AGV)', ['AGV', 'agv', 'AMR', 'amr', '移动机器人', '无人叉车',
                            '叉车机器人', '配送机器人', '清扫机器人', '清洁机器人']),
        ('服务/特种机器人', ['服务机器人', '送餐机器人', '消毒机器人', '陪伴机器人',
                        '教育机器人', '机器人教师', '特种机器人', '巡检机器人',
                        '水下机器人', '消防机器人']),
        ('机器人算法与研发', ['机器人算法', '运动控制', 'SLAM', 'slam', '导航算法',
                        '规控', '路径规划', '感知算法', '机器人软件', '机器人视觉',
                        '控制算法']),
        ('机器人调试与运维', ['机器人调试', '机器人维护', '机器人维修', '机器人保养',
                        '机器人安装', '机器人运维', '机器人电气', '机器人装配',
                        '机器人测试', '机器人机械']),
        ('机器人销售与方案', ['机器人销售', '机器人方案', '机器人市场', '机器人渠道',
                        '机器人售前', '机器人项目经理']),
    ]

    def robot_pick(name):
        n = name or ''
        for key, kws in ROBOT_DIRS:
            if any(k in n for k in kws):
                return key
        return '其他机器人岗位'

    # ============ 1) 行级主扫描（一次取回全部字段） ============
    rows = q('SELECT a.city, p.name, p.position_type, p.education, p.experience, p.type, '
             'CAST(p.min_salary AS SIGNED), CAST(p.max_salary AS SIGNED), '
             'p.description ' + join)
    cnt = len(rows)
    comp_set = set()
    city_counter = Counter()
    sub_counter = Counter()
    edu_counter = Counter()
    exp_counter = Counter()
    type_counter = Counter()
    edu_exp_counter = Counter()
    city_group = {}
    city_total = Counter()
    mids = []
    tmap = {}
    wc = Counter()
    stack_wc = Counter()
    cooc = {}                     # 细分方向 -> Counter(技能词)
    cooc_den = Counter()          # 细分方向分母
    # 职教池
    p_cnt = 0
    p_city = Counter()
    p_track = Counter()
    p_mids = []
    p_wc = Counter()
    p_track_edu = {}
    p_track_exp = {}
    p_track_sal = {}

    for (city, pname, pt, edu, exp, jtype, lo, hi, desc) in rows:
        comp = None  # company_archive_id 未取（行数即岗位记录数）
        edu_n = EDU_MAP.get(edu, edu)
        exp_n = EXP_MAP.get(exp, exp)
        typ_n = TYPE_MAP.get(jtype, jtype)
        if args.name_kw:
            pick = robot_pick(pname)
            grp = pick
        else:
            pick = pick_name(pt)
            grp = GROUP_OF.get(pick, '其他') if pick else '其他'
        if city:
            city_counter[city] += 1
            city_group.setdefault(city, Counter())[grp] += 1
            city_total[city] += 1
        if pick:
            sub_counter[pick] += 1
        edu_counter[edu_n] += 1
        exp_counter[exp_n] += 1
        type_counter[typ_n] += 1
        edu_exp_counter[(edu_n, exp_n)] += 1
        try:
            lo2, hi2 = int(lo), int(hi)
            if 0 < lo2 <= hi2 <= 500:
                mids.append((lo2 + hi2) / 2)
                if pick:
                    tmap.setdefault(pick, []).append((lo2 + hi2) / 2)
        except (TypeError, ValueError):
            pass
        if desc:
            hit_words = [w for w in SKILL_WORDS if w in desc]
            for w in hit_words:
                wc[w] += 1
            if pick:
                cooc_den[pick] += 1
                c = cooc.setdefault(pick, Counter())
                for w in hit_words:
                    c[w] += 1
        if edu in VOC_EDU_KEYS and exp in VOC_EXP_KEYS:
            p_cnt += 1
            if city:
                p_city[city] += 1
            p_track[grp] += 1
            p_track_edu.setdefault(grp, Counter())[edu_n] += 1
            p_track_exp.setdefault(grp, Counter())[exp_n] += 1
            try:
                lo2, hi2 = int(lo), int(hi)
                if 0 < lo2 <= hi2 <= 500:
                    p_mids.append((lo2 + hi2) / 2)
                    p_track_sal.setdefault(grp, []).append((lo2 + hi2) / 2)
            except (TypeError, ValueError):
                pass
            if desc:
                for w in SKILL_WORDS:
                    if w in desc:
                        p_wc[w] += 1

    out = {'meta': {'region': region_label, 'industry': ind_name,
                    'name_kw': args.name_kw,
                    'industry_ids': ind_ids, 'days': args.days,
                    'generated_at': time.strftime('%Y-%m-%d %H:%M:%S')}}

    # 总量（企业数单独一条 SQL）
    comp_cnt = q('SELECT COUNT(DISTINCT p.company_archive_id) ' + join)[0][0]
    out['total'] = {'positions': cnt, 'companies': comp_cnt,
                    'cities': len(city_counter)}
    print('在招岗位 %s / 企业 %s / 城市 %s' % (human_cnt(cnt), human_cnt(comp_cnt),
                                          len(city_counter)))

    # ============ 2) 各维度（Python 聚合） ============
    out['city'] = [[c, n] for c, n in city_counter.most_common(21)]
    top2 = sum(n for _, n in out['city'][:2])
    out['city_top2_pct'] = round(top2 / cnt * 100, 1) if cnt else 0

    items = sorted(
        [{'name': k, 'count': c, 'pct': round(c / cnt * 100, 1)}
         for k, c in sub_counter.items()], key=lambda x: -x['count'])
    other_cnt = cnt - sum(sub_counter.values())
    if other_cnt > 0:
        items.append({'name': '其他', 'count': other_cnt,
                      'pct': round(other_cnt / cnt * 100, 1)})
    out['track'] = items
    out['subtrack'] = items

    for m, order, key in ((EDU_MAP, EDU_ORDER, 'edu'), (EXP_MAP, EXP_ORDER, 'exp')):
        out[key] = [{'name': k, 'count': edu_counter[k],
                     'pct': round(edu_counter[k] / cnt * 100, 1)}
                    for k in order if k in edu_counter] if key == 'edu' else \
                   [{'name': k, 'count': exp_counter[k],
                     'pct': round(exp_counter[k] / cnt * 100, 1)}
                    for k in order if k in exp_counter]
    out['jobtype'] = sorted(
        [{'name': k, 'count': v, 'pct': round(v / cnt * 100, 1)}
         for k, v in type_counter.items()], key=lambda x: -x['count'])

    # ============ 3) SQL GROUP BY 交叉验证（同一数字两种算法） ============
    sql_city = {c: n for c, n in q('SELECT a.city, COUNT(*) c ' + join +
                                   ' GROUP BY a.city')}
    sql_edu = Counter()
    for k, c in q('SELECT p.education, COUNT(*) ' + join + ' GROUP BY p.education'):
        sql_edu[EDU_MAP.get(k, k)] += c
    sql_exp = Counter()
    for k, c in q('SELECT p.experience, COUNT(*) ' + join + ' GROUP BY p.experience'):
        sql_exp[EXP_MAP.get(k, k)] += c
    sql_type = Counter()
    for k, c in q('SELECT p.type, COUNT(*) ' + join + ' GROUP BY p.type'):
        sql_type[TYPE_MAP.get(k, k)] += c
    sql_ee = Counter()
    for a, b, c in q('SELECT p.education, p.experience, COUNT(*) c ' + join +
                     ' GROUP BY p.education, p.experience'):
        sql_ee[(EDU_MAP.get(a, a), EXP_MAP.get(b, b))] += c

    check('城市: Python聚合 = SQL聚合', sum(city_counter.values()),
          sum(sql_city.values()))
    check('城市: 明细逐市一致', 0, sum(abs(city_counter.get(c, 0) - sql_city.get(c, 0))
                                    for c in set(city_counter) | set(sql_city)))
    check('学历: Python = SQL', sum(edu_counter.values()), sum(sql_edu.values()))
    check('学历: 明细逐档一致', 0, sum(abs(edu_counter.get(k, 0) - v)
                                    for k, v in sql_edu.items()))
    check('经验: Python = SQL', sum(exp_counter.values()), sum(sql_exp.values()))
    check('经验: 明细逐档一致', 0, sum(abs(exp_counter.get(k, 0) - v)
                                    for k, v in sql_exp.items()))
    check('岗位性质: Python = SQL', sum(type_counter.values()), sum(sql_type.values()))
    check('学历×经验: Python = SQL', sum(edu_exp_counter.values()), sum(sql_ee.values()))

    # ============ 4) 交叉矩阵 / LQ / 职教池 ============
    top_cities = [c for c, _ in Counter(city_total).most_common(6)]
    grp_sum = Counter()
    for cg in city_group.values():
        grp_sum.update(cg)
    top_grps = [g for g, _ in grp_sum.most_common(6)]
    cells = []
    for ri, c in enumerate(top_cities):
        for ci, g in enumerate(top_grps):
            n = city_group[c].get(g, 0)
            cells.append([ri, ci, round(n / city_total[c] * 100, 1)
                          if city_total[c] else 0])
    out['city_track'] = {
        'rows': [{'name': (c[:-1] if c.endswith('市') else c),
                  'count': city_total[c]} for c in top_cities],
        'cols': top_grps, 'cells': cells,
    }
    # LQ 专业化指数：本市赛道占比 / 全省赛道占比
    grp_all = Counter()
    for cg in city_group.values():
        grp_all.update(cg)
    lq_cells = []
    for ri, c in enumerate(top_cities):
        for ci, g in enumerate(top_grps):
            share_city = city_group[c].get(g, 0) / city_total[c] if city_total[c] else 0
            share_all = grp_all.get(g, 0) / cnt if cnt else 0
            lq_cells.append([ri, ci, round(share_city / share_all, 2)
                             if share_all else 0])
    out['city_lq'] = {'rows': out['city_track']['rows'], 'cols': top_grps,
                      'cells': lq_cells}
    check('交叉矩阵城市计数之和 = 总量', cnt, sum(city_total.values()), 0)

    out['edu_exp'] = [[e, x, c] for (e, x), c in sorted(edu_exp_counter.items())]
    pool = {'edu_keys': list(VOC_EDU_KEYS), 'exp_keys': list(VOC_EXP_KEYS),
            'count': p_cnt, 'pct': round(p_cnt / cnt * 100, 1) if cnt else 0}
    p_mids.sort()

    def ppct(p):
        return round(p_mids[int(len(p_mids) * p)], 1) if p_mids else 0

    pool['salary'] = {'valid': len(p_mids), 'median': ppct(0.5),
                      'p25': ppct(0.25), 'p75': ppct(0.75)}
    pool['city'] = [[c, n] for c, n in p_city.most_common(6)]
    pool['track'] = [{'name': g, 'count': n, 'pct': round(n / p_cnt * 100, 1)}
                     for g, n in p_track.most_common(7) if p_cnt]
    # 适配岗位族群明细：岗位量 / 月薪中位 / 最常见学历与经验要求（第四章明细表数据源）
    td = []
    for g, n in p_track.most_common(6):
        if not p_cnt or n < 30:
            continue
        arr = sorted(p_track_sal.get(g, []))
        edu_top = p_track_edu[g].most_common(1)
        exp_top = p_track_exp[g].most_common(1)
        td.append({'name': g, 'count': n,
                   'pct': round(n / p_cnt * 100, 1),
                   'median': round(arr[len(arr) // 2], 1) if arr else None,
                   'edu': edu_top[0][0] if edu_top else '-',
                   'exp': exp_top[0][0] if exp_top else '-'})
    pool['track_detail'] = td
    pool['keywords'] = [{'name': w, 'count': c} for w, c in p_wc.most_common(10)]
    out['voc_pool'] = pool
    m_pool = sum(c for (e, x), c in edu_exp_counter.items()
                 if e in VOC_EDU_NAMES and x in VOC_EXP_NAMES)
    check('职教池 与 学历×经验交叉 一致', m_pool, p_cnt)

    # ============ 5) 薪酬 ============
    mids.sort()
    n = len(mids)

    def spct(p):
        return round(mids[int(n * p)], 1) if n else 0

    out['salary'] = {'valid': n, 'valid_pct': round(n / cnt * 100, 1) if cnt else 0,
                     'p25': spct(0.25), 'median': spct(0.5), 'p75': spct(0.75),
                     'p90': spct(0.9)}
    bins = [(0, 5, '5K以下'), (5, 10, '5-10K'), (10, 15, '10-15K'), (15, 20, '15-20K'),
            (20, 30, '20-30K'), (30, 50, '30-50K'), (50, 500, '50K以上')]
    out['salary_hist'] = [
        {'name': lb, 'count': sum(1 for m in mids if lo <= m < hi),
         'pct': round(sum(1 for m in mids if lo <= m < hi) / n * 100, 1) if n else 0}
        for lo, hi, lb in bins]
    ts = []
    for name, arr in tmap.items():
        if len(arr) >= 30:
            arr.sort()
            ts.append({'name': name, 'count': len(arr),
                       'median': round(arr[len(arr) // 2], 1)})
    out['salary_by_track'] = sorted(ts, key=lambda x: -x['median'])
    check('薪资直方图合计 = 薪资样本数', n,
          sum(h['count'] for h in out['salary_hist']))
    check('分赛道薪酬样本（互斥）合计 <= 薪资样本数', 1,
          1 if sum(t['count'] for t in ts) <= n else 0)

    # ============ 6) 关键词 / 能力栈 / 岗位×技能矩阵 ============
    out['keywords'] = [{'name': w, 'count': c} for w, c in wc.most_common(18)]
    word2stack = {w: s for s, ws in SKILL_STACKS.items() for w in ws}
    for w, c in wc.items():
        stack_wc[word2stack.get(w, '其他')] += c
    out['skill_stacks'] = [
        {'name': s, 'count': stack_wc.get(s, 0),
         'top_words': [w for w, _ in wc.most_common(40) if word2stack.get(w) == s][:5]}
        for s in SKILL_STACKS]
    top6_sub = [x['name'] for x in items[:6] if x['name'] != '其他'][:6]
    top8_words = [w for w, _ in wc.most_common(12)][:8]
    out['job_skill'] = {
        'rows': top6_sub, 'cols': top8_words,
        'cells': [[ri, ci, round(cooc.get(r, {}).get(c, 0) / cooc_den[r] * 100, 1)
                   if cooc_den.get(r) else 0]
                  for ri, r in enumerate(top6_sub) for ci, c in enumerate(top8_words)],
    }

    # ============ 7) 月度更新量（仅留档，禁止用于趋势结论） ============
    trend_sql = ("SELECT DATE_FORMAT(p.update_time, '%Y-%m') ym, COUNT(*) c "
                 + join + ' GROUP BY ym ORDER BY ym')
    out['trend'] = [{'ym': r[0], 'count': r[1]} for r in q(trend_sql)]
    check('月度更新量合计 = 总量（仅留档）', cnt, sum(t['count'] for t in out['trend']))
    conn.close()

    # ============ 8) 溯源与快照 ============
    body_sha = hashlib.sha256(
        json.dumps(out, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    out['provenance'] = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'source_platform': '优才知路平台的数据库',
        'params': {'region': region_label, 'industry_id': args.industry,
                   'industry_name': ind_name, 'days': args.days},
        'queries': qlog,
        'checks': checks,
        'all_checks_pass': all(c['pass'] for c in checks),
        'data_sha256': body_sha,
    }

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    snap_dir = os.path.join(BASE, 'output', 'snapshots')
    os.makedirs(snap_dir, exist_ok=True)
    snap = os.path.join(snap_dir, 'snapshot_%s.json' % time.strftime('%Y%m%d_%H%M%S'))
    shutil.copyfile(args.out, snap)

    print('\n已保存 %s\n数据快照 %s' % (args.out, snap))
    print('对账 %d 项，%s' % (len(checks),
                             '全部通过' if out['provenance']['all_checks_pass']
                             else '存在未通过项'))
    print('总岗位 %d | 职教池 %d (%s%%) | LQ最大 %s | 能力栈 %s' % (
        cnt, p_cnt, pool['pct'],
        max(lq_cells, key=lambda x: x[2])[2] if lq_cells else '-',
        max(stack_wc.items(), key=lambda x: x[1])[0] if stack_wc else '-'))


if __name__ == '__main__':
    main()
