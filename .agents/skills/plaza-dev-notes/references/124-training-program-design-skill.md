# 124 · training-program-design：产教培养方案技能、红线校验与 T05 任务包

**状态**：已实现并经真实 Pi 端到端样例验收（2026-11-18，见「端到端实测」节）；2026-11-20 起工作流改为「本地语料为底 + 轻量取数」（见对应节）。

## 动机

平台产教融合内容生产链需要起点智能体：为高职专业负责人/教务处生成/修订产教融合专业人才培养方案。区别于全国通用模板，核心差异化是把「真实岗位库可追溯口径 + 国家专业教学标准原文核对」做成硬校验——竞品调研（2026-11-18，记录见技能 `references/research-notes.md`）显示官方 VEPPAgent 与职教桥都未同时做实这两点。定稿后自动产出 T05 课程开发任务包。

## 约定细节

### 契约与脚本（技能目录 `.agents/skills/training-program-design/`）

- `program.json` 契约 `training-program/1`（`references/program-contract.md`）：meta/sources/metrics/jobGroups/capabilityDomains/standards/cultivation/curriculum/schedule/assurance/graduation/decisions/diff/redlineOverrides。sources/metrics 与产教报告同构（tq 工件 `data/tq-…/result.json` + contentHash + binding 回填；`user:` 来源 excerpt 逐字核对）。
- `scripts/program.py`：`validate`（结构 + 证据绑定 + 红线）/`build`（校验通过后产 program.md、program.json、validation.json、t05-package.json、t05-overview.md、program.docx、program-files.json 于 `output/program-<sha10>/`）。任一红线不达标 build 退出非零并逐项说明（阻断交付）。
- 红线 R1–R12（`references/redlines.md`）：13 号文核实数字为默认（总学时 2500–2800、实践≥50%、公共基础≥25%、选修≥10%、核心课 6–8 门、实习 20–30 周、学年 40 周、学分 120–170 且落在 16–18 学时/学分换算区间 ±2）；校本要求经 `redlineOverrides`（须 providedBy 引用用户原话）覆盖。学时学分总数由脚本从课程表汇总，契约不手填。
- Word 生成走**标准库手写最小 OOXML**（zipfile+固定模板，`write_docx`）：沙箱 python 3.12 无 python-docx/matplotlib（宿主 conda 3.13 有但沙箱 PATH 固定系统 python），否决 pip 安装（跨沙箱用户不可控）。XML 良构性由单测 minidom 校验；真机 Word 打开待样例验收。
- T05 任务包 `t05-course-development/1`（`references/t05-package.md`）：每门课的能力绑定、证据索引、学时学分与设置理由，内嵌 evidenceIndex 供下游回查，不重新取数。

### 平台接入点

- `web/server/lib/skills.ts`：`SKILL_PROMPTS['training-program-design']`、`INSTALLED_SKILLS`、`SKILL_DATA_DEPENDENCIES`、`SKILL_COMPANION_MOUNTS`（talent-data-query + chart-visualization + report-rendering）、`TRAINING_PROGRAM_TURN_SUFFIX`（红线阻断/决策卡/原文核对逐轮重申）。
- `web/server/lib/piRunner.ts`：pi-tools 扩展挂载条件扩展为本技能与 industry（talent_query 原生工具必需）；buildPrompt 追加上述后缀。
- `web/server/index.ts`：早前用户消息收集（industryUserSources 持久化）扩展到本技能；turnPrompt 写 `program-input.json`（runId/message/earlierMessages/uploads，供 program.py 核对决策 userReply 与 user: excerpt）与 `talent-query-turn.json`（pi-tools.mjs 强制要求的回合上下文）。
- `web/src/data/skills.ts` 富文案条目（卡名「产教培养方案设计」）；docs/index.md 已入文档中心（docs:check 通过，链接只允许同目录 md 或完整 URL）。
- 交付走通用 delivery.json 通道：`register_delivery.py <web目录> --files-from output/program-<hash>/program-files.json`，**无服务端专属校验**（否决仿 industryDelivery 四原件收据：本技能无纯呈现修订复用场景，校验全部内聚在 program.py）。

## 成本与取舍

- 决策卡授权靠 decisions.userReply 原话 + program-input.json 回查（有会话上下文时强制）；离线无上下文时跳过原话校验——与 industry continue_quote 同等强度，未做服务端 projectReply 映射。
- weknora 标准核对：沙箱无 WEKNORA 凭据（web/.env 未配），SKILL 按「凭据可用→检索；否则决策卡（提供原文/授权检索官方公开原文/按待核对继续）」设计，知识库未挂载（省上下文），调用语法写在 `references/standards-check.md`，未来宿主注入凭据即可启用。
- R12 双课程支撑为警告级（通行「无遗漏、无冗余」校验取建议强度，避免过度阻断）；单课学时学分比 14–30 区间外同样仅警告。
- 「三年一修订」不写入方案（非 13 号文条款，出自十四五规划教材文件与院校惯例），正文表述为动态调整机制。

## 端到端实测（2026-11-18）

真实广场会话（sess-tpd-e2e1，大数据技术 510205·广东省·云计算与大数据链，youcai 模型）完成全链路并经两轮修订交付：

- **决策卡链路**：4 张卡真实触发（产业口径确认、取数失败处理、旧版材料/标准原文获取、草稿确认），答复经 `answerTo` 续入原会话；decisions 留痕用户原话。
- **取数与绑定**：talent_query 成功（广东省 22581 岗位、学历分布、薪酬中位 15.5K），工件 `data/tq-14b48381…/`，program.json 以 `sample_1/positions.count` binding 回填核验。
- **红线阻断真实生效**：初版 validate 报 7 类不达标（总学时 1312、公共基础 17.7%、选修 7.3%、rationale 缺绑定等），模型多轮调整至全过（2608 学时、实践 60.7%、公共 25.8%、选修 11.7%、核心 7 门、145.5 学分、实习 26 周）后 build 才通过。
- **交付**：`output/program-146b28fd1f/` 六件产物（program.md 161 行表格、42KB program.json、validation.json、t05-package.json、真实 Word 文件 file 命令识别 Microsoft Word 2007+）；经 report-rendering + register_delivery 发布公网网页与 6 份下载（终版 delivery b69dcd4b…，网页 24.8KB 含全部课程表与红线对照）。
- **降级路径修正**：实测暴露契约缺陷——标准待核对时无来源可指，模型曾用查询来源冒名。已修：`program.py` standards pending 条目 sourceId 可省、cultivation.goalBasis 降级时免 standardSourceId（须 standards 决策），新增回归测试（22 项全绿）。
- **模型可用性发现**：手写 27 门课 JSON 曾耗尽一轮放弃，需夹具样例引导一次写全（SKILL.md 已写入指引）；网页首两版为摘要级，需明确「全文渲染、禁止详见占位」（SKILL.md 已强化）。
- **环境干扰（非本技能缺陷）**：并行开发会话（zjf）中途重启后端两次，杀掉两轮在途运行；会话文件曾被外部清空一次。重发即可恢复，`--continue` 会话上下文未丢。

## 本地语料为底（2026-11-20 起）

数据使用方式调整：对标参考以仓库内置培养方案语料库为主路径，取数降为轻量补充。

- 语料库：`data/人才培养方案/`（git 忽略，不进版本库），696 份清洗全文 TXT，按五方向组织（人工智能 389/智能制造 152/数字商科 127/智能网联汽车 27/具身智能 1），`索引.csv` 含 sha256 与标题（来源见库内 README 与 2026-11-20 探查记录）。无专业/学制/院校结构化分类，从文件名与标题解析。
- `corpus:` 来源类型（`program.py` corpus_index/corpus 分支）：url 为 `corpus:方向/文件名.txt`，校验索引登记、文件 sha256 与 excerpt 原句，title/publisher/published/accessed 空缺按索引与入库日（2026-11-20）回填；用于 rationale/goalBasis/diff 的对标引用。**不可作岗位需求证据（R9 仍要指标或用户材料）、不可作实施保障来源**；accessed=入库日，早于入库日的 as_of 引用语料会被截止日校验拦下（语义正确）。
- 工作流：查索引→按方向过滤→标题贴近选 3–5 份同类 + 1 份跨层次对照→精读提炼结构/课程体系/学时比例/表述→逐份登记 corpus: 来源。岗位证据一次 talent_query 取齐（同口径复用）或走用户材料；能力项缺口按原 user-material/insufficient 规则，不为凑证据反复取数。SKILL.md「本地语料为底/补充取证（轻量）」两段、skills.ts TRAINING_PROGRAM_TURN_SUFFIX 与 SKILL_PROMPTS 条目同步改写。
- 取舍：否决「能力项允许 corpus 证据」——同类方案的岗位判断不是本区域岗位需求事实，会架空 R9 的证据规则；否决「按专业名预建结构化映射」——696 份标题解析规则不稳定，先由选样时按需解析，映射质量需求出现后再建。
- 验证：26 项单测（含临时语料夹具三态 + 真实索引完整性集成）；真实索引选样（人工智能 389→标题过滤→三年制样本）+ corpus 来源 validate 通过；零查询纯语料+用户材料路径 validate 全绿。后端已重启加载新后缀。

## 后续路线

- 沙箱凭据注入后启用 weknora 原生检索路径；T05 课程开发技能消费任务包的对接约定。
- 证书-学分折算表、第二课堂学分等真实方案常见要素未入 v1 契约，按院校需求扩展。
- 网页全文渲染的稳定性可考虑在 register 侧加「正文表格完整性」检查（当前靠 SKILL 指令约束）。
