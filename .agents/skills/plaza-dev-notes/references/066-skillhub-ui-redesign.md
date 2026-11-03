# 066 · 在线对话/在线运行前端按 SkillHub 设计系统重构

**状态**：已实现（构建通过；无头浏览器双页双主题截图核对与一次真实 SSE 会话完成；真实长报告会话回归待用户执行）。
**适用范围**：`web/src/styles/tokens.css`、`web/src/styles/styles.css`（exp/use/md-body/hist 段）、`web/src/pages/ExperiencePage.vue`、`web/src/pages/UsePage.vue`、`web/src/components/ToolCallGroup.vue`（新增）、`MarkdownView.vue`、`UseHistoryList.vue`、`ReportOutput.vue`、`web/src/App.vue`（图标 sprite）。

## 动机

在线对话（`/experience`）与在线运行（`/use/:slug?`）两页此前是项目早期的第一批页面样式：用户/AI 消息都是"卡片墙"（黑底用户气泡 + 描边 AI 卡）、进度时间线是固定高度小框、运行页对话模式历史栏横在顶部。用户指定用本机 `~/.zcode/skills/skillhub-ui-design`（提取自 skillhub.cn 的设计系统 skill）整体重构这两页，要求按其规范执行而非保留旧结构。

## 约定细节

### 令牌层（tokens.css）

- 新增 `--sk-*` 前缀的 SkillHub 语义变量块（tokens.css:89-131 浅色 / 暗色覆盖在 dark 段末尾）：iOS 蓝 `--sk-blue: #007aff`（暗色 `#0a84ff`）只做点缀（链接/进行中/焦点环/选中）、系统色 green/red/orange/purple（状态与行内代码）、文字四级黑透明度 `--sk-ink-1..4`、表面色（`--sk-sidebar` #f2f2f7e6、`--sk-bubble` #f2f2f7、`--sk-toolgroup` #f9f9f9）、iOS 分段控件选中块 `--sk-seg-on`、墨色胶囊按钮 `--sk-btn/-hover/-disabled/-on`（暗色黑白反转）、标准/弹簧缓动 `--sk-ease/--sk-spring`、负字距 `--sk-track-*`。
- 既有 `--surface-*/--ink-*/--cat-*` 等全站令牌不动；其它页面零影响。暗色仍走 `html[data-mode="dark"]` 整体翻转，两页新样式全部引用 `--sk-*`，暗色自动配套。

### 布局与组件

- **在线对话（ExperiencePage）**：文档流式对话——260px `--sk-sidebar` 侧栏（黑胶囊"新建对话"、会话按今天/昨天/更早分组 `groupedConversations`、36px 行选中 `--sk-fill`）+ 768px 主列。用户消息右对齐 `#f2f2f7` 气泡（18px/右下 6px 圆角）；AI 消息=分类色小方块头像 + 名字/徽章/蓝点状态行 + **MarkdownView 渲染**（替换原 `pre` 裸文本，接入点 ExperiencePage.vue 模板 `.exp-msg-ai`）。输入区=20px 圆角白卡 + focus 蓝 3px 光环 + 32px 黑色圆形发送钮（arrow-up 图标），下缀"内容由 AI 生成，请仔细核对"。打字机/SSE 逻辑未动。
- **工具调用组（新组件 ToolCallGroup.vue）**：取代 UsePage 中重复两份的 `.use-progress-timeline`（表单结果区 + 对话流）。组头=扳手图标+「运行进度」+进行中 n/m（蓝 loader）/完成摘要「✓ 已完成 N 步 · 共 X.Xs，点击查看」；行=phase 图标（thinking=sparkles/tool=terminal/writing=file/system=note）+安全文案标题+detail+耗时（tabular-nums）。**正文首字到达自动折叠**（`proseStarted`，UsePage `text` 事件置 true，`beginRun()` 重置），点组头可重展开；展开态自动贴底。安全边界延续 030：只显示映射后的工具文案，参数/SQL/路径不进 DOM。
- **在线运行（UsePage）**：模式切换改 iOS 分段控件（`--sk-fill` 轨 + `--sk-seg-on` 选中块）；表单节=16px 圆角白卡；选项 chip 选中态从黑底反转为 **iOS 蓝**（蓝描边+蓝 8% 底+3px 光环）；输入/select focus 蓝 3px 光环。对话模式从"顶部历史横条"改为 **260px 历史侧栏 + 右侧聊天列**（≤1080px 侧栏转上方普通块）。运行卡主按钮=`--sk-btn` 黑胶囊（不再用全局 `.btn-primary`）；侧栏静态卡用新 `.use-side-card`（不复用带 24px hover 上浮的全局 `.card`）。
- **MarkdownView/ReportOutput**：`.md-body` 整体重写为 skill markdown-body 规范（标题负字距、blockquote 蓝左线+蓝 4% 底、行内码 iOS 紫、代码块 4% 黑底、表格 max-content 横滚、流式光标改 7px 圆角方块 `sk-caret`）；MarkdownView 增加 `streaming` prop 承接光标类；报告卡 `report-ready` 改蓝框浅底行 + 黑胶囊下载按钮（download 图标）。
- **UseHistoryList**：徽章脱离 runs 页的 `.runs-outcome`，改自有 `.use-hist-outcome`（is-success/timeout/error/aborted/historical）。
- **图标**：App.vue sprite 增补 lucide（ISC，取自 skill `assets/icons/`）：`plus/msg/arrow-up/terminal/wrench/download/file/refresh/x/loader/sparkles`。

### CSS 归位与死样式清理（styles.css）

- 被 RunList/RunDetail 反向依赖的 `.crumb-back`/`.use-eyebrow` 定义从 use 段**迁至 runs 段**（runs 段 1574-1580 附近），runs 两页视觉不变；UsePage 改用新类 `.use-back`/`.use-kicker`。
- 删除无消费者/被替换的死样式：`.engine-switch`/`.engine-btn`、`.use-history-input`、`.use-caret`/`use-caret-blink`、`.use-loading`、旧 keyframes（use-pulse/use-live-pulse/use-spin/exp-dot/exp-caret/exp-menu-in）。
- 共享 keyframes 统一为 `sk-rise/sk-pulse/sk-spin/sk-menu-in/sk-caret`（定义在 exp 段末，两页共用）。

## 成本与取舍

- **不引入 skill 的 Plus Jakarta Sans/Outfit webfont**（Google Fonts 国内不可达），沿用系统字体栈；负字距与字重纪律照做。视觉差异主要在拉丁字符，中文正文无感。
- **不做 skill 的缓冲区+cps 限速+逐字淡入播放器**：保留现有打字机（体验页演示）与 SSE 直渲+50ms 批渲染（014）约定，本次纯视觉重构不动流式管线。
- **不做 HITL 交互卡**：后端无 `request_hitl` 事件，纯前端无意义；skill 方案已记录，待协议扩展。
- 选项 chip 保留横排胶囊（非 skill 表单的整行选项），避免字段众多的任务表单被拉到过长；选中态语言与 skill 一致（蓝）。
- ReportChart 仍与 RunDetail 共用且色值硬编码在组件 JS，本次仅 scoped 统一容器圆角；ECharts 主题化留待后续。

## 后续扩展路线

- 全局导航/页脚玻璃化（glass-nav）与其它页面（runs/首页/广场）套用 `--sk-*` 令牌，可按本次模式分页推进。
- 若后端增加 `request_hitl` SSE 事件，按 skill chat-page.md 的 HITL 卡规范接入（choice/confirm/input 三型、pending→done 状态机）。
- 体验页可接入与 UsePage 同源的工具调用组（当前体验页仅状态行；后端 `/api/chat` status 事件已含 phase/state，前端未消费）。

## 实测与未完成验收

- `cd web && npm run build`（vue-tsc --noEmit + vite build）通过（2026-10-16）。
- 无头 Chrome（CDP 截图，1440×900）核对：体验页空态/真实运行态（浅深）、运行页表单模式/对话模式（浅深）、表单选项蓝选中态、历史侧栏 109 条真实数据渲染、暗色全局翻转（data-mode=dark 确认）。截图存 `/tmp/skillhub-shots/`（临时，未入库）。
- 真实 SSE 端到端一次：对话模式发送「只回复两个字：验收」→ 工具组 4 步完成自动折叠（共 4.8s）→ 正文与 usage 返回 → 历史列表 108→109。完整长报告（career-guidance/tech-forecast）浏览器回归待用户执行。
- 修复项：表单侧栏历史列表缺限高导致整页 15476px（已加 `.use-hist .use-hist-list { max-height: 320px }`，页面回落 3726px）；深色下侧栏登录链接与输入注对比度（改 `--sk-blue`/`--sk-ink-3`）。

## 2026-11-03 · 对话输入区随视口贴底（已实现）

- 4K 视口下，空对话将欢迎区和输入区一起居中，短对话则让输入区紧跟消息。在 3840×2160 的 Chrome 中，两种状态的输入区下方分别空出约 785px、1506px。
- `web/src/styles/styles.css:1026` 中主区最小高度与侧栏高度共用动态视口减去页头及其底边框的值。`:1114` 和 `:1192` 用 flex 自动上外边距分配剩余空间，使欢迎内容在输入区上方居中，短消息列上对齐，输入区始终沉底。长对话沿用文档滚动和 sticky，输入区在文档末尾占据自身高度，无需 fixed 浮层或脚本测量。
- Chrome 浏览器在 3840×2160、2560×1440（DPR 1.5）、1920×1080（DPR 2）、1440×900、390×844 下检查长历史会话。滚动至顶部、中段及末尾时，输入区外缘距视口底边均小于 1 CSS px，末条消息可滚至输入区上方。4K 空会话和短历史没有额外滚动条，模型菜单可展开；390px 宽时调低窗口高度后仍贴底。`cd web && npm run build` 通过。后续调整滚动容器时应复验上述位置；本次窄屏验证采用 Chrome 模拟视口，未覆盖真机软键盘。
