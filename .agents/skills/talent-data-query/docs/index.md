# 查询产业岗位目录与人才统计

报告开发者可以先离线查产业链岗位目录，再按明确的地区、产业和岗位范围查询人才统计。目录记录说明岗位与产业链的对应关系；薪资、数量等指标需要单独取数。

## 先定位，再取数

在仓库根目录试查「质量检验员」出现在哪些产业链节点。

```sh
node .agents/skills/talent-data-query/scripts/query.mjs catalog --job 质量检验员 --match exact
```

要回答「广东机器人产业有多少在招岗位」时，先用 `resolve --kind industry --name 机器人` 核对根产业，再按请求契约写明地域和 `positions.count`。目录节点 ID 和实时产业或岗位类型的筛选 ID 各有自己的用途。

## 核对统计结果

从会话工作目录运行 `query --request request.json`。读完整 result.json 中整体与逐指标的状态、时间、筛选和分母，报告用同一次结果里的数值。只要保存的结果已有目标指标，就可用 export 导出，无需重复取数。源库不可达或指标缺失时，在报告该位置注明缺口。

[请求与结果字段](../references/request-contract.md) · [指标与分母](../references/metrics.md)

产教决策报告按照相同的结果契约引用事实。改标题或建议时可用 `inspect --result data/<id>/result.json --full` 在本会话核验完整统计，保留原读取时间和分母。
