---
name: chart-visualization
description: 根据已核实的数据为报告绘制静态 HTML/SVG 图表。适用于类别比较、趋势、分布、评分和流向分析，以及有离线边界的行政区地图和城市热点图。
---

# 报告图表

先确认数据来源、统计范围和单位。读完[通用规则](references/common-rules.md)，按要回答的问题选择图表。

| 想回答的问题 | 需要的数据 | 图表 |
|---|---|---|
| 哪类岗位更多？不同薪资档位各占多少？ | 每个类别的数量或占比 | [柱状图](references/bar-chart.md) |
| 岗位数逐月怎样变化？ | 日期或有序区间，以及各期同口径数值 | [折线图](references/line-chart.md) |
| 薪资集中在哪段？ | 连续数值，或带上下界的分箱统计 | [直方图](references/histogram-chart.md) |
| 不同城市的学历构成有何差异？ | 每个城市内各学历类别的数量和组内分母 | [堆叠柱状图](references/stacked-bar-chart.md) |
| 几项技术在哪些维度得分较高？ | 同一量表下的多维评分及评分依据 | [雷达图](references/radar-chart.md) |
| 传统技能和哪些新技能关联最强？ | 来源、去向、每条连线的权重及其含义 | [桑基图](references/sankey-chart.md) |
| 样本覆盖了哪些行政区？ | 地区编码、分类或指标、匹配的离线边界 | [行政区地图](references/map-chart.md) |
| 省内哪些城市的岗位记录更集中？ | 同口径城市记录数、查询覆盖范围、离线边界 | [城市热点图](references/heatmap-chart.md) |

绘图时按通用规则生成含内联 SVG 的 HTML 图块，并核对图注、文字说明和数据。两种地图均须匹配[离线资源](resources/README.md)，目前覆盖广东、浙江的地级市。可打开[柱状图](examples/bar-chart.html)、[折线图](examples/line-chart.html)和[广东热点图](examples/java-guangdong-heatmap-no-bubbles.html)查看成品。

修改热点图示例后，在本技能目录运行 `python3 scripts/check-examples.py`，核对示例汇总、逐城填色和两份成品是否一致。
