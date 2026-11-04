import { createHash } from 'node:crypto'
import type { RunRecord } from './traceExport.ts'

/** Salt provisional session names to avoid collisions between browsers. Published IDs are shared. */
export function historyPrefix(req: { headers: Record<string, unknown> }): string | undefined {
  const value = req.headers['x-plaza-browser']
  if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) return
  return 'web-' + createHash('sha256').update(value).digest('hex').slice(0, 32) + '-'
}

export const browserSessionPattern = /^web-[a-f0-9]{32}-/

export function validSessionId(raw: unknown): raw is string {
  return typeof raw === 'string' && /^[a-zA-Z0-9_-]{1,217}$/.test(raw) && (raw.length <= 180 || browserSessionPattern.test(raw))
}

export function conversationItem(r: RunRecord) {
  const {
    runId,
    clientSessionId,
    ts,
    skill,
    engine,
    promptDigest,
    taskTitle,
    userMessage,
    outcome,
    durationMs,
    requestId,
    question,
    tokenUsage,
    webLinks,
    downloads,
    archived,
  } = r
  return {
    runId,
    clientSessionId: clientSessionId || runId,
    userMessage,
    requestId,
    ts,
    skill,
    engine,
    promptDigest,
    taskTitle,
    outcome,
    durationMs,
    question,
    webLinks,
    downloads,
    archived,
    tokenUsage: { provider: tokenUsage?.provider, model: tokenUsage?.model },
    files: { html: Boolean(r.files?.html), pdf: Boolean(r.files?.pdf) },
  }
}
