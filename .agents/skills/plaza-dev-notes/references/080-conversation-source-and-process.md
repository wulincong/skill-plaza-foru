# 080 · 用户原始输入与执行过程分离

**状态**：已实现（2026-10-23：28 项回归、前端构建、真实 Pi SSE、新记录历史、既有 PDF 历史及浏览器折叠交互通过；OpenAI 兼容端点回归通过）。

## 动机

历史恢复把 Pi 展开的 `<skill>` 文档与附件注入说明显示在用户气泡里：旧 `strip` 首先匹配到续轮的空前缀/空后缀，直接返回完整文本，后续技能剥离永远不执行。同时历史按 assistant 消息逐条展示，实时 plaza wire 也把所有 text delta 当正文；工具前的“我先检查…”因此变成多条回答。用户要求原始消息与后端注入分开，中间过程默认折叠，正文只显示最终回答。

## 约定细节

### 输入来源与历史投影

- `RunRecord.userMessage?: string`（`web/server/lib/traceExport.ts:148`）保存注入附件/技能说明之前的用户输入，`index.ts:1148` 随运行记录持久化。它不替代历史列表的 `taskTitle/promptDigest`，也不改变引擎实际 prompt 或权威 trace。
- 详情路由按同 clientSessionId 和不晚于当前运行的时间收集原始输入；2026-11-03 起跨引擎进程合并、按 Pi 原生会话累计快照去重（见 [089](089-conversation-restart-and-delivery-permissions.md)），不再仅取同 engineSessionId。各快照对应的记录数与 trace 用户轮数一致时才按顺序使用原始输入；数量不一致则保守回退，避免将未发送/失败请求错配到另一轮。附件在用户视图仅显示 `[附件] 文件名`。
- `conversation.ts:23` 只兼容能明确识别的旧格式：先去 Pi `<skill ... location=...>` 展开块，再清理 buildPrompt 包装与附件注入；空前后缀不能作为提前返回条件。原始输入快照优先，因此用户自己输入的类似技能标签不会被误删。不批量迁移/改写历史 trace。
- `conversation.ts:48` 按每个 user 轮次聚合 assistant：最后一条无工具消息才是正文；此前的可见 text 进入 `process?: string[]`，该轮所有工具汇总为 `tools`，保留真实起止时间与成败。仅有工具而没有最终回答的中断轮不把前置说明提升成答案；不同用户轮的回答与工具不能混并。system、reasoning 和工具 input/output 不进入用户对话投影。

### 实时分流与前端折叠

- `index.ts:744` 的消息缓冲同时用于 plaza 和 OpenAI wire。沿用 Pi `message_end` 的 toolCall 定性：工具消息的可见 text 为过程说明，plaza 用现有 `{type:'status', phase:'thinking', state:'completed', message}` 发送；最终答复用 `text.delta` 发送。协议帧形状不新增字段，消息边界仍是后端内部信号。
- 原始 `thinking_delta` 仍不进入 plaza 用户界面；OpenAI 的 reasoning_content/content 分流保持既有行为。消息文本按完整消息边界发送，代价是最终正文按消息到达，不再逐 token 显示；等待期继续显示真实工具状态与计时。
- `ExperiencePage.vue:397` 把过程说明写入 `Msg.process`，`done.content` 为最终正文；`:443` 保存工具摘要，下一轮开始后上一轮工具组仍存在。历史恢复同样接收 `process`，一个用户轮次只有一个 AI 回答。
- `ToolCallGroup.vue:28` 实时与历史统一默认折叠；新增 `notes`/`running` props，展开可查看过程说明与全部工具。过程说明不计入工具步数（`:67`），工具参数、输出和原始 reasoning 不进入面板。最终正文与产物链接留在折叠区外（`ExperiencePage.vue:989`）。

## 成本与取舍

- 否决继续把中间 assistant 文本独立渲染为回答：会把执行过程误认成结论，原 069 的该项取舍由本记录替代。
- 不把原始 reasoning 填入折叠区，也不回放工具输入/输出；折叠区承载已经面向用户生成的过程说明和安全工具摘要。
- 保存原始输入会在索引中增加一份用户文本，换取新历史不再依赖提示词字符串解析。旧记录只修复明确格式；不为不可靠的历史形态增加迁移或猜测。
- 原始 trace 继续用于开发详情与审计，用户对话采用单独投影，避免为 UI 清理而损坏运行证据。

## 验证

- `node --test web/server/lib/conversation.test.mjs web/server/lib/pdfReport.test.mjs web/server/lib/htmlReport.test.ts web/src/composables/useChatApi.test.mjs`：28 过 0 挂；新增 7 项覆盖技能展开/空包装、附件注入、多轮分组、过程与正文、工具链中断、原始输入优先与错配回退。
- `cd web && npm run build`、服务端 `node --check`、`git diff --check` 通过。
- 用户指出的旧 PDF 记录：详情与浏览器确认用户气泡仅原话+文件名，1 条最终回答，默认折叠 3 段过程说明与 22 次工具；展开可查，正文无技能提示/中间说明。历史 PDF 查看/下载链接沿用既有门控。
- 真实 Pi 通用任务（运行 `20261023-152822-jq4b`）先说明步骤再调用 bash：plaza `text` 仅“验证完成：5”，说明进入 thinking/message 状态；落库原始 userMessage 与恢复后的用户消息一致。OpenAI 真实工具任务的 content 仅“56”，工具 status、reasoning_content 与 `[DONE]` 保留。
- 浏览器模拟流验证：最终答案到达前过程区已默认折叠，说明不进入正文；第二轮开始后第一轮工具摘要仍保留。浏览器与 SSE 的实测产物保留在本机临时验收目录，持久运行证据以 traces 为准。

## 后续扩展路线

- 若要恢复逐 token 最终答复，需要引擎在输出前提供稳定的消息分类，或设计可撤回正文的独立协议；不再用时序猜测 text/工具归属。
- 如引入多文件产物或多引擎累计历史，使用显式输入消息 ID 关联索引和 trace，替代数量一致时的顺序关联。
- 不支持的旧提示词格式仅在具体证据出现时补精确规则，不扩大通用正则删除范围。
