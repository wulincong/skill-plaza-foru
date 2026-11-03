import type { ChatQuestion } from '../../shared/chatQuestion'
export type RunOutcome = 'success' | 'timeout' | 'aborted' | 'error' | 'historical'

export type ReportChart = {
  id: string
  type: 'bar' | 'stackedBar' | 'histogram' | 'line' | 'map'
  title: string
  data: Array<Record<string, unknown>>
  sourceIds: string[]
  unit?: string
  snapshotDate?: string
  region?: string
  caveat?: string
  altText?: string
  insight?: string
  xAxis?: { name?: string; unit?: string }
  yAxis?: { name?: string; unit?: string }
}

export interface RunListItem {
  localReply?: string
  question?: ChatQuestion
  requestId?: string
  userMessage?: string
  resumeSourceId?: string
  tokenUsage?: { provider?: string | null; model?: string | null }
  webLinks?: Array<{ name: string; url: string }>
  downloads?: Array<{ name: string; url: string }>
  runId: string
  ts: string
  skill: string
  /** 浏览器会话 id：同一会话的多条运行组成一个对话（旧记录缺省退化为单运行一组） */
  clientSessionId?: string
  taskTitle?: string
  promptDigest: string
  outcome: RunOutcome
  /** 执行引擎（历史记录缺省视为 zcode） */
  engine?: 'zcode' | 'pi'
  durationMs: number
  usage?: {
    inputTokens?: number
    outputTokens?: number
    cacheReadTokens?: number
    totalTokens?: number
    /** 本次运行花费（美元，pi 专属） */
    costUsd?: number
  }
  toolCallCount?: number
  /** Agent 与环境快照（历史记录缺省 → 详情页整块隐藏） */
  agentEnv?: {
    agentVersion?: string
    model?: string
    thinking?: string
    node?: string
    os?: string
  }
  /** MVP 直出模式的报告解析摘要（pi 运行才有） */
  report?: {
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
    /** report-meta 侧车校验摘要（来源/指标/结论分级） */
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
      gaps?: Array<Record<string, unknown>>
      risks?: Array<Record<string, unknown>>
      marketAnalysis?: { status?: string; queryId?: string; sampleSize?: number }
      resumeReview?: { strengths?: string[]; missingEvidence?: string[]; rewriteItems?: string[] }
      charts?: ReportChart[]
    }
  }
  /** 原始文件路径（真实数据才有；演示数据无） */
  files?: { events?: string; trace?: string; report?: string; html?: string; pdf?: string }
}

export interface RunToolPart {
  type: 'tool'
  tool: string
  callID: string
  state: { status: string; input?: unknown; output?: unknown }
}

export interface RunTextPart { type: 'text'; text: string }
export interface RunReasoningPart { type: 'reasoning'; text: string }

export type RunPart = RunToolPart | RunTextPart | RunReasoningPart

export interface RunDetail {
  session: {
    id: string
    title: string
    workspace: string
    created: string
    updated: string
  }
  outcome: RunOutcome
  usage?: RunListItem['usage']
  messages: Array<{ seq: number | null; time: string; role?: string; parts: RunPart[] }>
}

export const OUTCOME_LABEL: Record<RunOutcome, string> = {
  success: '成功',
  timeout: '超时',
  aborted: '中断',
  error: '错误',
  historical: '历史',
}
