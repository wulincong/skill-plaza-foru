/* 测试替身：可推送、可关闭的 attach 流，以及按脚本应答的 Pi。 */

export class FakeDuplex {
  constructor() {
    this.out = []
    this.err = []
    this.written = []
    this.outDone = false
    this.errDone = false
    this.waiters = new Set()
    this.onWrite = null
    this.onEnd = null
  }

  wake() {
    for (const resolve of this.waiters) resolve()
    this.waiters.clear()
  }

  pushOut(chunk) {
    this.out.push(Buffer.from(chunk))
    this.wake()
  }

  pushErr(chunk) {
    this.err.push(Buffer.from(chunk))
    this.wake()
  }

  endOut() {
    this.outDone = true
    this.wake()
  }

  endErr() {
    this.errDone = true
    this.wake()
  }

  /* 每次取数都重新读取结束状态；按值捕获会在等待期间拿到过期的 false */
  next(getQueue, getDone) {
    const queue = getQueue()
    if (queue.length) return Promise.resolve({ value: queue.shift(), done: false })
    if (getDone()) return Promise.resolve({ value: undefined, done: true })
    return new Promise((resolve) => this.waiters.add(resolve)).then(() => this.next(getQueue, getDone))
  }

  get stdout() {
    const self = this
    return { [Symbol.asyncIterator]: () => ({ next: () => self.next(() => self.out, () => self.outDone) }) }
  }

  get stderr() {
    const self = this
    return { [Symbol.asyncIterator]: () => ({ next: () => self.next(() => self.err, () => self.errDone) }) }
  }

  async write(data) {
    const text = data.toString()
    this.written.push(text)
    if (this.onWrite) await this.onWrite(text)
  }

  end() {
    if (this.onEnd) this.onEnd()
  }

  destroy() {
    this.outDone = true
    this.errDone = true
    this.wake()
  }
}

export const tick = (ms = 5) => new Promise((resolve) => setTimeout(resolve, ms))

/* 每条命令都成功应答的 Pi：get_state 回报会话，bash 回报探针文本 */
export function scriptedPi(duplex, options = {}) {
  duplex.onWrite = (text) => {
    const message = JSON.parse(text)
    const reply = (data) => duplex.pushOut(`${JSON.stringify({ id: message.id, type: 'response', command: message.type, success: true, data })}\n`)
    if (message.type === 'get_state') {
      reply(options.state ?? { sessionId: 'session-1', sessionFile: '/work/.pi-sessions/session-1.jsonl', messageCount: 0 })
    } else if (message.type === 'bash') {
      reply({ output: options.probe ?? '65532|4.19.0-gvisor|v22.23.5\n', exitCode: 0, cancelled: false, truncated: false })
    } else if (options.onCommand) {
      options.onCommand(message, reply)
    }
  }
}
