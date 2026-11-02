# 017 · 岗位库索引与检索实测：EXPLAIN 与 FULLTEXT 试验

**状态**：实测完成（2026-09-28），结论长期有效。原 017（学历统计 EXPLAIN）、018（岗位名索引 EXPLAIN）、019（FULLTEXT 试验）于 2026-10-19 合并，见 076。

## 动机

学历统计等聚合查询约 40 秒超时，需区分全表扫描与索引低选择性；并验证岗位名 FULLTEXT 索引能否替代 LIKE 筛选。

## 实测结论

- **学历统计 EXPLAIN**（`scripts/career-market-queries/education-distribution.sql` 广州 Java 实习口径）：无 `type=ALL` 全表扫描；岗位表以 `publish_state_index` 驱动（type=ref），候选行估计约 479 万，仍需剩余条件过滤，Extra 含 `Using temporary; Using filesort`；地址表 eq_ref 主键逐条查找再过滤城市。结论：大范围索引访问仍慢。注意不能把估计 rows 当实际扫描行数，filesort 也不证明磁盘排序；EXPLAIN 不能确认并行时 CPU/IO 的具体瓶颈。
- **岗位名索引形态**：`c_company_position` 岗位名只有 FULLTEXT 索引 `ft_position_name`，无 BTREE。`name LIKE 'Java%'` 与 `'%Java%'` 均 `type=ALL` 不走索引（rows ≈ 958 万）；`MATCH(name) AGAINST('+Java' IN BOOLEAN MODE)` 为 `type=fulltext`。现有岗位名索引只被 MATCH AGAINST 使用，不会被 LIKE 使用。
- **FULLTEXT 不能直接替代 LIKE**：全库 Java 命中 38,447 条、广州在招 596 条，但中文词 `+后端`、`+服务端`、`+开发` 均返回 0（当前分词不覆盖中文岗位词）；`MATCH(+Java)` 与中文 LIKE 混合仅 11 条、加实习谓词后 0，与原 LIKE 口径不等价。FULLTEXT 能走索引但改变召回口径；中文检索需 ngram、专用搜索字段或预计算标签之一。

## 成本与取舍

- 只做只读 EXPLAIN / SHOW INDEX / 计数，未建索引、未改业务查询；索引与改写方案须基于索引定义、选择性与实际对比决定，执行计划不能替代实测。

## 后续扩展路线

- 2026-11-02 为共享查询 Skill 设计再次只读核验：现有广州 Java 后端学历 SQL 仍选择 publish_state_index，估计岗位候选 rows=6,732,832，再按地址主键关联/筛城市；EXPLAIN 工具耗时 39ms，不是聚合耗时。当前索引元数据未发现岗位表以 company_address_id 为首列的索引，地址有 `(city,district)`、产业关系有 `(industry_chain_id,position_id)`。未运行真实聚合或实施索引变更；新设计先合并统计、按需取列与缓存，数据库级方案须另行对比验证，见 085。

- 评估城市过滤优先的执行计划、岗位地址关联索引、同一筛选结果复用。
- Java FULLTEXT 作候选集预过滤须先做结果一致性回归；中文词改预计算标签或中文分词索引后，再比较准确率和耗时。

## 验证

- MySQL 8.4 客户端，各次 EXPLAIN/计数均 `ok:true`（59–227ms）。
