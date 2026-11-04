# -*- coding: utf-8 -*-
"""
render_report.py — 把 report_outline.json（经数据校验的内部排版结构）渲染成报告图片
以 943px 为设计宽度，根据浏览器实测内容高度输出分屏。

用法:
    python render_report.py --outline output/outline/report_outline.json
    python render_report.py --outline xx.json --outdir output/report --scale 1

产出: pages/page_NN.png（943px 宽）+ report_full.png/jpg（拼接长图）+ manifest.json
"""
import argparse
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
from contextlib import nullcontext
from importlib.util import find_spec
from time import perf_counter
from bound_report import load_data, verify_outline, digest

from PIL import Image
from chart_layout import chart_js as modern_chart_js, chart_height, MEASURE_SCRIPT
import html as html_module

from report_runtime import report_root
BASE = str(report_root(__file__))
EDGE = os.environ.get('WECHAT_REPORT_BROWSER') or next(
    (p for p in (shutil.which('msedge'), shutil.which('google-chrome'),
                 shutil.which('chromium'), shutil.which('chromium-browser'),
                 r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
     if p and os.path.isfile(p)), None)
ASSETS = os.path.join(BASE, 'assets')
ECHARTS_URL = Path(ASSETS, 'echarts.min.js').resolve().as_uri()

# ===== 版式规范（来源：参考文章像素测量，详见 references/image-spec.md）=====
PAGE_W = 943            # 与原文一致
PAD_X = 42              # 左右边距（原文 40-45）
PAD_TOP = 60
PAD_BOTTOM = 34
CONTENT_W = PAGE_W - PAD_X * 2   # 859

C_PRIMARY = '#1E3A8A'
C_SECOND = '#3B82F6'
C_ACCENT = '#F97316'
C_TEAL = '#06B6D4'
C_TEXT = '#1F2937'
C_SUB = '#6B7280'
C_CARD = '#F5F7FB'

# ---------- 配色主题（assets/themes.json，--theme 手选；zhengwu=历史默认） ----------
THEME_FILE = os.path.join(BASE,
                          'assets', 'themes.json')


def load_theme(name):
    with open(THEME_FILE, 'r', encoding='utf-8') as f:
        themes = json.load(f)
    if name not in themes or name.startswith('_'):
        raise SystemExit('未知主题 "%s"，可用：%s' % (
            name, '、'.join(k for k in themes if not k.startswith('_'))))
    return themes[name]


THEME = load_theme('zhengwu')


def TH(key):
    """渲染期取当前主题色（main 里 apply_theme 后生效）"""
    return THEME[key]

CSS_TMPL = """
* { margin:0; padding:0; box-sizing:border-box; }
html,body { width:%(W)dpx; background:%(PBG)s;
  font-family:'Microsoft YaHei','PingFang SC',sans-serif;
  -webkit-font-smoothing:antialiased; }
.page { width:%(W)dpx; position:relative; background:%(PBG)s; overflow:hidden;
  padding:%(PT)dpx %(PX)dpx %(PB)dpx; }
/* 右侧装饰条（原文有） */
.edgebar { position:absolute; right:0; top:0; bottom:0; width:10px;
  background:linear-gradient(180deg,%(PRI)s,%(SEC)s); }
/* 章节头 */
.chapter { display:flex; align-items:center; gap:14px; }
.chapter .no { background:%(PRI)s; color:#fff; font-size:26px; font-weight:700;
  border-radius:12px; padding:6px 18px; letter-spacing:2px; }
.chapter .no { flex:none; }
.chapter .tt { font-size:47px; line-height:1.32; font-weight:700; color:%(HEAD)s; }
/* V4：短章节名 + 结论标题（读者问题式） */
.kicker2 { font-size:22px; color:%(SUB)s; letter-spacing:3px; font-weight:600;
  margin-bottom:10px; }
.tt2 { font-size:40px; font-weight:700; color:%(HEAD)s; line-height:1.32; }
/* V5：彩色"产业观察"洞察框（对标参考公众号） */
.insight { background:%(INSBG)s; border-left:8px solid %(ACC)s;
  border-radius:14px; padding:26px 28px; margin-top:6px; }
.insight .tag { color:%(PRI)s; font-weight:700; font-size:22px;
  letter-spacing:3px; margin-bottom:10px; }
.insight .txt { font-size:24px; line-height:1.75; color:%(TXT)s;
  text-align:justify; }
/* V5：金句框（末章升华） */
.quote { margin:26px 30px 8px; padding:30px 20px;
  border-top:3px solid %(PRI)s; border-bottom:3px solid %(PRI)s;
  font-size:28px; line-height:1.7; color:%(PRI)s; font-weight:700;
  text-align:center; }
/* 复刻版：摘要页核心判断卡 */
.sumcard { display:flex; gap:20px; background:%(CARD)s; border-radius:16px;
  padding:28px 26px; margin-bottom:22px; align-items:flex-start; }
.sumcard .no2 { flex:none; width:64px; height:64px; border-radius:16px;
  background:%(PRI)s; color:#fff; font-size:30px; font-weight:700;
  display:flex; align-items:center; justify-content:center; }
.sumcard .bd .jt { font-size:27px; font-weight:700; color:%(HEAD)s;
  line-height:1.5; margin-bottom:10px; }
.sumcard .bd .ds { font-size:23px; color:#4B5563; line-height:1.7;
  text-align:justify; }
/* 摘要页"核心结论"标题栏 */
.corebar { display:inline-block; background:%(PRI)s; color:#fff;
  font-size:24px; font-weight:700; padding:10px 28px; border-radius:10px;
  letter-spacing:5px; margin:2px 0 22px; }
/* 章末灵活小标题总结框（主题色系，区别于正文与图卡） */
.sbox { background:%(SBG)s; border-left:8px solid %(ACC)s;
  border-radius:14px; padding:24px 28px; margin-top:10px; }
.sbox .st { color:%(STT)s; font-weight:700; font-size:30px;
  letter-spacing:1px; margin-bottom:8px; }
.sbox .sx { font-size:36px; color:%(STX)s; line-height:1.55;
  text-align:justify; }
.subtitle { margin-top:14px; font-size:23px; color:%(SUB)s; letter-spacing:1px; }
.hr { margin:20px 0 24px; height:5px; width:120px;
  background:linear-gradient(90deg,%(PRI)s,%(ACC)s); border-radius:3px; }
/* 段落式正文（复刻原文：27px/1.85/两端对齐） */
.paras { margin-bottom:26px; }
.paras p { font-size:38px; line-height:1.55; color:%(TXT)s; text-align:left;
  margin-bottom:18px; letter-spacing:.3px; }
.paras .label { display:block; margin:26px 0 6px; color:%(PRI)s; font-size:29px; font-weight:700; }
.paras b { color:%(PRI)s; }
/* 数据卡 */
.stats { display:flex; gap:16px; margin-bottom:24px; }
.stat { flex:1; background:%(CARD)s; border-radius:14px; padding:20px 8px;
  text-align:center; }
.stat.hot { background:%(ZBG)s; }
.stat .v { font-size:36px; font-weight:700; color:%(PRI)s; }
.stat.hot .v { color:%(ACC)s; }
.stat .v.name { font-size:28px; }
.stat .l { margin-top:6px; font-size:19px; color:%(SUB)s; }
/* 图表卡片 */
.card { background:%(CARD)s; border-radius:16px; padding:24px 24px 10px;
  margin-bottom:20px; }
.card .cap { font-size:30px; font-weight:600; color:%(SUB)s; text-align:center; margin-bottom:4px; }
/* 数据表格（kind=table） */
.dtable { width:100%%; border-collapse:collapse; margin:10px 0 14px; }
.dtable th { background:%(PRI)s; color:#fff; font-size:30px; padding:15px 12px;
  font-weight:600; text-align:center; }
.dtable th:first-child { border-radius:12px 0 0 0; }
.dtable th:last-child { border-radius:0 12px 0 0; }
.dtable td { text-align:center; font-size:30px; padding:14px 12px; border-bottom:1px solid #E5E7EB;
  color:%(TXT)s; }
.dtable tr:nth-child(even) td { background:%(ZEB)s; }
.dtable tr:last-child td { border-bottom:none; }
.dtable td.num { text-align:right; font-variant-numeric:tabular-nums; }
.dtable td.hot { color:%(STT)s; font-weight:700; }
.rk { display:inline-block; min-width:42px; padding:3px 0; margin-right:12px;
  text-align:center; border-radius:9px; font-size:19px; color:#fff;
  background:%(GREY)s; }
.rk.r1 { background:%(ACC)s; } .rk.r2 { background:%(PRI)s; }
.rk.r3 { background:%(SEC)s; }
/* 准入矩阵：职教可进入区域 */
.dtable td.zone { background:%(ZBG)s !important; color:%(STT)s; font-weight:700; }
.dtable td.zone::after { content:' ★'; font-size: 18px; }
/* 大数字卡（极端不均衡构成，本项目可读性策略替代饼图） */
.bignum { background:%(CARD)s; border-radius:16px; padding:34px 30px 26px;
  margin-bottom:20px; text-align:center; }
.bignum .big { font-size:96px; font-weight:700; color:%(PRI)s; line-height:1.1; }
.bignum .big small { font-size:40px; }
.bignum .cap2 { font-size:24px; color:#374151; margin-top:8px; }
.bignum .rest { display:flex; justify-content:center; gap:44px;
  margin-top:22px; }
.bignum .rest .it { text-align:center; }
.bignum .rest .v { font-size:34px; font-weight:700; color:%(GREY)s; }
.bignum .rest .l { font-size:19px; color:%(SUB)s; margin-top:2px; }
.minibar { height:16px; background:#E5E7EB; border-radius:8px; overflow:hidden;
  margin:10px auto 0; width:70%%; }
.minibar i { display:block; height:100%%; background:%(PRI)s; border-radius:8px; }
/* 图表卡来源脚注 */
.src { font-size:25px; color:%(SUB)s; text-align:center;
  margin:0 0 12px; letter-spacing:.5px; }
/* 页脚 */
.footer { border-top:2px solid #e5e7eb; margin-top:32px; padding-top:18px;
  display:flex; justify-content:space-between; align-items:center; }
.footer .org { font-size:24px; color:%(SUB)s; }
.footer .dots { display:flex; gap:9px; }
.footer .d { width:11px; height:11px; border-radius:50%%; background:#E5E7EB; }
.footer .d.on { background:%(PRI)s; }
"""


def _css_params():
    return {'W': PAGE_W, 'PX': PAD_X, 'PT': PAD_TOP, 'PB': PAD_BOTTOM,
            'PRI': THEME['primary'], 'SEC': THEME['secondary'],
            'ACC': THEME['accent'], 'SUB': THEME['sub'], 'TXT': THEME['text'],
            'CARD': THEME['card'], 'PBG': THEME['page_bg'],
            'HEAD': THEME['head'], 'INSBG': THEME['insight_bg'],
            'SBG': THEME['sbox_bg'], 'STT': THEME['sbox_title'],
            'STX': THEME['sbox_text'], 'ZBG': THEME['zone_bg'],
            'GREY': THEME['grey'], 'ZEB': THEME['zebra']}


CSS = CSS_TMPL % _css_params()

COVER_CSS_TMPL = """
* { margin:0; padding:0; box-sizing:border-box; }
html,body { width:943px; font-family:'Microsoft YaHei',sans-serif; }
.cover { width:943px; height:1120px; position:relative; overflow:hidden;
  background: linear-gradient(160deg,%(COV1)s 0%%,%(COV2)s 45%%,%(COV3)s 100%%);
  color:#fff; }
.cover::before { content:''; position:absolute; width:860px; height:860px;
  border-radius:50%%;
  background:radial-gradient(circle,%(GLOW1)s 0%%,rgba(255,255,255,0) 62%%);
  top:-250px; right:-270px; }
.cover::after { content:''; position:absolute; width:660px; height:660px;
  border-radius:50%%;
  background:radial-gradient(circle,%(GLOW2)s 0%%,rgba(255,255,255,0) 60%%);
  bottom:-230px; left:-250px; }
.inner { position:absolute; inset:0; padding:84px 64px; display:flex;
  flex-direction:column; z-index:2; }
.issuers { text-align:center; font-size:24px; letter-spacing:3px; opacity:.92; }
.issuers .sep { margin:0 12px; opacity:.6; }
.mid { flex:1; display:flex; flex-direction:column; justify-content:center; }
.kicker { display:inline-block; align-self:flex-start;
  border:2px solid rgba(255,255,255,.65); border-radius:999px;
  padding:8px 22px; font-size:22px; letter-spacing:4px; margin-bottom:34px; }
h1 { text-wrap:balance; font-size:70px; line-height:1.35; font-weight:700; letter-spacing:2px; }
.sub { margin-top:26px; font-size:28px; opacity:.88; letter-spacing:1px; }
.chips { margin-top:50px; display:flex; flex-wrap:wrap; gap:14px; }
.chip { background:rgba(255,255,255,.13); border:1px solid rgba(255,255,255,.28);
  border-radius:12px; padding:14px 20px; font-size:28px;
  white-space:nowrap; }
.chip b { font-size:36px; margin-right:8px; color:%(CHIPT)s; }
.bottom { display:flex; justify-content:space-between; align-items:flex-end;
  font-size:22px; opacity:.85; letter-spacing:2px; }
"""

COVER_CSS = COVER_CSS_TMPL % {
    'COV1': THEME['cover1'], 'COV2': THEME['cover2'], 'COV3': THEME['cover3'],
    'GLOW1': THEME['glow1'], 'GLOW2': THEME['glow2'],
    'CHIPT': THEME['chip_num']}

BASE_JS_TMPL = """
function chart(el, opt, fs) {
  var c = echarts.init(document.getElementById(el), null,
                       {devicePixelRatio: window.__DPR__, renderer: 'svg', animation: false});
  c.on('finished', () => { c.__reportFinished = true; });
  opt.animation = false;
  opt.textStyle = {fontFamily: 'sans-serif', fontSize: (fs || 19)};
  c.setOption(opt);
  (window.__reportCharts ||= []).push(c);
  return c;
}
function wrapChartLabel(text, width, size) {
  const ctx = document.createElement('canvas').getContext('2d');
  ctx.font = size + 'px sans-serif';
  const lines = []; let line = '';
  for (const ch of text) {
    if (line && ctx.measureText(line + ch).width > width) {lines.push(line);line=ch;}
    else line += ch;
  }
  lines.push(line);return lines.join('\\n');
}
var PALETTE = %(PALETTE)s;
"""

BASE_JS = BASE_JS_TMPL % {'PALETTE': json.dumps(THEME['chart_palette'])}


def apply_theme(name):
    """按 --theme 切换配色并重建全部样式模板（版式不动，只换色）"""
    global THEME, CSS, COVER_CSS, BASE_JS
    THEME = load_theme(name)
    CSS = CSS_TMPL % _css_params()
    COVER_CSS = COVER_CSS_TMPL % {
        'COV1': THEME['cover1'], 'COV2': THEME['cover2'],
        'COV3': THEME['cover3'], 'GLOW1': THEME['glow1'],
        'GLOW2': THEME['glow2'], 'CHIPT': THEME['chip_num']}
    BASE_JS = BASE_JS_TMPL % {'PALETTE': json.dumps(THEME['chart_palette'])}
    print('配色主题: %s（%s）' % (name, THEME.get('label', '')))


def smart_wrap(text, max_chars, seps='：，、；｜——·（）()'):
    """按语义断行：优先在分隔符后断行，避免把语义单元硬拆。
    text 超过 max_chars 时，找到 ≤max_chars 的最后一个分隔符位置断行；
    没有分隔符则原样返回（交给 CSS 两端对齐，不强行断）。
    返回带 <br> 的 html。"""
    t = str(text)
    if len(t) <= max_chars:
        return t
    cut, best = -1, -1
    for i, ch in enumerate(t[:max_chars]):
        if ch in seps:
            best = i
    cut = best if best >= int(max_chars * 0.5) else max_chars
    head, rest = t[:cut + 1], t[cut + 1:]
    return head + '<br>' + smart_wrap(rest, max_chars, seps)

# 各图表类型的默认渲染高度（px）
CHART_H = {'heatmap': 600, 'funnel': 560, 'line': 460, 'scatter': 500}


def chart_js(cfg, el, height):
    """按 outline 里的 chart 配置生成 ECharts 代码。数据与样式来自统一图表模块；保留明确的历史类型兼容"""
    modern = modern_chart_js(cfg, el, THEME)
    if modern is not None:
        return modern
    kind = cfg.get('kind', 'hbar')
    data = cfg.get('data', [])
    unit = cfg.get('unit', '')
    js = "var D = %s;\n" % json.dumps(data, ensure_ascii=False)
    if kind == 'scatter':
        unit_x = cfg.get('unit_x', '')
        unit_y = cfg.get('unit_y', '')
        # 规范（chart-gallery）：气泡按方向分色 + 底部图例；仅岗位量最大的气泡保留名称标注
        js += """
var SMAX = Math.max.apply(null, D.map(function(d){return d[3] || 1;}));
var XMAX = Math.max.apply(null, D.map(function(d){return d[1] || 0;}));
chart('%s', {
  legend: {bottom: 0, left: 'center', itemWidth: 18, itemHeight: 18,
    itemGap: 16, textStyle: {fontSize: 18, color: '#374151'}},
  grid: {left: 20, right: 40, top: 40, bottom: 96, containLabel: true},
  xAxis: {type: 'value', name: '%s', nameLocation: 'middle', nameGap: 40,
    nameTextStyle: {fontSize: 18, color: '#6B7280'},
    axisLabel: {fontSize: 17, color: '#9CA3AF',
      formatter: function(v){ return v.toLocaleString(); }},
    splitLine: {lineStyle: {color: '#E5E7EB'}}},
  yAxis: {type: 'value', name: '%s', nameTextStyle: {fontSize: 18, color: '#6B7280'},
    axisLabel: {fontSize: 17, color: '#9CA3AF'},
    splitLine: {lineStyle: {color: '#E5E7EB'}}},
  series: D.map(function(d, i){
    return {name: d[0], type: 'scatter',
      data: [{value: [d[1], d[2]],
        symbolSize: 18 + 34 * Math.sqrt((d[3] || 1) / SMAX),
        label: {show: d[1] === XMAX, position: 'top', fontSize: 17,
          color: '#1F2937', formatter: d[0]}}],
      itemStyle: {color: PALETTE[i %% 7], borderColor: '#fff',
        borderWidth: 2}};})
});
""" % (el, unit_x, unit_y)
    elif kind == 'funnel':
        js += """
var FCOLORS = %s;
chart('%s', {
  series: [{type: 'funnel', sort: 'none', gap: 8,
    left: '4%%', width: '54%%', top: 14, bottom: 14, minSize: '10%%',
    label: {show: true, position: 'right', fontSize: 20, color: '%s',
      formatter: function(p){ return p.name + '  ' + p.value + '%%'; }},
    labelLine: {show: true, length: 14, lineStyle: {color: '#9CA3AF'}},
    data: D.map(function(d, i){ return {name: d[0], value: d[1],
      itemStyle: {color: FCOLORS[i %% FCOLORS.length],
        borderColor: '#fff', borderWidth: 2, borderRadius: 6}};})}]
});
""" % (el, json.dumps(TH('funnel')), TH('text'))
    elif kind == 'line':
        js += """
var LMAX = Math.max.apply(null, D.map(function(d){return d[1]}));
var LMIN = Math.min.apply(null, D.map(function(d){return d[1]}));
chart('%s', {
  grid: {left: 20, right: 30, top: 46, bottom: 14, containLabel: true},
  xAxis: {type: 'category', boundaryGap: false,
    data: D.map(function(d){return d[0]}),
    axisLabel: {fontSize: 17, rotate: 32, color: '#374151',
      formatter: function(v){ return v.replace('20', \"'\"); }},
    axisLine: {lineStyle: {color: '#D1D5DB'}}, axisTick: {show: false}},
  yAxis: {type: 'value',
    axisLabel: {fontSize: 16, color: '#9CA3AF',
      formatter: function(v){ return v >= 1000 ? (v/1000) + 'k' : v; }},
    splitLine: {lineStyle: {color: '#E5E7EB'}}},
  series: [{type: 'line', smooth: true, symbol: 'circle', symbolSize: 10,
    data: D.map(function(d){return d[1]}),
    lineStyle: {width: 4, color: '%s'},
    itemStyle: {color: '%s', borderColor: '#fff', borderWidth: 2},
    areaStyle: {color: {type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
      colorStops: [{offset: 0, color: '%s'},
                   {offset: 1, color: '%s'}]}},
    markPoint: {symbolSize: 58, itemStyle: {color: '%s'},
      label: {fontSize: 16, color: '#fff',
        formatter: function(p){ return p.value.toLocaleString(); }},
      data: [{type: 'max', name: '峰值'}]}}]
});
""" % (el, TH('primary'), TH('primary'), TH('line_grad1'),
       TH('line_grad2'), TH('accent'))
    return js


def render_table(cfg, src_line=''):
    """kind=table：HTML 数据表（斑马纹 + 名次徽章 + 数值列右对齐 + 可选高亮区域）"""
    cols = cfg.get('columns', [])
    rank = cfg.get('rank', False)
    align_num = set(cfg.get('align_num', []))
    hot_col = cfg.get('hot_col', len(cols) - 1)
    hot_cells = {tuple(x) for x in cfg.get('hot_cells', [])}
    head = ''.join('<th>%s</th>' % c for c in cols)
    body = []
    for i, row in enumerate(cfg.get('rows', [])):
        tds = []
        for ci, cell in enumerate(row):
            cls = []
            if (i, ci) in hot_cells:
                cls.append('zone')
            elif ci in align_num:
                cls.append('num')
            elif ci == hot_col:
                cls.append('hot')
            chtml = str(cell)
            if ci == 0 and rank:
                rkc = 'rk r%d' % (i + 1) if i < 3 else 'rk'
                chtml = '<span class="%s">%02d</span>%s' % (rkc, i + 1, chtml)
            tds.append('<td class="%s">%s</td>' % (' '.join(cls), chtml))
        body.append('<tr>%s</tr>' % ''.join(tds))
    return ('<div class="card"><div class="cap">%s</div>'
            '<table class="dtable"><thead><tr>%s</tr></thead>'
            '<tbody>%s</tbody></table>%s</div>'
            % (smart_wrap(cfg.get('caption', ''), 33), head, ''.join(body),
               src_line))


def render_bignum(cfg, src_line=''):
    """kind=bignum：极端不均衡构成的大数字卡（本项目可读性策略：替代饼图）"""
    top = cfg.get('top') or {}
    rest = cfg.get('rest') or []
    total = cfg.get('total', 0) or (top.get('count', 0)
                                    + sum(r.get('count', 0) for r in rest))
    pct = top.get('pct', 0)
    rests = ''.join(
        '<div class="it"><div class="v">%s%%</div><div class="l">%s</div></div>'
        % (r.get('pct', 0), r.get('name', '')) for r in rest[:3])
    cap2 = smart_wrap(cfg.get('label', top.get('name', '')), 20)
    return ('<div class="bignum"><div class="big">%s<small>%%</small></div>'
            '<div class="cap2">%s</div>'
            '<div class="minibar"><i style="width:%s%%"></i></div>'
            '<div class="rest">%s</div>%s</div>'
            % (pct, cap2, pct, rests, src_line))


def chart_div(cfg, width, height):
    return ('<div id="%s" style="width:%dpx;height:%dpx"></div>'
            % (cfg['_el'], width, height))


def assign_els(screen):
    """给图表配置分配元素 id，并注入 _el"""
    for ck, el in (('chart', 'c1'), ('chart2', 'c2'), ('chartA', 'a1'),
                   ('chartB', 'b1')):
        if screen.get(ck):
            screen[ck]['_el'] = el
    return screen


def render_screen(s, idx, total, org, scale, meta=None):
    """生成页面 HTML，内容高度在浏览器完成布局后测量。"""
    src_line = ''
    if meta:
        src_line = ('<div class="src">数据来源：%s｜全报告 %s 条岗位记录</div>'
                    % (meta.get('data_source', '优才知路').replace('的数据库', ''),
                       format(meta.get('sample_n'), ',') if isinstance(meta.get('sample_n'), int) else '—'))
    if s['type'] == 'cover':
        date_cn = s.get('date') or ''
        html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>%(css)s</style></head><body>
<div class="cover"><div class="inner">
  <div class="issuers">%(issuer)s<span class="sep">·</span>%(co)s</div>
  <div class="mid">
    <div class="kicker">%(series)s</div>
    <h1>%(title)s</h1>
    <div class="sub">—— %(sub)s</div>
    <div class="chips">%(chips)s</div>
  </div>
  <div class="bottom"><span>%(org)s</span><span>%(date)s</span></div>
</div></div></body></html>""" % {
            'css': COVER_CSS,
            'issuer': s['issuer'], 'co': s['co_issuer'],
            'series': s['series'], 'title': html_module.escape(s['title']).replace('人才需求观察报告', '<br>人才需求观察报告'), 'sub': s['subtitle'],
            'chips': ''.join('<div class="chip"><b>%s</b>%s</div>'
                             % (c['value'], c['label']) for c in s['chips']),
            'org': org, 'date': date_cn,
        }
        return html

    if s['type'] == 'summary':
        dots = ''.join('<div class="d%s"></div>' % (' on' if i == idx else '')
                       for i in range(total))
        lead = ''.join(
            '<p style="font-size:26px;line-height:1.85;color:#1F2937;'
            'text-align:justify;margin-bottom:26px">%s</p>' % p
            for p in (s.get('lead') or []))
        tail = ''.join(
            '<p style="font-size:25px;line-height:1.8;color:#374151;'
            'text-align:justify;margin-top:8px">%s</p>' % p
            for p in (s.get('tail') or []))
        cards = ''.join(
            '<div class="sumcard"><div class="no2">%s</div><div class="bd">'
            '<div class="jt">%s</div><div class="ds">%s</div></div></div>'
            % (c.get('no', ''), c.get('title', ''), c.get('desc', ''))
            for c in s.get('cards', []))
        html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>%(css)s</style></head>
<body><div class="page">
<div class="edgebar"></div>
<div class="chapter"><div class="tt" style="font-size:44px">%(title)s</div></div>
<div class="hr"></div>
%(lead)s
<div class="corebar">核心结论</div>
%(cards)s
%(tail)s
<div class="footer"><div class="org">%(org)s</div><div class="dots">%(dots)s</div></div>
</div></body></html>""" % {'css': CSS,
                             'title': s.get('title', '摘要'), 'lead': lead,
                             'cards': cards, 'tail': tail,
                             'org': org, 'dots': dots}
        return html

    if s['type'] == 'backcover':
        html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>%(css)s</style></head>
<body><div class="cover" style="height:1000px"><div class="inner">
  <div class="mid" style="justify-content:center;text-align:center">
    <div style="font-size:26px;letter-spacing:6px;opacity:.85">%(series)s</div>
    <div style="font-size:40px;font-weight:700;margin-top:26px">%(org)s</div>
    <div style="font-size:24px;opacity:.88;line-height:1.8;margin-top:34px;"
      >%(slogan)s</div>
    <div style="margin-top:56px;font-size:23px;opacity:.85">%(c1)s<br>%(c2)s</div>
  </div>
</div></div></body></html>""" % {'css': COVER_CSS, 'series': s.get('series', ''),
                                   'org': s.get('org', org),
                                   'slogan': s.get('slogan', ''),
                                   'c1': s.get('contact_name', ''),
                                   'c2': s.get('contact_phone', '')}
        return html

    # 内容屏骨架
    s = assign_els(s)

    def cap(c):
        t = ('%s｜%s' % (c['_no'], c['caption'])) if c.get('_no') else c['caption']
        return smart_wrap(t, 33)   # 图注 21px，卡片内宽约 760px → 33字/行，按语义断

    paras = ''.join('<p>%s</p>' % p for p in s.get('paragraphs', []))
    stats = ''
    if s.get('stats'):
        stats = '<div class="stats">%s</div>' % ''.join(
            '<div class="stat%s"><div class="v%s">%s</div><div class="l">%s</div></div>'
            % (' hot' if st.get('hot') else '',
               ' name' if len(str(st['value'])) > 6 else '',
               st['value'], smart_wrap(st['label'], 10)) for st in s['stats'])
    kpis = ''
    if s.get('kpis'):
        kpis = ('<div class="stats" style="margin-bottom:22px">%s</div>'
                % ''.join(
                    '<div class="stat"><div class="v">%s</div><div class="l">%s'
                    '</div></div>' % (k['value'], smart_wrap(k['label'], 10))
                    for k in s['kpis']))
    note = ''
    if s.get('note'):
        note = ('<div style="background:%s;border-radius:14px;'
                'padding:22px 24px;margin-bottom:22px">'
                '<div style="font-size:23px;font-weight:700;color:%s;'
                'margin-bottom:8px">口径说明</div>'
                '<div style="font-size:21px;line-height:1.7;color:%s;'
                'text-align:justify;overflow-wrap:anywhere">%s</div></div>'
                % (TH('sbox_bg'), TH('sbox_title'), TH('sbox_text'),
                   s['note']))

    js_parts = [BASE_JS.replace('window.__DPR__', str(scale))]
    body_parts = []

    # 图表区（按类型组合）
    if s['type'] == 'kpi':
        body_parts.append(kpis)
        body_parts.append('<div class="paras">%s</div>' % paras)
        body_parts.append(note)
    elif s['type'] == 'chart':
        # 先给事实，再给图组与解释；总结框始终在最后。
        paras_html = []
        for paragraph in s.get('paragraphs', []):
            if s.get('executive_structure')=='summary-integrated-points':
                if paragraph.startswith('摘要｜'):
                    paras_html.append('<p style="font-size:30px;line-height:1.8;background:#F5F7FB;padding:24px;border-radius:12px">'+html_module.escape(paragraph[3:])+'</p>')
                else:
                    heading,mark,body=paragraph.partition('。')
                    paras_html.append('<p style="font-size:31px;line-height:1.85;margin:26px 0"><strong style="color:'+TH('primary')+'">'+html_module.escape(heading)+'。</strong>'+html_module.escape(body)+'</p>')
                continue
            if s.get('executive_structure') and paragraph.startswith('结论') and '｜' in paragraph:
                number,title=paragraph.split('｜',1)
                paras_html.append('<h3 style="font-size:33px;line-height:1.55;color:%s;margin:30px 0 14px"><span style="color:%s">%s</span>｜%s</h3>'%(TH('primary'),TH('accent'),number,title))
                continue
            label, _, body = paragraph.partition('：')
            if s.get('analysis_key') == 'recommendations' or label in ('综合分析', '结构解读与分析推断','总体判断','分析','决策启示'):
                label = '解读' if label == '结构解读与分析推断' else label
                paras_html.append(f'<p><span class="label">{label}</span>{body}</p>')
            else:
                paras_html.append(f'<p>{paragraph}</p>')
        singles = [k for k in ('chart', 'chart2', 'chartA', 'chartB')
                   if s.get(k)]
        first_paras = paras_html[:1] if singles else paras_html
        rest_paras = paras_html[1:] if singles else []
        body_parts.append('<div class="paras">%s</div>' % ''.join(first_paras))
        body_parts.append(stats)
        if s.get('chart'):
            c1 = s['chart']
            if c1.get('kind') == 'table':
                c1 = dict(c1, caption=cap(c1))
                body_parts.append(render_table(c1, src_line))
            elif c1.get('kind') == 'bignum':
                body_parts.append(render_bignum(c1, src_line))
            else:
                h1 = chart_height(c1)
                js_parts.append(chart_js(c1, 'c1', h1))
                body_parts.append('<div class="card"><div class="cap">%s</div>%s%s</div>'
                                  % (cap(c1),
                                     chart_div(c1, CONTENT_W - 48, h1), src_line))
        if s.get('chart2'):
            c2=s['chart2'];h2=chart_height(c2)
            if c2.get('kind')=='table':body_parts.append(render_table(dict(c2,caption=cap(c2)),src_line))
            elif c2.get('kind')=='bignum':body_parts.append(render_bignum(c2,src_line))
            else:
                js_parts.append(chart_js(c2,'c2',h2))
                body_parts.append('<div class="card"><div class="cap">%s</div>%s%s</div>'
                    % (cap(c2),chart_div(c2,CONTENT_W-48,h2),src_line))
        if rest_paras:
            body_parts.append('<div class="paras">%s</div>' % ''.join(rest_paras))
    elif s['type'] == 'duo':
        body_parts.append('<div class="paras">%s</div>' % paras)
        duo = []
        if s.get('chartA'):
            ca = s['chartA']
            if ca.get('kind') == 'bignum':
                duo.append('<div style="flex:1">%s</div>'
                           % render_bignum(ca, src_line))
            else:
                js_parts.append(chart_js(ca, 'a1', 330))
                duo.append('<div class="card" style="flex:1"><div class="cap">%s</div>'
                           '%s</div>' % (cap(ca), chart_div(ca, CONTENT_W - 48, chart_height(ca))))
        if s.get('chartB'):
            js_parts.append(chart_js(s['chartB'], 'b1', 330))
            duo.append('<div class="card" style="flex:1.55"><div class="cap">%s'
                       '</div>%s%s</div>' % (cap(s['chartB']),
                                             chart_div(s['chartB'], CONTENT_W - 48, chart_height(s['chartB'])),
                                             src_line))
        body_parts.append('<div style="display:block;margin-bottom:4px">%s'
                          '</div>' % ''.join(duo))
    elif s['type'] == 'notes':
        blocks = ''.join(
            '<div style="margin-bottom:26px"><div style="font-size:32px;'
            'font-weight:700;color:%s;margin-bottom:10px;padding-left:14px;'
            'border-left:7px solid %s">%s</div><div style="font-size:32px;'
            'line-height:1.75;color:#4B5563;text-align:left;overflow-wrap:anywhere">%s</div></div>'
            % (TH('primary'), TH('accent'), t, c)
            for t, c in s.get('blocks', []))
        contact = ('<div style="background:linear-gradient(135deg,%s,'
                   '%s);border-radius:14px;padding:28px 30px;color:#fff;'
                   'margin-top:6px"><div style="font-size:26px;font-weight:700;'
                   'margin-bottom:10px">交流合作</div><div style="font-size:23px;'
                   'line-height:1.7;opacity:.92">%s<br>%s</div></div>'
                   % (TH('cover2'), TH('cover3'),
                      s.get('contact_name', ''), s.get('contact_phone', '')))
        body_parts.append(blocks)
        if s.get('contact_name') or s.get('contact_phone'):
            body_parts.append(contact)
    else:
        body_parts.append('<div class="paras">%s</div>' % paras)

    # V5：图后固定"产业观察"洞察框 / 金句框（对标参考公众号的总结框）
    if s.get('insight'):
        body_parts.append('<div class="insight"><div class="tag">产业观察</div>'
                          '<div class="txt">%s</div></div>' % s['insight'])
    # 章末灵活小标题总结框（橙系）
    if s.get('summary'):
        body_parts.append('<div class="sbox"><div class="st">%s</div>'
                          '<div class="sx">%s</div></div>'
                          % (s['summary'].get('title', ''),
                             s['summary'].get('text', '')))
    if s.get('quote'):
        body_parts.append('<div class="quote">%s</div>'
                          % smart_wrap(s['quote'], 26))

    dots = ''.join('<div class="d%s"></div>' % (' on' if i == idx else '')
                   for i in range(total))
    chapter = ''
    if s.get('section'):
        chapter = ('<div class="kicker2">%s</div><div class="tt2">%s</div>'
                   % (s['section'], s.get('title', '')))
    elif s.get('no'):
        chapter = ('<div class="chapter"><div class="no">%s</div>'
                   '<div class="tt">%s</div></div>' % (s['no'], s['title']))
    elif s.get('title'):
        chapter = '<div class="chapter"><div class="tt">%s</div></div>' % s['title']

    html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>%(css)s</style></head>
<body><div class="page">
<div class="edgebar"></div>
%(chapter)s
%(subtitle)s
<div class="hr"></div>
%(body)s
<div class="footer"><div class="org">%(org)s</div><div class="dots">%(dots)s</div></div>
</div>
<script src="%(ech)s"></script>
<script>%(js)s</script>
</body></html>""" % {
        'css': CSS, 'chapter': chapter,
        'subtitle': ('<div class="subtitle">%s</div>' % s['subtitle'])
                    if s.get('subtitle') else '',
        'body': '\n'.join(body_parts), 'org': org, 'dots': dots,
        'ech': ECHARTS_URL, 'js': '\n'.join(js_parts),
    }
    return html


def shoot(html_path, png_path, w, scale):
    if not EDGE:
        raise RuntimeError('未找到 Edge / Chrome / Chromium；请设置 WECHAT_REPORT_BROWSER')
    uri = Path(html_path).resolve().as_uri()
    probe = subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--hide-scrollbars',
        f'--force-device-scale-factor={scale}', f'--window-size={w},1000',
        '--virtual-time-budget=6000', '--dump-dom', uri],
        capture_output=True, text=True, timeout=60, check=True)
    size = re.search(r'data-report-layout="(\d+),(\d+)"', probe.stdout)
    if not size:
        raise RuntimeError('无法测量报告内容或浏览器视口')
    h, viewport = map(int, size.groups())
    evidence = re.search(r'data-report-audit="([^"]+)"', probe.stdout)
    if not evidence:
        raise RuntimeError('缺少浏览器布局质检证据')
    audit = json.loads(html_module.unescape(evidence.group(1)))
    if audit['errors']:
        raise RuntimeError('布局检查失败：'+str(audit['errors']))
    overhead = max(0, 1000 - viewport)
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--hide-scrollbars',
           '--force-device-scale-factor=%d' % scale,
           '--window-size=%d,%d' % (w, h+overhead),
           '--default-background-color=FFFFFFFF',
           '--virtual-time-budget=6000',
           '--screenshot=%s' % png_path,
           Path(html_path).resolve().as_uri()]
    subprocess.run(cmd, capture_output=True, timeout=120, check=True)
    if not os.path.exists(png_path):
        raise RuntimeError('截图失败: %s' % png_path)
    # Chrome's CLI window includes decorations; keep exactly the CSS content size.
    with Image.open(png_path) as image:
        if image.width != w*scale or image.height < h*scale:
            raise RuntimeError('截图尺寸与预期不一致')
        cropped = image.crop((0, 0, w*scale, h*scale))
    cropped.save(png_path)
    return h, audit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--outline',
                    default=os.path.join(BASE, 'output', 'outline',
                                         'report_outline.json'))
    ap.add_argument('--outdir', default=os.path.join(BASE, 'output', 'report'))
    ap.add_argument('--scale', type=int, default=1,
                    help='1=与原文一致(943px宽)；2=高清(1886px宽，公众号里字号'
                         '会显得只有原文一半)')
    ap.add_argument('--no-stitch', action='store_true')
    ap.add_argument('--renderer',choices=['auto','persistent','cli'],default='auto',
                    help='auto优先复用一个浏览器，cli保留逐页命令行兼容方式')
    ap.add_argument('--data', default=os.path.join(BASE, 'report_data.json'))
    ap.add_argument('--demo', action='store_true')
    ap.add_argument('--theme', default='zhengwu',
                    help='配色主题（assets/themes.json 的键名）：'
                         'zhengwu政务藏青/deep_purple深空紫/bamboo青竹绿/'
                         'crimson绛红典雅/ink_gold墨金年鉴/warm_sand暖沙杂志')
    args = ap.parse_args()

    if args.theme != 'zhengwu':
        apply_theme(args.theme)

    with open(args.outline, 'r', encoding='utf-8') as f:
        ol = json.load(f)
    data, binding = load_data(args.data, args.demo)
    if binding:
        verify_outline(data, binding, ol)

    screens = ol['screens']
    total = len(screens)
    # 图表自动编号（Quarto 式交叉引用：编号由渲染器统一分配）
    fign = tabn = 0
    for s in screens:
        for ck in ('chart', 'chart2', 'chartA', 'chartB'):
            c = s.get(ck)
            if not c:
                continue
            if c.get('kind') == 'table':
                tabn += 1
                c['_no'] = '表%d' % tabn
            else:
                fign += 1
                c['_no'] = '图%d' % fign
    pages_dir = os.path.join(args.outdir, 'pages')
    os.makedirs(pages_dir, exist_ok=True)

    chapter_keys = {item['key'] for item in ol['analysis']['sections']} if binding else set()
    manifest = []
    backend='persistent' if args.renderer=='persistent' or (args.renderer=='auto' and find_spec('playwright')) else 'cli'
    started=perf_counter()
    if backend=='persistent':
        from browser_renderer import ReportBrowser
        renderer=ReportBrowser(EDGE,PAGE_W,args.scale)
    else:renderer=nullcontext(None)
    with renderer as browser:
        for idx, s in enumerate(screens):
            if s['type'] == 'cover' and not s.get('date'):
                s['date'] = ol.get('generated_at', '')[:7].replace('-', '年') + '月'
            # Bound reports collect all chapter actions on the recommendations page.
            if s.get('analysis_key') in chapter_keys:
                s = dict(s, paragraphs=[p for p in s['paragraphs'] if not p.startswith('行动建议：')])
            html = render_screen(s, idx, total, ol.get('org', ''), args.scale,
                                    meta=ol.get('meta'))
            hp = os.path.join(pages_dir, 'page_%02d.html' % idx)
            measure = MEASURE_SCRIPT
            with open(hp, 'w', encoding='utf-8') as f:
                f.write(html.replace('</body>', measure + '</body>'))
            png = os.path.join(pages_dir, 'page_%02d.png' % idx)
            h, audit = browser.capture(hp,png) if browser else shoot(hp, png, PAGE_W, args.scale)
            manifest.append({'index': idx, 'name': s.get('title', 'screen'),
                             'file': 'pages/page_%02d.png' % idx,
                             'height': h, 'width': PAGE_W, 'scale': args.scale,
                             'sha256': digest(Path(png).read_bytes()), 'layout': audit})
            print('[%d/%d] %s%s -> %s' % (idx + 1, total, s.get('no', ''),
                                          s.get('title', ''), png))

    if not args.no_stitch:
        imgs = [Image.open(os.path.join(args.outdir, m['file'])) for m in manifest]
        W = imgs[0].width
        H = sum(im.height for im in imgs)
        canvas = Image.new('RGB', (W, H), '#ffffff')
        y = 0
        for im in imgs:
            canvas.paste(im, (0, y))
            y += im.height
        canvas.save(os.path.join(args.outdir, 'report_full.png'))
        canvas.save(os.path.join(args.outdir, 'report_full.jpg'), quality=88)
        print('长图: %s (%dx%d)' % (os.path.join(args.outdir, 'report_full.jpg'),
                                    W, H))

    with open(os.path.join(args.outdir, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump({'schema': 'wechat-render/2', 'theme': args.theme, 'pages': manifest, 'title': ol['title'],
                   'renderer':backend,'render_seconds':round(perf_counter()-started,3),
                   'outline_sha256': digest(Path(args.outline).read_bytes()),
                   'source_content_hash': ol.get('source_content_hash'),
                   'generated_at': ol.get('generated_at')}, f,
                  ensure_ascii=False, indent=2)
    print('完成：%s' % args.outdir)


if __name__ == '__main__':
    main()
