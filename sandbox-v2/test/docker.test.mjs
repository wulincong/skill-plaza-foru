import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { test } from 'node:test'
import { AttachedStreams } from '../src/docker.ts'
import { tick } from './helpers.mjs'

class FakeSocket extends EventEmitter {
  constructor() {
    super()
    this.written = []
    this.writableLength = 0
    this.destroyed = false
    this.writableEnded = false
    this.pauses = 0
    this.resumes = 0
  }

  pause() {
    this.pauses++
  }

  resume() {
    this.resumes++
  }

  destroy() {
    this.destroyed = true
    this.emit('close')
  }

  end() {
    this.writableEnded = true
  }

  write(chunk) {
    this.written.push(chunk)
    return true
  }
}

const frame = (type, payload) => {
  const body = Buffer.from(payload)
  const head = Buffer.alloc(8)
  head[0] = type
  head.writeUInt32BE(body.length, 4)
  return Buffer.concat([head, body])
}

const collect = (stream) =>
  new Promise((resolve) => {
    const chunks = []
    stream.on('data', (chunk) => chunks.push(chunk))
    stream.on('end', () => resolve(Buffer.concat(chunks).toString()))
  })

test('按 Docker 分帧拆出 stdout 与 stderr', async () => {
  const socket = new FakeSocket()
  const streams = new AttachedStreams(socket, frame(1, 'in-head'))
  const out = collect(streams.stdout)
  const err = collect(streams.stderr)
  socket.emit('data', Buffer.concat([frame(1, 'out-1'), frame(2, 'err-1'), frame(1, 'out-2'), frame(2, 'err-2')]))
  socket.emit('data', Buffer.concat([frame(1, 'out-3'), frame(0, 'echo')]))
  socket.destroy()
  assert.equal(await out, 'in-headout-1out-2out-3echo')
  assert.equal(await err, 'err-1err-2')
})

test('一帧被拆到多个数据块时仍能完整还原', async () => {
  const socket = new FakeSocket()
  const streams = new AttachedStreams(socket, Buffer.alloc(0))
  const out = collect(streams.stdout)
  const whole = Buffer.concat([frame(1, 'split-me'), frame(2, 'e')])
  for (let index = 0; index < whole.length; index++) socket.emit('data', whole.subarray(index, index + 1))
  socket.destroy()
  assert.equal(await out, 'split-me')
})

test('连接关闭时两条流结束且 closed 兑现', async () => {
  const socket = new FakeSocket()
  const streams = new AttachedStreams(socket, Buffer.alloc(0))
  const out = collect(streams.stdout)
  socket.emit('data', frame(1, 'last'))
  socket.destroy()
  assert.equal(await out, 'last')
  await streams.closed
})

test('下游读得慢时暂停 socket，恢复读取后继续', async () => {
  const socket = new FakeSocket()
  const streams = new AttachedStreams(socket, Buffer.alloc(0))
  const big = Buffer.alloc(2048, 0x61)
  const count = 64
  socket.emit('data', Buffer.concat(Array.from({ length: count }, () => frame(1, big))))
  await tick()
  assert.ok(socket.pauses >= 1, '应在缓冲超过水位时暂停 socket')
  assert.equal(socket.destroyed, false)
  // 边读边恢复：消费者开始读取后 _read 被调用，socket 才会继续
  const received = await new Promise((resolve, reject) => {
    let total = 0
    streams.stdout.on('data', (chunk) => {
      total += chunk.length
      if (total === count * big.length) {
        socket.destroy()
        resolve(total)
      }
    })
    streams.stdout.on('error', reject)
  })
  assert.equal(received, count * big.length)
  assert.ok(socket.resumes >= 1)
})

test('连接销毁后不能再写', async () => {
  const socket = new FakeSocket()
  const streams = new AttachedStreams(socket, Buffer.alloc(0))
  await streams.write(Buffer.from('x'))
  assert.equal(socket.written.length, 1)
  socket.destroy()
  await assert.rejects(streams.write(Buffer.from('y')), /attach 连接已关闭/)
})

test('未知帧类型视为协议错误并断开，不抛出无人接住的错误', async () => {
  const socket = new FakeSocket()
  const streams = new AttachedStreams(socket, Buffer.concat([frame(1, 'ok'), frame(7, 'bad'), frame(1, 'after')]))
  assert.equal(socket.destroyed, true)
  assert.match(streams.protocolError, /未知帧类型 7/)
  assert.equal(await collect(streams.stdout), 'ok')
  await streams.closed
})
