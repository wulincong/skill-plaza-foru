/* 受信沙箱 Worker：按登记的镜像 ID 与 runsc 启动一个离线 Pi 沙箱，从 Docker 侧核对后才放行，
   并保证正常退出、出错、超时三条路径都回收容器与工作卷。
   本模块只有 Docker 管理权限的受信进程可以加载；沙箱内代码和任务输入都不能控制这里的任何参数。 */

import { randomBytes } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  DockerApiError,
  DockerClient,
  API_VERSION,
  isNotFound,
  type AttachedStreams,
  type ContainerInspect,
  type DockerInfo,
  type ImageInspect,
  type VolumeInfo,
} from './docker.ts'
import { SandboxError, errorMessage } from './errors.ts'
import { readHostLimits, type HostCgroupLimits } from './host.ts'
import { PiRpcChannel, type PiBashResult, type PiState, type RpcEvent, type RpcRequestOptions } from './pi-rpc.ts'
import {
  LABEL_ATTEMPT,
  MANAGED_RUNTIME,
  RUNTIME_KERNEL_PATTERN,
  SESSION_DIR,
  STOP_TIMEOUT_SEC,
  WORK_DIR,
  assertRunId,
  buildCreateRequest,
  verifyRunningContainer,
  normalizeLimits,
  resolveInputs,
  resourceNames,
  runFilters,
  verifyContainer,
  verifyWorkVolume,
  workVolumeRequest,
  type ResolvedInput,
  type SandboxInput,
  type SandboxLimits,
} from './spec.ts'
import { readTar } from './tar.ts'

export interface ImageLock {
  name: string
  tag: string
  id: string
  repoDigest: string | null
  piVersion: string
  piIntegrity: string
  nodeVersion: string
  baseReference: string
  baseDigest: string
  user: string
  entrypoint: string[]
  layers: string[]
}

export interface SandboxRunSpec {
  runId: string
  inputs?: SandboxInput[]
  limits?: Partial<SandboxLimits>
}

export type SandboxOutcome = 'exited' | 'timeout' | 'oom' | 'error' | 'terminated'

export interface SandboxResult {
  outcome: SandboxOutcome
  exitCode: number | null
  oomKilled: boolean
  startedAt: string
  endedAt: string
  durationMs: number
  reason?: string
  reclaimed: { containers: number; volumes: number }
}

export interface ReclaimReport {
  containers: string[]
  volumes: string[]
}

export interface PreflightReport {
  docker: { version: string; apiVersion: string; runtime: string; runtimePath: string; defaultRuntime: string }
  image: { id: string; piVersion: string; nodeVersion: string; baseDigest: string; size: number }
}

export interface SandboxWorkerOptions {
  image: ImageLock
  /** 只读输入允许所在的宿主目录（规范化的绝对路径）。没有输入的运行不需要；要挂输入就必须显式给出 */
  inputsRoot?: string
  /** 只接受 runsc；省略即 runsc。传入其他值（包括 Docker 已注册的 runc）会在创建任何资源之前被拒绝 */
  runtime?: string
  socketPath?: string
  readyTimeoutMs?: number
  /** 容器内计时器到点后，Worker 再等多久仍未退出就强制停止；应大于入口里 timeout 的 10 秒强杀宽限 */
  deadlineGraceMs?: number
  /** 供测试注入替身；缺省按 socketPath 连接本地 Docker */
  docker?: DockerClient
}

export const DEFAULT_IMAGE_LOCK_FILE = fileURLToPath(new URL('../image.lock.json', import.meta.url))
const DIGEST = /^sha256:[0-9a-f]{64}$/
const CREDENTIAL_NAME = /(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|PRIVATE)/i
const DEFAULT_DEADLINE_GRACE_MS = 15_000
const SHUTDOWN_GRACE_MS = 15_000
const STDERR_TAIL_BYTES = 8192
const BASE_DIGEST_LABEL = 'plaza.sandbox.base.digest'
const PI_VERSION_LABEL = 'plaza.sandbox.pi.version'

export function parseImageLock(value: unknown): ImageLock {
  const lock = value as ImageLock
  const problems: string[] = []
  if (!lock || typeof lock !== 'object') throw new SandboxError('IMAGE_LOCK', '镜像登记文件不是对象')
  if (!DIGEST.test(lock.id ?? '')) problems.push('id 必须是 sha256 摘要')
  if (lock.repoDigest !== null && !DIGEST.test(lock.repoDigest ?? '')) problems.push('repoDigest 必须是 sha256 摘要或 null')
  for (const key of ['name', 'tag', 'piVersion', 'nodeVersion', 'baseReference'] as const) {
    if (typeof lock[key] !== 'string' || !lock[key]) problems.push(`${key} 缺失`)
  }
  if (!/^sha512-/.test(lock.piIntegrity ?? '')) problems.push('piIntegrity 必须是 sha512')
  if (!DIGEST.test(lock.baseDigest ?? '')) problems.push('baseDigest 必须是 sha256 摘要')
  if (!Array.isArray(lock.layers) || !lock.layers.length || lock.layers.some((item) => !DIGEST.test(item))) {
    problems.push('layers 必须是摘要数组')
  }
  if (!Array.isArray(lock.entrypoint) || !lock.entrypoint.length) problems.push('entrypoint 缺失')
  if (!/^[1-9][0-9]*:[1-9][0-9]*$/.test(lock.user ?? '')) problems.push('user 必须是非 0 的数字 uid:gid')
  if (problems.length) throw new SandboxError('IMAGE_LOCK', `镜像登记文件不合法：${problems.join('；')}`)
  return lock
}

export async function loadImageLock(file: string = DEFAULT_IMAGE_LOCK_FILE): Promise<ImageLock> {
  let text: string
  try {
    text = await readFile(file, 'utf8')
  } catch {
    throw new SandboxError('IMAGE_LOCK', `无法读取镜像登记文件 ${file}`)
  }
  try {
    return parseImageLock(JSON.parse(text))
  } catch (error) {
    if (error instanceof SandboxError) throw error
    throw new SandboxError('IMAGE_LOCK', `镜像登记文件不是合法 JSON：${file}`, null, { cause: error })
  }
}

/* 传给 Docker 的引用只能是登记的摘要，不接受可漂移的标签 */
export function imageReference(lock: ImageLock): string {
  return lock.repoDigest ? `${lock.name}@${lock.repoDigest}` : lock.id
}

/* Docker 的守护进程信息用 x86_64/aarch64，镜像元数据用 amd64/arm64 */
function normalizeArchitecture(value: string): string {
  return value === 'x86_64' ? 'amd64' : value === 'aarch64' ? 'arm64' : value
}

export function verifyImage(image: ImageInspect, lock: ImageLock, daemonArchitecture: string): string[] {
  const problems: string[] = []
  const config = image.Config
  const labels = config.Labels ?? {}
  if (image.Id !== lock.id) problems.push(`镜像 ID 为 ${image.Id}，登记为 ${lock.id}`)
  if (image.Os !== 'linux') problems.push(`镜像系统为 ${image.Os}`)
  const expectedArchitecture = normalizeArchitecture(daemonArchitecture)
  if (image.Architecture !== expectedArchitecture) problems.push(`镜像架构为 ${image.Architecture}，守护进程为 ${daemonArchitecture}`)
  if (labels[PI_VERSION_LABEL] !== lock.piVersion) problems.push(`镜像标签 ${PI_VERSION_LABEL}=${labels[PI_VERSION_LABEL]}，登记为 ${lock.piVersion}`)
  if (labels[BASE_DIGEST_LABEL] !== lock.baseDigest) problems.push(`镜像标签 ${BASE_DIGEST_LABEL} 与登记不符`)
  if (config.User !== lock.user) problems.push(`镜像运行用户为 ${config.User}，登记为 ${lock.user}`)
  if (JSON.stringify(config.Entrypoint ?? []) !== JSON.stringify(lock.entrypoint)) problems.push('镜像入口与登记不符')
  if ((config.Cmd ?? []).length) problems.push('镜像不应带默认命令')
  if (config.ExposedPorts && Object.keys(config.ExposedPorts).length) problems.push('镜像不应暴露端口')
  if (JSON.stringify(image.RootFS.Layers) !== JSON.stringify(lock.layers)) problems.push('镜像层与登记不符')
  const names = (config.Env ?? []).map((entry) => entry.slice(0, Math.max(entry.indexOf('='), 0)))
  const credentials = names.filter((name) => CREDENTIAL_NAME.test(name))
  if (credentials.length) problems.push(`镜像环境含凭据样式变量：${credentials.join(', ')}`)
  return problems
}

function compareVersion(left: string, right: string): number {
  const a = left.split('.').map(Number)
  const b = right.split('.').map(Number)
  for (let index = 0; index < Math.max(a.length, b.length); index++) {
    const difference = (a[index] ?? 0) - (b[index] ?? 0)
    if (difference) return Math.sign(difference)
  }
  return 0
}

function classifyExit(input: {
  intent: 'run' | 'shutdown' | 'terminate'
  forcedReason: string | null
  exitCode: number | null
  oomKilled: boolean
  waitMessage: string | null
  limitMs: number
  durationMs: number
}): { outcome: SandboxOutcome; reason?: string } {
  const { intent, forcedReason, exitCode, oomKilled, waitMessage } = input
  if (oomKilled) return { outcome: 'oom', reason: waitMessage ?? '容器被内存上限终止' }
  if (intent === 'terminate') {
    return forcedReason === 'deadline-exceeded' ? { outcome: 'timeout', reason: forcedReason } : { outcome: 'terminated', reason: forcedReason ?? undefined }
  }
  if (forcedReason) return { outcome: 'terminated', reason: forcedReason }
  /* 容器内的 timeout 到点：124 为收到 TERM 后退出，137 为宽限后被 KILL */
  const timedOut = exitCode === 124 || (exitCode === 137 && input.durationMs >= input.limitMs - 1000)
  if (timedOut) return { outcome: 'timeout', reason: '容器内计时器到点' }
  if (exitCode === 0) return { outcome: 'exited' }
  return { outcome: 'error', reason: `Pi 以退出码 ${exitCode ?? '未知'} 结束` }
}

export class SandboxHandle {
  readonly runId: string
  readonly attempt: string
  readonly containerId: string
  readonly containerName: string
  readonly workVolume: string
  readonly limits: SandboxLimits
  /** 启动前通过核对的 Docker 实际配置 */
  readonly inspect: ContainerInspect
  readonly rpc: PiRpcChannel
  readonly done: Promise<SandboxResult>
  readonly startedAt: Date
  session: { sessionId: string; sessionFile: string } | null = null
  attestation: { uid: string; kernel: string; nodeVersion: string } | null = null
  hostLimits: HostCgroupLimits | null = null

  private readonly worker: SandboxWorker
  private readonly streams: AttachedStreams
  private readonly events = new Set<(event: RpcEvent) => void>()
  private intent: 'run' | 'shutdown' | 'terminate' = 'run'
  private forcedReason: string | null = null
  private stderrChunks: Buffer[] = []
  private stderrBytes = 0

  constructor(
    worker: SandboxWorker,
    params: { runId: string; attempt: string; containerId: string; limits: SandboxLimits; streams: AttachedStreams; inspect: ContainerInspect },
  ) {
    this.worker = worker
    this.runId = params.runId
    this.attempt = params.attempt
    this.containerId = params.containerId
    this.limits = params.limits
    this.inspect = params.inspect
    this.streams = params.streams
    this.containerName = resourceNames(params.runId).container
    this.workVolume = resourceNames(params.runId).workVolume
    this.startedAt = new Date()
    this.rpc = new PiRpcChannel(params.streams)
    this.rpc.onEvent = (event) => {
      for (const listener of this.events) listener(event)
    }
    this.rpc.onFatal = () => {
      void this.terminate('protocol-error')
    }
    void this.drainStderr()
    this.done = this.watch()
  }

  onEvent(listener: (event: RpcEvent) => void): () => void {
    this.events.add(listener)
    return () => {
      this.events.delete(listener)
    }
  }

  stderrTail(): string {
    return Buffer.concat(this.stderrChunks).toString('utf8')
  }

  private async drainStderr() {
    try {
      for await (const chunk of this.streams.stderr) {
        this.stderrChunks.push(chunk)
        this.stderrBytes += chunk.length
        while (this.stderrBytes > STDERR_TAIL_BYTES && this.stderrChunks.length > 1) {
          this.stderrBytes -= this.stderrChunks[0].length
          this.stderrChunks.shift()
        }
      }
    } catch {
      /* stderr 只留末尾用于诊断，读取失败不影响生命周期 */
    }
  }

  /* 就绪 = Pi 应答 get_state 且会话落在 /work，并且容器内实际是非 root、gVisor 内核、登记的 Node 版本 */
  async waitReady(): Promise<void> {
    const timeoutMs = this.worker.readyTimeoutMs
    let state: PiState
    try {
      state = await this.rpc.request({ type: 'get_state' }, { timeoutMs })
    } catch (error) {
      throw new SandboxError('PI_NOT_READY', `Pi 未在 ${timeoutMs} 毫秒内回应 get_state：${errorMessage(error)}`, null, { cause: error })
    }
    if (typeof state?.sessionId !== 'string' || !state.sessionId || typeof state.sessionFile !== 'string' || !state.sessionFile.startsWith(`${SESSION_DIR}/`)) {
      throw new SandboxError('PI_NOT_READY', 'Pi 的就绪回报缺少会话 ID，或会话文件不在 /work 下')
    }
    this.session = { sessionId: state.sessionId, sessionFile: state.sessionFile }
    let probe: PiBashResult
    try {
      probe = await this.rpc.bash(`printf '%s|%s|%s\\n' "$(id -u)" "$(uname -r)" "$(node --version)"`, { timeoutMs, excludeFromContext: true })
    } catch (error) {
      throw new SandboxError('PI_NOT_READY', `Pi 就绪后无法在沙箱内执行命令：${errorMessage(error)}`, null, { cause: error })
    }
    const [uid, kernel, nodeVersion] = probe.output.trim().split('|')
    this.attestation = { uid, kernel, nodeVersion }
    const expectedUid = this.worker.image.user.split(':')[0]
    if (!uid || uid === '0' || uid !== expectedUid) {
      throw new SandboxError('RUNTIME_MISMATCH', `沙箱内进程 uid 为 ${uid || '未知'}，应为 ${expectedUid}`)
    }
    if (!RUNTIME_KERNEL_PATTERN.test(kernel ?? '')) {
      throw new SandboxError('RUNTIME_MISMATCH', `沙箱内核为 ${kernel || '未知'}，不是 gVisor（runsc）`)
    }
    if (nodeVersion.replace(/^v/, '') !== this.worker.image.nodeVersion.replace(/^v/, '')) {
      throw new SandboxError('RUNTIME_MISMATCH', `沙箱内 Node 为 ${nodeVersion || '未知'}，登记为 ${this.worker.image.nodeVersion}`)
    }
    const running = await this.worker.docker.inspectContainer(this.containerId)
    this.hostLimits = await readHostLimits(running.State.Pid)
  }

  /* 容器退出即收尾：读退出状态、释放本次尝试自己创建的容器与工作卷。done 不会 reject，失败写入结果。 */
  private async watch(): Promise<SandboxResult> {
    const limitMs = this.limits.maxDurationSec * 1000
    /* 容器内的计时器是第一道时限；Worker 只在它到点后仍在运行时兜底强制停止 */
    /* unref：定时器本身不维持进程存活；进程若已没有其他活动，沙箱的 attach 连接也已不在 */
    const guard = setTimeout(() => {
      void this.terminate('deadline-exceeded')
    }, limitMs + this.worker.deadlineGraceMs)
    guard.unref()
    let exitCode: number | null = null
    let waitMessage: string | null = null
    let waitError: unknown = null
    try {
      const waited = await this.worker.docker.waitContainer(this.containerId)
      exitCode = waited.StatusCode
      waitMessage = waited.Error?.Message || null
    } catch (error) {
      waitError = error
      await this.stopContainer().catch(() => undefined)
    }
    clearTimeout(guard)
    const state = await this.worker.docker.inspectContainer(this.containerId).then((item) => item.State, () => null)
    if (state?.Running) {
      await this.stopContainer().catch(() => undefined)
    }
    const endedAt = new Date()
    let reclaimed = { containers: 0, volumes: 0 }
    const notes: string[] = []
    try {
      reclaimed = await this.worker.release(this.runId, this.attempt, this.containerId)
    } catch (error) {
      notes.push(`回收未完成：${errorMessage(error)}`)
    }
    if (waitError) notes.push(`读取退出状态失败：${errorMessage(waitError)}`)
    const classified = classifyExit({
      intent: this.intent,
      forcedReason: this.forcedReason,
      exitCode,
      oomKilled: Boolean(state?.OOMKilled),
      waitMessage,
      limitMs,
      durationMs: endedAt.getTime() - this.startedAt.getTime(),
    })
    if (state && exitCode === null) exitCode = state.ExitCode
    return {
      ...classified,
      exitCode,
      oomKilled: Boolean(state?.OOMKilled),
      startedAt: this.startedAt.toISOString(),
      endedAt: endedAt.toISOString(),
      durationMs: endedAt.getTime() - this.startedAt.getTime(),
      ...(classified.reason || notes.length ? { reason: [classified.reason, ...notes].filter(Boolean).join('；') } : {}),
      reclaimed,
    }
  }

  private async stopContainer(): Promise<void> {
    await this.worker.docker.stopContainer(this.containerId, STOP_TIMEOUT_SEC)
  }

  /* 有序结束：关闭 Pi 的 stdin，等它写完会话自行退出；宽限后仍在运行则强制停止 */
  async shutdown(options: { graceMs?: number } = {}): Promise<SandboxResult> {
    if (this.intent === 'run') {
      this.intent = 'shutdown'
      this.rpc.end()
      setTimeout(() => {
        if (this.intent === 'shutdown') void this.terminate('shutdown-grace')
      }, options.graceMs ?? SHUTDOWN_GRACE_MS).unref()
    }
    return this.done
  }

  /* 强制结束：向整个容器发 SIGTERM，宽限后 SIGKILL，沙箱内全部子进程一并停止 */
  async terminate(reason = 'terminated'): Promise<SandboxResult> {
    if (this.intent !== 'terminate') {
      this.intent = 'terminate'
      this.forcedReason = reason
      await this.stopContainer().catch(() => undefined)
    }
    return this.done
  }

  private workPath(target: string): string {
    const normalized = path.posix.join(WORK_DIR, target)
    if (!normalized.startsWith(`${WORK_DIR}/`) && normalized !== WORK_DIR) {
      throw new SandboxError('INVALID_SPEC', `只允许读取 /work 之内的路径：${target}`)
    }
    return normalized
  }

  /* 以下两个方法只在容器运行期间有效：工作卷是 tmpfs，容器停止后被卸载 */
  async listWork(directory = ''): Promise<string[]> {
    const archive = await this.worker.docker.getArchive(this.containerId, this.workPath(directory))
    return readTar(archive).map((entry) => entry.name)
  }

  async readWorkFile(target: string): Promise<Buffer | null> {
    try {
      const archive = await this.worker.docker.getArchive(this.containerId, this.workPath(target))
      return readTar(archive).find((entry) => entry.type === 'file')?.data ?? null
    } catch (error) {
      if (isNotFound(error)) return null
      throw error
    }
  }

  /* 真实 Pi 进程在沙箱内执行的 shell，不经模型；供受信侧探针与后续网关使用 */
  bash(command: string, options: RpcRequestOptions & { excludeFromContext?: boolean } = {}): Promise<PiBashResult> {
    return this.rpc.bash(command, options)
  }
}

export class SandboxWorker {
  readonly docker: DockerClient
  readonly image: ImageLock
  readonly runtime = MANAGED_RUNTIME
  readonly inputsRoot: string
  readonly readyTimeoutMs: number
  readonly deadlineGraceMs: number

  constructor(options: SandboxWorkerOptions) {
    /* 生产 Worker 只允许 runsc：其他值哪怕 Docker 已注册（例如 runc）也在这里拒绝，此时还没有碰过 Docker */
    if (options.runtime !== undefined && options.runtime !== MANAGED_RUNTIME) {
      throw new SandboxError('INVALID_SPEC', `Worker 只允许运行时 ${MANAGED_RUNTIME}，收到 ${String(options.runtime)}`)
    }
    this.image = parseImageLock(options.image)
    this.docker = options.docker ?? new DockerClient({ socketPath: options.socketPath })
    this.inputsRoot = options.inputsRoot ?? ''
    this.readyTimeoutMs = options.readyTimeoutMs ?? 60_000
    this.deadlineGraceMs = options.deadlineGraceMs ?? DEFAULT_DEADLINE_GRACE_MS
  }

  /* 启动前的三道门：Docker 可达且 API 版本够、运行时已注册、镜像与本机登记逐项相符 */
  private async checkHost(): Promise<{ version: { ApiVersion: string; Version: string }; info: DockerInfo; image: ImageInspect }> {
    const version = await this.docker.version()
    if (compareVersion(version.ApiVersion, API_VERSION.slice(1)) < 0) {
      throw new SandboxError('DOCKER_API', `Docker API 版本 ${version.ApiVersion} 低于 Worker 使用的 ${API_VERSION}`)
    }
    const info = await this.docker.info()
    if (!info.Runtimes?.[this.runtime]) {
      throw new SandboxError(
        'RUNTIME_UNAVAILABLE',
        `Docker 未注册运行时 ${this.runtime}（已注册：${Object.keys(info.Runtimes ?? {}).join(', ') || '无'}）。Worker 不会回退到其他运行时。`,
      )
    }
    const image = await this.docker.inspectImage(this.image.id).catch((error: unknown) => {
      if (isNotFound(error)) {
        throw new SandboxError('IMAGE_LOCK', `登记的镜像 ${this.image.id} 不在本机，先执行 npm --prefix sandbox-v2 run build:image`, null, { cause: error })
      }
      throw error
    })
    const problems = verifyImage(image, this.image, info.Architecture)
    if (problems.length) throw new SandboxError('IMAGE_LOCK', '登记的镜像与 Docker 实际内容不符', problems)
    return { version, info, image }
  }

  async preflight(): Promise<PreflightReport> {
    const { version, info, image } = await this.checkHost()
    return {
      docker: {
        version: version.Version,
        apiVersion: version.ApiVersion,
        runtime: this.runtime,
        runtimePath: info.Runtimes?.[this.runtime]?.path ?? '',
        defaultRuntime: info.DefaultRuntime,
      },
      image: { id: image.Id, piVersion: this.image.piVersion, nodeVersion: this.image.nodeVersion, baseDigest: this.image.baseDigest, size: image.Size },
    }
  }

  /* 只核对本机镜像与登记是否相符，不检查运行时；供 verify-image 使用 */
  async registryProblems(): Promise<string[]> {
    const info = await this.docker.info()
    const image = await this.docker.inspectImage(this.image.id).catch((error: unknown) => {
      if (isNotFound(error)) return null
      throw error
    })
    if (!image) return [`登记的镜像 ${this.image.id} 不在本机`]
    return verifyImage(image, this.image, info.Architecture)
  }

  /* 只释放本次尝试自己创建的资源：容器按本次拿到的 ID 删除，工作卷必须带本次的 attempt 标签。
     启动失败与正常收尾都走这里，不会误删同一 runId 下别的执行的资源。 */
  async release(runId: string, attempt: string, containerId: string | null): Promise<{ containers: number; volumes: number }> {
    let containers = 0
    if (containerId) {
      try {
        await removeWithRetry(() => this.docker.removeContainer(containerId))
        containers = 1
      } catch (error) {
        if (!isNotFound(error)) throw error
      }
    }
    const name = resourceNames(runId).workVolume
    const volume = await this.docker.inspectVolume(name).catch((error: unknown) => {
      if (isNotFound(error)) return null
      throw error
    })
    let volumes = 0
    if (volume) {
      if (volume.Labels?.[LABEL_ATTEMPT] !== attempt) {
        throw new SandboxError('RECLAIM_FAILED', `工作卷 ${name} 不属于本次执行，未删除`)
      }
      await removeWithRetry(() => this.docker.removeVolume(name))
      volumes = 1
    }
    return { containers, volumes }
  }

  /* 显式回收入口（运维或后续任务服务调用）：删除带本次运行标签的全部容器与工作卷。
     启动失败路径不调用它，避免删掉同一 runId 下正在运行的别的执行。 */
  async list(runId: string): Promise<{ containers: string[]; volumes: string[] }> {
    assertRunId(runId)
    const filters = runFilters(runId)
    const containers = await this.docker.listContainers(filters)
    const volumes = await this.docker.listVolumes(filters)
    return { containers: containers.map((item) => `${item.Names?.[0] ?? item.Id.slice(0, 12)}(${item.State})`), volumes: (volumes.Volumes ?? []).map((item) => item.Name) }
  }

  /* 回收入口：只处理带本次运行标签的资源，可重复调用 */
  async reclaim(runId: string): Promise<ReclaimReport> {
    assertRunId(runId)
    const filters = runFilters(runId)
    const containers = (await this.docker.listContainers(filters)).map((item) => item.Id)
    for (const id of containers) await removeWithRetry(() => this.docker.removeContainer(id))
    const volumes = ((await this.docker.listVolumes(filters)).Volumes ?? []).map((item) => item.Name)
    for (const name of volumes) await removeWithRetry(() => this.docker.removeVolume(name))
    const left = (await this.docker.listContainers(filters)).length + ((await this.docker.listVolumes(filters)).Volumes ?? []).length
    if (left) throw new SandboxError('RECLAIM_FAILED', `run ${runId} 回收后仍有 ${left} 个资源残留`)
    return { containers, volumes }
  }

  /* 启动一次执行。同一 runId 在任何 Worker 上同时最多成功一个：工作卷名在一次运行内唯一，
     Docker 对同名卷的创建串行执行，卷已存在时拿到的是已有对象；它不带本次的 attempt 标签，
     就说明这次运行已被别的执行占用或留有未回收资源，此时直接拒绝，不触碰对方的资源。 */
  async start(spec: SandboxRunSpec): Promise<SandboxHandle> {
    const runId = assertRunId(spec?.runId ?? '')
    const limits = normalizeLimits(spec.limits)
    const inputs: ResolvedInput[] = await resolveInputs(spec.inputs ?? [], this.inputsRoot)
    const host = await this.checkHost()
    const attempt = randomBytes(12).toString('hex')
    const names = resourceNames(runId)
    const volumeRequest = workVolumeRequest(runId, limits, this.image.user, attempt)
    let volume: VolumeInfo
    try {
      volume = await this.docker.createVolume(volumeRequest)
    } catch (error) {
      throw new SandboxError(
        'RUN_EXISTS',
        `run ${runId} 的工作卷已存在且与本次请求不一致，可能仍有未回收资源（${errorMessage(error)}）。不会动它，确认后执行 reclaim`,
        null,
        { cause: error },
      )
    }
    const claimed = await this.docker.inspectVolume(names.workVolume).catch((error: unknown) => {
      if (isNotFound(error)) return volume
      throw error
    })
    if (claimed.Labels?.[LABEL_ATTEMPT] !== attempt) {
      throw new SandboxError(
        'RUN_EXISTS',
        `run ${runId} 已有其他执行或未回收资源（工作卷 ${names.workVolume}）。不会动它，确认后执行 reclaim`,
        { volume: names.workVolume },
      )
    }
    const volumeProblems = verifyWorkVolume(claimed, volumeRequest)
    if (volumeProblems.length) {
      await this.release(runId, attempt, null).catch(() => undefined)
      throw new SandboxError('VERIFY_FAILED', 'Docker 回报的工作卷与约定不符', volumeProblems)
    }

    let streams: AttachedStreams | null = null
    let containerId: string | null = null
    try {
      const built = buildCreateRequest({
        runId,
        imageRef: imageReference(this.image),
        imageId: this.image.id,
        entrypoint: this.image.entrypoint,
        imageEnv: host.image.Config.Env ?? [],
        imageLabels: host.image.Config.Labels ?? {},
        user: this.image.user,
        attempt,
        limits,
        inputs,
      })
      containerId = (await this.docker.createContainer(built.body)).Id
      const inspect = await this.docker.inspectContainer(containerId)
      const problems = verifyContainer(inspect, built.expected)
      if (problems.length) throw new SandboxError('VERIFY_FAILED', 'Docker 侧核对未通过，已拒绝启动', problems)
      /* 先 attach 再启动，Pi 的第一行输出不会丢 */
      streams = await this.docker.attach(containerId)
      await this.docker.startContainer(containerId)
      /* 网络接入等字段要到启动后才有实际值，补核一次再进入就绪等待 */
      const running = await this.docker.inspectContainer(containerId)
      const runningProblems = verifyRunningContainer(running, built.expected)
      if (runningProblems.length) throw new SandboxError('VERIFY_FAILED', '容器启动后的 Docker 状态核对未通过', runningProblems)
      const handle = new SandboxHandle(this, { runId, attempt, containerId, limits, streams, inspect })
      try {
        await handle.waitReady()
      } catch (error) {
        await handle.terminate('not-ready')
        throw error
      }
      return handle
    } catch (error) {
      streams?.destroy()
      const released = await this.release(runId, attempt, containerId).then(() => true, () => false)
      throw remapStartError(error, released)
    }
  }
}

async function removeWithRetry(remove: () => Promise<void>): Promise<void> {
  for (let attempt = 0; ; attempt++) {
    try {
      return await remove()
    } catch (error) {
      const busy = error instanceof DockerApiError && (error.status === 409 || error.status === 500)
      if (!busy || attempt >= 9) throw error
      await new Promise((resolve) => setTimeout(resolve, 300))
    }
  }
}

function remapStartError(error: unknown, released: boolean): unknown {
  const suffix = released ? '' : '；且本次创建的资源未能全部释放，请核对后执行 reclaim'
  if (error instanceof DockerApiError) {
    /* 同名容器已存在：这次运行被别的执行占着 */
    if (error.status === 409) {
      return new SandboxError('RUN_EXISTS', `run 的容器名已被占用，可能仍有未回收资源（${error.message}）`, error.details, { cause: error })
    }
    /* Docker 的通用前缀带 runtime 字样，这里只认运行时名称本身，避免把其他启动错误误报成运行时故障 */
    if (error.message.toLowerCase().includes(MANAGED_RUNTIME)) {
      return new SandboxError(
        'RUNTIME_UNAVAILABLE',
        `运行时 ${MANAGED_RUNTIME} 已注册但无法启动容器：${error.message}。Worker 不会回退到其他运行时${suffix}`,
        error.details,
        { cause: error },
      )
    }
    return new SandboxError('START_FAILED', `容器未能启动：${error.message}${suffix}`, error.details, { cause: error })
  }
  if (error instanceof SandboxError) {
    return released ? error : new SandboxError(error.code, `${error.message}${suffix}`, error.details, { cause: error })
  }
  return new SandboxError('START_FAILED', `启动沙箱时出现未预期错误：${errorMessage(error)}${suffix}`, null, { cause: error })
}
