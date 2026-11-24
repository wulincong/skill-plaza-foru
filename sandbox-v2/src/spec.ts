/* 沙箱规格：资源命名、限额、输入挂载校验、容器创建请求，以及创建后从 Docker 侧逐项核对的规则。
   创建请求和核对期望由同一段代码生成，核对针对 Docker 实际回报的配置而不是请求本身。 */

import { realpath, stat } from 'node:fs/promises'
import path from 'node:path'
import { SandboxError } from './errors.ts'
import type { ContainerInspect, VolumeInfo } from './docker.ts'

export const LABEL_MANAGED = 'plaza.sandbox.managed'
export const LABEL_RUN = 'plaza.sandbox.run'
export const LABEL_ATTEMPT = 'plaza.sandbox.attempt'
export const MANAGED_VALUE = 'v2'
export const MANAGED_RUNTIME = 'runsc'
export const RUNTIME_KERNEL_PATTERN = /gvisor/i
export const RUN_ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,62}$/
export const ATTEMPT_PATTERN = /^[0-9a-f]{24}$/
/* 宿主 cgroup 的进程数与沙箱内不是一比一（本机 systrap 实测）：
   gVisor 自身约占 37–50 个宿主任务，沙箱内每个线程约占 2 个（沙箱线程加配对的 stub 线程）。
   沙箱内上限须满足 SANDBOX_TASK_HOST_COST × tasks + SENTRY_TASK_HEADROOM ≤ pids，
   进程数才会先在沙箱内被拒，而不是等到宿主上限让整个沙箱退出。 */
export const SENTRY_TASK_HEADROOM = 64
export const SANDBOX_TASK_HOST_COST = 2
export const WORK_DIR = '/work'
export const INPUT_DIR = '/input'
export const SESSION_DIR = '/work/.pi-sessions'
export const STOP_TIMEOUT_SEC = 10
const NOFILE_SOFT = 4096
const NOFILE_HARD = 8192
const MAX_INPUTS = 16
const TARGET_PATTERN = /^\/input\/[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/

export interface SandboxLimits {
  cpus: number
  memoryMiB: number
  /** 宿主 cgroup 的 pids.max：沙箱内全部线程加 gVisor 自身线程，触顶时整个沙箱退出 */
  pids: number
  /** 沙箱内的 RLIMIT_NPROC：触顶时新进程被拒，沙箱其余部分继续运行 */
  tasks: number
  maxDurationSec: number
  tmpMiB: number
  workMiB: number
  workFiles: number
}

export const DEFAULT_LIMITS: SandboxLimits = {
  cpus: 1,
  memoryMiB: 512,
  pids: 256,
  tasks: 96,
  maxDurationSec: 300,
  tmpMiB: 16,
  workMiB: 256,
  workFiles: 2048,
}

/* 单个沙箱可申请的上限；超过说明调用方要的不是沙箱，应回到设计层重新评估 */
export const LIMIT_CEILINGS: SandboxLimits = {
  cpus: 4,
  memoryMiB: 4096,
  pids: 1024,
  tasks: (1024 - SENTRY_TASK_HEADROOM) / SANDBOX_TASK_HOST_COST,
  maxDurationSec: 6 * 3600,
  tmpMiB: 256,
  workMiB: 2048,
  workFiles: 65536,
}

const LIMIT_FLOORS: SandboxLimits = {
  cpus: 0.1,
  memoryMiB: 64,
  pids: SENTRY_TASK_HEADROOM + SANDBOX_TASK_HOST_COST * 16,
  tasks: 16,
  maxDurationSec: 1,
  tmpMiB: 1,
  workMiB: 1,
  workFiles: 8,
}

const INTEGER_KEYS: (keyof SandboxLimits)[] = ['memoryMiB', 'pids', 'tasks', 'maxDurationSec', 'tmpMiB', 'workMiB', 'workFiles']

export function normalizeLimits(partial: Partial<SandboxLimits> = {}): SandboxLimits {
  const merged = { ...DEFAULT_LIMITS }
  for (const [key, value] of Object.entries(partial) as [keyof SandboxLimits, unknown][]) {
    if (!(key in DEFAULT_LIMITS)) throw new SandboxError('INVALID_SPEC', `未知限额项 ${key}`)
    if (value === undefined) continue
    merged[key] = value as never
  }
  /* 没有显式给出沙箱内进程上限时，让它随宿主上限一起下调，始终先于宿主上限触发 */
  if (partial.tasks === undefined) {
    merged.tasks = Math.min(merged.tasks, Math.floor((merged.pids - SENTRY_TASK_HEADROOM) / SANDBOX_TASK_HOST_COST))
  }
  for (const key of Object.keys(DEFAULT_LIMITS) as (keyof SandboxLimits)[]) {
    const value = merged[key]
    if (typeof value !== 'number' || !Number.isFinite(value)) throw new SandboxError('INVALID_SPEC', `限额 ${key} 必须是数字`)
    if (INTEGER_KEYS.includes(key) && !Number.isInteger(value)) throw new SandboxError('INVALID_SPEC', `限额 ${key} 必须是整数`)
    if (value < LIMIT_FLOORS[key] || value > LIMIT_CEILINGS[key]) {
      throw new SandboxError('INVALID_SPEC', `限额 ${key}=${value} 超出允许范围 ${LIMIT_FLOORS[key]}–${LIMIT_CEILINGS[key]}`)
    }
  }
  if (merged.tasks * SANDBOX_TASK_HOST_COST + SENTRY_TASK_HEADROOM > merged.pids) {
    throw new SandboxError(
      'INVALID_SPEC',
      `沙箱内进程上限 tasks=${merged.tasks} 过高：每个沙箱线程约占 ${SANDBOX_TASK_HOST_COST} 个宿主任务，需满足 ${SANDBOX_TASK_HOST_COST} × tasks + ${SENTRY_TASK_HEADROOM} ≤ pids=${merged.pids}`,
    )
  }
  merged.cpus = Math.round(merged.cpus * 1000) / 1000
  return merged
}

export function assertRunId(runId: string): string {
  if (typeof runId !== 'string' || !RUN_ID_PATTERN.test(runId)) {
    throw new SandboxError('INVALID_SPEC', `runId 只能是 1–63 位小写字母、数字和连字符：${String(runId)}`)
  }
  return runId
}

export function resourceNames(runId: string): { container: string; workVolume: string } {
  return { container: `plaza-sb-${runId}`, workVolume: `plaza-sb-${runId}-work` }
}

/* attempt 标识一次启动尝试：工作卷与容器都带上它，失败时只清理本次自己创建的资源 */
export function assertAttempt(attempt: string): string {
  if (typeof attempt !== 'string' || !ATTEMPT_PATTERN.test(attempt)) {
    throw new SandboxError('INVALID_SPEC', 'attempt 必须是 24 位十六进制')
  }
  return attempt
}

export function runLabels(runId: string, attempt: string): Record<string, string> {
  return { [LABEL_MANAGED]: MANAGED_VALUE, [LABEL_RUN]: runId, [LABEL_ATTEMPT]: assertAttempt(attempt) }
}

export function runFilters(runId: string): Record<string, string[]> {
  return { label: [`${LABEL_MANAGED}=${MANAGED_VALUE}`, `${LABEL_RUN}=${runId}`] }
}

export function runEnvironment(runId: string, limits: SandboxLimits): string[] {
  return [`PI_SESSION_DIR=${SESSION_DIR}`, `PI_SESSION_NAME=${runId}`, `PI_MAX_SECONDS=${limits.maxDurationSec}`]
}

export interface WorkVolumeRequest {
  Name: string
  Driver: 'local'
  Labels: Record<string, string>
  DriverOpts: Record<string, string>
}

export function workVolumeRequest(runId: string, limits: SandboxLimits, user: string, attempt: string): WorkVolumeRequest {
  const [uid, gid] = user.split(':')
  return {
    Name: resourceNames(runId).workVolume,
    Driver: 'local',
    Labels: runLabels(runId, attempt),
    /* 宿主内核 tmpfs：字节与 inode 上限都在文件创建时强制，不依赖现有磁盘的配额功能 */
    DriverOpts: {
      type: 'tmpfs',
      device: 'tmpfs',
      o: `size=${limits.workMiB}m,nr_inodes=${limits.workFiles},mode=0700,uid=${uid},gid=${gid}`,
    },
  }
}

export function verifyWorkVolume(volume: VolumeInfo, expected: WorkVolumeRequest): string[] {
  const problems: string[] = []
  if (volume.Name !== expected.Name) problems.push(`工作卷名为 ${volume.Name}，应为 ${String(expected.Name)}`)
  if (volume.Driver !== 'local') problems.push(`工作卷驱动为 ${volume.Driver}，应为 local`)
  if (JSON.stringify(sortedEntries(volume.Options)) !== JSON.stringify(sortedEntries(expected.DriverOpts))) {
    problems.push(`工作卷选项为 ${JSON.stringify(volume.Options)}，应为 ${JSON.stringify(expected.DriverOpts)}`)
  }
  if (JSON.stringify(sortedEntries(volume.Labels)) !== JSON.stringify(sortedEntries(expected.Labels))) {
    problems.push('工作卷标签与本次运行不符')
  }
  return problems
}

export interface SandboxInput {
  hostPath: string
  target: string
}

export interface ResolvedInput {
  source: string
  target: string
  kind: 'directory' | 'file'
}

function isInside(root: string, candidate: string): boolean {
  const relative = path.relative(root, candidate)
  return relative !== '' && !relative.startsWith('..') && !path.isAbsolute(relative)
}

/* 只读输入只能来自 Worker 显式配置的受信目录。空值会被 path.resolve 解释成当前工作目录，
   也就是把仓库本身变成可挂载范围，必须在解析之前拒绝 */
export function assertInputsRoot(inputsRoot: string): string {
  if (typeof inputsRoot !== 'string' || !inputsRoot.trim()) {
    throw new SandboxError('INVALID_SPEC', '要挂载输入，必须在 Worker 配置里显式给出受信输入根目录 inputsRoot')
  }
  if (inputsRoot !== path.resolve(inputsRoot) || path.parse(inputsRoot).root === inputsRoot) {
    throw new SandboxError('INVALID_SPEC', `inputsRoot 必须是规范化且不是文件系统根的绝对路径：${inputsRoot}`)
  }
  return inputsRoot
}

/* 只读输入必须位于受信的输入根目录之内（按真实路径比对，拒绝符号链接或 .. 逃逸） */
export async function resolveInputs(inputs: SandboxInput[], inputsRoot: string): Promise<ResolvedInput[]> {
  if (!Array.isArray(inputs)) throw new SandboxError('INVALID_SPEC', 'inputs 必须是数组')
  if (!inputs.length) return []
  if (inputs.length > MAX_INPUTS) throw new SandboxError('INVALID_SPEC', `单个沙箱最多挂载 ${MAX_INPUTS} 个输入`)
  const root = await realpath(assertInputsRoot(inputsRoot)).catch(() => {
    throw new SandboxError('INVALID_SPEC', `输入根目录不存在：${inputsRoot}`)
  })
  const resolved: ResolvedInput[] = []
  const targets = new Set<string>()
  for (const input of inputs) {
    if (!input || !TARGET_PATTERN.test(input.target ?? '')) {
      throw new SandboxError('INVALID_SPEC', `输入目标路径只能是 /input/<名称>：${String(input?.target)}`)
    }
    if (targets.has(input.target)) throw new SandboxError('INVALID_SPEC', `输入目标重复：${input.target}`)
    targets.add(input.target)
    if (!path.isAbsolute(input.hostPath ?? '')) throw new SandboxError('INVALID_SPEC', `输入路径必须是绝对路径：${String(input.hostPath)}`)
    let source: string
    try {
      source = await realpath(input.hostPath)
    } catch {
      throw new SandboxError('INVALID_SPEC', `输入不存在或无法解析：${input.hostPath}`)
    }
    if (!isInside(root, source)) throw new SandboxError('INVALID_SPEC', `输入不在输入根目录内：${input.hostPath}`)
    const info = await stat(source)
    const kind = info.isDirectory() ? 'directory' : info.isFile() ? 'file' : null
    if (!kind) throw new SandboxError('INVALID_SPEC', `输入不是普通文件或目录：${input.hostPath}`)
    const needed = 0o004 | (kind === 'directory' ? 0o001 : 0)
    if ((info.mode & needed) !== needed) {
      throw new SandboxError('INVALID_SPEC', `输入需对沙箱用户可读（o+rX）：${input.hostPath}`)
    }
    resolved.push({ source, target: input.target, kind })
  }
  return resolved
}

export interface CreateRequestInput {
  runId: string
  imageRef: string
  imageId: string
  entrypoint: string[]
  imageEnv: string[]
  imageLabels: Record<string, string>
  user: string
  attempt: string
  limits: SandboxLimits
  inputs: ResolvedInput[]
}

export interface ExpectedContainer {
  imageRef: string
  imageId: string
  imageLabels: Record<string, string>
  entrypoint: string[]
  user: string
  runtime: string
  env: string[]
  mounts: string[]
  tmpfs: Record<string, string>
  pids: number
  tasks: number
  memory: number
  nanoCpus: number
  labels: Record<string, string>
}

function mountKey(type: string, source: string, target: string, rw: boolean): string {
  return `${type}:${source}:${target}:${rw ? 'rw' : 'ro'}`
}

export function buildCreateRequest(input: CreateRequestInput): { body: Record<string, unknown>; expected: ExpectedContainer } {
  const { runId, limits } = input
  const memory = limits.memoryMiB * 1024 * 1024
  const nanoCpus = Math.round(limits.cpus * 1e9)
  const tmpfs = { '/tmp': `rw,nosuid,nodev,noexec,size=${limits.tmpMiB}m,mode=1777` }
  const labels = runLabels(runId, input.attempt)
  const body = {
    Image: input.imageRef,
    Name: resourceNames(runId).container,
    User: input.user,
    Env: runEnvironment(runId, limits),
    Cmd: [],
    WorkingDir: WORK_DIR,
    Labels: labels,
    Hostname: 'sandbox',
    Tty: false,
    OpenStdin: true,
    StdinOnce: true,
    StopSignal: 'SIGTERM',
    StopTimeout: STOP_TIMEOUT_SEC,
    HostConfig: {
      Runtime: MANAGED_RUNTIME,
      NetworkMode: 'none',
      ReadonlyRootfs: true,
      Privileged: false,
      CapDrop: ['ALL'],
      CapAdd: [],
      SecurityOpt: ['no-new-privileges:true'],
      Devices: [],
      DeviceRequests: [],
      Mounts: [
        { Type: 'volume', Source: resourceNames(runId).workVolume, Target: WORK_DIR, ReadOnly: false },
        ...input.inputs.map((item) => ({
          Type: 'bind',
          Source: item.source,
          Target: item.target,
          ReadOnly: true,
          BindOptions: { Propagation: 'rprivate' },
        })),
      ],
      Tmpfs: tmpfs,
      PidsLimit: limits.pids,
      Memory: memory,
      MemorySwap: memory,
      MemorySwappiness: 0,
      NanoCpus: nanoCpus,
      Ulimits: [
        { Name: 'nofile', Soft: NOFILE_SOFT, Hard: NOFILE_HARD },
        { Name: 'nproc', Soft: limits.tasks, Hard: limits.tasks },
      ],
      IpcMode: 'private',
      CgroupnsMode: 'private',
      AutoRemove: false,
      Init: false,
      /* 输出只走 attach 流，不落盘到 Docker 日志 */
      LogConfig: { Type: 'none', Config: {} },
      RestartPolicy: { Name: 'no', MaximumRetryCount: 0 },
      OomKillDisable: false,
    },
  }
  const expected: ExpectedContainer = {
    imageRef: input.imageRef,
    imageId: input.imageId,
    imageLabels: input.imageLabels,
    entrypoint: input.entrypoint,
    user: input.user,
    runtime: MANAGED_RUNTIME,
    env: [...input.imageEnv, ...runEnvironment(runId, limits)].sort(),
    mounts: [
      mountKey('volume', resourceNames(runId).workVolume, WORK_DIR, true),
      ...input.inputs.map((item) => mountKey('bind', item.source, item.target, false)),
    ].sort(),
    tmpfs,
    pids: limits.pids,
    tasks: limits.tasks,
    memory,
    nanoCpus,
    labels,
  }
  return { body, expected }
}

export function sameStringList(actual: unknown, expected: string[]): boolean {
  return Array.isArray(actual) && JSON.stringify([...actual].sort()) === JSON.stringify([...expected].sort())
}

/* 入口是 argv：元素相同但顺序不同，含义就变了，必须按原顺序逐项比较 */
export function sameOrderedStringList(actual: unknown, expected: string[]): boolean {
  return Array.isArray(actual) && JSON.stringify(actual) === JSON.stringify(expected)
}

export function sortedEntries(value: Record<string, unknown> | null | undefined): [string, unknown][] {
  return Object.entries(value ?? {}).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
}

function isBlankList(value: unknown[] | null | undefined): boolean {
  return !value || value.length === 0
}

/* 从 Docker 实际回报逐项核对：运行时、挂载清单与读写权限、降权设置、限额、环境与标签 */
export function verifyContainer(inspect: ContainerInspect, expected: ExpectedContainer): string[] {
  const problems: string[] = []
  const need = (ok: boolean, message: string) => {
    if (!ok) problems.push(message)
  }
  const hc = inspect.HostConfig
  const config = inspect.Config
  need(inspect.Image === expected.imageId, `镜像 ID 为 ${inspect.Image}，应为 ${expected.imageId}`)
  need(config.Image === expected.imageRef, `镜像引用为 ${config.Image}，应为 ${expected.imageRef}`)
  need(hc.Runtime === expected.runtime, `运行时为 ${hc.Runtime}，应为 ${expected.runtime}`)
  need(hc.NetworkMode === 'none', `网络模式为 ${hc.NetworkMode}，应为 none`)
  /* 创建态容器尚未接入网络，这里只排除已接入其他网络的情况；启动后由 verifyRunningContainer 补核 */
  const createdNetworks = Object.keys(inspect.NetworkSettings.Networks)
  need(createdNetworks.length === 0 || JSON.stringify(createdNetworks) === '["none"]', `容器接入的网络为 ${createdNetworks.join(', ')}`)
  need(hc.ReadonlyRootfs === true, '根文件系统不是只读')
  need(hc.Privileged === false, '容器处于 privileged')
  need(isBlankList(hc.CapAdd), `不应有附加 capability：${JSON.stringify(hc.CapAdd)}`)
  need((hc.CapDrop ?? []).some((cap) => cap.toUpperCase() === 'ALL'), `未丢弃全部 capability：${JSON.stringify(hc.CapDrop)}`)
  const security = hc.SecurityOpt ?? []
  need(security.some((opt) => /^no-new-privileges(?::true)?$/.test(opt)), `未禁止提权：${JSON.stringify(security)}`)
  need(!security.some((opt) => /unconfined/.test(opt)), `存在放宽的安全选项：${JSON.stringify(security)}`)
  need(config.User === expected.user && !/^(0|root)(:|$)/.test(config.User), `运行用户为 ${config.User}，应为非 root 的 ${expected.user}`)
  need(isBlankList(hc.Devices) && isBlankList(hc.DeviceRequests), '容器挂载了设备')
  need(isBlankList(hc.Binds), `存在未经校验的 Binds：${JSON.stringify(hc.Binds)}`)
  need(isBlankList(hc.ExtraHosts) && isBlankList(hc.Dns), '容器配置了额外主机或 DNS')
  need(!hc.PortBindings || Object.keys(hc.PortBindings).length === 0, '容器发布了端口')
  need(!config.ExposedPorts || Object.keys(config.ExposedPorts).length === 0, '容器声明了暴露端口')
  need(hc.PidMode === '' && hc.UTSMode === '', `共享了宿主命名空间：pid=${hc.PidMode} uts=${hc.UTSMode}`)
  need(hc.UsernsMode === '', `用户命名空间模式为 ${hc.UsernsMode}`)
  need(hc.IpcMode === 'private' && hc.CgroupnsMode === 'private', `命名空间未私有化：ipc=${hc.IpcMode} cgroup=${hc.CgroupnsMode}`)
  need(hc.AutoRemove === false, '容器开启了自动删除，退出后无法核对状态')
  need(!hc.Init, '容器注入了宿主的 init')
  need(hc.LogConfig.Type === 'none', `日志驱动为 ${hc.LogConfig.Type}，应为 none`)
  need(hc.RestartPolicy.Name === 'no', `重启策略为 ${hc.RestartPolicy.Name}`)
  need(config.StopTimeout === STOP_TIMEOUT_SEC && config.StopSignal === 'SIGTERM', '停止信号或宽限期与约定不符')
  need(hc.OomKillDisable !== true, '容器禁用了 OOM 终止')
  need(hc.PidsLimit === expected.pids, `进程上限为 ${hc.PidsLimit}，应为 ${expected.pids}`)
  need(hc.Memory === expected.memory, `内存上限为 ${hc.Memory}，应为 ${expected.memory}`)
  need(hc.MemorySwap === expected.memory, `内存加交换上限为 ${hc.MemorySwap}，应为 ${expected.memory}（不使用交换）`)
  need(hc.NanoCpus === expected.nanoCpus, `CPU 配额为 ${hc.NanoCpus}，应为 ${expected.nanoCpus}`)
  const ulimits = (hc.Ulimits ?? []).map((item) => `${item.Name}=${item.Soft}:${item.Hard}`).sort()
  need(
    JSON.stringify(ulimits) === JSON.stringify([`nofile=${NOFILE_SOFT}:${NOFILE_HARD}`, `nproc=${expected.tasks}:${expected.tasks}`].sort()),
    `资源上限为 ${JSON.stringify(hc.Ulimits)}，应为 nofile ${NOFILE_SOFT}:${NOFILE_HARD} 与 nproc ${expected.tasks}`,
  )
  need(JSON.stringify(sortedEntries(hc.Tmpfs)) === JSON.stringify(sortedEntries(expected.tmpfs)), `/tmp 挂载为 ${JSON.stringify(hc.Tmpfs)}`)
  const mounts = (inspect.Mounts ?? [])
    .map((mount) => mountKey(mount.Type, mount.Type === 'volume' ? String(mount.Name) : mount.Source, mount.Destination, mount.RW))
    .sort()
  need(JSON.stringify(mounts) === JSON.stringify(expected.mounts), `挂载清单为 ${JSON.stringify(mounts)}，应为 ${JSON.stringify(expected.mounts)}`)
  need(sameStringList(config.Env, expected.env), `容器环境变量与约定不符：${JSON.stringify(config.Env)}`)
  need(
    JSON.stringify(sortedEntries(config.Labels)) === JSON.stringify(sortedEntries({ ...expected.imageLabels, ...expected.labels })),
    `容器标签为 ${JSON.stringify(config.Labels)}`,
  )
  need(config.OpenStdin === true && config.StdinOnce === true && config.Tty === false, 'stdio 配置与约定不符')
  need(config.Cmd === null || sameStringList(config.Cmd, []), `容器带有命令参数：${JSON.stringify(config.Cmd)}`)
  need(config.WorkingDir === WORK_DIR, `工作目录为 ${config.WorkingDir}`)
  need(sameOrderedStringList(config.Entrypoint, expected.entrypoint), `入口为 ${JSON.stringify(config.Entrypoint)}，应为 ${JSON.stringify(expected.entrypoint)}`)
  need(Array.isArray(hc.MaskedPaths) && hc.MaskedPaths.length > 0, 'Docker 默认的 /proc 与 /sys 屏蔽路径被清空')
  need(Array.isArray(hc.ReadonlyPaths) && hc.ReadonlyPaths.length > 0, 'Docker 默认的只读路径被清空')
  return problems
}

/* 容器启动后 Docker 才填充的信息：实际接入的网络、运行状态，以及挂载在启动后的最终读写权限 */
export function verifyRunningContainer(inspect: ContainerInspect, expected: ExpectedContainer): string[] {
  const problems: string[] = []
  const networks = Object.keys(inspect.NetworkSettings.Networks)
  if (JSON.stringify(networks) !== '["none"]') problems.push(`容器接入的网络为 ${networks.join(', ') || '无'}`)
  if (!inspect.State.Running) problems.push(`容器状态为 ${inspect.State.Status}`)
  if (inspect.HostConfig.Runtime !== expected.runtime) problems.push(`运行时变为 ${inspect.HostConfig.Runtime}`)
  if (inspect.HostConfig.ReadonlyRootfs !== true) problems.push('根文件系统不再只读')
  const mounts = (inspect.Mounts ?? [])
    .map((mount) => mountKey(mount.Type, mount.Type === 'volume' ? String(mount.Name) : mount.Source, mount.Destination, mount.RW))
    .sort()
  if (JSON.stringify(mounts) !== JSON.stringify(expected.mounts)) problems.push(`启动后的挂载清单为 ${JSON.stringify(mounts)}`)
  return problems
}
