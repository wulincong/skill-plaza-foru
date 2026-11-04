# 105 · 本机前后端的独立 systemd 用户服务

**状态**：已实现，本机两个正式端口已由 `wlc` 的用户级 systemd 接管。

## 动机

Vite 开发服务和 Node API 原先由不同终端启动。维护者需要稳定的重启入口、日志和开机自启，并希望前端热更新与服务维护不影响执行中的 Pi 任务。

## 约定与接入点

- 前端单元为 `skill-plaza-frontend.service`。从项目 `web/` 以稳定 Node 路径直接运行 Vite，绑定 `127.0.0.1:4188`，端口占用时失败，避免自动换端口导致公网代理失联。见 `deploy/systemd/skill-plaza-frontend.service:6`。
- 后端单元为 `skill-plaza-backend.service`。在相同工作目录运行 `server/index.ts`，继续读取 `web/.env`，沿用 078 的 sudo 白名单、沙箱账号和 104 的私有状态目录。见 `deploy/systemd/skill-plaza-backend.service:6`。
- 两个单元独立启用，各自设置 `Restart=on-failure` 和 3 秒重试，随用户管理器的默认 target 启动。本机 `Linger=yes`。安装步骤见 `README.md:41`。日常重启、查状态、查日志和健康检查以 `AGENTS.md:15` 为准。仅在确认没有执行中任务后重启后端。

## 成本与取舍

每个服务独立占用一个主进程，可在 Vite 更新失败时单独恢复前端，后端保持原会话。按用户要求不增加聚合 target 或前后端生命周期依赖。直接使用 `/opt/plaza-runtime/bin/node` 避免依赖 SSH 登录 shell 中的 nvm 初始化；更换主机时需核对运行时路径、仓库位置和服务账户。

## 验证与后续

`systemd-analyze --user verify` 通过。两个单元的 MainPID 分别与 4188、8767 的监听进程一致，单独执行两次重启（每个服务一次），另一个服务的 PID 均保持不变。前端代理的 `/api/health` 返回 Pi 就绪；公网 `/admin` 返回 200，未登录的管理接口返回 401。临时的同用户 systemd 进程可通过 sudo 白名单以沙箱账号运行 Pi 0.87.1。公网 Chrome 载入临时 CSS 模块后，样式随文件修改更新，页面内标记和前端 PID 均保持不变。已检查 enabled 和 linger，未为验证重启整台机器。后续迁移运行时或工作目录时，同步更新相应 unit 并重新安装。
