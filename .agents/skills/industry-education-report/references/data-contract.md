# 报告结构和证据交接

`report.json` 由报告技能编写。查询请求、指标名、单位、分母和清洗规则由 [人才数据库查询](../../talent-data-query/SKILL.md) 定义，以查询结果为准。

## 把决策问题映射到章节

| 章节 | 需要回答的问题 | 优先证据 |
|---|---|---|
| S01–S02 | 样本覆盖哪些岗位、企业和地区？ | 同条件的记录数、企业数与城市分布，标明地域依据和缺失 |
| S03–S04、S07 | 岗位集中在哪些方向？哪些城市的结构不同？ | 岗位名称排名，有明确分类规则才使用方向分布和城市交叉 |
| S05–S06、S08 | 入门门槛和薪酬如何影响培养定位？ | 学历、经验、薪酬有效数与中位数。分别统计的边际分布不能拼成联合分布 |
| S09–S12 | 哪些任务适合纳入课程，需向谁核实？ | 声明词表的技能统计、用户提供的课程和企业材料。单次岗位截面不能证明增长 |
| S00、附录 A/B/C | 哪些判断已有依据，哪些仍需补证？ | 回引正文的指标和限制，附来源、分母、采集时间与方法 |

## 结构与引用

- 顶层 `title, edition, region, industry, period, as_of, status`。region、industry、period 写可展示的文字，如“佛山市”“名称含 Java（不限制产业）”“平台更新时间 [起日, 止日)”；查询筛选对象只放在共享请求中。edition 为 observation，as_of 为报告证据截止日（YYYY-MM-DD），status 为 sample/draft/final；存在缺口不能用 final。
- `sections` 按 [章节表](../assets/templates.json) 的 S00–S12、APXA/B/C 排列，每项含 id、claim_ids、gap_ids。每章至少一条结论或一个缺口。
- `claims` 含 id、kind（fact/inference/recommendation）、text、source_ids、metric_ids、limitation。统计事实引用指标，质性事实引用材料的具体位置，建议说明依据和验证办法。
- `gaps` 含 id、description、owner、required_data、impact。`charts` 含 id、title、metric_ids、note、type（table）。图注交代样本和分母。只有缺口且没有数值时可用空 charts。
- `sources` 含 id、title、publisher、url、published、accessed、locator、scope、excerpt。用户附件用 uploads/ 相对路径，粘贴材料用 user: 加名称，两者均写页码、表号或段落。历史样板保留原 references/ 节号。
- `metrics` 含 id、label、value（有限数值）、unit、period、region、population、definition、source_ids。描述分母、样本、计量单位与对应限制；派生指标使用 derived.inputs 和 operation（sum/ratio/percent），写明 comparable_group 与 price_basis。输入单位、地区、时期、样本和价格口径必须可比。

## 引用共享统计

从真实 `query` 或离线 `inspect` 取得工件位置。每份结果建一项 source，url 原样填写工作区的 `data/tq-…/result.json`，生成脚本从已校验工件写入 **contentHash** 和 **dataReadAt**，并可据此填写 accessed 和未标注的 published。在 scope 写清实际地域、产业/岗位筛选与时间窗；在 locator 标记样本组。正文使用可读单位，记录数和企业数分别陈述。

每个直接引用的报告指标加 `binding`，写稿时可省略 value，生成脚本从对应数值字段填入；手填数值或指纹与原件不符会验收失败。例如引用样本组 all 的岗位数时填 `{"metricId":"all/positions.count","field":"value"}`；薪酬中位数用 value.median，首行计数用 rows.0.count，按真实返回的行标签陈述。field 取完整结果的原值，share 是 0–1 比例；若需百分数，在正文格式化或用同口径计数派生。结构脚本调用共享工具的离线 inspect，核对工件、指纹和字段值。分母、行标签、中文单位及结论含义仍需逐条语义复核。

学历等按类别计数、含标签与 share 的分布，field 用 rows 并省略 value。脚本用原分母作为该指标的数值，同时列出分组名称、计数和占比（最多二十组，注明展示范围）。只引用一个分组时可绑定 rows.N.count 等具体单元。无有效薪酬时登记缺口。

确认空样本时可以报告零条记录，薪酬或占比不可得。仅部分指标可用时登记缺口，引用须来自已完成事务、通过对账的指标。无可用结果则省略统计表并说明影响。公开报告保留可读出处与定位，查询内部证据文件不进入交付。

[历史样板](../assets/examples/observation/report.json) 可用于复现旧格式。旧样板不是新范围的数据源。
