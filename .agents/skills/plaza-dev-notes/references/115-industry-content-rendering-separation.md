# 115 · 产教报告只产出业务内容

**状态**：已实现。业务稿、共享渲染、平台交付分层回归通过。此条替代 112、113 中产教技能仍编写图稿规格、维护嵌图兼容入口和逐轮绘图指令的约定。

## 动机

引入 report-rendering 后，产教技能仍重复维护出图命令、图型与主题、移动端验收，章节模板固定了图 1–9 和蓝白配色。业务 JSON 还要求 charts，即使这里只用于 Markdown 表格。运行器每轮再次注入整套绘图步骤，删除入口文案仍不足以解耦。

## 职责与交接

- `.agents/skills/industry-education-report/SKILL.md:8` 保留需求、取证、证据门槛、业务论证、复核与四份原件构建；`:20` 只保留一句呈现交接。文档、报告契约和 observation 内容模板删除图型、图稿规格、主题、布局、HTML、移动端及导出版面要求。查询继续遵循 114 的受管工具，未改变查询协议。
- 业务 JSON 保留 title/edition/region/industry/period/as_of/status、decision、sections、claims、metrics、sources、gaps。删除 charts 的必填、图型校验和“数字必须登记图表”门槛。指标须被结论引用，数值、单位、分母、分组及来源仍核验，不能靠一个图表声明使孤立指标通过。旧输入的额外字段不参与呈现校验。
- `scripts/report.py:91` 只校验证据与业务结构；`:297` 的 compose_markdown 生成可复核的正文与指标口径附录，直接遍历已核 metrics，不再依赖 charts 配表。`:456` 的 build 保留正文、结构化报告、结构验收、证据复核四文件、指纹和本轮收据。旧 render 命令删除，文字预览使用 preview（`:519`）；validate/build/verify 继续使用。旧统计样板同步去除 charts 并更新正文，已发布文件不回写。
- 删除产教 `scripts/embed_chart.py`，没有保留转发壳。共享 `.agents/skills/report-rendering/references/page-model.md:22` 负责理解成稿与分组数值，按论证选择图表、表格和布局。图型多样化、最新 chart-visualization 能力发现、绘制/复验、主题、移动端验收统一由渲染技能维护。其内部页面模型仍由 Agent 整理，不要求业务 JSON 提供页面结构。
- `web/server/lib/skills.ts:137` 与 `piRunner.ts:728` 只注入成稿交接提示。补交付同样指向共享技能（`web/server/index.ts:1773`）。会话仍挂载查询、渲染和绘图技能，挂载是能力发现，不承担绘图步骤。
- `web/server/lib/reportWeb.ts:6` 接管原平台网页入口检查，独立于业务正文解析器。发布仍由平台合并本轮四原件与共享渲染登记的网页；此轮没有改变网页需求识别或已有交付协议。两代退役提示仅留在 `legacyIndustryPrompts.ts:1`，用于历史消息剥离，不再注入新轮次。

## 成本与取舍

保留 Markdown 正文与指标表，是为了独立复核和下载业务内容；它们不决定网页组件、图型或样式。不把 Markdown 内容组装移入 UI 层，避免业务校验和四件套交付反向依赖渲染器。拒绝保留已弃用的产教嵌图 CLI 和字段要求，以免维护两套入口。使用旧 render 命令的外部调用需改为 preview；旧草稿若有只被 charts 引用的指标，需将实际依据绑定到相应 claim。

保留退役提示的文本仅为恢复历史用户原话，删除它们会使旧运行显示内部指令。共享页面检查仍由当前产教交付挂接，其他业务接入时可以复用；此次未全局改变其他技能的发布行为。

## 验证

- 业务 Python 12 项、共享统计到业务构建 Node 4 项通过，覆盖无 charts 的数值报告、分组绑定、纯质性报告、等待用户、修订、指纹、四份原件与追加网页。
- 共享渲染 Python 6 项及迁入渲染技能的发布回归 1 项通过。后者不依赖产教 schema，实跑共享出图、重复嵌图、完整 figure 发布和损坏拒绝。
- 平台交付、历史、补交付、HTML 与 HTTP/SSE 相关 41 项通过。Node 入口语法、两个技能格式、文档索引与 Vue 构建通过。历史样板经 preview 输出与 verify 一致。另有 3 项文档解析回归通过。确认最近一小时运行均已结束后，以 systemctl 重启后端，直连与前端代理 health 均成功。
- 尚未使用真实模型重新生成报告；上述为本地脚本与 HTTP 回归，不宣称覆盖真实模型的任意内容映射。

## 后续

业务证据不足或推断错误由产教层处理；实体范围与查询时延由 talent-data-query 处理；选图、图稿和页面问题分别回到 chart-visualization 与 report-rendering。新的主题或图型不再修改产教模板。其他报告接入共享渲染时复用这一内容交接方式。
