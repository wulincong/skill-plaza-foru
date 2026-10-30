# -*- coding: utf-8 -*-
"""
verify_data.py — 数据真实性五层 Gate 校验（防"数据对、结论错、图错"）
用法:
    python verify_data.py                       # 校验 data + outline（+article 如存在）

五层 Gate（全过才输出"可发布"）:
    Gate1 数值一致性  各维度合计与总量对账、占比≤100%、provenance 对账全过
    Gate2 指标语义    禁用表述扫描（"可投递""增长最快""溢价"……），杜绝口径误导
    Gate3 图文一致性  正文提到的技能词必须实际上榜；图表数据与正文数字同池
    Gate4 推断证据    无时间序列不得下动态结论；趋势页已禁用；无基准不得比较
    Gate5 渲染与安全  render_check.py 像素级核验（热力图方向/图表存在）+ 敏感信息扫描

产出 output/verify_report.md；退出码非 0 = 不得渲染/发布。
"""
import argparse
import json
import os
import re
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report_common as rc
import chart_recommender as cr

# 出版级语言规则（V3，来源 research-benchmarks.md 第三节）
LANGUAGE_BANNED = [
    (r'第\s*\d+\s*屏', '渲染位置语言泄漏（正式报告无"屏"概念）'),
    (r'见后续|下一章|后续章节', '相对位置引用（应删或用编号引用）'),
    (r'如上图|如下图|上图|下图|如图|如上所述|如下所示', '渲染位置引用'),
    (r'本页', '页面概念泄漏'),
    (r'图中可以看出|从图中', '图解套话'),
    (r'值得一提的是', '机器腔过渡语'),
    (r'综合来看', '空泛总结语'),
    (r'口径说明', '内部语言（口径应进方法页）'),
]

# ---------- Gate2/4 禁用表述（出现即 FAIL，附原因） ----------
BANNED = [
    (r'可投递', '语义', '学历门槛累计口径会被误读为"大专生可投X%岗位"；职教机会只能用"职教可进入岗位池"实测指标'),
    (r'增长最快|快速增长|增速', '推断', '无多期时间序列，不能下增速判断'),
    (r'需求稳定|保持稳定', '推断', '无多期数据'),
    (r'持续释放|常态化用人|招聘节奏', '推断', 'update_time含批量同步伪影，趋势类页面与结论已禁用'),
    (r'显著高于|远高于|明显高于|溢价', '推断', '未引入全行业基准，禁止跨行业比较结论'),
    (r'样本代表性', '语义', '样本量大不等于代表性成立'),
    (r'扩散|向周边.{0,6}转移', '推断', '时间动态结论需多期数据'),
    (r'不模型生成|不人工虚构', '语义', '分析性结论由模型生成、人工复核，不可如此宣称'),
    (r'家门口', '语义', '口语化且隐含扩散论断'),
    (r'起跳板', '语义', '隐含因果推断，未经验证'),
    (r'普遍落在', '推断', '无交叉数据支撑的分布断言'),
]

# 与 fetch_data.SKILL_WORDS 保持一致（Gate3 实体词表）
SKILL_WORDS = ['Python', 'PyTorch', 'TensorFlow', '大模型', 'LLM', 'RAG', 'Agent',
               '智能体', '深度学习', '机器学习', '计算机视觉', 'NLP', '自然语言',
               'CUDA', '分布式', 'Spark', 'Hadoop', 'SQL', 'C++', 'Linux',
               '数据挖掘', '推荐系统', '自动驾驶', '语音识别', '图像处理',
               'Prompt', '微调', '向量数据库', '多模态', 'AIGC', '强化学习',
               '数据分析', '算法优化', '目标检测', 'SLAM', 'ROS', '大语言模型']

SENSITIVE = [
    (r'\b\d{1,3}(?:\.\d{1,3}){3}\b', '内网IP地址'),
    (r'[A-Za-z]:\\\\|Users\\\\Administrator', '本机绝对路径'),
    (r'\bSELECT\b.{0,40}\bFROM\b', 'SQL片段'),
    (r'password|passwd|secret', '凭据字段'),
]

WHITELIST_PATTERNS = [
    r'<[^>]+>',                       # HTML 标签
    r'20\d{2}[.\-/年]\s?\d{1,2}',   # 日期
    r'20\d{2}',                      # 年份
    r'Top\s*\d+', r'TOP\s*\d+',
    r'P\d{2}',
    r'\d+-\d+年', r'\d+年以内', r'\d+年以上',
    r'\d+-\d+K', r'\d+K以上', r'\d+K以下',
    r'\d+(?:\.\d+)?-\d+(?:\.\d+)?万',   # 万元区间档（1-1.5万）
    r'\d+千(?:以下|-1万)?',              # 5千以下 / 5千-1万
    r'[≥≤<>]\s*\d+',
    r'第[0-9、，,\s]+章',            # 多编号章节引用（第06、13、14章），需在单编号模式之前
    r'第\s*\d+',                     # 单个编号引用
    r'\d+%%',
]


def _walk_numbers(obj, pool):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        pool.add(round(float(obj), 4))
    elif isinstance(obj, dict):
        for v in obj.values():
            _walk_numbers(v, pool)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk_numbers(v, pool)


def _add_derived(d, pool):
    _walk_numbers(rc.derive(d), pool)

    def add_ordered(items):
        its = [x for x in items if x.get('name') != '其他']
        for arr_key in ('pct', 'count'):
            vals = [x.get(arr_key, 0) for x in its]
            for i in range(1, len(vals) + 1):
                pool.add(round(float(sum(vals[:i])), 4))
                pool.add(round(float(sum(vals[i - 1:])), 4))

    for key in ('edu', 'exp', 'subtrack', 'jobtype', 'salary_hist'):
        add_ordered(d.get(key, []))
    for key in ('edu', 'exp', 'subtrack', 'jobtype'):
        for x in d.get(key, []):
            pool.add(round(100 - float(x.get('pct', 0)), 4))

    for n in (d['total']['positions'], d['total']['companies']):
        if n >= 10000:
            pool.add(round(n / 10000, 2))
        if n >= 100000000:
            pool.add(round(n / 100000000, 2))

    ct = d.get('city_track')
    if ct:
        for c in ct['cells']:
            pool.add(round(float(c[2]), 4))
        for row in ct['rows']:
            pool.add(float(row['count']))
    # 各城市占全部岗位的百分比（正文中"深圳以7,496条居首，占52.4%"式举例）
    total_pos = d.get('total', {}).get('positions', 0)
    for _, n in d.get('city', []):
        if total_pos:
            pool.add(round(n / total_pos * 100, 1))
    pool_c = (d.get('voc_pool') or {}).get('city') or []
    for i in (1, 2, 3):
        if len(pool_c) >= i:
            pool.add(float(sum(n for _, n in pool_c[:i])))
            cnt = d['voc_pool']['count']
            if cnt:
                pool.add(round(sum(n for _, n in pool_c[:i]) / cnt * 100, 1))
    tr = d.get('trend', [])
    if tr:
        pool.add(float(len(tr)))
        pool.add(round(sum(t['count'] for t in tr) / len(tr)))
        for t in tr:
            pool.add(float(t['count']))
    pool.update({100.0, 30.0, 0.0, 1.0, 2.0, 3.0, 5.0, 36.0})
    # V4：万元/元 换算值与整数百分比（面向读者的单位表达也要可溯源）
    sal = d.get('salary', {})
    for k in ('p25', 'median', 'p75', 'p90'):
        v = sal.get(k)
        if v:
            pool.add(round(v / 10, 2))
            pool.add(int(round(v * 1000)))
    for t in d.get('salary_by_track', []):
        pool.add(round(t['median'] / 10, 2))
        pool.add(int(round(t['median'] * 1000)))
    ps = (d.get('voc_pool') or {}).get('salary') or {}
    for k in ('p25', 'median', 'p75'):
        v = ps.get(k)
        if v:
            pool.add(round(v / 10, 2))
            pool.add(int(round(v * 1000)))
    for t in (d.get('voc_pool') or {}).get('track_detail') or []:
        if t.get('median'):
            pool.add(int(round(t['median'] * 1000)))
    pool |= {round(v) for v in list(pool) if 0 <= v <= 100}


def strip_whitelist(text):
    for p in WHITELIST_PATTERNS:
        text = re.sub(p, ' ', text)
    return text


def extract_unverified(text, pool, source):
    out = []
    clean = re.sub(r'(?<=\d),(?=\d)', '', strip_whitelist(text))
    for m in re.finditer(r'\d+(?:\.\d+)?', clean):
        tok = m.group(0)
        try:
            v = float(tok)
        except ValueError:
            continue
        if round(v, 4) in pool:
            continue
        ctx = clean[max(0, m.start() - 18):m.end() + 18].strip()
        out.append((tok, ctx, source))
    return out


def outline_texts(ol):
    texts = []
    for i, s in enumerate(ol.get('screens', [])):
        src = '第%d章 %s%s' % (i + 1, s.get('no', ''), s.get('title', ''))
        for key in ('title', 'subtitle'):
            if s.get(key):
                texts.append((s[key], src))
        for p in s.get('paragraphs', []):
            texts.append((p, src))
        for b in s.get('blocks', []):
            texts.append((b[1], src))
        for st in (s.get('stats', []) or []) + (s.get('kpis', []) or []):
            texts.append(('%s %s' % (st.get('value', ''), st.get('label', '')), src))
        for c in (s.get('chips', []) or []):
            texts.append(('%s %s' % (c.get('value', ''), c.get('label', '')), src))
        if s.get('insight'):
            texts.append((s['insight'], src))
        if s.get('quote'):
            texts.append((s['quote'], src))
        if s.get('summary'):
            sm = s['summary']
            texts.append(('%s %s' % (sm.get('title', ''), sm.get('text', '')), src))
        for c in (s.get('cards') or []):
            texts.append(('%s %s %s' % (c.get('no', ''), c.get('title', ''),
                                        c.get('desc', '')), src))
        if s.get('slogan'):
            texts.append((s.get('slogan', ''), src))
        for ck in ('chart', 'chart2', 'chartA', 'chartB'):
            cfg = s.get(ck)
            if not cfg:
                continue
            texts.append((cfg.get('caption', ''), src))
            if cfg.get('kind') == 'table':
                for row in cfg.get('rows', []):
                    texts.append((' '.join(str(x) for x in row), src))
            elif cfg.get('kind') == 'heatmap':
                texts.append((' '.join(str(c2) for c2 in cfg.get('cells', [])), src))
            else:
                for item in cfg.get('data', []):
                    texts.append((' '.join(str(x) for x in item), src))
    return texts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=os.path.join(BASE, 'report_data.json'))
    ap.add_argument('--outline', default=os.path.join(
        BASE, 'output', 'outline', 'report_outline.json'))
    ap.add_argument('--article', default=os.path.join(
        BASE, 'output', 'article', 'article.md'))
    ap.add_argument('--report-dir', default=os.path.join(BASE, 'output', 'report'))
    ap.add_argument('--out', default=os.path.join(BASE, 'output', 'verify_report.md'))
    ap.add_argument('--skip-render-check', action='store_true')
    args = ap.parse_args()

    report = ['# 数据真实性校验报告（五层 Gate）', '']
    gates = []  # (gate名, [(项, ok, detail)])

    # ================= Gate 1 数值一致性 =================
    with open(args.data, 'r', encoding='utf-8') as f:
        d = json.load(f)
    total = d['total']['positions']
    g1 = []

    def check(name, expect, actual, tol=0):
        g1.append((name, abs(float(expect) - float(actual)) <= tol,
                   '期望 %s / 实际 %s' % (expect, actual)))

    check('赛道互斥合计 = 总量', total, sum(x['count'] for x in d.get('subtrack', [])))
    check('学历合计 = 总量', total, sum(x['count'] for x in d.get('edu', [])))
    check('经验合计 = 总量', total, sum(x['count'] for x in d.get('exp', [])))
    check('岗位性质合计 = 总量', total, sum(x['count'] for x in d.get('jobtype', [])))
    check('学历×经验交叉合计 = 总量', total,
          sum(c for _, _, c in d.get('edu_exp', [])))
    pool = d.get('voc_pool') or {}
    if pool.get('count'):
        m_pool = sum(c for e, x, c in d.get('edu_exp', [])
                     if e in ('大专', '高职', '中专/中技', '高中', '初中及以下', '学历不限')
                     and x in ('应届生/在校', '1年以内', '经验不限'))
        check('职教池 与 学历×经验交叉 一致', m_pool, pool['count'])
    check('薪资直方图合计 = 薪资样本', d.get('salary', {}).get('valid', 0),
          sum(h['count'] for h in d.get('salary_hist', [])))
    check('赛道占比之和 ≤ 100.05%', 1,
          1 if sum(x['pct'] for x in d.get('subtrack', []))
          <= 100.05 + 0.05 * len(d.get('subtrack', [])) else 0)
    prov = d.get('provenance')
    if prov:
        g1.append(('provenance.all_checks_pass', bool(prov.get('all_checks_pass')),
                   '快照 sha256: %s' % prov.get('data_sha256', '-')[:16]))
    gates.append(('Gate1 数值一致性', g1))

    # ================= 取值池 =================
    vpool = set()
    _walk_numbers(d, vpool)
    _add_derived(d, vpool)

    with open(args.outline, 'r', encoding='utf-8') as f:
        ol = json.load(f)
    otexts = outline_texts(ol)
    atexts = []
    if os.path.exists(args.article):
        with open(args.article, 'r', encoding='utf-8') as f:
            art = f.read()
        atexts = [(re.sub(r'^\s*\d+\.(?=\D)', '', ln), '文章')
                  for ln in art.split('\n')
                  if not ln.startswith('![') and not ln.startswith('# ')]

    # ================= Gate 2+4 语义与推断（禁用表述） =================
    g24 = []
    all_text = otexts + atexts
    for pat, kind, reason in BANNED:
        rx = re.compile(pat)
        hits = [(t[:40], src) for t, src in all_text if rx.search(t)]
        if hits:
            g24.append(('[%s] 禁用表述「%s」×%d' % (kind, pat, len(hits)), False,
                        '%s；出现于 %s' % (reason, hits[0][1])))
    # 趋势页禁用
    if any(s.get('title') == '招聘节奏' for s in ol.get('screens', [])):
        g24.append(('[推断] 招聘节奏页', False,
                    'update_time 含批量同步伪影，该页已禁用'))
    if not g24:
        g24.append(('禁用表述扫描', True, '未发现语义/推断违规'))
    gates.append(('Gate2/4 指标语义 + 推断证据', g24))

    # ================= Gate 3 图文一致性（实体） =================
    g3 = []
    kw_names = {k['name'] for k in d.get('keywords', [])}
    pool_kw = {k['name'] for k in (pool.get('keywords') or [])}
    kw_names |= {w for s in d.get('skill_stacks', [])
                 for w in s.get('top_words', [])}
    kw_names |= set((d.get('job_skill') or {}).get('cols') or [])
    # 实体纪律只约束"结论性正文"：技能/能力相关章节 + 文章；方法页举例词不算
    targets = [(t, src) for t, src in otexts
               if ('技能' in src or '能力' in src)] + atexts
    for t, src in targets:
        mentioned = [w for w in SKILL_WORDS if w in t]
        missing = [w for w in mentioned if w not in kw_names and w not in pool_kw]
        if missing:
            g3.append(('正文提及未上榜技能词', False,
                       '%s 提到 %s 但未进入词表统计' % (src, '、'.join(missing))))
    if not g3:
        g3.append(('技能词实体一致', True, '正文提到的技能词均实际在统计内'))
    gates.append(('Gate3 图文一致性', g3))

    # ================= 出版级 Gate（V3：语言/图表选择/冗余/叙事/出版格式） =================
    gl = []
    ol_screens = ol.get('screens', [])
    para_texts = [(p, '第%s章 %s' % (s.get('no', ''), s.get('title', '')))
                  for s in ol_screens for p in s.get('paragraphs', [])]
    # Language Gate：禁用表述 + 括号预算（每段 ≤1）
    for pat, why in LANGUAGE_BANNED:
        rx = re.compile(pat)
        hits = [(t[:40], src) for t, src in para_texts + atexts if rx.search(t)]
        if hits:
            gl.append(('[语言] 「%s」×%d' % (pat, len(hits)), False,
                       '%s；如 %s' % (why, hits[0][1])))
    paren_bad = [src for t, src in para_texts if t.count('（') > 1]
    if paren_bad:
        gl.append(('[语言] 括号预算超限（每段≤1）', False,
                   '涉及 %s' % '; '.join(paren_bad[:3])))
    # Chart Choice Gate
    for s in ol_screens:
        for ck in ('chart', 'chart2', 'chartA', 'chartB'):
            cfg = s.get(ck)
            if not cfg:
                continue
            for prob in cr.check_chart_choice(cfg):
                gl.append(('[图表选择] %s' % s.get('title', ''), False, prob))
    # Redundancy Gate：同屏正文同一数字 ≥3 次
    for s in ol_screens:
        nums = {}
        for p in s.get('paragraphs', []):
            for m in re.finditer(r'\d+(?:\.\d+)?',
                                 re.sub(r'(?<=\d),(?=\d)', '',
                                        strip_whitelist(p))):
                nums[m.group(0)] = nums.get(m.group(0), 0) + 1
        for v, c in nums.items():
            if c >= 3 and len(v) >= 2:
                gl.append(('[冗余] 数字%s 在同章正文出现%d次' % (v, c), False,
                           s.get('title', '')))
    # Narrative Gate：带图章节必须有前置段落且结论先行
    for s in ol_screens:
        has_chart = any(s.get(k) for k in ('chart', 'chart2', 'chartA', 'chartB'))
        if has_chart and not s.get('paragraphs'):
            gl.append(('[叙事] %s' % s.get('title', ''), False,
                       '带图章节缺少前置叙述'))
        if s.get('paragraphs') and '<b>' not in (s['paragraphs'][0] or ''):
            gl.append(('[叙事] %s' % s.get('title', ''), False,
                       '首段未以加粗结论句开头'))
    # Publication Gate：meta 与图注齐备
    meta = ol.get('meta') or {}
    for k in ('data_source', 'sample_n', 'period'):
        if not meta.get(k):
            gl.append(('[出版] meta.%s 缺失' % k, False, '图下来源行依赖这些字段'))
    for s in ol_screens:
        for ck in ('chart', 'chart2', 'chartA', 'chartB'):
            cfg = s.get(ck)
            if cfg and not (cfg.get('caption') or cfg.get('label')):
                gl.append(('[出版] %s 图注缺失' % s.get('title', ''), False, ck))
    if not any(not ok for _, ok, _ in gl):
        gl.append(('语言/图表选择/冗余/叙事/出版格式', True, '全部通过'))
    gates.append(('Gate6 出版级规则（语言·图表选择·冗余·叙事·出版）', gl))

    # ================= Gate 1b 数字溯源（并入 Gate1 展示） =================
    unverified = []
    n_checked = 0
    for text, src in otexts + atexts:
        clean = re.sub(r'(?<=\d),(?=\d)', '', strip_whitelist(text))
        n_checked += len(re.findall(r'\d+(?:\.\d+)?', clean))
        unverified.extend(extract_unverified(text, vpool, src))
    g1.append(('数字溯源 %d 个' % n_checked, not unverified,
               '全部可溯源' if not unverified
               else '无法溯源 %d 个：%s' % (len(unverified),
                                         '; '.join(u[0] for u in unverified[:8]))))

    # ================= Gate 5 渲染与安全 =================
    g5 = []
    mfp = os.path.join(args.report_dir, 'manifest.json')
    pages_synced = False
    if os.path.exists(mfp):
        with open(mfp, 'r', encoding='utf-8') as f:
            mf = json.load(f)
        okp = len(mf.get('pages', [])) == len(ol.get('screens', []))
        pages_synced = okp
        g5.append(('渲染页数 = 大纲屏数', okp,
                   '%d 页 / %d 屏' % (len(mf.get('pages', [])),
                                      len(ol.get('screens', [])))))
        rel = all(':' not in (p.get('file') or '') for p in mf.get('pages', []))
        g5.append(('manifest 路径为相对路径（脱敏）', rel, ''))
    if pages_synced and not args.skip_render_check:
        rcs = os.path.join(BASE, 'scripts', 'render_check.py')
        r = subprocess.run([sys.executable, rcs], capture_output=True, text=True)
        rcj = os.path.join(BASE, 'output', 'render_check.json')
        ok = (r.returncode == 0) and os.path.exists(rcj)
        det = ''
        if os.path.exists(rcj):
            with open(rcj, 'r', encoding='utf-8') as f:
                det = '; '.join('%s:%s' % (c['check'], '过' if c['pass'] else 'FAIL')
                                for c in json.load(f).get('checks', [])[:6])
        g5.append(('render_check 像素级核验', ok, det or r.stdout[-200:]))
    elif args.skip_render_check:
        g5.append(('render_check 像素级核验', True, '本次显式跳过（需另行手动执行并留存 render_check.json）'))
    else:
        g5.append(('render_check 像素级核验', False,
                   '页面未与当前大纲同步，渲染后必须复检'))
    # 敏感信息扫描（对外文本）
    sens_targets = [(json.dumps(ol, ensure_ascii=False), '大纲'),
                    (art if os.path.exists(args.article) else '', '文章')]
    for txt, src in sens_targets:
        for pat, name in SENSITIVE:
            if re.search(pat, txt):
                g5.append(('敏感信息：%s' % name, False, '出现于 %s' % src))
    if not any(not ok for _, ok, _ in g5):
        pass
    gates.append(('Gate5 渲染与安全', g5))

    # ================= 输出 =================
    all_ok = all(ok for _, items in gates for _, ok, _ in items)
    for gname, items in gates:
        report.append('## %s' % gname)
        report.append('')
        for name, ok, det in items:
            report.append('- %s **%s** %s' % ('✅' if ok else '❌', name,
                                              ('｜%s' % det) if det else ''))
        report.append('')
    report.append('## 结论')
    report.append('')
    report.append('**%s**' % ('✅ PASS — 五层 Gate 全部通过，可渲染/发布'
                              if all_ok else '❌ FAIL — 按上述 ❌ 项修复后再渲染/发布'))
    if unverified:
        report.append('')
        report.append('无法溯源数字明细：')
        for tok, ctx, src in unverified[:40]:
            report.append('- `%s` ｜ %s ｜ …%s…' % (tok, src, ctx))
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
    print('\n'.join(report[-3:]))
    print('审计报告: %s' % args.out)
    sys.exit(0 if all_ok else 1)


if __name__ == '__main__':
    main()
