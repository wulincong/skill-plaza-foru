<script setup lang="ts">
import { computed } from 'vue'
import Icon from './Icon.vue'
import MarkdownView from './MarkdownView.vue'
import ReportChart from './ReportChart.vue'
import type { ReportChart as ReportChartData } from '../data/runsMock'

const props = defineProps<{
  text: string
  charts?: ReportChartData[]
  streaming?: boolean
  reportUrl?: string
  htmlMode?: boolean
  artifactName?: string
}>()

const artifactName = computed(() => props.artifactName || '报告')
const isHtml = computed(() => props.htmlMode || /^\s*(?:<!doctype\s+html|<html[\s>])/i.test(props.text))
const isRawHtml = computed(() => /^\s*(?:<!doctype\s+html|<html[\s>])/i.test(props.text))
const htmlStatus = computed(() => {
  if (props.reportUrl) return '报告已生成。'
  if (props.streaming) return '就业指导报告正在生成，完成后可查看。'
  /* 新协议的失败原因由服务端放在 done.content；旧记录的普通文本也应保留。 */
  if (props.text && !isRawHtml.value) return props.text
  return '报告未生成或没有保存查看链接，请重新运行。'
})
</script>

<template>
  <p v-if="isHtml" class="report-ready">
    {{ htmlStatus }}
    <template v-if="reportUrl">
      <a class="report-open" :href="reportUrl" target="_blank" rel="noopener">查看{{ artifactName }}</a>
      <a class="report-download" :href="`${reportUrl}/download`" download>
        <Icon name="download" :size="13" />下载{{ artifactName }}
      </a>
    </template>
  </p>
  <MarkdownView v-else :text="text" :streaming="streaming" />
  <!-- 报告链接与正文解耦：非 html 模式的技能运行只要带回 reportUrl 也内联可开可下载 -->
  <p v-if="!isHtml && reportUrl" class="report-ready">
    <a class="report-open" :href="reportUrl" target="_blank" rel="noopener">查看{{ artifactName }}</a>
    <a class="report-download" :href="`${reportUrl}/download`" download>
      <Icon name="download" :size="13" />下载{{ artifactName }}
    </a>
  </p>
  <div v-if="!isHtml && charts?.length" class="use-report-charts">
    <ReportChart v-for="chart in charts" :key="chart.id" :chart="chart" />
  </div>
</template>
