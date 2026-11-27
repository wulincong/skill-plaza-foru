import { randomBytes, timingSafeEqual } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'

interface Options {
  env?: string
  appId?: string
  platformUrl?: string
  gatewayUrl?: string
  centerUrl?: string
  originAllowed: (origin: string) => boolean
  fetch?: typeof fetch
}

export function createUnifiedAuth(options: Options) {
  const test = options.env === 'test'
  const appId = options.appId || (test ? '3f363349005111ef808d0242ac110006' : 'dc8d609d021711ef8e910242ac120010')
  const platform = (options.platformUrl || (test ? 'http://192.168.8.2:19000' : 'http://192.168.8.1:18800')).replace(/\/$/, '')
  const gateway = (options.gatewayUrl || `${platform}/gateway`).replace(/\/$/, '')
  const center = (options.centerUrl || 'https://login.tringai.cn').replace(/\/$/, '')
  const upstream = options.fetch || fetch
  const cookieName = `plaza_auth_${test ? 'test' : 'prod'}`
  const transactionName = `${cookieName}_transaction`
  const transactions = new Map<string, { origin: string; path: string; expires: number }>()
  function cookie(req: IncomingMessage, name: string) {
    const value = req.headers.cookie?.split(';').map(c => c.trim()).find(c => c.startsWith(`${name}=`))?.slice(name.length + 1)
    try { return value ? decodeURIComponent(value) : '' } catch { return '' }
  }
  function setCookie(name: string, value: string, age: number, secure = false) {
    return `${name}=${encodeURIComponent(value)}; Path=/api/auth; HttpOnly; SameSite=Lax; Max-Age=${age}${secure ? '; Secure' : ''}`
  }
  function json(res: ServerResponse, status: number, data: unknown) {
    res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' }); res.end(JSON.stringify(data))
  }
  function redirect(res: ServerResponse, url: string) { res.writeHead(302, { Location: url }); res.end() }
  function validOrigin(raw: string, req: IncomingMessage) {
    try {
      const url = new URL(raw)
      return /^https?:$/.test(url.protocol) && url.origin === raw && url.host === req.headers.host?.toLowerCase() && options.originAllowed(raw)
    } catch { return false }
  }
  async function request(url: string, token?: string, body?: unknown) {
    const response = await upstream(url, {
      method: body ? 'POST' : 'GET', redirect: 'error', signal: AbortSignal.timeout(15_000),
      headers: { ...(token ? { token: `Bearer ${token}` } : {}), ...(body ? { 'Content-Type': 'application/json' } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
    })
    if (response.status === 401) throw new Error('unauthorized')
    const data = await response.json()
    if ([99, 301, 302, 303, 304, 305].includes(data.code)) throw new Error('unauthorized')
    if (!response.ok || ![0, 200].includes(data.code)) throw new Error('upstream')
    return data.data
  }
  async function profile(token: string) {
    const data = await request(`${gateway}/user/auth/users/view`, token)
    if (!data || typeof data !== 'object') throw new Error('upstream')
    return { id: String(data.id ?? data.userId ?? ''), nickname: String(data.nickname || data.realName || '用户'), phone: String(data.phone || data.mobile || ''), avatar: typeof data.userHead === 'string' && /^https?:\/\//.test(data.userHead) ? data.userHead : '' }
  }
  return async (req: IncomingMessage, res: ServerResponse) => {
    res.setHeader('Cache-Control', 'no-store')
    res.setHeader('Referrer-Policy', 'no-referrer')
    const url = new URL(req.url || '/', 'http://localhost')
    const action = url.pathname.slice('/api/auth/'.length)
    try {
      if (action === 'login' && req.method === 'GET') {
        const origin = url.searchParams.get('origin') || ''
        if (!validOrigin(origin, req)) { json(res, 403, { error: '登录来源未获准访问' }); return }
        for (const [key, item] of transactions) if (item.expires < Date.now()) transactions.delete(key)
        if (transactions.size >= 5000) { json(res, 503, { error: '请稍后重试' }); return }
        const rawPath = url.searchParams.get('returnTo') || '/'
        const destination = new URL(rawPath, origin)
        const path = rawPath.startsWith('/') && destination.origin === origin && !destination.pathname.startsWith('/api/') ? destination.pathname + destination.search + destination.hash : '/'
        const state = randomBytes(32).toString('hex')
        transactions.set(state, { origin, path, expires: Date.now() + 600_000 })
        const callback = new URL('/api/auth/callback', origin)
        callback.searchParams.set('state', state)
        const target = new URL(`${center}/login`)
        target.searchParams.set('app_id', appId)
        target.searchParams.set('redirect_url', callback.href)
        res.setHeader('Set-Cookie', setCookie(transactionName, state, 600, origin.startsWith('https:')))
        redirect(res, target.href); return
      }
      if (action === 'callback' && req.method === 'GET') {
        const state = url.searchParams.get('state') || ''
        const browserState = cookie(req, transactionName)
        const transaction = transactions.get(state)
        if (!transaction || transaction.expires < Date.now() || !/^[a-f0-9]{64}$/.test(browserState) || !/^[a-f0-9]{64}$/.test(state) || !timingSafeEqual(Buffer.from(state), Buffer.from(browserState))) {
          json(res, 400, { error: '登录已失效，请返回页面重新登录' }); return
        }
        transactions.delete(state)
        res.setHeader('Set-Cookie', setCookie(transactionName, '', 0))
        const ticket = url.searchParams.get('st')
        try {
          if (!ticket || ticket.length > 4096) throw new Error('ticket')
          const data = await request(`${platform}/api/oauth/anno/unionLogin`, undefined, { code: ticket, skipLoginCache: true })
          if (typeof data?.token !== 'string' || !data.token || data.token.length > 3000) throw new Error('token')
          await profile(data.token)
          res.setHeader('Set-Cookie', [setCookie(transactionName, '', 0), setCookie(cookieName, data.token, 86400, transaction.origin.startsWith('https:'))])
          redirect(res, transaction.origin + transaction.path)
        } catch {
          res.setHeader('Set-Cookie', [setCookie(transactionName, '', 0), setCookie(cookieName, '', 0)])
          redirect(res, `${transaction.origin}/?login_error=1${new URL(transaction.path, transaction.origin).hash}`)
        }
        return
      }
      if (action === 'me' && req.method === 'GET') {
        const token = cookie(req, cookieName)
        if (!token) { json(res, 401, { error: '尚未登录' }); return }
        try { json(res, 200, { user: await profile(token) }) }
        catch (error) {
          if (error instanceof Error && error.message === 'unauthorized') {
            res.setHeader('Set-Cookie', setCookie(cookieName, '', 0)); json(res, 401, { error: '登录已过期' })
          } else json(res, 502, { error: '暂时无法获取用户信息，请稍后刷新' })
        }
        return
      }
      if (action === 'logout' && req.method === 'POST') {
        const origin = req.headers.origin || ''
        if (!validOrigin(origin, req) || req.headers['x-plaza-auth'] !== '1') { json(res, 403, { error: '请求未获准访问' }); return }
        res.setHeader('Set-Cookie', setCookie(cookieName, '', 0))
        const target = new URL(`${center}/logout`)
        target.searchParams.set('redirect_url', `${origin}/`)
        json(res, 200, { url: target.href }); return
      }
      json(res, 404, { error: '接口不存在' })
    } catch { json(res, 502, { error: '登录服务暂不可用，请稍后重试' }) }
  }
}
