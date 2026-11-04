# 智能体搭子 · 智能体广场（产教领域）

面向产教任务的智能体平台。用户可在广场在线运行智能体，应用可通过 `POST /v1/chat/completions` 提交任务。两种接入方式与可复制的调用示例见[使用指南](http://biubiubiu.vip:14188/#/docs/guide)。

- 前端：`web/`，Vue 3 + TypeScript + Vite
- 后端：`web/server/index.ts`，node:http 零第三方依赖；`PiRunner` 通过 `pi --mode rpc` 为每会话启动常驻子进程（JSONL over stdio）。
- 技能：`.agents/skills/` 存放主仓库维护的技能和各自的使用文档（见「技能组织模式」）；Pi 用 `--skill` + `/skill:` 命令加载技能。

## 技能文档

在广场打开「文档中心」即可按任务查阅各技能的材料要求、示例和交付说明。仓库索引还收录绘图、数据查询和内部开发工具。[网站文档中心](http://biubiubiu.vip:14188/#/docs) · [仓库文档索引](docs/skill-index.md) · [给技能写文档](docs/writing-skill-docs.md)

## 架构

```
Vue SPA ── POST /api/chat {skill, messages} ──> Node 后端 (8767)
                              │  PiRunner（lib/piRunner.ts）
                              │    prompt → message_update(text_delta) → agent_settled
                              │  事件归一为 text/usage/terminal/error → SSE 推给浏览器
                              ├─ GET /api/health（Pi 模型状态）
                              └─ GET /api/admin/runs（管理员运行记录接口，含历史 engine 字段）
```

执行引擎固定为 Pi；`/experience`、`/use` 页面不再提供引擎切换，会话直接绑定 Pi。

开发期 Vite（4188）把 `/api` 代理到 8767；前端只访问同源 `/api/*`，不感知后端形态。

## 维护者开发环境

当前维护分支为 `wlc`。技能随主仓库一次检出。远程地址的变更历史见[开发手记 092](.agents/skills/plaza-dev-notes/references/092-main-repository-remote-migration.md)。

### 前置条件

| 依赖 | 说明 |
| --- | --- |
| Node.js ≥ 22.18（建议 24+） | 后端用 `node` 直接运行 TypeScript（内置 type stripping），不用 tsx |
| pi CLI | `npm i -g @earendil-works/pi-coding-agent`；模型 key 走环境变量（如 `DEEPSEEK_API_KEY`），自检 `pi auth check --provider deepseek` |

必须安装 Pi CLI 才能启动后端；模型凭据另外配置。

### 启动步骤

本机由 `wlc` 的两个独立 systemd 用户服务运行前后端。unit 使用 `/opt/plaza-runtime/bin/node`，来自本机的 Pi 沙箱配置（见 `scripts/setup-pi-sandbox.sh`），工作目录为 `~/project/skill-plaza-foru/web`。先安装依赖并配置好 `web/.env`，然后以 `wlc` 从仓库根目录执行：

```bash
(cd web && npm ci)
install -d ~/.config/systemd/user
install -m 644 deploy/systemd/skill-plaza-*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now skill-plaza-backend.service
systemctl --user enable --now skill-plaza-frontend.service
```

本机已为 `wlc` 启用 linger，用户服务可以在开机时启动并在退出 SSH 后继续运行。Vite 保留开发模式的热更新。日常重启和日志命令见 [AGENTS.md「本机前后端服务」](AGENTS.md#本机前后端服务)。

打开 http://127.0.0.1:4188 。运行记录位于独立的管理后台。

### 管理后台

首次部署时，在运行后端的系统账号下执行以下命令。它会创建管理员并在当前终端显示随机密码。已有账号时，命令会退出并保留原账号。

```bash
cd web
node server/scripts/adminAccount.ts admin
```

打开 [本机管理后台](http://127.0.0.1:4188/admin) 登录。可管理已注册技能的上架状态、默认模型、网页换模权限、思考档位、优才服务地址、DeepSeek 命名密钥及任务时限。在「账号设置」修改密码会注销所有设备。遗失密码时，在服务机上执行 `node server/scripts/adminAccount.ts admin --reset`。

后台配置保存于服务账号的 `~/.local/state/skill-plaza/admin/control.sqlite`，可用 `ADMIN_STATE_DIR` 指向 Web 根目录之外的专用目录。目录权限为 0700，数据库为 0600，备份应按密钥文件保管。首次使用部署环境中的模型配置。后台保存的配置优先，新一轮运行采用新设置，已开始的任务沿用原设置。

`/admin/runs` 读取现有 `traces/index.jsonl`，支持按任务、技能、结果筛选及归档、恢复、下载。目前只有后台管理员账号；前台手机号登录是本地演示。在线对话的共享历史向所有访客展示已有对话正文及交付链接，包括旧记录；所有测试人员都能继续同一段对话、回答决策题、归档、恢复和删除会话；原始运行文件仍由管理员查看。新部署请将 `/admin` 与 `/admin/*` 回落到 SPA 的 `index.html`，将 `/api/*` 和 `/p/*` 转发到 Node；远程管理入口应通过 HTTPS 访问。

### 使用文档翻译

打开 `#/use/doc-translate`，填写目标语言并上传带文本层的 PDF（单文件 ≤6MB），提交后在在线对话查看进度，完成后点击“查看译文 PDF”或“下载译文 PDF”；也可在在线对话用 `$doc-translate` 挂载技能并上传 PDF。需要系统已安装 poppler（`pdfinfo`、`pdftotext`、`pdftohtml`、`pdftoppm`）、XeLaTeX（含 graphicx/xeCJK）和中文字体。默认保留原图并翻译图注，位图提取后嵌入、矢量图裁切引用原 PDF，图内文字保持原样。版式保留纸张/分栏/标题等宏观结构；当前不支持扫描件 OCR 或加密文档。

新增技能或修改后端后须执行 `systemctl --user restart skill-plaza-backend.service` 并刷新前端；`GET /api/skills` 中应包含 `doc-translate` 且 `installed:true`。`PLAZA_ENV` 只控制测试默认值，真实翻译依赖后端实际加载技能；运行失败会显示原因，不会自动替换为演示译文。

### CLI 路径（自动检测）

后端优先使用 `PI_CLI` 配置，否则扫描 PATH 上的 `pi`。检测结果不落盘，每次启动重新检测。

确认 CLI 和配置是否就绪（不发起模型请求）：

```bash
cd web && npm run detect:cli
```

找不到 Pi CLI 时服务启动即报错；CLI 装在自定义位置时，在 `web/.env` 里设置 `PI_CLI`。

## 配置（web/.env）

后端支持 `web/.env` 本地配置文件：复制模板 `cp web/.env.example web/.env` 后按需取消注释。`.env` 已 gitignore 不进仓库；外部环境变量（shell 里 export 的）优先于 `.env` 文件。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PI_CLI` | 自动检测（PATH） | pi CLI 路径 |
| `PI_MODEL` | `openai-codex/gpt-6-astra` | pi 运行模型，格式 `provider/model` |
| `PI_THINKING` | `medium` | pi 思考档位（`off`..`max`） |
| `PI_IDLE_MS` | 30 分钟 | pi 会话进程空闲回收阈值（pi 每会话一进程） |
| `DEEPSEEK_API_KEY` | — | pi 引擎的模型 key（也可放 shell 环境；pi 按 `pi auth` 的读取顺序） |
| `PORT` | `8767` | 后端端口（Vite 代理目标需同步改） |
| `RUN_TIMEOUT_MS` | 已安装技能 20 分钟，其余 10 分钟 | 单次运行超时 |
| `TRACES_DIR` | `web/server/traces/` | 运行留痕目录（自定义时使用 0700 的服务账号专用目录） |

## 页面

| 路由 | 内容 |
| --- | --- |
| `/` | 首页 |
| `/skills`、`/skill/:slug` | SKILL 目录与详情 |
| `/experience` | 在线对话（多轮，流式输出） |
| `/use/:slug?` | 在线运行（结构化表单 → 真实 agent 执行 → 流式渲染 + token 用量） |
| `/admin`、`/admin/runs/:runId?` | 管理后台及真实运行记录，须管理员登录 |
| `/docs/guide` | 在线运行与 API 指南（旧地址 `/guide` 自动跳转） |
| `/docs`、`/docs/:slug/:topic?` | 技能文档中心、技能指南与专题页 |

## 后端 API

| 接口 | 说明 |
| --- | --- |
| `GET /api/health` | Pi 就绪状态与模型信息 |
| `GET /api/skills` | 可调用的专业智能体及其标识 |
| `POST /v1/chat/completions` | 对外调用，传入 `skill` 和 `messages`，返回 JSON 或 SSE |
| `POST /api/chat` | 广场前端专用。 `{ skill, messages }` → SSE 流式返回（text_delta / usage / 终止） |
| `GET /api/admin/runs` | 运行列表（来自 traces/index.jsonl） |
| `GET /api/admin/runs/:runId` | 运行详情 |
| `GET /api/admin/runs/:runId/file/:kind` | 下载留痕文件（md 可读版按需生成） |

## 技能组织模式

每个技能在主仓库内维护，路径为 `.agents/skills/<slug>/`。新增技能时，将 `SKILL.md`、脚本、参考资料与 `docs/` 一同提交。普通克隆当前维护分支即可取得全部技能文件。

```bash
git clone --branch wlc git@github.com:wulincong/skill-plaza-foru.git
```

`career-guidance`、`industry-education-report` 由 Pi 加载执行，`foru-web-ui` 用作开发时的设计参考。三个目录均已纳入主仓库。课堂助教、AI 面试和训练数据质检目前使用内置提示词，在各自的技能目录内维护用户文档。

## 运行留痕（traces）

每次 `/api/chat` 自动三层留痕到 `web/server/traces/`（gitignore）：

1. `<runId>.events.jsonl` — 实时协议流（请求/响应/事件 + runStart/runEnd）
2. `<runId>.json` — Pi 通过 RPC `get_messages` 导出的权威 trace
3. `index.jsonl` — 每运行一行（engine / outcome / duration / usage / toolCallCount），评测入口

配套脚本：`npm run traces:summary`（按 skill 统计成功率、时长分位数、token 与缓存命中率）、`npm run trace:md -- <runId>`（可读 MD）、`npm run traces:prune -- --keep N`。

## 沙箱与安全边界

- agent 的文件操作限定在 `web/server/workspace/<会话>/` 下，单次运行有超时。
- 当前定位是**内网自用**：绑本机 CLI 登录态，额度共享、并发受限。公网部署前需要容器隔离 + 工具白名单 + 真实用户体系。

## 构建与部署

```bash
cd web
npm run build   # vue-tsc 类型检查 + vite build，产物在 web/dist/
```

产物为纯静态站点，可直接静态托管；在线运行与运行记录功能仍需 8767 后端在 `/api` 同路径提供服务。

## 旧版演示（根目录）

根目录的 `index.html` / `app.js` / `server.py` 是早期无 npm 的静态演示版（Youcai API 本地代理），已被 `web/` 版取代，仅作历史保留。设计背景见 `.agents/skills/foru-web-ui/`；后端协议笔记见 `web/docs/pi-runner.md`。

---

更新：2026-09-29 — 移除 Zcode 执行接入、SQLite 补导与引擎切换；历史已落盘记录仍可读取。旧版 `AGENT_RUNNER`/`ZCODE_CLI`/`ZCODE_DB` 不再生效；API 只接受缺省或 `engine: "pi"`，其他引擎返回 400。
更新：2026-09-21 — 在线运行页新增表单/对话双模式（同一技能共用会话与附件）与简历附件上传：`POST /api/upload` 落会话沙箱 `server/workspace/<sessionId>/uploads/`，`/api/chat` 支持 attachments（md/txt 内联、其余指示引擎读工作目录，路径校验防穿越，运行记录留附件名）；career-guidance 注册进服务端 SKILL_PROMPTS 并按已安装技能真实加载。新增环境标识 `PLAZA_ENV`（web/.env，test|prod，前后端共用：后端直接读、前端经 vite envPrefix 暴露）：test 时工作台自动带入示例并附带测试简历（`test-data/测试简历-Java后端实习.md`，一键运行测试），prod 不预填。
更新：2026-09-20 — 技能组织模式改为父子仓库：每个技能独立仓库为父，广场以 submodule 挂载 `.agents/skills/`；industry-education-report 更新为 02 模板+05 快照离线版，foru-web-ui 迁入新仓库 foru-web-ui-skill。
更新：2026-09-18 — 双引擎落地：AgentRunner 抽象 + PiRunner（pi --mode rpc · DeepSeek，默认）+ ZcodeRunner 保留；前端可切换引擎。
更新：2026-09-17 — README 重写，对齐 zcode 无头后端 + 运行记录页的当前架构。

## 开发任务 Issue 流程

本仓库要求每次开发先把总结后的计划写入 GitHub issue，再开始提交代码：

```bash
scripts/start-task.sh "计划标题" /path/to/plan.md
```

该命令会创建并绑定活动 issue。提交和推送没有活动 issue 时会被 hook 阻止；提交信息会带上 `Task-Issue: #编号`，GitHub Actions 在 push 成功到达仓库后自动关闭绑定 issue。首次检出仓库或更换环境后执行 `scripts/install-task-hooks.sh` 启用本地 hook。创建 issue 依赖已认证的 GitHub CLI（`gh auth login -h github.com`）。
