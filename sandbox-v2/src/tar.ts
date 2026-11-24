/* 只读解析 Docker 归档接口返回的 tar（ustar/PAX/GNU 长文件名），用于受信侧核对 /work 内容。 */

import { SandboxError } from './errors.ts'

export interface TarEntry {
  name: string
  type: 'file' | 'dir' | 'other'
  size: number
  data: Buffer
}

const BLOCK = 512

function numeric(field: Buffer): number {
  const copy = Buffer.from(field)
  if (copy[0] & 0x80) {
    /* GNU base-256：12 字节大端，最高位是标记；长度小于 2^64 时低 8 字节就是数值 */
    copy[0] &= 0x7f
    return Number(copy.readBigUInt64BE(4))
  }
  const text = copy.toString('utf8').replace(/\0[\s\S]*$/, '').trim()
  return text ? Number.parseInt(text, 8) : 0
}

function paxPath(data: Buffer): string | null {
  const text = data.toString('utf8')
  const match = /(?:^|\n)\d+ path=([^\n]*)\n/.exec(text)
  return match ? match[1] : null
}

function ustarName(header: Buffer): string {
  const name = header.subarray(0, 100).toString('utf8').replace(/\0[\s\S]*$/, '')
  const magic = header.subarray(257, 263).toString('utf8')
  if (magic.startsWith('ustar')) {
    const prefix = header.subarray(345, 500).toString('utf8').replace(/\0[\s\S]*$/, '')
    if (prefix) return `${prefix}/${name}`
  }
  return name
}

export function readTar(archive: Buffer, maxEntries = 20000): TarEntry[] {
  const entries: TarEntry[] = []
  let offset = 0
  let longName: string | null = null
  let pax: string | null = null
  while (offset + BLOCK <= archive.length) {
    const header = archive.subarray(offset, offset + BLOCK)
    if (header.every((byte) => byte === 0)) break
    const size = numeric(header.subarray(124, 136))
    if (!Number.isSafeInteger(size) || size < 0 || offset + BLOCK + size > archive.length) {
      throw new SandboxError('DOCKER_API', 'Docker 归档的 tar 头部长度非法')
    }
    const type = String.fromCharCode(header[156])
    const data = archive.subarray(offset + BLOCK, offset + BLOCK + size)
    offset += BLOCK + Math.ceil(size / BLOCK) * BLOCK
    if (type === 'x') {
      pax = paxPath(data) ?? pax
      continue
    }
    if (type === 'g') continue
    if (type === 'L') {
      longName = data.toString('utf8').replace(/\0+$/, '')
      continue
    }
    const raw = pax ?? longName ?? ustarName(header)
    pax = null
    longName = null
    const name = raw.replace(/^\.\//, '').replace(/\/$/, '')
    const kind = type === '5' ? 'dir' : type === '0' || type === '\0' ? 'file' : 'other'
    entries.push({ name, type: kind, size, data: kind === 'file' ? data : Buffer.alloc(0) })
    if (entries.length > maxEntries) throw new SandboxError('DOCKER_API', `Docker 归档条目超过 ${maxEntries} 个`)
  }
  return entries
}
