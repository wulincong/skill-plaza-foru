# 柱状图绘图 Skill

用于比较岗位占比、薪资区间、学历占比、经验区间或热门岗位排序。

先读取 [通用图表规则](common-rules.md)：统一处理来源、筛选、快照、分母和小样本说明。

输出要求：

- 使用 `<figure data-chart-skill="bar-chart" data-chart-id="CH1">`。
- 包含 `<figcaption>`，写明图名、单位、筛选口径和快照日期。
- 使用内联 `<svg viewBox="0 0 760 360" role="img" aria-labelledby="CH1-title CH1-desc">` 绘制横向或纵向柱状图。
- 每根柱子对应一个已核验数据点，柱旁标出数值；不要只输出表格。
- 加入 `<title>`、`<desc>`、坐标轴名称和必要刻度。
