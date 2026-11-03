/* ============================================================
   运行记录数据层
   ------------------------------------------------------------
   优先请求后端 /api/runs（真实 trace）；后端不可用时回落到
   runsMock 演示数据，保证纯静态部署也能预览页面结构。
   ============================================================ */

import { RUNS_MOCK, RUN_DETAILS_MOCK, type RunListItem, type RunDetail } from '../data/runsMock'

export interface RunsResult {
  runs: RunListItem[]
  /** true = 后端真实数据；false = 演示数据兜底 */
  live: boolean
}

export async function fetchRuns(opts: { archived?: boolean } = {}): Promise<RunsResult> {
  try {
    const url = opts.archived ? '/api/runs?limit=200&archived=1' : '/api/runs?limit=200'
    const res = await fetch(url, { cache: 'no-store' })
    if (!res.ok) throw new Error(String(res.status))
    const data = (await res.json()) as { runs: RunListItem[] }
    /* 归档列表为空是正常态，不回落演示数据 */
    if (!Array.isArray(data.runs) || (data.runs.length === 0 && !opts.archived)) throw new Error('empty')
    return { runs: data.runs, live: true }
  } catch {
    if (opts.archived) return { runs: [], live: false }
    return { runs: RUNS_MOCK, live: false }
  }
}

/* ---------- 会话归档/删除（key = clientSessionId，旧记录退化为其 runId） ---------- */

export async function setConversationArchived(key: string, archived: boolean): Promise<boolean> {
  try {
    const res = await fetch(`/api/runs/session/${encodeURIComponent(key)}/${archived ? 'archive' : 'unarchive'}`, { method: 'POST' })
    return res.ok
  } catch {
    return false
  }
}

export async function deleteConversation(key: string): Promise<boolean> {
  try {
    const res = await fetch(`/api/runs/session/${encodeURIComponent(key)}`, { method: 'DELETE' })
    return res.ok
  } catch {
    return false
  }
}

/** 删除单条运行记录（运行记录页归档视图） */
export async function deleteRun(runId: string): Promise<boolean> {
  try {
    const res = await fetch(`/api/runs/${encodeURIComponent(runId)}`, { method: 'DELETE' })
    return res.ok
  } catch {
    return false
  }
}

export interface RunDetailResult {
  item?: RunListItem
  trace?: RunDetail
  /** 服务端从 trace 剥离技能提示词包装后的用户可读对话；assistant 轮可带工具摘要（名称+成败） */
  conversation?: Array<{ role: 'user' | 'assistant'; text: string; tools?: Array<{ tool: string; failed: boolean; startedAt?: number; endedAt?: number }>; process?: string[]; webLinks?: Array<{ name: string; url: string }>; downloads?: Array<{ name: string; url: string }> }>
  live: boolean
}

export async function fetchRunDetail(runId: string): Promise<RunDetailResult> {
  try {
    const res = await fetch(`/api/runs/${encodeURIComponent(runId)}`, { cache: 'no-store' })
    if (!res.ok) throw new Error(String(res.status))
    const data = (await res.json()) as { item: RunListItem; trace?: RunDetail; conversation?: RunDetailResult['conversation'] }
    if (!data.item) throw new Error('no item')
    return { item: data.item, trace: data.trace ?? undefined, conversation: data.conversation, live: true }
  } catch {
    return {
      item: RUNS_MOCK.find(r => r.runId === runId),
      trace: RUN_DETAILS_MOCK[runId],
      live: false,
    }
  }
}

/** 原始文件下载地址（仅真实数据可用） */
export function runFileUrl(runId: string, kind: 'events' | 'trace' | 'md' | 'report'): string {
  return `/api/runs/${encodeURIComponent(runId)}/file/${kind}`
}

export function runReportUrl(runId: string): string {
  return `/api/reports/${encodeURIComponent(runId)}`
}
