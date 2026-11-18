# 124 · training-program-design：产教培养方案技能、红线校验与 T05 任务包

**状态**：已实现（21 项离线单测、服务端测试、接口与文档收录验证通过；真实 Pi 端到端样例待运行）。

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

## 后续路线

- 真实样例端到端（用户配合决策卡答复）→ 回填本记录验证节。
- 沙箱凭据注入后启用 weknora 原生检索路径；T05 课程开发技能消费任务包的对接约定。
- 证书-学分折算表、第二课堂学分等真实方案常见要素未入 v1 契约，按院校需求扩展。
