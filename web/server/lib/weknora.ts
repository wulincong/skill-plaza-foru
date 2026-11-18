/** The host owns upstream credentials; Pi receives a revocable, library-scoped route. */
import { randomBytes } from 'node:crypto'
import { spawn } from 'node:child_process'
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http'
import { appendFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { Readable } from 'node:stream'
import { pipeline } from 'node:stream/promises'

const root = fileURLToPath(new URL('../../../', import.meta.url))
const skill = join(root, '.agents/skills/weknora-retrieval')
const upstream = 'https://kb.tringai.cn/api/v1'
const identifier = /^[A-Za-z0-9_-]{1,128}$/
export const DEFAULT_LEARNING_KB = 'b627daef-d505-4f16-9ee9-76474a6e5bde'
interface Query { operation: string; kb: string; query?: string; document?: string; tag?: string; keyword?: string; page?: number }
interface Result { status: string; items?: Record<string, any>[]; message?: string; [key: string]: any }
interface Options {
  key: string; kbIds: string[]; storeDir: string; publicBase: string
  execute?: (query: Query, signal?: AbortSignal) => Promise<Result>
  requestFile?: string
  evidenceFile?: string
  fetchImpl?: typeof fetch
}
class QueryError extends Error {
  status: string
  constructor(status: string, message: string) { super(message); this.status = status }
}
const failure = (status: string, message: string): never => { throw new QueryError(status, message) }

function config() {
  let local: Record<string, string> = {}
  try {
    local = Object.fromEntries(readFileSync(join(skill, '.env'), 'utf8').split(/\r?\n/)
      .map(line => /^\s*(WEKNORA_API_KEY|WEKNORA_KB_IDS)\s*=\s*(.*?)\s*$/.exec(line))
      .filter(Boolean).map(m => [m![1], m![2].replace(/^['"]|['"]$/g, '')]))
  } catch (error: any) { if (error.code !== 'ENOENT') failure('configuration_error', '无法读取知识库凭据配置。') }
  const key = (process.env.WEKNORA_API_KEY ?? local.WEKNORA_API_KEY ?? '').trim()
  const kbIds = (process.env.LEARNING_KB_IDS || DEFAULT_LEARNING_KB).split(',').map(x => x.trim())
  const raw = process.env.WEKNORA_KB_IDS ?? local.WEKNORA_KB_IDS
  const whitelist = raw?.trim() ? raw.split(',').map(x => x.trim()) : undefined
  if (whitelist && kbIds.some(id => !whitelist.includes(id))) failure('configuration_error', '学习知识库超出配置的授权范围。')
  return { key, kbIds,
    storeDir: join(process.env.DELIVERIES_DIR || join(root, 'web/server/deliveries'), 'learning-materials'),
    publicBase: process.env.DELIVERY_PUBLIC_BASE_URL || `http://127.0.0.1:${process.env.PORT || 8767}` }
}

function validate(value: any, kbIds: string[]): Query {
  if (!value || !['tags', 'documents', 'search', 'chunks'].includes(value.operation)) failure('invalid_request', '不支持的知识库操作。')
  if (!identifier.test(value.kb || '') || !kbIds.includes(value.kb)) failure('forbidden', '知识库不在本会话授权范围内。')
  if (Object.keys(value).some(k => !['operation','kb','query','document','tag','keyword','page'].includes(k))) failure('invalid_request', '包含不支持的查询字段。')
  for (const key of ['document', 'tag']) if (value[key] !== undefined && (typeof value[key] !== 'string' || !identifier.test(value[key]))) failure('invalid_request', '文档或分类 ID 无效。')
  for (const key of ['query', 'keyword']) if (value[key] !== undefined && (typeof value[key] !== 'string' || !value[key].trim() || value[key].length > 2000)) failure('invalid_request', '查询文字需要 1 到 2000 个字符。')
  if (value.operation === 'search' && !value.query?.trim()) failure('invalid_request', '缺少检索问题。')
  if (value.operation === 'chunks' && !value.document) failure('invalid_request', '缺少文档 ID。')
  if (value.page !== undefined && (!Number.isSafeInteger(value.page) || value.page < 1 || value.page > 10000)) failure('invalid_request', '页码无效。')
  const supported: Record<string, string[]> = {tags:['keyword','page'],documents:['keyword','page','tag'],search:['query','document'],chunks:['document','page']}
  if (Object.keys(value).some(k => !['operation','kb',...supported[value.operation]].includes(k))) failure('invalid_request', '查询字段与操作不匹配。')
  return value
}

function pythonQuery(value: Query, key: string, kbIds: string[], signal?: AbortSignal): Promise<Result> {
  const args = [join(skill, 'scripts/retrieve.py'), value.operation, '--kb', value.kb]
  for (const field of ['query','document','tag','keyword','page'] as const) if (value[field] !== undefined) args.push('--' + field, String(value[field]))
  return new Promise((resolve, reject) => {
    const child = spawn('python3', args, {env: {...process.env, WEKNORA_API_KEY:key, WEKNORA_KB_IDS:kbIds.join(',')}, signal})
    let output = '', bytes = 0
    const timer = setTimeout(() => child.kill(), 90_000)
    child.stdout.on('data', chunk => { bytes += chunk.length; if (bytes > 4 * 1024 * 1024) child.kill(); else output += chunk })
    child.stderr.resume() // Never forward credential-bearing diagnostics.
    child.once('error', () => { clearTimeout(timer); reject(new Error('知识库查询进程无法启动。')) })
    child.once('close', code => {
      clearTimeout(timer)
      try {
        const result = JSON.parse(output)
        if (code !== 0 || !['ok','empty'].includes(result.status)) {
          const statuses = ['forbidden','unauthorized','not_found','configuration_error','invalid_request','unavailable']
          reject(new QueryError(statuses.includes(result.status) ? result.status : 'unavailable', '知识库查询未成功，请检查服务或授权。'))
        } else resolve(result)
      } catch { reject(new Error('知识库未返回有效结果。')) }
    })
  })
}

/** Only verified directory results can mint persistent document capabilities. */
export function createKnowledgeService(options: Options) {
  const {key, kbIds, storeDir} = options
  if (!key || !kbIds.length || kbIds.some(id => !identifier.test(id))) failure('configuration_error', '未配置有效的知识库凭据或范围。')
  const base = new URL(options.publicBase)
  if (!['http:','https:'].includes(base.protocol) || base.username || base.password || base.pathname !== '/' || base.search || base.hash) failure('configuration_error', '教材公开地址配置无效。')
  const executeQuery = options.execute || ((q, signal) => pythonQuery(q, key, kbIds, signal))
  return {
    kbIds,
    async execute(input: Query, signal?: AbortSignal): Promise<Result> {
      const query = validate(input, kbIds)
      let runId: string | undefined
      if (options.requestFile) {
        try {runId = JSON.parse(readFileSync(options.requestFile,'utf8')).runId} catch {}
      }
      let result: Result
      try {result = await executeQuery(query, signal)}
      catch (error) {
        if (options.evidenceFile) appendFileSync(options.evidenceFile, JSON.stringify({runId,operation:query.operation,kb:query.kb,at:new Date().toISOString(),result:{status:error instanceof QueryError ? error.status : 'unavailable'}})+'\n', {mode:0o640})
        throw error
      }
      if (!['ok','empty'].includes(result.status) || !Array.isArray(result.items)) failure('unavailable', '知识库返回格式无效。')
      for (const item of result.items!) {
        if (item.knowledge_base_id !== query.kb) failure('forbidden', '返回资料超出请求范围。')
        if (query.operation !== 'documents') continue
        if (typeof item.id !== 'string' || !identifier.test(item.id) || typeof item.title !== 'string') failure('unavailable', '文档元信息无效。')
        if (query.tag && item.tag_id !== query.tag) failure('forbidden', '返回文档超出分类范围。')
      }
      if (query.operation === 'documents') {
        mkdirSync(storeDir, {recursive:true, mode:0o700})
        for (const item of result.items!) {
          const token = randomBytes(24).toString('hex')
          writeFileSync(join(storeDir, token + '.json'), JSON.stringify({kb:query.kb,document:item.id,title:item.title}), {flag:'wx',mode:0o600})
          item.preview_url = `${base.origin}/api/learning-materials/${token}/preview`
          item.download_url = `${base.origin}/api/learning-materials/${token}/download`
        }
      }
      if (options.evidenceFile) appendFileSync(options.evidenceFile, JSON.stringify({runId,operation:query.operation,kb:query.kb,at:new Date().toISOString(),result})+'\n', {mode:0o640})
      return result
    },
    handleMaterial(req: IncomingMessage, res: ServerResponse): boolean {
      const path = (req.url || '').split('?')[0]
      if (!path.startsWith('/api/learning-materials/')) return false
      const match = /^\/api\/learning-materials\/([a-f0-9]{48})\/(preview|download)$/.exec(path)
      if (!match) { res.writeHead(404).end(); return true }
      if (!['GET','HEAD'].includes(req.method || '')) {res.writeHead(405, {Allow:'GET, HEAD'}).end();return true}
      let grant: {kb:string;document:string;title:string}
      try {
        grant = JSON.parse(readFileSync(join(storeDir,match[1]+'.json'),'utf8'))
        if (!kbIds.includes(grant.kb) || typeof grant.document !== 'string' || !identifier.test(grant.document) || typeof grant.title !== 'string') throw Error()
      } catch {res.writeHead(404).end();return true}
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), 60_000)
      res.once('close', () => {clearTimeout(timer);controller.abort()})
      void (async () => {
        try {
          const metadata = await (options.fetchImpl || fetch)(`${upstream}/knowledge/${grant.document}`, {
            headers:{'X-API-Key':key},redirect:'error',signal:controller.signal,
          })
          if (!metadata.ok) {
            await metadata.body?.cancel()
            res.writeHead([401,403,404].includes(metadata.status) ? metadata.status : 502).end('教材暂不可访问')
            return
          }
          const current = await metadata.json() as any
          if (current?.success !== true || current.data?.id !== grant.document || current.data?.knowledge_base_id !== grant.kb) {
            res.writeHead(403).end('教材不再属于获准知识库')
            return
          }
          const response = await (options.fetchImpl || fetch)(`${upstream}/knowledge/${grant.document}/${match[2]}`, {
            headers:{'X-API-Key':key},redirect:'error',signal:controller.signal,
          })
          if (!response.ok || !response.body) {
            await response.body?.cancel()
            res.writeHead([401,403,404].includes(response.status) ? response.status : 502).end('教材暂不可访问')
            return
          }
          const type = response.headers.get('content-type')?.split(';')[0] || 'application/octet-stream'
          const inline = match[2] === 'preview' && type === 'application/pdf'
          res.writeHead(200, {
            'Content-Type':inline ? type : 'application/octet-stream',
            'Content-Disposition':`${inline ? 'inline':'attachment'}; filename*=UTF-8''${encodeURIComponent(grant.title).replace(/'/g,'%27')}`,
            'X-Content-Type-Options':'nosniff','Cache-Control':'private, no-store','Referrer-Policy':'no-referrer',
            'Content-Security-Policy':"sandbox; default-src 'none'",
          })
          if (req.method === 'HEAD') {await response.body.cancel();res.end()}
          else await pipeline(Readable.fromWeb(response.body as any),res)
        } catch { if (!res.headersSent) res.writeHead(502);res.end('教材暂不可访问') }
        finally {clearTimeout(timer)}
      })()
      return true
    },
  }
}

export async function openKnowledgeRelay(workspace?: string, service = createKnowledgeService({...config(),evidenceFile:workspace ? join(workspace,'.weknora-evidence.jsonl') : undefined,requestFile:workspace ? join(workspace,'.learning-request.json') : undefined})) {
  const token = randomBytes(32).toString('hex')
  const server = createServer(async (req,res) => {
    if (req.method !== 'POST' || req.url !== '/' + token) {res.writeHead(404).end();return}
    const controller = new AbortController()
    res.once('close',()=>controller.abort())
    try {
      let bytes = 0, body = ''
      for await (const chunk of req) {
        bytes += chunk.length
        if (bytes > 16000) {res.writeHead(413).end();return}
        body += chunk
      }
      let value
      try {value=JSON.parse(body)} catch {failure('invalid_request','请求不是有效 JSON。')}
      const result = await service.execute(value,controller.signal)
      res.writeHead(200,{'Content-Type':'application/json'}).end(JSON.stringify(result))
    } catch (error) {
      const known=error instanceof QueryError
      const status=known ? error.status:'unavailable'
      const codes: Record<string,number>={invalid_request:400,forbidden:403,unauthorized:401,not_found:404,configuration_error:503}
      res.writeHead(codes[status] || 502,{'Content-Type':'application/json'}).end(JSON.stringify({status,message:known?error.message:'知识库服务暂不可用。'}))
    }
  })
  await new Promise<void>((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve)})
  server.unref()
  const url=`http://127.0.0.1:${(server.address() as {port:number}).port}/${token}`
  try {
    if(workspace)writeFileSync(join(workspace,'.weknora-runtime.json'),JSON.stringify({url,kbIds:service.kbIds}),{mode:0o640})
  } catch(error) {server.close();server.closeAllConnections();throw error}
  return {url,close(){server.close();server.closeAllConnections()}}
}

export function handleLearningMaterial(req: IncomingMessage, res: ServerResponse): boolean {
  if (!(req.url || '').startsWith('/api/learning-materials/')) return false
  try {return createKnowledgeService(config()).handleMaterial(req,res)}
  catch {res.writeHead(503).end('教材服务未配置');return true}
}
