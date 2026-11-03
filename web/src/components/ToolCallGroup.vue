<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { executionTimes, type ExecutionStep, type TimeSpan } from '../../shared/execution'
import Icon from './Icon.vue'

const props = defineProps<{ steps: ExecutionStep[]; durationMs?: number; running: boolean }>()
const open = ref(false)
const body = ref<HTMLElement>()
const visibleSteps = computed(() => props.steps.filter(step => step.note || step.tools.length))
const tools = computed(() => props.steps.flatMap(step => step.tools))
const finishedCount = computed(() => tools.value.filter(tool => tool.state !== 'active').length)
const times = computed(() => !props.running && props.durationMs !== undefined
  ? executionTimes(props.steps, props.durationMs) : undefined)

const hasDetails = computed(() => Boolean(times.value || visibleSteps.value.length))

watch(() => [visibleSteps.value.length, tools.value.length], async () => {
  const el = body.value
  if (!el || !props.running || el.scrollHeight - el.scrollTop - el.clientHeight > 12) return
  await nextTick()
  el.scrollTop = el.scrollHeight
})

function fmt(ms: number) {
  if (ms < 1000) return Math.round(ms) + 'ms'
  if (ms < 60000) return (ms / 1000).toFixed(1) + '秒'
  return Math.floor(ms / 60000) + '分' + ((ms % 60000) / 1000).toFixed(1) + '秒'
}
function spanTime(span: TimeSpan) {
  return span.startedAt !== undefined && span.endedAt !== undefined ? fmt(span.endedAt - span.startedAt) : ''
}
const toolNames: Record<string, string> = { bash: '执行命令', read: '读取文件', write: '写入文件', edit: '编辑文件' }
</script>

<template>
  <div class="tool-group" :class="{ 'is-open': open }">
    <button type="button" class="tool-group-head" :disabled="!hasDetails" :aria-expanded="open && hasDetails" @click="open = !open">
      <Icon name="wrench" :size="14" class="tool-group-wrench" />
      <span class="tool-group-title">执行过程</span>
      <span class="tool-group-status" :class="{ 'is-running': running }">
        <span v-if="running">进行中 · </span><span v-if="tools.length" title="已结束的工具调用数 / 本轮已记录的工具调用数">工具调用 {{ finishedCount }}/{{ tools.length }} · </span>
        <span v-if="durationMs !== undefined">总用时 {{ fmt(durationMs) }}</span><span v-else-if="hasDetails">查看详情</span>
      </span>
      <Icon v-if="hasDetails" name="chev-down" :size="14" class="tool-group-chev" />
    </button>
    <div v-if="open && hasDetails" ref="body" class="tool-group-body">
      <p v-if="times" class="tool-times" :title="`思考输出 ${times.thinkingMs}ms，工具执行 ${times.toolMs}ms（并行去重），其余时间 ${times.otherMs}ms`">思考输出 {{ fmt(times.thinkingMs) }} · 工具执行 {{ fmt(times.toolMs) }} · 等待与生成 {{ fmt(times.otherMs) }}</p>
      <section v-for="(step, i) in visibleSteps" :key="i" class="tool-step">
        <p v-if="step.note" class="tool-process-note">{{ step.note }}</p>
        <div v-for="tool in step.tools" :key="tool.id" class="tool-row-line">
          <Icon name="terminal" :size="13" class="tool-row-icon" /><span class="tool-row-name">{{ toolNames[tool.tool] ?? tool.tool }}</span>
          <span v-if="tool.purpose" class="tool-row-purpose">{{ tool.purpose }}</span>
          <span class="tool-row-status">{{ tool.state === 'failed' ? '失败' : tool.state === 'active' ? (running ? '进行中' : '未收到结束事件') : '已完成' }} {{ spanTime(tool) }}</span>
        </div>
      </section>
    </div>
  </div>
</template>
<style scoped>
.tool-times, .tool-process-note { margin: 0; padding: 7px 12px; color: var(--sk-ink-3); font-size: 12px; line-height: 1.6; }
.tool-times { background: var(--sk-fill); }
.tool-process-note { white-space: pre-wrap; overflow-wrap: anywhere; }
.tool-step + .tool-step { border-top: 1px solid var(--sk-line); }
.tool-row-purpose { min-width: 0; color: var(--sk-ink-3); font-size: 11px; overflow-wrap: anywhere; }
.tool-group-status { display: inline; }
</style>
