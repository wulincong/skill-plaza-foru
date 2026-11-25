import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readTar } from '../src/tar.ts'

function header(name, { size = 0, type = '0', prefix = '', binarySize = false } = {}) {
  const block = Buffer.alloc(512)
  block.write(name, 0, 100, 'utf8')
  block.write('0000644\0', 100)
  block.write('0000000\0', 108)
  block.write('0000000\0', 116)
  if (binarySize) {
    block[124] = 0x80
    block.writeBigUInt64BE(BigInt(size), 128)
  } else {
    block.write(`${size.toString(8).padStart(11, '0')}\0`, 124)
  }
  block.write('00000000000\0', 136)
  block.write(type, 156)
  block.write('ustar\0', 257)
  block.write('00', 263)
  block.write(prefix, 345, 155, 'utf8')
  let sum = 0
  for (const byte of block) sum += byte
  block.write(`${sum.toString(8).padStart(6, '0')}\0 `, 148)
  return block
}

const pad = (size) => Buffer.alloc((512 - (size % 512)) % 512)
const file = (name, data, options = {}) => Buffer.concat([header(name, { size: Buffer.byteLength(data), ...options }), Buffer.from(data), pad(Buffer.byteLength(data))])
const END = Buffer.alloc(1024)

test('读出文件与目录，去掉 ./ 与结尾斜杠', () => {
  const entries = readTar(Buffer.concat([header('work/', { type: '5' }), file('./work/a.txt', 'hello'), file('work/sub/../b', 'x'), END]))
  assert.deepEqual(
    entries.map((entry) => [entry.name, entry.type, entry.data.toString()]),
    [
      ['work', 'dir', ''],
      ['work/a.txt', 'file', 'hello'],
      ['work/sub/../b', 'file', 'x'],
    ],
  )
})

test('支持 ustar 前缀、GNU 长文件名与 PAX path', () => {
  const long = `work/${'d'.repeat(120)}/file.txt`
  const record = `${144} path=${long}\n`
  assert.equal(record.length, 144)
  const archive = Buffer.concat([
    file('short', 'prefixed', { prefix: 'usr/local/share' }),
    header('././@LongLink', { size: long.length + 1, type: 'L' }),
    Buffer.from(`${long}\0`),
    pad(long.length + 1),
    file('old', 'long-name'),
    header('PaxHeader', { size: record.length, type: 'x' }),
    Buffer.from(record),
    pad(record.length),
    file('short', 'paxed'),
    END,
  ])
  const entries = readTar(archive)
  assert.deepEqual(
    entries.map((entry) => entry.name),
    ['usr/local/share/short', long, long],
  )
})

test('支持 base-256 编码的长度，并把符号链接标为 other', () => {
  const content = 'z'.repeat(70000)
  const link = header('work/link', { type: '2' })
  link.write('target.txt', 157, 100)
  const entries = readTar(Buffer.concat([file('work/big', content, { binarySize: true }), link, END]))
  assert.deepEqual(entries.map((entry) => [entry.name, entry.type, entry.size]), [
    ['work/big', 'file', 70000],
    ['work/link', 'other', 0],
  ])
  assert.equal(entries[0].data.length, 70000)
})

test('数据被截断或条目过多时报错', () => {
  assert.throws(() => readTar(Buffer.concat([header('a', { size: 4096 }), Buffer.alloc(512)])), /tar 头部长度非法/)
  assert.throws(() => readTar(Buffer.concat([file('a', 'x'), file('b', 'y'), END]), 1), /条目超过/)
})
