#!/usr/bin/env node
/* 离线沙箱第一步的一键验收。只用真实 Docker、runsc 与真实 Pi 的 RPC，不接在线模型；
   测试标记均为无敏感内容的随机串。只清理本次创建的容器、工作卷与临时目录。 */

import { execFile } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { rmSync } from 'node:fs'
import { chmod, mkdir, mkdtemp, readFile, realpath, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, join } from 'node:path'
import { promisify } from 'node:util'
import type { DockerClient } from '../src/docker.ts'
import { SandboxError, errorMessage } from '../src/errors.ts'
import { readHostLimits } from '../src/host.ts'
import type { PiBashResult } from '../src/pi-rpc.ts'
import { verifyLockSources } from '../src/registry.ts'
import { SandboxWorker, loadImageLock, type SandboxHandle, type SandboxResult } from '../src/sandbox.ts'
import { DEFAULT_LIMITS, LABEL_MANAGED, MANAGED_VALUE, SESSION_DIR, type SandboxLimits } from '../src/spec.ts'

interface Check {
  name: string
  status: 'pass' | 'fail'
  detail: string
  ms: number
}

const runCommand = promisify(execFile)
/* 在沙箱内持续派生常驻进程，直到派生被拒。用 Node 自己的 spawn：失败立即回报，
   不像 shell 会在被拒后反复重试。created 是成功派生的进程数 */
const FORK_PROBE =
  'node -e \'const {spawn}=require("child_process");let ok=0;'
  + 'const tick=()=>{const c=spawn("sleep",["30"],{stdio:"ignore"});c.on("spawn",()=>{ok++});'
  + 'c.on("error",e=>{console.log("created="+ok+" stop="+e.code);process.exit(0)});setImmediate(tick)};tick()\''

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new SandboxError('VERIFY_FAILED', message)
}

/* df -P -B1 的 total/used/avail：总量等于上限且写满后可用为 0 */
function fullDisk(output: string, limit: number): boolean {
  const fields = Object.fromEntries([...output.matchAll(/(total|used|avail)=(\d+)/g)].map((match) => [match[1], Number(match[2])]))
  return fields.total === limit && fields.avail === 0 && fields.used === limit
}

export async function runAcceptance(args: string[] = process.argv.slice(2)): Promise<number> {
  const jsonOutput = args.includes('--json')
  const checks: Check[] = []
  const startedAt = new Date()
  const log = (line: string) => {
    if (!jsonOutput) console.log(line)
  }
  const check = async (name: string, body: () => Promise<unknown>): Promise<boolean> => {
    const began = Date.now()
    try {
      const value = await body()
      const detail = value === undefined || value === '' ? '' : typeof value === 'string' ? value : JSON.stringify(value)
      checks.push({ name, status: 'pass', detail, ms: Date.now() - began })
      log(`通过  ${name}${detail ? `  —  ${detail}` : ''}`)
      return true
    } catch (error) {
      const parts = error instanceof SandboxError && Array.isArray(error.details) ? [error.message, ...error.details] : [errorMessage(error)]
      const detail = parts.join('；')
      checks.push({ name, status: 'fail', detail, ms: Date.now() - began })
      log(`失败  ${name}  —  ${detail}`)
      return false
    }
  }

  const stamp = Date.now().toString(36)
  const prefix = `acc-${stamp}-${process.pid.toString(36)}`
  const nonce = randomBytes(8).toString('hex')
  const INPUT_TEXT = `plaza-sandbox-acceptance-input ${nonce}`
  const HOST_MARKER = `plaza-sandbox-acceptance-host-marker ${nonce}`
  const MARKER_A = `plaza-sandbox-acceptance-work-marker-a ${nonce}`
  const MARKER_B = `plaza-sandbox-acceptance-work-marker-b ${nonce}`

  const lock = await loadImageLock()
  const root = await mkdtemp(join(tmpdir(), 'plaza-sandbox-acceptance-'))
  const inputsRoot = join(root, 'inputs')
  const inputDir = join(inputsRoot, 'task')
  const inputText = `${INPUT_TEXT}\n`
  const hostMarkerPath = join(inputsRoot, 'host-marker.txt')
  const hostMarkerText = `${HOST_MARKER}\n`
  await mkdir(inputDir, { recursive: true, mode: 0o755 })
  await chmod(inputsRoot, 0o755)
  await chmod(inputDir, 0o755)
  await writeFile(join(inputDir, 'brief.txt'), inputText, { mode: 0o644 })
  await writeFile(hostMarkerPath, hostMarkerText, { mode: 0o644 })
  const inputs = [{ hostPath: inputDir, target: '/input/task' }]

  const worker = new SandboxWorker({ image: lock, inputsRoot })
  const runIds = new Set<string>()
  const handles = new Set<SandboxHandle>()

  const managed = async (): Promise<string[]> => {
    const label = `${LABEL_MANAGED}=${MANAGED_VALUE}`
    const containers = (await worker.docker.listContainers({ label: [label] })).map((item) => item.Id)
    const volumes = ((await worker.docker.listVolumes({ label: [label] })).Volumes ?? []).map((item) => item.Name)
    return [...containers, ...volumes].sort()
  }

  const cleanup = async (): Promise<string[]> => {
    const problems: string[] = []
    for (const handle of handles) {
      try {
        await handle.terminate('acceptance-cleanup')
      } catch (error) {
        problems.push(`${handle.runId}：${errorMessage(error)}`)
      }
    }
    handles.clear()
    for (const runId of runIds) {
      try {
        await worker.reclaim(runId)
      } catch (error) {
        problems.push(`${runId}：${errorMessage(error)}`)
      }
    }
    return problems
  }

  for (const signal of ['SIGINT', 'SIGTERM'] as const) {
    process.once(signal, () => {
      void cleanup().finally(() => {
        rmSync(root, { recursive: true, force: true })
        process.exit(130)
      })
    })
  }

  const track = (handle: SandboxHandle): SandboxHandle => {
    runIds.add(handle.runId)
    handles.add(handle)
    return handle
  }
  const open = async (name: string, limits: Partial<SandboxLimits> = {}): Promise<SandboxHandle> => {
    runIds.add(`${prefix}-${name}`)
    return track(await worker.start({ runId: `${prefix}-${name}`, inputs, limits }))
  }
  const close = async (handle: SandboxHandle): Promise<SandboxResult> => {
    handles.delete(handle)
    const guard = setTimeout(() => void handle.terminate('acceptance-cleanup'), 20_000)
    const result = await handle.shutdown()
    clearTimeout(guard)
    return result
  }
  const isolated = async <T>(
    name: string,
    limits: Partial<SandboxLimits>,
    body: (handle: SandboxHandle) => Promise<T>,
  ): Promise<T> => {
    const handle = await open(name, limits)
    try {
      return await body(handle)
    } finally {
      if (handles.has(handle)) await handle.terminate('acceptance-cleanup').catch(() => undefined)
      handles.delete(handle)
    }
  }
  const sh = (handle: SandboxHandle, command: string, timeoutMs = 120_000): Promise<PiBashResult> =>
    handle.bash(command, { excludeFromContext: true, timeoutMs })
  const hostLimits = async (handle: SandboxHandle) =>
    readHostLimits((await worker.docker.inspectContainer(handle.containerId)).State.Pid)
  const cleanRun = async (runId: string, what: string) => {
    const left = await worker.list(runId)
    assert(!left.containers.length && !left.volumes.length, `${what}后仍有资源：${[...left.containers, ...left.volumes].join('，')}`)
  }
  const fullyReclaimed = (result: SandboxResult) => result.reclaimed.containers === 1 && result.reclaimed.volumes === 1
  const failureCode = async (start: () => Promise<unknown>): Promise<SandboxError> => {
    try {
      await start()
    } catch (error) {
      assert(error instanceof SandboxError, `抛出的不是 SandboxError：${errorMessage(error)}`)
      return error
    }
    throw new SandboxError('VERIFY_FAILED', '本应失败的启动却成功了')
  }

  let baseline: string[] = []
  let code = 1
  try {
    baseline = await managed()
    code = await main()
  } catch (error) {
    checks.push({ name: '验收过程异常中断', status: 'fail', detail: errorMessage(error), ms: 0 })
    log(`异常  ${errorMessage(error)}`)
    await cleanup()
  } finally {
    rmSync(root, { recursive: true, force: true })
  }

  const failed = checks.filter((item) => item.status === 'fail').length
  const summary = {
    startedAt: startedAt.toISOString(),
    endedAt: new Date().toISOString(),
    image: lock.id,
    piVersion: lock.piVersion,
    nodeVersion: lock.nodeVersion,
    passed: checks.length - failed,
    failed,
    checks,
  }
  if (jsonOutput) console.log(JSON.stringify(summary, null, 2))
  else console.log(`\n验收完成：通过 ${summary.passed} 项，失败 ${failed} 项，镜像 ${lock.id.slice(7, 19)}…（Pi ${lock.piVersion}）`)
  return failed ? 1 : code

  async function main(): Promise<number> {
    await check('镜像登记与源码一致', async () => {
      const problems = [...(await verifyLockSources(lock)), ...(await worker.registryProblems())]
      assert(!problems.length, '登记不一致')
      return `Pi ${lock.piVersion}，基础镜像 ${lock.baseDigest.slice(7, 19)}…`
    })

    await check('启动前门禁：Docker 可达、runsc 已注册、镜像与登记相符', async () => {
      const report = await worker.preflight()
      let release = ''
      try {
        release = (await runCommand(report.docker.runtimePath, ['--version'])).stdout.split('\n')[0]
      } catch {
        release = '版本不可读'
      }
      return `Docker ${report.docker.version}，${report.docker.runtime} → ${report.docker.runtimePath}（${release}），守护进程默认运行时 ${report.docker.defaultRuntime}`
    })

    await check('Worker 只允许 runsc：其他运行时在创建任何资源之前被拒绝', async () => {
      const outcomes: string[] = []
      for (const runtime of ['runc', 'runc-master', '']) {
        try {
          new SandboxWorker({ image: lock, runtime })
          throw new SandboxError('VERIFY_FAILED', `${JSON.stringify(runtime)} 被接受`)
        } catch (error) {
          assert(error instanceof SandboxError && error.code === 'INVALID_SPEC', errorMessage(error))
          outcomes.push(JSON.stringify(runtime))
        }
      }
      await cleanRun(`${prefix}-none`, '运行时被拒')
      return `runc 等值均返回 INVALID_SPEC，没有触达 Docker 的资源接口`
    })

    await check('指定运行时不可用时明确失败且不启动', async () => {
      const runId = `${prefix}-runtime-missing`
      runIds.add(runId)
      /* 本机的 runsc 已注册，不能为了测试去改守护进程配置。用一个只遮蔽 info 里 runsc 的包装客户端，
         让预检看到“未注册”；资源的创建与核对仍然对着真实守护进程 */
      const blind = Object.create(worker.docker) as DockerClient
      blind.info = async () => {
        const info = await worker.docker.info()
        const { runsc: _registered, ...rest } = info.Runtimes ?? {}
        return { ...info, Runtimes: rest }
      }
      const failure = await failureCode(() => new SandboxWorker({ image: lock, inputsRoot, docker: blind }).start({ runId, inputs }))
      assert(failure.code === 'RUNTIME_UNAVAILABLE', `期望 RUNTIME_UNAVAILABLE，实际 ${failure.code}`)
      await cleanRun(runId, '运行时缺失')
      return '返回 RUNTIME_UNAVAILABLE，没有创建容器或工作卷，也没有回退到其他运行时'
    })

    await check('镜像只能按登记的摘要启动', async () => {
      const outcomes: string[] = []
      try {
        new SandboxWorker({ image: { ...lock, id: `${lock.name}:${lock.piVersion}` } })
        throw new SandboxError('VERIFY_FAILED', '标签被当作镜像标识接受')
      } catch (error) {
        assert(error instanceof SandboxError && error.code === 'IMAGE_LOCK', errorMessage(error))
        outcomes.push('标签被拒绝')
      }
      const cases: [string, typeof lock][] = [
        ['不存在的摘要', { ...lock, id: `sha256:${'0'.repeat(64)}` }],
        ['与登记不符的镜像', { ...lock, piVersion: '0.0.0' }],
      ]
      for (const [label, image] of cases) {
        const runId = `${prefix}-image-${outcomes.length}`
        runIds.add(runId)
        const failure = await failureCode(() => new SandboxWorker({ image, inputsRoot }).start({ runId, inputs }))
        assert(failure.code === 'IMAGE_LOCK', `${label}：期望 IMAGE_LOCK，实际 ${failure.code}`)
        await cleanRun(runId, label)
        outcomes.push(`${label}被拒绝`)
      }
      return outcomes.join('，')
    })

    await check('挂输入却未配置受信输入根目录时拒绝启动', async () => {
      const runId = `${prefix}-no-input-root`
      runIds.add(runId)
      const failure = await failureCode(() => new SandboxWorker({ image: lock }).start({ runId, inputs }))
      assert(failure.code === 'INVALID_SPEC' && /inputsRoot/.test(failure.message), `期望 INVALID_SPEC 并指出 inputsRoot，实际 ${failure.code}：${failure.message}`)
      await cleanRun(runId, '缺输入根')
      return '返回 INVALID_SPEC，没有创建容器或工作卷；输入范围不会落到当前目录'
    })

    const openedAt = Date.now()
    let readyMs = 0
    const started = await check('启动沙箱 A：Docker 侧核对通过、Pi 就绪', async () => {
      await open('a')
      readyMs = Date.now() - openedAt
      return `${readyMs} ms`
    })
    if (!started) return finish()
    const a = [...handles][0]

    await check('Docker 回报：运行时为 runsc，按登记的镜像 ID 启动', async () => {
      const running = await worker.docker.inspectContainer(a.containerId)
      assert(running.HostConfig.Runtime === 'runsc', `运行时为 ${running.HostConfig.Runtime}`)
      assert(running.Image === lock.id && running.Config.Image === lock.id, '容器没有按登记的镜像 ID 启动')
      return `${running.HostConfig.Runtime}，镜像 ${running.Image.slice(7, 19)}…`
    })

    await check('Docker 回报：挂载清单与读写权限', async () => {
      const running = await worker.docker.inspectContainer(a.containerId)
      const mounts = running.Mounts.map((m) => `${m.Type}:${m.Type === 'volume' ? m.Name : m.Source}→${m.Destination}:${m.RW ? 'rw' : 'ro'}`).sort()
      const expected = [`bind:${await realpath(inputDir)}→/input/task:ro`, `volume:${a.workVolume}→/work:rw`].sort()
      assert(JSON.stringify(mounts) === JSON.stringify(expected), `挂载为 ${mounts.join('，')}`)
      return mounts.join('，')
    })

    await check('Docker 回报：非 root、根只读、无 capability、禁止提权、离线、不落日志', async () => {
      const created = a.inspect
      const running = await worker.docker.inspectContainer(a.containerId)
      const hc = created.HostConfig
      assert(created.Config.User === lock.user && !/^0(:|$)/.test(created.Config.User), `运行用户 ${created.Config.User}`)
      assert(hc.ReadonlyRootfs === true, '根文件系统不是只读')
      assert((hc.CapDrop ?? []).includes('ALL') && !(hc.CapAdd ?? []).length, `capability：drop=${JSON.stringify(hc.CapDrop)} add=${JSON.stringify(hc.CapAdd)}`)
      assert((hc.SecurityOpt ?? []).some((opt) => /^no-new-privileges(:true)?$/.test(opt)), `未禁止提权：${JSON.stringify(hc.SecurityOpt)}`)
      assert(hc.Privileged === false && !(hc.Devices ?? []).length && !(hc.DeviceRequests ?? []).length, '容器带有特权或设备')
      assert(hc.NetworkMode === 'none' && JSON.stringify(Object.keys(running.NetworkSettings.Networks)) === '["none"]', `网络为 ${hc.NetworkMode}`)
      assert(running.HostConfig.LogConfig.Type === 'none', `日志驱动为 ${running.HostConfig.LogConfig.Type}`)
      assert(!/KEY|TOKEN|SECRET|PASSWORD/i.test(JSON.stringify(created.Config.Env)), '容器环境含凭据样式变量')
      return `uid ${created.Config.User}，CapDrop=ALL，no-new-privileges，network=none，日志驱动 none`
    })

    await check('Docker 与宿主 cgroup：CPU、内存、交换、进程上限', async () => {
      const hc = a.inspect.HostConfig
      assert(hc.NanoCpus === DEFAULT_LIMITS.cpus * 1e9, `CPU 配额 ${hc.NanoCpus}`)
      assert(hc.Memory === DEFAULT_LIMITS.memoryMiB * 1048576 && hc.MemorySwap === hc.Memory, `内存 ${hc.Memory}/${hc.MemorySwap}`)
      assert(hc.PidsLimit === DEFAULT_LIMITS.pids, `进程上限 ${hc.PidsLimit}`)
      assert((hc.Ulimits ?? []).some((item) => item.Name === 'nproc' && item.Soft === DEFAULT_LIMITS.tasks && item.Hard === DEFAULT_LIMITS.tasks), `沙箱内进程上限 ${JSON.stringify(hc.Ulimits)}`)
      const host = await hostLimits(a)
      assert(host, '无法读取宿主 cgroup，未验证限额是否真正写入')
      assert(host.cpuMax === '100000 100000', `cpu.max=${host.cpuMax}`)
      assert(Number(host.memoryMax) === hc.Memory, `memory.max=${host.memoryMax}`)
      assert(host.memorySwapMax === '0', `memory.swap.max=${host.memorySwapMax}`)
      assert(host.pidsMax === String(DEFAULT_LIMITS.pids), `pids.max=${host.pidsMax}`)
      return `cpu.max ${host.cpuMax}，memory.max ${host.memoryMax}，memory.swap.max ${host.memorySwapMax}，pids.max ${host.pidsMax}，沙箱内 nproc ${DEFAULT_LIMITS.tasks}`
    })

    await check('真实 Pi 经 RPC get_state 回报就绪（不接在线模型）', async () => {
      const state = await a.rpc.getState()
      assert(state.sessionId && typeof state.sessionFile === 'string' && state.sessionFile.startsWith(`${SESSION_DIR}/`), '就绪回报缺少会话')
      return `会话 ${state.sessionId}，会话目录 ${SESSION_DIR}，就绪用时 ${readyMs} ms`
    })

    await check('沙箱内实测：非 root、gVisor 内核、登记的 Node 与 Pi', async () => {
      const r = await sh(
        a,
        'printf \'%s|%s|%s|%s\\n\' "$(id -u)" "$(uname -r)" "$(node --version)" "$(node /opt/pi/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js --version)"',
      )
      const [uid, kernel, nodeVersion, piVersion] = r.output.trim().split('|')
      assert(uid === lock.user.split(':')[0] && uid !== '0', `uid=${uid}`)
      assert(/gvisor/i.test(kernel ?? ''), `内核 ${kernel}`)
      assert(piVersion === lock.piVersion, `Pi 版本 ${piVersion}`)
      assert(nodeVersion.replace(/^v/, '') === lock.nodeVersion, `Node 版本 ${nodeVersion}`)
      return `uid ${uid}，内核 ${kernel}，Node ${nodeVersion}，Pi ${piVersion}`
    })

    await check('/work 可写，受信侧经 Docker 读到同一内容', async () => {
      await sh(a, `printf '%s\\n' '${MARKER_A}' > /work/ws-marker.txt`)
      const content = await a.readWorkFile('ws-marker.txt')
      assert(content?.toString('utf8') === `${MARKER_A}\n`, '受信侧读回的内容与写入不一致')
      return 'Pi 写入标记，Worker 经 Docker 归档接口读回一致'
    })

    // 不接模型时 Pi 只建会话目录、不落盘会话文件；文件本体要等首轮模型对话才写入，留到接入网关的一步验证。
    await check('Pi 在 /work 内建立会话目录', async () => {
      assert(String(a.session?.sessionFile).startsWith(`${SESSION_DIR}/`), `会话路径不在 /work 下：${String(a.session?.sessionFile)}`)
      const entries = await a.listWork()
      assert(entries.includes('work/.pi-sessions'), `受信侧读到的 /work 中没有会话目录：${entries.join('，')}`)
      return `${SESSION_DIR} 由 Pi 建立在可写工作区内（会话文件待首轮模型对话后写入，本步未验）`
    })

    await check('只读输入：可读、写入被拒', async () => {
      const read = await sh(a, 'cat /input/task/brief.txt')
      assert(read.output === `${INPUT_TEXT}\n`, `读到的内容不符：${read.output}`)
      const denied = await sh(a, 'touch /input/task/new.txt 2>&1; echo " exit=$?"')
      assert(/ exit=[1-9]/.test(denied.output), `新建文件未被拒绝：${denied.output}`)
      const append = await sh(a, 'echo x >> /input/task/brief.txt 2>&1; echo " exit=$?"')
      assert(/ exit=[1-9]/.test(append.output), `追加写入未被拒绝：${append.output}`)
      return `内容读取一致；${denied.output.trim().replace(/\n/g, ' ')}`
    })

    await check('根文件系统只读', async () => {
      const r = await sh(a, 'touch /probe 2>&1; echo " exit=$?"; touch /opt/pi/probe 2>&1; echo " exit=$?"')
      assert((r.output.match(/ exit=[1-9]/g) ?? []).length === 2, `根目录写入未被拒绝：${r.output}`)
      return r.output.trim().split('\n').filter((line) => line.includes('exit=')).join('，')
    })

    await check('沙箱内实测：无 capability、禁止提权', async () => {
      const r = await sh(a, "grep -E '^(CapEff|CapBnd|NoNewPrivs):' /proc/self/status")
      assert(/CapEff:\s+0+\s/.test(r.output) && /CapBnd:\s+0+\s/.test(r.output), `仍有 capability：${r.output}`)
      assert(/NoNewPrivs:\s+1\s/.test(r.output), `未禁止提权：${r.output}`)
      return r.output.trim().replace(/\n\s*/g, '，')
    })

    await check('挂载范围外的宿主标记与宿主路径不可见', async () => {
      const paths = ['/input/../host-marker.txt', '/host-marker.txt', `/tmp/${basename(root)}`, '/home/wlc', '/home/wlc/project', '/var/run/docker.sock', '/var/lib/docker']
      const r = await sh(a, `for p in ${paths.join(' ')}; do if [ -e "$p" ]; then echo "visible $p"; else echo "absent $p"; fi; done`)
      const visible = r.output.split('\n').filter((line) => line.startsWith('visible '))
      assert(!visible.length, `沙箱内可见：${visible.join('；')}`)
      return `${paths.length} 个宿主路径均不存在（含挂载目录旁的宿主标记与 Docker socket）`
    })

    await check('容器离线：只有回环接口、无路由、宿主服务不可达', async () => {
      const r = await sh(
        a,
        `echo "ifaces=$(awk -F: 'NR>2{gsub(/ /,"",$1); printf "%s,", $1}' /proc/net/dev)"; echo "routes=$(wc -l < /proc/net/route)"; `
          + `timeout 5 bash -c 'exec 3<>/dev/tcp/127.0.0.1/8767' 2>&1 | head -1; echo " local_exit=\${PIPESTATUS[0]}"; `
          + `timeout 5 bash -c 'exec 3<>/dev/tcp/1.1.1.1/53' 2>&1 | head -1; echo " public_exit=\${PIPESTATUS[0]}"`,
      )
      assert(r.output.includes('ifaces=lo,'), `网络接口：${r.output}`)
      assert(r.output.includes('routes=1'), `路由表：${r.output}`)
      assert(/local_exit=[1-9]/.test(r.output), `连到了宿主回环地址上的服务：${r.output}`)
      assert(/public_exit=[1-9]/.test(r.output), `连到了公网地址：${r.output}`)
      return r.output.trim().replace(/\n\s*/g, '，')
    })

    await check('/tmp：限额生效、不可执行', async () => {
      const r = await sh(
        a,
        'head -c 999999999 /dev/zero > /tmp/fill.bin 2>/dev/null; echo " fill_exit=$?"; echo " $(df -P -B1 /tmp | awk \'NR==2{print "total="$2" used="$3" avail="$4}\')"; '
          + 'rm -f /tmp/fill.bin; printf "#!/bin/sh\\n" > /tmp/s.sh; chmod +x /tmp/s.sh; /tmp/s.sh 2>&1 | head -1; echo " exec_exit=\${PIPESTATUS[0]}"',
      )
      assert(/ fill_exit=[1-9]/.test(r.output), `超出 /tmp 限额的写入未被拒绝：${r.output}`)
      assert(fullDisk(r.output, DEFAULT_LIMITS.tmpMiB * 1048576), `限额与预期不符：${r.output}`)
      assert(/ exec_exit=[1-9]/.test(r.output), `/tmp 中的脚本被执行：${r.output}`)
      return `df 总量 ${DEFAULT_LIMITS.tmpMiB} MiB，写满后可用 0 字节；执行被拒`
    })

    await check('/work 字节配额：写到上限即被拒', async () => {
      const r = await sh(
        a,
        'head -c 999999999 /dev/zero > /work/fill.bin 2>/dev/null; echo " exit=$?"; echo " $(df -P -B1 /work | awk \'NR==2{print "total="$2" used="$3" avail="$4}\')"; rm -f /work/fill.bin',
      )
      assert(/ exit=[1-9]/.test(r.output), `超出工作区上限的写入未被拒绝：${r.output}`)
      assert(fullDisk(r.output, DEFAULT_LIMITS.workMiB * 1048576), `限额与预期不符：${r.output}`)
      return `df 总量 ${DEFAULT_LIMITS.workMiB} MiB，写满后可用 0 字节`
    })

    await check('/work 文件数配额：inode 用尽即被拒', async () => {
      const r = await sh(
        a,
        "total=$(df -i /work | awk 'NR==2{print $2}'); before=$(df -i /work | awk 'NR==2{print $3}'); mkdir /work/many; "
          + 'i=0; while :; do echo x > /work/many/f$i 2>/dev/null || break; i=$((i+1)); done; '
          + "echo \" total=$total before=$before created=$i after=$(df -i /work | awk 'NR==2{print $3}')\"; rm -rf /work/many",
      )
      const fields = Object.fromEntries([...r.output.matchAll(/ (\w+)=(\d+)/g)].map((match) => [match[1], Number(match[2])]))
      assert(fields.total === DEFAULT_LIMITS.workFiles, `inode 总数 ${fields.total}，应为 ${DEFAULT_LIMITS.workFiles}`)
      assert(fields.after === fields.total, `inode 未在上限处停止：${r.output}`)
      assert(fields.created === fields.total - fields.before - 1, `可建文件数与上限不符：${r.output}`)
      return `inode 总数 ${fields.total}，原有 ${fields.before}，新建 1 个目录后最多再建 ${fields.created} 个文件`
    })

    await check('CPU 配额：多进程争用时不超出限额', async () => {
      const before = await hostLimits(a)
      assert(before, '无法读取宿主 cgroup')
      const began = Date.now()
      await sh(a, 'for i in 1 2 3 4; do ( while :; do :; done ) & done; sleep 1.5; for j in $(jobs -p); do kill "$j"; done; wait 2>/dev/null; echo burned', 60_000)
      const wallMs = Date.now() - began
      const after = await hostLimits(a)
      assert(after, '无法读取宿主 cgroup')
      const cpuMs = (after.cpuUsageUsec - before.cpuUsageUsec) / 1000
      const allowedMs = wallMs * DEFAULT_LIMITS.cpus
      assert(cpuMs <= allowedMs * 1.5 && cpuMs >= allowedMs * 0.5, `4 个忙循环在 ${wallMs} ms 内得到 CPU ${cpuMs.toFixed(0)} ms，限额 ${allowedMs.toFixed(0)} ms`)
      return `4 个忙循环 ${wallMs} ms 仅得 CPU ${cpuMs.toFixed(0)} ms，被限流 ${after.cpuThrottledPeriods - before.cpuThrottledPeriods} 个周期`
    })

    await check('进程上限：沙箱内先被拒且 Pi 存活，宿主 cgroup 上限未被触及', async () => {
      const report = await isolated('fork', {}, async (handle) => {
        const limit = (await sh(handle, 'ulimit -u')).output.trim()
        let peak = 0
        const sampler = setInterval(() => {
          void hostLimits(handle).then((host) => {
            if (host) peak = Math.max(peak, host.pidsCurrent)
          }, () => undefined)
        }, 10)
        let probe = ''
        try {
          probe = (await sh(handle, FORK_PROBE, 60_000)).output.trim()
        } finally {
          clearInterval(sampler)
        }
        const state = await handle.rpc.getState()
        return { limit, probe, peak, alive: state.sessionId === handle.session?.sessionId, ended: await close(handle) }
      })
      assert(report.limit === String(DEFAULT_LIMITS.tasks), `沙箱内进程上限为 ${report.limit}，应为 ${DEFAULT_LIMITS.tasks}`)
      const created = Number(/created=(\d+)/.exec(report.probe)?.[1])
      assert(created > 0 && created < DEFAULT_LIMITS.tasks, `派生结果 ${report.probe}`)
      assert(/stop=EAGAIN/.test(report.probe), `派生未按预期被拒：${report.probe}`)
      assert(report.alive, '进程数触顶后 Pi 不再应答')
      assert(report.peak < DEFAULT_LIMITS.pids, `宿主 cgroup 进程数峰值 ${report.peak}，触及或超过上限 ${DEFAULT_LIMITS.pids}`)
      assert(report.ended.outcome === 'exited' && fullyReclaimed(report.ended), `结束结果：${JSON.stringify(report.ended)}`)
      await cleanRun(`${prefix}-fork`, '进程上限')
      return `沙箱内上限 ${report.limit}（成功派生 ${created} 个进程后被拒，Pi 存活）；宿主 cgroup 上限 ${DEFAULT_LIMITS.pids}，峰值 ${report.peak}`
    })

    const pairStarted = await check('启动沙箱 B：与 A 并发运行，挂同一份只读输入', async () => {
      const b = await open('b')
      assert(b.containerId !== a.containerId && b.workVolume !== a.workVolume && b.session?.sessionId !== a.session?.sessionId, 'B 复用了 A 的容器、工作卷或会话')
      return `会话 ${b.session?.sessionId}，与 A 各自独占容器与工作卷`
    })
    if (pairStarted) {
      const b = [...handles].find((item) => item.runId === `${prefix}-b`)!
      await check('另一任务的标记不可见', async () => {
        await sh(b, `printf '%s\\n' '${MARKER_B}' > /work/b-marker.txt`)
        const inA = await sh(a, 'if [ -e /work/b-marker.txt ]; then echo visible; else echo absent; fi')
        const inB = await sh(b, 'if [ -e /work/ws-marker.txt ]; then echo visible; else echo absent; fi')
        assert(inA.output.trim() === 'absent' && inB.output.trim() === 'absent', `A 看到 B 的标记：${inA.output.trim()}；B 看到 A 的标记：${inB.output.trim()}`)
        const filesA = (await a.listWork()).filter((name) => name.endsWith('.txt')).sort()
        const filesB = (await b.listWork()).filter((name) => name.endsWith('.txt')).sort()
        assert(!filesA.some((name) => name.includes('b-marker')) && !filesB.some((name) => name.includes('ws-marker')), `受信侧读到的 /work 清单交叉：A=${filesA.join(',')} B=${filesB.join(',')}`)
        return 'A 看不到 B 的标记，B 看不到 A 的标记，受信侧两份 /work 清单互不交叉'
      })
      await check('回收 B 后 A 不受影响，重复回收为空', async () => {
        const result = await close(b)
        assert(result.outcome === 'exited' && fullyReclaimed(result), `B 的结束结果：${JSON.stringify(result)}`)
        await cleanRun(b.runId, 'B 回收')
        const state = await a.rpc.getState()
        assert(state.sessionId === a.session?.sessionId, 'B 回收后 A 的会话发生变化')
        const again = await worker.reclaim(b.runId)
        assert(!again.containers.length && !again.volumes.length, '重复回收不应再删除资源')
        return 'B 有序退出并回收；A 的会话不变；对 B 再次回收没有删除任何资源'
      })
    }

    await check('关闭 A：Pi 有序退出并回收', async () => {
      const result = await close(a)
      assert(result.outcome === 'exited' && result.exitCode === 0 && fullyReclaimed(result), `A 的结束结果：${JSON.stringify(result)}`)
      await cleanRun(a.runId, 'A 回收')
      return `退出码 ${result.exitCode}，${result.durationMs} ms，容器与工作卷已回收`
    })

    await check('同一 runId 并发启动：只成功一个，被拒的一方不动胜者的资源', async () => {
      const runId = `${prefix}-race`
      runIds.add(runId)
      const rival = new SandboxWorker({ image: lock, inputsRoot })
      const attempt = async () => {
        const settled = await Promise.allSettled([worker.start({ runId, inputs }), rival.start({ runId, inputs })])
        const winners = settled.filter((item) => item.status === 'fulfilled').map((item) => (item as PromiseFulfilledResult<SandboxHandle>).value)
        const losers = settled.filter((item) => item.status === 'rejected').map((item) => (item as PromiseRejectedResult).reason as SandboxError)
        return { winners, losers }
      }
      const first = await attempt()
      for (const handle of first.winners.slice(1)) await worker.reclaim(handle.runId)
      assert(first.winners.length === 1 && first.losers.length === 1, `胜出 ${first.winners.length} 个，被拒 ${first.losers.length} 个`)
      const winner = track(first.winners[0])
      const loser = first.losers[0]
      assert(loser.code === 'RUN_EXISTS', `被拒原因 ${loser.code}：${loser.message}`)
      const left = await worker.list(runId)
      assert(left.containers.length === 1 && left.volumes.length === 1, `被拒之后资源数变了：${[...left.containers, ...left.volumes].join('，')}`)
      const state = await winner.rpc.getState()
      assert(state.sessionId === winner.session?.sessionId, '胜出的沙箱不再应答')
      /* 胜者运行期间，任何一方再次启动同一 runId 都被拒 */
      const second = await attempt()
      for (const handle of second.winners) await worker.reclaim(handle.runId)
      assert(second.winners.length === 0 && second.losers.length === 2, `运行期间再次启动：胜出 ${second.winners.length} 个`)
      assert(second.losers.every((item) => item.code === 'RUN_EXISTS'), `再次启动的被拒原因：${second.losers.map((item) => item.code).join('，')}`)
      const result = await close(winner)
      assert(result.outcome === 'exited' && fullyReclaimed(result), `胜者的结束结果：${JSON.stringify(result)}`)
      await cleanRun(runId, '并发启动')
      return '两个 Worker 同时提交只成功一个，另一个得到 RUN_EXISTS 且未删任何资源；胜者照常应答并在结束后回收'
    })

    await check('Pi 异常退出：如实报错并回收', async () => {
      const result = await isolated('crash', {}, async (handle) => {
        await handle.rpc.bash('kill -KILL $PPID', { timeoutMs: 15_000, excludeFromContext: true }).catch(() => undefined)
        return handle.done
      })
      assert(result.outcome === 'error' && result.exitCode !== 0 && fullyReclaimed(result), `结束结果：${JSON.stringify(result)}`)
      await cleanRun(`${prefix}-crash`, '异常退出')
      return `outcome=${result.outcome}，退出码 ${result.exitCode}，容器与工作卷已回收`
    })

    await check('执行时限：到点后容器自行退出并回收', async () => {
      const result = await isolated('deadline', { maxDurationSec: 3 }, async (handle) => handle.done)
      assert(result.outcome === 'timeout' && result.exitCode === 124, `结束结果：${JSON.stringify(result)}`)
      assert(result.durationMs >= 2500 && result.durationMs <= 12_000, `用时 ${result.durationMs} ms`)
      assert(fullyReclaimed(result), `资源未回收：${JSON.stringify(result.reclaimed)}`)
      await cleanRun(`${prefix}-deadline`, '到点')
      return `3 秒时限，${result.durationMs} ms 结束，退出码 124，容器与工作卷已回收`
    })

    await check('强制终止：整个容器停止并回收', async () => {
      const began = Date.now()
      const result = await isolated('terminate', {}, async (handle) => {
        handle.rpc.bash('sleep 60', { timeoutMs: 70_000, excludeFromContext: true }).catch(() => undefined)
        await new Promise((resolve) => setTimeout(resolve, 500))
        return handle.terminate('acceptance-terminate')
      })
      assert(result.outcome === 'terminated' && fullyReclaimed(result), `结束结果：${JSON.stringify(result)}`)
      assert(Date.now() - began < 15_000, `终止用时 ${Date.now() - began} ms`)
      await cleanRun(`${prefix}-terminate`, '强制终止')
      return `运行中的命令随容器一起停止，${result.durationMs} ms，退出码 ${result.exitCode}`
    })

    await check('内存上限：超限分配被终止并回收', async () => {
      const result = await isolated('memory', { memoryMiB: 128 }, async (handle) => {
        await handle.rpc.bash("node -e 'const a=[]; for(;;) a.push(Buffer.alloc(1<<20,1))'", { timeoutMs: 60_000, excludeFromContext: true }).catch(() => undefined)
        return handle.done
      })
      assert(result.outcome === 'oom' && result.oomKilled && fullyReclaimed(result), `结束结果：${JSON.stringify(result)}`)
      await cleanRun(`${prefix}-memory`, '内存超限')
      return `128 MiB 上限下持续分配，outcome=oom，退出码 ${result.exitCode}，容器与工作卷已回收`
    })

    return finish()

    async function finish(): Promise<number> {
      for (const handle of [...handles]) await close(handle).catch(() => handle.done)
      const leftovers = await cleanup()
      await check('本次创建的容器与工作卷全部回收', async () => {
        assert(!leftovers.length, leftovers.join('；'))
        for (const runId of runIds) await cleanRun(runId, '收尾')
        const after = await managed()
        assert(JSON.stringify(after) === JSON.stringify(baseline), `带广场沙箱标签的资源与开始前不一致：${after.join('，') || baseline.join('，')}`)
        return `${runIds.size} 个运行，容器与工作卷均已回收；带沙箱标签的资源与开始前一致`
      })
      await check('宿主标记完整', async () => {
        assert((await readFile(hostMarkerPath, 'utf8')) === hostMarkerText, '宿主标记被改动')
        assert((await readFile(join(inputDir, 'brief.txt'), 'utf8')) === inputText, '只读输入的原件被改动')
        return '宿主标记与只读输入的原件内容未变'
      })
      await check('现网服务未受影响', async () => {
        const response = await fetch('http://127.0.0.1:8767/api/health', { signal: AbortSignal.timeout(8000) })
        assert(response.ok, `HTTP ${response.status}`)
        let services = ''
        try {
          services = (await runCommand('systemctl', ['--user', 'is-active', 'skill-plaza-backend.service', 'skill-plaza-frontend.service'])).stdout.trim().split('\n').join('，')
        } catch {
          services = '服务状态不可查询'
        }
        return `/api/health HTTP ${response.status}；前后端服务 ${services}`
      })
      return checks.some((item) => item.status === 'fail') ? 1 : 0
    }
  }
}

if (process.argv[1] && import.meta.url === `file://${process.argv[1]}`) {
  runAcceptance().then(
    (code) => {
      process.exitCode = code
    },
    (error) => {
      console.error(errorMessage(error))
      process.exitCode = 1
    },
  )
}
