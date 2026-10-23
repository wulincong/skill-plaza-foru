<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import Icon from './Icon.vue'

/* 消费方（ExperiencePage）的 ProgressItem 结构一致：只携带安全文案，
   工具参数、SQL、路径等敏感细节不进入前端 DOM（手记 030 约定）。
   工具行只登记真实调用；notes 展示面向用户的过程说明，不包含原始 reasoning。 */
export interface ToolProgressItem {
  id: string
  phase: 'thinking' | 'tool' | 'writing' | 'system'
  state: 'active' | 'completed' | 'failed'
  title: string
  detail: string
  tool?: string
  startedAt: number
  finishedAt?: number
}

const props = withDefaults(defineProps<{
  items: ToolProgressItem[]
  /* 正文开始流式输出时置 true：组自动折叠为摘要行 */
  proseStarted?: boolean
  notes?: string[]
  running?: boolean
}>(), { proseStarted: false, running: false })

/* 实时与历史都默认折叠，用户可主动展开查看执行过程。 */
const open = ref(false)
const bodyEl = ref<HTMLElement | null>(null)

watch(() => props.proseStarted, v => { if (v) open.value = false })

/* 展开状态下跟随最新事件贴底 */
watch(() => props.items.length, async () => {
  if (!open.value || !bodyEl.value) return
  await nextTick()
  if (bodyEl.value) bodyEl.value.scrollTop = bodyEl.value.scrollHeight
})

const doneCount = computed(() => props.items.filter(i => i.state !== 'active').length)
const allDone = computed(() => !props.running && doneCount.value === props.items.length)
/* trace 导出不带工具耗时：没有计时数据的组不显示「共 Xs」，不伪造 */
const hasTiming = computed(() => props.items.some(i => i.finishedAt != null))
const totalMs = computed(() => {
  if (!props.items.length) return 0
  const first = props.items[0].startedAt
  const last = Math.max(...props.items.map(i => i.finishedAt ?? i.startedAt))
  return Math.max(0, last - first)
})

const PHASE_ICON: Record<ToolProgressItem['phase'], string> = {
  thinking: 'sparkles',
  tool: 'terminal',
  writing: 'file',
  system: 'note',
}

function fmt(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`
}
</script>

<template>
  <div class="tool-group" :class="{ 'is-open': open }">
    <button type="button" class="tool-group-head" :aria-expanded="open" @click="open = !open">
      <Icon name="wrench" :size="14" class="tool-group-wrench" />
      <span class="tool-group-title">{{ notes?.length ? '工具调用与执行过程' : '工具调用' }}</span>
      <span class="tool-group-status" :class="{ 'is-running': !allDone }">
        <template v-if="allDone">
          <Icon name="check" :size="11" class="tool-status-ok" />
          <template v-if="items.length">已完成 {{ items.length }} 步</template><template v-else>执行结束</template><template v-if="hasTiming"> · 共 {{ fmt(totalMs) }}</template>，点击查看
        </template>
        <template v-else>
          <Icon name="loader" :size="11" class="tool-status-spin" />
          进行中 {{ doneCount }}/{{ items.length }}
        </template>
      </span>
      <Icon name="chev-down" :size="14" class="tool-group-chev" />
    </button>
    <div v-show="open" ref="bodyEl" class="tool-group-body">
      <div v-if="notes?.length" class="tool-process-notes">
        <p v-for="(note, index) in notes" :key="index">{{ note }}</p>
      </div>
      <div v-for="item in items" :key="item.id" class="tool-row" :class="`is-${item.state}`">
        <div class="tool-row-line">
          <Icon :name="PHASE_ICON[item.phase] ?? 'terminal'" :size="13" class="tool-row-icon" />
          <span class="tool-row-name">{{ item.title }}</span>
          <span v-if="item.detail" class="tool-row-detail">{{ item.detail }}</span>
          <span class="tool-row-status" :class="{ 'is-running': item.state === 'active' }">
            <template v-if="item.state === 'active'">
              <Icon name="loader" :size="10" class="tool-status-spin" />进行中
            </template>
            <template v-else-if="item.state === 'failed'">
              <i class="tool-status-fail">!</i>失败
            </template>
            <template v-else-if="item.finishedAt != null">
              <Icon name="check" :size="11" class="tool-status-ok" />{{ fmt(item.finishedAt - item.startedAt) }}
            </template>
            <template v-else>
              <Icon name="check" :size="11" class="tool-status-ok" />已完成
            </template>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
