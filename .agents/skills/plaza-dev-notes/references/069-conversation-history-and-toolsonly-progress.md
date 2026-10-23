# 069 · 历史按对话展示整段记录 + 运行进度只显示真实工具调用

- 状态：已实现（2026-10-16。构建通过；curl 验证 conversation 剥离（general 前缀、已安装技能 `<skill>` 展开文档与契约后缀）、列表 clientSessionId 分组；无头浏览器验证侧栏「N 条消息」分组、对话转录 DOM、产物链接与截图。真实长对话回归待用户）。
- 补注（2026-10-16 晚）：「详情卡」形态当日即被 [070-history-as-normal-chat.md](070-history-as-normal-chat.md) 取代——点开历史直接载入正常消息流并可续聊，专门卡片/kicker/产物区删除，报告链接内联在 AI 消息上。本记录的 conversation 派生、clientSessionId 分组、进度只显示工具调用三项约定不变。
- 补注（2026-10-23）：本记录“中间 assistant 叙述独立气泡展示”的取舍由 [080](080-conversation-source-and-process.md) 替代：每个用户轮仅一条最终回答，过程说明与工具聚合并默认折叠。原始输入快照优先，旧 `<skill>` 包装剥离的空前缀提前返回问题已修复。
- 动机：用户反馈三点——① 所有运行固定渲染「启动环境/分析任务/工具/生成结果」四阶段行不合理，通用智能体应按意图决定是否调工具，"生成结果"不是每次对话的必要步骤；② 点开历史想看的是包含来往消息的对话记录，不是孤立的最终结果；③ "结果展示"应删除，产物只保留打开 HTML 报告与下载 Agent 生成文件两种动作。

## 约定细节

### 运行进度：只登记真实工具调用（030 边界不变）

- `handleProgressStatus`（`web/src/pages/ExperiencePage.vue:139`）只处理 `phase === 'tool'` 事件：active 建行（沿用 toolProgress 安全映射），completed/failed 关行；`phase === 'text'` 仅兜底关闭未收到完成事件的工具行。initializing/thinking/writing 占位行彻底删除，`ProgressItem.phase` 收窄为 `'tool'`。
- 消息头状态行（`makeStreamHandler`，`web/src/pages/ExperiencePage.vue:324`）收敛为三态：等待/思考统一「正在思考…」，工具阶段显示映射后的工具文案，正文开始即清空（流式文本本身即反馈）。「正在启动运行环境」「正在生成结果」措辞退出展示层。
- `ToolCallGroup` 组头文案「运行进度」→「工具调用」（`web/src/components/ToolCallGroup.vue:62`）；无工具调用的运行不渲染该组。

### 详情 API：conversation 对话视图

- `GET /api/runs/:runId` 返回体新增 `conversation: Array<{ role: 'user'|'assistant'; text }>`（`web/server/index.ts:341`）。
- `deriveConversation`（`web/server/index.ts:269`）从权威 trace 提取：只取 user/assistant 的 text parts（reasoning、tool 过程不进对话视图）。
- 包装剥离两层（`web/server/index.ts:255` `promptWrappers`）：用哨兵内容跑一遍 `runner.buildPrompt(skill, …, first/!first)` 反推前缀/后缀，与拼装逻辑天然同步，不维护第二份提示词副本；pi 把 `/skill:x` 展开为完整技能文档写入 trace（sentinel 前缀对不上），对 `<skill ` 开头的消息按 `</skill>` 边界截断后再剥契约/侧车后缀。首轮系统提示、逐轮契约重申、会话重建重注入三种包装都能剥掉。
- 前端类型：`RunListItem` 补 `clientSessionId?`（`web/src/data/runsMock.ts`）；`RunDetailResult` 补 `conversation?`（`web/src/api/runsApi.ts`）。

### 侧栏：按对话（clientSessionId）分组

- `historyGroups`（`web/src/pages/ExperiencePage.vue:522`）把同一 `clientSessionId` 的多条运行合成一个对话条目；旧记录无该字段时退化为单运行一组。条目标题取最早一次运行的 taskTitle/promptDigest（对话开场），meta 行 `技能 · N 条消息`（多条时）或 `技能 · 时间`，结局徽章取最新运行。
- 换技能/新建对话会开新 clientSessionId（067 约定），天然成为分组边界——一个对话内技能恒定。
- 点击选择对话的**最新一次运行**取详情：trace 是会话累计快照，最新记录包含完整对话。

### 详情卡：整段对话转录 + 产物动作

- `.exp-history-view` 由"最终结果展示"（ReportOutput 单输出 + charts）改为只读对话转录 `.exp-history-talk`：user 右气泡（复用 `.exp-msg-user`）、assistant 左排（复用 `.exp-msg-ai`/`ReportOutput` 渲染 markdown），逐条对应 conversation。
- 产物行 `.exp-history-files`（存在才渲染）：`打开 HTML 报告`（`/api/reports/:runId`，新窗口）、`下载报告 HTML`（`?download=1`）、`下载 report.json`（`/api/runs/:runId/file/report`），全部按 `item.files` 存在性门控。charts 展示从历史功能中删除。

## 成本与取舍

- 多运行重叠对话：同会话每条运行的 trace 都含历史轮次，侧栏若不分组会重复；分组后点旧对话条目也加载最新 trace，一致完整。
- assistant 中间叙述（"I'll start by reading…"等 text parts）作为独立气泡展示：与在线对话实时流的拼接口径一致（live 也是全部 text delta 连续渲染），否决"只显示最后一条 assistant"——会丢追问场景的中途答复。
- 哨兵反推 buildPrompt：依赖 buildPrompt 纯函数性质（只依赖 skill/messages/first），未来若引入按会话状态变化的拼装需同步改造 wrapper 推导；用户消息本身以 `<skill ` 开头的极端情况会被误剥（可接受）。
- 历史详情只读不续聊：仍是 068 的取舍；从运行记录恢复可续聊会话需持久化 sessionId（路线未变）。

## 后续扩展路线

- 从历史对话恢复会话：把 clientSessionId ↔ convSessions/convSlugs 重建，点「继续对话」回到输入区带上下文（本次未做）。
- 产物清单泛化：uploads 附件回链、trace.md 导出按需加入产物行。
- 长对话转录虚拟滚动（当前一次渲染全部轮次）。

## 验证（2026-10-16 实测）

- `cd web && npm run build`（vue-tsc + vite）通过。
- curl：`/api/runs?limit=6` 返回项均带 clientSessionId，两轮 curl 测试会话（你好 + 追问）共用 `sess-20261016-163445-sn2g`；其详情 conversation 为 4 轮（user 你好 / assistant 回答 / user 追问 / assistant 你好），user 文本无系统提示词残留；career-guidance 运行（含 `<skill>` 展开文档 + 契约后缀 + 第二轮追问）user 文本干净剥离，files 含 html → 详情有打开/下载链接。
- 无头浏览器（CDP）：侧栏出现「你好 | 通用智能体 · 2 条消息 | 成功」合并条目（3 个多条对话组）；点开转录含 2 条 user 气泡与 2 条 assistant 渲染；历史视图无 `.tool-group`；tech-forecast 对话产物行 = `打开 HTML 报告 -> /api/reports/…` + `下载报告 HTML -> …?download=1`（无 report.json 时不渲染第三项）；截图核对版式。
