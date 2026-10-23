# 036 · OpenAI 兼容端点 /v1/chat/completions：外部项目统一接入入口

**状态**：已实现（本地流式/非流式/错误用例/多轮拍平/回归全通过，2026-10-13；2026-10-14 流式升级为标准 `chat.completion.chunk` 并复验通过；2026-10-15 二次修订：标准 chunk 外壳细化 + 叙述定性上移消息边界 + 侧车扣留按 `SIDECAR_SKILLS` 门控 + 工具状态帧聚合，详见下方两节与 `docs/openai-stream-upgrade.md`。typecheck 与帧序对照通过，线上真实抓包回归待跑）

## 2026-10-14 修订：流式帧升级为标准 chunk 格式

- **动机**：外部项目（Java 客户端）按标准 OpenAI 流式结构定义 `OpenAIChatCompletionChunk`（`choices[]`/`object`/`created`/`model`/`usage`/`id`），原简化帧正文在顶层 `content`、无 `choices` 数组，对接方反序列化后取不到任何正文。升级后对接方现有类零改动可解析。
- **新帧规范**（详见 `docs/agent-api.md` 第 0 节与 `docs/openai-stream-upgrade.md`）：所有帧为 `{id, object:"chat.completion.chunk", created, model, choices}` 外壳；role 首帧（`started` 时发出）；思考 `delta.reasoning_content`（DeepSeek 通行字段）；正文 `delta.content`；`finish_reason:"stop"` 收尾帧；报告帧与 usage 帧为 `choices:[]` + 顶层扩展（`reportUrl`/`runId`/`resultType`、`usage`）。
- **工具活动帧（新增）**：`status()` 原 openai 协议直接丢弃，现仅转发 `phase:'tool'` 事件为 `choices:[]` + 顶层 `status:{phase,state,tool,id}`——**活动时间线级别**，只有工具名与状态，不含入参/返回内容（runner 层流式事件本就没有参数；完整输入输出仅落盘 trace）。thinking/text 的 chars 节流状态不转发（全文已流式，冗余）。否决参数级 `tool_calls` 流（需扩 RunnerEvent，报告类技能外部展示只需进度级别）与 SSE 注释行方案（标准客户端不可解析）。
- **改动点**：仅 `web/server/index.ts` `createChatWire` openai 流式分支——`frame()` 拆为 `chunk(delta, finishReason)` 与 `extChunk(extra)` 两个出口；`started`/`thinkingDelta`/`textDelta`/`status`/`done` 五处。plaza 分支逐字节不变（`/api/chat` 事件序回归一致），非流式 JSON 不变，`busy`/`error` 流中帧不变。
- **复验**（2026-10-14，PI_MODEL=deepseek-flash）：流式简单问题 role → reasoning_content 1569 帧 → content 362 帧 → stop → usage → `[DONE]`，工具活动帧 32 条（classroom-assistant bash 工具）；career-guidance 流式端到端（run 20261014-135228-hzyi，6.9 分钟）终态 stop → 报告帧 `reportUrl`/`resultType:"success"` → usage → `[DONE]`，报告 URL 200/126KB 六章完整；400 假 skill 错误体不变；非流式标准 `chat.completion` 不变；plaza 事件序回归一致。公网浏览器侧打开报告仍待用户验证。

## 动机

另一个项目要调用本服务，其客户端已按 OpenAI 风格 SSE（`content` 正文增量、`reasonContent` 思考增量、`data: [DONE]`）开发。直接改造 `/api/chat` 会破坏广场前端两处事件消费（UsePage/ExperiencePage），故新增平行端点，两协议并存、共用编排核心。

**端点定位（长期策略）**：`/v1/chat/completions` 是外部项目的**唯一**接入入口；后续外部需求以可选字段在此扩展（attachments、会话优化等），协议骨架不破坏。`/api/chat` 冻结为广场前端专用、不再演进。外部接口文档在仓库 `docs/agent-api.md` 第 0 节。

## 约定细节

### 思考原文事件（前置改动）

- `web/server/lib/runner.ts:28-30`：`RunnerEvent` 新增 `{ kind: 'thinking_delta'; delta: string }`。
- `web/server/lib/piRunner.ts:309-314`：pi `thinking_delta` 分支计数照发（节流 status，plaza 前端 030 进度时间线不变），**同时** emit 原文事件。此前原文在该行被降级为字符计数丢弃（008 的取舍，本记录兑现其"后续扩展路线"）。

### 共享编排核心 + wire 适配器

- `web/server/index.ts:399-428`：`TurnParams`（protocol/stream/skill/messages/sessionId/taskTitle/attachments）；`handleOpenAiChat`（校验 + 历史拍平）与 `handleChat`（plaza 校验，行为与旧版一致）都调 `runChatTurn`。
- `web/server/index.ts` `createChatWire(protocol, stream)`：两套 wire 相邻放置——
  - **plaza wire**：输出与旧版 `/api/chat` 逐字节一致的 `type` 事件帧（回归安全）；
  - **openai wire**（2026-10-15 升级，帧规范见 `docs/openai-stream-upgrade.md` §二）：流式输出标准 `chat.completion.chunk` 外壳——role 首帧、`choices[0].delta.reasoning_content`（思考 + 过程叙述）、`delta.content`（仅最终答复）、`choices:[]` 顶层扩展帧（`status`/`reportUrl`/`usage` 含 cost_usd）、`finish_reason:"stop"` 收尾帧、`[DONE]`；JSON 模式不写 SSE 头，终态一次性回 `chat.completion`（career-guidance 成功时顶层 `reportUrl`/`runId` 扩展字段，`content` 空串）。
- 错误映射：流前校验 400（`unknown_skill_model` 列出可用技能）；流中失败 `{"error":{...,"type":"agent_error"}}` + `[DONE]`；非流式 agent 错误 500、会话占用 429。
- 会话与多轮：技能走**独立 `skill` 字段**（2026-10-13 修订，最初设计为复用 `model` 字段；因语义混淆改为独立字段，`model` 彻底释放——忽略不校验，预留给将来按请求选模型；错误码 `unknown_skill` 并列出可用技能；2026-10-16 起可用值另含 `general` 通用智能体——不挂技能直接回答，见 067，不进 `/api/skills` 清单但两入口校验均放行）。`taskTitle` 可选透传（同 plaza 清洗规则，用于运行标题与报告文件名）。无 `sessionId` 或服务端不认识时，messages>1 则历史拍平为「【对话历史】…【当前消息】…」注入首轮 prompt（复用 buildPrompt，不动 runner）；promptDigest 对拍平消息取【当前消息】段。非流式 JSON 的 `model` 字段回显 `runner.describe()` 真实服务模型。
- trace：`RunRecord.protocol: 'plaza' | 'openai'`（`web/server/lib/traceExport.ts:141-142`），运行记录页可区分两类流量；其余落盘（events/trace/报告校验/agentEnv）两入口完全一致。

### 维护性约定（新事件/字段的跟随关系）

- trace 记录、Agent 编排类改动在核心，改一处两入口自动生效。
- 新 RunnerEvent 的输出映射在两个 wire 各加 case（相邻放置降低遗漏）。
- 广场 `/api/chat` 自身协议变化有意不跟随——OpenAI 帧格式是冻结的对外契约。

### 流式升级为标准 chunk + 两项流式修复（2026-10-15，方案 `docs/openai-stream-upgrade.md`）

- **标准 chunk 外壳**：`createChatWire` 内 `frame(delta, finishReason?)` 出 `choices[0].delta` 增量帧、`extFrame(extra)` 出 `choices:[]` 顶层扩展帧（status/reportUrl/usage），`id`/`created`/`model` 复用 `begin()` 就绪值；帧序 role 首帧 → reasoning 增量 → 工具 status 帧 → content（仅最终答案）→ stop 帧 → 报告帧 → usage 帧 → `[DONE]`。仅 openai 分支改动，plaza 分支逐字节不变。
- **叙述缓冲与重分类（2026-10-15 二次修订：定性上移消息边界）**（修"过程叙述混进最终答案"）：Agent 一次运行产出多条 assistant 消息，工具调用前的过渡语与最终答复同为 text 块。openai 流式正文按消息缓冲（`msgBuf`）不外发；piRunner `message_end` 拿完整块列表一次定性——含 toolCall 块的消息其全部文本是过程叙述（`tool:'toolcall'`），不含则是最终答复（`tool:'final'`）；wire 在消息边界一次分流：叙述整段进 `reasoning_content`、最终答复整段进 `delta.content`。`message`/`start` 兜底上一条消息 end 丢失的残余缓冲（按叙述）、done 残余按最终答复、`error()`/`busy()` 丢弃。代价：content 与叙述按消息粒度突发、不再逐 delta 流式；thinking 增量不受影响。四轮事件级/消息级修复泄漏的实证：`recorde|d`、整段过渡语、`HTM|L`、`inline SVG charts.` 正好 18 字符——根因是事件映射层侧车扣留曾**无条件**滞后 18 字符（`SIDECAR_MARKER.length-1`）才放行，放行时机不定（同句拆在工具事件两侧、词中断裂），而 `SIDECAR_SKILLS` 是空集合，扣留层保护的是空气；现已按 `SIDECAR_SKILLS.has(skill)` 门控（空集合=全员即时透传），非侧车技能消息内全部 text 增量先于 message_end 到达（trace 实证），消息级定性确定性成立。
- **工具状态帧聚合**（修"状态帧刷屏/一直跳"）：active 帧压 `TOOL_ACTIVE_HOLD_MS`（300ms，`index.ts` 顶部）存入 `heldActive`，终态先到即 clearTimeout 吞掉 active——亚秒级工具只见终态帧；超时仍未终态才补发 active。终态缺 tool/id（旧事件兼容）从压帧条目回填；`finish()` 清空压帧定时器。叙述定性已上移消息级，聚合只管状态帧。
- **piRunner `toolcall_end` 字段路径修复**（修"completed 帧匿名"）：`web/server/lib/piRunner.ts:318-324` id/name 改从 `ev.toolCall` 下取（真实载荷顶层无这两个字段），顶层字段保留回落；`toolcall_start` 分支不动。plaza 协议同为纯增量字段受益。

## 成本与取舍

- 无新增常驻开销；无会话复用时对方每次调用技能指令重注入约 +1~2K token（实测 ai-interview 首轮 prompt_tokens ≈ 14.7K）。
- 被否决方案：① 直接改 `/api/chat` 输出格式——破坏广场前端，否决；② 复制一份完整 handler——trace/报告捕获/自愈全部双份维护，否决；③ reportUrl 走响应头（代理/封装易丢）或轮询接口（复杂+延迟），改为终帧扩展字段，标准客户端忽略未知字段不破坏。

## 验证口径（2026-10-15 消息级定性 + 扣留门控落地后实测，PI_MODEL=deepseek-flash）

- 静态：`tsc --noEmit`（index.ts + piRunner.ts）0 错误（含既有 2 处 TS2322 一并修复）；htmlReport 单测 12/12。
- 无工具完整运行（classroom-assistant）：role 首帧 → thinking 实时进 reasoning_content → **最终答复单帧完整发出** → stop → usage($0.0047) → [DONE]。对照扣留层行为（答案尾 18 字符会被拆进 done 兜底第二帧），单帧完整即门控生效的直接证据。
- plaza /api/chat 回归：帧型齐全（started/initializing/session/status/text×N/usage/done），`phase:'message'` 内部定性事件零外泄；text 增量因透传变为词级多帧（原扣留层合并转发），UsePage 按 delta 追加展示不受影响。
- 重型技能三次运行（career-guidance 18.7min / ai-interview 10min / tech-forecast 14.7min，trace xrvi/8j9s/z2sy）均被环境因素中断——内网 MySQL 断连致 bash 查询黑洞挂死 18min（nc 验证 192.168.8.1:3908 不可达）、DeepSeek flash 晚间响应极慢/首条消息挂起至服务端超时——但**到中断点为止全部帧零泄漏**：content 通道全程为空，叙述 100% 进 reasoning_content（1813/390/1068 字），status 帧 22/3/14 且 0 匿名。
- career-guidance 完整成功路径复跑通过（2026-10-15 20:43，run `20261015-204342-rjfq`，flash，约 18 分钟 / $0.062）：content **单帧 88 字纯最终答复**（零英文叙述，唯一英文词为题目自带的 Java），reasoning 10942 帧 33594 字承载全部过程叙述与思考，status 67 帧 0 匿名，终态 content×1 → stop → reportUrl → usage → [DONE]，报告链接 200 / 132KB。对照泄漏版本（同 prompt run wfgq）：content 混入 "inline SVG charts." 碎片且答案被拆两帧——本次单帧完整纯净，消息级定性 + 扣留门控修复闭环。

## 验证口径（2026-10-15 流式升级后本地实测，PI_MODEL=deepseek-flash）

openai 流式（ai-interview）content 仅 1 帧纯最终答复、英文过渡语全部进 reasoning_content；status 帧同题 36→21、亚秒工具只出终态帧且 0 匿名；plaza /api/chat 回归帧序与 done 载荷不变、13/13 终态帧带 tool/id；假 skill 400 为 OpenAI 错误体。详见 `docs/openai-stream-upgrade.md` §七。线上部署后真实抓包回归待跑。

## 验证口径（2026-10-13 本地实测，PI_MODEL=deepseek-v4-pro）

1. ✅ 流式（classroom-assistant 推理型问题）：reasonContent 989 字 → content 增量 → usage 帧 → [DONE]；简单问题无思考阶段时只有 content（pi 未吐 thinking_delta，符合预期）。
2. ✅ 非流式（ai-interview）：标准 chat.completion JSON，usage 含 cost_usd，model 回显真实服务模型。
3. ✅ 错误用例：缺/假 skill 400（列出 5 个可用技能）、空 messages 400，均为 OpenAI 错误体；乱填 model 被忽略照常运行。
4. ✅ 多轮拍平：两轮历史 + 新问题（无 sessionId），模型正确 recall 历史中的代号。
5. ✅ 回归：`/api/chat`（ai-interview）事件序 started → status → session → status → usage → text → usage → done，done 载荷形状与旧版一致；`/api/runs` 两条流量 protocol 分别为 plaza/openai。
6. ✅ career-guidance 端到端（/v1 流式，2026-10-13 run 20261013-025750-ydum）：reasonContent 66414 字流式输出、taskTitle 透传入记录、protocol=openai、trace 落盘全部正确；报告校验失败走 error 帧 + [DONE]（失败原因透传），**失败路径行为符合协议设计**。报告本身未过校验是 VPN 导致内网岗位库查询失败后 Agent 未按规则标注"热点图未评估"（环境+合规问题，与端点无关；VPN 关闭后公网侧同类运行当日已成功）。
7. ⬜ 公网部署后 career-guidance 成功路径（reportUrl 帧 + 报告链接可打开）待用户执行。
8. 2026-10-15 升级静态验证：`npx tsc --noEmit`（针对 `server/index.ts` + `server/lib/piRunner.ts`）无新增错误（仅存 `charts: checkedCharts` 一处与本改动无关的既有错误，源自工作区未提交的 htmlReport.ts 改动）；帧序与 `docs/openai-stream-upgrade.md` §二 表逐条对照一致。线上抓包回归待跑。

## 2026-10-23 补注：plaza 同步采用消息级分流

[080](080-conversation-source-and-process.md) 将已有消息缓冲定性同步用于 plaza：过程说明经现有 status/thinking/message 进入默认折叠区，text 只承载最终答复；这是用户要求的展示语义调整，替代本记录旧的“plaza 逐字节不变”约定。OpenAI 帧格式与分流行为未改变，真实工具任务回归通过。

## 后续扩展路线

- ~~附件接入~~：已实现（2026-10-13）——`/v1` 接受与 plaza 同规的 `attachments`（`{name, path}`，path 为 /api/upload 相对路径；沙箱防穿越/5 个上限/md-txt 内联在共享核心，入口只做透传）。
- 会话复用优化：对方稳定后建议用返回的 sessionId 续聊，避免每轮重注入历史。
- `reasonContent` 的 plaza 侧展示（008 预留的折叠区路线）如需要，消费同一 thinking_delta 事件即可。
- 按请求选模型：`model` 字段已预留（当前忽略不校验），需要时透传 createSession 的 `--model` 并配白名单。
