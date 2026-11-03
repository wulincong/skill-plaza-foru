export interface TimeSpan { startedAt?: number; endedAt?: number }
export interface ExecutionTool extends TimeSpan {
  id: string
  tool: string
  state: 'active' | 'completed' | 'failed'
}
export interface ExecutionStep {
  thinking: TimeSpan[]
  note?: string
  tools: ExecutionTool[]
}

/** Wall time covered by the union of measured intervals. Parallel tools count once. */
function covered(spans: TimeSpan[]) {
  const intervals = spans.flatMap(({ startedAt, endedAt }) =>
    startedAt !== undefined && endedAt !== undefined && endedAt >= startedAt ? [[startedAt, endedAt]] : [])
  let total = 0
  let last = -Infinity
  for (const [start, end] of intervals.sort((a, b) => a[0] - b[0])) {
    total += Math.max(0, end - Math.max(start, last))
    last = Math.max(last, end)
  }
  return total
}

export function executionTimes(steps: ExecutionStep[], total: number) {
  const tools = steps.flatMap(step => step.tools)
  const thinking = steps.flatMap(step => step.thinking)
  if ([...tools, ...thinking].some(s => s.startedAt === undefined || s.endedAt === undefined)) return
  const measured = covered([...tools, ...thinking])
  if (measured > total) return
  const toolMs = covered(tools)
  return { toolMs, thinkingMs: measured - toolMs, otherMs: total - measured }
}
