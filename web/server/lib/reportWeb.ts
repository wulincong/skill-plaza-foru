/** Shared presentation checks; independent of report evidence and chapter contracts. */
import { readFileSync, statSync } from 'node:fs'
import { MAX_HTML_REPORT_BYTES, validateHtmlReport } from './htmlReport.ts'

/** Check the staged public page, where the platform CSP disallows nested documents. */
export function checkReportWebEntry(file: string): void {
  if (statSync(file).size > MAX_HTML_REPORT_BYTES) throw new Error('报告网页入口超过 8 MiB')
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
