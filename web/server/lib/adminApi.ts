import type { IncomingMessage, ServerResponse } from 'node:http'
import { AdminStore, InputError, SESSION_SECONDS, publicConfig } from './adminStore.ts'
import { listPlazaSkills } from './skills.ts'
import { readIndex } from './traceExport.ts'

type Send = (res: ServerResponse, status: number, body: unknown) => void
const failures = new Map<string, { count: number; until: number }>()

export async function handleAdmin(
  req: IncomingMessage,
  res: ServerResponse,
  seg: string[],
  store: AdminStore,
  send: Send,
  read: (req: IncomingMessage, limit: number) => Promise<Buffer>,
  runs: (req: IncomingMessage, res: ServerResponse, seg: string[]) => Promise<void>,
) {
  try {
    const path = seg.slice(2).join('/')
    const token = /(?:^|;\s*)plaza_admin=([a-f0-9]{64})(?:;|$)/.exec(req.headers.cookie || '')?.[1] ?? ''
    const username = token && store.username(token)
    const write = req.method !== 'GET'
    if (
      write &&
      (req.headers['x-plaza-admin'] !== '1' || !req.headers['content-type']?.startsWith('application/json'))
    ) {
      throw new InputError('需要同源后台请求', 403)
    }
    if (req.headers.origin && new URL(req.headers.origin).host !== req.headers.host)
      throw new InputError('后台仅允许同源访问', 403)
    const cookie = (value: string, age: number) => {
      const secure = req.headers.origin?.startsWith('https://') || req.headers['x-forwarded-proto'] === 'https'
      res.setHeader(
        'Set-Cookie',
        `plaza_admin=${value}; HttpOnly; SameSite=Strict; Path=/api/admin; Max-Age=${age}${secure ? '; Secure' : ''}`,
      )
    }
    const readInput = async () => {
      let body
      try {
        body = JSON.parse((await read(req, 8192)).toString('utf8'))
      } catch {
        throw new InputError('请求内容无效')
      }
      if (!body || typeof body !== 'object' || Array.isArray(body)) throw new InputError('请求内容无效')
      return body
    }
    if (path === 'login' && req.method === 'POST') {
      const ip = req.socket.remoteAddress ?? 'unknown'
      const now = Date.now()
      const fail = failures.get(ip)
      if (fail && fail.until > now && fail.count >= 8) throw new InputError('登录尝试过多，请在一分钟后重试', 429)
      const body = await readInput()
      if (!store.verify(body.username, body.password)) {
        failures.set(
          ip,
          fail && fail.until > now ? { ...fail, count: fail.count + 1 } : { count: 1, until: now + 60_000 },
        )
        throw new InputError('账号或密码不正确', 401)
      }
      failures.delete(ip)
      cookie(store.createSession(), SESSION_SECONDS)
      send(res, 200, { username: body.username })
      return
    }
    if (!username) throw new InputError('请登录管理后台', 401)
    if (seg[2] === 'runs') {
      await runs(req, res, ['api', 'runs', ...seg.slice(3)])
      return
    }
    if (path === 'state' && req.method === 'GET') {
      const records = readIndex()
      const since = Date.now() - 24 * 3600_000
      const today = records.filter((r) => Date.parse(r.ts) >= since)
      send(res, 200, {
        username,
        config: publicConfig(store.config),
        skills: listPlazaSkills(),
        stats: {
          total: records.length,
          last24h: today.length,
          successes: today.filter((r) => r.outcome === 'success').length,
        },
        deployment: {
          sandbox: process.env.PI_SANDBOX_USER || '',
          environment: process.env.PLAZA_ENV || 'prod',
          databaseConfigured: ['MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE'].every((key) =>
            Boolean(process.env[key]),
          ),
        },
      })
      return
    }
    if (req.method === 'POST' && path === 'logout') {
      store.logout(token)
      cookie('', 0)
      send(res, 200, { ok: true })
      return
    }
    if (req.method === 'POST' && path === 'password') {
      const body = await readInput()
      if (!store.verify(username, body.currentPassword)) throw new InputError('当前密码不正确')
      store.setAccount(username, body.password)
      cookie('', 0)
      send(res, 200, { ok: true })
      return
    }
    if (req.method === 'PUT' && ['skills', 'keys', 'settings'].includes(path)) {
      send(res, 200, store.save(path, await readInput()))
      return
    }
    throw new InputError('后台接口不存在', 404)
  } catch (error) {
    send(res, error instanceof InputError ? error.status : 500, {
      error: error instanceof InputError ? error.message : '后台操作失败，请检查服务后重试',
    })
  }
}
