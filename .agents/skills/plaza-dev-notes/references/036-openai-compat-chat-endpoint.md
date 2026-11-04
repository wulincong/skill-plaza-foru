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

## 2026-11-03 · 面向用户的在线运行与 API 指南（已实现）

对外使用方式收敛为在线运行与 API。2026-11-04 起统一说明入口为文档中心的 `#/docs/guide`，原地址 `#/guide` 自动跳转。首页、广场、详情页、离线演示文案和页脚均撤下 Git 安装指引。根目录旧演示指向同一份在线指南，以免维护两套 API 示例。

- `docs/guide.md:11` 起维护当前公网 API 地址和可复制命令。网页位于 14188 端口，调用示例直接使用后端 18767 端口。服务迁移时应同步更新该地址和 `docs/agent-api.md:6`，并从指南复制命令做公网回归。
- `docs/guide.md:15` 通过 `GET /api/skills` 查找专业标识，`general` 单独用于通用问答。示例用 `skill`、`messages` 和 `stream` 提交任务，解释 JSON 正文、SSE 结束条件和可选交付链接。外部客户端自行分配会话号。维护者协议见 `docs/agent-api.md:46`。
- `web/src/data/skills.ts:19` 的展示条目仅含业务资料与运行示例。详情页 `web/src/pages/DetailPage.vue:49` 提供在线运行、API 文档与当前标识。源码仓库可见性由仓库管理员单独管理，页面改动只撤回站点分发入口。
- 验证通过。前端 `npm run build`，旧版 `node --check app.js` 与 `node --check skills.js`。Chrome 以 1366px、390px 检查公网指南、示例复制反馈、FAQ 和页面宽度，并检查首页、广场、8 个详情页及根目录演示的指南与详情。实际执行从指南提取的两条命令，清单返回 8 项，非流式请求 `20261103-180546-s8d0` 成功返回正文。另测同端点流式请求 `20261103-180619-j7v5` 收到正文、stop 和 `[DONE]`。空请求实测 400/`unknown_skill`。本次未复跑附件或报告生成流程。

## 2026-11-03 · 微信机器人接入设计

**状态：设计建议，待实现。** 本节面向相邻项目 `wechat-ai-bot`，本次只记录设计，没有修改机器人或广场运行代码、切换回复模式、重启服务、请求模型、查询岗位库或调用微信发送接口。

### 动机与已核实的边界

把微信机器人定位为公众号消息入口与任务管理层，报告规划、真实取数、分析和生成继续交给广场的 `wechat-report`，避免在机器人复制 Pi 运行器、技能、SQL 或报告流水线。

本次只读核实：

- 本机 `GET http://127.0.0.1:8767/api/health` 返回 `ok:true`、`runner:pi`；`GET /api/skills` 包含 `wechat-report` 且 `installed:true`。这只证明服务在线及技能注册，不代表新的在线长报告已经验收。
- 机器人当前 `REPLY_MODE=passive`；配置中存在客服凭据，但 `CS_ENABLED=false`。没有验证凭据有效性或公众号客服权限，不自动改配置。
- `wechat-ai-bot/wxbot/llm.py:36` 的请求没有 `skill`、`sessionId`，只取 `choices[0].message.content`，会丢失交付数组；其默认请求超时 60 秒。只替换 `LLM_BASE_URL` 无法完成接入。
- `wechat-ai-bot/wxbot/reply_flow.py:83` 客服分支每条消息直接开线程，没有消息去重和用户会话串行；被动分支 `:104` 的去重仅在进程内，累计等待上限 18 秒。报告不能沿用这套等待策略。
- `web/server/index.ts:838` 的 `session()` 只向 plaza 协议发送会话号；OpenAI 响应目前不回传 `sessionId`。客户端可以在首次调用前生成安全的随机会话号并持久保存，服务端接受该值，不必先调用 plaza 接口。
- `web/server/index.ts:1319` 在 SSE 客户端提前断开时停止本次运行；目前没有提交后与连接脱离的持久任务 API。微信回调返回并不影响独立 worker 的连接，但 worker 退出、网络断开可能中止 Agent。
- `wechat-report/SKILL.md:25` 要求审阅实际分析大纲后再渲染；确认超过十五分钟沿用已保存结果。现有 `gen_outline.py:179` 输出 Markdown 和图表 JSON，尚无面向手机的大纲审阅网页；`pack_delivery.py:14` 处理的是最终图片和 ZIP，不能直接视为大纲发布功能。
- 最终交付已有 `webLinks`、`downloads` 和持久托管；微信报告不依赖其他技能的固定 `reportUrl`。工具活动只给出工具名、状态，不给业务阶段。接口文档中的技能枚举及部分注释滞后，合法值以 `/api/skills` 和实现为准。

### 用户交互

入口支持“生成报告”“微信报告”以及“帮我做一份广东低空经济人才需求报告”等完整自然语言；“帮助、进度、结果、我的报告、取消、新建报告”由机器人本地处理。当前没有报告任务时保留已有普通聊天入口；有报告任务时，补充信息和修改意见进入该报告。首期可用文本指令，菜单 CLICK 作为后续入口，不要求用户学习技能名称或参数格式。

对话按以下顺序进行：

1. **说明需求**：收集地区、产业/岗位范围、目标读者与关注问题。地区与主题必须明确；读者未说明可建议“职业院校教师与专业负责人”，时间未说明使用“数据库全时间范围的在招记录”，把建议值一起呈现，不能静默加上“近一年”或 AI 条件。先问关键缺项，品牌、配色、页数等使用默认值；完整需求不再逐项追问。实体歧义由 Agent 通过共享查询 resolve 后让用户选择。
2. **确认范围**：给一段可修改的需求摘要；用户发送“开始分析”。这是开始真实统计和研究的触发点，不能把一条含糊需求直接升级为全量报告。已明确说“按上述范围开始”的输入可直接触发，不重复确认。
3. **后台分析**：微信即时回复任务编号，例如“已受理 Rxxxx，正在准备分析大纲；发送‘进度’可查看”。编号示例不代表真实任务。worker 负责调用 Agent，回调不等待分析完成。
4. **审阅大纲**：微信发送少量已核实的核心发现和审阅链接。网页展示完整分析、真实数字及其口径、图表的可读预览/表格、建议与数据缺口；不把原始图表 JSON 或内部核查表交给普通用户。用户发送“确认大纲”或具体修改意见。
5. **生成报告**：确认绑定当前大纲版本，沿用同一 Agent 会话和已保存数据；生成图文、文章并完成最终校验。单纯改措辞或版式不重新查库；修改地区、产业、时间等数据范围需重新分析，使旧大纲确认失效。
6. **交付与续改**：微信只发简短摘要、在线预览链接及下载包链接，长文和图片在网页查看。后续小改继续原报告，新主题用“新建报告”创建独立任务/会话。草稿箱推送作为单独能力，需用户明确提出并具备对应配置；生成完成不触发草稿推送、发布或群发。

示例流程（所有报告结果及链接均为占位说明，不是本次实测产物）：

```text
用户：帮我做一份山东智能制造人才需求报告，给高职院校老师看。
机器人：范围为山东省、智能制造相关产业、数据库全时间在招记录，
        重点分析地域、学历经验、薪酬与课程启示。回复“开始分析”即可。
用户：开始分析
机器人：已受理 Rxxxx。完成后可发送“进度”或“结果”查看。
机器人：分析大纲已就绪。查看：<平台返回的大纲链接>
        可以直接提出修改，或回复“确认大纲”。
用户：增加面向应届大专毕业生的分析。
机器人：已收到，正在修订大纲；完成后请确认新版本。
用户：确认大纲
机器人：开始生成图文，沿用本次已确认的分析数据。
机器人：报告已生成。在线查看：<webLinks 中的最终链接>
        下载图文与文章包：<downloads 中的链接>
```

上述完成通知仅在客服发送能力可用时主动发送；被动模式下由用户再次发送“进度/结果”取得当前结果，机器人首次受理时必须说明这一点，不能承诺主动送达。未受理前的需求问答若需要 Agent 推理，同样异步保存回答，不能让被动回调等待模型。

### 接入边界与调用方式

```text
微信用户 → 微信服务器 → Flask /wx
                          ├─ 验签、消息去重、命令路由
                          ├─ SQLite：任务、消息、待执行轮次、发送记录
                          └─ 即时回复受理/本地状态
独立 worker → POST /v1/chat/completions → Pi → wechat-report
               持续读取 SSE                    └─ talent-data-query
            → 保存回答/交互状态/公开链接
            → 客服通知；或等待用户发“结果”后被动返回
```

机器人新增独立 `AgentClient`；普通聊天的 `LLMClient` 可以保留。同机使用 `http://127.0.0.1:8767/v1/chat/completions`，不直接启动 Pi，也不通过广场前端端口中转。

以下请求体只使用**当前已支持**字段：

```json
{
  "skill": "wechat-report",
  "sessionId": "wxr-<服务器生成的随机UUID>",
  "stream": true,
  "taskTitle": "山东智能制造人才需求报告",
  "messages": [{"role": "user", "content": "<本轮需求、补充信息或大纲确认>"}]
}
```

会话号由机器人生成，不使用原始 OpenID、不接受用户任意指定路径。`(公众号标识, OpenID)` 关联任务，每个报告有独立 `taskId/sessionId`，每轮记录独立 `runId`；同一报告补充、修订和确认复用 session。不要每条消息重开会话，也不要让一个用户的所有报告永久共用一个 session。续聊通常只发最新 user 消息；完整历史只用于明确的上下文丢失恢复，防止反复注入。当前 OpenAI 入口不会把任意 system 消息作为独立系统策略应用，渠道规则应由服务端受信配置/技能注入。

SSE 适配约定：

- 解析完整 SSE 事件，兼容跨网络块拆分、多行 data、空行边界及 `: ping` 心跳。
- 累积 `choices[*].delta.content` 作为面向用户的最终回答；`reasoning_content` 不发送到微信。
- `choices:[]` 也要解析，保存顶层 `webLinks/downloads/reportUrl/runId/resultType/usage`。不能假设每帧都有 `choices[0]`。
- `finish_reason:stop` 后仍有交付和用量帧，必须继续读到 `[DONE]`；`error` 帧优先于内容/链接。`resultType:timeout` 即使有产物也标为超时后保留的阶段成果，不标完整成功。
- 无交付轮次目前不单独发送 runId 扩展帧，可从首帧 `id=chatcmpl-<runId>` 的已知协议规则记录本轮标识；未来宜统一显式回传 runId。没有最终报告链接的补充问答或大纲轮次不等于失败，也不等于报告完成。
- worker 可采用连接超时 5 秒、读空闲超时 60 秒，利用服务端 15 秒心跳维持长连接；总期限应参考实际 `RUN_TIMEOUT_MS` 并留收尾余量。已安装技能当前默认每轮 20 分钟，不是整个报告固定耗时承诺。
- 进度只显示真实任务状态、已运行时长和确定发生的事件。现有工具名不能可靠推断“取数完成/分析百分比”，不发送虚构百分比或连续工具消息。

### 建议补齐的最小服务协议（均待实现）

仅透传自然语言可以做人工联调，但稳定任务状态不应靠匹配“请确认”“已完成”等句子。建议在现有 OpenAI 端点增加**可选的微信报告工作流配置和终态交互字段**，不新增通用聊天协议、不改其他客户端默认行为：

```json
{
  "channel": "wechat",
  "reportAction": "message",
  "outlineVersion": null
}
```

这是请求新增字段示意，须与现有 `skill/sessionId/messages` 一起发送；当前服务未实现，发送它们不能视为生效。大纲确认使用 `reportAction:"confirm_outline"` 并带已展示的 `outlineVersion`。

终态扩展示意：

```json
{
  "choices": [],
  "runId": "<本轮运行标识>",
  "interaction": {
    "schema": "wechat-report-interaction/1",
    "type": "review_outline",
    "summary": "<面向微信用户的简短说明>",
    "missingFields": [],
    "outlineVersion": "<当前大纲内容指纹>",
    "artifactKind": "outline"
  },
  "webLinks": [{"name": "分析大纲", "url": "<平台实际发布的URL>"}]
}
```

`type` 建议枚举 `ask / review_outline / completed / no_data`，`artifactKind` 为 `outline / final / null`；运行失败、超时继续沿用现有错误/超时协议。`ask` 表示本轮结束但业务在等补充；`review_outline` 在等审阅；`no_data` 结束当前分析并说明缺口；只有最终数据/渲染校验通过且最终交付确已发布，才可使用 `completed`。已有大纲网页链接本身不能触发 completed。

建议接入点：`handleOpenAiChat` 解析并校验可选渠道/动作；`TurnParams` 与受信 prompt 传递本轮工作流；报告脚本产出经 schema 校验的轮次交互侧车；`runChatTurn` 结合当轮数据指纹、文件变更、阶段校验及发布结果核实语义；`WireDonePayload/createChatWire` 发送统一扩展帧。侧车必须绑定本轮 run/action 和大纲指纹、原子替换并拒绝旧文件；不能把模型自报状态直接当成真实产物校验。

大纲审阅建议补一个独立导出入口，将已校验的 `report_outline.json` 转成公开 HTML，图表用相同绑定数据绘制可读图/表，不展示 JSON；通过现有 `delivery.json` 托管，返回实际链接。大纲目录与最终 site 分开，旧链接保留原版本；确认绑定已展示指纹，旧确认不能应用到新大纲。确认动作应在**执行渲染前**检查状态和指纹；强约束放在渲染/工作流入口校验，单靠 prompt 不保证不会提前渲染。现有技能要求审阅是行为约定，尚无这套机器门禁。

### 本地任务状态、并发与恢复

业务状态建议：

```text
collecting → ready_to_analyze → analyzing → waiting_outline_confirmation
                                           ↑             │
                                           └─ 修改意见 ──┤
                                                         └─ 确认当前版本 → rendering → completed
活动状态还可转入 failed / interrupted / cancelled；空样本进入 no_data。
```

轮次队列单独记录 `queued/running/succeeded/failed/interrupted`，不能把“本轮 Agent 成功结束”直接映射成“整份报告已完成”。`ready_to_analyze` 是需求范围已清楚但尚未启动真实统计；大纲修订属于新的分析轮次。新数据范围使旧分析与确认失效；仅调整表达/版式优先复用保存数据。

SQLite 首期足够，复用现有依赖而不引入 Redis/Celery：

| 记录 | 关键字段/约束 |
| --- | --- |
| `inbound_messages` | `account_id, msg_id` 唯一，OpenID、原始内容、处理结果及缓存回复；菜单等无 MsgId 事件另定基于账号/事件/时间的去重键 |
| `report_tasks` | `task_id, account_id, openid, session_id, business_state, brief_json, outline_version, confirmed_outline_version, latest_run_id, web_links, downloads, error, created_at, updated_at` |
| `agent_turns` | `turn_id, task_id, inbound_key, action, state, run_id, lease_owner, lease_expires_at, answer, interaction, error`；输入幂等键唯一，事务领取及租约防重复 worker 执行 |
| `outbox` | `task_id, turn_id, notice_type` 唯一，内容、发送状态、错误码、重试时间，保证已生成结果先落库再尝试送达 |

回调在同一短事务内完成消息去重、状态检查、任务/轮次入队与缓存即时应答。目标在一秒内返回，超载/入库失败要诚实回复未受理。微信重试相同 MsgId 返回同一受理结果，不重复开任务；不同 MsgId 的重复“确认大纲”也要通过状态与 outlineVersion 的原子检查只入队一次。

每个用户首期最多一个活动报告执行轮次，同一 session 只由一个 worker 调用；全局初始并发 1，排队时明确提示。工作流等待用户回复时释放 worker。报告运行期间，“进度/结果/取消”本地处理，其他补充持久排队并说明将在当前轮次结束后处理；不并发往占用 session 发请求。实质改变范围的输入不能套用旧大纲确认。`新建报告` 在原任务运行时先作为待处理操作，除非用户明确取消原任务，不静默终止。

取消排队轮次可直接落 cancelled；取消正在执行的轮次由所属 worker 关闭其请求连接，利用现有断连停止行为，记录阶段产物。当前没有独立 cancel API，worker 必须轮询本地取消标志或可被唤醒，不能只改数据库状态。重置普通聊天不删除报告、交付或冒充已取消；需清理当前报告时路由为显式取消/结束。

机器人或广场重启后，保留 SQLite、广场 workspace、Pi 持久会话、traces 与 deliveries。过期执行租约先标 interrupted，利用已知 runId 查运行记录核实是否已有结果；记录缺失不证明任务仍在执行。SSE POST 无服务端幂等保证，不能因网络异常自动重发“生成报告”。有阶段成果可重新交付；需要继续时由明确的恢复动作复用原会话/文件，不默认重新查库。仅聊天历史仍在不保证工作文件和数据也在。

### 微信送达与链接

- 当前 passive 保留为完整可用模式：回调即时 XML 回复受理/本地状态，后台保存结果，用户发“进度/结果”获取。不要通过故意拖过回调时限争取报告执行时间。
- 客服模式在权限与凭据真实验证后启用。可用被动回复作受理回执，后续只在需补充、待审阅、完成/失败等关键点发送；同一事件避免既被动回复又发重复客服消息。消息条数、窗口和实际错误码以公众号能力为准，本次未核实微信官方最新额度，不将“配置齐全”等同于可发送。
- 客服失败不丢弃结果。越窗/无权限回落到用户主动查询；暂时失败按错误类型重试。网络超时可能已送达，不宣称通知严格 exactly-once；不明确的发送记为未知，避免无限重发。每条回复保持短文本，长度按渠道字节上限处理，长内容移至网页，不能直接塞完整报告。
- 结果链接只采用平台返回的 `webLinks/downloads`，不从回复正文提取磁盘路径或拼造交付 URL。设置可由手机访问的 `DELIVERY_PUBLIC_BASE_URL`，确认公网反代 `/p/` 和 `/api/deliveries/`；微信服务端走 localhost 不意味着手机能打开 localhost。移动端 ZIP 下载行为需真机验收，必要时给“在浏览器打开”提示。
- 现有链接为持链接可访问，不是用户鉴权。公众报告可沿用该能力；内部 SQL、核查表和原始上传材料不放入公开清单。首期按同机服务端调用，不额外开放当前无鉴权的 Agent 管理/执行接口到公众号用户。

### 实施范围、验证及取舍

机器人建议新增 `wxbot/agent_client.py`（SSE/交付字段）、`report_flow.py`（命令与业务状态）、`task_store.py`（持久记录）、`worker.py`（执行/取消/恢复）、`notifier.py`（短文本/发送记录）；`reply_flow.py` 负责分流，`app.py` 保留微信验签与 XML 边界，`config.py` 增加 Agent 地址、超时与并发配置。普通聊天记录与报告任务生命周期分开。

优先顺序：先完成被动模式的持久入队、状态查询和 worker/AgentClient；再补结构化交互、大纲公开审阅与确认门禁，打通完整两阶段报告；最后真实验证客服通知。前两步共同构成首期完整交付，不能把只拿到 Agent 文本或只生成大纲称为接入完成。后续再按需求增加菜单、图片素材、草稿推送和更多 skill，不在本轮引入通用多智能体编排。

必要验收：重复微信投递/确认只执行一次、连续输入串行、两个用户隔离、跨消息读取交付扩展且不在 stop 提前断开、超时有产物仍正确标注、旧大纲确认被拒、分析校验失败不渲染、客服失败可查结果、取消确实停止、重启不盲目重跑、手机可打开大纲/最终页与取得下载包。确定性传输先验证协议，再用小范围真实数据完成“需求→大纲→修改→确认→最终交付”；不以既有离线报告替代在线验收。

本次验证仅包含源码/手记核对、运行配置布尔状态和两个只读健康/技能接口；上述新增字段、队列、审阅网页、门禁、恢复与通知均未实现或实测。微信官方文档抓取未取得有效正文，因此本次不作最新客服额度/权限承诺。

取舍：首期复用现有对外端点、报告技能和交付托管，成本是机器人仍需独立 worker 持有 SSE 连接，崩溃不能无缝续接正在执行的请求。否决仅改 LLM 地址（缺字段和生命周期）、依赖微信回调重试跑长任务（等待窗口不适配）、透传全部思考/工具事件（不可读且消耗通知额度）、大纲和最终产物混为完成状态（会提前结束业务）、机器人直读广场磁盘（耦合部署与权限）、首期另造通用异步 Agent 平台（超出当前单技能需求）。后续若需要无人值守的长任务容错，再为广场设计服务端持久任务、幂等提交、状态查询与断线重连；不能把这项后续能力描述为当前已有。
