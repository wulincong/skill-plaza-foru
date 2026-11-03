# Agent 服务接口文档

供外部项目调用本服务（智能体广场后端，Pi 引擎）的接口说明。以 `web/server/index.ts` 实际实现为准。

- **Base URL**：`http://127.0.0.1:8767`（服务只监听本机回环；端口可用环境变量 `PORT` 覆盖）
- **公网部署**：API 服务 `http://biubiubiu.vip:18767`，网页使用指南位于 [智能体使用指南](http://biubiubiu.vip:14188/#/guide)。
- **认证**：无鉴权
- **数据格式**：对话请求为 JSON。对外端点默认返回 JSON，`stream: true` 时返回 SSE。
- **跨域限制**：浏览器调用对话接口时 `Origin` 必须在部署的允许列表内，或为本机/内网地址（localhost、127.0.0.1、`*.local`、10.x、192.168.x、172.16-31.x）；服务端对服务端调用（不带 Origin 头）不受限制
- **服务启动**：`cd web && npm run server`（需本机已安装 pi CLI，模型 key 在启动 shell 环境或 `web/.env`）

## 产物交付：网页分享与文件下载

生成文件的任务在会话工作区根目录提供 `delivery.json`，路径相对于该工作区：

```json
{
  "web": [{"name":"人才需求报告","directory":"output/public/site","entry":"index.html"}],
  "files": [{"name":"报告交付包","path":"output/public/report.zip"}]
}
```

网页目录必须独立、完整，只包含允许分享的 HTML/CSS/JS/图片/数据。所有依赖使用相对路径，外部服务、动态后端和嵌入页面不属于托管范围。内部核查表、SQL证据、配置与追踪不放入交付目录。文件准备完毕后原子替换清单；仅追问说明时不重写，避免把旧产物当成本轮生成。

Linux 低权运行器与后端须共享工作区组：公开目录至少组读/穿行（如 2750），公开文件和清单至少组读（如 0640）。临时文件/目录默认 0600/0700，替换清单前须补齐权限；读取失败会明确报交付失败，不当成没有产物。

服务器校验并复制到持久目录后，`/api/chat` 的 done、OpenAI 流式扩展帧和非流式 JSON 增加下列可选字段：

```json
{
  "webLinks": [{"name":"人才需求报告","url":"http://biubiubiu.vip:14188/p/<deliveryId>/0/"}],
  "downloads": [{"name":"报告交付包","url":"http://biubiubiu.vip:14188/api/deliveries/<deliveryId>/files/0"}]
}
```

- `GET /p/:deliveryId/:index/`：重定向到真实 HTML 入口，直接在线访问，可分享；静态依赖只能从该网页目录读取。
- `GET /api/deliveries/:deliveryId/files/:index`：固定 `Content-Disposition: attachment`，PDF、图片、Excel、ZIP都作为下载。两类入口均支持 HEAD，不依赖聊天会话。
- 链接保存进原有运行记录，详情 conversation 会把链接恢复到对应回答；旧 `reportUrl` 继续兼容。已有固定 HTML/PDF 技能自动接入新交付。
- 广场界面将当前对话的交付链接汇总到右侧悬浮资源面板，网页/文件分类可折叠，紧凑文件行提供打开或下载、复制链接操作；支持窄屏展开，消息下方保留定位入口。只使用上述已发布字段，不把正文磁盘路径当作资源链接。
- `DELIVERIES_DIR` 缺省 `web/server/deliveries/`，部署需保留此目录；清理会话或重启服务不会删除已保存交付。首期不自动清理，不承诺永久存储。
- `DELIVERY_PUBLIC_BASE_URL` 配置公开 HTTP(S) origin；缺省采用已校验的请求 Origin，非浏览器采用 Host。当前部署为 `http://biubiubiu.vip:14188`，反向代理必须转发 `/p/` 和 `/api/` 到 Node，不能将 `/p/` 回落到 SPA。
- 持链接可访问；不可猜测 ID 不是账号鉴权。网页用 CSP sandbox 创建不共享主站权限的来源，允许脚本和目录内静态数据，禁止访问主站 API、存储、表单及子页面。无 PDF/图片/表格在线查看组件。

每批上限 20 个网页、100 个下载、2000 个文件、256 MiB；拒绝符号链接、路径越界、隐藏文件、internal/uploads 和空文件。无效清单不返回新链接。网页与下载均不会触发模型生成或数据库查询。

## 0. POST /v1/chat/completions（OpenAI 兼容，外部项目推荐入口）

OpenAI 风格的对话补全端点，供已有 OpenAI SDK/SSE 客户端的项目直接接入（将 baseURL 指向 `<服务地址>/v1`，并在请求体中加入 `skill`）。运行记录与 `/api/chat` 同套落盘（`/api/runs` 里 `protocol` 字段为 `openai`）。

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `skill` | string | 是 | 通用问答填 `general`。专业智能体填 `GET /api/skills` 返回的 `skills[].id`，如 `career-guidance`。未知值返回 400 和可用值。 |
| `messages` | array | 是 | OpenAI 消息数组，最后一条必须是内容非空的 `user` 消息；无 `sessionId` 时历史会被拍平注入本轮上下文（无状态客户端直接带全量历史即可） |
| `stream` | boolean | 否 | 默认 `false`；`true` 时输出 SSE 流 |
| `sessionId` | string | 否 | 多轮对话由客户端在首轮生成并保存 UUID，后续使用同一标识。对外端点不会回传新会话号。省略时每次开启新会话。 |
| `taskTitle` | string | 否 | 任务标题，≤120 字符；用于运行记录展示与报告下载文件名，不传则回退消息摘要 |
| `attachments` | array | 否 | 附件列表 `[{ "name": "简历.pdf", "path": "uploads/简历.pdf" }]`，`path` 为 `/api/upload` 返回的相对路径，最多 5 个 |

`model` 字段被忽略（服务端模型由 `PI_MODEL` 配置决定，该字段预留给将来按请求选模型的扩展）。其他 OpenAI 常见字段（`temperature` 等）同样忽略。

**流式输出**（`stream: true`，每帧 `data: {JSON}\n\n`，标准 `chat.completion.chunk` 外壳，按序）：

所有帧均为标准 OpenAI `chat.completion.chunk` 外壳（`id` / `object` / `created` / `model` / `choices`），正文与思考在 `choices[0].delta` 内；帧序示例：

```
data: {"id":"chatcmpl-<runId>","object":"chat.completion.chunk","created":1760400000,"model":"<服务模型>","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]} ← role 首帧
data: {…同壳…,"choices":[{"index":0,"delta":{"reasoning_content":"思考片段…"},"finish_reason":null}]} ← 思考增量（有思考阶段时；工具调用前的过程叙述也归入此通道）
data: {…同壳…,"choices":[],"status":{"phase":"tool","state":"active"|"completed"|"failed","tool":"bash","id":"call_00_…"}} ← 工具活动帧（扩展；亚秒级工具只发终态帧）
data: {…同壳…,"choices":[{"index":0,"delta":{"content":"正文片段…"},"finish_reason":null}]} ← 正文增量（仅最终答复，done 时刻一次性发出）
data: {…同壳…,"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]} ← 收尾帧
data: {…同壳…,"choices":[],"reportUrl":"/api/reports/<runId>","runId":"…","resultType":"success"} ← 报告帧（扩展，报告类技能成功时）
data: {…同壳…,"choices":[],"usage":{"prompt_tokens":…,"completion_tokens":…,"total_tokens":…,"cost_usd":…}} ← 用量帧
data: [DONE]
```

- 从 `choices[0].delta.content` 取最终答复。思考与过程叙述在 `delta.reasoning_content`。
- `choices: []` 的扩展帧可包含顶层 `status`、交付字段或 `usage`。工具状态包含名称和状态。报告任务的正文可能为空，应读取 `webLinks`、`downloads` 或 `reportUrl`。
- 网页和文件取服务端返回的 URL。相对 `reportUrl` 以 API 服务地址为基准解析。若收到 `resultType: "timeout"`，交付物为超时时保留的结果。
- 忽略 SSE 心跳注释。在 `finish_reason: "stop"` 后继续读取交付信息和用量，直到 `data: [DONE]`。流中失败会先发送含有 `error.message` 的帧。

**非流式输出**（`stream: false`）返回 `chat.completion` JSON，正文位于 `choices[0].message.content`。有交付物时还会返回相应的顶层链接字段。

```json
{
  "id": "chatcmpl-20261013-023806-g0vj",
  "object": "chat.completion",
  "created": 1791873486,
  "model": "deepseek-v4-pro (DeepSeek · pi)",
  "choices": [{ "index": 0, "message": { "role": "assistant", "content": "…" }, "finish_reason": "stop" }],
  "usage": { "prompt_tokens": 14706, "completion_tokens": 3, "total_tokens": 17013, "cost_usd": 0.0195 }
}
```

**流前校验错误**：HTTP 400，`{"error":{"message":"…","type":"invalid_request_error","code":"unknown_skill"}}`；会话占用时非流式返回 HTTP 429。

**调用示例**：

```bash
curl -N http://127.0.0.1:8767/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"skill":"ai-interview","stream":true,"messages":[{"role":"user","content":"我是应届生，目标岗位是前端开发，请开始模拟面试"}]}'
```

说明：附件用法同 `/api/chat`——先 `POST /api/upload`（可不传 `sessionId`，从响应里拿），再把返回的 `sessionId` 与 `path` 作为本端点的 `sessionId` / `attachments` 传入。超时上限同 `/api/chat`（报告类 20 分钟）。

**附件解析方式**（两种格式路径不同）：

- `.md` / `.txt`：**服务端直接内联**——文件文本（截断 1.6 万字）拼进发给模型的 prompt，不依赖 Agent 解析，可靠性最高；对接方方便的话建议简历转成 md/txt 再传。
- `.pdf` / `.docx` / `.doc`：文件落会话沙箱 `workspace/<sessionId>/uploads/`（即 Agent 工作目录），**由 Agent 运行时自行解析**（bash/read 工具抽取文本）；解析成败依赖运行环境工具与模型发挥，失败时技能按纪律在报告中登记缺口（如"简历材料未读取"），不会编造内容。

**career-guidance（就业指导报告）完整示例**：

```bash
curl -N http://127.0.0.1:8767/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "skill": "career-guidance",
    "taskTitle": "Java 后端实习岗位匹配分析",
    "stream": true,
    "messages": [{
      "role": "user",
      "content": "使用 $career-guidance 完成以下任务：\n- 目标岗位或方向：Java 后端实习\n- 当前阶段：在校找实习\n- 本次任务：岗位匹配\n- 目标地区：广州\n- 每周可投入时间：5–10 小时\n- 匿名经历摘要：计算机相关专业，完成过 Spring Boot 校园二手交易平台项目，负责接口设计与 MySQL 建模；暂无实习经历。\n\n请先复述任务边界与缺失信息，再按该 SKILL 的方法推进。"
    }]
  }'
```

- `taskTitle` 可选，透传为运行标题（运行记录展示与报告下载文件名）。
- 任务通常运行数分钟；期间先收到若干 `reasoning_content`（思考与过程叙述）帧和工具 status 帧，正文（`delta.content`）在任务完成时一次性发出。
- 成功终态依次为：收尾帧（`finish_reason:"stop"`）→ 报告帧（`"choices":[],"reportUrl":"/api/reports/<runId>"`）→ usage 帧 → `[DONE]`。前端拿 `reportUrl` 拼后端地址给用户即可打开/下载报告（同 `/api/chat` 的报告获取方式）。
- 报告未生成时终态为错误帧（`reportUrl` 缺失即失败，原因在 `error.message`）。

## 1. GET /api/health

健康检查，返回服务与模型信息。

```json
{
  "ok": true,
  "model": "deepseek/deepseek-v4-pro",
  "runner": "pi",
  "engines": [{ "id": "pi", "available": true, "model": "…", "version": "…" }],
  "message": "API 已配置"
}
```

## 2. POST /api/chat（核心接口，SSE 流式）

发起一次 Agent 运行，响应为 `text/event-stream`。

**请求体**（≤512KB）：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `skill` | string | 是 | 技能 id，见下方合法取值 |
| `messages` | array | 是 | 消息数组；**最后一条必须是** `{ "role": "user", "content": "…" }`，前面的历史消息作为上下文传入 |
| `sessionId` | string | 否 | 复用会话（多轮对话）；不传则新开，返回的 `session` 事件里带新 id |
| `taskTitle` | string | 否 | 任务标题，≤120 字符，用于运行记录展示 |
| `engine` | string | 否 | 仅支持 `"pi"`（默认），传其他值报 400 |
| `attachments` | array | 否 | 附件列表 `[{ "name": "简历.pdf", "path": "uploads/简历.pdf" }]`，`path` 为 `/api/upload` 返回的相对路径，最多 5 个 |

**skill 合法取值** 同第 0 节。

**SSE 事件**（每条为 `data: {JSON}\n\n`，按可能出现顺序）：

| type | 载荷 | 说明 |
|---|---|---|
| `started` | `runId`, `startedAt` | 首包，运行已开始 |
| `status` | `phase`, `state`?, `chars`?, `tool`?, `id`? | 过程状态，枚举见下表 |
| `session` | `sessionId` | 新会话创建时返回，调用方需保存用于后续多轮 |
| `text` | `delta` | 正文增量片段，拼接即为完整回答 |
| `usage` | `usage`, `content` | token 用量信息 |
| `done` | `content`, `resultType`, `charts`, `runId`, `reportUrl?` | **终态**。`resultType` 为 `success` / `timeout`；`reportUrl` 仅报告类技能（career-guidance / tech-forecast）成功生成报告时有值；此时 `content` 为空串，报告走该 URL 获取 |
| `error` | `message` | **终态**，运行失败 |

**`status` 事件枚举**（前端判别"正在做什么"的依据）：

| phase | state | 附加字段 | 含义 |
|---|---|---|---|
| `initializing` | —（无 state） | `message` | 正在启动运行环境（每轮一条） |
| `thinking` | `active` | `chars`（已积累思考字数） | 模型思考中，约 700ms 一条节流进度 |
| `text` | `active` | — | 正文输出中（text 增量本身走 `text` 事件，此状态只标记块开始） |
| `tool` | `active` | `tool`（工具名，如 bash/read）、`id`（调用 id） | 正在执行工具调用 |
| `tool` | `completed` / `failed` | `tool`、`id` | 工具调用结束（成功/失败） |

即：看到 `phase:"tool"` 就是工具调用；`thinking` 或 `chars` 在涨就是思考；`text` 增量就是正文。

说明：

- 每 15 秒发一次 `: ping` 注释行作心跳，忽略即可。
- `done` 和 `error` 互斥，收到任一即结束本次流。
- 超时：一般技能 10 分钟，`career-guidance` / `industry-education-report` 20 分钟；超时收到 `error`（或带 `resultType: "timeout"` 的 `done`）。
- 同一 `sessionId` 同时只能跑一个任务，占用中再发会收到 `error`。
- 客户端中途断开（关闭 SSE 连接）即中止本次运行。

**调用示例**（curl，`-N` 关闭缓冲）：

```bash
curl -N http://127.0.0.1:8767/api/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "skill": "ai-interview",
    "messages": [
      { "role": "user", "content": "我是应届生，目标岗位是前端开发，请开始模拟面试" }
    ]
  }'
```

多轮：保存 `session` 事件返回的 `sessionId`，下一轮请求带上它，`messages` 里附上之前的对话历史。

## 3. POST /api/upload（附件上传）

上传附件到会话沙箱，供 `/api/chat` 与 `/v1/chat/completions` 引用。应在同 `sessionId` 的 chat 之前调用。

**请求体**（≤10MB）：`{ "sessionId": "可选，新会话可不传", "filename": "简历.pdf", "dataBase64": "…base64…" }`

- `dataBase64` 兼容裸 base64 与 `data:` URL 前缀两种格式；也可用 `dataText` 直传文本内容。
- 扩展名白名单：`.pdf` `.docx` `.doc` `.md` `.txt`；单文件 ≤6MB；同名文件自动追加 `-1`/`-2` 序号不覆盖。

**响应**：

```json
{ "sessionId": "sess-…", "name": "简历.pdf", "path": "uploads/简历.pdf", "size": 123456 }
```

之后在 `/api/chat` 或 `/v1/chat/completions` 的 `attachments` 里传 `{ "name", "path" }`。解析方式见第 0 节"附件解析方式"：`.md`/`.txt` 服务端内联进 prompt（截断 1.6 万字），其余格式由 Agent 自行读取工作目录文件。

## 4. GET /api/reports/:runId（HTML 报告）

获取 career-guidance 生成的 HTML 报告（`done` 事件 `reportUrl` 指向此接口）。

- `GET /api/reports/{runId}`：内联预览（`Content-Type: text/html`）
- `GET /api/reports/{runId}?download=1` 或 `GET /api/reports/{runId}/download`：以附件下载

## 5. 运行记录（只读，可选）

| 接口 | 说明 |
|---|---|
| `GET /api/runs?limit=100&skill=…&outcome=…` | 运行列表（倒序），可按技能/结果过滤 |
| `GET /api/runs/{runId}` | 单次运行详情 `{ item, trace }` |
| `GET /api/runs/{runId}/file/events` | 原始事件流（ndjson） |
| `GET /api/runs/{runId}/file/trace` | 完整 trace（json） |
| `GET /api/runs/{runId}/file/report` | 结构化报告数据（json） |
| `GET /api/runs/{runId}/file/md` | trace 的 Markdown 版（按需生成） |

## 6. GET /api/skills（技能清单）

返回当前可运行的技能列表（与 `/v1/chat/completions` 的 `skill` 合法值同源）。智能体广场的技能卡片数随此接口动态增减；公开数据，无鉴权、无跨源限制。

```json
{
  "skills": [
    { "id": "career-guidance", "name": "career-guidance", "description": "为学生、求职者和在职转型者提供…", "installed": true },
    { "id": "classroom-assistant", "name": "classroom-assistant", "description": "只在用户明确提供或授权的课程资料范围内…", "installed": false }
  ]
}
```

- `installed: true` 表示仓库 `.agents/skills/<id>/` 下有真实技能文件夹，`name`/`description` 读自该 SKILL.md 的 frontmatter（`name` 是技能加载键，非中文展示名）。
- `installed: false` 为外部仓库接入的技能（提示词内置），`description` 取回落提示词首句。

## 典型接入流程

**路线 A：`/v1/chat/completions`（外部项目推荐）**

1. `GET /api/health` 确认服务可用。
2. 需要附件时：`POST /api/upload`（可不传 `sessionId`，响应里返回），拿到 `sessionId` 与 `path`。
3. `POST /v1/chat/completions`（带 `skill`、`messages`，附件场景带上 `sessionId` 与 `attachments`），流式则拼 `content` 增量、等 `[DONE]`（失败看 `error` 帧）。
4. career-guidance 场景：终态报告帧的 `reportUrl` 拼后端地址即为报告链接。

**路线 B：`/api/chat`（广场前端协议）**

1. `GET /api/health` 确认服务可用。
2. 需要附件时：`POST /api/upload`（可先不传 sessionId，从响应里拿）。
3. `POST /api/chat`（带 `sessionId` 与 `attachments`），逐条处理 SSE：拼 `text` 增量、存 `session` 的 sessionId、等 `done`/`error`。
4. career-guidance 场景：用 `done.reportUrl`（或直接 `GET /api/reports/{runId}`）取报告。
