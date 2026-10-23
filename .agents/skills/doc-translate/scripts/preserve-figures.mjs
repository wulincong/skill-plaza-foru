#!/usr/bin/env node
/** Preserve embedded images and clipped PDF figures without OCR or redrawing. */
import { spawnSync } from 'node:child_process'
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { dirname, extname, join, relative, resolve, sep } from 'node:path'
import { pathToFileURL } from 'node:url'

const MAX_XML_BYTES = 64 * 1024 * 1024
function run(tool, args) {
  const result = spawnSync(tool, args, {
    encoding: 'utf8', timeout: 60_000, maxBuffer: MAX_XML_BYTES,
    env: { ...process.env, LC_ALL: 'C' },
  })
  if (result.error || result.status !== 0) {
    throw new Error(`${tool} 失败：${result.error?.message ?? result.stderr.trim().slice(0, 600) ?? result.status}`)
  }
  return result.stdout
}

function decodeXml(value) {
  const named = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'" }
  return value.replace(/&(#x[\da-f]+|#\d+|amp|lt|gt|quot|apos);/gi, (_, entity) => {
    if (!entity.startsWith('#')) return named[entity.toLowerCase()]
    const number = entity[1].toLowerCase() === 'x' ? parseInt(entity.slice(2), 16) : Number(entity.slice(1))
    return number <= 0x10ffff ? String.fromCodePoint(number) : ''
  })
}
function attributes(value) {
  return Object.fromEntries([...value.matchAll(/([\w-]+)="([^"]*)"/g)].map(match => [match[1], decodeXml(match[2])]))
}
function localPath(file) {
  const path = relative(process.cwd(), file).split(sep).join('/')
  if (!path || /[{}\r\n]/.test(path)) throw new Error('图片路径不能包含花括号或换行')
  return path
}
function includeGraphic(file, options = '') {
  return `\\includegraphics[${options}width=\\linewidth,height=0.7\\textheight,keepaspectratio]{\\detokenize{${localPath(file)}}}`
}

export function extractFigures(pdf, { outDir = 'figures', first = 1, last } = {}) {
  const input = resolve(pdf)
  if (!statSync(input).isFile()) throw new Error('原文不是普通文件')
  const summary = run('pdfinfo', [input])
  if (/^Encrypted:\s+yes/im.test(summary)) throw new Error('当前不支持加密 PDF')
  const count = Number(summary.match(/^Pages:\s+(\d+)/m)?.[1])
  last ??= count
  if (!Number.isInteger(first) || !Number.isInteger(last) || first < 1 || last < first || last > count) throw new Error('页码范围无效')
  const directory = resolve(outDir)
  mkdirSync(directory, { recursive: true })
  const temporary = mkdtempSync(join(directory, '.extract-'))
  const sourceFile = join(directory, 'source.pdf')
  try {
    if (input !== sourceFile) copyFileSync(input, sourceFile)
    const xmlFile = join(temporary, 'layout.xml')
    run('pdftohtml', ['-q', '-xml', '-hidden', '-nomerge', '-zoom', '1', '-noroundcoord', '-enc', 'UTF-8', '-f', String(first), '-l', String(last), sourceFile, xmlFile])
    if (statSync(xmlFile).size > MAX_XML_BYTES) throw new Error('PDF 布局信息过大，请按页码分批提取')
    const xml = readFileSync(xmlFile, 'utf8')
    const info = run('pdfinfo', ['-f', String(first), '-l', String(last), sourceFile])
    const sizes = new Map([...info.matchAll(/^Page\s+(\d+) size:\s+([\d.]+) x ([\d.]+) pts/gm)].map(match => [Number(match[1]), [Number(match[2]), Number(match[3])]]))
    const rotations = new Map([...info.matchAll(/^Page\s+(\d+) rot:\s+(\d+)/gm)].map(match => [Number(match[1]), Number(match[2])]))
    const pages = []
    const images = []
    for (const pageMatch of xml.matchAll(/<page\b([^>]*)>([\s\S]*?)<\/page>/g)) {
      const pageAttrs = attributes(pageMatch[1])
      const page = Number(pageAttrs.number)
      const body = pageMatch[2]
      const rotation = rotations.get(page) ?? 0
      let [widthPt, heightPt] = sizes.get(page) ?? [Number(pageAttrs.width), Number(pageAttrs.height)]
      if (rotation % 180 !== 0) [widthPt, heightPt] = [heightPt, widthPt]
      const text = [...body.matchAll(/<text\b([^>]*)>([\s\S]*?)<\/text>/g)].map(match => {
        const attrs = attributes(match[1])
        return { text: decodeXml(match[2].replace(/<[^>]*>/g, '')).trim(), top: Number(attrs.top), left: Number(attrs.left), width: Number(attrs.width), height: Number(attrs.height) }
      })
      const pageImages = [...body.matchAll(/<image\b([^>]*)\/?\s*>/g)]
      for (const [index, imageMatch] of pageImages.entries()) {
        const attrs = attributes(imageMatch[1])
        const extracted = resolve(dirname(xmlFile), attrs.src)
        if (!extracted.startsWith(temporary + sep) || !existsSync(extracted)) throw new Error('图片提取路径无效')
        const extension = extname(extracted).toLowerCase()
        if (!['.png', '.jpg', '.jpeg'].includes(extension)) throw new Error(`不支持的图片格式：${extension}`)
        const id = `image-p${String(page).padStart(3, '0')}-${String(index + 1).padStart(2, '0')}`
        const destination = join(directory, id + extension)
        copyFileSync(extracted, destination)
        const bboxPt = [Number(attrs.left), Number(attrs.top), Number(attrs.width), Number(attrs.height)]
        const bottom = bboxPt[1] + bboxPt[3]
        images.push({ id, page, file: localPath(destination), bboxPt, latex: includeGraphic(destination), nearbyText: text.filter(block => block.top >= bottom - 2 && block.top <= bottom + 90).slice(0, 5).map(block => block.text) })
      }
      pages.push({ page, widthPt, heightPt, rotation, imageCount: pageImages.length, captions: text.filter(block => /^(?:fig(?:ure)?\.?\s*\d|图\s*[\d一二三四五六七八九十])/i.test(block.text)) })
    }
    const manifest = {
      version: 1, sourcePdf: localPath(sourceFile), sourceSha256: createHash('sha256').update(readFileSync(sourceFile)).digest('hex'),
      range: { first, last }, pages, images, regions: [],
      notes: ['images 仅列嵌入位图，不包含由线条/文字组成的矢量图；不能据此判定原文无图。', '根据页码、位置和图注将原图插回对应章节；图内文字保持原样。', '矢量图/多元素组合图用 region 模式生成原 PDF 裁切引用；先查看原页确认图形边界，框内不要包含正文或图注。'],
    }
    writeFileSync(join(directory, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n')
    return { manifest: localPath(join(directory, 'manifest.json')), imageCount: images.length, pages: pages.length, captionPages: pages.filter(page => page.captions.length).map(page => page.page), notes: manifest.notes }
  } finally {
    rmSync(temporary, { recursive: true, force: true })
  }
}

export function preserveRegion(manifestFile, { page, box }) {
  const manifestPath = resolve(manifestFile)
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'))
  const dimensions = manifest.pages.find(item => item.page === page)
  if (!dimensions) throw new Error('页码不在已提取范围内')
  if (!Array.isArray(box) || box.length !== 4 || box.some(value => !Number.isFinite(value))) throw new Error('裁切框必须是 x,y,width,height 四个有限数值（pt，左上角为原点）')
  const [x, y, width, height] = box
  if (x < 0 || y < 0 || width <= 0 || height <= 0 || x + width > dimensions.widthPt || y + height > dimensions.heightPt) throw new Error('裁切框超出页面或宽高无效')
  if (width * height * (200 / 72) ** 2 > 20_000_000) throw new Error('裁切区域过大，请缩小到图形范围')
  const source = resolve(manifest.sourcePdf)
  if (createHash('sha256').update(readFileSync(source)).digest('hex') !== manifest.sourceSha256) throw new Error('原文文件已变化，请重新提取图片')
  const id = `region-p${String(page).padStart(3, '0')}-${createHash('sha256').update(box.join(',')).digest('hex').slice(0, 8)}`
  const prefix = join(dirname(manifestPath), id)
  const scale = 200 / 72
  run('pdftoppm', ['-f', String(page), '-l', String(page), '-singlefile', '-r', '200', '-x', String(Math.floor(x * scale)), '-y', String(Math.floor(y * scale)), '-W', String(Math.ceil(width * scale)), '-H', String(Math.ceil(height * scale)), '-png', source, prefix])
  const trim = [x, dimensions.heightPt - y - height, dimensions.widthPt - x - width, y].map(value => `${value.toFixed(3)}bp`).join(' ')
  const region = {
    id, page, bboxPt: box, preview: localPath(prefix + '.png'),
    method: dimensions.rotation ? 'raster-crop' : 'pdf-clip',
    latex: dimensions.rotation ? includeGraphic(prefix + '.png') : includeGraphic(source, `page=${page},trim={${trim}},clip,`),
  }
  manifest.regions = [...(manifest.regions ?? []).filter(item => item.id !== id), region]
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n')
  return region
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try {
    const [mode, input, ...args] = process.argv.slice(2)
    const options = {}
    for (let i = 0; i < args.length; i += 2) {
      const key = args[i]
      const value = args[i + 1]
      if (value === undefined || !['--out-dir', '--first', '--last', '--page', '--box'].includes(key)) throw new Error(`无效参数：${key}`)
      if (key === '--out-dir') options.outDir = value
      else if (key === '--box') options.box = value.split(',').map(Number)
      else options[key.slice(2)] = Number(value)
    }
    if (!input || !['extract', 'region'].includes(mode)) throw new Error('用法：preserve-figures.mjs extract <原文.pdf> [--out-dir figures] [--first 1 --last 20]；或 region <manifest.json> --page N --box x,y,width,height')
    console.log(JSON.stringify(mode === 'extract' ? extractFigures(input, options) : preserveRegion(input, options)))
  } catch (error) {
    console.error(error.message)
    process.exitCode = 1
  }
}
