# 086 · 人才查询的按需统计与产业多组聚合

**状态**：已实现（2026-11-02，`talent-query-engine/1.1.0`）。39 项自动测试通过；原 20 条真实请求及 5 次合并请求全部成功；20 项同快照参照校验通过；真实库全部 14 类指标联合查询成功。没有执行源库 DDL；后续公众号取数迁移和1.2方向/技能扩展见[087](087-report-query-skill-integration.md)；其他业务迁移与低权Pi在线验收仍未完成，沿用085的边界。

## 动机

用户最终需要统计数据，不需要岗位明细。1.0 即使只计数，也会关联地址并计算最大平台更新时间和六项缺失量；产业 EXISTS 从大量在招岗位出发，同产业四组重复扫描。需要减少首次实时查询成本，同时保留计数口径、缺失状态与真实执行证据，不能仅依赖结果缓存。

## 约定与接入点

| 接入点 | 当前行为 |
|---|---|
| `scripts/talent-data/core.mjs:3`、`:52` | 引擎升级 1.1.0；注册第 14 类指标 `data_quality.summary`，计数单位 job_records；只接受注册指标 |
| `scripts/talent-data/compile.mjs:11`、`:16` | 无 updatedAt 窗口的产业条件采用关系表 `deleted=0`、有效子树 ID → DISTINCT position_id → 岗位主键 JOIN；有时间窗口保留原 EXISTS 入口。多产业成员不会重复计数 |
| `scripts/talent-data/compile.mjs:40` | 基础 SQL 只投影请求需要的聚合字段；全国纯计数不关联地址；企业/地域/名称/来源统计按其依赖保留对应缺失量，质量指标显式计算全部缺失量与 MAX(update_time) |
| `scripts/talent-data/compile.mjs:67` | 只有 metrics 恰为 positions.count 才合并：共同产业/岗位类型 ID 集、title、updatedAt、state 相同，地域/学历/经验/招聘类型各自留在 CASE 分支。若所有分支有限制，将分支条件并集推入 WHERE，避免把两个城市对比扩大为全国扫描；仍最多四组 |
| `scripts/talent-data/service.mjs:35` | plan 的 queryCount 表示实际统计 SQL 数，logicalCohortCount 表示样本组数；合并 job 公开 cohortIds，仍不输出 SQL |
| `scripts/talent-data/metrics.mjs:59` | 合并响应必须包含完整、合法的每组计数，缺字段报错；各组独立基数与比较语义不变，evidenceIds 引用实际合并 job.id，不虚构四条 SQL |
| `scripts/talent-data/metrics.mjs:101`、`:168` | 可选质量指标返回 missingCompany/missingAddress/missing_city/missing_province/missing_title/missing_source 及最大平台更新时间；缺失项可能重叠。未请求时 missingAddressN/sourceLatestUpdateAt 为 null、dataQualityEvaluated=false；allPass 仅表示本次请求指标通过 |
| `scripts/talent-data/metrics.mjs:174`、`core.mjs:119` | 结果内容指纹按结果记载的 engine 计算，修复版本升级后旧工件无法验签的问题；新统计缓存仍由当前引擎版本隔离 |
| `.agents/skills/talent-data-query/SKILL.md`、`references/*.md` | 指导调用方只请求所需指标，同产业比较优先同请求多 cohort；质量统计、时间/缺失元数据与执行条数按实际评估状态呈现 |

SQL 只返回聚合行，不读取岗位 description 或岗位记录明细。`positions.count.missingN=0` 仅表示主键计数无缺失，不表示岗位属性完整；业务层不能用它回答“地域为空比例”。质量问题显式请求 data_quality.summary 后计算同组比例。

## 验证与证据

本次产物：`reports/query-benchmarks/2026-11-02-five-industries-optimized/优化复测.md`、`comparison.json`、`results.json`、`batch-results.json`、`parity-results.json`、`statistics-smoke.json`。旧基准目录保持不变，两个目录各自的 SQL 与读取时间均可复查；raw/ 工件仅留本机，不提交 Git。

- 原 20 条 live 请求各重测一次：平均 75.938 → 6.656 秒；累计 1518.752 → 133.118 秒，约 11.41 倍。新极值 0.495 / 13.434 秒。这是不同条件单次观测，未清空缓冲池、未隔离业务负载，不是 SLO。
- 同产业四组分别合并，5 个请求/5 条 SQL 得到 20 答案，累计 25.238 秒；不能把按答案分摊时间描述成独立请求延迟。本轮合并与独立数量 20/20 相等。
- 历史基准数量 17/20 与本轮相同；智慧交通全国/广东/广州大专三项分别增加 1141/29/1，字典版本和范围不变。另对五产业各开一个同连接 REPEATABLE READ 只读事务，比较直接关联后的 COUNT(DISTINCT p.id)、新合并计数及四条新独立计数，20/20 相等。不能宣称与历史基准 20/20 数量一致。
- 额外验证最初采用旧 EXISTS 全表入口的四组条件聚合，首组在 180 秒预算内未完成，失败记录 `parity-attempt-failed.json` 与对应 SQL 均保留；换为直接关联去重参照后验证完成。失败不记为零、不计入已完成的性能轮次。
- `node --test --test-reporter=tap scripts/talent-data/*.test.mjs`：39/39 通过。新增 SQLite 内存关系数据执行实际编译 SQL，验证重复产业链接、缺失地址/省、别名、空集合、城市分支并集和合并/独立计数等价；仅翻译 MySQL UTF-8 字面量语法，不写源数据库。开发测试需要 python3/sqlite3，生产查询仍仅需 Node 与 mysql 客户端。
- 真实广州低空经济大专样本 319 条，同时请求全部 14 指标，五条统计 SQL 全部完成，质量评估通过，源最大更新时间按需返回；没有岗位描述列。
- 原 20 个 1.0 结果及新 25 个结果的 manifest/contentHash 均重新校验通过；Skill quick_validate 通过。最终编译器生成的 20 条独立与五条合并 SQL 再与实际证据逐条比对，避免基准脱离最终实现。

完整请求 wallMs 与 sqlBatchMs 是可用计时；逐语句 elapsedMs 受 MySQL stdout 缓冲影响的已知限制保留在 085，不在本次改造中冒充已经修复。

## 成本与取舍

- 候选派生表有去重/临时集合成本。无时间窗产业优先是当前已测路径的启发式选择，不是按每次实际选择率自适应的优化器；宽产业集合、只有城市或高选择性名称条件的性能仍可继续评估。保留时间窗原入口，否决对所有查询强制同一访问路径。
- 条件聚合暂仅优化纯计数，其他指标继续独立按组统计。否决一并加入薪资多组复用、任意分组表达式或通用明细抽取，避免扩大本次正确性与兼容风险。
- 不再默认计算所有质量字段，改变了部分元数据的可用性，代价是调用者需要显式请求质量指标；用 null/未评估表达，否决省略计算后仍填零或宣称全部质量已通过。
- 本轮先完成代码改写与真实基准，再提出数据库方案，未对线上大表直接建索引。现有产业范围索引不覆盖 deleted，新覆盖索引预期收益仍待建后测量；不能把 SQL 改写的 11.41 倍归因于尚未创建的索引。

## 数据库方案与后续路线

实际索引、表规模与 EXPLAIN 见同目录 `database-metadata.json`、`explain-optimized.json`；TABLE_ROWS 和 EXPLAIN rows 都是估计值。岗位表数据约 15.57 GiB、现有索引约 4.75 GiB，建索引有显著的构建与写入成本。

1. 优先在测试副本评估 c_position_chain `(industry_chain_id,deleted,position_id)`；现有 chain_id/idx_chain_pos 未覆盖 deleted，新索引可能减少回表，不能消除多链去重。索引草案 `proposed-indexes.sql` 尚未执行。
2. 针对无产业限制的地域查询独立评估 c_company_position `(company_address_id,publish_state,deleted)`；当前没有地址首列索引，但本轮产业优先计时不能证明其收益。不要自动删除与新索引部分重叠的旧索引。
3. 对高频固定统计评估带刷新时间的预汇总/窄事实表，处理删除、下架、地域变化、跨产业重叠；任意产业并集不能直接求和。全局岗位名 LIKE 仍有成本，中文 FULLTEXT 召回问题沿用 017。
4. 根据真实负载再扩展路径选择、其他指标共享扫描与服务端计时；共享查询的业务迁移、低权在线链路验收仍按 085 单独推进。

## 2026-11-05 · 名称检索路径与调用预算的诊断补注

后续：原生查询入口、产业意图保留、每轮预算和分段诊断已按 [114](114-managed-talent-query-boundary.md) 落地；下文保留诊断时状态。索引与多指标物理扫描复用仍待优化。

**状态**：原因已核实，修复待实现。本轮只读复核产教运行、原始查询工件、当前编译器与真实库执行计划；未重跑重聚合、改索引或更改运行逻辑。详细耗时以 `web/server/traces/20261105-105805-824c.json`、`20261105-111159-qq0q.json` 的本轮 `execution` 及对应 workspace 的 `data/tq-*/{result,evidence}.json` 为准，不把续聊 trace 中累计的历史工具重复计数。

**动机**：产业候选优先已经实现，但业务调用若把产业名称放入 `title.any`，既改变统计口径，也不会进入该优化路径；需要区分调用选错范围、数据库访问成本和多轮重试。

### 持久事实与接入点

- `scripts/talent-data/compile.mjs:12` 仅在已解析产业 ID 非空且无更新时间条件时启用产业候选优先；`:20` 的 `title.any` 由 `scripts/talent-data/core.mjs:152` 编译成 `%词%` 名称匹配。实时 `resolve --kind industry --name 智能网联汽车` 返回唯一一级分类 `id=14`，离线 catalog 也有该产业。上述运行未调用 resolve，所有有效请求均只含 title；“智能网联汽车”→“自动驾驶”→“车联网”是更换样本定义，不能作为同口径的性能降级，更不能把车联网名称计数当作整个产业总量。
- 对原工件中广东名称含“智能网联汽车”、广州名称含“车联网”两条实际 SQL 执行只读 EXPLAIN，均为岗位 `publish_state_index` 的 `type=ref` 入口，估计候选 `rows=6982802`，再按地址主键关联过滤。当前索引元数据确认岗位表仍无 `company_address_id` 首列索引，名称索引为 FULLTEXT；这两条 LIKE 实际未使用它。不能称为全表扫描，也不能把估计行数当作实际扫描数。此路径下减少展示行数、缩小地域或更换低命中关键词，不保证减少驱动候选集；原成功结果虽仅计得 12 条，批次仍为 153780ms，排队 103ms、返回 193 字节。批次包括连接和传输；无服务端监控证据，不能进一步归因于某种 CPU/IO 饱和。
- `scripts/talent-data/compile.mjs:91`、`:96`、`:106`、`:121` 对计数、学历经验联合分组、岗位名称排行、薪酬分别生成 SQL，同连接并不复用一次物理扫描。对本次请求离线核对，纯计数为一条，追加上述维度后为四条。`scripts/talent-data/core.mjs:153` 的完整请求缓存键包含 metrics 和 topN；已成功的纯计数不会命中追加维度后的整包缓存。这是当前一致性与缓存粒度的边界，不能用拼接不同读取批次的指标规避。
- `scripts/talent-data/core.mjs:147` 区分单条 `timeoutMs`（默认 120000、最高 180000）和含排队的任务 `deadlineMs`（默认 240000）。`scripts/talent-data/db.mjs:14`、`:48` 分别实施服务端单条预算与客户端任务预算。模型额外套 `timeout 180` 或 `timeout 200`，可能在内部正常返回结构化失败或完整批次前终止整个 CLI；本次多次只留下外层退出码 124，没有查询工件，无法据此确定每次内部停在哪条 SQL 或排队多少。不能将这些外层终止一律解释为已确认的数据库单条超时。
- 查询技能入口已要求首次读请求契约、整个产业先 resolve，契约已要求超时不自动重跑昂贵查询；上述运行仍出现猜请求字段、超时换词、纯计数失败后增加指标的行为。说明文档规则尚不能保证在线模型执行纪律。失败缓存不复用、修改条件得到新缓存键，叠加没有跨调用的报告级取数总预算，会使每次工具内预算重新开始；仅增加单次超时不能解决累计等待。

### 验证与后续路线

验证：原 trace 起止时刻与两份已保存 result/evidence 对读；两条真实只读 EXPLAIN 和索引元数据查询成功；catalog/resolve 的产业映射一致；使用当前 `validateRequest`/`buildPlan` 离线核对有效请求的 SQL 类别与条数。没有把历史逐语句 `elapsedMs=0` 当成瞬时完成，计时边界沿用 085。未执行改写后的产业聚合性能测试，不能承诺切换路径后的秒级时延。

后续先修业务调用对产业/名称的选择，构造请求前读取契约并集中声明实际需要的指标；增加有原因的重试边界与报告级累计取数预算，协调外层终止和内部工件落盘。仍需按原口径进行名称检索时，再独立评估地域入口索引、筛选结果复用与检索设施。否决未经口径确认的换词、任意缩地域、强替换 FULLTEXT 或并发重聚合；这些做法可能改变答案或放大负载。原有共享查询、一致性读与证据契约继续保留，以上修复均未在本轮实施。
