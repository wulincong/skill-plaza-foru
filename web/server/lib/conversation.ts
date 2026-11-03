export interface ConversationTool {
  tool: string
  failed: boolean
  startedAt?: number
  endedAt?: number
}

export interface ConversationTurn {
  role: 'user' | 'assistant'
  text: string
  tools?: ConversationTool[]
  /** 工具调用前面向用户的过程说明；不包含模型 reasoning 或工具输入/输出。 */
  process?: string[]
  webLinks?: Array<{ name: string; url: string }>
  downloads?: Array<{ name: string; url: string }>
}

export interface OriginalUserMessage {
  text?: string
  attachments?: string[]
  webLinks?: Array<{ name: string; url: string }>
  downloads?: Array<{ name: string; url: string }>
}

export interface PromptWrapper { prefix: string; suffix: string }

export function stripUserPrompt(text: string, wrappers: PromptWrapper[]): string {
  let body = text.trimStart()
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
  let pending: { text: string; hasTools: boolean }[] = []
  let tools: ConversationTool[] = []
  let inTurn = false
  const flush = () => {
    const original = hasOriginals ? originalMessages[userIndex - 1] : undefined
    if (!pending.length && !tools.length && !original?.webLinks?.length && !original?.downloads?.length) return
    const last = pending.at(-1)
    const final = last && !last.hasTools ? last.text : ''
    const process = pending.slice(0, final ? -1 : undefined).map(message => message.text).filter(Boolean)
    turns.push({ role: 'assistant', text: final, ...(tools.length ? { tools } : {}), ...(process.length ? { process } : {}), ...(original?.webLinks?.length ? { webLinks: original.webLinks } : {}), ...(original?.downloads?.length ? { downloads: original.downloads } : {}) })
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
      turns.push({ role: 'user', text: clean + attachments })
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
      pending.push({ text, hasTools: toolParts.length > 0 })
    }
  }
  flush()
  return turns
}
