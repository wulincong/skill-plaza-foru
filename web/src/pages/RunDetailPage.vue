<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import Icon from '../components/Icon.vue'
import { bySlug, GENERAL_SKILL_NAME } from '../data/skills'
import { OUTCOME_LABEL, type RunDetail, type RunListItem, type RunPart } from '../data/runs'
import { api } from '../admin/state'
import { runFileUrl, runReportUrl } from '../api/runsApi'
import ReportChart from '../components/ReportChart.vue'

/* 运行详情：概要 + 用量条 + 按 trace parts 原始顺序合并的运行时间线。
   数据来自 GET /api/admin/runs/:runId（item = 索引记录，trace = 权威导出）；
   由后台登录会话授权读取。 */

const route = useRoute()
const runId = computed(() => String(route.params.runId ?? ''))

const item = ref<RunListItem | undefined>()
const trace = ref<RunDetail | undefined>()
const live = ref(false)
const loading = ref(true)

function isHtmlReportText(text: string, role?: string): boolean {
  /* 仅把带独立报告文件的 assistant 最终 HTML 隐去；用户任务、工具和思考 trace 保持可见。 */
  if (role !== 'assistant' || !item.value?.files?.html) return false
  return item.value.skill === 'career-guidance' || /^\s*(?:<!doctype\s+html|<html[\s>])/i.test(text)
}

async function load() {
  loading.value = true
  try {
    const result = await api<{item:RunListItem; trace?:RunDetail}>('runs/' + encodeURIComponent(runId.value))
    item.value = result.item
    trace.value = result.trace
    live.value = true
  } catch {
    item.value = undefined
    trace.value = undefined
    live.value = false
  }
  loading.value = false
}
onMounted(load)
watch(runId, load)

const skillName = computed(() => {
  const slug = item.value?.skill ?? 'industry-education-report'
  const known = bySlug.get(slug)?.name
  if (known) return known
  if (slug === 'general') return GENERAL_SKILL_NAME
  return slug === 'unknown' || slug === 'historical' ? '历史会话' : slug
})

interface TimelineItem {
  id: string
  seq: number
  time: string
  role?: string
  part: RunPart
}
/* Pi 的 message parts 已经包含真实发生顺序；seq 使用消息/part 顺序，
   不依赖可能相同的时间戳。 */
const runTimeline = computed<TimelineItem[]>(() => {
  const items: TimelineItem[] = []
  for (const [messageIndex, m] of (trace.value?.messages ?? []).entries()) {
    for (const [partIndex, part] of (m.parts ?? []).entries()) {
      items.push({
        id: `${m.seq ?? messageIndex}-${partIndex}-${part.type === 'tool' ? part.callID : part.type}`,
        seq: messageIndex * 1000 + partIndex,
        time: m.time,
        role: m.role,
        part,
      })
    }
  }
  return items
})

const toolCount = computed(() => runTimeline.value.filter(entry => entry.part.type === 'tool').length)

const openTool = ref<string | null>(null)
function toggleTool(callID: string) {
  openTool.value = openTool.value === callID ? null : callID
}

function partText(part: { type: string; text?: string }): string {
  return part.text ?? ''
}

function roleLabel(role?: string): string {
  return role === 'user' ? '任务' : role === 'assistant' ? 'AI' : role ?? '事件'
}

function fmtDuration(ms?: number): string {
  if (ms === undefined) return '-'
  const s = Math.round(ms / 1000)
  if (s < 90) return `${s}s`
  return `${Math.floor(s / 60)} 分 ${s % 60} 秒`
}
function fmtTokens(n?: number): string {
  if (!n) return '0'
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}
function fmtCost(v?: number): string {
  return v === undefined ? '' : `$${v.toFixed(4)}`
}
function fmtTime(ts?: string): string {
  return ts ? ts.slice(11, 19) : '-'
}
function fmtIO(value: unknown): string {
  if (value === undefined || value === null || value === '') return ''
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 1)
  return text.length > 500 ? text.slice(0, 500) + `\n…（共 ${text.length} 字符）` : text
}

const usagePct = computed(() => {
  const u = item.value?.usage ?? {}
  const input = u.inputTokens ?? 0
  const cache = Math.min(u.cacheReadTokens ?? 0, input)
  const output = u.outputTokens ?? 0
  const total = input + output || 1
  return {
    cache: Math.round((cache / total) * 100),
    input: Math.round(((input - cache) / total) * 100),
    output: Math.round((output / total) * 100),
  }
})

const hasData = computed(() => Boolean(item.value && trace.value))

/* Agent 与环境快照：缺项显示 —；整块缺省（历史记录）则隐藏 */
const envRows = computed(() => {
  const env = item.value?.agentEnv
  if (!env) return []
  const dash = (v?: string) => (v ? v : '—')
  return [
    { label: 'Agent 版本', value: dash(env.agentVersion) },
    { label: '模型', value: dash(env.model) },
    { label: '思考档位', value: dash(env.thinking) },
    { label: 'Node', value: dash(env.node) },
    { label: '系统', value: dash(env.os) },
  ]
})
</script>

<template>
  <section class="page page-run-detail">
    <div class="wrap">
      <RouterLink class="crumb-back" :to="{ name: 'runs' }">
        <Icon name="back" :size="14" /> 返回运行记录
      </RouterLink>

      <p v-if="loading" class="rd-missing">正在读取运行详情…</p>

      <template v-else-if="hasData && item && trace">
        <header class="rd-head">
          <div class="rd-head-copy">
            <p class="use-eyebrow">{{ skillName }} · 执行详情</p>
            <h1>{{ trace.session.title }}</h1>
            <p class="rd-meta">
              会话 <code>{{ trace.session.id }}</code> · 沙箱 <code>{{ trace.session.workspace }}</code> ·
              {{ fmtTime(trace.session.created) }} → {{ fmtTime(trace.session.updated) }}（{{ fmtDuration(item.durationMs) }}）
            </p>
          </div>
          <span class="rd-head-badges">
            <em v-if="item.engine" class="runs-engine" :class="`is-${item.engine}`">{{ item.engine }}</em>
            <span class="runs-outcome rd-outcome" :class="`is-${item.outcome}`">{{ OUTCOME_LABEL[item.outcome] }}</span>
          </span>
        </header>

        <dl v-if="envRows.length" class="rd-env">
          <div v-for="row in envRows" :key="row.label" class="rd-env-item">
            <dt>{{ row.label }}</dt>
            <dd>{{ row.value }}</dd>
          </div>
        </dl>

        <div class="rd-usage">
          <div class="rd-usage-bar" aria-hidden="true">
            <i class="rd-seg-cache" :style="{ width: usagePct.cache + '%' }"></i>
            <i class="rd-seg-input" :style="{ width: usagePct.input + '%' }"></i>
            <i class="rd-seg-output" :style="{ width: usagePct.output + '%' }"></i>
          </div>
          <div class="rd-usage-legend">
            <span><i class="rd-seg-cache"></i>缓存命中 {{ fmtTokens(item.usage?.cacheReadTokens) }}</span>
            <span><i class="rd-seg-input"></i>输入 {{ fmtTokens((item.usage?.inputTokens ?? 0) - (item.usage?.cacheReadTokens ?? 0)) }}</span>
            <span><i class="rd-seg-output"></i>输出 {{ fmtTokens(item.usage?.outputTokens) }}</span>
            <b>合计 {{ fmtTokens(item.usage?.totalTokens) }} tokens</b>
            <b v-if="fmtCost(item.usage?.costUsd)">≈ {{ fmtCost(item.usage?.costUsd) }}</b>
          </div>
        </div>

        <div v-if="item.report && item.skill === 'industry-education-report'" class="rd-parse" :class="{ 'is-fail': !item.report.structurePass }">
          <div class="rd-parse-head">
            <h2>报告解析</h2>
            <em class="runs-outcome" :class="item.report.structurePass ? 'is-success' : 'is-error'">
              {{ item.report.structurePass ? '结构完整' : `缺 ${item.report.missingSections?.length ?? 0} 章` }}
            </em>
          </div>
          <ul class="rd-parse-stats">
            <li><b>{{ item.report.stats?.sections }}</b><span>章节</span></li>
            <li><b>{{ item.report.stats?.facts }}</b><span>事实</span></li>
            <li><b>{{ item.report.stats?.inferences }}</b><span>推断</span></li>
            <li><b>{{ item.report.stats?.recommendations }}</b><span>建议</span></li>
            <li><b>{{ item.report.stats?.gaps }}</b><span>缺口</span></li>
            <li><b>{{ item.report.stats?.sources }}</b><span>来源</span></li>
          </ul>
          <p v-if="item.report.missingSections?.length" class="rd-parse-missing">
            缺失：{{ item.report.missingSections.join('、') }}
          </p>
          <a v-if="item.files?.report" class="rd-parse-dl" :href="runFileUrl(runId, 'report')" target="_blank" rel="noopener">下载解析结果（JSON）</a>
        </div>

        <div v-if="item.report?.meta" class="rd-parse" :class="{ 'is-fail': !item.report.meta.pass }">
          <div class="rd-parse-head">
            <h2>来源校验</h2>
            <em class="runs-outcome" :class="item.report.meta.pass ? 'is-success' : 'is-error'">
              {{ item.report.meta.pass ? '校验通过' : `${item.report.meta.errors.length} 处问题` }}
            </em>
          </div>
          <ul class="rd-parse-stats">
            <li><b>{{ item.report.meta.counts.sources }}</b><span>数据来源</span></li>
            <li><b>{{ item.report.meta.counts.metrics }}</b><span>关键指标</span></li>
            <li><b>{{ item.report.meta.counts.facts }}</b><span>事实</span></li>
            <li><b>{{ item.report.meta.counts.inferences }}</b><span>推断</span></li>
            <li><b>{{ item.report.meta.counts.recommendations }}</b><span>建议</span></li>
            <li><b>{{ item.report.meta.counts.charts }}</b><span>图表</span></li>
            <li><b>{{ item.report.meta.gaps?.length ?? 0 }}</b><span>数据缺口</span></li>
            <li><b>{{ item.report.meta.risks?.length ?? 0 }}</b><span>判断风险</span></li>
          </ul>
          <p v-if="item.report.meta.errors.length" class="rd-parse-missing">
            {{ item.report.meta.errors.slice(0, 5).join('；') }}{{ item.report.meta.errors.length > 5 ? ' 等' : '' }}
          </p>
          <div v-if="item.report.meta.gaps?.length || item.report.meta.risks?.length" class="rd-meta-notes">
            <h3>开发侧缺口与风险</h3>
            <ul>
              <li v-for="gap in item.report.meta.gaps ?? []" :key="String(gap.id)">
                <b>缺口：</b>{{ gap.title }}<span v-if="gap.impact">：{{ gap.impact }}</span>
              </li>
              <li v-for="risk in item.report.meta.risks ?? []" :key="String(risk.id)">
                <b>风险：</b>{{ risk.title }}<span v-if="risk.description">：{{ risk.description }}</span>
              </li>
            </ul>
          </div>
          <div v-if="item.report.meta.marketAnalysis || item.report.meta.resumeReview" class="rd-meta-notes">
            <h3>正式报告摘要</h3>
            <p v-if="item.report.meta.marketAnalysis">
              岗位分析：{{ String(item.report.meta.marketAnalysis.status ?? '未记录') }}
              <span v-if="item.report.meta.marketAnalysis.sampleSize !== undefined"> · 样本 {{ item.report.meta.marketAnalysis.sampleSize }}</span>
              <span v-if="item.report.meta.marketAnalysis.queryId"> · {{ item.report.meta.marketAnalysis.queryId }}</span>
            </p>
            <p v-if="item.report.meta.resumeReview">
              简历审阅：优点 {{ item.report.meta.resumeReview.strengths?.length ?? 0 }} 项 ·
              待补证据 {{ item.report.meta.resumeReview.missingEvidence?.length ?? 0 }} 项 ·
              改写项 {{ item.report.meta.resumeReview.rewriteItems?.length ?? 0 }} 项
            </p>
          </div>
          <div v-if="item.report.meta.charts?.length" class="rd-charts">
            <h3>数据图表</h3>
            <ReportChart v-for="chart in item.report.meta.charts" :key="chart.id" :chart="chart" />
          </div>
          <a v-if="item.files?.report" class="rd-parse-dl" :href="runFileUrl(runId, 'report')" target="_blank" rel="noopener">下载侧车数据（JSON）</a>
        </div>

        <div class="rd-layout">
          <main class="rd-stream">
            <div class="rd-stream-head">
              <h2>运行时间线（{{ runTimeline.length }} 个事件）</h2>
              <span class="rd-stream-count">{{ toolCount }} 次工具调用</span>
            </div>
            <ol class="rd-unified-timeline">
              <li v-for="(entry, i) in runTimeline" :key="entry.id" class="rd-event" :class="`is-${entry.part.type}`">
                <span class="rd-event-marker">{{ i + 1 }}</span>
                <article class="rd-event-card">
                  <header class="rd-event-head">
                    <span class="rd-msg-role">{{ entry.part.type === 'tool' ? '工具' : roleLabel(entry.role) }}</span>
                    <strong v-if="entry.part.type === 'tool'">{{ entry.part.tool }}</strong>
                    <strong v-else-if="entry.part.type === 'reasoning'">思考过程</strong>
                    <strong v-else>消息</strong>
                    <span class="rd-step-time">{{ fmtTime(entry.time) }}</span>
                  </header>
                  <p v-if="entry.part.type === 'text' && isHtmlReportText(partText(entry.part), entry.role)" class="rd-report-link">
                    HTML 报告已生成，<a :href="runReportUrl(runId)">点击查看具体报告</a>。
                  </p>
                  <pre v-else-if="entry.part.type === 'text'" class="rd-msg-text">{{ partText(entry.part) }}</pre>
                  <details v-else-if="entry.part.type === 'reasoning'" class="rd-reasoning">
                    <summary>展开思考内容</summary>
                    <pre>{{ partText(entry.part) }}</pre>
                  </details>
                  <template v-else-if="entry.part.type === 'tool'">
                    <button type="button" class="rd-tool-toggle" @click="toggleTool(entry.part.callID)">
                      <span class="rd-step-status" :class="`is-${entry.part.state.status}`">{{ entry.part.state.status === 'completed' ? '完成' : entry.part.state.status === 'error' ? '失败' : entry.part.state.status }}</span>
                      <span>{{ openTool === entry.part.callID ? '收起详情' : '查看入参与输出' }}</span>
                      <svg class="ic" :class="{ 'is-open': openTool === entry.part.callID }" width="12" height="12" aria-hidden="true"><use href="#i-chev-down" /></svg>
                    </button>
                    <div v-if="openTool === entry.part.callID" class="rd-step-body">
                      <p v-if="fmtIO(entry.part.state.input)" class="rd-step-label">入参</p>
                      <pre v-if="fmtIO(entry.part.state.input)" class="rd-step-io">{{ fmtIO(entry.part.state.input) }}</pre>
                      <p v-if="fmtIO(entry.part.state.output)" class="rd-step-label">输出</p>
                      <pre v-if="fmtIO(entry.part.state.output)" class="rd-step-io">{{ fmtIO(entry.part.state.output) }}</pre>
                    </div>
                  </template>
                </article>
              </li>
            </ol>
            <div v-if="live && item.files" class="rd-files">
              <span class="rd-files-label">原始数据：</span>
              <a v-if="item.files.html" :href="runReportUrl(runId)">HTML 报告</a>
              <a v-if="item.files.pdf" :href="runReportUrl(runId)" download>译文 PDF</a>
              <a v-if="item.files.events" :href="runFileUrl(runId, 'events')" download>events.jsonl</a>
              <a v-if="item.files.trace" :href="runFileUrl(runId, 'trace')" download>trace.json</a>
              <a v-if="item.files.trace" :href="runFileUrl(runId, 'md')" download>trace.md</a>
            </div>

          </main>
        </div>
      </template>

      <div v-else-if="item" class="adm-panel adm-form">
        <p class="adm-kicker">RUN SUMMARY</p><h2>{{ item.taskTitle || item.promptDigest || item.runId }}</h2>
        <p>{{ skillName }} · {{ OUTCOME_LABEL[item.outcome] }} · {{ fmtDuration(item.durationMs) }}</p><code>{{ item.runId }}</code>
        <p>此运行没有完整的模型 trace。</p>
        <p v-if="item.userMessage">{{ item.userMessage }}</p>
        <p v-if="item.localReply">{{ item.localReply }}</p>
        <a v-if="item.files?.events" class="adm-btn" :href="runFileUrl(runId,'events')" download>下载 events.jsonl</a>
      </div>
      <div v-else class="rd-missing">
        <h1>该运行暂无详情</h1>
        <p>运行不存在或服务暂时无法读取。</p>
        <RouterLink class="btn btn-primary" :to="{ name: 'runs' }">返回运行记录</RouterLink>
      </div>
    </div>
  </section>
</template>
