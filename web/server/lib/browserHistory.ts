import { createHash } from 'node:crypto'
import type { RunRecord } from './traceExport.ts'

/** A private browser capability scopes anonymous conversations without exposing the
 * capability in public session IDs, traces, URLs, or the administrator's exports. */
export function historyPrefix(req: { headers: Record<string, unknown> }): string | undefined {
  const value = req.headers['x-plaza-browser']
  if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) return
  return 'web-' + createHash('sha256').update(value).digest('hex').slice(0, 32) + '-'
}

export function scopedSession(raw: unknown, prefix?: string) {
  if (typeof raw !== 'string' || !/^[\w-]{1,217}$/.test(raw)) return null
  if (/^web-[a-f0-9]{32}-/.test(raw)) return prefix && raw.startsWith(prefix) ? raw : null
  if (raw.length > 180) return null
  return prefix ? prefix + raw : raw
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
    webLinks,
    downloads,
    archived,
    tokenUsage: { provider: tokenUsage?.provider, model: tokenUsage?.model },
    files: { html: Boolean(r.files?.html), pdf: Boolean(r.files?.pdf) },
  }
}
