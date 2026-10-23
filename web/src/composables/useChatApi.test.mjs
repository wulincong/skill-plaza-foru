import assert from 'node:assert/strict'
import { test } from 'node:test'
import { streamChat } from './useChatApi.ts'

const frame = event => `data: ${JSON.stringify(event)}\n\n`

function mockStream(t, chunks) {
  t.mock.method(globalThis, 'fetch', async () => new Response(new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(new TextEncoder().encode(chunk))
      controller.close()
    },
  })))
}

const request = onEvent => ({ skill: 'doc-translate', messages: [{ role: 'user', content: '翻译为中文' }], onEvent })

test('fragmented SSE delivers the real PDF link and skips malformed JSON', async t => {
  const events = []
  const data = frame({ type: 'text', delta: '完成' }) + 'data: invalid\n\n'
    + frame({ type: 'done', content: '译文已生成', reportUrl: '/api/reports/real' })
  mockStream(t, [data.slice(0, 9), data.slice(9, 40), data.slice(40)])
  await streamChat(request(event => events.push(event)))
  assert.equal(events.length, 2)
  assert.equal(events[1].reportUrl, '/api/reports/real')
})

test('SSE error propagates even without an error handler', async t => {
  mockStream(t, [frame({ type: 'error', message: '编译失败' })])
  await assert.rejects(streamChat(request(() => {})), /编译失败/)
})

test('callback errors are not swallowed as JSON errors', async t => {
  mockStream(t, [frame({ type: 'error', message: '服务失败' })])
  await assert.rejects(streamChat(request(() => { throw new Error('用户可见错误') })), /用户可见错误/)
})

test('disconnect before done is a failure even after partial text', async t => {
  mockStream(t, [frame({ type: 'text', delta: '正在翻译' })])
  await assert.rejects(streamChat(request(() => {})), /连接提前断开/)
})

test('HTTP rejection preserves the backend reason', async t => {
  t.mock.method(globalThis, 'fetch', async () => Response.json({ error: '未知的 skill' }, { status: 400 }))
  await assert.rejects(streamChat(request(() => {})), /未知的 skill/)
})
