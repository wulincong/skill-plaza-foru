# 折线图绘图 Skill

用于有真实时间顺序或连续区间的数据，不用于没有时间/顺序口径的分类比较。

先读取 [通用图表规则](common-rules.md)：统一处理来源、筛选、快照、分母和小样本说明。

输出要求：

- 使用 `<figure data-chart-skill="line-chart" data-chart-id="CH1">`。
- 包含 `<figcaption>`，写明时间范围、单位、筛选口径和快照日期。
- 使用内联 `<svg viewBox="0 0 760 360" role="img" aria-labelledby="CH1-title CH1-desc">` 绘制折线、节点、坐标轴和网格。
- 横轴必须对应真实日期、月份、季度或有序区间；节点旁标出关键数值。
- 加入 `<title>`、`<desc>` 和数据来源，不要只输出表格。
