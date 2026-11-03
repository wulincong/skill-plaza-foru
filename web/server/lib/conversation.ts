import { omitReportContinuations } from './reportFollowThrough.ts'
import type { ExecutionStep } from '../../shared/execution.ts'
import { projectQuestion, QUESTION_INSTRUCTION } from './chatQuestion.ts'
import type { ChatQuestion } from '../../shared/chatQuestion.ts'
import { publicToolPurpose } from './execution.ts'
import type { RunRecord } from './traceExport.ts'

export interface ConversationTool {
  tool: string
  failed: boolean
  startedAt?: number
  endedAt?: number
}

export interface ConversationTurn {
  question?: ChatQuestion
  answerTo?: string
  role: 'user' | 'assistant'
  runId?: string
  durationMs?: number
  execution?: ExecutionStep[]
  model?: string
  provider?: string
  text: string
  tools?: ConversationTool[]
  /** 工具调用前面向用户的过程说明；不包含模型 reasoning 或工具输入/输出。 */
  process?: string[]
  webLinks?: Array<{ name: string; url: string }>
  downloads?: Array<{ name: string; url: string }>
}

export interface OriginalUserMessage {
  runId?: string
  durationMs?: number
  execution?: ExecutionStep[]
  model?: string
  provider?: string
  text?: string
  attachments?: string[]
  webLinks?: Array<{ name: string; url: string }>
  downloads?: Array<{ name: string; url: string }>
}

export interface PromptWrapper { prefix: string; suffix: string }

/** Client conversations outlive engine processes. Merge persisted snapshots once
 * per native Pi session; a resumed process can expose the same cumulative trace. */
export function deriveSessionConversation(
  record: RunRecord,
  records: RunRecord[],
  loadTrace: (run: RunRecord) => unknown,
  wrappersFor: (skill: string) => PromptWrapper[],
): ConversationTurn[] {
  const runs = records.filter(run => (record.clientSessionId
    ? run.clientSessionId === record.clientSessionId : run.runId === record.runId) && run.ts <= record.ts)
    .sort((a, b) => a.ts.localeCompare(b.ts) || a.runId.localeCompare(b.runId))
  const groups = new Map<string, { runs: RunRecord[]; trace: unknown; captured: number }>()
  const nativeIds = new Map<string, string>()
  const snapshots = runs.filter(run => !run.promptNotSent).map(run => ({ run, trace: loadTrace(run) as any }))
  const executionByRun = new Map(snapshots.map(({ run, trace }) => [run.runId, trace?.execution]))
  // A later intact snapshot can identify an engine whose earlier trace is missing.
  for (const { run, trace } of snapshots) {
    const engineKey = run.engineSessionId || run.runId
    const nativeId = trace?.session?.id
    if (typeof nativeId === 'string' && nativeId) nativeIds.set(engineKey, `native:${nativeId}`)
  }
  for (const { run, trace } of snapshots) {
    const engineKey = run.engineSessionId || run.runId
    const key = nativeIds.get(engineKey) || `engine:${engineKey}`
    const group = groups.get(key) || { runs: [], trace: null, captured: 0 }
    group.runs.push(run)
    if (Array.isArray(trace?.messages) && trace.messages.some((message: any) => message?.role === 'user')) {
      group.trace = trace; group.captured = group.runs.length
    }
    groups.set(key, group)
  }
  const conversation = [...groups.values()].flatMap(group => {
    const turns = deriveConversation(omitReportContinuations(group.trace,group.runs), wrappersFor(group.runs[0]!.skill), group.runs.slice(0, group.captured).map(run => ({
      runId: run.runId, durationMs: run.durationMs, execution: executionByRun.get(run.runId),
      model: run.outcome === 'success' ? run.tokenUsage?.model ?? undefined : undefined,
      provider: run.outcome === 'success' ? run.tokenUsage?.provider ?? undefined : undefined,
      text: run.userMessage, attachments: run.attachments, webLinks: run.webLinks, downloads: run.downloads,
    })))
    // A missing trace must not remove a saved user message or its published files.
    for (const run of group.runs.slice(group.captured)) {
      turns.push({ role: 'user', runId: run.runId, text: (run.userMessage ?? run.promptDigest) + (run.attachments?.length ? `\n[附件] ${run.attachments.join('、')}` : '') })
      if (run.question) turns.push({ role: 'assistant', runId: run.runId, text: '', question: run.question, webLinks: run.webLinks, downloads: run.downloads })
      else if (run.webLinks?.length || run.downloads?.length) turns.push({ role: 'assistant', text: '', webLinks: run.webLinks, downloads: run.downloads })
    }
    return turns
  })
  // Refresh can precede Pi's prompt. Such a user request has no native message.
  for (const [i, run] of runs.entries()) {
    if (!run.promptNotSent) continue
    const following = new Set(runs.slice(i + 1).map(next => next.runId))
    const at = conversation.findIndex(turn => turn.runId && following.has(turn.runId))
    const text = (run.userMessage ?? run.promptDigest) + (run.attachments?.length ? `\n[附件] ${run.attachments.join('、')}` : '')
    const localTurns: ConversationTurn[] = [{role:'user',runId:run.runId,text}]
    if (run.localReply !== undefined) localTurns.push({role:'assistant',runId:run.runId,text:run.localReply,
      question:run.question,webLinks:run.webLinks,downloads:run.downloads})
    conversation.splice(at < 0 ? conversation.length : at, 0, ...localTurns)
  }
  const byRun = new Map(runs.map(run => [run.runId, run]))
  for (const [i, turn] of conversation.entries()) {
    const run = turn.runId && byRun.get(turn.runId)
    if (!run) continue
    if (turn.role === 'assistant' && run.localReply !== undefined) turn.text = run.localReply
    if (turn.role === 'user') {
      if (run.answerTo) turn.answerTo = run.answerTo
    } else if (run.question || (run.protocol !== 'openai' && run.engine === 'pi' && run.outcome === 'success')) {
      const projected = projectQuestion(turn.text)
      if (run.question || projected.question) {
        turn.question = run.question ?? projected.question
        turn.text = projected.text
        // Pre-card conversations recorded the actual reply as the next user turn.
        const next = conversation[i + 1]
        if (!run.question && next?.role === 'user') next.answerTo = turn.runId
      }
    }
  }
  return conversation
}

export function stripUserPrompt(text: string, wrappers: PromptWrapper[]): string {
  let body = text.trimStart()
  if (body.endsWith('\n\n' + QUESTION_INSTRUCTION)) body = body.slice(0, -(QUESTION_INSTRUCTION.length + 2))
  // 先处理 Pi 已展开的技能；空前后缀不能先命中并吞掉后续清理逻辑。
  if (/^<skill\s+[^>]*\blocation=/.test(body)) {
    const close = body.indexOf('</skill>')
    if (close >= 0) body = body.slice(close + '</skill>'.length).trimStart()
  }
  for (const { prefix, suffix } of wrappers) {
    if (!prefix && !suffix) continue
    if (body.startsWith(prefix) && body.endsWith(suffix)) {
      body = body.slice(prefix.length, suffix ? -suffix.length : undefined).trim()
      break
    }
  }
  for (const { suffix } of wrappers) {
    if (suffix && body.endsWith(suffix)) { body = body.slice(0, -suffix.length); break }
  }
  // 旧记录没有原始输入快照时，仅移除可明确识别的后端附件说明。
  body = body.replace(/\n\n用户已上传附件 [^\n]+，文件在当前工作目录内，请先读取该文件再继续任务。/g, '')
  const inlineAttachment = body.search(/\n\n\[附件 [^\n]+（[^\n]+）内容\]\n/)
  if (inlineAttachment >= 0) body = body.slice(0, inlineAttachment)
  return body.trim()
}

/** 一个用户轮次对应一个回答：仅最后一条无工具的 assistant 消息是正文。 */
export function deriveConversation(
  trace: unknown,
  wrappers: PromptWrapper[],
  originalMessages: OriginalUserMessage[] = [],
): ConversationTurn[] {
  const messages = (trace as any)?.messages
  if (!Array.isArray(messages)) return []
  const userCount = messages.filter(message => message?.role === 'user').length
  const hasOriginals = userCount === originalMessages.length
  const turns: ConversationTurn[] = []
  let userIndex = 0
  let pending: { text: string; hasTools: boolean; step: ExecutionStep }[] = []
  let tools: ConversationTool[] = []
  let inTurn = false
  const flush = () => {
    const original = hasOriginals ? originalMessages[userIndex - 1] : undefined
    if (!pending.length && !tools.length && !original?.webLinks?.length && !original?.downloads?.length) return
    const last = pending.at(-1)
    const final = last && !last.hasTools ? last.text : ''
    const process = pending.slice(0, final ? -1 : undefined).map(message => message.text).filter(Boolean)
    const steps = pending.map((message, i) => ({
      ...message.step, note: i === pending.length - 1 && final ? undefined : message.text || undefined,
    })).filter(step => step.note || step.thinking.length || step.tools.length)
    turns.push({ role: 'assistant', text: final, runId: original?.runId, model: original?.model,
      durationMs: original?.durationMs, execution: original?.execution ?? steps, ...(original?.provider ? { provider: original.provider } : {}), ...(tools.length ? { tools } : {}), ...(process.length ? { process } : {}), ...(original?.webLinks?.length ? { webLinks: original.webLinks } : {}), ...(original?.downloads?.length ? { downloads: original.downloads } : {}) })
    pending = []
    tools = []
  }
  for (const message of messages) {
    const parts = Array.isArray(message?.parts) ? message.parts : []
    const text = parts.filter((part: any) => part?.type === 'text').map((part: any) => String(part.text ?? '')).join('').trim()
    if (message?.role === 'user') {
      flush()
      const original = hasOriginals ? originalMessages[userIndex] : undefined
      userIndex++
      const clean = original?.text ?? stripUserPrompt(text, wrappers)
      const attachments = original?.attachments?.length ? `\n[附件] ${original.attachments.join('、')}` : ''
      turns.push({ role: 'user', runId: original?.runId, text: clean + attachments })
      inTurn = true
    } else if (message?.role === 'assistant' && inTurn) {
      const toolParts = parts.filter((part: any) => part?.type === 'tool')
      for (const part of toolParts) tools.push({
        tool: String(part.tool ?? ''),
        failed: part.state?.status === 'error',
        ...(typeof part.startedAt === 'number' ? { startedAt: part.startedAt } : {}),
        ...(typeof part.endedAt === 'number' ? { endedAt: part.endedAt } : {}),
      })
      // 即使没有 text，也记录最后一条消息是否仍在调用工具，不能把早先的叙述当最终回答。
      pending.push({ text, hasTools: toolParts.length > 0, step: {
        thinking: parts.some((p: any) => p.type === 'reasoning') ? [{}] : [],
        tools: toolParts.map((p: any, i: number) => ({
          id: p.callID ?? String(i), tool: String(p.tool ?? ''),
          purpose: publicToolPurpose(p.state?.input?.purpose),
          state: p.state?.status === 'error' ? 'failed' : 'completed',
        })),
      } })
    }
  }
  flush()
  return turns
}
