export interface ResourceLink { name: string; url: string }
export interface ConversationResource extends ResourceLink {
  kind: 'web' | 'file'
  turn: number
  messageIndex: number
}
interface ResourceMessage {
  role: string
  webLinks?: ResourceLink[]
  downloads?: ResourceLink[]
  reportUrl?: string
  skill?: { slug: string }
}

/** Only server-published links become resources; never infer files from prose. */
export function collectConversationResources(messages: ResourceMessage[]): ConversationResource[] {
  const resources = new Map<string, ConversationResource>()
  let turn = 0
  messages.forEach((message, messageIndex) => {
    if (message.role === 'user') { turn++; return }
    if (message.role !== 'ai') return
    const add = (link: ResourceLink, kind: ConversationResource['kind']) => {
      if (!link.url || resources.has(`${kind}:${link.url}`)) return
      resources.set(`${kind}:${link.url}`, { ...link, kind, turn, messageIndex })
    }
    for (const link of message.webLinks ?? []) add(link, 'web')
    for (const link of message.downloads ?? []) add(link, 'file')
    // Old PDF records stay download-only; HTML records keep their existing routes.
    if (message.reportUrl && !message.webLinks?.length && !message.downloads?.length) {
      const pdf = message.skill?.slug === 'doc-translate'
      if (!pdf) add({ name: '报告网页', url: message.reportUrl }, 'web')
      add({ name: pdf ? '译文 PDF' : '报告文件', url: `${message.reportUrl}/download` }, 'file')
    }
  })
  return [...resources.values()].reverse()
}
