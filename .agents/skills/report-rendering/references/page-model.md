# 内部页面模型

此模型由 Agent 生成，外部输入接受任意 Markdown、JSON 或普通文字。新业务 JSON 先理解关系再映射，未映射的有用内容保留，避免静默丢失。

```json
{
  "title":"下季度实训安排", "eyebrow":"教学工作简报", "meta":["秋季"],
  "blocks":[
    {"type":"summary", "lead":"先核对排课，再确定增班。", "text":"现有班次占满上午时段。", "note":"下午安排尚未提供。"},
    {"type":"section", "title":"已知条件", "blocks":[
      {"type":"text", "text":"用户提供 **20 个工位**，每班计划 18 人。"},
      {"type":"table", "pattern":"key-value", "title":"实训条件", "columns":[{"label":"条件"},{"label":"值"}], "rows":[["工位",20],["每班人数",18]], "source":"用户提供的实训说明"}
    ]}
  ]
}
```

普通文字识别标题、正文、列表与引用。Markdown 保留标题层级、列表、引用、表格、链接和代码；脚本可直接渲染 .md/.txt 为基础页面。需要摘要和图文组合时由 Agent 提取后组装，原稿留在公开目录之外。

JSON 对象数组通常映射行表，嵌套对象按含义变成键值表或章节，长文本保持正文。数据带对象和单位才适合提升为指标。脚本消费整理后的内部模型，新 JSON 形状由 Agent 理解转换。

产教报告按已构建 sections.claim_ids 顺序映射，保留 claim 的 text、basis、implication、limitation 和来源；recommendation 的 owner、next_step、condition、verification 映射到行动段落或 actions 元素。逐章记录内容映射，不能只提取摘要和总量。metrics 从同轮 build 成品读取，gaps 进入限制或未决事项。业务稿提供内容与证据，不要求提供 charts、图型或页面结构。

制作统计图时，从 metrics 选取支撑相关判断的数据。标量使用 value 和 unit；分布使用 breakdown.groups 的 label、count、share，并保留 breakdown.denominator、returnedGroups 和实际展示组数。分布指标的 value 可能是总分母，不能当成某个分组的值；缺测不补零，多指标比较先核对时期、单位和样本。图注附指标编号、公开来源与定位，查询内部路径留在工作区。图稿规格、选型、绘制与复验全部在本技能调用 chart-visualization 的流程中处理。

| type | 字段 | 用法 |
| --- | --- | --- |
| section | title、blocks、可选 label | 章节，可嵌套，标题层级递增 |
| text | text | 段落、列表或 Markdown 表格 |
| summary | lead、text、note | 重点结论、依据、限制 |
| metrics | items，每项 label、value、unit、note、可选 tone=attention | 数字可保留格式化字符串 |
| quote | text、source | 原文与出处 |
| callout | text、tone=attention/neutral | 条件或解释 |
| table | title、pattern、columns、rows、note、source、missing_label | columns 含 label、可选 numeric、row_header；rows 为单元格数组 |
| actions | items，每项 title、text、owner、when、condition | 顺序行动卡 |
| sources | items，每项 label、text、url、可选 id | 公开 HTTP(S) 链接可点击；内部路径用可公开出处代替 |
| figure | spec、bundle | figure/1 规格与 render 输出目录，嵌入前 verify |

通用可选 id 为页内唯一、英文字母开头的字母数字下划线连字符。title 可选，section 与表格应有可读标题。文字支持 Markdown，HTML 原文以文字显示。图稿相对路径以 page.json 所在目录为基准。顶层 theme 默认 paper，可由命令行覆盖；subtitle、meta、footer 可选。

脚本依赖 Python 3 与 markdown-it-py，复验依赖兄弟 chart-visualization 的工具链。输出采用新目录，成功后原子就位。内部错误由 Agent 修复，特殊布局可用同一 CSS 写 HTML。

内部复核记录逐项列出章节、claims 与主要指标在页面中的位置，以及图表选型或未绘制的具体原因。复核内容留在工作区；读者页面展示业务结论、数据、条件与来源。
