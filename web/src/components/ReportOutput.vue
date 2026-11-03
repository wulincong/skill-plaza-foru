<script setup lang="ts">
import { computed, ref } from 'vue'
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
  webLinks?: Array<{ name: string; url: string }>
  downloads?: Array<{ name: string; url: string }>
}>()

const hasDelivery = computed(() => Boolean(props.webLinks?.length || props.downloads?.length))
const copyStatus = ref('')
async function copyLink(url: string) {
  const absolute = new URL(url, window.location.href).href
  try {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(absolute)
    else {
      const input = document.createElement('textarea')
      input.value = absolute
      input.style.position = 'fixed'
      input.style.opacity = '0'
      document.body.appendChild(input)
      input.select()
      const ok = document.execCommand('copy')
      input.remove()
      if (!ok) throw new Error('copy')
    }
    copyStatus.value = '链接已复制'
  } catch { copyStatus.value = '复制失败，请从“打开网页”复制链接地址' }
}
const artifactName = computed(() => props.artifactName || '报告')
const isHtml = computed(() => props.htmlMode || /^\s*(?:<!doctype\s+html|<html[\s>])/i.test(props.text))
const isRawHtml = computed(() => /^\s*(?:<!doctype\s+html|<html[\s>])/i.test(props.text))
const htmlStatus = computed(() => {
  if (props.text && !isRawHtml.value && !props.streaming) return props.text
  if (props.reportUrl || hasDelivery.value) return '报告已生成。'
  if (props.streaming) return '报告正在生成，完成后可查看。'
  /* 新协议的失败原因由服务端放在 done.content；旧记录的普通文本也应保留。 */
  if (props.text && !isRawHtml.value) return props.text
  return '报告未生成或没有保存查看链接，请重新运行。'
})
</script>

<template>
  <p v-if="isHtml" class="report-ready">
    {{ htmlStatus }}
    <template v-if="reportUrl && !hasDelivery">
      <a class="report-open" :href="reportUrl" target="_blank" rel="noopener">查看{{ artifactName }}</a>
      <a class="report-download" :href="`${reportUrl}/download`" download>
        <Icon name="download" :size="13" />下载{{ artifactName }}
      </a>
    </template>
  </p>
  <MarkdownView v-else :text="text" :streaming="streaming" />
  <!-- 报告链接与正文解耦：非 html 模式的技能运行只要带回 reportUrl 也内联可开可下载 -->
  <p v-if="!isHtml && reportUrl && !hasDelivery" class="report-ready">
    <a class="report-open" :href="reportUrl" target="_blank" rel="noopener">查看{{ artifactName }}</a>
    <a class="report-download" :href="`${reportUrl}/download`" download>
      <Icon name="download" :size="13" />下载{{ artifactName }}
    </a>
  </p>
  <div v-if="hasDelivery" class="delivery-links">
    <p v-for="link in webLinks" :key="link.url" class="delivery-row">
      <span>{{ link.name }}</span>
      <a class="report-open" :href="link.url" target="_blank" rel="noopener noreferrer">打开网页</a>
      <button type="button" class="delivery-copy" @click="copyLink(link.url)">复制链接</button>
    </p>
    <p v-for="link in downloads" :key="link.url" class="delivery-row">
      <span>{{ link.name }}</span>
      <a class="report-download" :href="link.url" download><Icon name="download" :size="13" />下载</a>
    </p>
    <p v-if="copyStatus" class="delivery-copy-status" role="status">{{ copyStatus }}</p>
  </div>
  <div v-if="!isHtml && charts?.length" class="use-report-charts">
    <ReportChart v-for="chart in charts" :key="chart.id" :chart="chart" />
  </div>
</template>

<style scoped>
.delivery-links { margin: 12px 0; }
.delivery-row { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin: 8px 0; }
.delivery-copy { padding: 0; border: 0; background: none; color: var(--sk-text-2, #64748b); font: inherit; font-size: 13px; cursor: pointer; }
.delivery-copy:hover { text-decoration: underline; }
.delivery-copy-status { font-size: 12px; color: var(--sk-text-2, #64748b); }
</style>
