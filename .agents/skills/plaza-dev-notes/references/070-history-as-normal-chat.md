# 070 · 点开历史即正常对话流：删除专门详情卡，支持从历史续聊

- 状态：已实现（2026-10-16。构建通过；无头浏览器验证点开历史=正常消息流（无专门卡片）、侧栏高亮跟随、真实续聊成功（模型能复述恢复会话的第一句话）、报告卡内联且下载路由 200）。
- 动机：用户反馈 069 的历史详情形态仍是过度设计——「历史对话」kicker 标题、meta 信息行、「返回对话」按钮、「智能体产物」专区把历史框成了只读报告卡。期望形态是 ChatGPT/MiniMAX 式：点开历史记录，主区就是这段对话的**正常聊天界面**，能直接继续聊。

## 约定细节

### 历史载入正常消息流

- `selectHistory(group)`（`web/src/pages/ExperiencePage.vue`）把 conversation 轮次转成 `Msg[]` 灌入 `messages`：user → 右气泡，assistant → 左侧 AI 消息（`skill` 对象、`done: true`、`real: true`，报告链接挂最后一条 AI 消息）。载入期间主区只显示一行 `.exp-history-loading`，避免空态示例闪现。
- 删除模板与样式：`.exp-history-view` 卡片全系（kicker/h2/meta/返回按钮/state）、`.exp-history-talk`、`.exp-history-files` 产物区；相应删除 `fmtHistoryTime`/`fmtHistoryDuration`/`hasReportJson`/`runFileUrl` 引用。
- 选中态由 `selectedSessionKey`（clientSessionId）承载，替代按 runId；`loadHistory` 刷新后，当前对话（新建/表单交接/历史恢复）经 `convSessions` 反查自动获得或保持侧栏高亮。

### 从历史续聊（069 路线落地）

- restore 时同时重建运行态：`convSessions.set('pi:'+新convId, run.clientSessionId)`、`convSlugs.set(convId, group.skill)`、`activeSkill` 挂对应技能 chip。用户在恢复的对话里直接发消息即多轮续聊——服务端会话存活时带完整上下文；被空闲回收/重启则走服务端透明重开（旧上下文丢失，不报错），均为既有服务端行为。
- 请求守卫从 per-runId token map 简化为单调 `selectionSeq`：快速切换历史对话时旧请求结果作废。

### 报告链接与 html 模式解耦（ReportOutput）

- `reportUrl` 存在即渲染 `report-ready` 卡（`点击查看具体报告` + `下载报告` → `${reportUrl}/download`），不再要求 `htmlMode` 或正文以 `<!doctype html>` 开头。tech-forecast 等最终回复为短状态文本的技能，报告链接因此可见（069 遗留缺口）。
- html 模式（career-guidance）保持状态行 + 链接同卡；`htmlStatus` 文案「就业指导报告已生成。」泛化为「报告已生成。」。
- report.json 下载入口从 UI 删除（`/api/runs/:id/file/report` 路由保留，开发侧可用）。

## 成本与取舍

- 历史消息带「真实运行」徽章：与实时对话渲染完全同构，是复用而非伪装。（技能操作行「复制安装提示词/查看详情」曾随每条完成的技能回答渲染，2026-10-20 应用户要求移除——多轮对话中每轮重复出现过于打扰；安装入口保留在技能详情页。）
- `historyDetails` 缓存按 latest runId 键控：对话新增一轮后 latest 变化，再次点开自然拉取含新轮次的详情。
- 续聊依赖服务端内存会话；浏览器刷新仍丢当前对话（回列表重新点开）。持久化 sessionId 到 localStorage 仍被否决（会话生命周期耦合，068 已记录）。
- 空 conversation（trace 缺失/损坏）按加载失败处理：toast + 清除选中，不再有降级文案卡。

## 后续扩展路线

- 侧栏对话重命名/删除（RunRecord 不可变，需新增本地或服务端元数据）。
- 长对话在载入时定位到最后一条消息并虚拟滚动。

## 验证（2026-10-16 实测）

- `cd web && npm run build` 通过。
- 无头浏览器：点开「N 条消息」对话 → `.exp-stream` 正常消息流（user 气泡 ×3、AI 消息 ×6），`.exp-history-view/-talk/-files` 均不存在，侧栏对应条目高亮；真实续聊（在恢复的通用智能体对话中发「请只回答我第一句话是什么？」）回复「你第一句话是：你好」，侧栏计数 3→4 条消息；tech-forecast 对话最后一条 AI 消息内联单个报告卡（打开 + 下载），`/download` 路由返回 200 text/html。截图 40/42/44 核对版式。
