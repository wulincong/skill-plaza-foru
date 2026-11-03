---
name: chart-visualization
description: 根据有来源的观测或汇总数据制作独立的统计图、论文多面板图和报告图块。支持全国分省地图、分组与分面趋势、配对变化、分布、相关、区间与矩阵，离线输出可编辑 SVG、PDF 和带数值表的 HTML，也可按专题规范绘制构成、流向或行政区图。
---

# 数据图表

先写出读者要做的比较，确认一行代表谁、计量单位、缺失含义和最终图宽。用用户给出的表或已经核实的数据，保留出处和筛选依据。需要匹配观测、估计不确定性时先核对研究设计。[通用规则](references/common-rules.md)

## 可复现的独立出图

把原列名映射到 `figure/1`，可将多张来源表放在同一规格中。从技能目录运行下列命令，输入和输出路径也可用绝对路径。

```sh
python3 scripts/figure.py render examples/paired-recovery.json --out /tmp/recovery-figure
python3 scripts/figure.py verify examples/paired-recovery.json --out /tmp/recovery-figure
```

输出目录须是新目录。交付矢量 PDF 或 SVG 时附上图注，网页交付可直接使用含图注和数值表的 `figure.html`。[字段、依赖与验收](references/figure-spec.md) · [中文单栏图与图注](examples/paired-recovery.html) · [矢量 PDF](examples/paired-recovery.pdf) · [英文双栏示例](examples/sensor-calibration.html)

| 读者要回答的问题 | 数据前提 | 选择 |
|---|---|---|
| 各类别的量相差多少？指标随时间怎么变？ | 同口径汇总。趋势要有真实数值间距 | `bar`、`barh`、`line`，未观测时期显式给空值 |
| 多组趋势何时交叉？同一行业在各省怎样变化？ | 时间、值、系列或分面标识，时间单位一致 | 同轴比较用 `grouped-line`，每省一幅用 `faceted-line`，分面内也可按行业画多条线 |
| 全国各省的指标如何分布？ | 省级名称或六位编码、指标及单位 | `province-map` 用 34 个省级行政区的离线边界按值着色，缺行保留为缺失 |
| 两个量如何共同变化？ | 同一观测单元同时测得两个数值 | `scatter`。仅有组均值时标明分析层级 |
| 分布集中在哪里？有多少观测低于阈值？ | 原始数值。分组点图保留每个观测 | 小样本用 `distribution`。密集数据用 `ecdf` 或[直方图](references/histogram-chart.md) |
| 同一个体如何变化？哪组变化较大？ | 组、对象 ID、两个有序条件和数值 | `paired` 看轨迹，`change-distribution` 看差值，`median-change` 看组内变化中位数及区间 |
| 估计值有多不确定？ | 估计值、可追溯上下界、方法和区间含义 | `interval`。组间效应用经验证的组间估计及其区间 |
| 哪些行列组合存在模式？ | 行、列、每格一个指标 | `matrix`。有意义的正负偏差可围绕零对称着色 |

多面板应分别回答不同问题。需要读者直接比较的组放在同一面板上，使其共享尺度。跨面板比较可显式复用一组数值刻度。单栏优先上下排列，双栏再尝试并排。按成品大小复核最密处、缺失标记和单位。

## 专题图与报告嵌入

报告沿用[柱状图](references/bar-chart.md)、[折线图](references/line-chart.md)和[直方图](references/histogram-chart.md)的口径。比较互斥的组内构成用[堆叠柱](references/stacked-bar-chart.md)，同一量表上的多维评分用[雷达图](references/radar-chart.md)，有权重的来源与去向用[桑基图](references/sankey-chart.md)。这些专题指南也适用于手工生成的内联 SVG。

[行政区地图](references/map-chart.md)和[城市热点图](references/heatmap-chart.md)需要匹配的[离线边界](resources/README.md)，省内地市资源覆盖广东和浙江。全国分省地图使用单独的省级底图。[全国分省与趋势示例输入](examples/provincial-trends.json)报告嵌入与无法评估时的图块见[通用规则](references/common-rules.md)。
