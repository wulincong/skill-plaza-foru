# 127 · talent-data-query 1.4：受控 JD 原文抽样 description.samples

**状态**：已实现（query/demand 43 项单测全绿；真库机器人产业 live 查询、inspect 指纹、缓存复用、脱敏扫描通过；wechat-integration 13 项失败为既有 Python 夹具问题，非本次引入）。

## 动机

course-development（T05）的规格要求「内容单元必须来自岗位库 JD 原文的任务表述」，而共享查询技能此前只开放聚合（SKILL.md「不返回描述明细」）。085 记录 P1 已规划「少量脱敏岗位摘要」，本次按该方向落地为受控抽样指标。

## 约定细节

- **注册与限制**（`scripts/talent-data/core.mjs`）：`METRICS['description.samples']`（kind `samples`）；`LIMITS.samplesPerCohort=5`、`sampleExcerptChars=1600`；引擎版本升至 `talent-query-engine/1.4.0` 隔离旧缓存。条数为服务端固定上限，不新增请求字段，`talent_query` 参数枚举与 capabilities 自动跟随。
- **SQL job**（`compile.mjs` buildPlan `description-samples`）：投影 `CAST(p.id AS CHAR)`、岗位名/学历/经验（`CAST(NULLIF(TRIM(x),'') AS CHAR)`）、`SUBSTRING(p.description,1,1600)`、`CHAR_LENGTH`；有效描述过滤 `NULLIF(TRIM(p.description),'') IS NOT NULL`；`ORDER BY p.id ASC LIMIT 5`（确定性前 N，非随机）。`describedN` 在 base job 按需聚合（与 skills job 同法）。
- **脱敏单点**（`scripts/talent-data/redaction.mjs`，`jd-excerpt-redaction/1`）：在 `service.mjs` 的 `adapter.run` 之后、`buildResult` 与 evidence 落盘之前，对 description-samples 日志的 excerpt 统一正则掩蔽（手机/座机/邮箱/URL/微信QQ）；result.json 与 evidence.json 同源脱敏，日志带 `redaction` 标记。
- **结果分支**（`metrics.mjs`）：rows[]{positionId(字符串), title, education/experience(中文标签), excerpt, charCount, truncated, hash(脱敏后文本 sha256)}；`missingN=total-describedN`；样本有岗位但无有效描述 → unavailable/NO_VALID_DESCRIPTION；bounds 检查进 quality.checks。
- **真库暴露并修复的两个问题**：① 岗位主键为雪花 BIGINT，超出 JS 安全整数——SQL 侧 CAST 为字符串、JS 侧按 `\d{1,19}` 校验；② MySQL 5.7.43 在**逐行（非 GROUP BY）**JSON_OBJECT 值位放 `NULLIF(TRIM(x),'')` 会序列化为 `false`——包 `CAST(... AS CHAR)` 修复。生产 cube/dimension job 全部 GROUP BY，不受影响。
- **性能事实（2026-11-18 实测）**：`c_company_position` 1410 万行、在招约 700 万；position 表无 `company_address_id` 索引，城市口径（地址 join）连 `positions.count` 都超 120s 单条预算（既有现状，非本次引入）；产业口径走 industryFirst 派生表正常，抽样 job 与聚合同路径，LIMIT 5 不劣化。纯 LIKE 名称包含同样超预算。
- **文档同步**：talent-data-query `SKILL.md` 已实现边界改写；`references/metrics.md` 指标表加行 + 「1.4 扩展」段（抽样方法/限量/脱敏/指纹/不可推断总体分布）；`references/request-contract.md` 补 rows 形态与 evidence 脱敏说明。

## 成本与取舍

- 否决 SQL 侧定串 REPLACE 脱敏：5.7 无 REGEXP_REPLACE，且与 JS 侧两套规则易漂移；单点日志脱敏让两份工件天然同源，掩蔽从宽（宁可误伤相邻文本）。
- 否决 `ORDER BY MD5(p.id)` 稳定哈希抽样：实测城市口径下排序不是瓶颈（全扫描才是），产业口径下主键升序已可复现；method 如实写明「确定性前 N 条，不用于推断岗位总体的表述分布」。
- evidence.json 含**脱敏后**文本（visibility internal）；原始联系方式不出现在任何工件。

## 后续路线

- 城市/title 口径性能依赖数据侧索引（如 `p.company_address_id`），引擎侧不改口径换速度。
- 专业关联、区县、全量描述明细与 XLSX 导出仍未提供，沿用 085 P1 清单。
- 抽样条数/窗口如需业务侧可调，再评估 demand 参数扩展；当前固定上限已覆盖课程开发用途。
