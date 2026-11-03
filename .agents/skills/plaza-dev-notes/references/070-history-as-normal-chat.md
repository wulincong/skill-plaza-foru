# 070 · 点开历史即正常对话流：删除专门详情卡，支持从历史续聊

2026-11-03 展示修订见 [090](090-conversation-resource-sidebar.md)：保留正常消息流与历史续聊，完整产物操作移到可折叠右侧资源栏，原消息下方保留定位入口；本文的旧内联按钮实现已被替代。

- 状态：已实现（2026-10-16。构建通过；无头浏览器验证点开历史=正常消息流（无专门卡片）、侧栏高亮跟随、真实续聊成功（模型能复述恢复会话的第一句话）、报告卡内联且下载路由 200）。
- 动机：用户反馈 069 的历史详情形态仍是过度设计——「历史对话」kicker 标题、meta 信息行、「返回对话」按钮、「智能体产物」专区把历史框成了只读报告卡。期望形态是 ChatGPT/MiniMAX 式：点开历史记录，主区就是这段对话的**正常聊天界面**，能直接继续聊。

## 约定细节

### 历史载入正常消息流

- `selectHistory(group)`（`web/src/pages/ExperiencePage.vue`）把 conversation 轮次转成 `Msg[]` 灌入 `messages`：user → 右气泡，assistant → 左侧 AI 消息（`skill` 对象、`done: true`、`real: true`，报告链接挂最后一条 AI 消息）。载入期间主区只显示一行 `.exp-history-loading`，避免空态示例闪现。
- 删除模板与样式：`.exp-history-view` 卡片全系（kicker/h2/meta/返回按钮/state）、`.exp-history-talk`、`.exp-history-files` 产物区；相应删除 `fmtHistoryTime`/`fmtHistoryDuration`/`hasReportJson`/`runFileUrl` 引用。
- 选中态由 `selectedSessionKey`（clientSessionId）承载，替代按 runId；`loadHistory` 刷新后，当前对话（新建/表单交接/历史恢复）经 `convSessions` 反查自动获得或保持侧栏高亮。

### 从历史续聊（069 路线落地）

- restore 时同时重建运行态：`convSessions.set('pi:'+新convId, run.clientSessionId)`、`convSlugs.set(convId, group.skill)`、`activeSkill` 挂对应技能 chip。用户在恢复的对话里直接发消息即多轮续聊。2026-11-03 起，空闲回收/重启后使用 Pi `--continue` 恢复同工作区持久上下文；历史页面跨引擎进程合并，具体边界与验证见 [089](089-conversation-restart-and-delivery-permissions.md)。旧版“透明重开即丢上下文”的行为已修订。
- 请求守卫从 per-runId token map 简化为单调 `selectionSeq`：快速切换历史对话时旧请求结果作废。

### 报告链接与 html 模式解耦（ReportOutput）

- `reportUrl` 存在即渲染 `report-ready` 卡（`点击查看具体报告` + `下载报告` → `${reportUrl}/download`），不再要求 `htmlMode` 或正文以 `<!doctype html>` 开头。tech-forecast 等最终回复为短状态文本的技能，报告链接因此可见（069 遗留缺口）。
- html 模式（career-guidance）保持状态行 + 链接同卡；`htmlStatus` 文案「就业指导报告已生成。」泛化为「报告已生成。」。
- report.json 下载入口从 UI 删除（`/api/runs/:id/file/report` 路由保留，开发侧可用）。

## 成本与取舍

- 历史消息带「真实运行」徽章：与实时对话渲染完全同构，是复用而非伪装。（技能操作行「复制安装提示词/查看详情」曾随每条完成的技能回答渲染，2026-10-20 应用户要求移除——多轮对话中每轮重复出现过于打扰；安装入口保留在技能详情页。）
- `historyDetails` 缓存按 latest runId 键控：对话新增一轮后 latest 变化，再次点开自然拉取含新轮次的详情。
- 续聊依赖服务端内存会话；空闲对话刷新后从列表重新点开；运行中刷新的恢复约定见下文。持久化 sessionId 到 localStorage 仍被否决（会话生命周期耦合，068 已记录）。
- 空 conversation（trace 缺失/损坏）按加载失败处理：toast + 清除选中，不再有降级文案卡。

## 后续扩展路线

- 侧栏对话重命名/删除（RunRecord 不可变，需新增本地或服务端元数据）。
- 长对话在载入时定位到最后一条消息并虚拟滚动。

## 验证（2026-10-16 实测）

- `cd web && npm run build` 通过。
- 无头浏览器：点开「N 条消息」对话 → `.exp-stream` 正常消息流（user 气泡 ×3、AI 消息 ×6），`.exp-history-view/-talk/-files` 均不存在，侧栏对应条目高亮；真实续聊（在恢复的通用智能体对话中发「请只回答我第一句话是什么？」）回复「你第一句话是：你好」，侧栏计数 3→4 条消息；tech-forecast 对话最后一条 AI 消息内联单个报告卡（打开 + 下载），`/download` 路由返回 200 text/html。截图 40/42/44 核对版式。

## 运行中刷新与手动继续（2026-11-03）

**状态与动机**　已实现。浏览器刷新会关闭 SSE，原先用户既找不到刚提交的任务，也容易重新执行已经写过文件的步骤。现在刷新自动找回这一次提交，用户点击“继续任务”才执行下一轮。

- 浏览器在发请求之前为本轮分配 128 位随机 `requestId`，首轮也提前生成 `sessionId`。标签页的 `sessionStorage` 保存这次请求的原文、技能、模型、表单标题和附件引用，正常终态清除。表单和对话框共用提交路径。离开文档时对当前请求发送 keepalive 中断，刷新后再次核对，覆盖代理仍保持 SSE 的情况。见 `web/src/composables/interruptedTask.ts:5`、`web/src/pages/ExperiencePage.vue:336`、`:374`、`:750`。
- `POST /api/runs/session/:sessionId/interrupt/:requestId` 只会停止标识匹配的运行。Pi 确认中断并完成索引写入前返回 202/settling。索引已存在返回 saved 与会话最新记录，以真实终态决定是否提供按钮。提交从未到达时返回 missing 和稳定的替换请求编号。代理里迟到的旧请求有 60 秒拒收窗口。页面恢复原始输入等待点击，即使连续刷新也不自动发起模型请求。见 `web/server/index.ts:369`、`:1413`、`:1454`、`web/server/lib/piRunner.ts:569`。
- `POST /api/chat` 接受可选 `requestId`、`resumeOf`；仅允许继续同一会话最新的中断运行，服务端核验重复提交。继续沿用同会话工作区、技能和原模型。运行记录的 `resumeSourceId` 指回最初任务，`attachmentFiles` 保留已校验的附件引用；模型收到原任务并被要求先检查文件与工具结果。用户视图只增加“继续任务”。初始化期间尚未向 Pi 投递的原始请求标为 `promptNotSent`，恢复历史时按时间补入，不占用 Pi 原生用户轮次。见 `web/server/index.ts:764`、`:1086`、`:1321`、`web/server/lib/conversation.ts:54`、`:86`、`web/src/pages/ExperiencePage.vue:417`、`:697`、`:1051`。
- 成本与取舍：复用已有文件、Pi 持久上下文和历史索引；刷新中断与手动继续各自保留运行记录。文件可从已保存的位置接着处理，执行到一半的命令可能需要重做。保留模型从实际状态判断的空间，未引入任务队列、命令级断点或自动重放。
- 验证：Chrome 390px + 真实优才，运行中刷新后展示原输入和继续按钮；同会话中断、继续成功各一条。真实 30 秒命令在等待中中断，文件保存了运行时生成的时间戳；下一轮 read 返回了同一值（隔离运行 20261103-172719-2pgz、20261103-172724-if0p）。另用代理故意延迟首次 POST，连续刷新两次，迟到请求返回 409，双击继续只产生一条成功记录。HTTP/SSE 回归覆盖附件、同一轮重复提交、陈旧按钮、首轮 Pi 尚未收到 prompt 和重复核对终态。服务端库、HTTP/SSE、Pi 扩展与对话 composable 合计 56 项回归通过，Vue 类型检查和生产构建通过。
- 后续边界：现有模型之外的逐模型实测、服务进程故障时恢复仍在执行的命令，均未在本次验收覆盖。长任务若需要刷新后持续执行，需单独设计任务所有权与事件重连。
