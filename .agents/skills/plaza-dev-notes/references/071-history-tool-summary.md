# 071 · 历史对话补回工具调用摘要

## 2026-11-03 工具调用进度（已实现）

按模型消息分组后，组头只显示调用总数，用户看不到并行调用还有几项在执行。`web/src/components/ToolCallGroup.vue:10-11,41` 从本轮所有步骤的工具状态计算“工具调用 已结束数/已记录数”。成功和失败都计入分子，仍为 `active` 的调用只计入分母。零调用时省略计数。实时与历史共用同一口径。

分母随实际登记的调用增长，预估后续调用会给出虚假进度。直接从现有步骤快照派生计数，避免重发同一步时重复累加；以后若增加工具状态，需要同步界定该状态是否已结束。

Chrome 通过对话输入框回放 SSE，核对零调用、并行调用的 18/20 → 19/20 → 20/20，以及失败明细。重新打开既有历史轮显示 10/10，与 10 行工具一致。两项执行计时回归及生产构建通过。

## 2026-11-03 计时与过程分组修订（已实现）

用户发现过程区混排了不同调用的说明，组头时长与运行记录也不一致。旧版把模型流式生成工具参数的区间记为工具耗时，组头仅覆盖首尾工具之间的时间。下方 10 月记录反映旧实现。

- **完整轮次**。`web/server/index.ts:1207` 在终态冻结从服务端启动本轮到交付结果的墙钟时长，SSE 的 `done/error.durationMs` 和运行索引使用同一值。初始化、模型等待、生成答案、收尾均在总时长内。结束前界面显示运行计时，完成或恢复历史后显示服务端值。
- **归属**。`web/server/lib/execution.ts:8` 按 Pi assistant 消息形成步骤。每步含 `thinking: [{startedAt?,endedAt?}]`、可选公开过程说明 `note` 和 `tools: [{id,tool,state,startedAt?,endedAt?}]`。调用 ID 把并行执行及晚到的结束帧关联回发起步骤。同一步有多次调用时只展示一次说明。有独立思考的最终回答也保留该步。隐藏推理、命令参数与工具返回值不进入这个投影。
- **时间证据**。`web/server/lib/piRunner.ts:358` 使用 `tool_execution_start/end` 计实际工具耗时。思考流从可见的流式起始或首个增量到结束标记，提供方只有完整思考块时保留发生标记，缺失边界时省略耗时。它无法测量提供方输出首包前内部推理用了多久。`web/shared/execution.ts:26` 对重叠工具区间取并集；思考与工具重合时优先归入工具。总时长扣除这些已覆盖的时间归入“等待与生成”，包含服务端收尾开销。缺少必要边界则只显示可确认的时长。
- **实时与恢复**。`web/server/index.ts:851` 的 plaza SSE 帧 `{type:'execution',index,step}` 按序号更新一个步骤，终态快照保存到本轮 trace 的 `execution`。历史按原运行配对使用索引时长与快照；旧记录按需流式读该轮已有 events 日志（`web/server/lib/execution.ts:77`）。日志缺失时只用原 assistant 消息分组，旧工具参数生成时长不作为执行时间显示。`web/src/components/ToolCallGroup.vue:9` 将含公开说明或工具的步骤用于明细，保持原分组和顺序。纯等待步骤此前逐段显示“模型思考”，长任务会反复出现同一行。现在思考区间只参与整轮耗时汇总；展开后，同一步的公开说明紧接对应工具，无明细或汇总时收起展开入口。

**取舍与后续。** 每次更新只发发生变化的步骤，存储小型公开投影换取历史恢复的一致性。否决平铺两份列表后按位置配对，这会错配没有说明的调用及并行工具。旧日志按行读取，未批量改写历史记录；超长历史的重复读取开销留待观测。

**验证。** 52 项回归与生产构建通过。专项用例覆盖并行工具、跨步骤交错结束、失败、缺失边界与不公开工具参数或推理原文。真实浏览器中 Flash 执行含 1 秒等待的命令，2.781 秒总用时中工具约 1.0 秒，公开说明出现在该命令上方。复核既有记录 `20261103-105417-hggy`，129322ms 总用时分为 20374ms 思考输出、97683ms 工具执行、11265ms 等待与生成。该历史轮共 11 个步骤，其中 10 个步骤同时有思考与工具。精简明细后，Chrome 展开同一历史轮显示 10 个非空分组、10 行工具和原有公开说明，思考耗时在汇总显示一次。两项计时回归及生产构建通过。


- 状态：已实现（2026-10-16。构建通过；curl 验证 conversation 携带工具摘要；无头浏览器验证历史对话渲染折叠工具组、展开行、无命令/SQL/路径泄露。同日晚补注：工具耗时已记录进 trace 并在历史还原，见文末）。
- 2026-10-23：每轮全部工具改为挂在该轮唯一的最终回答上，中间可见叙述进入 `process` 并与工具一起默认折叠，不再分别挂首条/末条 AI 消息。协议与验证见 [080](080-conversation-source-and-process.md)。
- 补注（2026-10-16 晚）：原「历史工具行无耗时」的限制已消除——PiRunner 运行时捕获每个工具的起止时间并写入 trace 导出（工具 part 新增 `startedAt`/`endedAt` epoch ms），conversation.tools 透传，前端 `historyToolItems` 映射为 ProgressItem 的 `startedAt`/`finishedAt`：历史组恢复每行耗时与组头真实总时长（首个开始→最后结束的墙钟时间），与实时运行完全同构。计时实现：`toolcall_start` 通知不带调用 id，按 `轮次:contentIndex` 键建档（轮次 = message_end 计数），`toolcall_end` 带 callID 补 `id:callID` 别名，`exportTrace` 按 part.callID 取用；disposeSession 清理。旧 trace 无计时字段时优雅降级（不显示时长，不伪造）。实测：新运行（20261016-173844）历史组头「已完成 2 步 · 共 2.9s」、行「执行数据处理 · 507ms / 288ms」。
- 动机：用户发现实时对话有「工具调用」组（折叠行 + 明细），从历史重新打开同一对话后工具信息消失——070 的 conversation 只含文本轮次，工具 parts 被排除。历史应与实时对话同构。

## 约定细节

- `deriveConversation`（`web/server/index.ts`）assistant 轮新增 `tools?: Array<{ tool: string; failed: boolean }>`：工具 parts 降级为「名称 + 成败」（`state.status === 'error'` 为失败），030 边界不变——参数、命令、SQL、路径不出服务端。
- 聚合口径：一个用户轮次内的全部工具调用挂到该轮**首条** AI 消息的 `tools`（对齐实时对话"一轮一个组"）；末轮只有工具没有正文时并入该轮最后一条 AI 消息。
- 前端（`web/src/pages/ExperiencePage.vue`）：`Msg.tools` + `historyToolItems()`（ProgressItem：中性标题、failed 显示「工具执行失败」，无耗时字段），恢复的消息渲染第二个 `ToolCallGroup` 分支（`:prose-started="true"` 初始折叠）；实时组与历史组互斥（progressOwner 优先）。
- `ToolCallGroup`（`web/src/components/ToolCallGroup.vue`）：`open` 初始值跟随 `proseStarted`（历史进场即折叠，修复 watch 不触发初始值的问题）；新增 `hasTiming`——没有计时数据的组头部不显示「共 Xs」，不伪造。
- `toolProgress` 文案中性化（「正在查询岗位库」→「查询岗位库」等）：实时状态行由 `makeStreamHandler` 拼「正在 + 标题 + …」，已完成行与历史行不再显示"正在"字样。

## 成本与取舍

- 历史工具行无耗时：trace 导出（get_messages 快照）不含 per-call 起止时间，实时事件流（events.jsonl 的 message_update）有但按 callID 关联脆弱（toolcall_start 不带 id），否决事件流反推；显示"已完成 N 步"不带时长。
- 旧记录同样生效：tools 从既有 trace 的 tool parts 派生，无需回填。

## 后续扩展路线

- ~~trace 导出补 per-call 起止时间~~（2026-10-16 晚已实现，见顶部补注）。

## 验证（2026-10-16 实测）

- `cd web && npm run build` 通过。
- curl：天气运行（20261016-162605）conversation 的 assistant 轮携带 4 个 `{tool: 'bash', failed: false}`；你好运行无工具（tools 缺省）。
- 无头浏览器：点开天气对话 → 「工具调用 已完成 4 步，点击查看」默认折叠；展开 4 行「执行数据处理 · 已完成」；DOM 正则断言无 `web-search|\.mjs|SELECT |workspace/` 泄露；截图核对。
