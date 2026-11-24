# 131 · 离线 runsc 沙箱：固定版本 Pi 镜像与受信 Worker

**状态**　2026-11-24 已实现并在本机实测：单元测试 49 项、实机验收 37 项全部通过，严格类型检查无错误。这是 [129](129-sandbox-v2-greenfield-migration.md) 的第一步。现网仍走宿主机执行链，本记录的入口没有接入任何业务。未验证项见文末。

## 动机

129 第一步要求交付固定版本的 Pi 镜像、Worker 的启动与回收入口和一条可重复的验收命令，并把 Pi 及其工具整体放进容器。验收方审阅初稿后提出三处修正，均已落实并各有回归：启动入口只能用 `runsc`；没有配置受信输入根时不得挂载；同一 `runId` 的并发启动要原子认领，失败时不得误删别的执行。

## 约定细节

代码在 `sandbox-v2/`，入口、限额与用法见该目录的 `README.md`。

### 接入点

| 位置 | 作用 |
| --- | --- |
| `sandbox-v2/src/sandbox.ts:433` | `SandboxWorker`：`:442` 构造时只接受 `runsc`；`:454` 启动前预检；`:556` `start`；`:504` `release`；`:541` `reclaim` |
| `sandbox-v2/src/sandbox.ts:211` | `SandboxHandle`：`:287` 就绪判定；`:322` 退出收尾与分类；`:382` `shutdown`；`:394` `terminate`；`:412` `listWork` |
| `sandbox-v2/src/sandbox.ts:113`、`:158` | 镜像登记文件的校验、本机镜像与登记的逐项核对 |
| `sandbox-v2/src/spec.ts:45` | 默认限额；`:81` 合并与校验；`:274` 生成创建请求；`:369`、`:434` 从 Docker 回报逐项核对 |
| `sandbox-v2/src/spec.ts:194`、`:205` | 输入根目录与只读输入的校验 |
| `sandbox-v2/src/docker.ts:297` | Docker Engine API 客户端，固定 `v1.44`（`:8`）；`:205` attach 流的分帧与背压 |
| `sandbox-v2/src/pi-rpc.ts:49` | Pi 的 JSONL RPC 通道 |
| `sandbox-v2/bin/acceptance.ts:45` | 一键验收；`sandbox-v2/bin/sandbox.ts:25` 运维命令 |
| `sandbox-v2/image/Dockerfile:1`、`:30` | 基础镜像摘要与入口；`image/entrypoint.sh:12` 容器内计时器 |

### 镜像

- 基础镜像 `node:22-bookworm-slim@sha256:170fab70…`，Pi `0.87.1`，Node `22.23.5`。依赖由 `sandbox-v2/image/pi/package-lock.json` 锁定，144 个条目全部带 sha512 integrity，安装时 `--ignore-scripts`。
- 入口为 `tini 0.19.0` → `timeout --kill-after=10 $PI_MAX_SECONDS` → `pi --mode rpc --offline`，并关闭扩展、技能、模板、主题、上下文文件与项目本地配置的自动发现。运行用户 `65532:65532`。
- 会话目录 `/work/.pi-sessions`，agent 目录 `/tmp/pi-agent`（Pi 启动时会写 `auth.json` 与 `models-store.json`，所以必须可写）。
- `sandbox-v2/image.lock.json` 登记镜像 ID、层摘要、Pi 版本与 integrity、基础镜像摘要、用户与入口。Worker 只用登记的 ID 启动，并在预检时重新比对。

### 启动序列

校验规格与输入 → 预检（Docker 版本、`runsc` 已注册、镜像相符）→ 创建工作卷并读回尝试标签 → 创建容器并从 Docker 侧核对 → 先 attach 再启动 → 启动后补核网络与运行状态 → `get_state` 就绪，并实测沙箱内的用户、内核与 Node 版本。

### 认领与释放

- 每次启动生成 24 位十六进制的 `attempt`，写进工作卷与容器的标签 `plaza.sandbox.attempt`（`sandbox-v2/src/spec.ts:129`）。
- 工作卷名 `plaza-sb-<runId>-work` 在一次运行内唯一。卷已存在时 Docker 返回已有对象而不改标签，尝试标签不是本次的就返回 `RUN_EXISTS`，不触碰它。
- `release` 只删除本次拿到的容器 ID 与带本次尝试标签的工作卷。启动失败与正常收尾都走它。
- `reclaim(runId)` 是显式的运维入口，按运行标签删除全部资源；启动失败路径不调用。

### 限额

默认值：1 核、512 MiB 内存且不用交换、沙箱内进程 96、宿主进程 256、300 秒、`/tmp` 16 MiB、`/work` 256 MiB 与 2048 个 inode。校验要求 `2 × tasks + 64 ≤ pids`（`sandbox-v2/src/spec.ts:21`）；调用方只调低 `pids` 时 `tasks` 自动跟随。

`/work` 是 Docker 创建的 tmpfs 卷，`o=size=…,nr_inodes=…,uid=65532,gid=65532`。宿主内核在创建文件时强制上限，不依赖现有磁盘的配额功能。

### 错误码

`RUNTIME_UNAVAILABLE`、`RUNTIME_MISMATCH`、`RUN_EXISTS`、`IMAGE_LOCK`、`VERIFY_FAILED`、`INVALID_SPEC`、`PI_NOT_READY`、`START_FAILED`、`FRAME_TOO_LARGE`、`RPC_TIMEOUT`、`RPC_CLOSED`、`RPC_COMMAND`、`RECLAIM_FAILED`、`DOCKER_UNREACHABLE`、`DOCKER_API`。结束结果为 `exited`、`error`、`timeout`、`oom`、`terminated`。

## 实测到的事实

环境：Docker 28.3.3（API 1.51），`runsc` release-20261102.0，平台 systrap，cgroup v2 与 systemd，经典 overlay2 镜像存储，内核 6.14。

**配额与内存**

- tmpfs 卷的字节与 inode 上限都被强制：写到 256 MiB 后 `df` 显示可用为 0；inode 总数 2048，用尽后新建文件返回 `No space left on device`。
- tmpfs 卷的数据计入容器的内存 cgroup：写入 32 MiB 后 `memory.current` 增加约 35 MiB。
- 沙箱内的 `--tmpfs size=` 只限制字节，每个空文件按 4 KiB 计入，4 MiB 下最多建 1024 个空文件。
- 内存超限时 Docker 标记 `OOMKilled`，容器以 137 退出。

**进程上限的两个生效范围**

- 宿主 cgroup 的 `pids.max` 计入沙箱内全部线程与 gVisor 自身线程，空闲的 Pi 沙箱占 37–50。它从未被越过，但一旦触顶整个沙箱以退出码 2 结束，沙箱 stderr 为空；根因没有直接取到证据，推断为 gVisor 无法再创建线程。
- 沙箱内默认没有任何进程上限：`ulimit -u` 为 unlimited，镜像里没有 `/sys/fs/cgroup/pids.*`。设置 `RLIMIT_NPROC` 后 gVisor 会执行它，触顶时只是派生被拒（`EAGAIN`），Pi 继续应答。
- 本机 systrap 下沙箱内每个线程约占 2 个宿主任务。`tasks=128`、`pids=256` 时实测宿主峰值到了 255，所以把公式定为上文的 `2 × tasks + 64`，默认改为 96；复测成功派生 76 个进程后被拒，宿主峰值 193。

**生命周期**

- 以 `timeout` 作为 PID 1 时，孤儿进程会成为僵尸（实测 1 个）；换成 `tini` 后为 0。
- 容器内计时器到点后退出码为 124；`docker stop` 路径为 143。Pi 在 stdin 关闭后会放弃运行中的命令并立即退出。
- 连接断开后容器的 stdin 随之关闭，Pi 自行退出。

**Pi 行为**

- 不接模型时，`get_state`、`bash`、`set_session_name`、`set_auto_compaction`、`new_session` 等命令都不会让 Pi 写出会话文件，它只建立会话目录。会话文件要到首轮模型对话才落盘。
- RPC 的 `bash` 命令让真实 Pi 进程在沙箱内执行 shell，不需要模型。验收的标记与配额探针都走这条路。

**Docker 与 gVisor 的回报形式**

- 创建态容器的 `Networks` 为空，启动后才变成 `["none"]`。请求里多带 `NetworkDisabled: true` 会让它一直为空，所以只发 `NetworkMode: "none"`。
- 容器标签会并入镜像标签；`StopSignal` 与 `StopTimeout` 在 `Config` 下；`Cmd` 回报为 `null`。
- tmpfs 卷在容器停止后被卸载：对停止的容器做归档读取只得到空目录，运行中的容器可以读到内容。普通本地卷在容器停止后仍可读。
- gVisor 不提供 `/sys/class/net`、`/proc/sys/kernel/threads_max`，`uname -r` 为 `4.19.0-gvisor`。
- 守护进程的架构写作 `x86_64`，镜像元数据写作 `amd64`。

**构建**

- 本机直连 Docker Hub 超时，守护进程配置的镜像源均不可用。基础镜像经 ECR Public 取得，摘要与两个独立的 Docker Hub 镜像站按标签解析的结果一致。
- Pi 自带的 npm-shrinkwrap 对其 5 个 monorepo 自发包不写 integrity。`sandbox-v2/image/lock.mjs` 按 registry 元数据补全，并下载实测 sha512 交叉核对。
- Node 22 默认把编译缓存写进 `/tmp/node-compile-cache`，版本自检会留下 565 个文件、4.6 MB。镜像里设置 `NODE_DISABLE_COMPILE_CACHE=1`。
- 镜像 ID 不保证逐字节可复现：两次无缓存构建的文件内容与最终元数据一致，但部分层的摘要不同。

**工具**

- `node --check` 对 `.ts` 文件不可靠，它放过过一个真实的语法错误。`sandbox-v2/test/load.test.mjs` 改为实际加载每个模块；可执行脚本因此都带“只有被直接调用才执行”的入口保护。

## 成本与取舍

- **否决用 bind mount 做 `/work`**：没有容量上限。给现有 ext4 启用项目配额要改动或重挂现有盘，本步明确不做。tmpfs 卷的字节与 inode 上限都由内核强制，代价是数据放在内存里、容器停止后读不到。
- **否决沙箱内 `--tmpfs /work`**：没有独立的文件数上限。
- **否决 `--init`**：会把宿主的 init 二进制挂进容器，挂载清单里多出一项宿主路径。改为在镜像里固定版本的 `tini`。
- **否决 Worker 调用 docker CLI**：参数以字符串拼接，且 CLI 会拒绝部分 tmpfs 选项。改为直接调用固定版本的 Engine API。
- **否决复用 `web/server/lib/runner.ts` 的 `JsonlChannel`**：它绑定子进程，且改动它会影响现网服务。新写的通道带帧上限、背压，并按完整帧解码 UTF-8。
- **否决先查询再创建**：同一 `runId` 的并发启动会双双通过查询。改为用工作卷名与尝试标签认领。
- **否决启动失败时按 `runId` 回收**：会把同一 `runId` 下另一执行的资源删掉。
- **否决接受任何已注册的运行时**：初稿允许传入 `runc`。改为构造时只接受 `runsc`，创建请求里也写死。
- **否决省略输入根时的默认值**：空串会被解析成仓库当前目录。改为解析前拒绝。
- **否决逐字节可复现的镜像构建**：先后尝试 `SOURCE_DATE_EPOCH`、逐层归一化时间戳、预建挂载点、`COPY --link`，以及导出期重写时间戳（本机默认构建驱动不支持 OCI 与 docker 导出器），都没有得到稳定 ID。验收方确认这不作为交付条件，改为每次构建后登记 ID。
- **保留的两级进程上限**：多一个限额项，换来进程数在沙箱内被拒而不是整个沙箱退出。
- 镜像约 345 MB。沙箱内每个线程占两个宿主任务，同样的沙箱内进程数在本机需要两倍的宿主余量。

## 后续扩展路线

- **第二步的收集方式要改。** 原计划是先停止容器再从静止的任务目录收集，但 tmpfs 卷在容器停止后读不到。需要在 Pi 退出而容器仍在时导出，或者另设导出通道；续跑还需要导入通道。
- **会话文件落盘待验证。** 接入网关并完成首轮模型对话后，核对会话文件确实写在 `/work` 内。
- **可信扩展与技能的加载通道。** T03 需要 `--extension` 与 `--skill`，来源必须是只读的，不能落在可写的 `/work`。
- **进程余量按真实任务调整。** 先测 T03 的资源峰值再定默认值；宿主上限触顶时沙箱退出的根因仍未取证。
- **孤儿资源的对账。** Worker 崩溃后留下的容器与工作卷目前靠 `reclaim <runId>`，后续由任务服务按标签对账。
- **两条只有单元测试的路径**：运行时已注册但无法启动容器、Pi 单帧输出超过上限。需要不改守护进程配置的故障注入手段。
- **异机分发镜像。** 推送并按摘要分发，或重建后重新登记。

## 验证

在项目根目录执行：

```bash
npm --prefix sandbox-v2 test              # 49 项通过，约 2 秒，不需要 Docker
npm --prefix sandbox-v2 run acceptance    # 37 项通过，约 13 秒
```

实机验收覆盖：登记与源码一致；预检；只允许 `runsc`；运行时不可用时明确失败且不创建资源；只按登记的摘要启动；缺输入根时拒绝；Docker 侧的运行时、挂载、降权与离线、宿主 cgroup 读回；`get_state` 就绪（约 0.7 秒）；`/work` 可写且受信侧读回一致；会话目录在 `/work` 内；只读输入可读不可写；根只读；沙箱内无 capability；宿主标记与宿主路径不可见；只有回环接口且宿主服务不可达；`/tmp`、`/work` 的字节与文件数上限；CPU、内存与两级进程上限；双任务隔离；同一 `runId` 并发启动只成功一个；异常退出、到点超时、强制终止与内存超限都回收；本次资源全部回收；宿主标记完整；现网服务未受影响。

**未验证**：会话文件落盘；运行时已注册但损坏；单帧超限；Worker 进程被杀后的现场；真实模型与 T03 工具的负载；异机部署；长时间运行。

## 参考

- [gVisor Docker 快速入门](https://gvisor.dev/docs/user_guide/quick_start/docker/)、[gVisor 安全模型](https://gvisor.dev/docs/architecture_guide/security/)
- [Docker 绑定挂载](https://docs.docker.com/engine/storage/bind-mounts/)、[Docker none 网络](https://docs.docker.com/engine/network/drivers/none/)
- Pi npm 包内的 `docs/rpc.md`、`docs/rpc-commands.md`、`docs/containerization.md`、`docs/environment-variables.md`
- 项目：[129 沙箱二期迁移计划](129-sandbox-v2-greenfield-migration.md)、[119 多用户工作区与 gVisor 边界](119-multi-user-gvisor-workspaces.md)、[121 架构审查](121-sandbox-architecture-reliability-review.md)
