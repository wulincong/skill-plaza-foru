#!/usr/bin/env node
/* 从一次真实运行抓取测试夹具：Docker 对镜像、容器、工作卷的原始回报，以及对应的核对期望。
   需要本机 Docker、runsc 与已登记的镜像。重建镜像后重新执行：node sandbox-v2/test/capture-fixtures.mjs */

import { randomBytes } from 'node:crypto'
import { chmod, mkdir, mkdtemp, realpath, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { buildCreateRequest, DEFAULT_LIMITS } from '../src/spec.ts'
import { SandboxWorker, loadImageLock } from '../src/sandbox.ts'

const here = dirname(fileURLToPath(import.meta.url))
const output = join(here, 'fixtures')
const RUN = 'fixture-a'
const NEUTRAL_INPUT = '/srv/plaza/inputs/task'

const lock = await loadImageLock()
const root = await mkdtemp(join(tmpdir(), 'plaza-fixture-'))
try {
  const inputsRoot = join(root, 'inputs')
  const input = join(inputsRoot, 'task')
  await mkdir(input, { recursive: true })
  await chmod(inputsRoot, 0o755)
  await chmod(input, 0o755)
  await writeFile(join(input, 'brief.txt'), 'fixture\n', { mode: 0o644 })
  const source = await realpath(input)
  // 夹具里的宿主路径统一改写成中性路径，其余保持 Docker 的真实回报
  const sanitize = (value) => JSON.parse(JSON.stringify(value).split(source).join(NEUTRAL_INPUT))

  const worker = new SandboxWorker({ image: lock, inputsRoot })
  const handle = await worker.start({ runId: RUN, inputs: [{ hostPath: input, target: '/input/task' }] })
  const image = await worker.docker.inspectImage(lock.id)
  const built = buildCreateRequest({
    runId: RUN,
    imageRef: lock.id,
    imageId: lock.id,
    entrypoint: lock.entrypoint,
    imageEnv: image.Config.Env,
    imageLabels: image.Config.Labels,
    user: lock.user,
    attempt: handle.attempt,
    limits: DEFAULT_LIMITS,
    inputs: [{ source, target: '/input/task', kind: 'directory' }],
  })
  const running = await worker.docker.inspectContainer(handle.containerId)
  const volume = (await worker.docker.listVolumes({ label: [`plaza.sandbox.run=${RUN}`] })).Volumes[0]
  await handle.shutdown()

  await mkdir(output, { recursive: true })
  const files = {
    'image.lock.json': lock,
    'image.json': sanitize(image),
    'container-created.json': sanitize(handle.inspect),
    'container-running.json': sanitize(running),
    'expected.json': { ...sanitize(built.expected), imageId: lock.id },
    'volume.json': sanitize(volume),
  }
  for (const [name, value] of Object.entries(files)) await writeFile(join(output, name), `${JSON.stringify(value, null, 2)}\n`)
  console.log(`已写入 ${Object.keys(files).length} 个夹具（镜像 ${lock.id.slice(7, 19)}…），本次运行已回收：${JSON.stringify(await worker.list(RUN))}`)
} finally {
  await rm(root, { recursive: true, force: true })
}
