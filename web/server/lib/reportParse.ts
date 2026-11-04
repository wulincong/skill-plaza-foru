/** 运行详情从已交付的报告正文提取章节、引用和结论统计。 */
import { readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import type { DeliveryLinks } from './delivery.ts'
import { industryReportSections } from './skills.ts'

/** Read the immutable Markdown copy published for this turn by report.py build. */
export function parseDeliveredReport(delivery: DeliveryLinks, store: string, reply: string): ReportParseResult | null {
  const link = delivery.downloads?.find(file => file.name === '报告正文')
  if (link) {
    const match = /^\/api\/deliveries\/([a-f0-9]{32})\/files\/(\d+)$/.exec(new URL(link.url).pathname)
    if (!match) throw new Error('报告正文交付地址无效')
    const file = join(store, match[1], 'files', match[2] + '.md')
    if (statSync(file).size > 8 * 1024 * 1024) throw new Error('报告正文过大')
    return parseReport(readFileSync(file, 'utf8'))
  }
  // Earlier clients can still deliver the report directly in their final Markdown.
  if (!/^##\s+/m.test(reply)) return null
  const expected = industryReportSections()
  const parsed = parseReport(reply, expected)
  return parsed && parsed.missingSections.length < expected.length ? parsed : null
}

export interface ReportStats {
  sections: number
  facts: number
  inferences: number
  recommendations: number
  gaps: number
  sources: number
  chars: number
}

export interface ReportParseResult {
  structurePass: boolean
  missingSections: string[]
  sections: Array<{ id?: string; title: string; level: number; chars: number }>
  sources: Array<{ id: string; url: string; cited: number }>
  stats: ReportStats
}

function countMatches(text: string, re: RegExp): number {
  return (text.match(re) ?? []).length
}

/** 解析报告全文；空文本返回 null */
export function parseReport(
  text: string,
  expected: Array<{ id: string; title: string }> = industryReportSections(),
): ReportParseResult | null {
  if (!text || !text.trim()) return null

  /* 章节：按 Markdown 标题切分（# ~ ####），统计各节正文字数 */
  const lines = text.split('\n')
  const sections: ReportParseResult['sections'] = []
  let current: ReportParseResult['sections'][number] | null = null
  for (const line of lines) {
    const m = /^(#{1,4})\s+(.+?)\s*$/.exec(line)
    if (m) {
      current = { title: m[2], level: m[1].length, chars: 0 }
      sections.push(current)
    } else if (current) {
      current.chars += line.length
    }
  }

  /* 期望章节：标题互相包含即算命中（模型可能在标题前后加限定词） */
  const titles = sections.map(s => s.title)
  const missingSections = expected
    .filter(e => !titles.some(t => t.includes(e.title)))
    .map(e => `${e.id} ${e.title}`)

  /* 来源：[S1](https://...) 形态的证据引用按编号聚合；
     模型未必用行内链接（附录表/纯 URL 也常见），以全文唯一 URL 兜底去重 */
  const srcMap = new Map<string, { id: string; url: string; cited: number }>()
  for (const m of text.matchAll(/\[S(\d+)\]\((https?:\/\/[^)\s]+)\)/g)) {
    const id = `S${m[1]}`
    const hit = srcMap.get(id)
    if (hit) hit.cited++
    else srcMap.set(id, { id, url: m[2], cited: 1 })
  }
  let uSeq = 0
  const seenUrls = new Set([...srcMap.values()].map(s => s.url))
  for (const m of text.matchAll(/https?:\/\/[^\s)\]'"，。、；]+/g)) {
    if (seenUrls.has(m[0])) continue
    seenUrls.add(m[0])
    srcMap.set(`U${++uSeq}`, { id: `U${uSeq}`, url: m[0], cited: 1 })
  }
  // The renderer lists shared results and user materials by citation ID without a public URL.
  for (const m of text.matchAll(/^- \*\*([^*]+)\*\* (.+?)；发布机构：/gm)) {
    const url = /\]\(([^)]+)\)/.exec(m[2])?.[1] ?? ''
    if (url) {
      for (const [key, source] of srcMap) if (key.startsWith('U') && source.url === url) srcMap.delete(key)
    }
    if (!srcMap.has(m[1])) srcMap.set(m[1], { id: m[1], url, cited: 1 })
  }
  const sources = [...srcMap.values()]

  /* 分级计数：技能约定的「X1 · fact/inference/recommendation/数据缺口」标记 */
  const stats: ReportStats = {
    sections: sections.length,
    facts: countMatches(text, /·\s*fact\b/gi),
    inferences: countMatches(text, /·\s*inference\b/gi),
    recommendations: countMatches(text, /·\s*recommendation\b/gi),
    gaps: countMatches(text, /·\s*数据缺口/g),
    sources: sources.length,
    chars: text.length,
  }

  return {
    structurePass: missingSections.length === 0,
    missingSections,
    sections,
    sources,
    stats,
  }
}
