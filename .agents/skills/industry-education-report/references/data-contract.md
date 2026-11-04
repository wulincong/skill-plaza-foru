# 报告结构和证据交接

`report.json` 由报告技能编写。查询请求、指标名、单位、分母和清洗规则由 [人才数据库查询](../../talent-data-query/SKILL.md) 定义，以查询结果为准。

## 选择报告版式

单项决定使用 edition=decision，sections 顺序为 D01 决策摘要、D02 证据与判断、D03 行动与适用条件。各章均写 claim_ids、gap_ids 两个数组。D01 的结论回应原问题；D02 引用的每条 claim 除 text（判断）、limitation、source_ids 或 metric_ids 外，还填 basis（具体证据）和 implication（这对本次决定意味着什么）；D03 写可执行的建议与条件。新观察版在 S02–S12 使用相同的 basis、implication 写论证段。次要缺项只在相关位置交代。没有适合的量化比较时，charts 填空数组。

新报告声明 `decision`，例如 `{"reader":"专业负责人","question":"下学期是否增开调试班？","critical_gap_ids":[]}`。critical_gap_ids 只填阻断当前决定的 gaps ID。与当前任务无关的模板专题不算关键缺口。关键缺证先提问，不构建；只有用户选按现有证据继续才写 `decision.continue_quote`，逐字引用表示同意的原话，例如“按现有证据继续”。只给材料、要求扩围、提问或否定该选项均不授权出稿。范围、指标或用户补充的材料改变时重新判断，不能沿用其他决定的选择。独立命令行运行限定报告时使用 `--user-reply 用户实际回复文件`；广场自动提供本轮原话。Markdown 和 TXT 附件的 excerpt 还会核对文件原句；PDF、Word 的页码和摘录需要在复核时查原件。报告形成的有条件结论不等于审批通过。

粘贴材料可按下面两项相互引用（示意；运行时替换为用户的真实原句和时点）：

```json
{
  "sources": [{"id":"S1","title":"院校排课表","publisher":"用户提供","url":"user:院校排课表","published":"未标注","accessed":"2026-11-04","locator":"第3行","scope":"该校春季可用课时","excerpt":"唯一实训室所有可用课时都已排满"}],
  "claims": [{"id":"C1","kind":"inference","text":"本期需要另找上课时段。","basis":"院校排课表第3行表明既有场地已满。","implication":"专业负责人先核实能否调课，再排入教学计划。","source_ids":["S1"],"metric_ids":[],"limitation":"只适用于该校本期。"}]
}
```

明确需要全景观察时选 edition=observation。下表是完整观察版的章节映射。

## 把决策问题映射到章节

| 章节 | 需要回答的问题 | 优先证据 |
|---|---|---|
| S01–S02 | 样本覆盖哪些岗位、企业和地区？ | 同条件的记录数、企业数与城市分布，标明地域依据和缺失 |
| S03–S04、S07 | 岗位集中在哪些方向？哪些城市的结构不同？ | 岗位名称排名，有明确分类规则才使用方向分布和城市交叉 |
| S05–S06、S08 | 入门门槛和薪酬如何影响培养定位？ | 学历、经验、薪酬有效数与中位数。分别统计的边际分布不能拼成联合分布 |
| S09–S12 | 哪些任务适合纳入课程，需向谁核实？ | 声明词表的技能统计、用户提供的课程和企业材料。单次岗位截面不能证明增长 |
| S00、附录 A/B/C | 哪些判断已有依据，哪些仍需补证？ | 回引正文的指标和限制，附来源、分母、采集时间与方法 |

## 结构与引用

- 顶层 `title, edition, region, industry, period, as_of, status`。region、industry、period 写可展示的文字，如“佛山市”“名称含 Java（不限制产业）”“平台更新时间 [起日, 止日)”；查询筛选对象只放在共享请求中。edition 为 decision 或 observation，as_of 为报告证据截止日（YYYY-MM-DD），status 为 sample/draft/final；仍有关键缺口用 draft；只有次要缺项可在相关段落说明。
- `sections` 按 [章节表](../assets/templates.json) 的对应版式排列，observation 含 S00–S12、APXA/B/C，每项含 id、claim_ids、gap_ids。每章至少一条结论或一个缺口。
- `claims` 含 id、kind（fact/inference/recommendation）、text、source_ids、metric_ids、limitation。统计事实引用指标，质性事实引用材料的具体位置，建议说明依据和验证办法。
- `gaps` 含 id、description、owner、required_data、impact。`charts` 含 id、title、metric_ids、note、type（table）。图注交代样本和分母。只有缺口且没有数值时可用空 charts。
- `sources` 含 id、title、publisher、url、published、accessed、locator、scope、excerpt。用户附件用 uploads/ 相对路径，粘贴材料用 user: 加名称，两者均写页码、表号或段落。粘贴材料的 excerpt 摘录用户原句，不改写，不另建附件；解释写进 claim。历史样板保留原 references/ 节号。
- `metrics` 含 id、label、value（有限数值）、unit、period、region、population、definition、source_ids。描述分母、样本、计量单位与对应限制；派生指标使用 derived.inputs 和 operation（sum/ratio/percent），写明 comparable_group 与 price_basis。输入单位、地区、时期、样本和价格口径必须可比。

## 引用共享统计

从真实 `query` 或离线 `inspect` 取得工件位置。每份结果建一项 source，url 原样填写工作区的 `data/tq-…/result.json`，生成脚本从已校验工件写入 **contentHash** 和 **dataReadAt**，并可据此填写 accessed 和未标注的 published。在 scope 写清实际地域、产业/岗位筛选与时间窗；在 locator 标记样本组。正文使用可读单位，记录数和企业数分别陈述。

每个直接引用的报告指标加 `binding`，写稿时可省略 value，生成脚本从对应数值字段填入；手填数值或指纹与原件不符会验收失败。例如引用样本组 all 的岗位数时填 `{"metricId":"all/positions.count","field":"value"}`；薪酬中位数用 value.median，首行计数用 rows.0.count，按真实返回的行标签陈述。field 取完整结果的原值，share 是 0–1 比例；若需百分数，在正文格式化或用同口径计数派生。结构脚本调用共享工具的离线 inspect，核对工件、指纹和字段值。分母、行标签、中文单位及结论含义仍需逐条语义复核。

学历等按类别计数、含标签与 share 的分布，field 用 rows 并省略 value。脚本用原分母作为该指标的数值，同时列出分组名称、计数和占比（最多二十组，注明展示范围）。只引用一个分组时可绑定 rows.N.count 等具体单元。无有效薪酬时登记缺口。

确认空样本时可以报告零条记录，薪酬或占比不可得。仅部分指标可用时登记缺口，引用须来自已完成事务、通过对账的指标。无可用结果则省略统计表并说明影响。公开报告保留可读出处与定位，查询内部证据文件不进入交付。

[历史样板](../assets/examples/observation/report.json) 可用于复现旧格式。旧样板不是新范围的数据源。
