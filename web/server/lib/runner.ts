/* ============================================================
   AgentRunner 抽象基类
   ------------------------------------------------------------
   Pi 是「常驻子进程 + JSONL over stdio」的桥：公共机制放这里——
   严格 \n 分帧、请求/响应 id 关联、pending 拒绝、会话事件回调
   （listen）、协议留痕 tap（trace 记录用）。
   PiRunner 负责进程生命周期、消息路由与事件归一、会话创建/收尾、
   trace 导出和首轮提示词拼装。
   协议说明：docs/pi-runner.md。
   ============================================================ */

import { spawn, type ChildProcess } from 'node:child_process'
import type {
  AgentEnvInfo,
  ModelContextInfo,
  TraceExportOptions,
  UsageRound,
  UsageSummary,
} from './traceExport.ts'

export type EngineName = 'pi'

export type EventCb = (event: RunnerEvent) => void
export type TapFn = (dir: 'out' | 'in', msg: any) => void

/** 归一后的引擎事件；index.ts 统一映射成 SSE，前端协议不感知引擎 */
export type RunnerEvent =
  | { kind: 'text_delta'; delta: string }
  /* 思考原文增量（pi thinking_delta）：plaza 协议只消费节流计数（status），
     OpenAI 兼容端点用它填 reasoning_content；广场 /api/chat 忽略本事件 */
  | { kind: 'thinking_delta'; delta: string }
  | {
      kind: 'status'
      /* message 相位是 assistant 消息边界（piRunner 在 message_start/end 发出），
         OpenAI wire 以消息级定性分流 text：tool 字段携带定性结果
         （'toolcall'=过程叙述 | 'final'=最终答复） */
      phase: 'thinking' | 'tool' | 'text' | 'message'
      state?: 'active' | 'completed' | 'failed' | 'start' | 'end'
      chars?: number
      tool?: string
      id?: string
    }
  | {
      kind: 'usage'
      usage?: UsageSummary
      content?: string
      round?: UsageRound
      context?: ModelContextInfo
    }
  | {
      kind: 'terminal'
      response: string
      resultType: string
      usage?: UsageSummary
      rounds?: UsageRound[]
      context?: ModelContextInfo
    }
  | { kind: 'error'; message: string }

/** 单个 JSONL over stdio 的子进程通道 */
export class JsonlChannel {
  readonly proc: ChildProcess
  private buf = ''
  private closed = false
  onLine: (msg: any) => void = () => {}
  onExit: () => void = () => {}

  constructor(command: string, args: string[], opts: { cwd?: string; shell?: boolean } = {}) {
    this.proc = spawn(command, args, {
      stdio: ['pipe', 'pipe', 'inherit'],
      ...(opts.cwd ? { cwd: opts.cwd } : {}),
      ...(opts.shell ? { shell: true } : {}),
    })
    /* pi rpc.md 明确要求：只按 \n 分帧、容忍尾部 \r（readline 会错误地
       在 U+2028/U+2029 分行，不能用）；协议外的行直接忽略 */
    this.proc.stdout!.on('data', (d: Buffer) => {
      this.buf += d.toString('utf8')
      let i: number
      while ((i = this.buf.indexOf('\n')) >= 0) {
        const line = this.buf.slice(0, i).trim()
        this.buf = this.buf.slice(i + 1)
        if (line) {
          try {
            this.onLine(JSON.parse(line))
          } catch {
            // 协议外的行直接忽略
          }
        }
      }
    })
    this.proc.once('exit', () => this.close())
    this.proc.once('error', () => this.close()) // spawn 失败（如命令不存在）
  }

  write(obj: any) {
    this.proc.stdin?.write(JSON.stringify(obj) + '\n')
  }

  kill() {
    try {
      this.proc.kill()
    } catch {
      /* 已退出 */
    }
  }

  get exited() {
    return this.proc.exitCode !== null || this.proc.killed || this.closed
  }

  private close() {
    if (this.closed) return
    this.closed = true
    this.onExit()
  }
}

export abstract class AgentRunner {
  abstract readonly name: EngineName
  /** 健康描述（/api/health 的 model 字段与启动日志） */
  abstract describe(): string
  /** 运行环境快照（run 记录落盘用）；子类补充版本/思考档位等引擎特有字段 */
  envInfo(_sessionId?: string): Partial<AgentEnvInfo> {
    return { model: this.describe() }
  }

  private nextId = 1
  protected pending = new Map<
    number,
    { resolve: (v: any) => void; reject: (e: Error) => void; label: string; sid?: string }
  >()
  /** 引擎会话 id → 归一事件回调集合 */
  private listeners = new Map<string, Set<EventCb>>()
  /** 引擎会话 id → 协议 tap（trace 记录用） */
  private taps = new Map<string, TapFn>()

  /* ---------------- 子类定制点 ---------------- */

  /** 取会话对应的 Pi 通道；每个引擎会话一个进程。 */
  protected abstract channelFor(sessionId: string): JsonlChannel

  /** 非响应类消息（通知 / 反向请求 / 事件）的路由与归一 */
  protected abstract routeMessage(channel: JsonlChannel, msg: any): void

  /** 通道退出善后；默认拒绝全部 pending（子类可按通道范围细化） */
  protected onChannelExit(_channel: JsonlChannel): void {
    for (const p of this.pending.values()) p.reject(new Error('引擎子进程退出'))
    this.pending.clear()
  }

  /* ---------------- 对 index.ts 暴露的统一 API ---------------- */

  abstract createSession(workspaceDir: string, opts?: { skill?: string }): Promise<string>
  abstract send(sessionId: string, content: string): Promise<void>
  /** 新一轮运行开始；无状态引擎可保持默认空操作。 */
  beginTurn(_sessionId: string): void {}
  /** 停止当前执行（超时/断连用）；尽力而为，不抛错 */
  abstract stop(sessionId: string): Promise<void>
  /** 会话终态 trace 导出（写入 outFile，返回 toolCallCount；导不出返回 null） */
  abstract exportTrace(
    sessionId: string,
    outFile: string,
    options?: TraceExportOptions,
  ): Promise<{ toolCallCount: number } | null>
  /** 可在 runStart 阶段取得的模型标识；上下文窗口未知时必须明确返回 unavailable。 */
  modelInfo(): ModelContextInfo {
    return {
      model: this.envInfo().model ?? null,
      provider: null,
      contextWindowTokens: null,
      contextWindowSource: 'provider_metadata_unavailable',
    }
  }
  /** 会话创建后可返回 provider/model 配置中的上下文窗口。 */
  modelInfoForSession(_sessionId: string): ModelContextInfo {
    return this.modelInfo()
  }
  /** 首轮提示词拼装（各引擎的技能接法不同） */
  abstract buildPrompt(skill: string, messages: any[], isFirstTurn: boolean): string
  /** 会话资源回收（pi：杀子进程）；无持久资源者默认空操作 */
  disposeSession(_sessionId: string): void {}

  listen(sessionId: string, cb: EventCb): () => void {
    let set = this.listeners.get(sessionId)
    if (!set) {
      set = new Set()
      this.listeners.set(sessionId, set)
    }
    set.add(cb)
    return () => set!.delete(cb)
  }

  tapSession(sessionId: string, fn: TapFn): () => void {
    this.taps.set(sessionId, fn)
    return () => {
      if (this.taps.get(sessionId) === fn) this.taps.delete(sessionId)
    }
  }

  protected dropSessionBookkeeping(sessionId: string) {
    this.listeners.delete(sessionId)
    this.taps.delete(sessionId)
  }

  /* ---------------- 子类可用的公共机制 ---------------- */

  protected emit(sessionId: string, event: RunnerEvent) {
    const cbs = this.listeners.get(sessionId)
    if (cbs) for (const cb of [...cbs]) cb(event)
  }

  protected tapOf(sessionId: unknown): TapFn | undefined {
    return typeof sessionId === 'string' ? this.taps.get(sessionId) : undefined
  }

  /**
   * 发请求并按 id 关联响应。Pi payload 使用 {type, ...}，id 由这里统一附加。
   */
  protected request(payload: Record<string, any>, sid?: string): Promise<any> {
    const ch = this.channelFor(sid ?? '')
    const id = this.nextId++
    const label = payload.method || payload.type || 'request'
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, label, sid })
      this.tapOf(sid)?.('out', { id, ...payload })
      ch.write({ id, ...payload })
    })
  }

  /** 尝试把一行消息按 pending 响应结算；命中返回 true */
  protected trySettle(msg: any): boolean {
    if (msg?.id === undefined || msg.id === null || msg.method) return false
    const p = this.pending.get(msg.id)
    if (!p) return false
    this.pending.delete(msg.id)
    this.tapOf(p.sid)?.(
      'in',
      msg.error
        ? { id: msg.id, label: p.label, error: msg.error }
        : { id: msg.id, label: p.label, success: msg.success, result: msg.result ?? msg.data },
    )
    if (msg.error || msg.success === false)
      p.reject(new Error(msg.error?.message || msg.error || `${p.label} 失败`))
    else p.resolve(msg.result ?? msg.data)
    return true
  }

  /** 通道消息的公共入口：先按响应结算，剩下交给子类路由 */
  protected wireChannel(ch: JsonlChannel) {
    ch.onLine = (msg) => {
      if (!this.trySettle(msg)) this.routeMessage(ch, msg)
    }
    ch.onExit = () => this.onChannelExit(ch)
  }
}
