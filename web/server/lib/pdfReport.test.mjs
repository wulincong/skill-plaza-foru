import assert from 'node:assert/strict'
import { mkdtempSync, rmSync, writeFileSync, symlinkSync, truncateSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { MAX_PDF_REPORT_BYTES, readWorkspacePdfReport, workspacePdfFingerprint } from './pdfReport.ts'

function workspace(t) {
  const dir = mkdtempSync(join(tmpdir(), 'plaza-pdf-report-'))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  return dir
}

// A real one-page PDF; validation uses the same Poppler dependency as production.
function pdf(text = 'Hello') {
  const stream = `BT /F1 12 Tf 50 750 Td (${text}) Tj ET`
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    `<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}\nendstream`,
  ]
  let data = '%PDF-1.4\n'
  const offsets = [0]
  objects.forEach((object, i) => {
    offsets.push(Buffer.byteLength(data))
    data += `${i + 1} 0 obj\n${object}\nendobj\n`
  })
  const xref = Buffer.byteLength(data)
  data += `xref\n0 6\n0000000000 65535 f \n${offsets.slice(1).map(offset => `${String(offset).padStart(10, '0')} 00000 n \n`).join('')}`
  return data + `trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`
}

test('new valid PDF is accepted with its page count', t => {
  const dir = workspace(t)
  writeFileSync(join(dir, 'translation.pdf'), pdf())
  const report = readWorkspacePdfReport(dir)
  assert.equal(report.found, true)
  assert.equal(report.pages, 1)
})

test('unchanged previous translation is rejected; rewritten translation is accepted', t => {
  const dir = workspace(t)
  const file = join(dir, 'translation.pdf')
  writeFileSync(file, pdf())
  const before = workspacePdfFingerprint(dir)
  assert.match(readWorkspacePdfReport(dir, before).error, /本轮未生成/)
  writeFileSync(file, pdf('New translation'))
  assert.equal(readWorkspacePdfReport(dir, before).found, true)
})

test('missing, empty and invalid PDFs are not delivered', t => {
  const dir = workspace(t)
  assert.equal(readWorkspacePdfReport(dir).found, false)
  writeFileSync(join(dir, 'translation.pdf'), '')
  assert.match(readWorkspacePdfReport(dir).error, /为空/)
  writeFileSync(join(dir, 'translation.pdf'), 'not a PDF')
  assert.match(readWorkspacePdfReport(dir).error, /无效/)
})

test('symlinks and oversized files are rejected before pdfinfo', t => {
  const dir = workspace(t)
  const outside = workspace(t)
  const file = join(dir, 'translation.pdf')
  writeFileSync(join(outside, 'source.pdf'), pdf())
  symlinkSync(join(outside, 'source.pdf'), file)
  assert.match(readWorkspacePdfReport(dir).error, /不是普通文件/)
  rmSync(file)
  writeFileSync(file, '')
  truncateSync(file, MAX_PDF_REPORT_BYTES + 1)
  assert.match(readWorkspacePdfReport(dir).error, /超过/)
})
