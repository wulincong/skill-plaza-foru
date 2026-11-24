# 离线 runsc 沙箱：固定版本的 Pi 与受信 Worker

真实 Pi 在 gVisor（`runsc`）容器里启动，由受信 Worker 核对 Docker 实际回报后才使用。本目录是沙箱二期的第一步，独立于现网的宿主机执行链，两者并行、互不依赖。

## 设计原则

- **只认登记的镜像。** Worker 用 `image.lock.json` 里的镜像 ID 启动，启动前把本机镜像与登记逐项比对；标签、不存在的摘要、与登记不符的镜像都在创建任何资源之前被拒绝。
- **只认 runsc。** Worker 不接受其他运行时，包括 Docker 已注册的 `runc`。运行时未注册、或注册了却无法启动容器，都是明确失败，不回退。
- **核对回报而不是核对请求。** 容器创建后、启动前，Worker 从 Docker 读回运行时、挂载清单与读写权限、用户、capability、网络、限额、环境与标签，逐项与约定比对，任何一处不符就不启动。
- **失败时不扩大损失。** 一次启动只释放自己创建的容器与工作卷。同一 `runId` 在任何 Worker 上同时最多成功一个，被拒的一方不碰胜者的资源。
- **输入范围由配置决定。** 只读输入必须位于 Worker 显式配置的受信输入根目录之内，没有配置就不挂载。

## 目录

| 路径 | 内容 |
| --- | --- |
| `image/Dockerfile`、`image/entrypoint.sh` | 镜像定义与容器内启动器 |
| `image/pi/package.json`、`image/pi/package-lock.json` | Pi 与依赖的锁定版本 |
| `image/lock.mjs`、`image/build.mjs` | 依赖锁与镜像构建脚本 |
| `image.lock.json` | 已登记的镜像 ID、Pi 版本、依赖 integrity、基础镜像摘要 |
| `src/sandbox.ts` | Worker：预检、启动、核对、结束与回收 |
| `src/spec.ts` | 资源命名、限额、输入校验、创建请求、Docker 侧核对规则 |
| `src/docker.ts` | Docker Engine API 客户端（本地 unix socket，固定 API 版本） |
| `src/pi-rpc.ts` | Pi 的 JSONL RPC 通道（只按 LF 分帧，带背压与帧上限） |
| `src/host.ts`、`src/tar.ts`、`src/registry.ts` | 宿主 cgroup 读回、归档读取、登记与源码核对 |
| `bin/acceptance.ts` | 一键实机验收 |
| `bin/sandbox.ts` | 运维命令 |
| `test/` | 不依赖 Docker 的单元测试与从真实运行抓取的夹具 |

## 使用

前置条件：本机 Docker 已注册 `runsc`，当前用户能访问 Docker socket，已登记的镜像在本机。

```bash
# 项目根目录执行
npm --prefix sandbox-v2 run acceptance    # 一条可重复的实机验收，约 13 秒
npm --prefix sandbox-v2 test              # 单元测试，不需要 Docker
```

验收输出每项的实测值，失败时退出码为 1。需要机器可读的结果时直接调用脚本，经 npm 运行会带上 npm 的横幅行：

```bash
node sandbox-v2/bin/acceptance.ts --json
```

运维命令：

```bash
node sandbox-v2/bin/sandbox.ts verify-image          # 登记与源码、本机镜像是否一致
node sandbox-v2/bin/sandbox.ts preflight             # Docker、运行时与镜像
node sandbox-v2/bin/sandbox.ts list                   # 带沙箱标签的容器与工作卷
node sandbox-v2/bin/sandbox.ts reclaim <runId>        # 回收指定运行的全部资源，可重复执行
```

受信代码里的用法：

```ts
import { SandboxWorker, loadImageLock } from './sandbox-v2/src/sandbox.ts'

const worker = new SandboxWorker({
  image: await loadImageLock(),
  inputsRoot: '/srv/plaza/inputs',          // 要挂输入时必须显式给出
})
const handle = await worker.start({
  runId: 't03-20261124-0001',
  inputs: [{ hostPath: '/srv/plaza/inputs/task-01', target: '/input/task' }],
})
await handle.rpc.request({ type: 'get_state' })             // 与 Pi 的 JSONL RPC
await handle.bash('ls -la /work')                           // 真实 Pi 进程在沙箱内执行，不经模型
const result = await handle.shutdown()                      // 有序退出并释放资源
```

`handle.done` 在容器退出后兑现结束结果，不会 reject。`handle.terminate(reason)` 停止整个容器。`handle.listWork()` 与 `handle.readWorkFile()` 只在容器运行期间有效。

## 启动过程

1. 校验 `runId`、限额与输入。输入按真实路径比对，符号链接与 `..` 逃逸被拒。
2. 预检：Docker 可达且 API 版本够，`runsc` 已注册，镜像的 ID、架构、标签、用户、入口、层与环境同登记相符。
3. 认领：创建本次运行的工作卷，读回它的尝试标签。卷已存在且不属于本次，说明这次运行已被占用或留有未回收资源，直接拒绝。
4. 创建容器，从 Docker 侧核对。先建立 attach 再启动，Pi 的第一行输出不会丢。启动后再补核网络接入与运行状态。
5. 就绪：Pi 应答 `get_state`，会话目录在 `/work` 下；沙箱内实际是非 root、gVisor 内核、登记的 Node 版本。
6. 结束：容器退出后读退出状态，释放本次的容器与工作卷。结果分为 `exited`、`error`、`timeout`、`oom`、`terminated`。

同一 `runId` 的并发启动只成功一个：工作卷名在一次运行内唯一，Docker 对同名卷的创建串行执行，后来者拿到的是已有对象。

## 隔离与限额

容器离线、非 root（`65532:65532`）、根文件系统只读、丢弃全部 capability、禁止提权、不挂设备、不发布端口、输出只走 attach 流不落日志。挂载只有本次的可写 `/work` 与只读输入，宿主家目录、仓库、`.env`、Docker socket 都不在容器内。

| 限额 | 默认 | 生效位置 |
| --- | --- | --- |
| CPU | 1 核 | 宿主 cgroup |
| 内存 | 512 MiB，不用交换 | 宿主 cgroup；`/work` 与 `/tmp` 的数据也计入 |
| 进程（沙箱内） | 96 | 沙箱内 `RLIMIT_NPROC`，触顶时新进程被拒，沙箱其余部分继续运行 |
| 进程（宿主兜底） | 256 | 宿主 cgroup，含 gVisor 自身线程；触顶时整个沙箱退出 |
| 运行时长 | 300 秒 | 容器内 `timeout` 自行退出；Worker 在到点后仍在运行时兜底停止 |
| `/tmp` | 16 MiB，不可执行 | 沙箱内 tmpfs |
| `/work` | 256 MiB，2048 个 inode | Docker 创建的 tmpfs 卷，由宿主内核在文件创建时强制 |

沙箱内每个线程约占 2 个宿主任务，所以沙箱内上限须满足 `2 × tasks + 64 ≤ pids`，保证先在沙箱内被拒。调用方调低 `pids` 而未给出 `tasks` 时，`tasks` 自动跟随下调。

`/work` 用 tmpfs 卷是因为 bind mount 没有容量上限，而给现有磁盘启用配额需要重挂；tmpfs 卷的字节与 inode 上限不依赖磁盘配额功能，验收里实测写到上限即被拒。

## 镜像

基础镜像以摘要固定，经 ECR Public 镜像站拉取，摘要与两个独立的 Docker Hub 镜像站按标签解析的结果一致。Pi 及全部依赖由 `package-lock.json` 锁定，每个条目都带 sha512 integrity，安装时禁用生命周期脚本。构建上下文只装入 Dockerfile、入口脚本与两个依赖文件，不读取仓库其他内容、宿主环境或凭据。

```bash
node sandbox-v2/image/lock.mjs                # 重新生成依赖锁
node sandbox-v2/image/build.mjs               # 构建并重新登记镜像 ID
node sandbox-v2/test/capture-fixtures.mjs     # 重建镜像后重新抓取测试夹具
```

本机构建不保证逐字节可复现，每次构建后镜像 ID 都会重新登记，Worker 只认登记的 ID。

## 已知限制

- **镜像不跨机器复现。** 异机部署需要分发已登记的镜像，或重建后重新登记。
- **工作卷不持久。** 它在内存中，容器停止后被卸载，停止的容器读不到卷内文件。收集产物要在 Pi 退出而容器仍在时进行，续跑需要另外的导入通道。
- **会话文件未验证落盘。** Pi 在首轮模型对话后才写入会话文件；本步不接模型，只验证了会话目录建在 `/work` 内。
- **Worker 异常退出后的回收。** 本机实测强制结束 Worker 后，Pi 容器自行退出。用 `node sandbox-v2/bin/sandbox.ts reclaim <runId>` 可清除该任务遗留的已停止容器和工作卷。
- **故障测试范围。** 运行时已注册却无法启动容器、Pi 单帧输出超过上限这两项已有单元测试，实机故障注入待验证。
- **未纳入本步。** 模型网关、T03 业务接入、任务队列、暂停续跑、上线切流。

## 参考

- [gVisor Docker 快速入门](https://gvisor.dev/docs/user_guide/quick_start/docker/)、[gVisor 安全模型](https://gvisor.dev/docs/architecture_guide/security/)、[gVisor 与 systemd cgroup](https://gvisor.dev/docs/user_guide/systemd/)
- [Docker 绑定挂载](https://docs.docker.com/engine/storage/bind-mounts/)、[Docker none 网络](https://docs.docker.com/engine/network/drivers/none/)
- Pi 的 RPC 协议：npm 包 `@earendil-works/pi-coding-agent` 内的 `docs/rpc.md` 与 `docs/rpc-commands.md`
- 项目手记：[129 沙箱二期迁移计划](../.agents/skills/plaza-dev-notes/references/129-sandbox-v2-greenfield-migration.md)、[131 离线 runsc 沙箱](../.agents/skills/plaza-dev-notes/references/131-sandbox-v2-offline-pi-sandbox.md)
