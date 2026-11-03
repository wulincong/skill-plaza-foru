# 021 · 共享图表与城市热点图 Skill

- 状态：已实现（2026-09-29 初期以子模块整合；2026-11-03 按用户决定转为主仓库内置目录，21 个文件原样保留，迁移与验证见 092）。以下早期实现细节保留为设计来源，当前分发方式以 092 为准。
- 动机：柱状图、折线图、直方图、堆叠柱状图、地图和城市热点图规则此前散落在 career-guidance 子仓库、主仓库 reports 和提示词中；需要统一维护，并为岗位需求分析增加条件化城市热点图。
- 约定细节：初期新增 `.agents/skills/chart-visualization` 子模块，指向本地共享仓库提交 `1f9e20a`；包含 `SKILL.md`、`references/common-rules.md`、六类图表规则、广东省 21 城和浙江省 11 城编码映射、按省份 registry/manifest 管理的离线 GeoJSON、资源说明/校验脚本和无气泡示例。资源校验入口为 `.agents/skills/chart-visualization/scripts/validate-resources.mjs`，当前覆盖广东和浙江两省，边界许可状态待核实。career-guidance 子模块提交 `4dbcc6c` 固定中国目标地点先解析 registry，成功图表标识为 `data-chart-skill="heatmap-chart" data-chart-id="CH_CITY"` 和 `limit=20`，查询失败可用 `data-chart-status="unassessed"` 状态块并给出原因；`web/server/lib/skills.ts` 与 `piRunner.ts` 提示同步该分支。`web/server/lib/htmlReport.ts:100-180` 校验 figure 标记、CH_CITY、成功 SVG 可访问性和失败原因，`web/server/index.ts:752-758` 将摘要写入 recorder note 与 `RunRecord.report.html`，不阻塞用户报告展示。
- 成本与取舍：多一个共享 Skill 子模块和一个待创建的远端仓库；换取所有图表规则、可访问性、来源口径和地图边界约束集中维护。热点图采用行政区填色而非气泡，避免绝对数量视觉误导；无标准边界或城市范围不明时不生成地图。
- 验证：`node scripts/validate-resources.mjs` 返回广东 21/21/42、浙江 11/11/22 匹配，资源子仓库 `git diff --check` 通过；`cd web && npm run build` 通过；`cd web && node --experimental-strip-types --test server/lib/htmlReport.test.ts`（6 项）通过。Pi 的 Skill 展开和认证探测通过，但外部模型请求最终 `Connection error`，真实报告仍待模型网络恢复。
- 后续扩展路线：原远端推送待办已由 092 的主仓库内置方式替代，后续图表规范随主仓库维护。继续完成边界来源许可复核；按 registry/manifest 校验格式增加其他省份或全国资源；将跨城市查询提供的同口径总量接入后再稳定生成“其他”汇总。

## 2026-11-03 · 中文选图与示例校验（已实现）

- 现在由 `.agents/skills/chart-visualization/SKILL.md:8-23` 按问题和输入索引八类图，含后续加入的雷达图、桑基图。共用的图注、图标识和未评估规则集中在 `references/common-rules.md:3-14`。柱状图和折线图的可打开样例从各自说明链接，模拟数据已标明。
- 原热点图 JSON 中的汇总与行数值不符，成品还把 5 个有 1–3 条记录的城市画成了缺失色。`references/heatmap-chart.md:10-47` 现用小样本说明汇总、实测零值、缺行和范围外城市。历史广东成品保留查询日和 669 条记录，明确快照日未记录。HTML 内嵌与独立下载共用相同的 SVG 图形，两个文件均可离线打开。
- 维护时沿用静态示例，不引入运行时渲染依赖。`scripts/check-examples.py:16-65` 核对示例汇总、两份 SVG 的一致性，以及每个城市的数值、缺失状态和实际填色。行政区资源仍使用原 Node 校验。
- 验证通过：技能格式、11 份文档的 26 个相对链接、3 项热点图示例检查、2 个省份资源包、12 项 HTML 报告回归。3 个示例及热点图失败图块通过报告校验。Chrome 在 390 和 1024 像素宽度下均能解析图名和描述，文字未越出画布。在线模型生成完整报告的效果本轮未测。

## 2026-11-03 · 独立科研图稿生成与复验（已实现）

**动机**。既有 HTML 校验能识别图块，却会接受把数值 6 的柱长画成 2 的图。通用统计图需要能从非岗位数据单独生成，且保留可以复算的数值、最终尺寸与编辑能力。

**输入与边界**。技能内的 `references/figure-spec.md:25-48` 和 `scripts/figure_data.py:55-165` 定义 `figure/1`。每个面板映射本地具名表的列，共有 12 种可执行面板。配对用组、对象 ID 和阶段建立身份，每组区分登记数及完整数。组内变化中位数的双侧区间使用次序统计量，独立观测是显式前提，少于 6 个完整配对时省略区间。外部模型的区间单独声明方法。旧报告可继续嵌入 HTML 图块，地理热点专用的 `CH_CITY` 与统计矩阵分别标识。

**成品与成本**。`scripts/figure.py:94-169` 负责从规格生成、校验并发布整个目录，复验时重算 SVG、PDF、HTML 及数值 JSON。`scripts/figure_svg.py:368-418` 按毫米布局，使用 librsvg 度量各面板内实际字形，GJS/Cairo 导出矢量 PDF。Poppler 检查嵌入的 TrueType 字体和可提取文字。使用系统已有的 Linux 组件使渲染器可以脱离项目、业务 Skill 和数据库运行。手写 SVG 难以复算，单纯检查标签也无法验收几何数值，因此保留原有专题说明，将常用统计图交由独立入口生成。离线打开成品仍只需要普通浏览器或 PDF 阅读器。重放要求同一套渲染库及字体。

**验证**。在仓库外仅拷贝本技能并清空继承环境，系统 Python 成功为未收入示例的中文涂层试验出图、复验。6/7 配对组的中位变化为 −0.5 GU，区间为 [−3, 2] GU，2/2 配对组仅给出 +3.5 GU 的中位数。可从数值表追溯缺测的试件 J07。技能目录下 `python3 scripts/check-figures.py` 的 16 项覆盖实际几何、缺失、区间、共享尺度、越界及篡改复验，含将 6 的柱长改成 2 的反例。`check-examples.py` 的 4 项、区域资源的 2 个包和服务端 12 项 HTML 回归通过。单栏与双栏 PDF 已栅格预览。89 × 156 mm 的中文图通过物理尺寸、字体、可提取文字及无嵌入位图检查。五份 HTML 在 Chrome 的 390 和 1024 px 视口通过文字边界及整页溢出核对。

**后续适用范围**。雷达、桑基、堆叠及地理专题仍使用原独立指南。新增可执行面板时需给出原始数据、可复算的视觉编码及反例。目标期刊的具体版式要求、真实研究的抽样设计和编辑审稿结论需逐稿核实。
