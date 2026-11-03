# 城市热点图

用地级市边界的填色展示同一省内岗位库记录的分布。颜色越深，记录越多。图注说明统计的是岗位记录，不能据此推算就业人数。

## 何时绘制

- 目标在中国境内时，先按[离线资源说明](../resources/README.md)查目标省份。查询范围的 `provinceCode` 必须与资源清单一致。境外目标省略此图。目标不明时先询问或标“未评估”。
- 每条查询记录先用城市名查 `cityNameToCode`，核对六位字符串 `rows[].code`，再连接边界的 `properties.adcode`。省份未注册、名称匹配不唯一或缺少边界时，说明具体原因，停止绘图。

## 输入与汇总

以下为演示数据。四个城市在查询范围内，珠海明确返回零条，佛山没有返回记录。

```json
{
  "queryId": "city-distribution",
  "scope": { "country": "中国", "province": "广东省", "provinceCode": "440000", "level": "city" },
  "queryDate": "2026-09-28",
  "snapshotDate": "2026-09-27",
  "source": "教学样例（模拟）",
  "filters": { "keywords": ["Java"], "roleTerms": ["后端"], "internship": true },
  "unit": "job_records",
  "coveredCodes": ["440100", "440300", "440400", "440600"],
  "rows": [
    { "city": "广州", "code": "440100", "count": 3 },
    { "city": "深圳", "code": "440300", "count": 1 },
    { "city": "珠海", "code": "440400", "count": 0 }
  ],
  "totalCount": 4,
  "otherCount": 0
}
```

- `coveredCodes` 列出查询实际覆盖的城市。每个城市至多一行，`count` 为非负整数。按记录数降序保留前 20 行。
- `totalCount` 必须来自相同地区、时间和筛选条件。`otherCount = totalCount - sum(rows[].count)`。示例中 4 − (3 + 1 + 0) = 0。“其他”是合计数，不分摊到地图上。
- 只有前 20 行、缺少同口径总量时，先补查总量。无法取得时标“未评估”。不要把已显示行的和当作查询总量。

## 填色与输出

| 数据状态 | 图上表达 |
|---|---|
| 有正数 | 用从浅到深的同一色阶。采用分档图例时，地图与图例共用区间边界和颜色。 |
| 明确返回 0 | 使用独立的零值色或最低数据色，图例注明“0 条”。 |
| 范围内缺行或未展示该城数值 | 用中性色，文字注明“未返回”或“未展示”。不得补零。 |
| 查询范围之外 | 保留中性底色，文字注明“未覆盖”。 |

使用 `<figure data-chart-skill="heatmap-chart" data-chart-id="CH_CITY">`。每市用离线边界绘制路径，只给重点城市加文字标签，不叠加气泡。图注或可访问文字写出查询日、快照日、来源、城市字段、筛选、范围、分母和单位。[查看广东成品](../examples/java-guangdong-heatmap-no-bubbles.html)。

查询失败时保留同一图表标识，图注说明实际原因。例如：

```html
<figure data-chart-skill="heatmap-chart" data-chart-id="CH_CITY" data-chart-status="unassessed">
  <figcaption>热点图未评估：本次省内城市分布查询超时。</figcaption>
</figure>
```
