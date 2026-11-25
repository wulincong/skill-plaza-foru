#!/usr/bin/env node
/* 受信 Worker 的运维入口：核对镜像登记、查看预检结果、列出与回收指定运行的沙箱资源。
   回收只处理带本次运行标签的容器与工作卷。 */

import { SandboxError, errorMessage } from '../src/errors.ts'
import { verifyLockSources } from '../src/registry.ts'
import { SandboxWorker, loadImageLock, type ImageLock } from '../src/sandbox.ts'
import { MANAGED_VALUE, LABEL_MANAGED, assertRunId } from '../src/spec.ts'

const HELP = `用法：node sandbox-v2/bin/sandbox.ts <命令>

  verify-image            核对镜像登记与源码、本机镜像是否一致
  preflight               核对 Docker、运行时与镜像（启动前的三道门）
  list                    列出本机带广场沙箱标签的容器与工作卷
  reclaim <runId>         回收指定运行的容器与工作卷（可重复执行）
`

async function registry(worker: SandboxWorker, lock: ImageLock): Promise<number> {
  const problems = [...(await verifyLockSources(lock)), ...(await worker.registryProblems())]
  for (const problem of problems) console.log(`不符：${problem}`)
  if (!problems.length) console.log(`镜像登记一致：${lock.name} ${lock.piVersion} ${lock.id}`)
  return problems.length ? 1 : 0
}

export async function main(argv: string[]): Promise<number> {
  const [command, argument] = argv
  if (!command || command === 'help' || command === '--help' || command === '-h') {
    console.log(HELP)
    return command ? 0 : 2
  }
  const lock = await loadImageLock()
  const worker = new SandboxWorker({ image: lock })
  if (command === 'verify-image') return registry(worker, lock)
  if (command === 'preflight') {
    const report = await worker.preflight()
    console.log(`Docker ${report.docker.version}（API ${report.docker.apiVersion}），运行时 ${report.docker.runtime} → ${report.docker.runtimePath}，守护进程默认运行时 ${report.docker.defaultRuntime}`)
    console.log(`镜像 ${report.image.id}（Pi ${report.image.piVersion}，Node ${report.image.nodeVersion}，基础镜像 ${report.image.baseDigest}）`)
    return 0
  }
  if (command === 'list') {
    const label = `${LABEL_MANAGED}=${MANAGED_VALUE}`
    const containers = await worker.docker.listContainers({ label: [label] })
    const volumes = (await worker.docker.listVolumes({ label: [label] })).Volumes ?? []
    for (const item of containers) console.log(`容器 ${item.Names?.[0] ?? item.Id.slice(0, 12)}  ${item.State}  run=${item.Labels?.['plaza.sandbox.run'] ?? '?'}`)
    for (const item of volumes) console.log(`工作卷 ${item.Name}  run=${item.Labels?.['plaza.sandbox.run'] ?? '?'}`)
    console.log(`共 ${containers.length} 个容器，${volumes.length} 个工作卷`)
    return 0
  }
  if (command === 'reclaim') {
    assertRunId(argument ?? '')
    const before = await worker.list(argument)
    const report = await worker.reclaim(argument)
    console.log(`已回收 ${argument}：容器 ${report.containers.length} 个，工作卷 ${report.volumes.length} 个（回收前：${[...before.containers, ...before.volumes].join('、') || '无'}）`)
    return 0
  }
  console.log(`未知命令：${command}\n\n${HELP}`)
  return 2
}

if (process.argv[1] && import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv.slice(2)).then(
    (code) => process.exit(code),
    (error) => {
      console.error(`${error instanceof SandboxError ? `${error.code}：` : ''}${errorMessage(error)}`)
      if (error instanceof SandboxError && Array.isArray(error.details)) for (const item of error.details) console.error(`  - ${item}`)
      process.exit(1)
    },
  )
}
