import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer, request as httpRequest } from 'node:http'
import { createUnifiedAuth } from './unifiedAuth.ts'

// Use raw HTTP so proxy-preserved Host can be exercised (fetch overrides Host).
function fetch(url, options = {}) {
  return new Promise((resolve, reject) => {
    const req = httpRequest(url, { method: options.method || 'GET', headers: options.headers }, res => {
      const chunks = []
      res.on('data', c => chunks.push(c))
      res.on('end', () => {
        const headers = new Headers()
        for (let i = 0; i < res.rawHeaders.length; i += 2) headers.append(res.rawHeaders[i], res.rawHeaders[i + 1])
        resolve(new Response(Buffer.concat(chunks), { status: res.statusCode, headers }))
      })
    })
    req.on('error', reject)
    req.end()
  })
}

test('统一登录：事务绑定、换票、资料恢复和退出', async () => {
  const calls = []
  const handler = createUnifiedAuth({ env: 'test', originAllowed: o => o === 'http://plaza.test', fetch: async (url, options) => {
    calls.push([String(url), options])
    return Response.json(String(url).endsWith('unionLogin')
      ? { code: 0, data: { token: 'real-token' } }
      : { code: 200, data: { id: 'u1', nickname: '张老师', userHead: 'https://example.com/a.png' } })
  } })
  const server = createServer((req, res) => { void handler(req, res) })
  await new Promise(r => server.listen(0, '127.0.0.1', r))
  const base = `http://127.0.0.1:${server.address().port}/api/auth`
  try {
    assert.equal((await fetch(`${base}/login?origin=http://plaza.test`, { redirect: 'manual' })).status, 403)
    const start = await fetch(`${base}/login?origin=http://plaza.test&returnTo=${encodeURIComponent('/#/experience?skill=a&x=b')}`, { redirect: 'manual', headers: { host: 'plaza.test' } })
    assert.equal(start.status, 302)
    const login = new URL(start.headers.get('location'))
    assert.equal(login.searchParams.get('app_id'), '69543990ecb048a88f76ef9279e82fc5')
    const callback = new URL(login.searchParams.get('redirect_url'))
    assert.equal(callback.pathname, '/api/auth/callback')
    const transaction = start.headers.get('set-cookie').split(';')[0]
    const callbackPath = `${base}/callback${callback.search}&st=one-use-ticket`
    assert.equal((await fetch(callbackPath, { redirect: 'manual' })).status, 400)
    const result = await fetch(callbackPath, { headers: { cookie: transaction }, redirect: 'manual' })
    assert.equal(result.status, 302)
    assert.equal(result.headers.get('location'), 'http://plaza.test/#/experience?skill=a&x=b')
    const cookies = result.headers.getSetCookie()
    const token = cookies.find(c => c.startsWith('plaza_auth_test='))
    assert.match(token, /HttpOnly/)
    assert.match(token, /SameSite=Lax/)
    assert.equal(JSON.parse(calls[0][1].body).code, 'one-use-ticket')
    assert.equal(JSON.parse(calls[0][1].body).skipLoginCache, true)
    const cookie = token.split(';')[0]
    const me = await fetch(`${base}/me`, { headers: { cookie } })
    assert.equal((await me.json()).user.nickname, '张老师')
    assert.equal(calls.at(-1)[1].headers.token, 'Bearer real-token')
    assert.equal((await fetch(callbackPath, { headers: { cookie: transaction }, redirect: 'manual' })).status, 400)
    assert.equal((await fetch(`${base}/me`)).status, 401)
    assert.equal((await fetch(`${base}/logout`, { method: 'POST' })).status, 403)
    const out = await fetch(`${base}/logout`, { method: 'POST', headers: { host: 'plaza.test', origin: 'http://plaza.test', 'x-plaza-auth': '1' } })
    assert.equal(out.status, 200)
    assert.match(out.headers.get('set-cookie'), /Max-Age=0/)
    assert.match((await out.json()).url, /login.tringai.cn\/logout/)
    assert.equal((await fetch(`${base}/login?origin=https://evil.test`, { redirect: 'manual' })).status, 403)
  } finally { server.closeAllConnections(); await new Promise(r => server.close(r)) }
})

test('正式配置、HTTPS Cookie、站外返回拦截和失效处理', async () => {
  let mode = 'success'
  const handler = createUnifiedAuth({ originAllowed: o => o === 'https://plaza.test', fetch: async (url) => {
    if (mode === 'network') throw new Error('unavailable')
    if (mode === 'http401') return new Response(null, { status: 401 })
    if (mode === 'expired') return Response.json({ code: 301 })
    return Response.json(String(url).endsWith('unionLogin') ? { code: 0, data: { token: 'valid-token' } } : { code: 200, data: { nickname: '真实用户' } })
  } })
  const server = createServer((req, res) => { void handler(req, res) })
  await new Promise(r => server.listen(0, '127.0.0.1', r))
  const base = `http://127.0.0.1:${server.address().port}/api/auth`
  try {
    const start = await fetch(`${base}/login?origin=https://plaza.test&returnTo=//evil.test`, { redirect: 'manual', headers: { host: 'plaza.test' } })
    assert.match(start.headers.get('set-cookie'), /; Secure/)
    const login = new URL(start.headers.get('location'))
    assert.equal(login.searchParams.get('app_id'), 'dc8d609d021711ef8e910242ac120010')
    const callback = new URL(login.searchParams.get('redirect_url'))
    const result = await fetch(`${base}/callback${callback.search}&st=ticket`, { headers: { cookie: start.headers.get('set-cookie').split(';')[0] }, redirect: 'manual' })
    assert.equal(result.headers.get('location'), 'https://plaza.test/')
    assert.match(result.headers.getSetCookie().find(c => c.startsWith('plaza_auth_prod=')), /; Secure/)
    mode = 'network'
    const unavailable = await fetch(`${base}/me`, { headers: { cookie: 'plaza_auth_prod=valid-token' } })
    assert.equal(unavailable.status, 502)
    assert.equal(unavailable.headers.get('set-cookie'), null)
    mode = 'expired'
    const expired = await fetch(`${base}/me`, { headers: { cookie: 'plaza_auth_prod=invalid-token' } })
    assert.equal(expired.status, 401)
    assert.match(expired.headers.get('set-cookie'), /Max-Age=0/)
    mode = 'http401'
    const rejected = await fetch(`${base}/me`, { headers: { cookie: 'plaza_auth_prod=invalid-token' } })
    assert.equal(rejected.status, 401)
    mode = 'expired'
    const again = await fetch(`${base}/login?origin=https://plaza.test`, { redirect: 'manual', headers: { host: 'plaza.test' } })
    const failedCallback = new URL(new URL(again.headers.get('location')).searchParams.get('redirect_url'))
    const failed = await fetch(`${base}/callback${failedCallback.search}&st=bad`, { headers: { cookie: again.headers.get('set-cookie').split(';')[0] }, redirect: 'manual' })
    assert.equal(failed.headers.get('location'), 'https://plaza.test/?login_error=1')
    assert.match(failed.headers.getSetCookie().find(c => c.startsWith('plaza_auth_prod=')), /Max-Age=0/)
  } finally { server.closeAllConnections(); await new Promise(r => server.close(r)) }
})
