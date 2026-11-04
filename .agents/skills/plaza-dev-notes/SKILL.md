---
name: plaza-dev-notes
description: 技能广场仓库（skill-plaza-foru）的开发手记，沉淀本仓库后端 runner、报告输出协议、结构化侧车、广场技能接入等开发约定与设计决策。在本仓库修改 web/server、SSE 协议、报告解析或新增技能/引擎前先读对应记录；产生新的设计决策后按「记录规则」追加条目。
---

# 技能广场开发手记

本技能是本仓库的**活记录本**，供开发会话（zcode / pi 在本仓库工作时）使用，记录"为什么这么设计、接在哪、后续怎么扩"。代码本身能说明的不重复记。

**边界**：这是开发用内部技能——不进 `web/server/lib/skills.ts` 智能体列表、不进 `INSTALLED_SKILLS`、不在广场前端任何接入点出现；2026-10-19 起广场沙箱 pi 以 `--no-context-files` 关闭 AGENTS.md 链发现并显式注入沙箱说明，仓库根 AGENTS.md 与本技能不再进入运行上下文（见 075）。面向广场用户的技能接入走 skills.ts 等四个接入点，与本技能无关。

## 何时读

- 改动 `web/server/lib/`（runner / piRunner / zcodeRunner / reportParse / skills / traceExport）或 `/api/chat` SSE 协议前
- 设计报告输出、结构化协议、图表方案前
- 接入新技能或新引擎前

先读下面索引中与任务相关的记录，再动手。索引按主题分区，编号保留重组前原号（含空洞，见 076）。

## 何时写

相关任务结束前检查是否满足任一条件：形成新的设计决策、修改既有约定、实现记录中的后续路线，或发现会影响后续开发的重要事实。满足时必须在同一变更中更新对应记录，或新增下一编号的记录并更新本索引；只做与手记无关的局部修复且没有新的可复用约定时，可以不新增记录。

实现落地后回填实际 `file:line`、验证命令/结果和仍未完成的验收项。无法实测的内容标为“待验证”，不要把计划或静态检查写成已完成。

## 记录规则（后续内容按此持续追加）

- 一条记录一个主题：正文放 `references/<三位编号>-<slug>.md`，并在下方索引对应分区加一行。
- 记录必含五要素：**状态**（设计中 / 已实现 / 已废弃）、**动机**、**约定细节**（schema、字段、接入点 file:line）、**成本与取舍**（含被否决的备选方案及理由）、**后续扩展路线**。
- **运行观察不入册**：单次会话的运行过程、产物细节（字节/图表清单/耗时分布）不作为独立记录；观察中发现的持久事实（工具坑、口径结论、schema 影响）以补注并入所属约定记录。运行产物以 traces/events 与报告文件为准（2026-10-19 重组确立，见 076）。
- 设计定稿但未实现时标"设计定稿，待实现"；实现落地后**回填**实际 file:line 与实测数据，状态改"已实现"。
- 状态变化优先更新原记录；被推翻的决策标"已废弃"并注明替代者。
- 编号只增不改且**禁止重号**（下一号为 105；093/094 已被 2026-11-03 回退的两条记录占用过，勿复用）；同主题小记录可并入更早编号的记录并更新 slug，被并文件删除并在 076 的映射表登记。

## 记录索引

### 运行链路与开放接口

| # | 主题 | 状态 | 文件 |
|---|---|---|---|
| 008 | 流式体验：status 过程事件、首包/等待计时、会话失效自愈、zcode 错误上抛、渲染批处理（原 014 并入） | 已实现（浏览器端人工验收待用户） | [008-streaming-status-and-session-selfheal.md](references/008-streaming-status-and-session-selfheal.md) |
| 026 | Pi 每次模型请求的上下文占用记录 | 已实现（真实 Pi/API 端到端回归待用户执行） | [026-pi-context-usage-per-request.md](references/026-pi-context-usage-per-request.md) |
| 027 | Pi-only 执行链与就业报告固定用户结构 | 已实现（真实报告回归待用户执行） | [027-pi-only-user-report-structure.md](references/027-pi-only-user-report-structure.md) |
| 030 | 在线运行安全进度时间线：只登记真实工具调用，工具参数/SQL/路径不进前端 DOM | 已实现（066 起以 ToolCallGroup 工具组形态呈现） | [030-stream-progress-timeline.md](references/030-stream-progress-timeline.md) |
| 035 | Pi 通用模型选择与计费来源（全局 Skill，防误走第三方计费） | 已实现 Skill，项目运行时接入待实现 | [035-pi-model-selection-and-billing-source.md](references/035-pi-model-selection-and-billing-source.md) |
| 082 | 在线模型切换（DeepSeek Flash / Pro、优才之路产教融合大模型） | 已实现（弹出菜单、浏览器跨型号续聊与历史恢复通过） | [082-youcai-model-provider.md](references/082-youcai-model-provider.md) |
| 036 | OpenAI 兼容端点 /v1/chat/completions：外部项目统一接入入口 | 接口与在线运行/API 公开指南已验证；微信机器人两阶段报告接入待实现 | [036-openai-compat-chat-endpoint.md](references/036-openai-compat-chat-endpoint.md) |
| 075 | 沙箱 pi 上下文隔离：--no-context-files 断链 + 沙箱说明显式注入 + 工程边界节 | 已实现（重启后探针会话验证） | [075-sandbox-context-isolation.md](references/075-sandbox-context-isolation.md) |
| 077 | 运行详情页统一时间线（Pi trace 单列；原 012 迁号） | 已实现 | [077-run-detail-timeline.md](references/077-run-detail-timeline.md) |
| 078 | pi 沙箱第一层：低权系统用户运行（写权限限 workspace；PI_SANDBOX_USER + setup-pi-sandbox.sh） | 已实现（探针会话验证；kill 链与技能全链路待观察） | [078-pi-sandbox-user-isolation.md](references/078-pi-sandbox-user-isolation.md) |
| 088 | 产物交付：网页分享与资源下载，轻量双通道 | 已实现（双通道/97项回归/公网网页与下载通过） | [088-artifact-presentation-and-web-hosting.md](references/088-artifact-presentation-and-web-hosting.md) |
| 089 | 服务重启后的对话恢复与低权产物交接 | 已实现（公网历史/下载恢复、低权打包与Pi持久恢复验证通过） | [089-conversation-restart-and-delivery-permissions.md](references/089-conversation-restart-and-delivery-permissions.md) |
| 079 | doc-translate：PDF 翻译/交付、专用表单、附件会话绑定、真实失败呈现与工件更新校验 | 已实现（真实浏览器全链路/低权 XeLaTeX/下载/历史恢复/21 项回归通过；长文档待验证） | [079-doc-translate-skill.md](references/079-doc-translate-skill.md) |
| 081 | doc-translate 原图保留：位图素材清单、原 PDF 矢量裁切引用、图注翻译 | 已实现（4 项素材回归/构建/真实 Pi 图文翻译与下载通过） | [081-doc-translate-original-figures.md](references/081-doc-translate-original-figures.md) |
| 083 | wechat-report：公众号报告技能安装、Linux 工具链与无表单对话入口 | 安装已实现（11-02 审查复现数据范围/质检/渲染/交付缺陷，待修） | [083-wechat-report-skill.md](references/083-wechat-report-skill.md) |

| 096 | 公众号报告直接图片交付、统一选图与渲染质检 | 首轮已实现；用户指出分析与图型不足，新规范见099 | [096-wechat-images-direct-delivery.md](references/096-wechat-images-direct-delivery.md) |
| 097 | 已验证报告成品库、公众号自然消息与草稿确认桥 | 已实现（真实草稿受IP白名单限制） | [097-report-library-and-wechat-drafts.md](references/097-report-library-and-wechat-drafts.md) |
| 099 | 多维图片报告、总分总论证与官方参考资料 | 代码与真实Pi构建已验证；文案持续加强、用户待验收 | [099-multivariate-report-evidence-and-references.md](references/099-multivariate-report-evidence-and-references.md) |
| 100 | 受信报告入口、Pi短批次工具、修订与完成判定 | Pi生成/修订与双入口复验通过；真实草稿受限 | [100-native-report-writing-and-trusted-runtime.md](references/100-native-report-writing-and-trusted-runtime.md) |
| 102 | 数据约束的结构分析、短批次原生工具与适用图型 | 九范围真实Pi构建通过；用户待验收 | [102-report-structural-reasoning.md](references/102-report-structural-reasoning.md) |
| 103 | 新版成品缓存、自然确认与草稿真实失败 | 端到端已验证；真实草稿受白名单限制 | [103-report-cache-version-and-draft-failure.md](references/103-report-cache-version-and-draft-failure.md) |

### 报告输出协议（就业指导）

| # | 主题 | 状态 | 文件 |
|---|---|---|---|
| 001 | report-meta 侧车：校验字段与用户内容双轨输出 | 已实现（端到端验收待跑） | [001-report-meta-sidecar.md](references/001-report-meta-sidecar.md) |
| 006 | 用户正文边界与开发侧 evidence 字段（原 006+007） | 已实现（真实会话回归待跑） | [006-career-guidance-user-boundary-and-evidence.md](references/006-career-guidance-user-boundary-and-evidence.md) |
| 010 | 数据图表：report-meta/2.charts 结构化规格、服务端校验与前端 ECharts 渲染 | 已实现（前端组件与真实会话待回归） | [010-career-guidance-charts.md](references/010-career-guidance-charts.md) |
| 013 | 正式报告：岗位需求分析与简历修改建议（marketAnalysis/resumeReview 侧车） | 已实现（真实查询与浏览器回归待跑） | [013-career-guidance-formal-report.md](references/013-career-guidance-formal-report.md) |
| 015 | HTML 报告文件产物：workspace/report.html 协议、服务端校验、failureHint 文案坑 | 已实现（真实超时恢复与浏览器回归待验证） | [015-career-guidance-html-report.md](references/015-career-guidance-html-report.md) |
| 018 | 比例展示与来源文案口径（比例优先、来源统一表述、小样本提示） | 已实现（真实报告待回归） | [018-career-proportion-source-display.md](references/018-career-proportion-source-display.md) |
| 028 | 在线报告下载（?download=1）与结构化任务标题 taskTitle | 已实现（真实浏览器下载与历史运行回归待验证） | [028-online-report-download-and-task-title.md](references/028-online-report-download-and-task-title.md) |

### 岗位库与查询链路

| # | 主题 | 状态 | 文件 |
|---|---|---|---|
| 009 | MySQL 只读查询工具：scripts/mysql-query.mjs + 沙箱 AGENTS.md 声明 | 已实现（CLI 与 pi 端到端验收通过） | [009-mysql-query-tool.md](references/009-mysql-query-tool.md) |
| 012 | career-market-query 白名单查询侧车（六类查询、谓词语义） | 已实现（真实内网岗位库回归待跑） | [012-career-market-query-sidecar.md](references/012-career-market-query-sidecar.md) |
| 016 | 查询客户端执行：native_password 回落、批次预探测、受控并行（原 016+020） | 已实现（2026-09-28 实测通过） | [016-career-query-client-execution.md](references/016-career-query-client-execution.md) |
| 017 | 索引与检索实测：EXPLAIN 与 FULLTEXT 试验（原 017+018+019） | 实测完成，结论长期有效 | [017-career-query-index-experiments.md](references/017-career-query-index-experiments.md) |
| 084 | 通用人才数据分析：真实库能力、地域/产业/专业/岗位语义筛选与证据绑定 | 设计中（真实库连通/表结构/有限专业映射已验证，协议与改造未实现） | [084-general-talent-analysis-skill-design.md](references/084-general-talent-analysis-skill-design.md) |
| 085 | 共享人才数据库查询 Skill：取数协议、缓存与离线产业链岗位目录 | 共享查询已实现；目录与真实库逐节点对账，离线双向检索通过 | [085-shared-talent-data-query-skill-design.md](references/085-shared-talent-data-query-skill-design.md) |
| 086 | 人才统计查询优化：按需质量字段、产业候选优先、四组计数合并与真实基准 | 已实现（39 项测试、20+5 请求与20项同快照核验通过；源库索引待评估） | [086-talent-statistics-query-optimization.md](references/086-talent-statistics-query-optimization.md) |
| 087 | 报告智能体接入共享人才查询：按章节请求、兼容适配、证据绑定与迁移验收 | 接入已实现；同口径改标题触发重复取数已核实，修订复用待优化；分析阶段见091 | [087-report-query-skill-integration.md](references/087-report-query-skill-integration.md) |
| 098 | 城市薪酬与学历结构同口径联合统计 | 取数、单城预检与可选职教池一致性已验证 | [098-city-salary-multivariate-data.md](references/098-city-salary-multivariate-data.md) |
| 091 | wechat-report：强制真实数据分析、比较证据、解释与行动建议后再生成报告 | 已实现（63项测试/真实保存结果全链路；在线模型新会话待验） | [091-wechat-evidence-led-analysis.md](references/091-wechat-evidence-led-analysis.md) |

### 图表与区域资源

| # | 主题 | 状态 | 文件 |
|---|---|---|---|
| 021 | 独立科研图稿与报告图表（全国分省地图、分组与分面趋势、多面板矢量导出、城市热点图） | 已实现（独立数据、几何与排版复验、报告兼容通过） | [021-shared-chart-visualization-skill.md](references/021-shared-chart-visualization-skill.md) |
| 023 | 城市热点图与 34 个省级行政区的下级边界（白名单查询、资源注册与图鉴） | 已实现（498 个单元离线验收，原广东、浙江报告验证） | [023-city-heatmap-region-resources.md](references/023-city-heatmap-region-resources.md) |

### tech-forecast 技能

| # | 主题 | 状态 | 文件 |
|---|---|---|---|
| 038 | tech-forecast：契约泛化、四级证据链、投标规格七章、库内快照层、检索降级兜底（原 036+038+040+041） | 已实现（2026-10-12~16 多轮真实运行校验通过） | [038-tech-forecast-skill-and-evidence.md](references/038-tech-forecast-skill-and-evidence.md) |
| 043 | 纺织服装快照（含公开来源节）与 web-search 检索源修复 | 已实现（guangdong-textile.md 交付审阅） | [043-textile-snapshot-and-search-fallback.md](references/043-textile-snapshot-and-search-fallback.md) |

### DeepResearch 设计（未实现）

| # | 主题 | 状态 | 文件 |
|---|---|---|---|
| 029 | 多智能体编排设计：拓扑/协议/两层资料/上下文预算与交接/拆分与冲突控制（原 029+030+031+033） | 设计定稿，待实现 | [029-deep-research-design.md](references/029-deep-research-design.md) |
| 032 | 外部研究输入：Anthropic 工作流原语与论文启发（原 032+034） | 研究输入已整理，待长任务验证 | [032-deep-research-external-inputs.md](references/032-deep-research-external-inputs.md) |

### 前端交互与历史会话

| # | 主题 | 状态 | 文件 |
|---|---|---|---|
| 095 | 在线对话人工决策卡：双向确认、单选、多选、自由输入与原会话续答 | 已实现（优才四种类型、Flash/Pro 单选、窄屏 Chrome、历史与并发提交通过） | [095-chat-human-decisions.md](references/095-chat-human-decisions.md) |
| 090 | 在线对话悬浮资源管理器：Zero4-UI、紧凑文件行、分类折叠及行内操作 | 已实现（21项回归/构建/公网明暗及窄屏交互通过） | [090-conversation-resource-sidebar.md](references/090-conversation-resource-sidebar.md) |
| 080 | 原始用户输入快照、历史提示词剥离、每轮最终回答与默认折叠执行过程 | 已实现（28 项回归/构建/真实 Pi 与 OpenAI/浏览器通过） | [080-conversation-source-and-process.md](references/080-conversation-source-and-process.md) |
| 022 | 就业指导开发侧测试模板切换 | 已实现（构建与浏览器交互已验证） | [022-career-test-template-switcher.md](references/022-career-test-template-switcher.md) |
| 066 | 在线对话/在线运行前端按 SkillHub 设计系统重构（--sk-* 令牌、文档流对话、ToolCallGroup） | 已实现（双页双主题、真实 SSE、4K 至窄屏输入区贴底已验证） | [066-skillhub-ui-redesign.md](references/066-skillhub-ui-redesign.md) |
| 067 | 在线对话默认通用智能体与 $ 技能选择器 | 已实现（构建/后端 e2e/浏览器断言通过） | [067-experience-general-agent-dollar-picker.md](references/067-experience-general-agent-dollar-picker.md) |
| 068 | /use 收敛为任务配置表单，历史统一到在线对话侧栏 | 已实现（历史形态被 069 修订，其余约定生效） | [068-form-only-usepage-and-experience-surface.md](references/068-form-only-usepage-and-experience-surface.md) |
| 069 | 历史按对话展示整段记录 + 运行进度只显真实工具调用 | 已实现（构建/curl/浏览器断言与截图通过） | [069-conversation-history-and-toolsonly-progress.md](references/069-conversation-history-and-toolsonly-progress.md) |
| 070 | 历史续聊、运行中刷新恢复原任务与手动继续 | 已实现（Chrome 实模中断续跑、首次提交及重复点击回归通过） | [070-history-as-normal-chat.md](references/070-history-as-normal-chat.md) |
| 071 | 执行过程按模型消息分组、工具行内用途、调用进度与整轮计时 | 已实现（优才与 Pro 实模、并行进度、历史与窄屏验证通过；Flash 用途待实模复验） | [071-history-tool-summary.md](references/071-history-tool-summary.md) |
| 072 | 会话归档与删除（archived 标记、session 路由、两步删除、归档分区） | 已实现（构建/curl/浏览器断言与截图通过） | [072-conversation-archive-delete.md](references/072-conversation-archive-delete.md) |
| 074 | 侧栏实时对话条目与落库竞态重拉（liveConvGroup 占位、运行中徽章） | 已实现（真实两轮 e2e 8 断言通过） | [074-live-sidebar-entry.md](references/074-live-sidebar-entry.md) |

### 工程与协作

| # | 主题 | 状态 | 文件 |
|---|---|---|---|
| 003 | 开发任务 GitHub issue 生命周期与 push 关闭 | 已实现（GitHub 认证后待实测） | [003-task-issue-lifecycle.md](references/003-task-issue-lifecycle.md) |
| 005 | 新仓库协作初始化 Skill：手记、Issue hooks 与项目约定 | 已实现（GitHub 远端待验证） | [005-repo-bootstrap-skill.md](references/005-repo-bootstrap-skill.md) |
| 092 | 主仓库远程迁移至 wulincong：分支与标签同步、chart 技能内置（旧安装入口已由 036 撤下） | 已实现（SSH读写/标签同步/构建/全新递归克隆及21文件一致通过） | [092-main-repository-remote-migration.md](references/092-main-repository-remote-migration.md) |
| 104 | 独立管理后台、技能发布、密钥轮换与共享只读对话历史 | 已实现（浏览器、双协议、真实 Pi 沙箱和现存索引验收） | [104-admin-console.md](references/104-admin-console.md) |
| 048 | 广场技能列表动态化：/api/skills 与幽灵卡移除 | 已实现（API 实测 6 技能；浏览器页面回归待用户） | [048-plaza-skill-list-dynamic.md](references/048-plaza-skill-list-dynamic.md) |
| 057 | 公网入口 origin 白名单 PLAZA_ALLOWED_ORIGINS | 已实现（curl 四场景验证；公网浏览器回归待确认） | [057-public-origin-allowlist.md](references/057-public-origin-allowlist.md) |
| 076 | 开发手记重组：清除运行观察、合并同主题、分区索引（删并映射表） | 已实现 | [076-dev-notes-reorg.md](references/076-dev-notes-reorg.md) |
| 101 | 技能文档的原文目录、仓库索引与公开阅读入口 | 已实现 | [101-skill-documentation.md](references/101-skill-documentation.md) |
