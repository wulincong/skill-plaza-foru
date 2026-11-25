# 128 · course-development：产教课程开发技能、T05 任务包消费与课程包硬校验

**状态**：已实现（course.py 17 项离线单测、docs:check、vue-tsc 通过；后端注册与 /api/skills 重启验证通过；真实 Pi 端到端样例待运行）。

## 动机

内容生产链第二环（蓝图 T05）：面向课程组与骨干教师，把 T03 培养方案的课程卡片开发为完整课程。差异化是「JD 原文驱动任务提炼 + 知识点双向对齐硬校验 + 课证合规逐条核对」，并落实 124 记录后续路线中的「T05 课程开发技能消费任务包的对接约定」。JD 原文能力来自 127 的 description.samples。

## 约定细节

### 契约与脚本（技能目录 `.agents/skills/course-development/`）

- `course.json` 契约 `course-package/1`（`references/course-contract.md`）：meta（含 sourcePackage 指向 `t05-course-development/1` 任务包时的逐项一致性：课程名/课时/学分/学期）、sources/metrics（与培养方案同构：tq 工件 binding 回填、`user:` 材料逐字摘录）、**workTasks.jdRefs**（positionId + 脱敏指纹 hash + 逐字 quote，校验为样本原文子串）、learningUnits/outline（模块·内容·任务·评价三栏，逐周覆盖 1–18、课时对账）、**knowledgePoints**（capabilityId 上挂 + assessmentPoint{form/criteria/passStandard} 下接，缺一不得进大纲）、lessonSamples/trainingTasks（前两个模块成套，评分权重合计 100）、assessmentPlan（权重合计 100、points 挂知识点、合格标准）、resourceGaps（generated 注明下游技能——课件类 courseware-studio 的输入是教案与实训指导书 / manual）、complianceChecks（conform/conflict/pending；conform/conflict 必须有原文摘录+可解析来源，conflict 必须给建议）、decisions（userReply 原话）与 openDecisions（final 时必须为空）。
- `scripts/course.py`：`validate`（结构 + tq 工件经共享 inspect 子进程核验 + 硬规则 + 决策原话对 course-input.json 回查）/ `build`（通过后写 course.md、course.json、validation.json、course-files.json 于 `output/course-<sha10>/`）。stdlib only，无 Word 版（v1）。
- 决策原话回查与 124 的 program-input 同构：服务端每轮写 course-input.json（runId/message/earlierMessages/uploads）。

### 平台接入点

- `web/server/lib/skills.ts`：`SKILL_PROMPTS['course-development']`、`INSTALLED_SKILLS`、`SKILL_DATA_DEPENDENCIES`（talent-data-query）、`SKILL_COMPANION_MOUNTS`（talent-data-query + chart-visualization + report-rendering）、`COURSE_DEVELOPMENT_TURN_SUFFIX`（逐轮重申：任务包复述、JD 原文硬规则、脚本阻断、决策卡、交付链）。
- `web/server/lib/piRunner.ts`：pi-tools 扩展挂载条件加本技能；buildPrompt 追加上述后缀。
- `web/server/index.ts`：`course-input.json` 与 `talent-query-turn.json` 每轮写入（复用 124 的代码形态）。
- `web/src/data/skills.ts` 富文案卡（teaching 类，「产教课程开发」）；docs/index.md 入文档中心（公开技能 15 个）。
- 交付：course.py build → 读 report-rendering 渲染网页 → `register_delivery.py --files-from output/course-<hash>/course-files.json` 登记课程包全部文件。

## 成本与取舍

- 否决 HTML_REPORT_CONTRACTS 直写 workspace/report.html：课程包是成套文档 + 结构化文件交付，走 115 内容呈现分离链（与 ier/tpd 一致）。
- 否决纯 agent 自校验：链上技能（124–126）已标准化「脚本硬校验阻断」模式，规格的双向对齐、权重合计、评价可执行、JD 指纹核对都需要机器可查；course.py 校验全内聚，交付走通用 delivery 通道，无服务端专属校验（同 124 取舍）。
- weknora 凭据未配（web/.env 无 WEKNORA_*）：标准核对按 124 同款「凭据可用→检索；否则决策卡（提供原文/授权检索官方原文/按待核对继续）」，知识库不挂载省上下文。
- 单元教学设计分钟数与课时对齐、安全注意事项、H 级能力覆盖为**告警级**（不阻断），避免过度拦截真实教学法差异。

## 后续路线

- 真实样例端到端（任务包输入 + 决策卡答复 + 网页交付）→ 回填本记录验证节。
- weknora 凭据注入后启用标准原文检索路径；合规核对表先按用户材料/授权检索运行。
- 教务系统导入格式（如特定 Excel 模板）按院校需求从 course.json 派生，另立记录。
