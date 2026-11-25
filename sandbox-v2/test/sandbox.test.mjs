import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import { DockerApiError } from '../src/docker.ts'
import { imageReference, parseImageLock, SandboxWorker, verifyImage } from '../src/sandbox.ts'
import { DEFAULT_LIMITS, LABEL_ATTEMPT, LABEL_RUN } from '../src/spec.ts'
import { FakeDuplex, scriptedPi } from './helpers.mjs'

const fixture = async (name) => JSON.parse(await readFile(new URL(`./fixtures/${name}`, import.meta.url), 'utf8'))
const RUN = 'fixture-a'
const PROBE = '65532|4.19.0-gvisor|v22.23.5\n'
const STATE = { sessionId: 'session-1', sessionFile: '/work/.pi-sessions/session-1.jsonl', messageCount: 0 }
const attemptOf = (labels) => labels?.[LABEL_ATTEMPT]
/* Worker 的错误把逐项核对结果放在 details 里，断言同时看 message 与 details */
const code = (expected, pattern) => (error) => error.code === expected && pattern.test([error.message, ...(Array.isArray(error.details) ? error.details : [])].join(' '))

/* Docker 替身，照 Docker 的实际语义：
   - 同名卷的创建串行执行，卷已存在时返回已有对象，不改它的标签；
   - 容器名唯一，重名返回 409；
   - inspect 按创建请求回报配置，外壳取自真实夹具。 */
async function fakeDocker(t) {
  /* Worker 的时限兜底定时器不维持进程存活；替身没有真实 I/O，这里显式保活，免得事件循环提前结束 */
  const keepAlive = setInterval(() => {}, 60_000)
  t.after(() => clearInterval(keepAlive))
  const calls = []
  const state = { containers: [], volumes: [] }
  const fake = {
    calls,
    state,
    image: await fixture('image.json'),
    template: await fixture('container-created.json'),
    daemon: { Runtimes: { runc: { path: 'runc' }, runsc: { path: '/usr/bin/runsc' } }, DefaultRuntime: 'runc', Architecture: 'x86_64' },
    /* 大于 0 时，删除操作先抛出若干次冲突再成功，用来覆盖重试 */
    removeErrors: 0,
    stuck: null,
    startError: null,
    volumeError: null,
    gate: null,
    mutateCreated: null,
    mutateRunning: null,
    duplex: new FakeDuplex(),
    nextId: 1,
    async version() {
      return { ApiVersion: '1.51', Version: '28.3.3' }
    },
    async info() {
      return fake.daemon
    },
    async inspectImage(id) {
      calls.push(['inspectImage'])
      if (id !== fake.image.Id) throw new DockerApiError(404, 'No such image')
      return fake.image
    },
    async createVolume(body) {
      calls.push(['createVolume', body.Name])
      if (fake.gate) await fake.gate
      if (fake.volumeError) throw fake.volumeError
      /* 这一段是原子的，对应 Docker 内部按卷名加锁 */
      const existing = state.volumes.find((item) => item.Name === body.Name)
      if (existing) return structuredClone(existing)
      const volume = { Name: body.Name, Driver: body.Driver, Mountpoint: `/var/lib/docker/volumes/${body.Name}/_data`, Labels: body.Labels, Options: body.DriverOpts }
      state.volumes.push(volume)
      return structuredClone(volume)
    },
    async inspectVolume(name) {
      const volume = state.volumes.find((item) => item.Name === name)
      if (!volume) throw new DockerApiError(404, `get ${name}: no such volume`)
      return structuredClone(volume)
    },
    async createContainer(body) {
      calls.push(['createContainer', body.Name])
      if (state.containers.some((item) => item.body.Name === body.Name)) {
        throw new DockerApiError(409, `Conflict. The container name "/${body.Name}" is already in use by container "abc". You have to remove (or rename) that container to be able to reuse that name.`)
      }
      const record = { id: String(fake.nextId++).padStart(64, '0'), body, state: 'created' }
      state.containers.push(record)
      return { Id: record.id, Warnings: [] }
    },
    async inspectContainer(id) {
      const record = state.containers.find((item) => item.id === id)
      if (!record) throw new DockerApiError(404, 'No such container')
      const inspect = inspectFrom(record, fake)
      if (record.state === 'created' && fake.mutateCreated) fake.mutateCreated(inspect)
      if (record.state === 'running' && fake.mutateRunning) fake.mutateRunning(inspect)
      return inspect
    },
    async startContainer(id) {
      calls.push(['startContainer'])
      if (fake.startError) throw fake.startError
      state.containers.find((item) => item.id === id).state = 'running'
    },
    async stopContainer(id, timeout) {
      calls.push(['stopContainer', timeout])
      fake.exit?.({ StatusCode: 143, Error: null })
    },
    async attach() {
      calls.push(['attach'])
      return fake.duplex
    },
    waitContainer() {
      calls.push(['waitContainer'])
      return new Promise((resolve) => {
        fake.exit = resolve
      })
    },
    async listContainers(filters) {
      return state.containers
        .filter((item) => item.body.Labels[LABEL_RUN] === runOf(filters))
        .map((item) => ({ Id: item.id, Names: ['/' + item.body.Name], State: item.state, Labels: item.body.Labels }))
    },
    async listVolumes(filters) {
      return { Volumes: state.volumes.filter((item) => item.Labels[LABEL_RUN] === runOf(filters)).map((item) => structuredClone(item)) }
    },
    async removeContainer(id) {
      calls.push(['removeContainer'])
      if (fake.removeErrors-- > 0) throw new DockerApiError(409, 'removal of container is already in progress')
      if (fake.stuck === 'container') return
      state.containers = state.containers.filter((item) => item.id !== id)
    },
    async removeVolume(name) {
      calls.push(['removeVolume', name])
      if (fake.removeErrors-- > 0) throw new DockerApiError(409, 'volume is in use')
      if (fake.stuck === 'volume') return
      state.volumes = state.volumes.filter((item) => item.Name !== name)
    },
  }
  return fake
}

function inspectFrom(record, fake) {
  const { body } = record
  const running = record.state === 'running'
  const copy = structuredClone(fake.template)
  copy.Id = record.id
  copy.Name = `/${body.Name}`
  copy.Image = fake.image.Id
  copy.State = { ...copy.State, Status: record.state, Running: running, Pid: 0, ExitCode: 0 }
  copy.Config = {
    ...copy.Config,
    User: body.User,
    /* Docker 把镜像环境与容器环境合并后回报 */
    Env: [...fake.image.Config.Env, ...body.Env].sort(),
    Image: body.Image,
    Cmd: null,
    Entrypoint: fake.template.Config.Entrypoint,
    WorkingDir: body.WorkingDir,
    Labels: { ...fake.image.Config.Labels, ...body.Labels },
    OpenStdin: true,
    StdinOnce: true,
    Tty: false,
    ExposedPorts: undefined,
    StopSignal: body.StopSignal,
    StopTimeout: body.StopTimeout,
  }
  copy.HostConfig = { ...copy.HostConfig, ...body.HostConfig }
  copy.Mounts = body.HostConfig.Mounts.map((mount) =>
    mount.Type === 'volume'
      ? { Type: 'volume', Name: mount.Source, Source: `/var/lib/docker/volumes/${mount.Source}/_data`, Destination: mount.Target, Driver: 'local', Mode: 'z', RW: !mount.ReadOnly, Propagation: '' }
      : { Type: 'bind', Source: mount.Source, Destination: mount.Target, Mode: '', RW: !mount.ReadOnly, Propagation: 'rprivate' },
  )
  copy.NetworkSettings.Networks = running ? { none: {} } : {}
  return copy
}

const runOf = (filters) => filters.label.find((item) => item.startsWith(`${LABEL_RUN}=`)).slice(LABEL_RUN.length + 1)
const has = (fake, name) => fake.calls.some(([call]) => call === name)
const count = (fake, name) => fake.calls.filter(([call]) => call === name).length
const clean = (fake) => assert.deepEqual([fake.state.containers.length, fake.state.volumes.length], [0, 0])
/* 容器自行结束：输出流关闭，wait 返回给定退出码 */
function end(fake, status, error = null) {
  fake.duplex.endOut()
  fake.exit({ StatusCode: status, Error: error })
}
/* Pi 有序退出：stdin 关闭后输出流结束，wait 返回给定退出码 */
function exitsWith(fake, status) {
  fake.duplex.onEnd = () => end(fake, status)
}
function freshPi(fake) {
  fake.duplex = new FakeDuplex()
  scriptedPi(fake.duplex)
}
async function readyWorker(t, options = {}) {
  const fake = await fakeDocker(t)
  freshPi(fake)
  const lock = await fixture('image.lock.json')
  return { fake, lock, worker: new SandboxWorker({ image: lock, docker: fake, ...options }) }
}

test('登记文件校验与不可变引用', async (t) => {
  const lock = await fixture('image.lock.json')
  assert.deepEqual(parseImageLock(lock), lock)
  assert.equal(imageReference(lock), lock.id)
  assert.equal(imageReference({ ...lock, repoDigest: `sha256:${'a'.repeat(64)}` }), `${lock.name}@sha256:${'a'.repeat(64)}`)
  for (const [mutate, pattern] of [
    [{ id: `${lock.name}:${lock.piVersion}` }, /id 必须是 sha256/],
    [{ repoDigest: 'latest' }, /repoDigest/],
    [{ piVersion: '' }, /piVersion 缺失/],
    [{ piIntegrity: 'sha256:abc' }, /piIntegrity/],
    [{ baseDigest: 'sha256:abc' }, /baseDigest/],
    [{ layers: [] }, /layers/],
    [{ layers: [...lock.layers, 'x'] }, /layers/],
    [{ entrypoint: [] }, /entrypoint/],
    [{ user: '0:0' }, /uid:gid/],
    [{ user: 'root' }, /uid:gid/],
  ]) {
    assert.throws(() => parseImageLock({ ...lock, ...mutate }), code('IMAGE_LOCK', pattern))
  }
  assert.throws(() => parseImageLock(null), code('IMAGE_LOCK', /不是对象/))
  assert.throws(() => parseImageLock('x'), code('IMAGE_LOCK', /不是对象/))
})

test('镜像核对：标识、架构、标签、用户、入口、层与环境', async (t) => {
  const lock = await fixture('image.lock.json')
  const image = await fixture('image.json')
  const config = (change) => ({ ...image, Config: { ...image.Config, ...change } })
  assert.deepEqual(verifyImage(image, lock, 'x86_64'), [])
  assert.deepEqual(verifyImage(image, lock, 'amd64'), [])
  for (const [mutated, pattern] of [
    [{ ...image, Id: `sha256:${'0'.repeat(64)}` }, /镜像 ID 为/],
    [{ ...image, Os: 'windows' }, /镜像系统为 windows/],
    [{ ...image, Architecture: 'arm64' }, /镜像架构为 arm64，守护进程为 x86_64/],
    [config({ Labels: { ...image.Config.Labels, 'plaza.sandbox.pi.version': '0.0.0' } }), /pi\.version=0\.0\.0/],
    [config({ Labels: { ...image.Config.Labels, 'plaza.sandbox.base.digest': `sha256:${'b'.repeat(64)}` } }), /base\.digest 与登记不符/],
    [config({ User: '0:0' }), /运行用户为 0:0/],
    [config({ Entrypoint: ['sh'] }), /入口与登记不符/],
    [config({ Cmd: ['node'] }), /不应带默认命令/],
    [config({ ExposedPorts: { '80/tcp': {} } }), /不应暴露端口/],
    [{ ...image, RootFS: { Layers: image.RootFS.Layers.slice(1) } }, /镜像层与登记不符/],
    [config({ Env: [...image.Config.Env, 'SOME_API_TOKEN=x'] }), /凭据样式变量：SOME_API_TOKEN/],
    [config({ Env: [...image.Config.Env, 'DATABASE_PASSWORD=x'] }), /凭据样式变量：DATABASE_PASSWORD/],
  ]) {
    const problems = verifyImage(mutated, lock, 'x86_64')
    assert.equal(problems.length, 1, `${pattern}: ${JSON.stringify(problems)}`)
    assert.match(problems[0], pattern)
  }
  assert.deepEqual(verifyImage(config({ Env: [...image.Config.Env, 'NODE_ENV=production'] }), lock, 'x86_64'), [])
})

test('Worker 只允许 runsc：传入其他运行时在接触 Docker 之前被拒绝', async (t) => {
  const lock = await fixture('image.lock.json')
  const fake = await fakeDocker(t)
  for (const runtime of ['runc', 'runc-dev', 'RUNSC', '']) {
    assert.throws(() => new SandboxWorker({ image: lock, docker: fake, runtime }), code('INVALID_SPEC', /只允许运行时 runsc/))
  }
  assert.equal(fake.calls.length, 0)
  assert.equal(new SandboxWorker({ image: lock, docker: fake, runtime: 'runsc' }).runtime, 'runsc')
  assert.equal(new SandboxWorker({ image: lock, docker: fake }).runtime, 'runsc')
})

test('挂输入必须显式给出受信输入根目录：空值不会落到当前工作目录', async (t) => {
  const { fake, lock } = await readyWorker(t)
  /* 回归：路径就在当前工作目录之内。没有受信输入根时必须拒绝，而不是把仓库当成可挂载范围 */
  const inside = { hostPath: process.cwd(), target: '/input/repo' }
  const missingRoot = new SandboxWorker({ image: lock, docker: fake })
  await assert.rejects(missingRoot.start({ runId: RUN, inputs: [inside] }), code('INVALID_SPEC', /显式给出受信输入根目录/))
  for (const root of ['', '   ']) {
    const blank = new SandboxWorker({ image: lock, docker: fake, inputsRoot: root })
    await assert.rejects(blank.start({ runId: RUN, inputs: [inside] }), code('INVALID_SPEC', /显式给出受信输入根目录/))
  }
  for (const root of ['inputs', '/tmp/../', '/']) {
    const odd = new SandboxWorker({ image: lock, docker: fake, inputsRoot: root })
    await assert.rejects(odd.start({ runId: RUN, inputs: [inside] }), code('INVALID_SPEC', /inputsRoot 必须/))
  }
  assert.equal(fake.calls.length, 0, '被拒绝的请求不应触达 Docker')
  /* 不挂输入的运行不需要输入根 */
  exitsWith(fake, 0)
  const handle = await missingRoot.start({ runId: RUN })
  await handle.shutdown()
  clean(fake)
})

test('未注册运行时：明确失败，不创建任何资源', async (t) => {
  const { fake, worker } = await readyWorker(t)
  delete fake.daemon.Runtimes.runsc
  await assert.rejects(worker.start({ runId: RUN }), code('RUNTIME_UNAVAILABLE', /不会回退到其他运行时/))
  assert.equal(has(fake, 'createVolume'), false)
  assert.equal(has(fake, 'createContainer'), false)
})

test('登记的镜像不在本机或与登记不符：IMAGE_LOCK', async (t) => {
  const missing = await readyWorker(t)
  missing.fake.image = { ...missing.fake.image, Id: `sha256:${'0'.repeat(64)}` }
  await assert.rejects(missing.worker.start({ runId: RUN }), code('IMAGE_LOCK', /不在本机/))
  assert.equal(has(missing.fake, 'createVolume'), false)
  const tampered = await readyWorker(t)
  tampered.fake.image = { ...tampered.fake.image, Config: { ...tampered.fake.image.Config, Labels: { ...tampered.fake.image.Config.Labels, 'plaza.sandbox.pi.version': '0.0.0' } } }
  await assert.rejects(tampered.worker.start({ runId: RUN }), code('IMAGE_LOCK', /pi\.version=0\.0\.0/))
  assert.equal(has(tampered.fake, 'createVolume'), false)
})

test('Docker 回报与约定不符：拒绝启动并只释放本次创建的资源', async (t) => {
  for (const [where, change, pattern] of [
    ['mutateCreated', (copy) => (copy.HostConfig.Runtime = 'runc'), /运行时为 runc，应为 runsc/],
    ['mutateCreated', (copy) => (copy.HostConfig.ReadonlyRootfs = false), /根文件系统不是只读/],
    ['mutateCreated', (copy) => copy.Mounts.push({ Type: 'bind', Source: '/var/run/docker.sock', Destination: '/var/run/docker.sock', RW: false }), /挂载清单为/],
    ['mutateCreated', (copy) => (copy.Config.Env = [...copy.Config.Env, 'PLAZA_SECRET=x']), /环境变量与约定不符/],
    ['mutateCreated', (copy) => (copy.Config.Labels['plaza.sandbox.attempt'] = 'f'.repeat(24)), /容器标签为/],
    ['mutateCreated', (copy) => (copy.HostConfig.Ulimits = copy.HostConfig.Ulimits.filter((item) => item.Name !== 'nproc')), new RegExp(`资源上限为.*nofile 4096:8192 与 nproc ${DEFAULT_LIMITS.tasks}`)],
    ['mutateRunning', (copy) => (copy.NetworkSettings.Networks = { bridge: {} }), /接入的网络为 bridge/],
    ['mutateRunning', (copy) => ((copy.State.Running = false), (copy.State.Status = 'exited')), /容器状态为 exited/],
  ]) {
    const { fake, worker } = await readyWorker(t)
    fake[where] = change
    await assert.rejects(worker.start({ runId: RUN }), code('VERIFY_FAILED', pattern))
    if (where === 'mutateCreated') {
      assert.equal(has(fake, 'startContainer'), false)
      assert.equal(has(fake, 'attach'), false)
    }
    clean(fake)
  }
})

test('容器启动失败：不回退，带出 Docker 原因并释放本次资源', async (t) => {
  const broken = await readyWorker(t)
  broken.fake.startError = new DockerApiError(500, 'failed to launch runsc: open /usr/bin/runsc: no such file or directory')
  await assert.rejects(broken.worker.start({ runId: RUN }), code('RUNTIME_UNAVAILABLE', /runsc.*no such file.*不会回退/s))
  clean(broken.fake)
  const other = await readyWorker(t)
  other.fake.startError = new DockerApiError(400, 'OCI runtime create failed: exec: "pi": executable file not found')
  await assert.rejects(other.worker.start({ runId: RUN }), code('START_FAILED', /executable file not found/))
  clean(other.fake)
})

test('正常路径：就绪、会话与证明信息，关闭后有序退出并释放资源', async (t) => {
  const { fake, worker } = await readyWorker(t)
  exitsWith(fake, 0)
  const handle = await worker.start({ runId: RUN })
  assert.equal(handle.session.sessionId, 'session-1')
  assert.equal(handle.attestation.kernel, '4.19.0-gvisor')
  assert.equal(handle.hostLimits, null)
  assert.deepEqual([handle.limits.pids, handle.limits.tasks], [DEFAULT_LIMITS.pids, DEFAULT_LIMITS.tasks])
  assert.match(handle.attempt, /^[0-9a-f]{24}$/)
  assert.equal(attemptOf(fake.state.volumes[0].Labels), handle.attempt)
  assert.equal(attemptOf(fake.state.containers[0].body.Labels), handle.attempt)
  assert.equal(fake.duplex.written[0], '{"id":1,"type":"get_state"}\n')
  assert.match(fake.duplex.written[1], /"type":"bash","command":"printf/)
  const result = await handle.shutdown()
  assert.equal(result.outcome, 'exited')
  assert.equal(result.exitCode, 0)
  assert.equal(result.reason, undefined)
  assert.deepEqual(result.reclaimed, { containers: 1, volumes: 1 })
  assert.equal(handle.rpc.isOpen, false)
  clean(fake)
})

test('同一 runId 并发启动：只成功一个，被拒的一方不动胜者的资源', async (t) => {
  const fake = await fakeDocker(t)
  freshPi(fake)
  exitsWith(fake, 0)
  const lock = await fixture('image.lock.json')
  const workers = [0, 1, 2].map(() => new SandboxWorker({ image: lock, docker: fake }))
  /* 让三次启动都走到创建工作卷那一步再放行，对应 Docker 内部按卷名串行 */
  let release
  fake.gate = new Promise((resolve) => {
    release = resolve
  })
  const attempts = workers.map((worker) => worker.start({ runId: RUN }).then(
    (handle) => ({ handle }),
    (error) => ({ error }),
  ))
  await new Promise((resolve) => setImmediate(resolve))
  release()
  const settled = await Promise.all(attempts)
  const winners = settled.filter((item) => item.handle)
  const losers = settled.filter((item) => item.error)
  assert.equal(winners.length, 1, '应恰好一个启动成功')
  assert.equal(losers.length, 2)
  for (const { error } of losers) assert.ok(code('RUN_EXISTS', /不会动它/)(error), error.message)
  assert.deepEqual([fake.state.containers.length, fake.state.volumes.length], [1, 1])
  assert.equal(attemptOf(fake.state.containers[0].body.Labels), winners[0].handle.attempt)
  assert.equal(attemptOf(fake.state.volumes[0].Labels), winners[0].handle.attempt)
  /* 胜者照常工作；在它运行期间再次启动同一 runId 同样被拒 */
  assert.equal((await winners[0].handle.rpc.getState()).sessionId, 'session-1')
  await assert.rejects(workers[1].start({ runId: RUN }), code('RUN_EXISTS', /不会动它/))
  assert.equal(count(fake, 'removeContainer'), 0)
  assert.equal(count(fake, 'removeVolume'), 0)
  const result = await winners[0].handle.shutdown()
  assert.deepEqual(result.reclaimed, { containers: 1, volumes: 1 })
  clean(fake)
  /* 释放之后同一 runId 可以重新启动 */
  freshPi(fake)
  exitsWith(fake, 0)
  const again = await workers[2].start({ runId: RUN })
  await again.shutdown()
  clean(fake)
})

test('run 留有未回收资源时拒绝启动，且不删除这些资源', async (t) => {
  const { fake, worker } = await readyWorker(t)
  const stale = 'e'.repeat(24)
  fake.state.volumes.push({ Name: 'plaza-sb-fixture-a-work', Driver: 'local', Mountpoint: '/var/lib/docker/volumes/x/_data', Labels: { 'plaza.sandbox.managed': 'v2', [LABEL_RUN]: RUN, [LABEL_ATTEMPT]: stale }, Options: {} })
  fake.state.containers.push({ id: '9'.repeat(64), body: { Name: 'plaza-sb-fixture-a', Labels: { 'plaza.sandbox.managed': 'v2', [LABEL_RUN]: RUN, [LABEL_ATTEMPT]: stale } }, state: 'exited' })
  await assert.rejects(worker.start({ runId: RUN }), code('RUN_EXISTS', /不会动它/))
  assert.deepEqual([fake.state.containers.length, fake.state.volumes.length], [1, 1])
  assert.equal(count(fake, 'removeContainer'), 0)
  assert.equal(count(fake, 'removeVolume'), 0)
  /* 显式回收才清掉它们 */
  assert.deepEqual(await worker.reclaim(RUN), { containers: ['9'.repeat(64)], volumes: ['plaza-sb-fixture-a-work'] })
  clean(fake)
})

test('卷创建报错、或容器名被占用：按已有执行处理，只释放本次自己建的卷', async (t) => {
  const mismatched = await readyWorker(t)
  mismatched.fake.volumeError = new DockerApiError(500, 'error while creating Volume: driver "local" already has a volume "plaza-sb-fixture-a-work" with different options')
  await assert.rejects(mismatched.worker.start({ runId: RUN }), code('RUN_EXISTS', /工作卷已存在且与本次请求不一致.*不会动它/s))
  assert.equal(count(mismatched.fake, 'removeVolume'), 0)
  assert.equal(mismatched.fake.state.containers.length, 0)

  const occupied = await readyWorker(t)
  /* 残留容器没有对应的工作卷：本次认领到新卷，但容器名冲突 */
  occupied.fake.state.containers.push({ id: '7'.repeat(64), body: { Name: 'plaza-sb-fixture-a', Labels: { 'plaza.sandbox.managed': 'v2', [LABEL_RUN]: RUN, [LABEL_ATTEMPT]: 'e'.repeat(24) } }, state: 'exited' })
  await assert.rejects(occupied.worker.start({ runId: RUN }), code('RUN_EXISTS', /容器名已被占用/))
  assert.equal(occupied.fake.state.volumes.length, 0, '本次认领的卷已释放')
  assert.equal(occupied.fake.state.containers.length, 1, '占用名字的残留容器不能被删')
  assert.equal(occupied.fake.state.containers[0].id, '7'.repeat(64))
})

test('回收只处理带本次运行标签的资源，可重复调用，遇到暂时冲突会重试', async (t) => {
  const { fake, worker } = await readyWorker(t)
  fake.state.containers = [
    { id: 'a'.repeat(64), state: 'exited', body: { Name: 'a', Labels: { [LABEL_RUN]: RUN } } },
    { id: 'b'.repeat(64), state: 'running', body: { Name: 'b', Labels: { [LABEL_RUN]: 'other-run' } } },
    { id: 'c'.repeat(64), state: 'exited', body: { Name: 'c', Labels: {} } },
  ]
  fake.state.volumes = [
    { Name: 'plaza-sb-fixture-a-work', Labels: { [LABEL_RUN]: RUN } },
    { Name: 'plaza-sb-other-run-work', Labels: { [LABEL_RUN]: 'other-run' } },
  ]
  fake.removeErrors = 2
  assert.deepEqual(await worker.reclaim(RUN), { containers: ['a'.repeat(64)], volumes: ['plaza-sb-fixture-a-work'] })
  /* 容器：两次冲突后第三次成功；卷一次成功 */
  assert.equal(count(fake, 'removeContainer'), 3)
  assert.equal(count(fake, 'removeVolume'), 1)
  assert.deepEqual(await worker.reclaim(RUN), { containers: [], volumes: [] })
  assert.deepEqual(fake.state.containers.map((item) => item.id[0]), ['b', 'c'])
  assert.deepEqual(fake.state.volumes.map((item) => item.Name), ['plaza-sb-other-run-work'])
})

test('回收后仍有残留时报 RECLAIM_FAILED；非法 runId 不触发任何 Docker 调用', async (t) => {
  const { fake, worker } = await readyWorker(t)
  fake.state.volumes = [{ Name: 'plaza-sb-fixture-a-work', Labels: { [LABEL_RUN]: RUN } }]
  fake.stuck = 'volume'
  await assert.rejects(worker.reclaim(RUN), code('RECLAIM_FAILED', /仍有 1 个资源残留/))
  assert.equal(count(fake, 'removeVolume'), 1)
  const fresh = await readyWorker(t)
  await assert.rejects(fresh.worker.reclaim('../other'), code('INVALID_SPEC', /runId/))
  assert.equal(fresh.fake.calls.length, 0)
})

test('沙箱内不是 gVisor、不是登记的用户或 Node：拒绝就绪并停止容器', async (t) => {
  for (const [probe, pattern] of [
    ['65532|5.15.0-generic|v22.23.5\n', /不是 gVisor/],
    ['0|4.19.0-gvisor|v22.23.5\n', /uid 为 0/],
    ['1000|4.19.0-gvisor|v22.23.5\n', /uid 为 1000/],
    ['65532|4.19.0-gvisor|v20.1.0\n', /Node 为 v20\.1\.0/],
    ['\n', /uid 为 未知/],
  ]) {
    const fake = await fakeDocker(t)
    freshPi(fake)
    scriptedPi(fake.duplex, { probe })
    const worker = new SandboxWorker({ image: await fixture('image.lock.json'), docker: fake })
    await assert.rejects(worker.start({ runId: RUN }), code('RUNTIME_MISMATCH', pattern))
    assert.equal(has(fake, 'stopContainer'), true)
    clean(fake)
  }
})

test('Pi 不回应、会话不在 /work：按未就绪处理并停止容器', async (t) => {
  /* 不接脚本的替身：Pi 对任何命令都不应答 */
  const silent = await readyWorker(t)
  silent.fake.duplex = new FakeDuplex()
  const impatient = new SandboxWorker({ image: silent.lock, docker: silent.fake, readyTimeoutMs: 30 })
  await assert.rejects(impatient.start({ runId: RUN }), code('PI_NOT_READY', /未在 30 毫秒内回应 get_state/))
  assert.equal(has(silent.fake, 'stopContainer'), true)
  clean(silent.fake)
  const misplaced = await readyWorker(t)
  scriptedPi(misplaced.fake.duplex, { state: { ...STATE, sessionFile: '/tmp/session-1.jsonl' } })
  await assert.rejects(misplaced.worker.start({ runId: RUN }), code('PI_NOT_READY', /会话文件不在 \/work 下/))
  clean(misplaced.fake)
  const anonymous = await readyWorker(t)
  scriptedPi(anonymous.fake.duplex, { state: { sessionFile: STATE.sessionFile } })
  await assert.rejects(anonymous.worker.start({ runId: RUN }), code('PI_NOT_READY', /缺少会话 ID/))
  clean(anonymous.fake)
})

test('退出分类：异常退出、到点超时、内存超限、强制终止', async (t) => {
  const dies = (status, error = null) => async (fake, handle) => {
    end(fake, status, error)
    return handle.done
  }
  const cases = [
    ['Pi 异常退出', dies(137), {}, 'error', 137, /退出码 137/],
    ['到点超时', dies(124), {}, 'timeout', 124, /计时器到点/],
    ['内存超限', dies(137, { Message: 'OOM killed' }), { OOMKilled: true }, 'oom', 137, /OOM killed/],
    ['到点后被强杀', dies(137), {}, 'error', 137, /退出码 137/],
    ['沙箱运行时崩溃', dies(2), {}, 'error', 2, /退出码 2/],
    ['强制终止', async (fake, handle) => handle.terminate('operator'), {}, 'terminated', 143, /operator/],
    ['到点后仍在运行被 Worker 兜底停止', async (fake, handle) => handle.terminate('deadline-exceeded'), {}, 'timeout', 143, /deadline-exceeded/],
  ]
  for (const [name, finish, state, outcome, exitCode, pattern] of cases) {
    const { fake, worker } = await readyWorker(t)
    fake.mutateRunning = (copy) => Object.assign(copy.State, state)
    const handle = await worker.start({ runId: RUN })
    const result = await finish(fake, handle)
    assert.equal(result.outcome, outcome, name)
    assert.equal(result.exitCode, exitCode, name)
    assert.match(result.reason, pattern)
    assert.equal(result.oomKilled, Boolean(state.OOMKilled), name)
    assert.deepEqual(result.reclaimed, { containers: 1, volumes: 1 }, name)
    clean(fake)
  }
})

test('超过时限仍在运行：Worker 到点兜底强制停止', async (t) => {
  const { fake, lock } = await readyWorker(t)
  const worker = new SandboxWorker({ image: lock, docker: fake, readyTimeoutMs: 1000, deadlineGraceMs: 200 })
  const handle = await worker.start({ runId: RUN, limits: { maxDurationSec: 1 } })
  assert.equal(has(fake, 'stopContainer'), false)
  const result = await handle.done
  assert.equal(result.outcome, 'timeout')
  assert.equal(result.reason, 'deadline-exceeded')
  assert.ok(result.durationMs >= 1200 && result.durationMs < 5000, `用时 ${result.durationMs} ms`)
  assert.equal(has(fake, 'stopContainer'), true)
  clean(fake)
})

test('Pi 中途死亡：未完成请求被拒绝，结果如实报错', async (t) => {
  const fake = await fakeDocker(t)
  freshPi(fake)
  fake.duplex.onWrite = (text) => {
    const message = JSON.parse(text)
    const reply = (data) => fake.duplex.pushOut(`${JSON.stringify({ id: message.id, type: 'response', command: message.type, success: true, data })}\n`)
    if (message.type === 'get_state') reply(STATE)
    else if (message.command === 'kill -KILL $PPID') end(fake, 137)
    else reply({ output: PROBE, exitCode: 0, cancelled: false, truncated: false })
  }
  const worker = new SandboxWorker({ image: await fixture('image.lock.json'), docker: fake })
  const handle = await worker.start({ runId: RUN })
  await assert.rejects(handle.rpc.bash('kill -KILL $PPID'), code('RPC_CLOSED', /Pi 标准输出已结束/))
  const result = await handle.done
  assert.equal(result.outcome, 'error')
  assert.equal(result.exitCode, 137)
  clean(fake)
})
