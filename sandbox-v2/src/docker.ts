/* 受信 Worker 的 Docker Engine API 客户端：只经本地 unix socket 调用固定版本 API，
   不依赖 docker CLI，也不让任务输入有机会拼进任何 Docker 参数。 */

import { Agent, request as httpRequest, type IncomingMessage } from 'node:http'
import { Readable } from 'node:stream'
import { SandboxError } from './errors.ts'

export const API_VERSION = 'v1.44'
export const DEFAULT_SOCKET_PATH = '/var/run/docker.sock'
const JSON_LIMIT_BYTES = 32 * 1024 * 1024
const AGENT = new Agent({ keepAlive: false })

export interface ContainerState {
  Status: string
  Running: boolean
  Paused: boolean
  Restarting: boolean
  OOMKilled: boolean
  Dead: boolean
  Pid: number
  ExitCode: number
  Error: string
  StartedAt: string
  FinishedAt: string
}

export interface ContainerMount {
  Type: string
  Name?: string
  Source: string
  Destination: string
  Target?: string
  Mode: string
  RW: boolean
  Propagation: string
}

export interface ContainerInspect {
  Id: string
  Name: string
  Image: string
  State: ContainerState
  Config: {
    User: string
    Env: string[]
    Image: string
    Cmd: string[] | null
    Entrypoint: string[] | null
    WorkingDir: string
    Labels: Record<string, string>
    OpenStdin: boolean
    StdinOnce: boolean
    Tty: boolean
    ExposedPorts?: Record<string, unknown>
    StopSignal: string
    StopTimeout: number | null
  }
  HostConfig: {
    Runtime: string
    NetworkMode: string
    ReadonlyRootfs: boolean
    Privileged: boolean
    CapAdd: string[] | null
    CapDrop: string[] | null
    SecurityOpt: string[] | null
    Devices: unknown[]
    DeviceRequests: unknown[]
    Tmpfs: Record<string, string> | null
    Mounts: unknown[]
    Binds: string[] | null
    PidsLimit: number
    Memory: number
    MemorySwap: number
    NanoCpus: number
    Ulimits: { Name: string; Soft: number; Hard: number }[] | null
    AutoRemove: boolean
    Init: boolean | null
    LogConfig: { Type: string; Config: Record<string, string> | null }
    ExtraHosts: string[] | null
    Dns: string[] | null
    PortBindings: Record<string, unknown> | null
    IpcMode: string
    PidMode: string
    UTSMode: string
    UsernsMode: string
    CgroupnsMode: string
    RestartPolicy: { Name: string }
    StopTimeout: number | null
    StopSignal: string
    Sysctls: Record<string, string> | null
    VolumeDriver: string
    VolumesFrom: string[] | null
    MaskedPaths: string[] | null
    ReadonlyPaths: string[] | null
    Isolation: string
    OomKillDisable: boolean | null
  }
  Mounts: ContainerMount[]
  NetworkSettings: { Networks: Record<string, unknown> }
}

export interface ContainerSummary {
  Id: string
  Names: string[]
  Image: string
  State: string
  Labels: Record<string, string>
}

export interface VolumeInfo {
  Name: string
  Driver: string
  Mountpoint: string
  Labels: Record<string, string> | null
  Options: Record<string, string> | null
}

export interface ImageInspect {
  Id: string
  RepoDigests: string[]
  Architecture: string
  Os: string
  Size: number
  Config: {
    User: string
    Env: string[]
    Cmd: string[] | null
    Entrypoint: string[] | null
    WorkingDir: string
    Labels: Record<string, string> | null
    ExposedPorts?: Record<string, unknown>
  }
  RootFS: { Layers: string[] }
}

export interface DockerInfo {
  Runtimes: Record<string, { path: string }> | null
  DefaultRuntime: string
  ServerVersion: string
  Architecture: string
  CgroupVersion: string
  CgroupDriver: string
  OperatingSystem: string
}

export class DockerApiError extends SandboxError {
  readonly status: number

  constructor(status: number, message: string) {
    super('DOCKER_API', message, { status })
    this.name = 'DockerApiError'
    this.status = status
  }
}

export function isNotFound(error: unknown): boolean {
  return error instanceof DockerApiError && error.status === 404
}

export function resolveSocketPath(env: Record<string, string | undefined> = process.env): string {
  const raw = env.DOCKER_HOST?.trim()
  if (!raw) return DEFAULT_SOCKET_PATH
  const match = /^unix:\/\/(.+)$/.exec(raw)
  if (!match) {
    throw new SandboxError('INVALID_SPEC', `只接受本地 unix socket 的 DOCKER_HOST（unix:///路径），当前为 ${raw}`)
  }
  return match[1]
}

type Query = Record<string, string | string[] | undefined>
interface SendOptions {
  method?: 'GET' | 'POST' | 'DELETE'
  query?: Query
  body?: unknown
  /** 0 表示不设超时（等待容器退出等长连接） */
  timeoutMs?: number
}

function translateSocketError(error: NodeJS.ErrnoException, socketPath: string): SandboxError {
  if (error instanceof SandboxError) return error
  const cause = { cause: error }
  switch (error.code) {
    case 'EACCES':
      return new SandboxError('DOCKER_UNREACHABLE', `无权访问 Docker socket ${socketPath}`, null, cause)
    case 'ENOENT':
    case 'ECONNREFUSED':
    case 'ECONNRESET':
    case 'EPIPE':
    case 'ETIMEDOUT':
      return new SandboxError('DOCKER_UNREACHABLE', `Docker socket 不可达：${socketPath}（${error.message}）`, null, cause)
    default:
      return new SandboxError('DOCKER_API', `Docker 请求失败：${error.message}`, null, cause)
  }
}

function describeApiError(status: number, payload: Buffer): string {
  try {
    const parsed = JSON.parse(payload.toString('utf8'))
    return parsed?.message ? String(parsed.message) : `HTTP ${status}`
  } catch {
    return payload.length ? `HTTP ${status} ${payload.toString('utf8', 0, 200)}` : `HTTP ${status}`
  }
}

export class AttachedStreams {
  readonly stdout: Readable
  readonly stderr: Readable
  readonly closed: Promise<void>
  protocolError: string | null = null
  private readonly socket: import('node:net').Socket
  private pending = Buffer.alloc(0)
  private paused = false
  private resolveClosed: () => void = () => {}
  private readonly drained: Promise<void>
  private readonly maxWriteBuffer: number

  constructor(socket: import('node:net').Socket, head: Buffer, maxWriteBuffer = 1024 * 1024) {
    this.socket = socket
    this.maxWriteBuffer = maxWriteBuffer
    this.stdout = new Readable({ read: () => this.resume() })
    this.stderr = new Readable({ read: () => this.resume() })
    this.closed = new Promise((resolve) => {
      this.resolveClosed = () => {
        resolve()
      }
    })
    this.drained = new Promise((resolve) => socket.once('drain', resolve))
    socket.on('data', (chunk: Buffer) => this.demux(chunk))
    if (head.length) this.demux(head)
    socket.on('error', () => {})
    socket.on('close', () => this.finish())
  }

  private finish() {
    this.stdout.push(null)
    this.stderr.push(null)
    this.resolveClosed()
  }

  /* 下游读得慢就暂停 socket，让背压一路传回 Pi，而不是在这里无界堆积 */
  private deliver(target: Readable, payload: Buffer) {
    if (!target.push(payload)) {
      this.paused = true
      this.socket.pause()
    }
  }

  private resume() {
    if (this.paused) {
      this.paused = false
      this.socket.resume()
    }
  }

  /* Docker 未分配 TTY 时输出按 8 字节头分帧：[流类型, 0,0,0, 长度(4 字节大端)] */
  private demux(chunk: Buffer) {
    this.pending = this.pending.length ? Buffer.concat([this.pending, chunk]) : chunk
    let offset = 0
    while (this.pending.length - offset >= 8) {
      const type = this.pending[offset]
      const size = this.pending.readUInt32BE(offset + 4)
      if (type > 2) {
        /* 协议错误：断开连接并结束两条流。不用带错误对象的 destroy，避免此时还没有消费者而让 error 事件无人接住 */
        this.protocolError = `attach 流出现未知帧类型 ${type}`
        this.socket.destroy()
        this.finish()
        return
      }
      if (this.pending.length - offset - 8 < size) break
      if (size) this.deliver(type === 2 ? this.stderr : this.stdout, this.pending.subarray(offset + 8, offset + 8 + size))
      offset += 8 + size
    }
    this.pending = offset ? this.pending.subarray(offset) : this.pending
  }

  get writable(): boolean {
    return !this.socket.destroyed && !this.socket.writableEnded
  }

  async write(data: Buffer): Promise<void> {
    if (!this.writable) throw new SandboxError('RPC_CLOSED', 'attach 连接已关闭，无法再向 Pi 写入')
    if (this.socket.writableLength > this.maxWriteBuffer) await Promise.race([this.drained, this.closed])
    if (!this.writable) throw new SandboxError('RPC_CLOSED', 'attach 连接已关闭，无法再向 Pi 写入')
    this.socket.write(data)
  }

  /* 半关闭：只结束容器 stdin，让 Pi 有序退出，输出方向继续读到容器退出 */
  end() {
    if (!this.socket.destroyed) this.socket.end()
  }

  destroy() {
    this.socket.destroy()
  }
}

export class DockerClient {
  readonly socketPath: string

  constructor(options: { socketPath?: string } = {}) {
    this.socketPath = options.socketPath ?? resolveSocketPath()
  }

  private path(resource: string, query?: Query): string {
    const search = new URLSearchParams()
    for (const [key, value] of Object.entries(query ?? {})) {
      if (value === undefined) continue
      for (const item of Array.isArray(value) ? value : [value]) search.append(key, item)
    }
    return `/${API_VERSION}${resource}${search.size ? `?${search}` : ''}`
  }

  private open(resource: string, options: SendOptions, headers: Record<string, string>, agent: Agent | undefined) {
    const body = options.body === undefined ? null : Buffer.from(JSON.stringify(options.body))
    return new Promise<IncomingMessage>((resolve, reject) => {
      const req = httpRequest(
        {
          socketPath: this.socketPath,
          path: this.path(resource, options.query),
          method: options.method ?? 'GET',
          agent,
          headers: body ? { ...headers, 'Content-Type': 'application/json', 'Content-Length': String(body.length) } : headers,
          timeout: options.timeoutMs ?? 30_000,
        },
        resolve,
      )
      req.on('timeout', () => req.destroy(new SandboxError('DOCKER_UNREACHABLE', `Docker 守护进程响应超时（${resource}）`)))
      req.on('error', (error: NodeJS.ErrnoException) => reject(translateSocketError(error, this.socketPath)))
      req.end(body ?? undefined)
    })
  }

  async request(resource: string, options: SendOptions = { method: 'GET' }): Promise<Buffer> {
    const res = await this.open(resource, options, {}, AGENT)
    const chunks: Buffer[] = []
    let size = 0
    for await (const chunk of res) {
      size += chunk.length
      if (size > JSON_LIMIT_BYTES) {
        res.destroy()
        throw new SandboxError('DOCKER_API', `Docker 响应超过 ${JSON_LIMIT_BYTES} 字节（${resource}）`)
      }
      chunks.push(chunk)
    }
    const payload = Buffer.concat(chunks)
    if (res.statusCode === undefined || res.statusCode >= 400) {
      throw new DockerApiError(res.statusCode ?? 0, `${options.method} ${resource}：${describeApiError(res.statusCode ?? 0, payload)}`)
    }
    return payload
  }

  async json<T>(resource: string, options?: SendOptions): Promise<T> {
    return JSON.parse((await this.request(resource, options)).toString('utf8')) as T
  }

  version(): Promise<{ ApiVersion: string; MinAPIVersion: string; Version: string }> {
    return this.json('/version')
  }

  info(): Promise<DockerInfo> {
    return this.json('/info')
  }

  inspectImage(reference: string): Promise<ImageInspect> {
    return this.json(`/images/${encodeURIComponent(reference)}/json`)
  }

  createContainer(body: unknown): Promise<{ Id: string; Warnings: string[] }> {
    return this.json('/containers/create', { method: 'POST', body })
  }

  startContainer(id: string): Promise<void> {
    return this.request(`/containers/${id}/start`, { method: 'POST' }).then(() => undefined)
  }

  inspectContainer(id: string): Promise<ContainerInspect> {
    return this.json(`/containers/${id}/json`)
  }

  waitContainer(id: string): Promise<{ StatusCode: number; Error: { Message: string } | null }> {
    return this.json(`/containers/${id}/wait`, { method: 'POST', query: { condition: 'not-running' }, timeoutMs: 0 })
  }

  stopContainer(id: string, timeoutSec: number): Promise<void> {
    return this.request(`/containers/${id}/stop`, { method: 'POST', query: { t: String(timeoutSec) }, timeoutMs: 0 }).then(() => undefined)
  }

  async removeContainer(id: string): Promise<void> {
    try {
      await this.request(`/containers/${id}`, { method: 'DELETE', query: { v: '1', force: '1' }, timeoutMs: 120_000 })
    } catch (error) {
      if (!isNotFound(error)) throw error
    }
  }

  listContainers(filters: Record<string, string[]>): Promise<ContainerSummary[]> {
    return this.json('/containers/json', { query: { all: '1', filters: JSON.stringify(filters) } })
  }

  createVolume(body: unknown): Promise<VolumeInfo> {
    return this.json('/volumes/create', { method: 'POST', body })
  }

  inspectVolume(name: string): Promise<VolumeInfo> {
    return this.json(`/volumes/${encodeURIComponent(name)}`)
  }

  listVolumes(filters: Record<string, string[]>): Promise<{ Volumes: VolumeInfo[] | null }> {
    return this.json('/volumes', { query: { filters: JSON.stringify(filters) } })
  }

  async removeVolume(name: string): Promise<void> {
    try {
      await this.request(`/volumes/${encodeURIComponent(name)}`, { method: 'DELETE', query: { force: '1' } })
    } catch (error) {
      if (!isNotFound(error)) throw error
    }
  }

  /* 运行中容器的归档读取，只用于受信侧核对 /work 内容 */
  getArchive(id: string, path: string): Promise<Buffer> {
    return this.request(`/containers/${id}/archive`, { query: { path }, timeoutMs: 60_000 })
  }

  attach(id: string, options: { openTimeoutMs?: number } = {}): Promise<AttachedStreams> {
    return new Promise((resolve, reject) => {
      const req = httpRequest(
        {
          socketPath: this.socketPath,
          path: this.path(`/containers/${id}/attach`, { stream: '1', stdin: '1', stdout: '1', stderr: '1' }),
          method: 'POST',
          agent: false,
          headers: { Connection: 'Upgrade', Upgrade: 'tcp' },
        },
        (res) => {
          const chunks: Buffer[] = []
          res.on('data', (chunk: Buffer) => chunks.push(chunk))
          res.on('end', () => reject(new DockerApiError(res.statusCode ?? 0, describeApiError(res.statusCode ?? 0, Buffer.concat(chunks)))))
          res.on('error', (error) => reject(translateSocketError(error as NodeJS.ErrnoException, this.socketPath)))
        },
      )
      const timer = setTimeout(() => {
        req.destroy()
        reject(new SandboxError('START_FAILED', `attach 容器 ${id.slice(0, 12)} 超时`))
      }, options.openTimeoutMs ?? 30_000)
      req.once('upgrade', (_res, socket, head) => {
        clearTimeout(timer)
        resolve(new AttachedStreams(socket, head))
      })
      req.once('error', (error: NodeJS.ErrnoException) => {
        clearTimeout(timer)
        reject(translateSocketError(error, this.socketPath))
      })
      req.end()
    })
  }
}
