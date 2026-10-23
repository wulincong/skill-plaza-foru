# 078 · pi 沙箱第一层：低权系统用户运行（文件系统写边界）

**状态**：已实现（2026-10-20。系统配置脚本执行完成、自检 5 项通过；后端重启后探针会话验证 pi 以 plaza-sandbox 用户运行。空闲回收 kill 信号链与带 MySQL 查询的技能全链路待观察，见验证节）。

**动机**：075 完成的是**上下文隔离**（意图层），其残余风险已实证记录：pi 以开发用户（wlc）运行，read/bash 可达 wlc 能到的任何路径，可读 `web/.env`（MySQL 主凭据 + DeepSeek key）、可写整个仓库与家目录。用户选定「第一层：独立低权用户」方案，用 Linux 文件权限把 pi 的**写权限硬性限制在 workspace 内**。

## 约定细节

### 代码侧（已实现，默认不启用）

- `web/server/lib/piRunner.ts` 新增 `piSandboxPrefix()`：读 `PI_SANDBOX_USER`（web/.env），未设置返回 null、行为与从前完全一致；设置后 `createSession` 以 `sudo -n -u <user> <PI_CLI绝对路径> <原参数>` spawn pi。`this.cli` 此时必须为绝对路径（`PI_CLI` 指向包装脚本），否则 sudo 按自身 PATH 找不到命令。
- `web/server/index.ts` `workspaceDirFor` 在 mkdir 后显式 `chmodSync(dir, 0o2775)`：会话目录组可写（组由 workspace 根 setgid 继承），不依赖服务器进程 umask；`uploads` 等子目录同理继承。非 POSIX 文件系统时 try/catch 忽略。
- `web/.env.example` 补 `PI_SANDBOX_USER` 说明。

### 系统侧（`scripts/setup-pi-sandbox.sh` 一次性配置，幂等，`--refresh` 重拷运行时）

- 系统用户 `plaza-sandbox`（`--system -m -d /home/plaza-sandbox -s /usr/sbin/nologin`）+ 运行组 `plaza-run`（成员 wlc + plaza-sandbox）。**不加入 `users` 组**——hsq 共享后仓库目录 `2775 wlc:users` 组可写，入组即对全仓库可写，隔离失效。
- node+pi 运行时复制到 `/opt/plaza-runtime`（沙箱用户访问不到 `/home/wlc/.nvm`），root:root `a+rX`；包装脚本 `/opt/plaza-runtime/bin/pi-sandbox` 固定 `PATH=/opt/plaza-runtime/bin:…` 后 `exec pi`（pi 的 npm shim 依赖 `env node` 解析）。
- 权限布局：`setfacl -m u:plaza-sandbox:x /home/wlc`（仅穿行，不开 other；仓库各目录 other 本有 r-x）；`web/server/workspace` 整树 `chgrp plaza-run` + 目录 `2775`；`web/.env` 收紧 `640 wlc:users`（**修复此前 664 全机可读的凭据暴露**）+ `setfacl -m u:plaza-sandbox:r`（career-market-query.mjs:28 需读它取 MySQL 配置）。
- sudoers `/etc/sudoers.d/plaza-pi`：`wlc ALL=(plaza-sandbox) NOPASSWD: /opt/plaza-runtime/bin/pi-sandbox`（只白名单包装脚本，任意参数）+ `Defaults!<脚本> env_keep += "DEEPSEEK_API_KEY"`（sudo env_reset 后仍把 key 从服务器进程环境透传给 pi；`loadLocalEnv` 已把 .env 注入 process.env）。
- 脚本自检：沙箱用户跑 `pi --version`、workspace 可写、.env 可读、sudo 免密链路、**仓库根不可写**。

### 隔离边界（第一层达成后）

- **写**：仅 `web/server/workspace/**`（经 plaza-run 组）。仓库其余、家目录、`/opt` 均不可写。
- **读**：仓库（other r-x 全可读）、`web/.env`（ACL r）、`/opt/plaza-runtime`。家目录其余部分不可达（/home/wlc 仅 x 穿行到仓库路径）。
- 不变项：MySQL 主凭据对沙箱仍可读（与从前一致，见扩展路线）；网络无限制（web-search 需要）。

## 成本与取舍

- **否决 plaza-sandbox 入 `users` 组**：换取零 ACL 的简洁，代价是组写全仓库，隔离名存实亡。
- **否决 `chmod o+x /home/wlc`**：对全机开放穿行；ACL 只授权单一用户，最小暴露。
- **否决 workspace 挪出仓库**：075 已否决（uploads、报告捕获、.pi-sessions 连续性改动面大），本方案无需挪动。
- **否决 `sudo --preserve-env`/`-E`**：透传整个环境不可控；`env_keep` 精确到单变量。
- **运行时复制 vs 系统包管理器装 node**：复制钉死版本（与开发机 pi 行为一致），代价是升级 pi 需 `--refresh` 重拷。
- 残余风险（诚实记录）：`JsonlChannel.kill()` 发 SIGTERM 给 sudo，sudo→pi 的信号转发依赖 sudo 默认行为，**待真实会话验证**；pi 以新 HOME（/home/plaza-sandbox）运行，若 pi 依赖 `~/.pi` 下的凭据/配置文件将缺失（当前凭据走 env，理论不依赖，待探针验证）。

## 后续扩展路线

- **（下一优先）MySQL 只读账号**：给岗位库建仅 SELECT 账号，career-market-query 沙箱侧不再读主凭据——第一层后最大的剩余暴露面。
- 第二层：systemd-run 瞬态沙箱（ProtectSystem=strict / ReadWritePaths / PrivateTmp / IPAddressAllow），叠加在用户隔离之上。
- 第三层：容器（Podman rootless），面向公网多用户时。
- 升级 pi 后：`bash scripts/setup-pi-sandbox.sh --refresh`。

## 验证

- 代码静态（2026-10-20）：`import('./lib/piRunner.ts')` 通过且 `piSandboxPrefix()` 缺省返回 null；`node --experimental-strip-types --check index.ts` 通过；`bash -n` 配置脚本通过。
- 系统配置（2026-10-20 用户执行）：脚本 1–7 步完成，自检 5 项全 OK（pi 版本经包装脚本输出、workspace 可写、.env 可读、sudo 免密、仓库根不可写）。
- **端到端探针（2026-10-20，运行 `20261020-160642-h6ai` / 会话 `sess-20261020-160642-yqdq`）**：`/api/health` 正常（pi 0.87.1）；general 探针 SSE 完整走通（started→text→done，回答正常）；进程表实证 `wlc → sudo -n -u plaza-sandbox /opt/plaza-runtime/bin/pi-sandbox --mode rpc …`，pi 进程属主 `plaza-sandbox`；会话目录 `wlc:plaza-run 2775`（服务器建），`.pi-sessions/` 与会话 jsonl 属主 `plaza-sandbox`（pi 写、服务器可读）。075 参数链（--no-context-files、--append-system-prompt）原样保留。
- 部署过程中修复的脚本三坑（持久事实）：① root 下 `sudo -u wlc bash -lc` 找不到 pi——nvm 只在 wlc 交互 shell 加载，改为提权前捕获 `command -v pi` + nvm 目录兜底；② nvm `bin/pi` 是指向 `lib/node_modules/.../cli.js` 的相对符号链接，`readlink -f` 解引用后取上两级得到的是包目录而非 node 版本根，必须按路径模式推导且复制整个版本目录（相对链接才成立）；③ `set -euo pipefail` 下 `find | head -1` 会因 SIGPIPE+pipefail 静默杀掉脚本（同 016 的并行输出截断坑家族），取首条匹配用 `-print -quit`，检查项失败要显式报出。
- 待观察（不阻塞使用）：空闲回收时 `JsonlChannel.kill()` 的 SIGTERM 经 sudo 转发是否正常终结 pi 子进程（30 分钟 sweeper 自然触发时核对进程表）；带 MySQL 查询的技能（career-guidance/tech-forecast 实时查库）在沙箱用户下读 web/.env 与 mysql 客户端的完整链路。
