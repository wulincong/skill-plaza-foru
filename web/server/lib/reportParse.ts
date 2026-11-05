/** 运行详情从已交付的报告正文提取章节、引用和结论统计。 */
import { readFileSync, statSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { deliveryFingerprint, readDeliveryManifest, type DeliveryLinks, type DeliveryManifest } from './delivery.ts'
import { industryReportSections } from './skills.ts'

const webFormat = /网页|html\b|web\s*page/i

/** A fresh website may accompany a revision even when the user simply asks
 * to change the legend. References alone do not request a build; completed content defaults to web delivery. */
function webIntent(request: string): 'required' | 'omit' | 'unspecified' {
  if (!webFormat.test(request)) return 'unspecified'
  let intent: 'required' | 'omit' | 'unspecified' = 'unspecified'
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
  return webIntent(request) !== 'omit'
}

/** Only presentation work can reuse a previously delivered content version. */
export function isIndustryPresentationRevision(request: string): boolean {
  return /网页|排版|样式|主题|图表|图例|配色|字体|布局|html/i.test(request) &&
    !/完整报告|全量|重查|刷新|重新(?:分析|查询|评估|生成|制作)|改.{0,8}(?:地区|范围|城市|产业|数据|结论)|(?:换|改为|改成).{0,12}(?:市|省|专业)|新(?:的)?报告/.test(request)
}

/** A current build receipt supplies the four originals. A fresh public manifest
 * may additionally declare a requested website or file format. */
export function industryDelivery(workspace: string, runId: string, previous: string | undefined, request: string): DeliveryManifest | undefined {
  const publicManifest = readDeliveryManifest(workspace, previous)
  let receipt = readDeliveryManifest(workspace, undefined, `industry-build-${runId}.json`)
  let reused = false
  if (!receipt && publicManifest?.web?.length && isIndustryPresentationRevision(request)) {
    const context = JSON.parse(readFileSync(join(workspace, 'industry-report-input.json'), 'utf8'))
    const prior = context.previousBuildRun
    if (context.runId === runId && /^[0-9]{8}-[0-9]{6}-[a-z0-9]+$/.test(prior ?? '')) {
      receipt = readDeliveryManifest(workspace, undefined, `industry-build-${prior}.json`)
      reused = !!receipt
      if (receipt && JSON.stringify(publicManifest.files) !== JSON.stringify(receipt.files)) {
        throw new Error('纯呈现修订须保留上一已交付版本的四份原件及指纹；内容改变请重新 build')
      }
    }
  }
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
  const extra = formats.length ? publicManifest?.files ?? [] : []
  const files = [...originals, ...extra.filter(f => formats.some(format => format.ext.test(f.path)))]
  const web = intent !== 'omit' ? publicManifest?.web : undefined
  if (!web?.length) {
    if (intent !== 'omit') throw new Error('完整报告须交付网页：请按 report-rendering 完成并更新 delivery.json 的 web，不能停在四份业务文件')
    return {files}
  }
  if (!Array.isArray(web) || web.some(item => !item?.directory?.startsWith('output/public/'))) throw new Error('网页版报告须使用 output/public/ 下的专用站点目录')
  // Keep the content association for subsequent presentation-only revisions.
  // publishDelivery still verifies every original against these hashes.
  if (reused) writeFileSync(join(workspace, `industry-build-${runId}.json`), JSON.stringify({files: originals}), {flag:'wx',mode:0o640})
  return {web, files}
}

export function expectsIndustryBuild(request: string, answer: string): boolean {
  const intent = webIntent(request)
  if (intent === 'required') return true
  if (intent === 'omit') request = request.split(/[，,。；;！!？?\n]/).filter(text => !webFormat.test(text)).join('。')
  if (/仅用文字|只(?:在|用)对话|(?:无需|不用|不要|不需要).{0,4}(?:文件|下载)|(?:怎么|如何).{0,8}(?:生成|构建|下载)/.test(request)) return false
  if (isIndustryPresentationRevision(request) &&
      /(?:报告|网页|图表)[^。\n]{0,12}已(?:生成|完成|更新|准备就绪)|已(?:成功)?[^。\n]{0,12}(?:生成|嵌入|更新|交付)[^。\n]{0,12}(?:报告|网页|图表)/.test(answer)) return true
  if (/^(?:为什么|为何|怎么|如何|解释)/.test(request.trim())) return false
  const deliver = /(?:生成|出具|撰写|交付|修订|制作|重写).{0,30}(?:报告|简报|四份文件)|按(?:现有证据|已有材料)继续|(?:把|将)(?:报告)?标题改(?:为|成)/s
  if (deliver.test(request)) return true
  if (/^(?:继续|扩大范围|补充材料)(?:[，,。；;\s]|$)/.test(request.trim()) ||
      /(?:评估|研判|分析|判断|帮我看).{0,40}(?:是否|有没有必要|专业|实训|培养)/s.test(request)) return true
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
