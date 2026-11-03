<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { ECharts } from 'echarts/core'
import type { ReportChart } from '../data/runs'

const props = defineProps<{ chart: ReportChart }>()
const chartEl = ref<HTMLDivElement | null>(null)
let instance: ECharts | undefined
let resizeObserver: ResizeObserver | undefined
let echartsApi: typeof import('echarts/core') | undefined

async function loadECharts() {
  if (echartsApi) return echartsApi
  const [core, charts, components, renderers] = await Promise.all([
    import('echarts/core'),
    import('echarts/charts'),
    import('echarts/components'),
    import('echarts/renderers'),
  ])
  core.use([
    charts.BarChart,
    charts.LineChart,
    components.GridComponent,
    components.TooltipComponent,
    renderers.CanvasRenderer,
  ])
  echartsApi = core
  return core
}

function rows() {
  return props.chart.data.map((row, index) => ({
    label: String(row.label ?? row.name ?? row.date ?? row.x ?? index + 1),
    value: typeof row.value === 'number' ? row.value : Number(row.value ?? 0),
  })).filter(row => Number.isFinite(row.value))
}

async function render() {
  if (!chartEl.value) return
  const echarts = await loadECharts()
  if (!instance) instance = echarts.init(chartEl.value)
  const data = rows()
  const horizontal = props.chart.type !== 'line'
  const unit = props.chart.unit ?? props.chart.yAxis?.unit ?? ''
  const isMapFallback = props.chart.type === 'map'
  instance.setOption({
    animation: false,
    grid: { top: 12, right: 20, bottom: 32, left: horizontal ? 82 : 48, containLabel: true },
    tooltip: { trigger: 'axis', valueFormatter: (value: unknown) => `${value}${unit}` },
    xAxis: horizontal
      ? { type: 'value', name: unit, axisLabel: { color: '#7a746c' }, splitLine: { lineStyle: { color: '#eee9e2' } } }
      : { type: 'category', data: data.map(row => row.label), axisLabel: { color: '#7a746c' } },
    yAxis: horizontal
      ? { type: 'category', data: data.map(row => row.label), axisLabel: { color: '#49443d' } }
      : { type: 'value', name: unit, axisLabel: { color: '#7a746c' }, splitLine: { lineStyle: { color: '#eee9e2' } } },
    series: [{
      type: props.chart.type === 'line' ? 'line' : 'bar',
      data: data.map(row => row.value),
      barMaxWidth: 24,
      smooth: props.chart.type === 'line',
      itemStyle: { color: '#176b5c', borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] },
      lineStyle: { color: '#176b5c', width: 2 },
      areaStyle: props.chart.type === 'line' ? { color: 'rgba(23, 107, 92, .12)' } : undefined,
    }],
    graphic: isMapFallback ? [{ type: 'text', left: 'center', top: 'middle', style: { text: '地图数据待接入行政区 GeoJSON', fill: '#7a746c' } }] : undefined,
  }, true)
}

onMounted(() => {
  void render()
  if (chartEl.value) {
    resizeObserver = new ResizeObserver(() => instance?.resize())
    resizeObserver.observe(chartEl.value)
  }
})
watch(() => props.chart, () => { void render() }, { deep: true })
onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  instance?.dispose()
})
</script>

<template>
  <figure class="report-chart" :aria-label="chart.altText || chart.title">
    <figcaption>
      <strong>{{ chart.title }}</strong>
      <span v-if="chart.snapshotDate || chart.region">{{ [chart.region, chart.snapshotDate].filter(Boolean).join(' · ') }}</span>
    </figcaption>
    <div ref="chartEl" class="report-chart-canvas" role="img" :aria-label="chart.altText || chart.title"></div>
    <p v-if="chart.insight" class="report-chart-insight">{{ chart.insight }}</p>
    <p v-if="chart.caveat" class="report-chart-caveat">口径：{{ chart.caveat }}</p>
  </figure>
</template>
