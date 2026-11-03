# 堆叠柱状图绘图 Skill

用于展示学历、经验、薪资或地域等构成比例，并比较多个口径或群组。

先读取 [通用图表规则](common-rules.md)：统一处理来源、筛选、快照、分母和小样本说明。

输出要求：

- 使用 `<figure data-chart-skill="stacked-bar-chart" data-chart-id="CH1">`。
- 每根柱子表示一个群组，每个堆叠段表示一个构成项；所有段的单位必须一致。
- 使用内联 `<svg viewBox="0 0 760 360" role="img" aria-labelledby="CH1-title CH1-desc">`，提供图例、百分比标签和比例分母定义。
- 包含 `<figcaption>`、`<title>`、`<desc>`、来源和快照日期；不要用 Markdown 表格代替。
