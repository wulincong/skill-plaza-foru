import { browserHeaders } from './browserHistory.ts'
import type { ChatQuestion } from '../../shared/chatQuestion'
/* ============================================================
   模型对话接入（Node 后端 → pi RPC）
   ------------------------------------------------------------
   浏览器只访问本机 /api/*：后端持有 pi CLI 与模型配置，不进前端。
   /api/chat 为 SSE 流式：text 增量 → usage 用量 → done 收尾。
   未启动本地服务时，工作台会提示如何启动，不影响表单预览。
   ============================================================ */

import type { ExecutionStep } from '../../shared/execution'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export type ApiState = 'checking' | 'ready' | 'offline' | 'nokey'
export type EngineId = 'pi'
export interface DeliveryLink { name: string; url: string }
import type { ReportChart } from '../data/runs'

export type ChatModelId = 'deepseek-flash' | 'deepseek-pro' | 'youcai' | 'deployment'
export interface ChatModelOption { id: ChatModelId; name: string; provider: string; modelId: string }

export interface HealthResult {
  chatModels?: ChatModelOption[]
  defaultChatModel?: ChatModelId
  ok: boolean
  model?: string
  runner?: EngineId
  /** 未就绪时的原因：nokey = 服务在但没读到密钥；offline = 服务没启动 */
  reason?: 'nokey' | 'offline'
  message?: string
}

/* SSE 事件（与 server/index.ts 的输出一一对应） */
export type ChatEvent =
  | { type: 'started'; runId: string; startedAt: number }
  | { type: 'session'; sessionId: string }
  | {
      type: 'status'
      phase: 'initializing' | 'thinking' | 'tool' | 'text'
      state?: 'active' | 'completed' | 'failed'
      message?: string
      chars?: number
      tool?: string
      id?: string
    }
  | { type: 'execution'; index: number; step: ExecutionStep }
  | { type: 'text'; delta: string }
  | { type: 'usage'; usage: Record<string, number | string> }
  | { type: 'done'; question?: ChatQuestion; durationMs?: number; content: string; resultType?: string; charts?: ReportChart[]; runId?: string; reportUrl?: string; webLinks?: DeliveryLink[]; downloads?: DeliveryLink[] }
  | { type: 'error'; durationMs?: number; message: string }

export async function checkHealth(): Promise<HealthResult> {
  try {
    const response = await fetch('/api/health', { cache: 'no-store' })
    const data = (await response.json()) as HealthResult
    if (!response.ok || !data.ok) {
      const message = data.message || 'API 未配置'
      return { ok: false, reason: message.includes('密钥') ? 'nokey' : 'offline', message }
    }
    return { ok: true, model: data.model, runner: data.runner, chatModels: data.chatModels, defaultChatModel: data.defaultChatModel }
  } catch {
    return { ok: false, reason: 'offline', message: '需要启动本地服务' }
  }
}

export interface ChatAttachment {
  /** 展示名（原始文件名） */
  name: string
  /** 相对会话沙箱目录的路径（由 /api/upload 返回，如 uploads/resume.pdf） */
  path: string
}

export interface StreamChatOptions {
  interactive?: boolean
  answerTo?: string
  requestId?: string
  resumeOf?: string
  model?: ChatModelId
  skill: string
  /** 结构化任务生成的用户可读标题，用于运行历史和报告文件名。 */
  taskTitle?: string
  messages: ChatMessage[]
  /** 复用会话（多轮）；缺省由后端新建并通过 session 事件返回 */
  sessionId?: string
  /** 本次消息随带的附件（已上传到会话沙箱） */
  attachments?: ChatAttachment[]
  onEvent: (event: ChatEvent) => void
  signal?: AbortSignal
}

/** 流式对话：消费 /api/chat 的 SSE，逐事件回调。 */
export class ChatRequestError extends Error {
  readonly status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}

export async function streamChat(options: StreamChatOptions): Promise<void> {
  const { skill, model, taskTitle, messages, sessionId, attachments, onEvent, signal } = options
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { ...browserHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ interactive: options.interactive, answerTo: options.answerTo, skill, model, taskTitle, messages, sessionId, attachments, requestId: options.requestId, resumeOf: options.resumeOf }),
    signal,
  })
  if (!response.ok || !response.body) {
    const data = (await response.json().catch(() => ({}))) as { error?: string }
    throw new ChatRequestError(data.error || '请求失败，请稍后重试。', response.status)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let completed = false
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const chunk = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue
          let event: ChatEvent
          try {
            event = JSON.parse(line.slice(6)) as ChatEvent
          } catch {
            /* 跳过无法解析的行 */
            continue
          }
          /* 只捕获 JSON 解析错误，不能吞掉调用方抛出的真实运行错误。 */
          onEvent(event)
          if (event.type === 'error') throw new Error(event.message)
          if (event.type === 'done') completed = true
        }
      }
    }
    if (!completed) throw new Error('运行连接提前断开，未收到完成结果，请重试。')
  } finally {
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}

/** 非流式调用（兼容旧用法）：聚齐流式事件后一次性返回。 */
export async function sendChat(skill: string, messages: ChatMessage[]): Promise<string> {
  let text = ''
  let lastError: string | null = null
  await streamChat({
    skill,
    messages,
    onEvent: event => {
      if (event.type === 'text') text += event.delta
      else if (event.type === 'done') text = event.content || text
      else if (event.type === 'error') lastError = event.message
    },
  })
  if (lastError && !text) throw new Error(lastError)
  if (!text) throw new Error('模型接口返回了无法识别的数据。')
  return text
}
