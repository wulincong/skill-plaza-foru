# 独立图稿规格 figure/1

## 从表到图稿

每个数据集是一张具名的行表。将 CSV 的数值列转为 JSON 数字，缺失单元格转为 `null`，保留实测的 0。字段映射使用原列名。不同面板可以读取同一张表，也可以读取不同的表。规格、输入数据和工具版本共同决定可复现范围。

```json
{
  "schema": "figure/1",
  "id": "F_YIELD",
  "lang": "zh",
  "title": "两批试件的合格数",
  "caption": "每批检测 10 件，纵轴表示合格件数。",
  "source": "模拟检验记录",
  "datasets": {"检验": [{"批号": "甲", "合格件": 6}, {"批号": "乙", "合格件": 4}]},
  "panels": [{
    "kind": "bar", "title": "批次比较", "data": "检验",
    "fields": {"category": "批号", "value": "合格件"},
    "x_label": "批次", "y_label": "合格数 (件)"
  }]
}
```

`id` 以英文字母开头，可含数字、连字符、下划线。`lang` 可用 `zh` 或默认的 `en`，控制自动图注。面板按行排，`columns` 默认 1。`width_mm` 是整图物理宽度，默认 89。`panel_height_mm` 是一行面板的高度，默认 55。双栏示例使用 183 mm。标题简短，单位随坐标轴或矩阵标题一起给出，具体栏宽以目标期刊为准。

## 面板字段

| kind | fields 中的角色 | 规则 |
|---|---|---|
| bar、barh | category, value | 每类一行，从零起画，允许负值。barh 横向排长标签，数值轴单位写在 x_label |
| line | x, y | x 为真实数值坐标，升序连接。日期可转为距起点的日数并标明起点。缺失 y 断线 |
| scatter | x, y | 两列均有观测才绘点。相同坐标合并并按频数编码点面积，密集云图按最终尺寸审阅 |
| distribution | group, value | 单点保留原纵坐标，横向错开重合点。短线为中位数 |
| histogram | value | 另给递增的 `edges`，覆盖全部有效值。纵轴注明概率密度及倒数单位，各箱面积表示比例 |
| ecdf | value | 用有效行数作分母，重复值累加在同一阶跃 |
| paired、change-distribution、median-change | group, id, phase, value | 在面板上另给 `phases` 数组，顺序决定变化的正负 |
| interval | group, value, lower, upper | 另给 `method`，写明区间方法和水平。仅有估计值时上下界均填 null |
| matrix | row, column, value | 每个格子最多一行。`scale` 为 `sequential` 或 `zero-centered`。省略的行列组合与显式 null 均为缺失，0 照常着色 |

有定量尺度的轴可用 `x_ticks`、`y_ticks` 给出完整递增刻度。当跨面板比较需要同尺度时复用同一组。刻度须覆盖所有观测、上下界以及适用的零基线。ECDF 纵轴固定为 0 到 1。

分组、类别、阶段、行列名为非空文本，对象 ID 也可统一用整数。缺少整列或重复配对键会报错。矩阵的行列全集由输入中出现的标签确定。数据只有汇总时直接使用相应汇总面板。不从均值生成散点、配对或区间。

## 配对与区间

同一个对象只能属于一个组，每阶段至多有一条测量。技术重复应按研究方案先合并。一次访视缺行或为 null 时，轨迹保留另一次的单点。图注给出完整配对数与登记对象总数。分布和区间均以完整配对的“第二阶段减第一阶段”为单位。两阶段均未测量的已登记对象只进入对象总数，解释失访偏差时要说明。

`median-change` 估计**各组内**配对变化的总体中位数。仅当抽样单位独立、连续型变化的中位数是目标量时指定 `independent_units: true`。将 n 个变化量升序排列，选最大的 k，使 Bin(n, 0.5) 的左尾 P(X < k) ≤ 0.025。区间为第 k 小到第 k 大的值，实际覆盖率随 n 离散变化。小于 6 对时没有满足条件的有限双侧区间，只绘中位数。存在并列值时覆盖可更保守。数值表保留对应对象编号，使用敏感数据时先在输入表中用代号替换身份。机器数值表记录的是连续模型下的名义覆盖率。对聚类、重复批次或组间处理效应，先按正确的分析单位拟合，再用 `interval` 展示所得估计与上下界。[配对输入](../examples/paired-recovery.json)

## 输出与验收

- Linux 离线工具链使用 Python 3、PyGObject 的 Rsvg 2.0 和 GJS 的 Cairo PDF 后端。开发环境 Python 缺少系统绑定时，入口会尝试 `/usr/bin/python3`。准备 Liberation Sans 和文泉驿正黑可复现中英文版式。生成时用 Poppler 的 `pdffonts` 与 `pdftotext` 实查嵌入字体和可提取字形。复验还需要 `mutool`，查看最终版面可用 `pdftocairo`。
- `render` 写入新目录的 `figure.svg`、`figure.pdf`、`figure.html` 和 `values.json`。SVG 使用可编辑文字。PDF 按物理尺寸导出。HTML 含来源、图注和可展开数值表。交付独立 PDF 时从 HTML 一并提供图注。原始规格应保留供复算。
- `verify` 在相同渲染环境中从原始规格重算，对比实际交付物。PDF 展开对象、忽略导出时间，再对比字体和绘图对象。改过图、标签或数值表后应重新复验。
- 渲染时按实际字形检查文字越界和相互覆盖。超限先分行安排面板、缩短类别名或合理调宽。保留量纲。正式导出时按最终尺寸查看最密处，包括点的遮挡、线的交叉、组间尺度与灰度可辨性。正文通常 5–7 pt，面板字母 8 pt，以目标期刊的最新要求为准。[Nature 图稿规范](https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/)
- [传感器输入](../examples/sensor-calibration.json)在同一张图中分别展示校准散点、累积分布、带缺失格的偏差矩阵和外部模型给出的区间。矩阵图标识为 `matrix-chart`。地理热点图另用 `heatmap-chart`。
