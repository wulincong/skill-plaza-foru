/* Pi RPC（JSONL over stdio）在 attach 流上的通道。分帧规则照 Pi 的 rpc.md：
   只按 LF 分帧、容忍前置 CR，不使用会把 U+2028/U+2029 当换行的通用行读取器。 */

import { SandboxError } from './errors.ts'

export interface RpcDuplex {
  stdout: AsyncIterable<Buffer>
  write(data: Buffer): Promise<void>
  end(): void
  destroy(): void
}

export interface PiBashResult {
  output: string
  exitCode: number
  cancelled: boolean
  truncated: boolean
  fullOutputPath?: string
}

export interface PiState {
  sessionId?: string
  sessionFile?: string
  sessionName?: string
  isStreaming?: boolean
  thinkingLevel?: string
  model?: { id?: string; provider?: string }
  messageCount?: number
}

export type RpcEvent = Record<string, unknown>

interface Pending {
  label: string
  resolve: (value: any) => void
  reject: (error: Error) => void
  timer: NodeJS.Timeout
}

export interface RpcRequestOptions {
  timeoutMs?: number
}

interface ChannelOptions {
  maxFrameBytes?: number
  defaultTimeoutMs?: number
}

export class PiRpcChannel {
  readonly closed: Promise<string>
  readonly stats = { frames: 0, badLines: 0, bytes: 0 }
  /** 非响应记录（会话事件、反向请求） */
  onEvent: (event: RpcEvent) => void = () => {}
  /** 协议级致命错误（超限帧），由沙箱决定终止 */
  onFatal: (error: SandboxError) => void = () => {}

  private readonly stream: RpcDuplex
  private readonly maxFrameBytes: number
  private readonly defaultTimeoutMs: number
  private pending = new Map<string | number, Pending>()
  private buffer: Buffer = Buffer.alloc(0)
  private nextId = 1
  private closeReason: string | null = null
  private resolveClosed: (reason: string) => void = () => {}

  constructor(stream: RpcDuplex, options: ChannelOptions = {}) {
    this.stream = stream
    this.maxFrameBytes = options.maxFrameBytes ?? 4 * 1024 * 1024
    this.defaultTimeoutMs = options.defaultTimeoutMs ?? 60_000
    this.closed = new Promise((resolve) => {
      this.resolveClosed = resolve
    })
    void this.pump()
  }

  get isOpen(): boolean {
    return this.closeReason === null
  }

  get closeInfo(): string | null {
    return this.closeReason
  }

  private async pump() {
    try {
      for await (const chunk of this.stream.stdout) this.ingest(chunk)
      this.close('Pi 标准输出已结束')
    } catch (error) {
      if (error instanceof SandboxError) {
        this.close(error.message)
        this.onFatal(error)
      } else {
        this.close(`Pi 输出流异常：${error instanceof Error ? error.message : String(error)}`)
      }
    }
  }

  close(reason: string) {
    if (this.closeReason !== null) return
    this.closeReason = reason
    for (const entry of this.pending.values()) {
      clearTimeout(entry.timer)
      entry.reject(new SandboxError('RPC_CLOSED', `${entry.label} 未完成：${reason}`))
    }
    this.pending.clear()
    this.resolveClosed(reason)
  }

  private ingest(chunk: Buffer) {
    this.buffer = this.buffer.length ? Buffer.concat([this.buffer, chunk]) : chunk
    this.stats.bytes += chunk.length
    for (;;) {
      const newline = this.buffer.indexOf(0x0a)
      if (newline < 0) {
        if (this.buffer.length > this.maxFrameBytes) {
          throw new SandboxError('FRAME_TOO_LARGE', `Pi 输出超过 ${this.maxFrameBytes} 字节仍无换行，已按超限处理`)
        }
        return
      }
      if (newline > this.maxFrameBytes) {
        throw new SandboxError('FRAME_TOO_LARGE', `Pi 单帧 ${newline} 字节超过上限 ${this.maxFrameBytes}`)
      }
      let frame = this.buffer.subarray(0, newline)
      this.buffer = this.buffer.subarray(newline + 1)
      if (frame.length && frame[frame.length - 1] === 0x0d) frame = frame.subarray(0, frame.length - 1)
      if (!frame.length) continue
      this.stats.frames++
      let record: any
      try {
        record = JSON.parse(frame.toString('utf8'))
      } catch {
        this.stats.badLines++
        continue
      }
      if (!record || typeof record !== 'object' || !this.settle(record)) this.onEvent(record)
    }
  }

  private settle(record: any): boolean {
    if (record.type !== 'response' || record.id === undefined || record.id === null) return false
    const entry = this.pending.get(record.id)
    if (!entry) return false
    this.pending.delete(record.id)
    clearTimeout(entry.timer)
    if (record.success === false || record.error) {
      const reason = typeof record.error === 'string' ? record.error : JSON.stringify(record.error ?? '未知错误')
      entry.reject(new SandboxError('RPC_COMMAND', `Pi 命令 ${entry.label} 失败：${reason}`))
    } else {
      entry.resolve(record.data ?? record.result)
    }
    return true
  }

  request(payload: Record<string, unknown>, options: RpcRequestOptions = {}): Promise<any> {
    if (this.closeReason !== null) {
      return Promise.reject(new SandboxError('RPC_CLOSED', `Pi 通道已关闭：${this.closeReason}`))
    }
    const id = this.nextId++
    const label = String(payload.type ?? 'request')
    const timeoutMs = options.timeoutMs ?? this.defaultTimeoutMs
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id)
        reject(new SandboxError('RPC_TIMEOUT', `Pi 未在 ${timeoutMs} 毫秒内回应 ${label}`))
      }, timeoutMs)
      this.pending.set(id, { label, resolve, reject, timer })
      this.stream.write(Buffer.from(`${JSON.stringify({ id, ...payload })}\n`, 'utf8')).catch((error: unknown) => {
        const entry = this.pending.get(id)
        if (entry) {
          this.pending.delete(id)
          clearTimeout(entry.timer)
          entry.reject(error instanceof Error ? error : new SandboxError('RPC_CLOSED', String(error)))
        }
      })
    })
  }

  getState(): Promise<PiState> {
    return this.request({ type: 'get_state' })
  }

  /* 真实 Pi 进程在沙箱内执行的 shell；不经模型 */
  bash(command: string, options: RpcRequestOptions & { excludeFromContext?: boolean } = {}): Promise<PiBashResult> {
    return this.request(
      { type: 'bash', command, ...(options.excludeFromContext ? { excludeFromContext: true } : {}) },
      options,
    )
  }

  /* 关闭 Pi 的 stdin 请求有序退出，输出方向继续读到容器退出 */
  end() {
    this.stream.end()
  }
}
