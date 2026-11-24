/* 镜像登记与源码的一致性核对：登记的 Pi 版本、基础镜像摘要必须与 package.json、依赖锁、Dockerfile 一致。 */

import { readFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { DEFAULT_IMAGE_LOCK_FILE, type ImageLock } from './sandbox.ts'

const DIGEST = /^sha256:[0-9a-f]{64}$/
const PI_PACKAGE = '@earendil-works/pi-coding-agent'

interface DependencyEntry {
  version?: string
  resolved?: string
  integrity?: string
  dependencies?: Record<string, string>
}

export async function verifyLockSources(lock: ImageLock, lockFile: string = DEFAULT_IMAGE_LOCK_FILE): Promise<string[]> {
  const problems: string[] = []
  const imageDir = join(dirname(lockFile), 'image')
  const read = async (file: string) => readFile(join(imageDir, file), 'utf8')
  const [pkgText, dependenciesText, dockerfile] = await Promise.all(['pi/package.json', 'pi/package-lock.json', 'Dockerfile'].map(read))
  const pkg = JSON.parse(pkgText) as { dependencies: Record<string, string> }
  const dependencies = JSON.parse(dependenciesText) as { packages: Record<string, DependencyEntry> }
  const entry = dependencies.packages[`node_modules/${PI_PACKAGE}`]
  const unpinned = Object.entries(dependencies.packages).filter(([, item]) => item?.resolved && !item.integrity)
  if (pkg.dependencies[PI_PACKAGE] !== lock.piVersion || entry?.version !== lock.piVersion || dependencies.packages[''].dependencies?.[PI_PACKAGE] !== lock.piVersion) {
    problems.push(`package.json 与依赖锁的 Pi 版本与登记的 ${lock.piVersion} 不一致`)
  }
  if (entry?.integrity !== lock.piIntegrity) problems.push('依赖锁中 Pi 的 integrity 与登记不符')
  if (unpinned.length) problems.push(`依赖锁有 ${unpinned.length} 个条目缺少 integrity：${unpinned.map(([key]) => key.split('node_modules/').pop()).join(', ')}`)
  const from = /^FROM\s+(\S+)@(sha256:[0-9a-f]{64})\s*$/m.exec(dockerfile)
  if (!from) problems.push('Dockerfile 未以摘要固定基础镜像')
  else if (from[2] !== lock.baseDigest) problems.push(`Dockerfile 的基础镜像摘要 ${from[2].slice(0, 19)}… 与登记不符`)
  if (!DIGEST.test(lock.baseDigest)) problems.push('登记的基础镜像摘要格式非法')
  return problems
}
