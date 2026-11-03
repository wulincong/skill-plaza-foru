<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { executionTimes, type ExecutionStep, type TimeSpan } from '../../shared/execution'
import Icon from './Icon.vue'

const props = defineProps<{ steps: ExecutionStep[]; durationMs?: number; running: boolean }>()
const open = ref(false)
const body = ref<HTMLElement>()
const toolCount = computed(() => props.steps.reduce((n, step) => n + step.tools.length, 0))
const times = computed(() => !props.running && props.durationMs !== undefined
  ? executionTimes(props.steps, props.durationMs) : undefined)

watch(() => [props.steps.length, toolCount.value], async () => {
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
    <button type="button" class="tool-group-head" :aria-expanded="open" @click="open = !open">
      <Icon name="wrench" :size="14" class="tool-group-wrench" />
      <span class="tool-group-title">执行过程</span>
      <span class="tool-group-status" :class="{ 'is-running': running }">
        <span v-if="running">进行中 · </span><span v-if="toolCount">{{ toolCount }} 次工具调用 · </span>
        <span v-if="durationMs !== undefined">总用时 {{ fmt(durationMs) }}</span><span v-else>查看详情</span>
      </span>
      <Icon name="chev-down" :size="14" class="tool-group-chev" />
    </button>
    <div v-if="open" ref="body" class="tool-group-body">
      <p v-if="times" class="tool-times" :title="`思考输出 ${times.thinkingMs}ms，工具执行 ${times.toolMs}ms（并行去重），其余时间 ${times.otherMs}ms`">思考输出 {{ fmt(times.thinkingMs) }} · 工具执行 {{ fmt(times.toolMs) }} · 等待与生成 {{ fmt(times.otherMs) }}</p>
      <section v-for="(step, i) in steps" :key="i" class="tool-step">
        <div v-for="(span, j) in step.thinking" :key="j" class="tool-row-line">
          <Icon name="sparkles" :size="13" /><span>模型思考</span>
          <span class="tool-row-status">{{ spanTime(span) || (running && span.startedAt !== undefined ? '进行中' : '') }}</span>
        </div>
        <p v-if="step.note" class="tool-process-note">{{ step.note }}</p>
        <div v-for="tool in step.tools" :key="tool.id" class="tool-row-line">
          <Icon name="terminal" :size="13" /><span>{{ toolNames[tool.tool] ?? tool.tool }}</span>
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
.tool-group-status { display: inline; }
</style>
