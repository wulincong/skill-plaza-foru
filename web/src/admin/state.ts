import { computed, ref } from 'vue'
import { toast } from '../composables/toast'
import { bySlug } from '../data/skills'

export interface Settings {
  defaultModel: string
  allowModelChoice: boolean
  thinking: string
  reportThinking: string
  youcaiEndpoint: string
  timeoutMs: number
  installedTimeoutMs: number
  idleMs: number
}
export interface Config {
  revision: number
  disabledSkills: string[]
  settings: Settings
  activeKey: string
  keys: { id: string; name: string }[]
  environmentKeyConfigured: boolean
  models: { id: string; name: string; provider: string; modelId: string }[]
  thinkingLevels: string[]
}
interface State {
  username: string
  config: Config
  skills: { id: string; name: string; description: string; installed: boolean }[]
  stats: { total: number; last24h: number; successes: number }
  deployment: { sandbox: string; environment: string; databaseConfigured: boolean }
}

export const state = ref<State>()
export const busy = ref(false)
export const errorMessage = ref('')
export const catalog = computed(() =>
  (state.value?.skills ?? []).map((skill) => ({
    ...skill,
    title: bySlug.get(skill.id)?.name ?? skill.name,
    description: bySlug.get(skill.id)?.summary ?? skill.description,
    enabled: !state.value!.config.disabledSkills.includes(skill.id),
  })),
)
export const activeModel = computed(() =>
  state.value?.config.models.find((m) => m.id === state.value?.config.settings.defaultModel),
)

export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const res = await fetch('/api/admin/' + path, {
    method,
    cache: 'no-store',
    credentials: 'same-origin',
    headers: method === 'GET' ? {} : { 'Content-Type': 'application/json', 'X-Plaza-Admin': '1' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await res.json()
  if (!res.ok) {
    if (res.status === 401) state.value = undefined
    throw new Error(data.error || '请求失败')
  }
  return data
}

export async function refresh() {
  state.value = await api<State>('state')
}
export async function action(fn: () => Promise<void>, message?: string) {
  if (busy.value) return false
  busy.value = true
  errorMessage.value = ''
  try {
    await fn()
    if (message) toast(message)
    return true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '服务连接失败'
    return false
  } finally {
    busy.value = false
  }
}
export function save(section: string, fields: Record<string, unknown>, message: string) {
  return action(async () => {
    if (!state.value) throw new Error('请重新登录')
    state.value.config = await api<Config>(section, 'PUT', { ...fields, revision: state.value.config.revision })
  }, message)
}
