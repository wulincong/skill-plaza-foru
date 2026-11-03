import type { ChatAttachment, ChatModelId } from './useChatApi'
import type { RunListItem } from '../data/runsMock'

/** One in-flight submission per browser tab, saved before the first network request. */
export interface ChatSubmission {
  sessionId: string
  requestId: string
  text: string
  skill: string
  model?: ChatModelId
  taskTitle?: string
  attachments?: ChatAttachment[]
  answerTo?: string
  resumeOf?: string
}

export function newRequestId(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), n => n.toString(16).padStart(2, '0')).join('')
}

const KEY = 'skill-plaza:in-flight-chat'

export function saveSubmission(task: ChatSubmission | null) {
  try {
    if (task) sessionStorage.setItem(KEY, JSON.stringify(task))
    else sessionStorage.removeItem(KEY)
  } catch { /* Browser storage can be disabled. Server history remains available. */ }
}

export function readSubmission(): ChatSubmission | null {
  try {
    const task = JSON.parse(sessionStorage.getItem(KEY) ?? 'null')
    return task && typeof task.text === 'string' && typeof task.skill === 'string' &&
      typeof task.sessionId === 'string' && /^[a-f0-9]{32}$/.test(task.requestId) ? task : null
  } catch { return null }
}

export async function interruptSubmission(task: ChatSubmission, keepalive = false): Promise<{
  state: 'settling' | 'saved' | 'missing'
  retryId?: string
  latest?: RunListItem
}> {
  const url = '/api/runs/session/' + encodeURIComponent(task.sessionId) + '/interrupt/' + encodeURIComponent(task.requestId)
  const res = await fetch(url, { method: 'POST', keepalive })
  if (!res.ok) throw new Error('暂时无法读取任务状态。')
  return res.json()
}
