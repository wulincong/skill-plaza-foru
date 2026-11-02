# 研究基准与借鉴清单（V3 起 Skill 的对齐目标）

> 来源：FT Visual Vocabulary、BBC rcookbook、UK GOV.AI 岗位空缺分析、LinkedIn Economic Graph、Lightcast AI Heatmap、Quarto、Evidence、Observable Framework、Stanford AI Index、WEF FoJ。
> 用法：写报告结构/选图/措辞前先对照本表；每个"我们采用"条目都已在代码或文档中落地，标注了落点。

## 一、报告结构（学 UK GOV / LinkedIn / Lightcast）

| 基准做法 | 来源 | 我们采用 | 落点 |
|---|---|---|---|
| 执行摘要全部量化：体量、份额、溢价、变化 | UK GOV | 01 核心发现每条带数 | gen_outline 01 |
| 分类体系先行（Experts/Specialists/Implementers 三层，先定义再分析，明示不可相加） | UK GOV | 赛道互斥口径 + 岗位族群在"研究范围与方法"先定义 | 12 方法页 |
| 技能/学历/经验合并成"门槛"一章，而不是三个孤立章节 | UK GOV | 08 学历×经验准入矩阵（职教可进入区域框出） | render matrix + fetch edu_exp |
| 每图每表下印 Source 与 Base（样本量+周期） | UK GOV | 图下来源行：来源：优才知路平台数据库｜N=…｜周期… | render_report src line |
| 告诫紧贴受影响数据，不埋进附录 | UK GOV | 图 Note 一行 + 局限紧随结论段 | outline note |
| 完整检索逻辑进附录，可复现 | UK GOV | provenance 快照 + verify 审计 | fetch/verify |
| 报告一句话摘要写成"结论"而非"主题" | LinkedIn | 大纲 meta.message + 文章 digest | gen_outline/build_article |
| 方法论独立成篇（不混入正文） | LinkedIn | 12 研究范围与方法（口径集中） | gen_outline 12 |
| 按受众组织洞察（policymaker/employer/education/learner） | Lightcast | 面向 education provider：能力栈→岗位×技能矩阵→培养建议 | 12-15 屏 |
| 一份研究多种产品形态（Full/Summary/Infographic/Data Explorer） | WEF | 路线图：同一 outline 渲染 PDF/Web/微信（见第五节） | V4 roadmap |

## 二、图表选择（学 FT Visual Vocabulary + BBC）

**先判断关系，再选图**（chart_recommender.py 的规则来源）：

| 关系 | 首选 | 禁忌 |
|---|---|---|
| 排名 | 排序条形/棒棒糖 | 无序条形；字母序 |
| 相关 | 散点/气泡 | 双轴；暗示因果 |
| 分布 | 直方图/箱线 | — |
| 构成 | 比例堆叠条；类别≤5 可环形 | >7 类环形；精确比较用饼 |
| 极端不均衡构成（一份>85%） | 大数字卡+迷你条 | **饼/环图（标签必挤）** |
| 二维交叉 | 热力矩阵 | 用它比"精细胞差" |
| 随时间 | 折线/柱 | 面积慎用；spline 平滑离散数据 |

BBC 风格规则（render_report 落地）：条形永远排序；直接标注优先于图例；仅横向网格线；灰 #dddddd 弱化非重点、条件高亮主色；来源固定图下左；千分位分隔、百分比后缀；去掉轴线/刻度/面板底色。

## 三、叙事与语言（学 LinkedIn/UK GOV/Quarto）

1. **Message title**：标题即结论（"深圳与广州吸纳近四分之三的AI招聘需求"），不用字段名做标题。
2. **每章一个主结论**，叙事弧：结论 → 证据 → 解释 → 意义 → 边界。
3. **图前讲"为什么看"，图后讲"意味着什么"**；图文紧邻，不写"见第X屏/如上图"。
4. **括号预算**：每段 ≤1 个解释性括号；数量/单位/口径进图表、数据卡、图注或方法页。
5. **自动交叉引用**（Quarto 思想）：图/表由渲染器自动编号（图N/表N），正文不手写编号。
6. **禁止内部语言泄漏**：屏/页面/口径说明（正文）/详见后续章节/图中可以看出/值得一提的是/综合来看。

## 四、工程化（学 Quarto / Evidence / Observable）

| 思想 | 来源 | 我们采用 |
|---|---|---|
| 声明意图、延迟外观：内容是语义树，渲染决定样子 | Quarto | outline 即语义文档；renderer 只管版式 |
| 图表/章节自动编号与交叉引用 | Quarto | 渲染器自动 图N/表N |
| 报告即代码：SQL+Markdown，可 diff 可复现 | Evidence | talent-data-query 的实际 evidence（内部留档）+ outline.json（可审阅可编辑）+ 快照 |
| Agent-ready：AGENTS.md 约定 | Evidence | SKILL.md 即操作约定 |
| 数据快照在构建期生成 | Observable | output/snapshots/ |

## 五、批判性继承：暂缓项与理由

- **Quarto/Observable 全套多渲染器**：方向正确，但当前交付物只有微信长图一种，先在 outline 语义层对齐（message/claim/evidence 字段化），多格式渲染进 V4 路线图，避免半成品。
- **英国报告的时间趋势章**：其 update_time 语义干净；我们的含批量同步伪影，在字段语义确认前继续禁用趋势页（Gate 拦截）。
- **LinkedIn 的外部基准溢价算法**：需要权威基准数据源，未接入前 Gate 禁用"溢价/显著高于"。
- **WEF Data Explorer 交互版**：依赖 Web 渲染管线，进路线图。

## 六、出版级 Gate 对照（V3 verify_data）

| Gate | 规则 | 来源启发 |
|---|---|---|
| Research | 每屏标题必须是结论句（含数字或判断），非字段名 | LinkedIn/UK GOV |
| Evidence | 定量结论必须可溯源 | V2 已有 |
| Inference | 无序列/基准不得下动态/比较结论 | V2 已有 |
| Chart Choice | >85% 构成禁饼/环；>7 类禁环；排名必须有序 | FT |
| Chart Legibility | 像素核验（热力图秩相关、图表存在性） | render_check |
| Narrative | 带图屏必须有前置段落；结论先行 | UK GOV |
| Redundancy | 同屏正文同一数字重复 ≥3 次即冗余 | FT/BBC 直接标注哲学 |
| Language | 禁内部语言 + 括号预算 | 本文档第三节 |
| Publication | Source/Base 齐备；图注完整 | UK GOV |
