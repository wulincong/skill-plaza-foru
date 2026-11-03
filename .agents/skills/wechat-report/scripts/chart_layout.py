"""Deterministic mobile report charts and browser layout evidence. No model calls."""
import json
import math

KINDS = {'hbar', 'vbar', 'pie', 'donut', 'heatmap', 'range_dot', 'table', 'bignum', 'scatter', 'line', 'funnel'}


def chart_height(cfg):
    kind = cfg.get('kind')
    if kind in ('hbar', 'range_dot'):
        return max(260, 76 * len(cfg.get('data', [])) + 70)
    if kind == 'heatmap':
        return max(420, 84 * len(cfg.get('rows', [])) + 220)
    return 540


def chart_js(cfg, el, theme):
    """Return None only for legacy kinds that still have an explicit renderer."""
    kind = cfg.get('kind')
    if kind not in KINDS:
        raise ValueError('不支持的图表类型：'+str(kind))
    if kind not in {'hbar', 'vbar', 'pie', 'donut', 'heatmap', 'range_dot'}:
        return None
    data = cfg.get('data', [])
    primary, accent, text, sub = (theme[k] for k in ('primary', 'accent', 'text', 'sub'))
    opt = {'animation': False, 'textStyle': {'fontSize': 28, 'color': text}, 'tooltip': {'show': False}}
    axis = {'axisLine': {'show': False}, 'axisTick': {'show': False},
            'axisLabel': {'fontSize': 28, 'color': text, 'interval': 0}}
    if kind in ('hbar', 'vbar'):
        pct = cfg.get('pct_label', False)
        if pct and any(len(d) < 3 for d in data):
            raise ValueError('比例标签须绑定明确的百分比值')
        values = [d[2] if pct else d[1] for d in data]
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in values):
            raise ValueError('柱图数值须为有限非负数')
        suffix = '%' if pct else cfg.get('unit', '条')
        series = {'type': 'bar', 'barMaxWidth': 30, 'data': [
            {'value': v, 'itemStyle': {'color': accent if i < cfg.get('top', 1) else primary,
                                      'borderRadius': [0, 6, 6, 0]},
             'label': {'show': True, 'position': 'right' if kind == 'hbar' else 'top',
                       'fontSize': 28, 'color': text,
                       'formatter': format(v, ',')+suffix}} for i, v in enumerate(values)]}
        category = dict(axis, type='category', data=[d[0] for d in data])
        if kind == 'hbar':
            category['inverse'] = True
            category['axisLabel'] = dict(category['axisLabel'], width=220, overflow='break', lineHeight=34)
            opt.update(grid={'left': 235, 'right': 145, 'top': 16, 'bottom': 20},
                       xAxis={'type': 'value', 'show': False}, yAxis=category, series=[series])
        else:
            category['axisLabel'] = dict(category['axisLabel'], fontSize=26, lineHeight=32)
            opt.update(grid={'left': 25, 'right': 25, 'top': 55, 'bottom': 75, 'containLabel': True},
                       xAxis=category, yAxis={'type': 'value', 'show': False}, series=[series])
    elif kind in ('pie', 'donut'):
        total = sum(d[1] for d in data)
        if total <= 0:
            raise ValueError('构成图没有正数样本')
        opt.update(legend={'orient': 'vertical', 'right': 0, 'top': 'middle',
                           'itemWidth': 24, 'itemHeight': 24, 'itemGap': 24,
                           'textStyle': {'fontSize': 28, 'color': text}},
                   series=[{'type': 'pie', 'radius': ['40%', '70%'], 'center': ['28%', '50%'],
                            'label': {'show': False}, 'data': [
                                {'name': d[0]+'  '+str(round(d[1]/total*100, 1))+'%', 'value': d[1],
                                 'itemStyle': {'color': theme['chart_palette'][i % 7]}}
                                for i, d in enumerate(data)]}])
    elif kind == 'heatmap':
        cells = cfg.get('cells', [])
        if not cells or not cfg.get('rows') or not cfg.get('cols'):
            raise ValueError('热力矩阵不能为空')
        vals = [c[2] for c in cells]
        opt.update(grid={'left': 205, 'right': 20, 'top': 20, 'bottom': 175},
                   xAxis=dict(axis, type='category', data=cfg['cols']),
                   yAxis=dict(axis, type='category', inverse=True, data=cfg['rows']),
                   visualMap={'min': 0, 'max': max(1, max(vals)), 'orient': 'horizontal',
                              'left': 'center', 'bottom': 0, 'itemWidth': 22, 'itemHeight': 220,
                              'textStyle': {'fontSize': 24}, 'inRange': {'color': theme['heat']}, 'text': [str(round(max(vals),1)), '0']},
                   series=[{'type': 'heatmap', 'data': [[c[1], c[0], c[2]] for c in cells],
                            'label': {'show': True, 'fontSize': 26, 'color': '#111827',
                                      'textBorderColor': '#FFFFFF', 'textBorderWidth': 3},
                            'itemStyle': {'borderColor': '#FFFFFF', 'borderWidth': 3}}])
        opt['xAxis']['axisLabel'] = dict(opt['xAxis']['axisLabel'], fontSize=25, lineHeight=30)
        opt['yAxis']['axisLabel'] = dict(opt['yAxis']['axisLabel'], width=185, overflow='break', fontSize=27, lineHeight=33)
        # Wrap labels without truncating the actual category keys used by the series.
    elif kind == 'range_dot':
        # data = [name, validN, p25, median, p75]; unavailable/small groups stay excluded upstream.
        opt.update(grid={'left': 235, 'right': 60, 'top': 24, 'bottom': 65},
                   xAxis=dict(axis, type='value', min=0, name='K/月', nameGap=15,
                              splitLine={'lineStyle': {'color': '#E5E7EB'}}),
                   yAxis=dict(axis, type='category', inverse=True, data=[d[0] for d in data]))
        opt['yAxis']['axisLabel'] = dict(opt['yAxis']['axisLabel'], width=210, overflow='break', lineHeight=34)
        # Invisible stacked base + visible IQR; an independent point marks the median.
        opt['series'] = [
            {'type': 'bar', 'stack': 'iqr', 'silent': True, 'itemStyle': {'color': 'transparent'}, 'data': [d[2] for d in data]},
            {'type': 'bar', 'stack': 'iqr', 'barWidth': 16, 'itemStyle': {'color': primary}, 'data': [d[4]-d[2] for d in data]},
            {'type': 'scatter', 'symbolSize': 20, 'itemStyle': {'color': accent},
             'data': [[d[3], i] for i, d in enumerate(data)]}]
    raw = json.dumps(opt, ensure_ascii=False).replace('</', '<\\/')
    code = '(() => {const opt = '+raw+';'
    if kind == 'heatmap':
        code += "opt.xAxis.axisLabel.formatter = v => wrapChartLabel(v, (document.getElementById("+json.dumps(el)+").clientWidth-225)/opt.xAxis.data.length-8, 25);"
        code += "opt.series[0].label.formatter = p => Number(p.data[2].toFixed(1)).toString();"
    return code+f"chart({json.dumps(el)}, opt);"+'})();\n'


MEASURE_SCRIPT = r"""<script>
addEventListener('load', async () => {
  await document.fonts.ready;
  const page = document.querySelector('.page, .cover');
  const box = page.getBoundingClientRect();
  const errors = [];
  for (const node of page.querySelectorAll('p,th,td,.tt,h1,.src,.sbox,.footer')) {
    const r = node.getBoundingClientRect();
    if (r.left < -1 || r.right > box.right + 1 || r.bottom > box.bottom + 1 ||
        node.scrollWidth > node.clientWidth + 2) errors.push('overflow:'+node.className);
  }
  const charts = (window.__reportCharts || []).map(c => {
    const el = c.getDom(), r = el.getBoundingClientRect();
    const svg = el.querySelector('svg');
    const shapes = svg ? svg.querySelectorAll('path,rect,circle').length : 0;
    if (!svg || shapes < 2) errors.push('chart-not-ready:'+el.id);
    const texts = [...el.querySelectorAll('svg text')].map(t => ({text:t.textContent, box:t.getBoundingClientRect()}));
    for (let i=0;i<texts.length;i++) for (let j=i+1;j<texts.length;j++) {
      const a=texts[i].box,b=texts[j].box;
      if (Math.min(a.right,b.right)-Math.max(a.left,b.left)>2 &&
          Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>2)
        errors.push('chart-label-overlap:'+el.id+':'+texts[i].text+'/'+texts[j].text);
    }
    for (const t of el.querySelectorAll('svg text')) {
      const b = t.getBoundingClientRect();
      if (b.left < -1 || b.right > box.right + 1 || b.bottom > box.bottom + 1)
        errors.push('chart-label-clipped:'+el.id);
    }
    return {id:el.id, x:r.x, y:r.y, width:r.width, height:r.height, shapes};
  });
  document.documentElement.dataset.reportLayout =
    [Math.ceil(box.height), innerHeight].join(',');
  document.documentElement.dataset.reportAudit = JSON.stringify({
    schema:'wechat-layout/1', width:box.width, height:Math.ceil(box.height), charts, errors
  });
});
</script>"""
