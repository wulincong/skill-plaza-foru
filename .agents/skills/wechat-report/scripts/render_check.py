# -*- coding: utf-8 -*-
"""
render_check.py — 复核本次PNG、DOM布局、实际SVG图元和浏览器系列数据。
矩阵行列、类别顺序、计数/比例、中位点与区间必须匹配已绑定规格。
旧像素采样函数保留供人工定位问题，主验收不依赖整页颜色猜测。
"""
import argparse
import json
import os
import hashlib
from pathlib import Path

from PIL import Image
from chart_semantics import errors as semantic_errors

from report_runtime import report_root
BASE = str(report_root(__file__))
OUTLINE = os.path.join(BASE, 'output', 'outline', 'report_outline.json')
REPORT = os.path.join(BASE, 'output', 'report')


def _bands(ys, gap=6):
    bands = []
    for y in ys:
        if bands and y - bands[-1][1] <= gap:
            bands[-1][1] = y
        else:
            bands.append([y, y])
    return bands


def _rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def _spearman(a, b):
    if len(a) != len(b) or len(a) < 3:
        return -1
    ra, rb = _rank(a), _rank(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** .5
    db = sum((y - mb) ** 2 for y in rb) ** .5
    return num / (da * db) if da and db else -1


def _rgb(hexs):
    h = hexs.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _zhengwu_predicates():
    def is_cell(r, g, b):
        # 覆盖 #EFF6FF(最浅)到 #1E3A8A(最深)整个渐变段；白底/灰字/卡片底不命中
        return b > 190 and b - r > 8 and b >= g

    def depth(r, g, b):
        return b - (r + g) / 2
    return is_cell, depth


def band_funcs(theme_name):
    """按主题生成热力图像素判据（is_cell）与色深度量（depth）。

    zhengwu 保持历史蓝色判据（基线不变）；其他主题按 themes.json 的
    heat 色带端点做"到线段距离"匹配，色深=在色带上的投影进度。
    """
    if theme_name == 'zhengwu':
        return _zhengwu_predicates()
    with open(os.path.join(BASE, 'assets', 'themes.json'),
              'r', encoding='utf-8') as f:
        themes = json.load(f)
    t = themes[theme_name]
    A, B = _rgb(t['heat'][0]), _rgb(t['heat'][-1])
    ab = [b_ - a_ for a_, b_ in zip(A, B)]
    ab2 = sum(v * v for v in ab)

    def proj(r, g, b):
        u = [c - a_ for c, a_ in zip((r, g, b), A)]
        tt = sum(x * y for x, y in zip(u, ab)) / ab2
        d = max(0., sum(v * v for v in u) - tt * tt * ab2) ** .5
        return tt, d

    def is_cell(r, g, b):
        tt, d = proj(r, g, b)
        if not (0 <= tt <= 1.001 and d <= 48):
            return False
        return sum((c - cd) ** 2 for c, cd in zip((r, g, b), card)) ** .5 > 26

    def depth(r, g, b):
        tt, _ = proj(r, g, b)
        return tt

    card = _rgb(t['card'])
    return is_cell, depth


def check_heatmap(png, cfg, is_cell=None, depth=None, card_rgb=(245, 247, 251)):
    """cfg: outline 里 kind=heatmap 的配置；返回 (pass, detail)

    检测方式：找到蓝色单元格的包围盒（取最长连续块，避开正文/图例），
    按 R×C 均分网格采样色深，与期望数值矩阵做秩相关。不依赖单元格间隙。
    """
    rows = cfg.get('rows', [])
    cols = cfg.get('cols', [])
    cells = cfg.get('cells', [])
    R, C = len(rows), len(cols)
    im = Image.open(png).convert('RGB')
    W, H = im.size
    px = im.load()

    if is_cell is None or depth is None:
        is_cell, depth = _zhengwu_predicates()

    # 0) 先定位图表卡（底色=主题卡片色），把上方段落文字的抗锯齿像素排除在外
    y_lo, y_hi = 0, H - 1
    card_rows = [y for y in range(0, H)
                 if sum(1 for x in range(60, min(900, W), 4)
                        if abs(px[x, y][0] - card_rgb[0]) < 6
                        and abs(px[x, y][1] - card_rgb[1]) < 6
                        and abs(px[x, y][2] - card_rgb[2]) < 6) > 200]
    if card_rows:
        y_lo, y_hi = min(card_rows), max(card_rows)

    # 1) 行方向：每行蓝色命中数 → 取最长连续块（允许 ≤12px 空洞）
    row_cnt = []
    for y in range(y_lo, y_hi + 1):
        cnt = 0
        for x in range(340, min(910, W), 3):
            if is_cell(*px[x, y]):
                cnt += 1
        row_cnt.append(cnt)
    thresh = max(6, C * 2)
    hit_ys = [y_lo + i for i, c in enumerate(row_cnt) if c >= thresh]
    y0, y1 = _longest_run(hit_ys, hole=12)
    if y0 is None or (y1 - y0) < R * 20:
        return False, '未找到热力图单元格区域（蓝色命中不足）'
    # 2) 列方向：在行块内做 x 直方图 → 最长连续块
    xh = {}
    for y in range(y0, y1 + 1, 2):
        for x in range(340, min(910, W), 2):
            if is_cell(*px[x, y]):
                xh[x] = xh.get(x, 0) + 1
    hit_xs = sorted(x for x, c in xh.items() if c >= 3)
    x0, x1 = _longest_run(hit_xs, hole=12)
    if x0 is None or (x1 - x0) < C * 20:
        return False, '未找到热力图列区域'
    # 3) 均分网格，采样单元格色深（蓝度 = b - (r+g)/2）
    got = []
    exp = []
    grid = {(ri, ci): v for ri, ci, v in cells}
    for ri in range(R):
        for ci in range(C):
            ya = y0 + (y1 - y0 + 1) * ri // R
            yb = y0 + (y1 - y0 + 1) * (ri + 1) // R
            xa = x0 + (x1 - x0 + 1) * ci // C
            xb = x0 + (x1 - x0 + 1) * (ci + 1) // C
            s = n = 0
            # 采样避开单元格中央文字带（取上下两条带）
            bands_y = list(range(ya + (yb - ya) // 10, ya + (yb - ya) * 3 // 10, 3)) + \
                      list(range(ya + (yb - ya) * 7 // 10, yb - (yb - ya) // 10, 3))
            for y in bands_y:
                for x in range(xa + (xb - xa) // 5, xb - (xb - xa) // 5, 3):
                    r, g, b = px[x, y]
                    s += depth(r, g, b)
                    n += 1
            got.append(s / n if n else 0)
            exp.append(grid.get((ri, ci), 0))
    corr = _spearman(got, exp)
    corr_T = _spearman(got, exp_T(R, C, cells)) if R == C else -1
    # 转置判定需要强证据：转置方向自身高相关且高于正向（避免低方差噪声误报）
    if corr_T >= 0.85 and corr_T > corr + 0.02:
        return False, ('疑似行列转置：色深/数值秩相关 corr=%.3f，转置 corr=%.3f'
                       % (corr, corr_T))
    if corr >= 0.85:
        return True, ('色深矩阵与数值矩阵秩相关 corr=%.3f（阈值0.85，转置对照%.3f）'
                      % (corr, corr_T))
    # 全矩阵秩相关不足时，用定向探针复核极值格（对采样噪声鲁棒，仍可抓转置）
    def probe(ri, ci):
        """定向探针：采样单元格左右侧带（避开中央数值文字），取两侧均值较大者"""
        ya = y0 + (y1 - y0 + 1) * ri // R
        yb = y0 + (y1 - y0 + 1) * (ri + 1) // R
        xa = x0 + (x1 - x0 + 1) * ci // C
        xb = x0 + (x1 - x0 + 1) * (ci + 1) // C
        out = []
        for x0_, x1_ in ((xa + (xb - xa) // 6, xa + (xb - xa) // 3),
                         (xa + (xb - xa) * 2 // 3, xb - (xb - xa) // 6)):
            s = n = 0
            for y in range(ya + (yb - ya) // 6, yb - (yb - ya) // 6, 3):
                for x in range(x0_, x1_, 3):
                    r, g, b = px[x, y]
                    s += depth(r, g, b)
                    n += 1
            out.append(s / n if n else 0)
        return max(out)

    ei = exp.index(max(exp))
    er, ec = ei // C, ei % C
    b_med = sorted(got)[len(got) // 2]
    b_direct = probe(er, ec)
    b_trans = probe(ec, er) if (ec, er) != (er, ec) and ec < R and er < C else -1
    top_g = set(sorted(range(len(got)), key=lambda i: -got[i])[:6])
    top_e = set(sorted(range(len(exp)), key=lambda i: -exp[i])[:6])
    overlap = len(top_g & top_e)
    if b_direct >= b_trans and b_direct > b_med + 2:
        return True, ('全矩阵corr=%.3f 不足，定向探针通过：期望最深格(行%d列%d)'
                      '色深%.1f ≥ 转置位%.1f 且高于中位%.1f'
                      % (corr, er, ec, b_direct, b_trans, b_med))
    if b_direct >= b_trans and overlap >= 4:
        return True, ('低方差矩阵回退判据通过：最深格探针一致，Top6重合%d/6'
                      % overlap)
    return False, ('色深矩阵与数值矩阵不匹配：corr=%.3f，探针 直%.1f/转%.1f/'
                   '中位%.1f，Top6重合%d/6'
                   % (corr, b_direct, b_trans, b_med, overlap))


def _longest_run(xs, hole=12):
    """最长连续段（允许 ≤hole 的空洞）；xs 需有序。返回 (start, end) 或 (None, None)"""
    if not xs:
        return None, None
    best = (xs[0], xs[0])
    cur_s = xs[0]
    prev = xs[0]
    for x in xs[1:]:
        if x - prev > hole:
            cur_s = x
        prev = x
        if prev - cur_s > best[1] - best[0]:
            best = (cur_s, prev)
    return best


def exp_T(R, C, cells):
    grid = {(ri, ci): v for ri, ci, v in cells}
    return [grid.get((ci, ri), 0) for ri in range(R) for ci in range(C)]


def check_colored(png):
    """图表存在性：彩色（非灰）像素量"""
    im = Image.open(png).convert('RGB')
    W, H = im.size
    px = im.load()
    cnt = 0
    # Short charts may start near the top; exclude the chapter header and edge bar.
    for y in range(int(H * 0.12), int(H * 0.92), 3):
        for x in range(60, min(890, W), 3):
            r, g, b = px[x, y]
            if max(r, g, b) - min(r, g, b) > 28:
                cnt += 1
    return cnt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--outline', default=OUTLINE)
    ap.add_argument('--report-dir', default=REPORT)
    ap.add_argument('--out', default=os.path.join(BASE, 'output',
                                                  'render_check.json'))
    ap.add_argument('--theme', default='zhengwu',
                    help='与 render_report.py --theme 一致；热力图判据跟随主题')
    args = ap.parse_args()

    with open(args.outline, 'r', encoding='utf-8') as f:
        ol = json.load(f)
    manifest = json.loads((Path(args.report_dir)/'manifest.json').read_text('utf-8'))
    results = []
    all_ok = bool(ol.get('screens'))
    for i, s in enumerate(ol.get('screens', [])):
        png = os.path.join(args.report_dir, 'pages', 'page_%02d.png' % i)
        if not os.path.exists(png):
            results.append({'page': i, 'screen': s.get('title', ''), 'check': '图片存在性', 'pass': False, 'detail': '缺少本次图片'})
            all_ok = False
            continue
        results.append({'page': i, 'screen': s.get('title', ''), 'check': '图片存在性', 'pass': True, 'detail': '存在'})
        charts = [s.get(k) for k in ('chart', 'chart2', 'chartA', 'chartB')]
        charts = [c for c in charts if c]
        page = manifest.get('pages', [])[i] if i < len(manifest.get('pages', [])) else {}
        layout = page.get('layout', {})
        expected = sum(c['kind'] not in ('table','bignum') for c in charts)
        valid = (manifest.get('schema') == 'wechat-render/2' and manifest.get('theme') == args.theme
                 and page.get('sha256') == hashlib.sha256(Path(png).read_bytes()).hexdigest()
                 and layout.get('schema') == 'wechat-layout/2' and not layout.get('errors', ['missing'])
                 and len(layout.get('charts', [])) == expected
                 and all(c.get('shapes', 0) >= 2 for c in layout.get('charts', [])))
        with Image.open(png) as image:
            valid = valid and image.size == (page.get('width', 0)*page.get('scale', 1), page.get('height', 0)*page.get('scale', 1))
        results.append({'page':i, 'screen':s.get('title',''), 'check':'布局、图表就绪与图片指纹',
                        'pass':bool(valid), 'detail':'通过' if valid else '渲染证据缺失、布局错误或图片已改变'})
        all_ok = all_ok and valid
        visual=[c for c in charts if c['kind'] not in ('table','bignum')]
        for cfg,actual in zip(visual,layout.get('charts',[])):
            problems=semantic_errors(cfg,actual)
            results.append({'page':i,'screen':s.get('title',''),'check':'实际系列数据与图表方向',
                            'pass':not problems,'detail':'通过' if not problems else '；'.join(problems)})
            all_ok=all_ok and not problems

    out = {'all_pass': bool(all_ok), 'checks': results}
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    for r in results:
        print('[%s] 第%d页 %s · %s：%s' % ('✅' if r['pass'] else '❌',
                                          r['page'], r['screen'],
                                          r['check'], r['detail']))
    print('render_check: %s （明细 %s）' % (
        'PASS' if all_ok else 'FAIL', args.out))
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys_exit = main()
    raise SystemExit(sys_exit)
