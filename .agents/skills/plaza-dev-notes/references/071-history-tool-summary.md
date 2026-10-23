# 071 · 历史对话补回工具调用摘要

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
