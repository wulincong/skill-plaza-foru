# 报告结构和证据交接

`report.json` 由报告技能编写。查询请求、指标名、单位、分母和清洗规则由 [人才数据库查询](../../talent-data-query/SKILL.md) 定义，以查询结果为准。

## 完整报告结构

新报告统一使用 `edition=full`，按 [章节表](../assets/templates.json) 的 F01–F09 排列，不提供简报或观察版选择。F01 先回答问题，F02 交代范围和口径，F03–F06 分别论证需求、门槛与薪酬、培养定位和实施条件，F07 比较备选方案，F08 给出行动与风险，F09 收束结论和未决事项。每节含 claim_ids、gap_ids 数组，至少有一项结论或缺口。与本次决定无关的专题，用有依据的适用性判断说明原因；不要把全部 claims 重复放进每一章。

每条 claim 写 text（判断）、basis（可定位证据）、implication（决策影响）和 limitation，引用 source_ids 或 metric_ids。F08 至少有一条 recommendation，另填 owner（建议责任方）、next_step、condition、verification；建议安排不得写成用户已批准的事实。结论与行动不能只是复用同一条摘要。

`decision.evidence_checks` 按 scope、demand、feasibility 顺序记录范围身份、需求依据和实施条件三项检查。每项含 topic、status、reason、source_ids、metric_ids、gap_ids。status 为 supported 时有具体来源或指标；missing 时引用 gaps 并纳入 critical_gap_ids；not_applicable 写清与本次决定的关系及不适用原因。检查理由由真实材料支持，不能把“无登记缺口”视为证据充分。学院层次未知不能写成高职；需求统计不能证明本校可行。必要条件已经否决方案时，说明为什么其余未知不再阻断本期结论。

新报告声明 `decision`。以下仅展示其结构，运行时使用真实材料和判断，不能沿用示例的状态：

```json
{
  "reader": "专业负责人",
  "question": "下学期是否增开调试班？",
  "critical_gap_ids": ["G_CAPACITY"],
  "evidence_checks": [
    {"topic":"scope","status":"supported","reason":"用户明确了本校与下学期。","source_ids":["S_TASK"],"metric_ids":[],"gap_ids":[]},
    {"topic":"demand","status":"supported","reason":"企业访谈说明调试训练需求。","source_ids":["S_INTERVIEW"],"metric_ids":[],"gap_ids":[]},
    {"topic":"feasibility","status":"missing","reason":"尚无可用工位与排课依据。","source_ids":[],"metric_ids":[],"gap_ids":["G_CAPACITY"]}
  ]
}
```

critical_gap_ids 只填阻断当前决定的 gaps ID。与当前任务无关的模板专题不算关键缺口。关键缺证先提问，不构建；只有用户选按现有证据继续才写 `decision.continue_quote`，逐字引用表示同意的原话，例如“按现有证据继续”。只给材料、要求扩围、提问或否定该选项均不授权出稿。范围、指标或用户补充的材料改变时重新判断，不能沿用其他决定的选择。独立命令行运行限定报告时使用 `--user-reply 用户实际回复文件`；广场自动提供本轮原话。Markdown 和 TXT 附件的 excerpt 还会核对文件原句；PDF、Word 的页码和摘录需要在复核时查原件。报告形成的有条件结论不等于审批通过。

粘贴材料可按下面两项相互引用（示意；运行时替换为用户的真实原句和时点）：

```json
{
  "sources": [{"id":"S1","title":"院校排课表","publisher":"用户提供","url":"user:院校排课表","published":"未标注","accessed":"2026-11-04","locator":"第3行","scope":"该校春季可用课时","excerpt":"唯一实训室所有可用课时都已排满"}],
  "claims": [{"id":"C1","kind":"inference","text":"本期需要另找上课时段。","basis":"院校排课表第3行表明既有场地已满。","implication":"专业负责人先核实能否调课，再排入教学计划。","source_ids":["S1"],"metric_ids":[],"limitation":"只适用于该校本期。"}]
}
```

## 证据与章节的对应

| 章节 | 需要回答的问题 | 证据 |
|---|---|---|
| F02–F03 | 研究什么、需求在哪、样本能说明什么？ | 真实范围、记录数、企业数、城市与岗位分布 |
| F04–F05 | 面向哪些学习者，培养哪些能力？ | 学历、经验、薪酬及有效数、岗位任务、课程或企业材料 |
| F06 | 本地需求能否转为本单位实施方案？ | 办学层次、目标人群、教师、场地、预算等与决定相关的材料 |
| F07–F09 | 选什么路径、谁做什么、什么情况下调整？ | 回引已核证据，比较替代和暂缓方案，登记条件与未决项 |

仅有边际分布不能拼成联合分布；单次快照不能证明增长。完整保留实际用于论证的分布与数值，不能只交四个总量。

## 结构与引用

- 顶层 `title, edition, region, industry, period, as_of, status`。region、industry、period 写可展示的文字，如“佛山市”“名称含 Java（不限制产业）”“未限定更新时间；读取时点见 dataReadAt”；查询筛选对象只放在共享请求中。只有实际设置了时间筛选才写区间，读取日期不代替时间窗。edition 为 full，as_of 为报告证据截止日（YYYY-MM-DD），status 为 sample/draft/final；仍有关键缺口用 draft；只有次要缺项可在相关段落说明。
- `sections` 按 [章节表](../assets/templates.json) 的 F01–F09 排列，每项含 id、claim_ids、gap_ids。每章至少一条结论或一个缺口。
- `claims` 含 id、kind（fact/inference/recommendation）、text、source_ids、metric_ids、limitation。统计事实引用指标，质性事实引用材料的具体位置，建议说明依据和验证办法。用户材料中的人数、工位、金额等数量同样登记 metrics（引用该 user: 来源，无需 binding），同口径数值使用一致的 unit、period、region、population。不能把“文字来源”当作省略结构化数量的理由；所有用于比较的分类值均保留，不能只绑定一个总数。
- `gaps` 含 id、description、owner、required_data、impact。
- `sources` 含 id、title、publisher、url、published、accessed、locator、scope、excerpt。用户附件用 uploads/ 相对路径，粘贴材料用 user: 加名称，两者均写页码、表号或段落。粘贴材料的 excerpt 摘录用户原句，不改写，不另建附件；校验仅容忍中文与数字之间的排版空格，数字、词句及标点仍须一致；解释写进 claim。历史样板保留原 references/ 节号。
- `metrics` 含 id、label、value（有限数值）、unit、period、region、population、definition、source_ids。描述分母、样本、计量单位与对应限制；派生指标使用 derived.inputs 和 operation（sum/ratio/percent），写明 comparable_group 与 price_basis。输入单位、地区、时期、样本和价格口径必须可比。

## 引用共享统计

在线从 `talent_query` 或离线 `talent_inspect` 取得工件位置；无原生工具时由查询技能使用其 CLI。报告侧不构造数据库请求。每份结果建一项 source，url 原样填写工作区的 `data/tq-…/result.json`，生成脚本从已校验工件写入 **contentHash** 和 **dataReadAt**，并可据此填写 accessed 和未标注的 published。在 scope 写清实际地域、产业/岗位筛选与时间窗；在 locator 标记工具实际返回的样本组。正文使用可读单位，记录数和企业数分别陈述。

每个直接引用的报告指标加 `binding`，写稿时可省略 value，生成脚本从对应数值字段填入；手填数值或指纹与原件不符会验收失败。例如引用样本组 all 的岗位数时填 `{"metricId":"all/positions.count","field":"value"}`；薪酬中位数用 value.median，首行计数用 rows.0.count，按真实返回的行标签陈述。field 取完整结果的原值，share 是 0–1 比例；若需百分数，在正文格式化或用同口径计数派生。结构脚本调用共享工具的离线 inspect，核对工件、指纹和字段值。分母、行标签、中文单位及结论含义仍需逐条语义复核。

学历等按类别计数、含标签与 share 的分布，field 用 rows 并省略 value。脚本用原分母作为该指标的数值，同时列出分组名称、计数和占比（最多二十组，注明展示范围）。只引用一个分组时可绑定 rows.N.count 等具体单元。无有效薪酬时登记缺口。

确认空样本时可以报告零条记录，薪酬或占比不可得。仅部分指标可用时登记缺口，引用须来自已完成事务、通过对账的指标。无可用结果则省略统计表并说明影响。公开报告保留可读出处与定位，查询内部证据文件不进入交付。

本轮 build 输出的 report.json 已补齐绑定的数值、分组明细与来源，可交给下游消费；工作区根目录的同名草稿可能尚未补齐。

[历史样板](../assets/examples/observation/report.json) 用于复现旧统计口径，不是新范围的数据源。

## 业务构建之后

本轮 build 成功后必须交接 report-rendering 继续到最终成品及平台发布；四份原件只是业务交接结果。旧 decision/observation 稿可 validate、preview、verify，不能作为新的完整报告 build；迁移时补齐论证与必要决策，不机械复制章节。
