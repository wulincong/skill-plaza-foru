---
name: talent-data-query
description: 离线查产业链岗位目录与对应产业，按地域、产业、岗位类型与名称、学历和经验查询平台真实人才数据库，输出统计、薪酬、分布、交叉分析及可追溯证据。用于独立数据问答或为产教决策、就业指导、技术预测、公众号报告提供数据。
---

# 人才数据库查询

本 Skill 是当前仓库共享数据能力。根据问题选择样本与指标，由受信工具执行查询、计算和校验；业务解释、课程建议、趋势研判与报告排版留给调用方。

## 调用

在本次会话工作区执行，`<skill-dir>` 是本 Skill 的安装目录，不能将示例路径原样当作真实路径。工具内部读取项目连接配置，不读取或复制密码文件，不在安装目录生成输出。

```bash
node <skill-dir>/scripts/query.mjs capabilities
node <skill-dir>/scripts/query.mjs catalog --job 质量检验员 --match exact
node <skill-dir>/scripts/query.mjs catalog --industry 机器人
node <skill-dir>/scripts/query.mjs resolve --kind industry --name 机器人
node <skill-dir>/scripts/query.mjs plan --request request.json
node <skill-dir>/scripts/query.mjs query --request request.json
node <skill-dir>/scripts/query.mjs inspect --result data/<requestId>/result.json
node <skill-dir>/scripts/query.mjs export --result data/<requestId>/result.json --format csv
```

首次构造请求时读 [request-contract.md](references/request-contract.md)；指标、分母与清洗规则读 [metrics.md](references/metrics.md)；不确定产业/岗位类型、地址或时间语义时读 [data-domains.md](references/data-domains.md)。`capabilities` 是实际支持能力的权威，不猜指标名或表关系。

## 使用规则

- 问“某产业有哪些目录岗位”或“某岗位在哪些产业链出现”，直接用本地 `catalog` 双向检索并标记快照日期；可组合 `--job` 与 `--industry`。问实时需求量、企业数或薪酬则用 `query`。本地节点 ID 不能传入 `roles`。涉及专业、毕业去向、年度目录或拿不准数据源时，取数前查[目录与选表指引](references/catalog-and-sources.md)。
- 明确地域；全国显式写 national。未指定行业或岗位词时不添加 AI、Java 等默认条件。产业、岗位类型和“名称包含”是不同筛选；用户问整个产业时，先 resolve 并依据语义选择唯一的 level=0 产业候选 ID，同名细链不自动替代整个产业。岗位名检索用 title，仅明确要按岗位类型筛选时用 roles；范围仍有歧义时只澄清会改变结果的事项。
- 一次请求声明所需指标与具名比较组。query 内部完成解析、计划和执行；普通问题不必分别调用所有操作。plan 用于核对复杂范围，执行元数据查询但不跑统计聚合。只传受支持字段与指标，不传 SQL。
- 只需数量时使用 `positions.count`；同一产业的地域、学历、经验等对比尽量放在一次请求的最多四个 cohort 中。执行器在共同条件相同时合并计数，不读取岗位明细。缺失率和平台最大更新时间仅在需要时请求 `data_quality.summary`；未计算的质量元数据为 null/未评估，不解释为没有缺失。
- 默认 cache-ok 接受最长 15 分钟的同条件结果；明确要求重新查询时用 live。引用工具的原始读取时间和数据模式；snapshot-only 必须指明已有 snapshotId、相同条件及允许的新鲜度，不会联网补算。cacheKey 是可刷新的查询缓存键，不能代替不可变 snapshotId。
- 先检查整体与逐指标 status，再读取完整 result.json 中需要的指标。保存结果用 inspect 核验清单；追加 --full 可离线读取已校验的完整结果。普通 stdout 中的 rows 是预览；不以预览行重算分母。partial/failed、空结果、没有有效薪资均如实处理，不替换为样例或凭常识补数字。
- 正文与图表引用同一 result.json、metricId 和 contentHash。报告保留单位、分母、筛选和日期；指标值需要改变时重新查询，不能手工修改结果后继续使用旧验收。
- `evidence.json` 是内部实际查询记录，包含 SQL；默认不进入公开报告或公众号交付。JSON/CSV/Markdown 导出消费已有结果，不再查库；只使用工具实际返回的文件路径，不虚构下载链接。

## 已实现边界

支持省、市、全国和最多四个样本组；产业/岗位类型子树，名称 any/all/exclude；学历、经验、招聘类型、平台更新时间；基础统计、薪酬、低基数交叉、方向互斥归类、技能词聚合、结构化证据与缓存。需要方向/技能指标时读 [analysis.md](references/analysis.md)，显式提供受限规则和词表；不返回描述明细、不自动套用 AI 分类。LQ可由完整城市×方向频数派生，报告侧必须记录公式。专业关联、区县、原始描述明细与 XLSX 导出尚未提供。

数据是平台岗位记录，地址来自企业关联地址；去重主键不等于去除所有跨平台重复职位。专业映射、真实发布时间、就业跟踪未提供对应能力，不能从库内记录推导就业率、实际录用人数或市场新增招聘趋势。

数据库未配置、源不可达或超时，按工具错误说明未完成的指标。此仓库部署使用 Node ≥20 和已兼容的 mysql 客户端；共享工具不依赖各报告 Skill 的 Python `.venv`。
