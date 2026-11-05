# 受管取数与业务交接

报告提出证据需求，查询技能对实际筛选、请求构造、执行预算、结果与诊断负责。产教在线会话已挂载本技能维护的原生工具；业务技能不维护查询实现或复制 SQL。其他现有 CLI 调用方的迁移需单独验证。

## 提交业务需求

```json
{
  "samples": [{
    "region": {"level":"province", "name":"广东"},
    "industries": ["智能网联汽车"]
  }],
  "metrics": ["positions.count", "education.distribution", "experience.distribution", "salary.summary", "title.top"]
}
```

这是 `talent_query` 参数，不是写入文件的数据库请求。指标由当前论证决定，示例不要求每份报告查询这五项。

- samples 最多四个，各自包含 region。industries 用产业名称；工具自动选择唯一同名 level=0 节点及子树，有歧义就返回候选，不改成岗位名搜索。roles 用明确的岗位类型名称，不能传目录节点 ID。
- title.any/all/exclude 仅表达真实的岗位名限制。education、experience、jobType、updatedAt 与共享查询契约语义相同。工具不补默认行业、不为提速改地域或时间窗。
- metrics 使用 `talent_query_capabilities` 的注册指标；需要方向/技能分析时，analysis 沿用 [analysis.md](analysis.md) 的规则。freshness 默认 cache-ok，用户明确要求刷新才用 live。
- 不接受 SQL、数据库表名、内部请求路径、输出路径或执行超时参数；内部样本 ID、固定统计策略、产业 ID 与预算由本技能构造。
- 对用户原话中可识别的明确产业需求，工具检查产业是否保留，阻止把智能网联汽车产业换成“自动驾驶”“车联网”等标题词。该检查基于随技能分发的目录与明确措辞，不代替完整自然语言理解；复杂排除、组合和模糊产业仍应核对实际返回范围。

## 执行和失败边界

每轮共用 240 秒取数预算，覆盖工具内解析、等待、执行和落盘，最多两次统计批次。相同需求可直接复用本轮已验工件。一次列齐需要的指标，避免先查计数再追加维度造成第二轮扫描。单条 SQL 最长 120 秒；预算由查询技能统一管理，报告不能加外层 timeout。

数据库超时、取消或执行失败会停止本轮后续查询。格式或范围错误可在没有执行统计前修正；不能因失败就试其他关键词。新一轮能重新提出需求，但业务技能必须遵守用户对缺口、范围和继续方式的选择。跨轮同条件缓存仍采用原 15 分钟新鲜度与完整指标包规则，不拼接不同读取批次的指标。

正常返回沿用 talent-preview/1 和已有 `data/tq-…/result.json`；`talent_inspect(resultPath)` 离线核验并返回完整统计。失败不是零，partial 逐指标判断，内部 evidence 不公开。

## 定位问题

每次调用有 `handoff.owner=talent-data-query`、`traceId`、`runId`、wallMs、结果状态及实际工件路径。工作区 `.talent-query/events.jsonl` 记录同一标识下的阶段事件：

| 阶段 | 责任和含义 |
|---|---|
| demand / scope_resolution / validation / resolution | 业务需求校验、一级产业解析、内部请求校验、实体展开 |
| setup / capability / cache_lookup / cache_write | 查询环境、读能力检查、缓存读取与保存 |
| request_queue / database_queue | 同请求合并等待与数据源重查询等待 |
| database / database_result | 整个客户端批次耗时、实际 SQL 完成状态与逐条服务端包围计时 |
| aggregation / artifacts | 聚合结果计算校验、证据与结果落盘 |
| handoff | 交还业务技能的状态、工件位置或失败阶段 |

阶段日志不复制 SQL 或密码，SQL 仍仅在内部 evidence。`serverElapsedMs` 是数据库时钟在该条 SQL 前后记录的间隔，含边界语句的小量开销；未完成语句为 null。旧 `elapsedMs` 仍是 stdout 到达间隔，不能作为真实 SQL 耗时。`sqlBatchMs` 包含建连和传输。缓存复用时旧执行字段描述源批次，本次 wallMs 和阶段日志描述当前调用；不能相加。

运行器挂载 `scripts/pi-tools.mjs` 并传递 `talent-query-turn/1` 用户原话与 runId，不解析产业或计算统计。原生工具拦截常规直接查询 CLI、连接配置访问与自编数据库脚本；这是工作流约束，不是针对任意恶意代码的操作系统网络隔离。独立 CLI、查询核心与原生适配器均归本技能维护。

计时设计参考 [MySQL 日期时间函数](https://dev.mysql.com/doc/refman/8.4/en/date-and-time-functions.html#function_now) 的语句起始时刻语义：起止分别使用独立语句读取时间，避免在同一条 SELECT 中比较两个 NOW()。当前部署的 MySQL 兼容性通过真实统计执行验收。
