import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { createServer } from 'node:http'
import { test } from 'node:test'
import { openModelRelay } from './modelRelay.ts'

test('managed keys are pinned to separate Pi routes and never returned by the relay', async t => {
  const keys = [randomBytes(20).toString('hex'), randomBytes(20).toString('hex')]
  const received = []
  const upstream = createServer(async (req, res) => {
    let message = ''
    for await (const chunk of req) message += chunk
    received.push({ path: req.url, authorization: req.headers.authorization, message })
    if (message === 'reject') {
      res.writeHead(401).end(req.headers.authorization)
      return
    }
    res.writeHead(200, { 'Content-Type': 'text/event-stream' }).end('data: [DONE]\n\n')
  })
  await new Promise(resolve => upstream.listen(0, '127.0.0.1', resolve))
  t.after(() => { upstream.close(); upstream.closeAllConnections() })
  const original = process.env.ADMIN_DEEPSEEK_UPSTREAM
  process.env.ADMIN_DEEPSEEK_UPSTREAM = `http://127.0.0.1:${upstream.address().port}/v1`
  t.after(() => {
    if (original === undefined) delete process.env.ADMIN_DEEPSEEK_UPSTREAM
    else process.env.ADMIN_DEEPSEEK_UPSTREAM = original
  })
  const routes = await Promise.all(keys.map(openModelRelay))
  t.after(() => routes.forEach(route => route.close()))
  for (const [i, route] of routes.entries()) {
    const post = body => fetch(route.url + '/chat/completions', {
      method: 'POST', headers: { Authorization: 'Bearer ignored' }, body,
    })
    const response = await post('complete')
    assert.equal(await response.text(), 'data: [DONE]\n\n')
    assert.deepEqual(received.at(-1), {
      path: '/v1/chat/completions', authorization: 'Bearer ' + keys[i], message: 'complete',
    })
    const denied = await post('reject')
    assert.equal(denied.status, 401)
    assert.equal((await denied.text()).includes(keys[i]), false)
    assert.equal((await fetch(route.url + '/models', { method: 'POST' })).status, 404)
  }
})
