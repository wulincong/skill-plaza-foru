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

状态：配置已修改，已安装并启动当前用户 zjf 的独立服务；未启用开机自启。当前副本 `/home/wmq/skill-plaza-foru2` 使用前端4189、后端8768；wlc原服务4188/8767不变。`web/vite.config.ts` 的 server/preview 指定4189并启用strictPort，两处代理指向8768。`web/.env` 的 PORT、公开报告入口和来源白名单改成本机新入口；其他配置保留。

新增 `deploy/systemd/skill-plaza-foru2-frontend.service` 与 `skill-plaza-foru2-backend.service`，工作目录均为当前副本，使用独立名称；原模板不修改。后端unit显式PORT=8768，避免进程环境覆盖回旧端口。只保留本机访问，不新增公网代理。

取舍：采用少量配置改动，便于撤回，不重写业务代码或通用配置系统。后续安装到当前用户的systemd目录，确认Pi运行权限后再启动；实际双端口health、代理和模型运行尚待启动验收。

撤回：Vite端口恢复4188、代理恢复8767，删除新增strictPort或按原偏好保留；停止并移除foru2两个独立unit，不操作wlc原服务。修改本地.env前的值如下（仅记录非敏感访问配置）：
- `PORT`：原先未设置，恢复时删除此项。
- `DELIVERY_PUBLIC_BASE_URL`：`http://biubiubiu.vip:14188`。
- `PLAZA_ALLOWED_ORIGINS`：`http://115.231.218.150:14188,http://biubiubiu.vip:14188`。

验证：两个新增unit通过 `systemd-analyze --user verify`；Vue类型检查、Vite生产构建与 `git diff --check` 通过。没有安装unit或启动/重启任何服务。

启动验收补注（2026-11-18）：两个foru2 unit已安装到 `/home/zjf/.config/systemd/user/`，经 `systemctl --user daemon-reload` 和 start 启动。4189/8768均仅监听127.0.0.1；首页HTTP200、后端health与前端代理health通过，技能列表包含student-learning。wlc原服务未操作。当前.env仍使用plaza-sandbox，但zjf执行 `sudo -n -u plaza-sandbox /opt/plaza-runtime/bin/pi-sandbox --version` 返回需要密码，因此本次只确认网页/API服务可访问，不能宣称模型任务可运行。未降低沙箱权限，后续需配置该用户的受限sudo权限或由用户选择运行方式。

局域网访问修正（2026-11-18）：原先4189仅绑定127.0.0.1，实测访问192.168.10.7返回连接失败，端口放行不能解决监听范围。已将当前副本Vite server/preview及foru2前端unit的host改为0.0.0.0；后端8768继续只绑定loopback。web/.env公开入口改为http://192.168.10.7:4189，来源允许该LAN入口及127.0.0.1/localhost:4189。确认后端无Pi子进程后，仅重启foru2两个服务；首页通过LAN地址HTTP200，携带LAN Origin的代理health及直连后端health均通过。新unit静态校验与diff检查通过，wlc服务未操作。模型任务的sudo权限缺口仍保留。

Pi权限补齐（2026-11-18）：经用户授权，管理员新增 `/etc/sudoers.d/plaza-pi-zjf`，仅允许zjf免密以plaza-sandbox执行 `/opt/plaza-runtime/bin/pi-sandbox`，全局visudo校验通过，未改wlc规则。仅当前副本workspace递归增加zjf/plaza-sandbox的rwX ACL，目录增加两者默认rwx ACL，保证新会话继承；未开放仓库写权限或知识库Key文件。包装脚本版本检查返回0.87.1。通过LAN同源 `/api/chat` 真实运行student-learning/优才模型及weknora_retrieve，4.8秒成功返回“智能模型训练（1份文档）”，运行20261118-164355-72tw，确认低权Pi启动和知识库查询链路可用；原先sudo权限缺口已解决。不需要重启服务。完整八周低权报告仍待业务验收。管理员密码未写入脚本、配置或文档。
