#!/usr/bin/env node
/* ============================================================
   PDF 宏结构探测（doc-translate 技能配套）
   ------------------------------------------------------------
   输出译文重排所需的三个宏观参数：纸张尺寸、页数、单双栏，
   外加文本量线索（识别扫描件）。只依赖 poppler（pdfinfo /
   pdftotext），在广场沙箱用户可达的系统路径上。

   用法：node detect-layout.mjs <file.pdf>
   输出：单行 JSON（stdout），失败时 stderr 说明并以非零码退出。
   ============================================================ */

import { spawnSync } from 'node:child_process'
import { statSync } from 'node:fs'

const pdf = process.argv[2]
if (!pdf) {
  console.error('用法：node detect-layout.mjs <file.pdf>')
  process.exit(2)
}
try {
  statSync(pdf)
} catch {
  console.error(`文件不存在或不可读：${pdf}`)
  process.exit(2)
}

function run(tool, args) {
  const r = spawnSync(tool, args, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 })
  if (r.error || r.status !== 0) {
    console.error(`${tool} 执行失败：${r.error?.message ?? `exit ${r.status}`}`)
    process.exit(1)
  }
  return r.stdout
}

/* ---- pdfinfo：页数 + 纸张尺寸（poppler 直接标注标准纸名） ---- */
const info = run('pdfinfo', [pdf])
const pages = Number((info.match(/^Pages:\s+(\d+)$/m) || [])[1] ?? 0)
const sizeMatch = info.match(/^Page size:\s+([\d.]+)\s*x\s*([\d.]+)\s*pts(?:\s+\((.+)\))?/m)
const widthPt = sizeMatch ? Number(sizeMatch[1]) : 0
const heightPt = sizeMatch ? Number(sizeMatch[2]) : 0
let paperLabel = sizeMatch?.[3] ?? ''
if (!paperLabel && widthPt && heightPt) paperLabel = `custom ${widthPt}x${heightPt}pt`

/* ---- 纯文本量：扫描件判定线索 ---- */
const plainText = run('pdftotext', [pdf, '-'])
const textChars = plainText.replace(/\s+/g, '').length

/* ---- bbox 布局：按行坐标判别单双栏 ----
   判据：取每页文本行（<line>）中心点与页宽中线比较。栏间隙可能很窄
   （LaTeX 默认 columnsep 约 10pt），按行端点判会漏；按行中心归类：
   双栏页的行聚在中线两侧、居中行很少（标题/跨栏行除外）；单栏页
   大量行的中心恰在中线附近。只统计文本行 ≥ 8 的页面（跳过封面/插图页），
   按多数表决。 */
const bbox = run('pdftotext', ['-bbox-layout', pdf, '-'])
let twoColumnPages = 0
let sampledPages = 0
const pageRe = /<page width="([\d.]+)"[^>]*>([\s\S]*?)<\/page>/g
let m
while ((m = pageRe.exec(bbox)) !== null) {
  const width = Number(m[1])
  const lines = [...m[2].matchAll(/<line xMin="([\d.]+)"[^>]*xMax="([\d.]+)"/g)]
  if (lines.length < 8) continue
  sampledPages++
  const center = width / 2
  let left = 0
  let right = 0
  let mid = 0
  for (const l of lines) {
    const lineCenter = (Number(l[1]) + Number(l[2])) / 2
    if (lineCenter < center - 6) left++
    else if (lineCenter > center + 6) right++
    else mid++
  }
  if (left >= 4 && right >= 4 && mid <= Math.max(3, 0.2 * (left + right + mid))) twoColumnPages++
}
const columns = sampledPages > 0 && twoColumnPages >= Math.ceil(sampledPages / 2) ? 2 : 1

const out = {
  file: pdf,
  bytes: statSync(pdf).size,
  pages,
  paper: { label: paperLabel, widthPt, heightPt },
  columns,
  twoColumnPages,
  sampledPages,
  textChars,
  charsPerPage: pages > 0 ? Math.round(textChars / pages) : 0,
  likelyScanned: pages > 0 && textChars / pages < 100,
}
console.log(JSON.stringify(out))
