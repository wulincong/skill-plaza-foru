/* 从宿主 cgroup 读回 Docker 实际写入容器的限额与用量（只读）。
   Worker 与守护进程不在同一主机、或无权读取时返回 null；此时只以 Docker inspect 的配置为准。 */

import { readFile } from 'node:fs/promises'

export interface HostCgroupLimits {
  path: string
  cpuMax: string
  memoryMax: string
  memorySwapMax: string
  pidsMax: string
  memoryCurrent: number
  pidsCurrent: number
  cpuUsageUsec: number
  cpuThrottledPeriods: number
}

async function readText(base: string, file: string): Promise<string | null> {
  try {
    return (await readFile(`${base}/${file}`, 'utf8')).trim()
  } catch {
    return null
  }
}

async function resolveCgroup(pid: number): Promise<string | null> {
  if (!Number.isInteger(pid) || pid <= 0) return null
  try {
    const line = (await readFile(`/proc/${pid}/cgroup`, 'utf8')).split('\n').find((item) => item.startsWith('0::')) ?? ''
    const relative = line.slice(3)
    return relative.startsWith('/') ? relative : null
  } catch {
    return null
  }
}

async function readScope(relative: string): Promise<HostCgroupLimits | null> {
  const base = `/sys/fs/cgroup${relative}`
  const [cpuMax, memoryMax, memorySwapMax, pidsMax, memoryCurrent, pidsCurrent, cpuStat] = await Promise.all([
    readText(base, 'cpu.max'),
    readText(base, 'memory.max'),
    readText(base, 'memory.swap.max'),
    readText(base, 'pids.max'),
    readText(base, 'memory.current'),
    readText(base, 'pids.current'),
    readText(base, 'cpu.stat'),
  ])
  if (cpuMax === null || memoryMax === null || memorySwapMax === null || pidsMax === null || memoryCurrent === null) return null
  const usage = /^usage_usec (\d+)$/m.exec(cpuStat ?? '')
  const throttled = /^nr_throttled (\d+)$/m.exec(cpuStat ?? '')
  return {
    path: relative,
    cpuMax,
    memoryMax,
    memorySwapMax,
    pidsMax,
    memoryCurrent: Number(memoryCurrent),
    pidsCurrent: Number(pidsCurrent),
    cpuUsageUsec: usage ? Number(usage[1]) : NaN,
    cpuThrottledPeriods: throttled ? Number(throttled[1]) : NaN,
  }
}

export async function readHostLimits(pid: number): Promise<HostCgroupLimits | null> {
  const relative = await resolveCgroup(pid)
  if (!relative) return null
  /* runsc 会把沙箱进程放进容器的子 cgroup；限额在 docker-<id>.scope 这一层 */
  const parts = relative.split('/').filter(Boolean)
  const scope = parts.findIndex((part) => /^docker-.+\.scope$/.test(part))
  const candidates = scope >= 0 ? [`/${parts.slice(0, scope + 1).join('/')}`, relative] : [relative]
  const found: HostCgroupLimits[] = []
  for (const candidate of candidates) {
    const limits = await readScope(candidate)
    if (limits) found.push(limits)
  }
  return found.find((item) => item.pidsMax !== 'max') ?? found[0] ?? null
}
