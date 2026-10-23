# 智能体搭子 · 智能体广场（产教领域）

展示产教领域公开 SKILL 的目录站点，并提供**在线真实运行**：浏览器提交任务 → Node 后端桥接本机 **pi · DeepSeek** → SSE 流式看到多步 agent 执行 → 运行留痕可回看。

- 前端：`web/`，Vue 3 + TypeScript + Vite
- 后端：`web/server/index.ts`，node:http 零第三方依赖；`PiRunner` 通过 `pi --mode rpc` 为每会话启动常驻子进程（JSONL over stdio）。
- 技能：`.agents/skills/` 下均为独立技能仓库的 git submodule（见「技能组织模式」），clone 需 `--recurse-submodules`；Pi 用 `--skill` + `/skill:` 命令加载技能。

## 架构

```
Vue SPA ── POST /api/chat {skill, messages} ──> Node 后端 (8767)
                              │  PiRunner（lib/piRunner.ts）
                              │    prompt → message_update(text_delta) → agent_settled
                              │  事件归一为 text/usage/terminal/error → SSE 推给浏览器
                              ├─ GET /api/health（Pi 模型状态）
                              └─ GET /api/runs（运行记录只读 API，含历史 engine 字段）
```

执行引擎固定为 Pi；`/experience`、`/use` 页面不再提供引擎切换，会话直接绑定 Pi。

开发期 Vite（4188）把 `/api` 代理到 8767；前端只访问同源 `/api/*`，不感知后端形态。

## 快速开始

### 前置条件

| 依赖 | 说明 |
| --- | --- |
| Node.js ≥ 22.18（建议 24+） | 后端用 `node` 直接运行 TypeScript（内置 type stripping），不用 tsx |
| pi CLI | `npm i -g @earendil-works/pi-coding-agent`；模型 key 走环境变量（如 `DEEPSEEK_API_KEY`），自检 `pi auth check --provider deepseek` |

必须安装 Pi CLI 才能启动后端；模型凭据另外配置。

### 启动步骤

```bash
# 1. 准备 Pi：
#    npm i -g @earendil-works/pi-coding-agent，并保证启动后端的 shell
#    环境里有 DEEPSEEK_API_KEY（或写入 web/.env）

# 2. 克隆仓库后安装依赖
cd web
npm install

# 3. 终端 1：启动 Node 后端（8767）
npm run server

# 4. 终端 2：启动前端开发服务（4188，/api 自动代理到 8767）
npm run dev
```

打开 http://127.0.0.1:4188 。后端未启动时页面不报错：运行记录页自动回落演示数据，在线运行页会提示启动方式。

### 使用文档翻译

打开 `#/use/doc-translate`，填写目标语言并上传带文本层的 PDF（单文件 ≤6MB），提交后在在线对话查看进度，完成后点击“查看译文 PDF”或“下载译文 PDF”；也可在在线对话用 `$doc-translate` 挂载技能并上传 PDF。需要系统已安装 poppler（`pdfinfo`、`pdftotext`、`pdftohtml`、`pdftoppm`）、XeLaTeX（含 graphicx/xeCJK）和中文字体。默认保留原图并翻译图注，位图提取后嵌入、矢量图裁切引用原 PDF，图内文字保持原样。版式保留纸张/分栏/标题等宏观结构；当前不支持扫描件 OCR 或加密文档。

新增技能或修改后端后须重启 `npm run server` 并刷新前端；`GET /api/skills` 中应包含 `doc-translate` 且 `installed:true`。`PLAZA_ENV` 只控制测试默认值，真实翻译依赖后端实际加载技能；运行失败会显示原因，不会自动替换为演示译文。

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
| `TRACES_DIR` | `web/server/traces/` | 运行留痕目录（已 gitignore） |

## 页面

| 路由 | 内容 |
| --- | --- |
| `/` | 首页 |
| `/skills`、`/skill/:slug` | SKILL 目录与详情 |
| `/experience` | 在线对话（多轮，流式输出） |
| `/use/:slug?` | 在线运行（结构化表单 → 真实 agent 执行 → 流式渲染 + token 用量） |
| `/runs`、`/runs/:runId` | 运行记录列表与详情（后端离线时回落演示数据） |
| `/guide` | 使用指南 |

## 后端 API

| 接口 | 说明 |
| --- | --- |
| `GET /api/health` | Pi 就绪状态与模型信息 |
| `POST /api/chat` | `{ skill, messages }` → SSE 流式返回（text_delta / usage / 终止） |
| `GET /api/runs` | 运行列表（来自 traces/index.jsonl） |
| `GET /api/runs/:runId` | 运行详情 |
| `GET /api/runs/:runId/file/:kind` | 下载留痕文件（md 可读版按需生成） |

## 技能组织模式（父子仓库）

每个技能一个**独立仓库（父）**：技能的全部内容与修改历史都在父仓库，广场不保存副本，只以 git submodule 将其挂载到 `.agents/skills/<slug>`（子引用，钉住 commit）。**今后新增技能默认沿用此模式；例外需在 README 和开发手记中注明**——当前例外：`tech-forecast`（新岗位·新技术预判）直接内置于主仓库 `.agents/skills/tech-forecast/`，不设独立父仓库；开发手记 `plaza-dev-notes` 同为主仓库内置。

新技能接入三步：

```bash
# 1. 技能完成并推送到其独立仓库（技能文件放在仓库根，README 声明与广场的父子关系）
# 2. 广场挂载
git submodule add https://github.com/Lntanohuang/<skill-repo>.git .agents/skills/<slug>
# 3. 在下表登记，提交 .gitmodules 与子模块指针
```

父仓库更新后广场同步：`git submodule update --remote .agents/skills/<slug>` 后提交。fresh clone 用 `git clone --recurse-submodules`，已克隆的补一句 `git submodule update --init`。

当前挂载：

| `.agents/skills/` | 父仓库 | 状态 |
| --- | --- | --- |
| `industry-education-report` | [industry-education-report-skill](https://github.com/Lntanohuang/industry-education-report-skill) | 已安装：Pi 通过 `--skill` 加载，首轮使用 `/skill:` 命令 |
| `foru-web-ui` | [foru-web-ui-skill](https://github.com/Lntanohuang/foru-web-ui-skill) | 设计参考资料技能（旧版静态演示的设计背景），未接入运行时 |
| `career-guidance` | [career-guidance-skill](https://github.com/Lntanohuang/career-guidance-skill) | 已安装：职业定位、岗位匹配、简历改进与求职行动计划 |

**classroom-assistant / ai-interview / training-data-qa**：尚未安装为真实技能，运行时回落到后端内置的方法论提示词；后续接入时按上表模式建仓挂载。

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

根目录的 `index.html` / `app.js` / `server.py` 是早期无 npm 的静态演示版（Youcai API 本地代理），已被 `web/` 版取代，仅作历史保留。设计背景见 `.agents/skills/foru-web-ui/`（独立仓库 [foru-web-ui-skill](https://github.com/Lntanohuang/foru-web-ui-skill) 的 submodule）；后端协议笔记见 `web/docs/pi-runner.md`。

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
