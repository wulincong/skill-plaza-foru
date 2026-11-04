/** Persistent static websites and attachment downloads. No workspace is served. */
import {
  constants, closeSync, copyFileSync, fstatSync, lstatSync, mkdirSync, mkdtempSync, openSync,
  readFileSync, readdirSync, readSync, realpathSync, renameSync, rmSync, writeFileSync, writeSync,
  createReadStream,
} from 'node:fs'
import { randomBytes, createHash } from 'node:crypto'
import { dirname, extname, isAbsolute, join, sep } from 'node:path'
import type { IncomingMessage, ServerResponse } from 'node:http'

export interface DeliveryLink { name: string; url: string }
export interface DeliveryLinks { webLinks?: DeliveryLink[]; downloads?: DeliveryLink[] }
interface WebInput { name: string; directory: string; entry: string }
interface FileInput { name: string; path: string; sha256?: string }
export interface DeliveryManifest { web?: WebInput[]; files?: FileInput[] }
interface Metadata {
  web: Array<{ name: string; entry: string; paths: string[] }>
  files: Array<{ name: string; stored: string; filename: string }>
}
const MAX_BYTES = 256 * 1024 * 1024
const MAX_FILES = 2000
const ID = /^[a-f0-9]{32}$/
const forbidden = new Set(['internal', 'uploads', 'node_modules', '__pycache__'])

function parts(path: string): string[] {
  if (typeof path !== 'string' || !path || isAbsolute(path) || /[\\\x00-\x1f]/.test(path)) throw new Error('交付路径必须是工作区内的相对路径')
  const result = path.split('/')
  if (result.some(p => !p || p === '.' || p === '..' || p.startsWith('.') || forbidden.has(p))) throw new Error('交付路径包含非公开目录或无效路径段')
  return result
}

function checkedPath(root: string, path: string): string {
  let current = root
  for (const part of parts(path)) {
    current = join(current, part)
    if (lstatSync(current).isSymbolicLink()) throw new Error('交付文件不能使用符号链接')
  }
  if (!realpathSync(current).startsWith(realpathSync(root) + sep)) throw new Error('交付路径越界')
  return current
}

function label(value: string): string {
  if (typeof value !== 'string' || !value.trim() || value.length > 160 || /[\x00-\x1f]/.test(value)) throw new Error('交付名称无效')
  return value.trim()
}

/** Includes mtime: rewriting an unchanged manifest deliberately reissues the deliverables. */
export function deliveryFingerprint(workspace: string, filename = 'delivery.json'): string | undefined {
  const path = join(workspace, filename)
  try {
    const stat = lstatSync(path)
    if (!stat.isFile() || stat.size > 64 * 1024) return `invalid:${stat.ino}:${stat.mtimeMs}`
    return `${stat.ino}:${stat.mtimeMs}:${stat.ctimeMs}:${createHash('sha256').update(readFileSync(path)).digest('hex')}`
  } catch (error: any) {
    // A permission error is a failed declaration, not an absent deliverable.
    return error?.code === 'ENOENT' ? undefined : `unreadable:${error?.code || 'UNKNOWN'}`
  }
}

/** Undefined means no new declaration in this turn. Invalid declarations throw. */
export function readDeliveryManifest(workspace: string, previous?: string, filename = 'delivery.json'): DeliveryManifest | undefined {
  const fingerprint = deliveryFingerprint(workspace, filename)
  if (fingerprint?.startsWith('unreadable:')) throw new Error(`无法读取 delivery.json（${fingerprint.slice(11)}），请检查交付文件的共享组读取权限`)
  if (!fingerprint || fingerprint === previous) return undefined
  const path = checkedPath(workspace, filename)
  const stat = lstatSync(path)
  if (!stat.isFile() || stat.size > 64 * 1024) throw new Error('delivery.json 不是有效的小型清单')
  const manifest = JSON.parse(readFileSync(path, 'utf8'))
  if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest)) throw new Error('delivery.json 必须是对象')
  return manifest
}

/** Public origin comes from deployment config, then the already-validated browser Origin. */
export function deliveryBaseUrl(req: IncomingMessage): string {
  const browserOrigin = /^https?:\/\//i.test(req.headers.origin || '') ? req.headers.origin : undefined
  const value = process.env.DELIVERY_PUBLIC_BASE_URL || browserOrigin || `http://${req.headers.host || 'localhost:8767'}`
  const url = new URL(value)
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.pathname !== '/' || url.search || url.hash) throw new Error('DELIVERY_PUBLIC_BASE_URL 必须是完整 HTTP(S) origin')
  return url.origin
}

export function publishDelivery(workspace: string, manifest: DeliveryManifest, store: string, baseUrl: string, checkEntry?: (file: string) => void): DeliveryLinks {
  if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest)) throw new Error('delivery.json 必须是对象')
  const web = manifest.web ?? [], files = manifest.files ?? []
  if (!Array.isArray(web) || !Array.isArray(files) || web.length > 20 || files.length > 100 || web.length + files.length === 0) throw new Error('交付清单为空或超过数量上限')
  const metadata: Metadata = { web: [], files: [] }
  const copies: Array<{ source: string; target: string; size: number; ino: number; dev: number; sha256?: string }> = []
  let bytes = 0
  const add = (source: string, target: string, sha256?: string) => {
    const stat = lstatSync(source)
    if (!stat.isFile() || !stat.size) throw new Error('交付文件必须是非空普通文件')
    bytes += stat.size
    if (bytes > MAX_BYTES || copies.length >= MAX_FILES) throw new Error('交付超过 256MB 或 2000 文件上限')
    copies.push({ source, target, size: stat.size, ino: stat.ino, dev: stat.dev, sha256 })
  }
  web.forEach((item, i) => {
    const name = label(item.name)
    const directory = checkedPath(workspace, item.directory)
    if (!lstatSync(directory).isDirectory()) throw new Error('网页 directory 不是目录')
    parts(item.entry)
    if (!/\.html?$/i.test(item.entry)) throw new Error('网页入口必须是 HTML 文件')
    const paths: string[] = []
    const walk = (dir: string, prefix = '') => {
      for (const file of readdirSync(dir)) {
        const path = prefix + file
        const source = checkedPath(directory, path)
        const stat = lstatSync(source)
        if (stat.isDirectory()) walk(source, path + '/')
        else { add(source, `web/${i}/${path}`); paths.push(path) }
      }
    }
    walk(directory)
    if (!paths.includes(item.entry)) throw new Error('网页入口不存在')
    metadata.web.push({ name, entry: item.entry, paths })
  })
  files.forEach((item, i) => {
    const name = label(item.name)
    const source = checkedPath(workspace, item.path)
    const extension = extname(source).slice(0, 16)
    const stored = `${i}${extension}`
    add(source, `files/${stored}`, item.sha256)
    const clean = name.replace(/[\\/:*?"<>|]/g, '-').trim()
    const filename = clean.toLowerCase().endsWith(extension.toLowerCase()) ? clean : clean + extension
    metadata.files.push({ name, stored, filename })
  })
  const id = randomBytes(16).toString('hex')
  mkdirSync(store, { recursive: true, mode: 0o700 })
  const temporary = join(store, `.pending-${id}`)
  mkdirSync(temporary, { mode: 0o700 })
  try {
    for (const { source, target, size, ino, dev, sha256 } of copies) {
      // Open the checked inode, never follow a swapped leaf symlink.
      const original = lstatSync(source)
      if (original.size !== size || original.ino !== ino || original.dev !== dev) throw new Error('交付文件在收集期间发生变化')
      const input = openSync(source, constants.O_RDONLY | constants.O_NOFOLLOW)
      try {
        const stat = fstatSync(input)
        if (!stat.isFile() || stat.ino !== original.ino || stat.dev !== original.dev || stat.size !== original.size || !realpathSync(source).startsWith(realpathSync(workspace) + sep)) throw new Error('交付文件在收集期间发生变化')
        const destination = join(temporary, target)
        mkdirSync(dirname(destination), { recursive: true })
        const output = openSync(destination, 'wx', 0o600)
        try {
          const buffer = Buffer.alloc(64 * 1024)
          const digest = sha256 ? createHash('sha256') : undefined
          let copied = 0, count = 0
          while ((count = readSync(input, buffer, 0, buffer.length, null)) > 0) {
            digest?.update(buffer.subarray(0, count))
            copied += count
            if (copied > original.size) throw new Error('交付文件在收集期间发生变化')
            let written = 0
            while (written < count) written += writeSync(output, buffer, written, count - written)
          }
          if (digest && digest.digest('hex') !== sha256) throw new Error('交付文件与构建时核验的内容不一致')
          if (copied !== original.size || fstatSync(input).mtimeMs !== original.mtimeMs) throw new Error('交付文件在收集期间发生变化')
        } finally { closeSync(output) }
      } finally { closeSync(input) }
    }
    if (checkEntry) metadata.web.forEach((page, i) => checkEntry(join(temporary, 'web', String(i), page.entry)))
    writeFileSync(join(temporary, 'metadata.json'), JSON.stringify(metadata), { mode: 0o600 })
    renameSync(temporary, join(store, id))
  } catch (error) {
    rmSync(temporary, { recursive: true, force: true })
    throw error
  }
  return {
    webLinks: metadata.web.length ? metadata.web.map((item, i) => ({ name: item.name, url: `${baseUrl}/p/${id}/${i}/` })) : undefined,
    downloads: metadata.files.length ? metadata.files.map((item, i) => ({ name: item.name, url: `${baseUrl}/api/deliveries/${id}/files/${i}` })) : undefined,
  }
}

/** Adapter for already-validated, server-owned trace files. Never writes into agent directories. */
export function publishLegacyDelivery(html: string | undefined, pdf: string | undefined, name: string, store: string, baseUrl: string): DeliveryLinks {
  mkdirSync(store, { recursive: true, mode: 0o700 })
  const source = mkdtempSync(join(store, '.source-'))
  try {
    const manifest: DeliveryManifest = {}
    if (html) {
      mkdirSync(join(source, 'site'))
      copyFileSync(html, join(source, 'site/index.html'))
      manifest.web = [{ name: name || '报告', directory: 'site', entry: 'index.html' }]
    }
    if (pdf) {
      copyFileSync(pdf, join(source, 'translation.pdf'))
      manifest.files = [{ name: '译文 PDF', path: 'translation.pdf' }]
    }
    return publishDelivery(source, manifest, store, baseUrl)
  } finally { rmSync(source, { recursive: true, force: true }) }
}

const mime: Record<string, string> = {
  '.html': 'text/html; charset=utf-8', '.htm': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.json': 'application/json',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml', '.gif': 'image/gif',
  '.webp': 'image/webp', '.ico': 'image/x-icon', '.woff': 'font/woff', '.woff2': 'font/woff2',
  '.pdf': 'application/pdf', '.zip': 'application/zip', '.txt': 'text/plain; charset=utf-8',
}
function notFound(res: ServerResponse) { res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }); res.end('交付资源不存在') }

/** Handles only /p and /api/deliveries. Sandboxed documents get an opaque origin. */
export function handleDelivery(req: IncomingMessage, res: ServerResponse, store: string): boolean {
  const rawPath = (req.url || '/').split('?')[0]
  if (!rawPath.startsWith('/p/') && !rawPath.startsWith('/api/deliveries/')) return false
  try {
    if (!['GET', 'HEAD'].includes(req.method || '')) { res.writeHead(405, { Allow: 'GET, HEAD' }); res.end(); return true }
    const path = decodeURIComponent(rawPath)
    if (/[\\\x00-\x1f]/.test(path)) throw new Error('path')
    const match = path.match(/^\/p\/([a-f0-9]{32})\/(\d+)(?:\/(.*))?$/)
    const download = path.match(/^\/api\/deliveries\/([a-f0-9]{32})\/files\/(\d+)$/)
    if (!match && !download) { notFound(res); return true }
    const [, id, index] = (match || download)!
    if (!ID.test(id)) throw new Error('id')
    const root = join(store, id)
    const metadata: Metadata = JSON.parse(readFileSync(join(root, 'metadata.json'), 'utf8'))
    let file: string, headers: Record<string, string> = { 'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, max-age=3600', 'Referrer-Policy': 'no-referrer' }
    if (match) {
      const item = metadata.web[Number(index)]
      if (!item) throw new Error('web')
      const requested = match[3]
      if (!requested) {
        res.writeHead(302, { Location: `/p/${id}/${index}/${item.entry.split('/').map(encodeURIComponent).join('/')}`, 'Cache-Control': 'no-store' })
        res.end(); return true
      }
      parts(requested)
      if (!item.paths.includes(requested)) throw new Error('file')
      file = checkedPath(root, `web/${index}/${requested}`)
      // No same-origin permission, popups, forms, workers, or app API connections.
      const base = deliveryBaseUrl(req)
      headers = { ...headers,
        'Content-Security-Policy': `sandbox allow-scripts; default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; media-src 'self'; connect-src ${base}/p/; base-uri 'none'; form-action 'none'; object-src 'none'; frame-src 'none'; worker-src 'none'`,
        'Access-Control-Allow-Origin': '*', // Static assets only, supports fetch/fonts from opaque origin.
      }
    } else {
      const item = metadata.files[Number(index)]
      if (!item) throw new Error('file')
      file = checkedPath(root, `files/${item.stored}`)
      const encoded = encodeURIComponent(item.filename).replace(/['()*]/g, c => '%' + c.charCodeAt(0).toString(16))
      headers['Content-Disposition'] = `attachment; filename="download${extname(item.stored).replace(/[^.a-z0-9]/gi, '')}"; filename*=UTF-8''${encoded}`
      headers['Content-Security-Policy'] = "sandbox; default-src 'none'"
    }
    const stat = lstatSync(file)
    if (!stat.isFile()) throw new Error('file')
    res.writeHead(200, { ...headers, 'Content-Type': mime[extname(file).toLowerCase()] || 'application/octet-stream', 'Content-Length': stat.size })
    if (req.method === 'HEAD') res.end()
    else createReadStream(file).on('error', () => res.destroy()).pipe(res)
  } catch { if (!res.headersSent) notFound(res); else res.destroy() }
  return true
}
