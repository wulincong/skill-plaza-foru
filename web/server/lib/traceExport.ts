/* ============================================================
   运行 Trace 记录与导出
   ------------------------------------------------------------
   三层：实时事件流（RunRecorder，逐行落盘）/ 权威导出
   （Pi RPC → trace.json）/ 运行索引（index.jsonl）。
   目录：web/server/traces/（TRACES_DIR 环境变量可覆盖）。
   评测只依赖 index.jsonl 与 <runId>.json，schema 保持稳定。
   ============================================================ */

import { appendFileSync, mkdirSync, writeFileSync, readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { ExecutionStep } from '../../shared/execution.ts'
import type { HtmlReportValidation } from './htmlReport.ts'

const __dirname = dirname(fileURLToPath(import.meta.url))
export const TRACES_DIR = process.env.TRACES_DIR || join(__dirname, '..', 'traces')

export interface UsageSummary {
  inputTokens?: number
  outputTokens?: number
  cacheReadTokens?: number
  totalTokens?: number
  /** 本次运行花费（美元）；pi 的 usage 事件自带 cost.total，按轮累计 */
  costUsd?: number
}

/** 当前模型及上下文窗口的来源；unknown 不作为默认值，拿不到时固定使用 unavailable。 */
export interface ModelContextInfo {
  model?: string | null
  provider?: string | null
  contextWindowTokens?: number | null
  contextWindowSource?: string
  /** Provider 明确报告的某轮最大上下文占用。 */
  peakContextTokens?: number | null
}

/** 一次实际模型请求的 token 用量；与运行期间累计 usage 分开记录。 */
export interface UsageRound {
  round: number
  model: string | null
  provider: string | null
  inputTokens: number | null
  outputTokens: number | null
  cacheReadTokens: number | null
  totalTokens: number | null
  /** Provider/runtime 明确报告的该次请求上下文占用。 */
  contextTokens: number | null
  contextWindowTokens: number | null
  contextWindowSource: string
  contextUsageRatio: number | null
}

/** runStart、runEnd、索引和权威 trace 共用的完整累计/上下文快照。 */
export interface TokenUsageSnapshot {
  model: string | null
  provider: string | null
  contextWindowTokens: number | null
  contextWindowSource: string
  inputTokens: number
  outputTokens: number
  cacheReadTokens: number
  totalTokens: number
  peakContextTokens: number | null
  contextUsageRatio: number | null
}

export interface TraceExportOptions {
  execution?: ExecutionStep[]
  tokenUsage?: TokenUsageSnapshot
  usageRounds?: UsageRound[]
}

export function tokenUsageFrom(
  usage?: UsageSummary,
  context: ModelContextInfo = {},
  rounds: UsageRound[] = [],
): TokenUsageSnapshot {
  const contextWindowTokens = Number.isFinite(context.contextWindowTokens) && (context.contextWindowTokens ?? 0) > 0
    ? Number(context.contextWindowTokens)
    : null
  const peakFromRounds = rounds.reduce<number | null>(
    (peak, round) => round.contextTokens === null ? peak : Math.max(peak ?? 0, round.contextTokens),
    null,
  )
  const peakContextTokens = Number.isFinite(context.peakContextTokens)
    ? Number(context.peakContextTokens)
    : peakFromRounds
  const ratio =
    peakContextTokens !== null && contextWindowTokens !== null
      ? peakContextTokens / contextWindowTokens
      : null
  return {
    model: context.model ?? null,
    provider: context.provider ?? null,
    contextWindowTokens,
    contextWindowSource:
      context.contextWindowSource ??
      (contextWindowTokens === null ? 'provider_metadata_unavailable' : 'provider_metadata'),
    inputTokens: usage?.inputTokens ?? 0,
    outputTokens: usage?.outputTokens ?? 0,
    cacheReadTokens: usage?.cacheReadTokens ?? 0,
    totalTokens: usage?.totalTokens ?? 0,
    peakContextTokens,
    contextUsageRatio: ratio,
  }
}

/** 将完整快照放入旧 usage 字段，兼容已有列表消费者。 */
export function usageWithTokenSnapshot(
  usage: UsageSummary | undefined,
  snapshot: TokenUsageSnapshot,
): UsageSummary & TokenUsageSnapshot {
  return {
    ...(usage ?? {}),
    ...snapshot,
  }
}

/** Agent 与环境快照（随运行落盘：升级 CLI/换模型不影响旧记录的复现对比） */
export interface AgentEnvInfo {
  /** Agent CLI 版本（--version / package.json 探测；失败省略，界面显示 —） */
  agentVersion?: string
  /** 模型标识（pi：provider/modelId） */
  model?: string
  /** 思考档位（pi 专属） */
  thinking?: string
  /** 服务端 Node 版本（process.version） */
  node?: string
  /** 操作系统（平台 + 架构，如 darwin arm64） */
  os?: string
}

export type RunOutcome = 'success' | 'timeout' | 'error' | 'aborted' | 'historical'

export interface RunRecord {
  /** 索引与文件名共用的运行标识：YYYYMMDD-HHMMSS-xxxx */
  runId: string
  ts: string
  clientSessionId: string
  /** 执行引擎；历史记录可能保留旧版 zcode 值。 */
  engine?: 'zcode' | 'pi'
  /** 入口协议：plaza=广场 /api/chat，openai=/v1/chat/completions；旧记录缺省视为 plaza */
  protocol?: 'plaza' | 'openai'
  engineSessionId?: string
  skill: string
  /** 用户可读的运行标题；旧记录缺省时回退到 promptDigest。 */
  taskTitle?: string
  /** 用户原始输入（注入技能/附件说明之前），用于历史对话恢复；旧记录缺省。 */
  userMessage?: string
  promptNotSent?: boolean
  requestId?: string
  resumeSourceId?: string
  attachmentFiles?: Array<{ name: string; path: string }>
  promptDigest: string
  outcome: RunOutcome
  durationMs: number
  /** 会话归档标记（前端侧栏隐藏，?archived=1 可查）；由 /api/runs/session/:id 写入 */
  archived?: boolean
  usage?: UsageSummary
  /** 完整累计 token 与上下文窗口快照；usage 保留旧字段形状。 */
  tokenUsage?: TokenUsageSnapshot
  /** 每次实际模型请求的用量，累计 usage 不替代此数组。 */
  usageRounds?: UsageRound[]
  toolCallCount?: number
  /** 本次运行随消息上传的附件文件名（文件在会话沙箱 uploads/ 下） */
  attachments?: string[]
  /** Agent 与环境快照（版本/模型/系统等；历史记录缺省） */
  agentEnv?: AgentEnvInfo
  /** MVP 直出模式的报告解析摘要（pi 专属；全文见 files.report） */
  report?: {
    /** industry-education-report 章节校验（reportParse） */
    structurePass?: boolean
    missingSections?: string[]
    stats?: {
      sections: number
      facts: number
      inferences: number
      recommendations: number
      gaps: number
      sources: number
      chars: number
    }
    /** report-meta 侧车校验摘要（SIDECAR_SKILLS；见 lib/reportMeta.ts） */
    meta?: {
      pass: boolean
      errors: string[]
      counts: {
        sources: number
        metrics: number
        facts: number
        inferences: number
        recommendations: number
        charts: number
      }
      /** 开发侧缺口与风险；用户页不读取。 */
      gaps?: Array<Record<string, unknown>>
      risks?: Array<Record<string, unknown>>
      marketAnalysis?: Record<string, unknown>
      resumeReview?: Record<string, unknown>
      /** 已通过侧车校验的图表规格，供运行详情页渲染。 */
      charts?: Array<Record<string, unknown>>
    }
    /** career-guidance HTML figure/heatmap structural check. */
    html?: HtmlReportValidation
  }
  webLinks?: Array<{ name: string; url: string }>
  downloads?: Array<{ name: string; url: string }>
  files: { events?: string; trace?: string; report?: string; html?: string; pdf?: string }
}

/** 时间可读 id：YYYYMMDD-HHMMSS-xxxx；prefix 用于区分用途（runId 无前缀，会话 id 传 'sess-'） */
export function newRunId(prefix = ''): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  const rand = Math.random().toString(36).slice(2, 6)
  return `${prefix}${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}-${rand}`
}

export function appendIndex(rec: RunRecord): void {
  mkdirSync(TRACES_DIR, { recursive: true })
  appendFileSync(join(TRACES_DIR, 'index.jsonl'), JSON.stringify(rec) + '\n')
}

export function readIndex(): RunRecord[] {
  try {
    return readFileSync(join(TRACES_DIR, 'index.jsonl'), 'utf8')
      .split('\n')
      .filter(Boolean)
      .map((line) => JSON.parse(line) as RunRecord)
  } catch {
    return []
  }
}

/** 整体重写运行索引（归档标记/删除会话用）。同步写与同步 append 单线程内不交错；
    trace 文件保留在磁盘（删除是索引层面的，不做不可逆清理）。 */
export function rewriteIndex(records: RunRecord[]): void {
  mkdirSync(TRACES_DIR, { recursive: true })
  writeFileSync(join(TRACES_DIR, 'index.jsonl'), records.map(r => JSON.stringify(r) + '\n').join(''))
}

export function traceFilePath(runId: string, kind: 'events' | 'trace' | 'report' | 'html' | 'pdf'): string {
  if (kind === 'events') return join(TRACES_DIR, `${runId}.events.jsonl`)
  if (kind === 'report') return join(TRACES_DIR, `${runId}.report.json`)
  if (kind === 'html') return join(TRACES_DIR, `${runId}.report.html`)
  if (kind === 'pdf') return join(TRACES_DIR, `${runId}.translation.pdf`)
  return join(TRACES_DIR, `${runId}.json`)
}

/* ------------------------------------------------------------
   实时记录器：appendFileSync 逐行落盘，崩溃不丢已写内容
   ------------------------------------------------------------ */

export class RunRecorder {
  readonly file: string
  private closed = false

  constructor(runId: string, meta: Record<string, unknown>) {
    mkdirSync(TRACES_DIR, { recursive: true })
    this.file = traceFilePath(runId, 'events')
    this.line({ t: now(), kind: 'runStart', ...meta })
  }

  /**
   * 会话创建后补齐 runStart 的 provider/model 元数据。创建阶段尚未挂接
   * proto tap，因此首行仍可安全更新；如果已有后续事件则保持原始首行。
   */
  updateStart(meta: Record<string, unknown>): void {
    if (this.closed) return
    try {
      const lines = readFileSync(this.file, 'utf8').split('\n')
      if (!lines[0]) return
      const first = JSON.parse(lines[0]) as Record<string, unknown>
      if (first.kind !== 'runStart') return
      lines[0] = JSON.stringify({ ...first, ...meta })
      writeFileSync(this.file, lines.join('\n'))
    } catch {
      /* 仅补充元数据失败不影响运行 */
    }
  }

  /** 协议交互（带 sessionId 的请求/响应/通知） */
  proto(dir: 'out' | 'in', msg: unknown): void {
    this.line({ t: now(), kind: 'proto', dir, msg })
  }

  /** 补记无法归属到协议方向的说明行 */
  note(msg: Record<string, unknown>): void {
    this.line({ t: now(), kind: 'note', ...msg })
  }

  end(outcome: RunOutcome, extra: Record<string, unknown> = {}): void {
    if (this.closed) return
    this.closed = true
    this.line({ t: now(), kind: 'runEnd', outcome, ...extra })
  }

  private line(obj: Record<string, unknown>): void {
    try {
      appendFileSync(this.file, JSON.stringify(obj) + '\n')
    } catch {
      /* 记录失败不影响主流程 */
    }
  }
}

function now(): string {
  return new Date().toISOString()
}

/* ------------------------------------------------------------
   权威导出：Pi RPC get_messages → trace.json
   schema：session / summary / messages
   ------------------------------------------------------------ */

export interface SessionTrace {
  execution?: ExecutionStep[]
  session: {
    id: string
    title: string
    workspace: string
    created: string
    updated: string
    trace_id?: string
  }
  /** 权威 trace 顶层保留完整快照，便于不读取运行索引也能审计上下文。 */
  model: string | null
  provider: string | null
  contextWindowTokens: number | null
  contextWindowSource: string
  inputTokens: number
  outputTokens: number
  cacheReadTokens: number
  totalTokens: number
  peakContextTokens: number | null
  contextUsageRatio: number | null
  /** 一次实际请求一条；以上 token 字段是整个运行期间累计值。 */
  usageRounds: UsageRound[]
  summary: {
    messages: number
    toolCalls: Array<{ tool: string; status: string; read_only: boolean; started: string }>
  }
  messages: Array<{ seq: number | null; time: string; role?: string; parts: unknown[] }>
}
