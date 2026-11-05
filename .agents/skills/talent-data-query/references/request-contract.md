# 请求、结果与操作

本文是查询技能内部 CLI 契约。在线调用方有 `talent_query` 时只提交[受管取数需求](managed-query.md)，不自行生成本页的请求文件。

## 最小请求

在会话工作区创建 request.json。下面按岗位名称包含“机器人”查询广州市；不代表整个机器人产业。

```json
{
  "schema": "talent-query/1",
  "sourceId": "talent-main",
  "cohorts": [
    {
      "id": "gz",
      "filters": {
        "region": {"level": "city", "province": "广东省", "name": "广州市"},
        "title": {"any": ["机器人"]}
      }
    }
  ],
  "metrics": ["positions.count", "education.distribution", "salary.summary"],
  "execution": {"freshness": "cache-ok"},
  "output": {"previewRows": 10, "topN": 20, "exports": []}
}
```

多地区对比增加 cohort，给每组独立 id 和完整 filters，最多四组；两组时返回可比较指标的确定性差值。不会自动复用上一组的地域或岗位条件。

只求数量时将 metrics 设为 `["positions.count"]`。共同的产业子树、岗位类型、名称、时间条件和状态相同，只有地域、学历、经验或招聘类型不同的样本组，自动合并为一条条件聚合 SQL。各组保持独立条件与分母；不从省域/全国数量推算城市数量。不满足合并条件时独立查询。

无平台更新时间窗口的产业筛选先在产业关系表去重岗位 ID，再关联岗位；带时间窗口保留原有查询路径供优化器选择。全国纯计数省略地址关联和额外质量统计；地域过滤仍使用相同的企业关联地址与省市别名。此策略不改变筛选口径，也不保证每种条件都同样快。

## filters

| 字段 | 形式与含义 |
|---|---|
| region | 必需。`{"level":"national"}`；或 `{"level":"province","name":"浙江"}`；或 `{"level":"city","province":"浙江省","name":"杭州"}`。城市省份可省略，但有歧义需澄清。区县不支持 |
| title | `any / all / exclude` 字符串数组，每组最多 8 项、每项最长 60 字符；按岗位名包含匹配，字母大小写依数据源 utf8mb4_general_ci；百分号/下划线作为文字，不是通配符；空数组表示没有该限制 |
| industries | 如 `[{"name":"机器人","includeDescendants":true}]` 或 `[{"id":"15"}]`；产业链字典，最多 8 项，项内只选 id/name 之一；子树默认包含 |
| roles | 同 industries 格式，但属于岗位类型字典，不能混用产业 ID；两维同时存在取交集，每维内部取并集 |
| education / experience / jobType | 原始枚举数组，同维 OR；支持值见 capabilities.enums；三个维度之间 AND |
| updatedAt | 如 `{"from":"2026-10-01","to":"2026-11-01"}`，from 包含、to 不包含；数据库存储时区下的平台更新时间，不是职位发布时间 |
| state | 仅 `publishing`，默认即在招且岗位未删除 |

不接受 majors、SQL、表名、自由表达式或自定义输出路径。可在顶层 analysis 声明显式方向规则和技能词，格式见 [analysis.md](analysis.md)。全国/省域任意名称包含查询可能较慢；可以按问题本身限定城市、分类或平台更新时间，不能为提速暗改用户条件。

## execution / output / policies

- freshness：live 重新读业务统计；cache-ok 接受未超过 maxAgeMs 的同条件结果（默认/上限 900000ms）；snapshot-only 只读此前返回的不可变 snapshotId，要求统计请求完全相符且未超过 maxAgeMs，不补查数据库。cacheKey 是会刷新的查询缓存键，与 snapshotId 分开。字典允许使用最长 24h 的已校验缓存。
- deadlineMs：任务预算含等待和查询，默认 240000，上限 360000；timeoutMs 单条默认 120000，上限 180000。复杂任务可减少不需要的指标；超时不自动扩大范围或重跑昂贵查询。
- output.previewRows：0–20，仅影响 stdout；topN：1–100，影响排名的输出与 otherCount，但不改变基数；exports：json/csv/markdown，可选。完整枚举分布仍保留所有组。
- policies.salary 固定 salary-policy/1；policies.consistency 固定 consistent-read。所有样本组在同一连接 REPEATABLE READ 只读事务内统计，产业/岗位字典版本在事务前解析并记录，不宣称它们与业务数据同一事务读取。

## 结果与导出

stdout 返回 talent-preview/1：总体状态、规范化/实际筛选、指标摘要、有限 rows、数据时间、缓存 key、耗时和真实工件路径。完整工件位于 `data/tq-<uuid>/`：

- `inspect --result data/<id>/result.json --full` 在本会话校验清单和内容指纹后返回完整 talent-result/1，不访问数据库，也不读写查询缓存。省略 `--full` 保留有限行预览。
- result.json：talent-result/1；每个指标保留 metricId、name、cohortId、版本、值或 rows、单位、分母、缺失/有效量、方法与 evidenceIds。
- summary.md：由同一结果生成的可读概要。
- evidence.json：实际 SQL、原始聚合行、执行时间、解析字典与校验依据；内部文件。
- manifest.json：本次文件的大小与 SHA-256；inspect/export 会核验必需工件与内容指纹。
- 可选 export.json/csv/md：由结果导出，不含实际 SQL。单独 export 操作输出独立派生目录与清单，不修改原结果。

city/province/title 的 TOP N 返回 totalCount、displayedCount、otherCount、missingN；rows[].share 使用完整样本分母，范围 0–1。previewTruncated 只表示 stdout 裁剪。统计分组超过行数/字节预算将失败或部分完成，不把计算截断伪装为全量。

executedAt 是原任务时间，dataReadAt 是原统计事务的客户端观察时间，servedAt 是本次返回时间；sourceReadTime 是数据库时钟原值；sourceLatestUpdateAt 仅在请求 `data_quality.summary` 时计算样本内平台更新时间最大值，源时区未换算，否则为 null。命中缓存不将 dataReadAt 改成今天。consistency.completeTransaction 指示整个批次是否完成。

`execution.queryCount` 是实际统计 SQL 条数，`logicalCohortCount` 是样本组数；合并的四个指标可共同引用同一个真实 evidenceId。`sqlBatchMs` 包含建连、查询与传输；逐语句日志 elapsedMs 受 mysql stdout 缓冲影响，不能当作可靠的服务端计时。新执行的完整语句另有 serverElapsedMs，记录数据库时钟包围该语句的间隔，含边界语句开销；未完成及旧结果为 null/缺省。execution.stages 和受管阶段日志用于区分当前调用的各层耗时。引擎版本参与缓存键；升级后不复用旧版本统计缓存，已有结果仍按其记录的引擎版本验证指纹。

退出码 complete/empty=0、partial=3、需澄清/修正=2、failed=1。始终检查结构化状态及逐指标 status；无岗位为 empty，没有有效薪资为 unavailable，未识别地域为 needs_clarification，查询超时不是 0 岗位。失败结果不缓存为可复用统计。

capabilities 不连接数据库；catalog 读取随技能安装的[岗位与产业快照](catalog-and-sources.md)，不读取数据库或写工作区；resolve 查字典/地址候选；plan 不执行岗位聚合；query 执行并落盘；inspect/export 只读本会话经校验的结果。数据库配置和共享状态目录由部署者提供，业务请求不能指定客户端、密码或缓存根目录。
