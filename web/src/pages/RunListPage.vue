<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { action, api, busy, catalog } from '../admin/state'
import { bySlug, GENERAL_SKILL_NAME } from '../data/skills'
import { OUTCOME_LABEL, type RunListItem } from '../data/runs'
import Icon from '../components/Icon.vue'

const runs = ref<RunListItem[]>([])
const total = ref(0)
const archived = ref(false)
const skill = ref('')
const outcome = ref('')
const search = ref('')
const page = ref(1)
const limit = 25
const loading = ref(true)
const failure = ref('')
const confirmId = ref('')
let sequence = 0
const pages = computed(() => Math.max(1, Math.ceil(total.value / limit)))
async function load() {
  const seq = ++sequence
  loading.value = true
  failure.value = ''
  confirmId.value = ''
  try {
    const query = new URLSearchParams({
      archived: archived.value ? '1' : '0',
      skill: skill.value,
      outcome: outcome.value,
      q: search.value,
      offset: String((page.value - 1) * limit),
      limit: String(limit),
    })
    const data = await api<{ runs: RunListItem[]; total: number }>('runs?' + query)
    if (seq !== sequence) return
    runs.value = data.runs
    total.value = data.total
    if (page.value > pages.value) page.value = pages.value
  } catch {
    if (seq === sequence) failure.value = '读取运行记录失败，请重试。'
  } finally {
    if (seq === sequence) loading.value = false
  }
}
watch([skill, outcome, archived, search], () => {
  page.value = 1
})
watch(
  [skill, outcome, archived, search, page],
  (_, __, cleanup) => {
    const timer = setTimeout(load, 120)
    cleanup(() => clearTimeout(timer))
  },
  { immediate: true },
)
const title = (id: string) => bySlug.get(id)?.name ?? (id === 'general' ? GENERAL_SKILL_NAME : id)
async function changeArchive(run: RunListItem) {
  await action(
    async () => {
      await api(
        'runs/session/' +
          encodeURIComponent(run.clientSessionId || run.runId) +
          (archived.value ? '/unarchive' : '/archive'),
        'POST',
      )
      await load()
    },
    archived.value ? '会话已恢复' : '会话已归档',
  )
}
async function remove(id: string) {
  if (confirmId.value !== id) {
    confirmId.value = id
    return
  }
  await action(async () => {
    await api('runs/' + encodeURIComponent(id), 'DELETE')
    await load()
  }, '记录已删除')
}
</script>
<template>
  <section>
    <p class="adm-kicker">04 / ACTIVITY</p>
    <div class="adm-heading">
      <div>
        <h1>运行记录</h1>
        <p class="adm-sub">查看所有入口的任务结果、用量与完整执行过程。</p>
      </div>
      <button class="adm-btn" :disabled="loading" @click="load"><Icon name="refresh" :size="14" />刷新</button>
    </div>
    <div class="adm-panel">
      <div class="adm-toolbar">
        <div class="adm-segment" aria-label="归档状态">
          <button :aria-pressed="!archived" @click="archived = false">常规</button
          ><button :aria-pressed="archived" @click="archived = true">已归档</button>
        </div>
        <input v-model="search" type="search" aria-label="搜索运行" placeholder="搜索任务或运行 ID" />
        <select v-model="skill" aria-label="技能筛选">
          <option value="">全部技能</option>
          <option value="general">{{ GENERAL_SKILL_NAME }}</option>
          <option v-for="s in catalog" :key="s.id" :value="s.id">{{ s.title }}</option>
        </select>
        <select v-model="outcome" aria-label="运行结果">
          <option value="">全部结果</option>
          <option v-for="(label, id) in OUTCOME_LABEL" :key="id" :value="id">{{ label }}</option>
        </select>
      </div>
      <div v-if="failure" class="adm-empty" role="alert">
        {{ failure }} <button class="adm-btn" @click="load">重试</button>
      </div>
      <div v-else-if="loading" class="adm-empty" role="status">正在读取运行记录…</div>
      <div v-else-if="!runs.length" class="adm-empty">没有符合条件的运行记录。</div>
      <div v-else class="adm-table-scroll">
        <table class="adm-table">
          <thead>
            <tr>
              <th>任务 / SKILL</th>
              <th>时间</th>
              <th>结果</th>
              <th>耗时</th>
              <th>Token / 工具</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="run in runs" :key="run.runId">
              <td>
                <RouterLink :to="{ name: 'runDetail', params: { runId: run.runId } }">{{
                  run.taskTitle || run.promptDigest || run.runId
                }}</RouterLink
                ><small>{{ title(run.skill) }}</small>
              </td>
              <td>
                {{
                  new Date(run.ts).toLocaleString('zh-CN', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                  })
                }}
              </td>
              <td>
                <span
                  class="adm-badge"
                  :class="{
                    on: run.outcome === 'success',
                    warn: run.outcome === 'error' || run.outcome === 'timeout',
                  }"
                  >{{ OUTCOME_LABEL[run.outcome] }}</span
                >
              </td>
              <td>{{ (run.durationMs / 1000).toFixed(1) }}s</td>
              <td>{{ run.usage?.totalTokens?.toLocaleString() ?? '—' }} / {{ run.toolCallCount ?? '—' }}</td>
              <td>
                <button class="adm-text" :disabled="busy" @click="changeArchive(run)">
                  {{ archived ? '恢复会话' : '归档会话' }}
                </button>
                <button v-if="archived" class="adm-text danger" :disabled="busy" @click="remove(run.runId)">
                  {{ confirmId === run.runId ? '确认删除' : '删除记录' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="adm-pager">
        <small>共 {{ total }} 条 · 第 {{ page }} / {{ pages }} 页</small
        ><button class="adm-btn" :disabled="page <= 1 || loading" @click="page--">上一页</button
        ><button class="adm-btn" :disabled="page >= pages || loading" @click="page++">下一页</button>
      </div>
    </div>
  </section>
</template>
