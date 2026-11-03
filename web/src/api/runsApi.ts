import type { ChatQuestion } from '../../shared/chatQuestion'
import type { ExecutionStep } from '../../shared/execution'
import { browserHeaders } from '../composables/browserHistory'
import type { RunListItem, RunDetail } from '../data/runs'

export interface RunsResult {
  runs: RunListItem[]
  /** true = 后端真实数据；false = 服务不可用 */
  live: boolean
}

export async function fetchRuns(opts: { archived?: boolean } = {}): Promise<RunsResult> {
  try {
    const url = opts.archived ? '/api/conversations?limit=200&archived=1' : '/api/conversations?limit=200'
    const res = await fetch(url, { headers: browserHeaders(), cache: 'no-store' })
    if (!res.ok) throw new Error(String(res.status))
    const data = (await res.json()) as { runs: RunListItem[] }
    /* 归档列表为空是正常态，不回落演示数据 */
    if (!Array.isArray(data.runs)) throw new Error('empty')
    return { runs: data.runs, live: true }
  } catch {
    return { runs: [], live: false }
  }
}

/* ---------- 会话归档/删除（key = clientSessionId，旧记录退化为其 runId） ---------- */

export async function setConversationArchived(key: string, archived: boolean): Promise<boolean> {
  try {
    const res = await fetch(`/api/conversations/session/${encodeURIComponent(key)}/${archived ? 'archive' : 'unarchive'}`, { method: 'POST', headers: browserHeaders() })
    return res.ok
  } catch {
    return false
  }
}

export async function deleteConversation(key: string): Promise<boolean> {
  try {
    const res = await fetch(`/api/conversations/session/${encodeURIComponent(key)}`, { method: 'DELETE', headers: browserHeaders() })
    return res.ok
  } catch {
    return false
  }
}

export interface RunDetailResult {
  item?: RunListItem
  trace?: RunDetail
  /** 服务端从 trace 剥离技能提示词包装后的用户可读对话；assistant 轮可带工具摘要（名称+成败） */
  conversation?: Array<{ question?: ChatQuestion; runId?: string; answerTo?: string; durationMs?: number; execution?: ExecutionStep[]; model?: string; provider?: string; role: 'user' | 'assistant'; text: string; tools?: Array<{ tool: string; failed: boolean; startedAt?: number; endedAt?: number }>; process?: string[]; webLinks?: Array<{ name: string; url: string }>; downloads?: Array<{ name: string; url: string }> }>
  live: boolean
}

export async function fetchRunDetail(runId: string): Promise<RunDetailResult> {
  try {
    const res = await fetch(`/api/conversations/${encodeURIComponent(runId)}`, { headers: browserHeaders(), cache: 'no-store' })
    if (!res.ok) throw new Error(String(res.status))
    const data = (await res.json()) as { item: RunListItem; trace?: RunDetail; conversation?: RunDetailResult['conversation'] }
    if (!data.item) throw new Error('no item')
    return { item: data.item, trace: data.trace ?? undefined, conversation: data.conversation, live: true }
  } catch {
    return { live: false }
  }
}

/** 原始文件下载地址（仅真实数据可用） */
export function runFileUrl(runId: string, kind: 'events' | 'trace' | 'md' | 'report'): string {
  return `/api/admin/runs/${encodeURIComponent(runId)}/file/${kind}`
}

export function runReportUrl(runId: string): string {
  return `/api/reports/${encodeURIComponent(runId)}`
}
