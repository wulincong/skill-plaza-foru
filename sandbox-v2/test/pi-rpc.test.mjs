import assert from 'node:assert/strict'
import { test } from 'node:test'
import { SandboxError } from '../src/errors.ts'
import { PiRpcChannel } from '../src/pi-rpc.ts'
import { FakeDuplex, tick } from './helpers.mjs'

test('只按 LF 分帧，容忍 CR，保留 U+2028/U+2029，跨块的多字节字符不损坏', async () => {
  const stream = new FakeDuplex()
  const channel = new PiRpcChannel(stream, { defaultTimeoutMs: 1000 })
  const first = channel.request({ type: 'get_state' })
  const second = channel.request({ type: 'get_available_models' })
  const text = '甲\u2028乙\u2029丙'
  const line = Buffer.from(`${JSON.stringify({ id: 1, type: 'response', command: 'get_state', success: true, data: { text } })}\r\n`)
  const cut = line.length - 6
  stream.pushOut(line.subarray(0, cut))
  await tick()
  stream.pushOut(line.subarray(cut))
  stream.pushOut('\n\nnot json\n')
  const other = Buffer.from(`${JSON.stringify({ id: 2, type: 'response', command: 'get_available_models', success: true, data: { models: [] } })}\n`)
  stream.pushOut(other.subarray(0, 9))
  stream.pushOut(other.subarray(9))
  assert.deepEqual(await first, { text })
  assert.deepEqual(await second, { models: [] })
  assert.deepEqual(stream.written, ['{"id":1,"type":"get_state"}\n', '{"id":2,"type":"get_available_models"}\n'])
  assert.equal(channel.stats.frames, 3)
  assert.equal(channel.stats.badLines, 1)
})

test('非响应记录与迟到响应交给事件回调', async () => {
  const stream = new FakeDuplex()
  const channel = new PiRpcChannel(stream)
  const events = []
  channel.onEvent = (event) => events.push(event)
  stream.pushOut('{"type":"agent_start"}\n{"type":"bash_execution_update","id":9,"delta":"x"}\n{"id":99,"type":"response","command":"late","success":true,"data":1}\n')
  await tick()
  assert.deepEqual(events.map((event) => event.type ?? 'response'), ['agent_start', 'bash_execution_update', 'response'])
})

test('命令失败按 RPC_COMMAND 拒绝并带出 Pi 的错误', async () => {
  const stream = new FakeDuplex()
  const channel = new PiRpcChannel(stream)
  const pending = channel.request({ type: 'set_model', provider: 'x', modelId: 'y' })
  stream.pushOut('{"id":1,"type":"response","command":"set_model","success":false,"error":"Model not found"}\n')
  await assert.rejects(pending, (error) => error instanceof SandboxError && error.code === 'RPC_COMMAND' && /set_model/.test(error.message) && /Model not found/.test(error.message))
})

test('超时按 RPC_TIMEOUT 拒绝，后续同名请求不受影响', async () => {
  const stream = new FakeDuplex()
  const channel = new PiRpcChannel(stream, { defaultTimeoutMs: 20 })
  await assert.rejects(channel.request({ type: 'get_state' }), (error) => error.code === 'RPC_TIMEOUT')
  const again = channel.request({ type: 'get_state' })
  stream.pushOut('{"id":2,"type":"response","command":"get_state","success":true,"data":{"sessionId":"s"}}\n')
  assert.deepEqual(await again, { sessionId: 's' })
})

test('输出流结束时未完成的请求被拒绝，通道关闭后不再接受请求', async () => {
  const stream = new FakeDuplex()
  const channel = new PiRpcChannel(stream)
  const pending = channel.request({ type: 'prompt', message: 'hi' })
  stream.endOut()
  await assert.rejects(pending, (error) => error.code === 'RPC_CLOSED' && /未完成/.test(error.message))
  assert.equal(await channel.closed, 'Pi 标准输出已结束')
  assert.equal(channel.isOpen, false)
  await assert.rejects(channel.request({ type: 'get_state' }), (error) => error.code === 'RPC_CLOSED')
})

test('超过帧上限的输出触发致命错误并关闭通道', async () => {
  for (const payload of [Buffer.alloc(80, 0x61), Buffer.concat([Buffer.alloc(65, 0x61), Buffer.from('\n')])]) {
    const stream = new FakeDuplex()
    const channel = new PiRpcChannel(stream, { maxFrameBytes: 64 })
    const fatal = []
    channel.onFatal = (error) => fatal.push(error.code)
    stream.pushOut(payload)
    await tick()
    assert.deepEqual(fatal, ['FRAME_TOO_LARGE'])
    assert.equal(channel.isOpen, false)
  }
})

test('恰好等于帧上限的记录可以正常解析', async () => {
  const stream = new FakeDuplex()
  const channel = new PiRpcChannel(stream)
  const line = `${JSON.stringify({ id: 1, type: 'response', command: 'get_state', success: true, data: { text: 'ok' } })}\n`
  const pending = channel.request({ type: 'get_state' })
  stream.pushOut(line.slice(0, line.length - 1))
  await tick()
  assert.equal(channel.isOpen, true)
  stream.pushOut('\n')
  assert.deepEqual(await pending, { text: 'ok' })
})

test('写入失败时请求被拒绝', async () => {
  const stream = new FakeDuplex()
  stream.write = async () => {
    throw new SandboxError('RPC_CLOSED', '连接已断开')
  }
  const channel = new PiRpcChannel(stream)
  await assert.rejects(channel.request({ type: 'get_state' }), (error) => error.code === 'RPC_CLOSED' && /连接已断开/.test(error.message))
})

test('bash 结果与 excludeFromContext 透传', async () => {
  const stream = new FakeDuplex()
  const channel = new PiRpcChannel(stream)
  const pending = channel.bash('echo hi', { excludeFromContext: true })
  assert.equal(stream.written[0], '{"id":1,"type":"bash","command":"echo hi","excludeFromContext":true}\n')
  stream.pushOut('{"id":1,"type":"response","command":"bash","success":true,"data":{"output":"hi\\n","exitCode":0,"cancelled":false,"truncated":false}}\n')
  assert.deepEqual(await pending, { output: 'hi\n', exitCode: 0, cancelled: false, truncated: false })
})
