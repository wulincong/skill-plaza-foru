# 090 · 在线对话悬浮资源管理器（Zero4-UI）

**状态**：已实现（2026-11-03；21 项回归、生产构建与公网浏览器明暗/窄屏交互通过）。

## 动机

用户要求把网页、文件下载从长回答中提取到右侧，常驻且可折叠，使用已安装的 zero4-ui。后续要求悬浮卡片和类似 VS Code 的紧凑文件列表，替代初期全高侧栏与每项大卡片。沿用 088 的网页分享/文件下载两类交付，不引入在线 PDF/图片/表格查看器或资源管理后台。

## 约定与接入点

- `web/src/composables/conversationResources.ts:16` 从当前 messages 的 AI 回答收集已发布 webLinks/downloads，按 kind+URL 去重，保留原消息位置和用户轮次，较新的独立交付先显示。网页与文件各一组，不解析正文、Markdown URL 或工作区路径来猜文件。
- 前端投影字段：`{name,url,kind:'web'|'file',turn,messageIndex}`。仅 UI 派生，不写入后端、不改 SSE 或运行索引。新交付优先；无新交付的旧 reportUrl 适配：HTML 保留原网页/下载路由，doc-translate 仅下载，沿用服务端 attachment。
- `ExperiencePage.vue:79` 计算当前对话资源，`:1134` 渲染 ConversationResources；加载另一段历史时不显示旧列表，新建对话自然清空，恢复历史后从同一组消息重新派生。继续追问不会清空前轮产物。
- `ConversationResources.vue:137`：1200px 起默认展开为 320px 右侧悬浮卡片，距头部/右侧 16px，sticky 随滚动保持可见；圆角、玻璃底与轻阴影，按内容确定高度，上限 480px 或可见视口剩余空间，超出时列表独立滚动。收起为胶囊入口；窄屏仍为右上方入口及 340px 上限浮层，同样自适应高度。这是非模态面板，支持关闭按钮、Esc 和窄屏点外部关闭，无背景锁定或伪造模态语义。
- `ConversationResources.vue:16`：网页/文件两个分类各自可折叠；缩进、文件夹/文件图标和细树线表达层级，是真实交付项的分类，不伪装工作区完整文件系统。`:164` 桌面行高 34px、窄屏 44px，名称单行省略，title 保留完整名称与来源轮次，行右侧始终显示操作图标。网页提供打开/复制分享链接，文件提供下载/复制下载链接；图标有 title 与完整 aria-label，不为网页猜下载路由。
- `ConversationResources.vue:36` 的 reveal 由原消息下方“查看资源”调用，展开面板及分类、定位该轮文件行并聚焦操作。收起返回入口焦点，面板/分类按钮含 aria-expanded/controls；复制反馈为行内勾选与 live status，不再用常驻说明占高度，失败单独提示。HTTP 环境保留 execCommand 回落，HTTPS Clipboard 拒绝时同样回落。
- `ExperiencePage.vue:1016` 与 ReportOutput.vue 将正文/图表和资源操作分开：回复中只放资源数量与定位入口，真实网页/下载按钮集中右侧。消息原文保留，不篡改旧模型已经写出的路径文字；右侧只提供服务端真实链接。
- `styles.css:1169` 为消息入口和窄屏顶部留位提供样式。Zero4-UI 的 iOS 蓝、胶囊入口、16px 卡片与玻璃浮层适配既有 `--sk-*` 语义令牌和 data-mode 明暗主题；不整体替换站点样式，不增加 CDN/字体/图标依赖。规范来源为本机 `~/.codex/skills/zero4-ui` 的 SKILL、design-tokens、chat-page、forms-feedback 及 design-tokens.json。

## 验证

- `node --experimental-strip-types --test web/src/composables/*.test.mjs web/server/lib/conversation.test.mjs`：21 项通过，覆盖资源去重/轮次、追问保留、无产物、新对话、仅服务端链接、旧 PDF/HTML 适配、碎片 SSE 与历史恢复。
- `cd web && npm run build`：Vue 类型检查与 Vite 构建通过；`git diff --check` 通过。
- 公网真实对话页面 1440px/390px 浏览器验证：右栏不挤出横向滚动，页面滚动时保持在头部下，收起、回复入口定位、真实鼠标复制、窄屏展开/关闭、Esc、点击外部、深色模式正常。切换对话不串资源，刷新可恢复，空新对话无侧栏。网页链接及 attachment 地址保持原值。
- 悬浮列表修订实测：2 项资源的桌面面板为 320×191px，行高 34px；窄屏面板 340×228px，行高 44px。分类折叠后回复入口可重新展开并定位；网页与下载链接复制均通过。确定性多资源 SSE 场景覆盖长名称、480px 高度上限及独立滚动。
- CDP 在浏览器请求层拦截 `/api/chat`，用确定性 SSE 验证实时新增交付从 2 项增至 4 项，旧资源保留；请求未到达后端，没有伪造持久运行、调用模型或查询数据库。真实下载按钮对应已有公开 ZIP。
- 初期验收摘要为忽略目录 `web/server/traces/resource-panel-acceptance-20261103.json`；悬浮列表修订摘要为 `resource-explorer-acceptance-20261103.json`，其中引用实际截图路径。没有重跑新的长报告任务。

## 成本与取舍

只增加前端派生列表与一个组件，浏览器不额外逐资源 HEAD/抓大小，不编造格式、体积或生成状态。否决正文与侧栏同时摆两套完整按钮：用轻量入口保留轮次关系。初期高卡片已改为文件行，长名称完整显示让位给紧凑密度，通过 title 和可访问标签补足；操作图标常驻，避免必须悬停才能找到。没有资源不占右栏；面板/分类折叠状态只在当前组件内，切换对话或跨断点恢复相应默认状态，不耦合 localStorage 与会话生命周期。

## 后续扩展路线

仅在资源量增加后考虑组内筛选或显式文件元数据；需由后端提供字段后再显示格式/大小。撤销、过期与权限管理仍按 088 的实际需求另行设计，不在此实现中预建。
