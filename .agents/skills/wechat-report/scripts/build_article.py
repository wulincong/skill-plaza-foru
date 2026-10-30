# -*- coding: utf-8 -*-
"""
build_article.py — 生成公众号文章（导语总结文案 + 报告分页图片引用）
用法:
    python build_article.py --report-dir output/report [--out output/article]
    python build_article.py --style data      # 数读速览式（默认）
    python build_article.py --style voc       # 院校视角式
    python build_article.py --style scene     # 场景切入式
产出 article/:
    article.md          # 文案 + 图片位（发布时按顺序把 png 上传到公众号后台）
    article.html        # 带样式预览版

导语写法与更多风格样例见 references/article-styles.md（风格库），
红线：数据来源只写"优才知路平台的数据库"。
"""
import argparse
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report_common  # noqa: E402

DATA_SOURCE = '优才知路平台的数据库'
STYLES = ('data', 'voc', 'scene')


def build_markdown(r, brand, pages, article_outdir, style='data'):
    t2 = r['city_top2']
    c1 = (t2[0][0][:-1] if t2 and t2[0][0].endswith('市') else (t2[0][0] if t2 else ''))
    c2 = (t2[1][0][:-1] if len(t2) > 1 and t2[1][0].endswith('市')
          else (t2[1][0] if len(t2) > 1 else ''))
    g = r.get('track_core', r['track_groups'])
    st = r['salary_top_track']
    anno = r['anno_group']
    md = []
    md.append('# %s|《%s》发布\n' % (brand['report_series'], r['title']))

    # ---------- 导语开头（三种自有风格） ----------
    if style == 'voc':
        md.append(
            '%s产业，中职、高职的学生进得去吗？这是很多职业院校老师、'
            '学生和家长最关心的问题。%s联合%s发布的《%s》，用%s条在招岗位的'
            '真实数据给出了回答：<b>进得去，而且通道清晰。</b>\n' % (
                r['industry'], brand['issuer'], brand['co_issuer'],
                r['title'], r['total_h']))
    elif style == 'scene':
        md.append(
            '一间数据标注车间里，几十名年轻人正给图像打标签、为模型"喂"数据——'
            '他们中的大多数，来自职业院校的人工智能技术应用等专业。这样的一幕，'
            '正在%s的智能工厂与数据公司里反复上演。它背后对应多少岗位机会？'
            '%s联合%s发布《%s》，用数据说话。\n' % (
                r['region'], brand['issuer'], brand['co_issuer'], r['title']))
    else:  # data 数读速览式
        md.append(
            '%s条在招岗位、%s家招聘企业、%d座城市——过去%s天，%s%s岗位市场'
            '的三个切面。《%s》把这三个数字背后的结构拆开给你看。\n' % (
                r['total_h'], r['companies_h'], r['cities'], r['days'],
                r['region'], r['industry'], r['title']))
        md.append(
            '这份报告由%s联合%s发布，岗位数据来源于%s，从企业真实招聘需求'
            '反推产业人才变化。\n' % (brand['issuer'], brand['co_issuer'],
                                   DATA_SOURCE))

    # ---------- 报告介绍（voc/scene 风格下补齐，data 风格已带） ----------
    if style != 'data':
        md.append(
            '报告基于%s%s条%s相关在招岗位记录，围绕城市分布、技术赛道、'
            '岗位结构、学历经验、薪酬水平及能力关键词进行系统分析。\n' % (
                r['region'], r['total_h'], r['industry']))

    # ---------- 三个核心信号 ----------
    md.append('数据呈现出几个值得关注的信号：\n')
    md.append('1.%s、%s两市招聘记录占全省样本%s%%，%s%s人才需求呈现明显"双核引领、周边梯度集聚"特征；\n' % (
        c1, c2, r['city_top2_pct'], r['region'], r['industry']))
    md.append('2.%s等主要方向合计占%s%%，%s岗位依旧是主战场，%s等环节岗位'
              '已形成完整的需求链条；\n' % (
                  g[0]['name'], r['top4_pct'], g[0]['name'],
                  ('%s（%s%%）' % (anno['name'], anno['pct']))
                  if anno.get('count') else '应用与实施'))
    md.append('3.岗位薪酬中位数达%sK/月%s，高薪背后，企业更看重"来了就能打仗"的实战能力。\n' % (
        r['salary']['median'],
        ('，%s方向中位数%sK/月领跑' % (st['name'], st['median'])) if st else ''))

    # ---------- 职教通道段（基于"职教可进入岗位池"实测指标） ----------
    pool = r.get('voc_pool') or {}
    if pool.get('count'):
        pcity = '、'.join((c[0][:-1] if c[0].endswith('市') else c[0])
                          for c in (pool.get('city') or [])[:3])
        md.append(
            '更值得职教圈注意的是：报告在岗位级做了交叉筛选——<b>学历要求为'
            '大专及以下或不限、且经验要求为应届/1年以内/不限</b>的"职教可进入'
            '岗位池"共<b>%s条</b>，占全部样本<b>%s%%</b>%s。这批岗位集中在哪里、'
            '做什么、薪酬如何，报告"交叉分析：学历×经验"一章专门拆解。\n' % (
                '{:,}'.format(pool['count']), pool.get('pct'),
                ('，主要分布在' + pcity) if pcity else ''))
    else:
        md.append(
            '要求大专及以下学历的%s岗位占%s%%——技术应用与维护环节的操作性岗位'
            '，构成了职业院校毕业生的对口空间。\n' % (
                r['industry'], r['edu_dazhuan_below_pct']))

    # ---------- 价值段 ----------
    md.append(
        '从"企业在招什么人"，进一步回答"职业院校应该培养什么人"，正是这份报告的核心价值。'
        '可为政府人才政策、企业人才规划、院校专业与课程建设、职业技能培训、'
        '人才评价标准及就业方向选择提供数据参考。\n')

    md.append(
        '%s产业竞争的下一阶段，不只是模型和算力的竞争，'
        '更是能否形成一支既懂技术、又懂工程、更懂产业场景的人才队伍。\n' % r['industry'])

    # 联系方式
    md.append('欢迎广大产业伙伴与院校交流沟通，携手共建产业人才发展生态！\n')
    md.append('**%s**\n' % brand['contact_name'])
    md.append('**%s**\n' % brand['contact_phone'])

    # 报告全文 = 图片（路径相对于文章输出目录）
    md.append('\n**阅读报告全文**\n')
    for p in pages:
        rel = os.path.relpath(p['file'], article_outdir)
        md.append('![%s](%s)\n' % (p['name'], rel.replace('\\', '/')))

    md.append('\n---\n*数据来源：%s｜发布：%s｜生成时间：%s*\n' % (
        DATA_SOURCE, brand['issuer'], r['generated_at'][:10]))
    return '\n'.join(md)


HTML_TMPL = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s</title>
<style>
body { max-width:677px; margin:0 auto; padding:28px 20px 60px;
  font-family:'Microsoft YaHei',sans-serif; color:#333; line-height:1.9; }
h1 { font-size:22px; line-height:1.5; margin-bottom:24px; }
p { font-size:16px; margin:0 0 20px; text-align:justify; }
img { width:100%%; display:block; margin:8px 0; }
hr { border:none; border-top:1px solid #eee; margin:28px 0; }
em { color:#999; font-size:13px; }
</style></head><body>
<h1>%(series)s|《%(title)s》发布</h1>
%(body)s
</body></html>"""


def md_to_html(md, r, brand):
    import re
    parts = []
    for block in md.split('\n'):
        b = block.strip()
        if not b:
            continue
        if b.startswith('# '):
            continue
        if b.startswith('!['):
            m = re.match(r'!\[(.*?)\]\((.*?)\)', b)
            if m:
                parts.append('<img src="%s" alt="%s">' % (m.group(2), m.group(1)))
                continue
        if b == '---':
            parts.append('<hr>')
            continue
        if b.startswith('*') and b.endswith('*') and not b.startswith('**'):
            parts.append('<em>%s</em>' % b.strip('*'))
            continue
        b = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', b)
        parts.append('<p>%s</p>' % b)
    return HTML_TMPL % {
        'title': r['title'], 'series': brand['report_series'],
        'body': '\n'.join(parts)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report-dir', default=os.path.join(BASE, 'output', 'report'))
    ap.add_argument('--out', default=None)
    ap.add_argument('--data', default=os.path.join(BASE, 'report_data.json'))
    ap.add_argument('--style', default='data', choices=STYLES,
                    help='导语风格：data=数读速览 voc=院校视角 scene=场景切入')
    args = ap.parse_args()

    with open(args.data, 'r', encoding='utf-8') as f:
        d = json.load(f)
    with open(os.path.join(BASE, 'assets', 'brand.json'), 'r', encoding='utf-8') as f:
        brand = json.load(f)
    r = report_common.derive(d)

    mp = os.path.join(args.report_dir, 'manifest.json')
    with open(mp, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    pages = manifest['pages']
    for p in pages:
        p['file'] = os.path.normpath(os.path.join(args.report_dir, p['file']))

    outdir = args.out or os.path.join(os.path.dirname(args.report_dir.rstrip('\\/')),
                                      'article')
    os.makedirs(outdir, exist_ok=True)

    md = build_markdown(r, brand, pages, outdir, style=args.style)
    with open(os.path.join(outdir, 'article.md'), 'w', encoding='utf-8') as f:
        f.write(md)
    html = md_to_html(md, r, brand)
    with open(os.path.join(outdir, 'article.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    print('文章已生成: %s（风格 %s）' % (outdir, args.style))


if __name__ == '__main__':
    main()
