import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { chmodSync, mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { readFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import {
  DEFAULT_LIMITS,
  LABEL_ATTEMPT,
  LIMIT_CEILINGS,
  SANDBOX_TASK_HOST_COST,
  SENTRY_TASK_HEADROOM,
  assertAttempt,
  assertInputsRoot,
  assertRunId,
  runFilters,
  runLabels,
  buildCreateRequest,
  normalizeLimits,
  resolveInputs,
  resourceNames,
  verifyContainer,
  verifyRunningContainer,
  verifyWorkVolume,
  workVolumeRequest,
} from '../src/spec.ts'

const ATTEMPT = '0123456789abcdef01234567'

const fixture = async (name) => JSON.parse(await readFile(new URL(`./fixtures/${name}`, import.meta.url), 'utf8'))
const code = (pattern) => (error) => error.code === 'INVALID_SPEC' && pattern.test(error.message)

function tree(t) {
  const root = mkdtempSync(join(tmpdir(), 'plaza-spec-'))
  t.after(() => rmSync(root, { recursive: true, force: true }))
  const inputs = join(root, 'inputs')
  mkdirSync(inputs)
  mkdirSync(join(inputs, 'task'))
  writeFileSync(join(inputs, 'task', 'brief.txt'), 'brief')
  chmodSync(join(inputs, 'task'), 0o755)
  chmodSync(join(inputs, 'task', 'brief.txt'), 0o644)
  mkdirSync(join(root, 'outside'))
  writeFileSync(join(root, 'outside', 'secret.txt'), 'not an input')
  chmodSync(join(root, 'outside'), 0o755)
  chmodSync(join(root, 'outside', 'secret.txt'), 0o644)
  return { root, inputs }
}

test('限额：缺省值、上下限与非法值', () => {
  assert.deepEqual(normalizeLimits(), DEFAULT_LIMITS)
  /* 未显式给出 tasks 时随 pids 下调：(100 − 64) / 2 = 18 */
  assert.deepEqual([normalizeLimits({ cpus: 0.5 }).cpus, normalizeLimits({ pids: 100 }).tasks, normalizeLimits({ pids: 100 }).pids], [0.5, 18, 100])
  assert.equal(normalizeLimits({ memoryMiB: undefined }).memoryMiB, DEFAULT_LIMITS.memoryMiB)
  const edge = (pids) => normalizeLimits({ pids, tasks: (pids - SENTRY_TASK_HEADROOM) / SANDBOX_TASK_HOST_COST })
  assert.deepEqual([edge(100).pids, edge(100).tasks, edge(96).tasks], [100, 18, 16])
  assert.equal(normalizeLimits({ pids: 96 }).tasks, 16)
  assert.deepEqual([DEFAULT_LIMITS.pids, DEFAULT_LIMITS.tasks], [256, 96])
  assert.deepEqual(normalizeLimits(LIMIT_CEILINGS), LIMIT_CEILINGS)
  for (const [partial, pattern] of [
    [{ cpus: 0 }, /cpus=0/],
    [{ memoryMiB: LIMIT_CEILINGS.memoryMiB + 1 }, /超出允许范围/],
    [{ pids: 1.5 }, /pids 必须是整数/],
    [{ pids: 16 }, /pids=16 超出允许范围/],
    [{ tasks: 1.5 }, /tasks 必须是整数/],
    [{ tasks: 100000 }, /tasks=100000 超出允许范围/],
    [{ tasks: DEFAULT_LIMITS.pids }, /tasks=256 过高.*≤ pids=256/],
    [{ pids: 100, tasks: 19 }, /tasks=19 过高.*≤ pids=100/],
    [{ pids: 100, tasks: DEFAULT_LIMITS.tasks }, /tasks=96 过高/],
    [{ maxDurationSec: -1 }, /maxDurationSec=-1/],
    [{ tmpMiB: '16' }, /必须是数字/],
    [{ bogus: 1 }, /未知限额项/],
  ]) {
    assert.throws(() => normalizeLimits(partial), code(pattern))
  }
})

test('runId 与资源命名', () => {
  assert.equal(assertRunId('acc-mwuh76nc-1vlqx-a'), 'acc-mwuh76nc-1vlqx-a')
  for (const bad of ['', 'A-b', '-abc', 'a_b', 'a b', '../x', 'a'.repeat(64), undefined, 7]) {
    assert.throws(() => assertRunId(bad), code(/runId/))
  }
  assert.deepEqual(resourceNames('run-1'), { container: 'plaza-sb-run-1', workVolume: 'plaza-sb-run-1-work' })
})

test('尝试标识：工作卷与容器的标签都带本次 attempt', () => {
  assert.equal(assertAttempt(ATTEMPT), ATTEMPT)
  assert.deepEqual(runLabels('run-1', ATTEMPT), { 'plaza.sandbox.managed': 'v2', 'plaza.sandbox.run': 'run-1', [LABEL_ATTEMPT]: ATTEMPT })
  for (const bad of ['', 'abc', ATTEMPT.toUpperCase(), `${ATTEMPT}0`, undefined, 42]) {
    assert.throws(() => runLabels('run-1', bad), code(/attempt 必须是 24 位十六进制/))
  }
  assert.deepEqual(runFilters('run-1'), { label: ['plaza.sandbox.managed=v2', 'plaza.sandbox.run=run-1'] })
})

test('只读输入必须位于输入根目录内、是普通文件或目录、对沙箱用户可读', async (t) => {
  const { inputs, root } = tree(t)
  mkdirSync(join(inputs, 'private'))
  chmodSync(join(inputs, 'private'), 0o700)
  symlinkSync('../outside', join(inputs, 'escape'))
  execFileSync('mkfifo', [join(inputs, 'pipe')])
  const brief = { hostPath: join(inputs, 'task', 'brief.txt'), target: '/input/brief.txt' }
  assert.deepEqual(await resolveInputs([], ''), [])
  assert.deepEqual(await resolveInputs([brief], inputs), [{ source: join(inputs, 'task', 'brief.txt'), target: '/input/brief.txt', kind: 'file' }])
  assert.equal((await resolveInputs([{ hostPath: join(inputs, 'task'), target: '/input/task' }], inputs))[0].kind, 'directory')
  for (const [input, pattern] of [
    [{ hostPath: join(root, 'outside'), target: '/input/x' }, /不在输入根目录内/],
    [{ hostPath: join(inputs, '..', 'outside'), target: '/input/x' }, /不在输入根目录内/],
    [{ hostPath: join(inputs, 'escape'), target: '/input/x' }, /不在输入根目录内/],
    [{ hostPath: inputs, target: '/input/x' }, /不在输入根目录内/],
    [{ hostPath: join(inputs, 'missing'), target: '/input/x' }, /不存在/],
    [{ hostPath: join(inputs, 'private'), target: '/input/x' }, /o\+rX/],
    [{ hostPath: join(inputs, 'pipe'), target: '/input/x' }, /不是普通文件或目录/],
    [{ hostPath: 'inputs/task', target: '/input/x' }, /绝对路径/],
    [{ hostPath: join(inputs, 'task'), target: '/work/task' }, /\/input\/<名称>/],
    [{ hostPath: join(inputs, 'task'), target: '/input/task/../../etc' }, /\/input\/<名称>/],
    [{ hostPath: join(inputs, 'task'), target: 'input/task' }, /\/input\/<名称>/],
  ]) {
    await assert.rejects(resolveInputs([input], inputs), code(pattern))
  }
  await assert.rejects(
    resolveInputs(
      [
        { hostPath: join(inputs, 'task'), target: '/input/same' },
        { hostPath: join(inputs, 'task', 'brief.txt'), target: '/input/same' },
      ],
      inputs,
    ),
    code(/重复/),
  )
  const many = Array.from({ length: 17 }, (_, index) => ({ hostPath: join(inputs, 'task', 'brief.txt'), target: `/input/f${index}` }))
  await assert.rejects(resolveInputs(many, inputs), code(/最多挂载 16/))
  await assert.rejects(resolveInputs([brief], join(root, 'nowhere')), code(/输入根目录不存在/))
})

test('输入根目录必须显式、规范且不是文件系统根；空值不会落到当前工作目录', async (t) => {
  const { inputs } = tree(t)
  const inside = { hostPath: join(inputs, 'task'), target: '/input/task' }
  assert.equal(assertInputsRoot(inputs), inputs)
  for (const bad of [undefined, '', '   ', null, 42]) {
    assert.throws(() => assertInputsRoot(bad), code(/显式给出受信输入根目录/))
  }
  for (const bad of ['inputs', './inputs', `${inputs}/..`, `${inputs}/`, '/']) {
    assert.throws(() => assertInputsRoot(bad), code(/inputsRoot 必须是规范化且不是文件系统根的绝对路径/))
  }
  /* 回归：没有输入根时，当前工作目录里的路径也必须被拒绝 */
  const cwdInput = { hostPath: process.cwd(), target: '/input/repo' }
  await assert.rejects(resolveInputs([cwdInput], ''), code(/显式给出受信输入根目录/))
  await assert.rejects(resolveInputs([cwdInput], undefined), code(/显式给出受信输入根目录/))
  await assert.rejects(resolveInputs([cwdInput], '/'), code(/inputsRoot 必须/))
  assert.deepEqual(await resolveInputs([], ''), [])
})

test('创建请求：降权、离线、挂载、临时目录与限额都显式写出', () => {
  const input = { source: '/srv/plaza/inputs/task', target: '/input/task', kind: 'directory' }
  const { body, expected } = buildCreateRequest({
    runId: 'run-1',
    imageRef: 'sha256:abc',
    imageId: 'sha256:abc',
    entrypoint: ['/tini'],
    imageEnv: ['PATH=/bin'],
    imageLabels: { 'plaza.sandbox.role': 'pi' },
    user: '65532:65532',
    attempt: ATTEMPT,
    limits: { ...DEFAULT_LIMITS, cpus: 0.5, tasks: 96 },
    inputs: [input],
  })
  const hc = body.HostConfig
  assert.equal(body.Image, 'sha256:abc')
  assert.equal(hc.Runtime, 'runsc')
  assert.equal(hc.NetworkMode, 'none')
  assert.equal(hc.ReadonlyRootfs, true)
  assert.equal(hc.Privileged, false)
  assert.deepEqual(hc.CapDrop, ['ALL'])
  assert.deepEqual(hc.CapAdd, [])
  assert.deepEqual(hc.SecurityOpt, ['no-new-privileges:true'])
  assert.equal(hc.Binds, undefined)
  assert.equal(hc.Devices.length, 0)
  assert.deepEqual(hc.Tmpfs, { '/tmp': `rw,nosuid,nodev,noexec,size=${DEFAULT_LIMITS.tmpMiB}m,mode=1777` })
  assert.deepEqual(
    hc.Mounts.map((mount) => [mount.Type, mount.Source, mount.Target, mount.ReadOnly]),
    [
      ['volume', 'plaza-sb-run-1-work', '/work', false],
      ['bind', '/srv/plaza/inputs/task', '/input/task', true],
    ],
  )
  assert.equal(hc.PidsLimit, DEFAULT_LIMITS.pids)
  assert.equal(hc.Memory, DEFAULT_LIMITS.memoryMiB * 1048576)
  assert.equal(hc.MemorySwap, hc.Memory)
  assert.equal(hc.NanoCpus, 500000000)
  assert.deepEqual(hc.Ulimits, [
    { Name: 'nofile', Soft: 4096, Hard: 8192 },
    { Name: 'nproc', Soft: 96, Hard: 96 },
  ])
  assert.deepEqual(body.Labels, { 'plaza.sandbox.managed': 'v2', 'plaza.sandbox.run': 'run-1', [LABEL_ATTEMPT]: ATTEMPT })
  assert.equal(expected.tasks, 96)
  assert.equal(hc.LogConfig.Type, 'none')
  assert.deepEqual(body.Env, ['PI_SESSION_DIR=/work/.pi-sessions', 'PI_SESSION_NAME=run-1', `PI_MAX_SECONDS=${DEFAULT_LIMITS.maxDurationSec}`])
  assert.deepEqual(expected.mounts, ['bind:/srv/plaza/inputs/task:/input/task:ro', 'volume:plaza-sb-run-1-work:/work:rw'])
})

test('工作卷请求带字节与 inode 上限，并按本次运行标签核对', () => {
  const request = workVolumeRequest('run-1', DEFAULT_LIMITS, '65532:65532', ATTEMPT)
  assert.deepEqual(request.DriverOpts, { type: 'tmpfs', device: 'tmpfs', o: `size=${DEFAULT_LIMITS.workMiB}m,nr_inodes=${DEFAULT_LIMITS.workFiles},mode=0700,uid=65532,gid=65532` })
  const volume = { Name: 'plaza-sb-run-1-work', Driver: 'local', Options: { type: 'tmpfs', device: 'tmpfs', o: request.DriverOpts.o }, Labels: request.Labels }
  assert.deepEqual(verifyWorkVolume(volume, request), [])
  assert.match(verifyWorkVolume({ ...volume, Options: { ...volume.Options, o: 'size=8m' } }, request)[0], /工作卷选项为.*nr_inodes/)
  assert.deepEqual(verifyWorkVolume({ ...volume, Name: 'other' }, request).length, 1)
  assert.deepEqual(verifyWorkVolume({ ...volume, Driver: 'nfs' }, request).length, 1)
  assert.deepEqual(verifyWorkVolume({ ...volume, Labels: {} }, request).length, 1)
})

test('Docker 实际回报与约定逐项核对：真实夹具通过，任何一处偏离都报出', async () => {
  const inspect = await fixture('container-created.json')
  const running = await fixture('container-running.json')
  const expected = await fixture('expected.json')
  assert.deepEqual(verifyContainer(inspect, expected), [])
  assert.deepEqual(verifyRunningContainer(running, expected), [])

  const mutated = (change) => {
    const copy = structuredClone(inspect)
    change(copy)
    return copy
  }
  const mount = (copy) => copy.Mounts.find((item) => item.Type === 'bind')
  const problemsWhen = (change) => verifyContainer(mutated(change), expected)
  for (const [change, pattern] of [
    [(copy) => (copy.HostConfig.Runtime = 'runc'), /运行时为 runc/],
    [(copy) => (copy.Image = `sha256:${'0'.repeat(64)}`), /镜像 ID 为/],
    [(copy) => (copy.HostConfig.NetworkMode = 'bridge'), /网络模式为 bridge/],
    [(copy) => (copy.NetworkSettings.Networks = { bridge: {} }), /接入的网络为 bridge/],
    [(copy) => (copy.HostConfig.ReadonlyRootfs = false), /根文件系统不是只读/],
    [(copy) => (copy.HostConfig.Privileged = true), /privileged/],
    [(copy) => (copy.HostConfig.CapAdd = ['SYS_ADMIN']), /附加 capability/],
    [(copy) => (copy.HostConfig.CapDrop = ['NET_ADMIN']), /未丢弃全部 capability/],
    [(copy) => (copy.HostConfig.SecurityOpt = ['seccomp=unconfined']), /未禁止提权/],
    [(copy) => (copy.HostConfig.SecurityOpt = ['no-new-privileges', 'apparmor=unconfined']), /放宽的安全选项/],
    [(copy) => (copy.Config.User = '0:0'), /运行用户为 0:0/],
    [(copy) => (copy.Config.User = 'root'), /运行用户为 root/],
    [(copy) => (copy.HostConfig.Devices = [{ PathOnHost: '/dev/sda' }]), /挂载了设备/],
    [(copy) => (copy.HostConfig.Binds = ['/var/run/docker.sock:/var/run/docker.sock']), /未经校验的 Binds/],
    [(copy) => (copy.HostConfig.ExtraHosts = ['host:host-gateway']), /额外主机或 DNS/],
    [(copy) => (copy.HostConfig.PortBindings = { '80/tcp': [{ HostPort: '80' }] }), /发布了端口/],
    [(copy) => (copy.Config.ExposedPorts = { '80/tcp': {} }), /暴露端口/],
    [(copy) => (copy.HostConfig.PidMode = 'host'), /共享了宿主命名空间/],
    [(copy) => (copy.HostConfig.IpcMode = 'host'), /命名空间未私有化/],
    [(copy) => (copy.HostConfig.AutoRemove = true), /自动删除/],
    [(copy) => (copy.HostConfig.Init = true), /宿主的 init/],
    [(copy) => (copy.HostConfig.LogConfig.Type = 'json-file'), /日志驱动为 json-file/],
    [(copy) => (copy.HostConfig.RestartPolicy.Name = 'always'), /重启策略为 always/],
    [(copy) => (copy.Config.StopTimeout = 30), /停止信号或宽限期/],
    [(copy) => (copy.HostConfig.PidsLimit = 0), /进程上限为 0/],
    [(copy) => (copy.HostConfig.Memory = 0), /内存上限为 0/],
    [(copy) => (copy.HostConfig.MemorySwap = -1), /内存加交换上限为 -1/],
    [(copy) => (copy.HostConfig.NanoCpus = 0), /CPU 配额为 0/],
    [(copy) => (copy.HostConfig.Ulimits = [{ Name: 'nofile', Soft: 10, Hard: 10 }]), /资源上限为/],
    [(copy) => (copy.HostConfig.Ulimits = copy.HostConfig.Ulimits.filter((item) => item.Name === 'nproc')), new RegExp(`与 nproc ${DEFAULT_LIMITS.tasks}`)],
    [(copy) => (copy.HostConfig.Tmpfs = { '/tmp': 'rw,size=999m' }), /\/tmp 挂载为/],
    [(copy) => mount(copy) && (mount(copy).RW = true), /挂载清单为/],
    [(copy) => copy.Mounts.push({ Type: 'bind', Source: '/var/run/docker.sock', Destination: '/var/run/docker.sock', RW: false }), /挂载清单为/],
    [(copy) => copy.Mounts.splice(0, 1), /挂载清单为/],
    [(copy) => (copy.Config.Env = [...copy.Config.Env, 'OPENAI_API_KEY=x']), /环境变量与约定不符/],
    [(copy) => (copy.Config.OpenStdin = false), /stdio 配置与约定不符/],
    [(copy) => (copy.Config.Cmd = ['sh']), /带有命令参数/],
    [(copy) => (copy.Config.WorkingDir = '/'), /工作目录为 \//],
    [(copy) => (copy.Config.Entrypoint = ['sh']), /入口为/],
    [(copy) => (copy.HostConfig.MaskedPaths = []), /屏蔽路径被清空/],
    [(copy) => (copy.HostConfig.ReadonlyPaths = []), /只读路径被清空/],
    [(copy) => delete copy.Config.Labels['plaza.sandbox.run'], /容器标签为/],
  ]) {
    const problems = verifyContainer(mutated(change), expected)
    assert.ok(problems.some((problem) => pattern.test(problem)), `${change}: ${JSON.stringify(problems)}`)
  }
  assert.equal(problemsWhen((copy) => (copy.State.Status = 'running')).length, 0, '创建态检查不依赖容器状态字段')
  assert.equal(problemsWhen((copy) => (copy.HostConfig.CapDrop = ['all'])).length, 0, 'capability 名字大小写不敏感')
  assert.equal(problemsWhen((copy) => (copy.HostConfig.SecurityOpt = ['no-new-privileges'])).length, 0, 'no-new-privileges 可不带 :true')
  assert.equal(problemsWhen((copy) => (copy.Config.Cmd = null)).length, 0, '命令为 null 与空数组等价')

  for (const [change, pattern] of [
    [(copy) => (copy.NetworkSettings.Networks = {}), /接入的网络为 无/],
    [(copy) => (copy.NetworkSettings.Networks = { none: {}, bridge: {} }), /接入的网络为 none, bridge/],
    [(copy) => ((copy.State.Running = false), (copy.State.Status = 'exited')), /容器状态为 exited/],
    [(copy) => (copy.HostConfig.Runtime = 'runc'), /运行时变为 runc/],
    [(copy) => (copy.HostConfig.ReadonlyRootfs = false), /根文件系统不再只读/],
    [(copy) => (copy.Mounts.find((item) => item.Type === 'bind').RW = true), /启动后的挂载清单为/],
  ]) {
    const copy = structuredClone(running)
    change(copy)
    const problems = verifyRunningContainer(copy, expected)
    assert.ok(problems.some((problem) => pattern.test(problem)), `${change}: ${JSON.stringify(problems)}`)
  }
})
