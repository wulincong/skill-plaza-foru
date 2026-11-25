# 123 · 智能分班技能：确定性求解、审计留痕与一次受控重掷

**状态**　求解器、接入与回归已实现；真实 Pi 端到端验收进行中（结果见文末验证节，未完成项如实标注）。

## 动机

T07 面向教务处与产业学院教学秘书：中小学均衡分班软件成熟，但高职的方向分流与分层教学分班缺专用工具，且教务场景要求公平可审计（随机种子留档、日志不可篡改、结果可复现、公示前允许一次重掷）。语言模型不能直接心算分班——几百人的多目标求解既不可审计也不可复现，因此全部计算固化为纯标准库 Python 脚本，模型只负责字段核对、参数组装、摘要呈现与报告交接。

## 实现与接入点

- 技能包 `.agents/skills/class-placement/`：`SKILL.md` 定流程（读名单→字段检查→求解→决策卡→report-rendering 交付）；`references/solver-contract.md` 是 params/students/result 的 schema 与重掷状态机，`references/delivery.md` 是报告口径、隐私规则与验收清单；`docs/index.md` 为公开指南（含设计参考），`examples/sample-roster.csv` 为 60 人示例名单。
- `scripts/read_roster.py`：CSV/XLSX（zipfile+xml 标准库解析）→ 规范化 students.json，stdout 打印字段完整性报告（缺失计数按源数据口径，占位编号不计入）。列名同义词识别 + `--map 列名=字段` 手工映射；志愿支持单列分隔与志愿1/志愿2 多列。
- `scripts/assign.py`（solver 1.0.0）：
  - **均衡模式**：综合分 + 种子抖动后蛇形铺班（S 形折返，均值天然均衡、班内高低混合），再以可分离目标（各班维度均值/构成相对全局的偏差平方和，增量评估）做最优改进交换；候选对按综合分尾部 + 分类维度余缺定向（全对枚举 O(U²) 在 400 人实测 65s 不可用，定向化后 3s）。**只交换同规模单元**，各班人数保持初解 ±1——首轮真实运行曾暴露不等大小交换使班额漂移到 19/11/10/20，同时修复了折返游标错位（折返班应连续获得两单元）；修复后 60 人 4 班为 15/15/16/14（±1 来自双胞胎单元）。回避约束在搜索中按班 id 集合索引强制，同班约束合并为不可拆单元。
  - **分层模式**：assessment 向量标准化后 k-means++（固定种子）分 L 层（默认 3）；方向层名额 = 方向容量 × 全局层占比（最大余数法），志愿按固定随机序逐生申请（方向,层）名额，未满足区分「班级容量已满」与「X 层名额已满（画像分布不匹配）」；方向内按层人数递减装箱（整层独占班，装不下的余量轮转摊入余位班，layer_mixed 留痕），班名 `{方向}{序号}班`、层构成进元数据。
  - **审计**：`audit/manifest.json`（seed/effectiveSeed/attempt/paramsSha256/studentsSha256/inputFingerprint/resultSha256/reproduceCommand）+ `audit/solver-log.jsonl` 哈希链（每条含前条哈希，manifest.solverLogHead 为链头）。指纹按 params 去掉 attempt 后与学生名单联合计算——attempt 是控制字段不是问题定义。
  - **一次受控重掷状态机**：状态文件 `output/placement-state.json`；同一指纹 attempt 2 必须先有 attempt 1，attempt 2 后拒绝一切重掷；改参数/名单即新任务从 1 开始；`--fresh-state` 供复现与演示跳过校验。复现口径：同输入+同种子+--fresh-state 得到相同分班（result.json 除 generatedAt 外一致）。
  - 名册输出 `roster/`：每班 CSV（utf-8-sig）+ roster-all.csv；`scripts/make_files_manifest.py` 生成 register_delivery.py 的 `--files-from` 清单（名册+result+审计，中文公示名）。
- 接入：`web/server/lib/skills.ts:146` 伴生挂载 chart-visualization + report-rendering（沿 122 引入的 SKILL_COMPANION_MOUNTS 表）；`:149` CLASS_PLACEMENT_TURN_SUFFIX 逐轮重申脚本优先/决策卡/重掷/交付规则；`:184` SKILL_PROMPTS；`:223` INSTALLED_SKILLS。`web/server/lib/piRunner.ts:739` 注入每轮后缀。前端 `web/src/data/skills.ts` 详情条目与 `web/src/data/useTaskConfigs.ts` 分班工作台表单（名单必传 .csv/.xlsx，上传白名单由并行改动扩至 csv/xlsx）。
- 决策卡走通用 plaza-question 通道（095 机制），不新增服务端分支；交付走通用 delivery.json 通道（captureDelivery 的 readDeliveryManifest 分支），不加 HTML_REPORT_CONTRACTS。

## 成本与取舍

- **纯标准库**：沙箱 Python 无 openpyxl/numpy，XLSX 读取用 zipfile+xml 手写（测试覆盖共享字符串/内联/多表），名册输出 CSV（utf-8-sig Excel 直开）而非 xlsx；如需 xlsx 输出再评估引入依赖。
- **定向候选局部搜索**替代全对枚举或精确求解：均衡质量由回归阈值兜底（160 人 4 班均值差 <3 分、性别差 <8pp、班内 std > 0.85×全局），不追求最优解——阳光分班要求的是可解释的均衡而非数学最优。
- **层名额按全局占比**而非各方向实际需求：保证每个方向 A/B/C 层都有预留座（分层教学可开齐），代价是方向需求偏离全局时产生更多混班；混班如实留痕呈现，不静默。
- **attempt 排除出指纹**：否则重掷会因 params 里 attempt 字段不同被当成新任务，状态机失效。
- 与 teaching-diagnosis（122）同批接入：两者共用伴生挂载表、决策卡与 report-rendering 交付约定，本技能未引入新的平台机制。

## 验证

- `python3 .agents/skills/class-placement/scripts/test_assign.py`：10 项全过——均衡质量与确定性（同种子逐字节一致、异种子不同解、班额 ±1 等额断言）、同班/回避约束、重掷链（未首解拒绝重掷、重复首解拒绝、重掷后拒绝第三次、参数变化重置、--fresh-state 复现一致）、日志哈希链逐条核对、分层全覆盖/容量/画像同质/志愿口径、分层缺画像拒绝、CSV/XLSX 读取与手工映射。
- 规模：均衡 400 人 8 班 3.0s（定向候选优化后；优化前全对枚举 >300s），分层 400 人 9 班 0.05s。
- `npm run docs:check`（20 技能 23 页）、`vue-tsc && vite build`、服务端 `delivery-api` 9 项 + lib 58 项 + docs 插件 3 项全部通过；重启后端后 `/api/health` 与 `/api/skills` 均含 class-placement（installed=true）。
- 真实 Pi 端到端（youcai 模型，会话 `e2e-t07c-121343`，均衡模式 60 人 4 班 + 双胞胎约束）：首轮实际运行读取与求解脚本，摘要给出等额班额（每班 15 人）、成绩均值差 0.027 分、女生比例差 6.67%、班内 std 58.04≈总体 58.12、双胞胎同班满足，并输出确认/重掷单选决策卡；确认后经 report-rendering 交付网页（两幅图块：`score-distribution` 成绩分布、`gender-composition` 性别构成，均带图注、来源与可展开数值表）与 8 个下载项（4 份班级名册、全员名册、result.json、审计清单、哈希链日志）。首轮交付（`e2e-t07-115719`）产物实测：求解日志哈希链逐条校验通过、manifest.solverLogHead 与 resultSha256 吻合、按 reproduceCommand 在空目录复现得到一致分班。验收网页结构含公示建议（编号与姓名公示、敏感字段不公开）与复核方法（种子+指纹复现）。
- 验收暴露并修复的三个问题：①蛇形折返游标错位 + 不等大小单元交换使班额漂移（首轮 19/11/10/20）——改为折返班连续获得两单元、只交换同规模单元，班额回到 ±1；算法变更随 SOLVER_VERSION 1.0.0→1.1.0 升级（复现以版本为前提，老产物标 1.0.0 属旧算法）。②首轮报告只有数值表没有统计图——逐轮规则明确每维度至少一幅图并以完整图块嵌入，index.ts 的 captureDelivery 为 class-placement 挂共享 checkReportWebEntry（无指标口径，校验图块结构完整性）。③模型两次以"计划"一句话收尾（无工具调用）——index.ts 新增 missingPlacementSolve 续跑闸门：无决策卡且无交付时自动续跑一次，决策卡答复轮要求推进到交付、普通轮看是否已有求解产物（避免对随问答疑误触发）。
- 验收边界：分层模式与重掷路径经脚本单测覆盖，未做真实模型整链复验；浏览器可视化验收工具本会话不可用，前端以 vue-tsc/构建、bundle 内容（表单/指南/摘要）与 /api/skills 断言代替。

## 后续扩展路线

- 分层模式与重掷路径的真实模型端到端复验（本轮验收先跑均衡确认链）。
- T12 岗位胜任力测评上线后，assessment 字段直接对接其测评结果导出。
- 结果对比：上次分班结果目前只做人工对照说明，后续可在 result.json 增加 drift 统计。
