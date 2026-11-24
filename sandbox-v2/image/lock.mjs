#!/usr/bin/env node
// 生成镜像内 Pi 的依赖锁。Pi 自带的 npm-shrinkwrap 对其 monorepo 自发包不写 integrity，
// 这里按 registry 元数据补全，并下载压缩包实测 sha512 交叉核对后才写入锁。
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))

export async function refreshLock() {
  const dir = join(here, 'pi')
  const lockPath = join(dir, 'package-lock.json')
  execFileSync('npm', ['install', '--package-lock-only', '--ignore-scripts', '--no-audit', '--no-fund', '--no-progress'], {
    cwd: dir,
    stdio: ['ignore', 'ignore', 'inherit'],
  })
  const lock = JSON.parse(readFileSync(lockPath, 'utf8'))
  const missing = Object.entries(lock.packages).filter(([, entry]) => entry?.resolved && !entry.integrity)
  for (const [key, entry] of missing) {
    const name = key.slice(key.lastIndexOf('node_modules/') + 'node_modules/'.length)
    const spec = `${name}@${entry.version}`
    const meta = JSON.parse(execFileSync('npm', ['view', spec, 'dist.tarball', 'dist.integrity', '--json'], { encoding: 'utf8' }))
    const { 'dist.tarball': tarball, 'dist.integrity': integrity } = meta
    if (tarball !== entry.resolved) throw new Error(`${spec} 的 registry 地址与锁不一致：${tarball} ≠ ${entry.resolved}`)
    const res = await fetch(tarball)
    if (!res.ok) throw new Error(`${spec} 下载失败：HTTP ${res.status}`)
    const actual = 'sha512-' + createHash('sha512').update(Buffer.from(await res.arrayBuffer())).digest('base64')
    if (actual !== integrity) throw new Error(`${spec} 实测 sha512 与 registry 不一致`)
    entry.integrity = actual
    console.log(`已补全 ${spec}`)
  }
  writeFileSync(lockPath, JSON.stringify(lock, null, 2) + '\n')
  console.log(`依赖锁共 ${Object.keys(lock.packages).length - 1} 个包，补全 ${missing.length} 个 integrity`)
}

if (process.argv[1] && import.meta.url === `file://${process.argv[1]}`) {
  refreshLock().catch((error) => {
    console.error(error instanceof Error ? error.message : error)
    process.exit(1)
  })
}
