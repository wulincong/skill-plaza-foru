import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { extractFigures, preserveRegion } from '../../../.agents/skills/doc-translate/scripts/preserve-figures.mjs'

const available = ['xelatex', 'pdfinfo', 'pdftohtml', 'pdftoppm', 'pdftotext', 'pdfimages'].every(tool => !spawnSync(tool, [tool === 'xelatex' ? '--version' : '-v']).error)
function run(tool, args) {
  const result = spawnSync(tool, args, { encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr + result.stdout)
  return result.stdout
}
function source(t) {
  const previous = process.cwd()
  const directory = mkdtempSync(join(tmpdir(), 'plaza-figures-'))
  process.chdir(directory)
  t.after(() => { process.chdir(previous); rmSync(directory, { recursive: true, force: true }) })
  writeFileSync('pixels.png', Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGO4o6GhsSCAQSPg0v///wEkRAaMh9XknAAAAABJRU5ErkJggg==', 'base64'))
  writeFileSync('source.tex', String.raw`\documentclass{article}
\usepackage[a4paper,margin=25mm]{geometry}
\usepackage{graphicx}
\begin{document}
\section*{Raster source}
The original raster image below has four colors. Preserve its visual content and translate its caption.
\begin{figure}[h]\centering\includegraphics[width=80bp]{pixels.png}\caption{Raster result.}\end{figure}
\newpage
\section*{Vector source heading}
The source contains a vector diagram with a visible label. Preserve the lines and label in the translated document.
\begin{figure}[h]\centering\setlength{\unitlength}{1bp}\begin{picture}(200,70)\put(0,0){\framebox(200,70){VECTOR LABEL}}\end{picture}\caption{Vector workflow.}\end{figure}
\end{document}`)
  run('xelatex', ['-interaction=nonstopmode', '-halt-on-error', 'source.tex'])
  return directory
}

test('extracts original bitmap bytes, coordinates, page sizes and vector caption candidates', { skip: !available }, t => {
  source(t)
  const result = extractFigures('source.pdf')
  const manifest = JSON.parse(readFileSync(result.manifest, 'utf8'))
  assert.equal(result.imageCount, 1)
  assert.equal(manifest.pages.length, 2)
  assert.equal(manifest.pages[1].imageCount, 0)
  assert.match(manifest.pages[1].captions[0].text, /Vector workflow/)
  assert.ok(manifest.pages[0].heightPt > 841)
  assert.ok(manifest.images[0].bboxPt.every(Number.isFinite))
  assert.match(manifest.images[0].nearbyText.join(' '), /Raster result/)
  const original = readFileSync('pixels.png')
  const extracted = readFileSync(manifest.images[0].file)
  assert.equal(extracted.readUInt32BE(16), original.readUInt32BE(16))
  assert.equal(extracted.readUInt32BE(20), original.readUInt32BE(20))
})

test('preserved bitmap and clipped vector compile into a standalone PDF with visible figure text', { skip: !available }, t => {
  source(t)
  extractFigures('source.pdf')
  const manifest = JSON.parse(readFileSync('figures/manifest.json', 'utf8'))
  const caption = manifest.pages[1].captions[0]
  const region = preserveRegion('figures/manifest.json', { page: 2, box: [100, caption.top - 95, 390, 85] })
  assert.equal(region.method, 'pdf-clip')
  assert.ok(readFileSync(region.preview).length > 100)
  writeFileSync('translated.tex', String.raw`\documentclass{article}\usepackage{graphicx}\begin{document}` + manifest.images[0].latex + '\n' + region.latex + String.raw`\par Translated caption.\end{document}`)
  run('xelatex', ['-interaction=nonstopmode', '-halt-on-error', 'translated.tex'])
  const text = run('pdftotext', ['translated.pdf', '-'])
  assert.match(text, /VECTOR LABEL/)
  assert.match(text, /Translated caption/)
  // PDF clipping is visual: text extractors may still read off-clip source text.
  // Verify that the standalone PDF also renders successfully, rather than
  // treating pdftotext as a test of the graphic's visible bounds.
  run('pdftoppm', ['-f', '1', '-l', '1', '-singlefile', '-scale-to', '900', '-png', 'translated.pdf', 'rendered'])
  assert.equal(readFileSync('rendered.png').subarray(1, 4).toString(), 'PNG')
  assert.match(run('pdfimages', ['-list', 'translated.pdf']), /image/)
  // Original materials are no longer needed to read the generated PDF.
  rmSync('figures', { recursive: true })
  assert.match(run('pdftotext', ['translated.pdf', '-']), /VECTOR LABEL/)
})

test('page-range extraction is repeatable and rejects invalid crop coordinates or changed source', { skip: !available }, t => {
  source(t)
  assert.equal(extractFigures('source.pdf', { first: 1, last: 1 }).imageCount, 1)
  assert.equal(extractFigures('source.pdf', { first: 1, last: 1 }).imageCount, 1)
  assert.throws(() => preserveRegion('figures/manifest.json', { page: 2, box: [1, 1, 50, 50] }), /页码不在/)
  assert.throws(() => preserveRegion('figures/manifest.json', { page: 1, box: [-1, 1, 50, 50] }), /裁切框超出/)
  assert.throws(() => preserveRegion('figures/manifest.json', { page: 1, box: [0, 0, Infinity, 20] }), /有限数值/)
  assert.throws(() => extractFigures('source.pdf', { first: 3 }), /页码范围无效/)
  writeFileSync('figures/source.pdf', Buffer.concat([readFileSync('figures/source.pdf'), Buffer.from('\n')]))
  assert.throws(() => preserveRegion('figures/manifest.json', { page: 1, box: [1, 1, 50, 50] }), /原文文件已变化/)
})

test('spaces in source paths do not leak into generated image references', { skip: !available }, t => {
  source(t)
  mkdirSync('uploaded documents')
  writeFileSync('uploaded documents/原文 with spaces.pdf', readFileSync('source.pdf'))
  const result = extractFigures('uploaded documents/原文 with spaces.pdf')
  const manifest = JSON.parse(readFileSync(result.manifest, 'utf8'))
  assert.equal(manifest.sourcePdf, 'figures/source.pdf')
  assert.equal(manifest.images[0].file, 'figures/image-p001-01.png')
})
