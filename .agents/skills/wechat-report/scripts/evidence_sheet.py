# -*- coding: utf-8 -*-
"""
evidence_sheet.py — 生成数据证据核查表（xlsx），供人工核对报告数字的计算过程
用法:
    python scripts/evidence_sheet.py               # 读 report_data.json
    python scripts/evidence_sheet.py --out output/evidence_核查表.xlsx

四张表：
    1 查询清单   每条 SQL 全文 / 返回行数 / 耗时 / 用途
    2 指标计算   指标名 / 结果值 / 计算式（人话） / 输入来源 / 对账结果
    3 关键数字   报告引用的核心数字 → report_data.json 字段路径（逐个可回查）
    4 元信息     生成时间 / 快照指纹 sha256 / 参数 / 对账总况
"""
import argparse
import json
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report_common as rc

HEAD_FILL = PatternFill('solid', fgColor='1E3A8A')
HEAD_FONT = Font(color='FFFFFF', bold=True, size=11)
MONO = 'Consolas'
THIN = Border(*[Side(style='thin', color='D9D9D9')] * 4)


def _sheet(wb, name, headers, widths):
    ws = wb.create_sheet(name)
    for i, (h, w) in enumerate(zip(headers, widths), 1):
        c = ws.cell(row=1, column=i, value=h)
        c.fill, c.font = HEAD_FILL, HEAD_FONT
        c.alignment = Alignment(horizontal='center', vertical='center')
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = 'A2'
    return ws


def _put(ws, row, values, mono_cols=(), wrap_cols=()):
    for i, v in enumerate(values, 1):
        c = ws.cell(row=row, column=i, value=v)
        c.border = THIN
        c.alignment = Alignment(vertical='top', wrap_text=(i in wrap_cols))
        if i in mono_cols:
            c.font = Font(name=MONO, size=10)


def rebuild_queries(d):
    """按 report_data.meta 重建取数当次的完整 SQL（与 fetch_data.py 完全一致）"""
    m = d['meta']
    if m.get('name_kw'):
        kw = m['name_kw']
        days = m['days']
        days_cond = (" AND p.update_time >= DATE_SUB(NOW(), INTERVAL %d DAY)" % days
                     if days else '')
        GD = ['广州市', '深圳市', '东莞市', '佛山市', '珠海市', '惠州市', '中山市',
              '江门市', '汕头市', '湛江市', '肇庆市', '揭阳市', '茂名市', '梅州市',
              '清远市', '韶关市', '潮州市', '河源市', '汕尾市', '阳江市', '云浮市']
        region = ("(a.province LIKE '%%广东%%' OR a.city IN (%s))"
                  % ','.join("'%s'" % c for c in GD))
        base = ("p.publish_state='PUBLISHING' AND p.deleted=b'0' %s "
                "AND p.name LIKE '%%%s%%'" % (days_cond, kw))
        join = ('FROM c_company_position p '
                'JOIN c_company_address a ON p.company_address_id = a.id '
                'WHERE %s AND %s' % (base, region))
        return [
            ('行级主扫描（岗位名称含"%s"）' % kw,
             'SELECT a.city, p.name, p.position_type, p.education, p.experience, '
             'p.type, CAST(p.min_salary AS SIGNED), CAST(p.max_salary AS SIGNED), '
             'p.description ' + join),
            ('总量·企业数', 'SELECT COUNT(DISTINCT p.company_archive_id) ' + join),
            ('交叉验证·城市', 'SELECT a.city, COUNT(*) c ' + join + ' GROUP BY a.city'),
            ('交叉验证·学历',
             'SELECT p.education, COUNT(*) ' + join + ' GROUP BY p.education'),
            ('交叉验证·经验',
             'SELECT p.experience, COUNT(*) ' + join + ' GROUP BY p.experience'),
            ('交叉验证·岗位性质',
             'SELECT p.type, COUNT(*) ' + join + ' GROUP BY p.type'),
            ('交叉验证·学历×经验',
             'SELECT p.education, p.experience, COUNT(*) c ' + join +
             ' GROUP BY p.education, p.experience'),
            ('月度更新量（仅留档）',
             "SELECT DATE_FORMAT(p.update_time, '%Y-%m') ym, COUNT(*) c " + join +
             ' GROUP BY ym ORDER BY ym'),
        ]
    ids = m['industry_ids']
    likes = ' OR '.join(["p.position_type LIKE '%%,%d,%%'" % i for i in ids])
    days = m['days']
    days_cond = (" AND p.update_time >= DATE_SUB(NOW(), INTERVAL %d DAY)" % days
                 if days else '')
    base = ("p.publish_state='PUBLISHING' AND p.deleted=b'0' %s AND (%s)"
            % (days_cond, likes))
    GD = ['广州市', '深圳市', '东莞市', '佛山市', '珠海市', '惠州市', '中山市',
          '江门市', '汕头市', '湛江市', '肇庆市', '揭阳市', '茂名市', '梅州市',
          '清远市', '韶关市', '潮州市', '河源市', '汕尾市', '阳江市', '云浮市']
    region = ("(a.province LIKE '%%广东%%' OR a.city IN (%s))"
              % ','.join("'%s'" % c for c in GD))
    join = ('FROM c_company_position p '
            'JOIN c_company_address a ON p.company_address_id = a.id '
            'WHERE %s AND %s' % (base, region))
    voc_edu = ('DAZHUAN', 'GAOZHI', 'ZHONGZHUAN/ZHONGJI', 'GAOZHONG',
               'CHUZHONGJIYIXIA', 'BUXIAN')
    voc_exp = ('ON_CAMPUS', 'GRADUATING', 'LESS_THAN_1', 'BUXIAN')
    return [
        ('行级主扫描（全部维度聚合的原始数据）',
         'SELECT a.city, p.position_type, p.education, p.experience, p.type, '
         'CAST(p.min_salary AS SIGNED), CAST(p.max_salary AS SIGNED), '
         'p.description ' + join),
        ('总量·企业数', 'SELECT COUNT(DISTINCT p.company_archive_id) ' + join),
        ('交叉验证·城市', 'SELECT a.city, COUNT(*) c ' + join +
         ' GROUP BY a.city'),
        ('交叉验证·学历',
         'SELECT p.education, COUNT(*) ' + join + ' GROUP BY p.education'),
        ('交叉验证·经验',
         'SELECT p.experience, COUNT(*) ' + join + ' GROUP BY p.experience'),
        ('交叉验证·岗位性质',
         'SELECT p.type, COUNT(*) ' + join + ' GROUP BY p.type'),
        ('交叉验证·学历×经验',
         'SELECT p.education, p.experience, COUNT(*) c ' + join +
         ' GROUP BY p.education, p.experience'),
        ('月度更新量（仅留档）',
         "SELECT DATE_FORMAT(p.update_time, '%Y-%m') ym, COUNT(*) c " + join +
         ' GROUP BY ym ORDER BY ym'),
        ('职教池行级明细（低门槛岗位）',
         'SELECT a.city, p.position_type, CAST(p.min_salary AS SIGNED), '
         'CAST(p.max_salary AS SIGNED), p.description ' + join +
         ' AND p.education IN (%s) AND p.experience IN (%s)'
         % (','.join("'%s'" % k for k in voc_edu),
            ','.join("'%s'" % k for k in voc_exp))),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=os.path.join(BASE, 'report_data.json'))
    ap.add_argument('--out', default=os.path.join(BASE, 'output',
                                                  'evidence_核查表.xlsx'))
    args = ap.parse_args()

    with open(args.data, 'r', encoding='utf-8') as f:
        d = json.load(f)
    prov = d.get('provenance') or {}
    qlog = prov.get('queries') or []
    checks = prov.get('checks') or []
    m = d.get('meta') or {}
    r = rc.derive(d)

    wb = Workbook()
    wb.remove(wb.active)

    # ---- 1 查询清单 ----
    ws = _sheet(wb, '1查询清单',
                ['序号', '用途', 'SQL 全文', '返回行数', '耗时(秒)'], [5, 22, 90, 9, 9])
    for i, (usage, sql) in enumerate(rebuild_queries(d), 1):
        rows_n = sec = ''
        for q in qlog:
            if sql[:80].replace('\n', ' ')[:60] in (q.get('sql') or '')[:60] \
               or (q.get('sql') or '').startswith(sql[:60]):
                rows_n, sec = q.get('rows', ''), q.get('seconds', '')
                break
        _put(ws, i + 1, [i, usage, sql, rows_n, sec], mono_cols=(3,))

    # ---- 2 指标计算 ----
    ws = _sheet(wb, '2指标计算',
                ['指标', '结果值', '计算式（人话描述）', '输入来源', '对账'],
                [26, 16, 52, 24, 10])
    ck = {c.get('name'): c for c in checks}
    def ok(name):
        c = ck.get(name)
        return {True: '✅一致', False: '❌不符'}.get(bool(c and c.get('pass')),
                                                '—')
    t = d['total']
    edu = {e['name']: e for e in d.get('edu', [])}
    rows2 = [
        ('在招岗位总量', t['positions'], '主扫描返回的行数（每行=1条在招岗位记录）',
         '行级主扫描', '—'),
        ('招聘企业数', t['companies'], 'COUNT(DISTINCT 企业id)', '查询2', '—'),
        ('覆盖城市数', t['cities'], '主扫描中去重城市数', '行级主扫描',
         ok('城市: Python聚合 = SQL聚合')),
        ('广深合计占比%', d.get('city_top2_pct'),
         '(深圳+广州岗位数) ÷ 总量 × 100', '城市分布', '—'),
        ('前5城占比%', r.get('city_top5_pct'), '前5城岗位数之和 ÷ 总量 × 100',
         '城市分布', '—'),
        ('四大方向合计占比%', r.get('top4_pct'),
         '主方向归属后前4组之和 ÷ 总量 × 100（每个岗位只计1个主方向）',
         '赛道互斥归属', '—'),
        ('第一大方向占比%',
         (r.get('track_core') or [{}])[0].get('pct', 0),
         '主方向归属后第一组 ÷ 总量 × 100', '赛道互斥归属', '—'),
        ('方向归属口径',
         '岗位名称关键词互斥归属' if m.get('name_kw') else '行业类目互斥主归属',
         '每个岗位只计一个主方向，占比之和≤100%', '—', '—'),
        ('本科及以上占比%', r.get('edu_above_benke_pct'),
         '(本科+硕士+博士) ÷ 总量 × 100', '学历分布',
         ok('学历: Python = SQL')),
        ('大专及以下占比%', r.get('edu_dazhuan_below_pct'),
         '(大专+高职+中专/中技+高中+初中及以下) ÷ 总量 × 100', '学历分布',
         ok('学历: Python = SQL')),
        ('1-5年经验合计占比%', r.get('exp_1_5_pct'),
         '(1-3年+3-5年) ÷ 总量 × 100', '经验分布', ok('经验: Python = SQL')),
        ('社招占比%', r.get('jobtype_soc_pct'), '社招 ÷ 总量 × 100',
         '岗位性质', ok('岗位性质: Python = SQL')),
        ('月薪中位数(K)', d.get('salary', {}).get('median'),
         '各岗位薪资区间中值=(最低+最高)/2 → 排序取中位', '行级主扫描·薪资列',
         ok('薪资直方图合计 = 薪资样本数')),
        ('P25/P75/P90(K)',
         '/'.join(str(d.get('salary', {}).get(k, '')) for k in
                  ('p25', 'p75', 'p90')),
         '薪资中值序列的 25/75/90 分位点', '行级主扫描·薪资列', '—'),
        ('方向薪酬中位数(K)',
         '; '.join('%s=%s' % (x['name'], x['median'])
                   for x in d.get('salary_by_track', [])[:5]),
         '各互斥主方向内，薪资区间中值排序取中位（样本≥30才输出）',
         '行级主扫描', '—'),
        ('低门槛岗位数(职教池)', (d.get('voc_pool') or {}).get('count'),
         '学历∈{大专,高职,中专/中技,高中,初中及以下,不限} 且 '
         '经验∈{应届/在校,1年以内,不限} 的行数', '行级主扫描',
         ok('职教池 与 学历×经验交叉 一致')),
        ('职教池占比%', (d.get('voc_pool') or {}).get('pct'),
         '职教池 ÷ 总量 × 100', '行级主扫描', '—'),
        ('职教池月薪中位数(K)',
         (d.get('voc_pool') or {}).get('salary', {}).get('median'),
         '池内岗位薪资区间中值排序取中位', '职教池明细', '—'),
        ('城市×赛道矩阵(%)', '见report_data.city_track',
         '每城市内部：该赛道岗位数 ÷ 本城市岗位数 × 100（行内占比）',
         '行级主扫描', ok('交叉矩阵城市计数之和 = 总量')),
        ('城市专业化倍数(LQ)', '见report_data.city_lq',
         '本市赛道占比 ÷ 全省该赛道占比（>1即更集中）', '行级主扫描', '—'),
        ('能力栈次数', '; '.join('%s=%s' % (x['name'], x['count'])
                                 for x in d.get('skill_stacks', [])),
         '36技能词按5栈归类，词频加总（未去重）', '行级主扫描·描述列', '—'),
        ('岗位×技能提及率(%)', '见report_data.job_skill',
         '该方向提到该词的岗位数 ÷ 该方向岗位数 × 100', '行级主扫描·描述列',
         '—'),
    ]
    for i, row in enumerate(rows2, 2):
        _put(ws, i, list(row), wrap_cols=(3,))

    # ---- 3 关键数字 ----
    ws = _sheet(wb, '3关键数字', ['报告中的数字', '值', 'report_data.json 路径'],
                [30, 16, 40])
    pool = d.get('voc_pool') or {}
    keys = [
        ('岗位总量', t['positions'], 'total.positions'),
        ('企业数', t['companies'], 'total.companies'),
        ('城市数', t['cities'], 'total.cities'),
        ('深圳岗位数', d['city'][0][1], 'city[0][1]'),
        ('广州岗位数', d['city'][1][1], 'city[1][1]'),
        ('广深合计占比', d.get('city_top2_pct'), 'city_top2_pct'),
        ('四大方向占比', r.get('top4_pct'), 'derive.top4_pct'),
        ('大模型占比', next((x['pct'] for x in r.get('track_core', [])
                              if '大模型' in x['name']), 0), 'track_groups[大模型].pct'),
        ('数据标注/AI训练岗位数', r.get('anno_group', {}).get('count'),
         'anno_group.count'),
        ('本科及以上占比', r.get('edu_above_benke_pct'), 'derive.edu_above_benke_pct'),
        ('大专及以下占比', r.get('edu_dazhuan_below_pct'),
         'derive.edu_dazhuan_below_pct'),
        ('月薪中位数', d.get('salary', {}).get('median'), 'salary.median'),
        ('P75', d.get('salary', {}).get('p75'), 'salary.p75'),
        ('方向薪酬榜首', (d.get('salary_by_track') or [{}])[0].get('name'),
         'salary_by_track[0].name'),
        ('低门槛岗位数', pool.get('count'), 'voc_pool.count'),
        ('低门槛占比', pool.get('pct'), 'voc_pool.pct'),
        ('低门槛月薪中位', (pool.get('salary') or {}).get('median'),
         'voc_pool.salary.median'),
    ]
    for i, row in enumerate(keys, 2):
        _put(ws, i, list(row))

    # ---- 4 元信息 ----
    ws = _sheet(wb, '4元信息', ['项', '值'], [26, 80])
    meta_rows = [
        ('生成时间', prov.get('generated_at')),
        ('数据快照指纹 sha256', prov.get('data_sha256')),
        ('统计参数', json.dumps(prov.get('params', {}), ensure_ascii=False)),
        ('对账项数', len(checks)),
        ('对账全部通过', '是' if prov.get('all_checks_pass') else '否'),
        ('说明', '本表由 scripts/evidence_sheet.py 生成；SQL 与 fetch_data.py '
                '执行时完全一致；核对方法：用表中 SQL 在数据库重跑，与"值"列'
                '比对。'),
    ]
    for i, row in enumerate(meta_rows, 2):
        _put(ws, i, list(row), wrap_cols=(2,))

    wb.save(args.out)
    print('证据核查表已生成: %s' % args.out)
    print('  4张表：查询清单 / 指标计算 / 关键数字 / 元信息')


if __name__ == '__main__':
    main()
