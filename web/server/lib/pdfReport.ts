import { spawnSync } from 'node:child_process'
import { lstatSync, realpathSync } from 'node:fs'
import { join } from 'node:path'

export const MAX_PDF_REPORT_BYTES = 64 * 1024 * 1024

/** 记录本轮开始前的工件，避免把上一轮译文交付成新结果。 */
export function workspacePdfFingerprint(workspaceDir: string): string | undefined {
  try {
    const stat = lstatSync(join(workspaceDir, 'translation.pdf'), { bigint: true })
    return `${stat.ino}:${stat.size}:${stat.mtimeNs}:${stat.ctimeNs}`
  } catch {
    return undefined
  }
}

export type WorkspacePdfReport =
  | { found: true; file: string; pages: number; bytes: number }
  | { found: false; error?: string }

export function readWorkspacePdfReport(workspaceDir: string, previousFingerprint?: string): WorkspacePdfReport {
  try {
    const file = join(realpathSync(workspaceDir), 'translation.pdf')
    const stat = lstatSync(file)
    if (!stat.isFile()) return { found: false, error: '译文 PDF 不是普通文件' }
    if (previousFingerprint && workspacePdfFingerprint(workspaceDir) === previousFingerprint) {
      return { found: false, error: '本轮未生成新的译文 PDF' }
    }
    if (!stat.size || stat.size > MAX_PDF_REPORT_BYTES) {
      return { found: false, error: stat.size ? `译文 PDF 超过 ${MAX_PDF_REPORT_BYTES} 字节上限` : '译文 PDF 为空文件' }
    }
    const info = spawnSync('pdfinfo', [file], { encoding: 'utf8', timeout: 5000, maxBuffer: 1024 * 1024 })
    const pages = Number((info.stdout?.match(/^Pages:\s+(\d+)$/m) || [])[1] ?? 0)
    if (info.error || info.status !== 0 || !pages) {
      return { found: false, error: '译文 PDF 无效（pdfinfo 校验失败或超时）' }
    }
    return { found: true, file, pages, bytes: stat.size }
  } catch (exc: any) {
    return { found: false, error: exc?.code === 'ENOENT' ? undefined : exc?.message ?? String(exc) }
  }
}
