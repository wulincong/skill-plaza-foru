import { createReadStream } from 'node:fs'
import { createInterface } from 'node:readline'
import type { ExecutionStep, TimeSpan } from '../../shared/execution.ts'
import { extractSidecar } from './reportMeta.ts'

/** Only the dedicated, short Chinese display phrase may leave the tool arguments. */
export function publicToolPurpose(value: unknown): string | undefined {
  if (typeof value !== 'string') return
  const phrase = value.trim().replace(/。$/, '')
  return /^\p{Script=Han}{4,24}$/u.test(phrase) ? phrase : undefined
}

/** Group timing, public narration, tool names and purposes by assistant message.
 * Never copy raw RPC payloads into the execution timeline. */
export class ExecutionTracker {
  steps: ExecutionStep[] = []
  private step?: ExecutionStep
  private thought?: TimeSpan
  private calls = new Map<string, ExecutionStep>()

  private currentStep() {
    if (!this.step) {
      this.step = { thinking: [], tools: [] }
      this.steps.push(this.step)
    }
    return this.step
  }

  accept(msg: any, at: number): ExecutionStep | undefined {
    if (msg.type === 'message_start' && msg.message?.role === 'assistant') {
      this.step = undefined
      this.thought = undefined
    }
    if (msg.type === 'message_update') {
      const type = msg.assistantMessageEvent?.type
      if (type === 'thinking_start' || (type === 'thinking_delta' && !this.thought)) {
        this.thought = { startedAt: at }
        this.currentStep().thinking.push(this.thought)
        return this.step
      }
      if (type === 'thinking_end' && this.thought) {
        this.thought.endedAt = at
        this.thought = undefined
        return this.step
      }
    }
    if (msg.type === 'message_end' && msg.message?.role === 'assistant') {
      const parts = Array.isArray(msg.message.content) ? msg.message.content : []
      // Some providers return a completed reasoning block without streaming its boundaries.
      if (parts.some((p: any) => p.type === 'thinking' && p.thinking) && !this.step?.thinking.length) {
        this.currentStep().thinking.push({})
      }
      const calls = parts.filter((p: any) => p.type === 'toolCall')
      if (calls.length) {
        const step = this.currentStep()
        for (const call of calls) this.calls.set(call.id, step)
        const text = parts.filter((p: any) => p.type === 'text').map((p: any) => p.text).join('')
        step.note = extractSidecar(text).cleanText.trim() || undefined
      }
      return this.step
    }
    if (msg.type === 'tool_execution_start' || msg.type === 'tool_execution_end') {
      const id = msg.toolCallId
      if (typeof id !== 'string') return
      const step = this.calls.get(id) ?? this.currentStep()
      this.calls.set(id, step)
      let tool = step.tools.find(t => t.id === id)
      if (!tool) {
        tool = { id, tool: msg.toolName, state: 'active' }
        step.tools.push(tool)
      }
      if (msg.type === 'tool_execution_start') {
        tool.startedAt = at
        tool.purpose = publicToolPurpose(msg.args?.purpose) ?? ({report_next:'读取已核实报告证据',report_submit:'校验并保存分析章节',report_build:'生成并检查报告图片'} as Record<string,string>)[msg.toolName]
      } else {
        tool.endedAt = at
        tool.state = msg.isError ? 'failed' : 'completed'
      }
      return step
    }
  }
}

/** Older snapshots only timed streamed tool arguments. Recover execution from
 * the run-owned RPC log when present, without loading an entire log into RAM. */
export async function readLegacyExecution(file: string) {
  const tracker = new ExecutionTracker()
  const stream = createReadStream(file, { encoding: 'utf8' })
  try {
    for await (const line of createInterface({ input: stream, crlfDelay: Infinity })) {
      if (!line.includes('"dir":"in"') || !/"type":"(?:message_start|message_end|thinking_start|thinking_end|tool_execution_start|tool_execution_end)"/.test(line)) continue
      const frame = JSON.parse(line)
      const at = Date.parse(frame.t)
      if (frame.kind === 'proto' && frame.dir === 'in' && frame.msg && Number.isFinite(at)) tracker.accept(frame.msg, at)
    }
    return tracker.steps.length ? tracker.steps : undefined
  } catch {
    return undefined
  } finally {
    stream.destroy()
  }
}
