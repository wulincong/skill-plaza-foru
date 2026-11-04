/** 运行详情从已交付的报告正文提取章节、引用和结论统计。 */
import { readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { deliveryFingerprint, readDeliveryManifest, type DeliveryLinks, type DeliveryManifest } from './delivery.ts'
import { industryReportSections } from './skills.ts'
import { MAX_HTML_REPORT_BYTES, validateHtmlReport } from './htmlReport.ts'

const webFormat = /网页|html\b|web\s*page/i

/** A fresh website may accompany a revision even when the user simply asks
 * to change the legend. A reference to a page is not a request to publish it. */
function webIntent(request: string): 'required' | 'omit' | 'unspecified' {
  if (!webFormat.test(request)) return 'unspecified'
  let intent: 'required' | 'omit' = 'omit'
  for (const clause of request.split(/[，,。；;！!？?\n]/).filter(text => webFormat.test(text))) {
    if (/(?:不要|无需|不用|不需要|不必|禁止|别|不(?:再)?(?:生成|制作|发布|交付|输出|做)|no |without ).{0,6}(?:网页|html|web\s*page)/i.test(clause)) {
      intent = 'omit'
    } else if (!/为什么|为何|怎么|如何|在哪|哪里|参考|作为(?:来源|材料)|(?:链接|路径)(?:是|在)/.test(clause) &&
      (/^(?:网页|html|web\s*page)(?:版|报告|简报|格式)?$/i.test(clause.trim()) ||
       /(?:生成|制作|做成|做个|输出|导出|改成|改为|转成|提供|需要|想要|只要|我要|给我|请给|请用|交付|发布|分享|render|generate).{0,16}(?:网页|html|web\s*page)/i.test(clause))) {
      intent = 'required'
    }
  }
  return intent
}

export function expectsIndustryWeb(request: string): boolean {
  return webIntent(request) === 'required'
}

/** Check the staged public page, where the platform CSP disallows nested documents. */
export function checkIndustryWebEntry(file: string): void {
  if (statSync(file).size > MAX_HTML_REPORT_BYTES) throw new Error('产教报告网页入口超过 8 MiB')
  const html = readFileSync(file, 'utf8')
  if (/<!--\s*chart:[\w-]+\s*-->/.test(html)) throw new Error('网页仍有绘图占位，请运行 embed_chart.py 嵌入已复验图稿')
  const markup = html.replace(/<!--[\s\S]*?-->|<(script|style)\b[^>]*>[\s\S]*?<\/\1\s*>/gi, '')
  if (/<(?:object|embed|iframe)\b/i.test(markup)) throw new Error('平台不显示嵌入文档，请用 embed_chart.py 将完整图块直接放入网页')
  const ids = new Set<string>()
  const outsideFigures = markup.replace(/<figure\b[^>]*>[\s\S]*?<\/figure\s*>/gi, block => {
    if (!/data-chart-(?:id|skill)\s*=|<svg\b[^>]*\bclass\s*=\s*["'][^"']*\bchart\b/i.test(block)) return ''
    const checked = validateHtmlReport(block, {heatmapChecks:false})
    const figure = checked.figures[0]
    if (!checked.pass || !figure?.chartId || ids.has(figure.chartId) || !/<figcaption\b/i.test(block) ||
        (figure.chartStatus !== 'unassessed' && (!/<details\b/i.test(block) || !/<table\b/i.test(block)))) {
      throw new Error('统计图缺少唯一标识、图注或数值表，请用 embed_chart.py 嵌入共享图块')
    }
    ids.add(figure.chartId)
    return ''
  })
  if (Array.from(outsideFigures.matchAll(/<svg\b[^>]*>[\s\S]*?<\/svg\s*>/gi)).some(([svg]) => /<text\b/i.test(svg)) ||
      /<img\b[^>]*\bsrc\s*=\s*["'](?:[^"']*\/)?figure\.svg(?:[?#][^"']*)?["']/i.test(markup)) {
    throw new Error('网页单独引用了图形，请用 embed_chart.py 将共享图稿、图注和数值表作为一个图块嵌入')
  }
}

/** A current build receipt supplies the four originals. A fresh public manifest
 * may additionally declare a requested website or file format. */
export function industryDelivery(workspace: string, runId: string, previous: string | undefined, request: string): DeliveryManifest | undefined {
  const receipt = readDeliveryManifest(workspace, undefined, `industry-build-${runId}.json`)
  if (!receipt) {
    if (deliveryFingerprint(workspace) !== previous) throw new Error('产教报告未通过本轮 build，不能交付')
    return undefined
  }
  const originals = receipt.files ?? []
  const required = [['报告正文','report.md'], ['结构化报告','report.json'], ['结构验收','validation.json'], ['证据复核','review.md']]
  const folder = originals[0]?.path?.match(/^(output\/report-[\w-]+)\/report\.md$/)?.[1]
  if (!folder || originals.length !== required.length || required.some(([name, file], i) =>
    originals[i]?.name !== name || originals[i]?.path !== folder + '/' + file || !/^[a-f0-9]{64}$/.test(originals[i]?.sha256 ?? ''))) throw new Error('产教报告的四份构建文件不完整')
  const formats = [
    {request: /word|docx?/i, ext: /\.docx?$/i}, {request: /pdf/i, ext: /\.pdf$/i},
    {request: /zip|压缩包/i, ext: /\.zip$/i},
  ].filter(f => f.request.test(request) && !new RegExp('(?:不要|无需|不用|不需要)\\s*(?:' + f.request.source + ')', 'i').test(request))
  const intent = webIntent(request)
  let publicManifest: DeliveryManifest | undefined
  if (intent !== 'omit' || formats.length) {
    try {
      publicManifest = readDeliveryManifest(workspace, previous)
    } catch (error) {
      // Optional additions cannot invalidate the verified originals.
      if (intent === 'required' || formats.length) throw error
    }
  }
  const extra = formats.length ? publicManifest?.files ?? [] : []
  const files = [...originals, ...extra.filter(f => formats.some(format => format.ext.test(f.path)))]
  const web = intent !== 'omit' ? publicManifest?.web : undefined
  if (!web?.length) {
    if (intent === 'required') throw new Error('本轮没有登记网页版报告，请在 delivery.json 的 web 中登记 HTML 入口')
    return {files}
  }
  if (!Array.isArray(web) || web.some(item => !item?.directory?.startsWith('output/public/'))) throw new Error('网页版报告须使用 output/public/ 下的专用站点目录')
  return {web, files}
}

export function expectsIndustryBuild(request: string, answer: string): boolean {
  const intent = webIntent(request)
  if (intent === 'required') return true
  if (intent === 'omit') request = request.split(/[，,。；;！!？?\n]/).filter(text => !webFormat.test(text)).join('。')
  if (/仅用文字|只(?:在|用)对话|(?:无需|不用|不要|不需要).{0,4}(?:文件|下载)|(?:怎么|如何).{0,8}(?:生成|构建|下载)/.test(request)) return false
  const deliver = /(?:生成|出具|撰写|交付|修订|制作|重写).{0,30}(?:报告|简报|四份文件)|按(?:现有证据|已有材料)继续|(?:把|将)(?:报告)?标题改(?:为|成)/s
  if (deliver.test(request)) return true
  const revises = /生成|交付|修订|制作|改为|改成|改.*标题/.test(request)
  return revises && /已[^。；\n]{0,28}(?:完成|生成|交付|修订)|^#{1,3} .*(?:决策简报|产教决策报告)/m.test(answer)
}

function deliveredFile(url: string, store: string, extension: string): string {
  const match = /^\/api\/deliveries\/([a-f0-9]{32})\/files\/(\d+)$/.exec(new URL(url).pathname)
  if (!match) throw new Error('报告交付地址无效')
  const file = join(store, match[1], 'files', match[2] + extension)
  if (statSync(file).size > 8 * 1024 * 1024) throw new Error('报告文件过大')
  return readFileSync(file, 'utf8')
}

/** The published JSON selects the same template that rendered this revision. */
export function parseDeliveredReport(delivery: DeliveryLinks, store: string, reply: string): ReportParseResult | null {
  const markdown = delivery.downloads?.find(file => file.name === '报告正文')
  if (markdown) {
    const text = deliveredFile(markdown.url, store, '.md')
    const data = delivery.downloads?.find(file => file.name === '结构化报告')
    if (!data) return parseReport(text)
    const report = JSON.parse(deliveredFile(data.url, store, '.json'))
    const parsed = parseReport(text, industryReportSections(report.edition))
    if (parsed && report.decision) {
      for (const [key, kind] of [['facts','fact'], ['inferences','inference'], ['recommendations','recommendation']] as const) {
        parsed.stats[key] = report.claims.filter((c: { kind: string }) => c.kind === kind).length
      }
      parsed.stats.gaps = report.gaps.length
    }
    return parsed
  }
  if (!/^##\s+/m.test(reply)) return null
  const expected = industryReportSections(/^## 证据与判断$/m.test(reply) ? 'decision' : 'observation')
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
