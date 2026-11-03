# 直方图绘图 Skill

用于薪资、工作年限或其他连续数值的区间分布。

先读取 [通用图表规则](common-rules.md)：统一处理来源、筛选、快照、分母和小样本说明。

输出要求：

- 使用 `<figure data-chart-skill="histogram-chart" data-chart-id="CH1">`。
- 横轴必须是连续区间，柱宽表达区间宽度，柱高表达占比（等宽区间）或占比密度（不等宽区间），并标注单位。
- 使用内联 `<svg viewBox="0 0 760 360" role="img" aria-labelledby="CH1-title CH1-desc">`。
- 包含 `<figcaption>`、`<title>`、`<desc>`、比例分母定义、来源和快照日期；不得把直方图仅写成表格。
