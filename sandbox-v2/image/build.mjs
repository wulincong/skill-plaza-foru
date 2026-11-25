#!/usr/bin/env node
// 构建固定版本 Pi 镜像。构建上下文只装入列明的四个文件，不读取仓库其他内容、宿主环境或凭据；
// 构建后把镜像 ID 等不可变标识写入 sandbox-v2/image.lock.json，Worker 只认这份锁。
import { execFileSync } from 'node:child_process'
import { cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))

export async function buildImage() {
  const root = join(here, '..')
  const imageName = process.env.PLAZA_SANDBOX_IMAGE_NAME || 'plaza-sandbox-pi'
  const CONTEXT_FILES = ['Dockerfile', 'entrypoint.sh', 'pi/package.json', 'pi/package-lock.json']
  const ENTRYPOINT = ['/usr/bin/tini', '-g', '--', '/usr/local/sbin/plaza-sandbox-pi']

  const pkg = JSON.parse(readFileSync(join(here, 'pi/package.json'), 'utf8'))
  const lock = JSON.parse(readFileSync(join(here, 'pi/package-lock.json'), 'utf8'))
  const piVersion = pkg.dependencies['@earendil-works/pi-coding-agent']
  const piEntry = lock.packages['node_modules/@earendil-works/pi-coding-agent']
  const unlocked = Object.entries(lock.packages).filter(([, entry]) => entry?.resolved && !entry.integrity)
  if (!piVersion || lock.packages[''].dependencies['@earendil-works/pi-coding-agent'] !== piVersion || piEntry?.version !== piVersion || unlocked.length) {
    throw new Error('依赖锁与 package.json 不一致或缺 integrity，先运行 node sandbox-v2/image/lock.mjs')
  }

  const dockerfile = readFileSync(join(here, 'Dockerfile'), 'utf8')
  const from = /^FROM\s+(\S+)@(sha256:[0-9a-f]{64})\s*$/m.exec(dockerfile)
  if (!from) throw new Error('Dockerfile 必须以摘要固定基础镜像')

  const context = mkdtempSync(join(tmpdir(), 'plaza-sandbox-image-'))
  try {
    for (const file of CONTEXT_FILES) {
      mkdirSync(dirname(join(context, file)), { recursive: true })
      cpSync(join(here, file), join(context, file))
    }
    const tag = `${imageName}:${piVersion}`
    execFileSync('docker', [
      'build', '--pull=false',
      '--label', `plaza.sandbox.pi.version=${piVersion}`,
      '--label', `plaza.sandbox.base.digest=${from[2]}`,
      '--tag', tag, context,
    ], { stdio: 'inherit' })

    const [image] = JSON.parse(execFileSync('docker', ['image', 'inspect', tag], { encoding: 'utf8' }))
    const nodeVersion = image.Config.Env.find((entry) => entry.startsWith('NODE_VERSION=')).slice('NODE_VERSION='.length)
    const repoDigest = image.RepoDigests.find((entry) => entry.startsWith(`${imageName}@sha256:`))?.split('@')[1] ?? null
    if (!/^sha256:[0-9a-f]{64}$/.test(image.Id)) throw new Error(`镜像 ID 非法：${image.Id}`)
    const labels = image.Config.Labels
    if (image.Config.User !== '65532:65532') throw new Error(`镜像运行用户不是 65532:65532：${image.Config.User}`)
    if (image.Config.Entrypoint.join(' ') !== ENTRYPOINT.join(' ')) throw new Error(`镜像入口不是 ${ENTRYPOINT.join(' ')}`)
    if (labels['plaza.sandbox.pi.version'] !== piVersion) throw new Error('镜像标签与 Pi 版本不一致')
    if (labels['plaza.sandbox.base.digest'] !== from[2]) throw new Error('镜像标签与基础镜像摘要不一致')

    // 镜像 ID 是镜像配置（含全部层摘要）的 sha256；本机构建不保证逐字节可复现，每次构建后重新登记。
    writeFileSync(join(root, 'image.lock.json'), JSON.stringify({
      name: imageName,
      tag,
      id: image.Id,
      repoDigest,
      piVersion,
      piIntegrity: piEntry.integrity,
      nodeVersion,
      baseReference: from[1],
      baseDigest: from[2],
      user: image.Config.User,
      entrypoint: image.Config.Entrypoint,
      layers: image.RootFS.Layers,
    }, null, 2) + '\n')
    console.log(`已写入 sandbox-v2/image.lock.json：${imageName} ${piVersion}，镜像 ${image.Id}，${image.RootFS.Layers.length} 层`)
  } finally {
    rmSync(context, { recursive: true, force: true })
  }
}

if (process.argv[1] && import.meta.url === `file://${process.argv[1]}`) {
  buildImage().catch((error) => {
    console.error(error instanceof Error ? error.message : error)
    process.exit(1)
  })
}
