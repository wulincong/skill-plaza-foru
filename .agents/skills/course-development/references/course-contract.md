# course.json 结构与证据交接

`course.json` 由本技能编写，是课程包的可校验结构契约（`course-package/1`）。岗位口径、JD 抽样与指标绑定由 [人才数据库查询](../../talent-data-query/SKILL.md) 定义，以查询工件为准；三栏对齐、双向挂接、权重与合格标准等硬规则由 `scripts/course.py` 校验，契约里不手填脚本可计算的汇总。

## 顶层字段

```json
{
  "schema": "course-package/1",
  "status": "draft",
  "asOf": "2026-11-18",
  "meta": {},
  "sources": [],
  "metrics": [],
  "workTasks": [],
  "learningUnits": [],
  "outline": [],
  "knowledgePoints": [],
  "lessonSamples": [],
  "trainingTasks": [],
  "assessmentPlan": {},
  "resourceGaps": [],
  "complianceChecks": [],
  "decisions": [],
  "openDecisions": []
}
```

`status` 为 draft/final；存在未决决策或待核对标准时只能是 draft。

## meta

```json
{
  "courseName": "Hadoop 大数据平台运维",
  "courseId": "CS1",
  "positioning": "专业核心课，面向数据平台运维岗位群……",
  "major": {"name": "大数据技术", "code": "510205"},
  "programVersion": "2026-1",
  "sourcePackage": "uploads/t05-package.json",
  "targetPositions": [{"name": "大数据运维工程师", "sourceIds": ["S_T05"]}],
  "region": {"level": "province", "name": "广东"},
  "industryScope": {"name": "机器人", "resolvedId": "15"},
  "weeks": 18,
  "totalHours": 72,
  "theoryHours": 40,
  "practiceHours": 32,
  "semester": 3,
  "credits": 4.5,
  "periodMinutes": 45,
  "studentStart": "已修 Linux 基础（user: 学生起点说明）",
  "assessmentForm": "考试"
}
```

`sourcePackage` 指向 T03 培养方案生成的课程开发任务包（`t05-course-development/1`，见[任务包契约](../../training-program-design/references/t05-package.md)）时，courseId 必填，课程名、理论/实践课时、学分、学期、考核形式与任务包逐项一致；直接开发（无任务包）时 sourcePackage 省略，courseName/positioning/targetPositions/weeks/totalHours/semester 必填。`theoryHours + practiceHours` 必须等于 `totalHours`，`weeks` 为 16–18。

## sources 与 metrics（与培养方案同构）

`sources` 含 id、title、publisher、url、published、accessed、locator、scope、excerpt。共享统计的 url 填工作区 `data/tq-…/result.json`，构建脚本回填 contentHash 与 dataReadAt；用户附件用 `uploads/` 相对路径，粘贴材料用 `user:` 加名称，excerpt 逐字摘录原句。`metrics` 含 id、label、value、unit、definition、source_ids；直接引用查询结果的指标加 `binding`（如 `{"metricId":"robot/description.samples","field":"value"}`），写稿时可省略 value，脚本从已校验工件填入，手填数值与工件不符会校验失败。规则与培养方案 [结构契约](../../training-program-design/references/program-contract.md) 一致。

## workTasks（典型工作任务，JD 原文驱动）

```json
{
  "id": "WT1",
  "name": "集群部署与监控",
  "jdRefs": [{"positionId": "14600406343483407", "hash": "sha256…", "quote": "负责物流运输机器人的系统开发"}],
  "sourceIds": []
}
```

任务表述必须可回溯：`jdRefs` 引用 description.samples 返回样本的 positionId 与脱敏摘录指纹（hash），`quote` 逐字摘录该样本原文（校验为子串）；没有库内样本时改用 `sourceIds` 指向用户材料并说明。**禁止用模型常识补充任务表述、岗位事实或设备型号。**每个 workTask 必须被至少一个学习单元覆盖。

## learningUnits 与 outline（模块与三栏对齐）

```json
{"id": "M1", "name": "平台部署", "actionDomain": "部署与实施行动领域", "weeks": [1, 2, 3, 4], "hours": 16, "taskIds": ["WT1"]}
```

```json
{"week": 1, "unitId": "M1", "content": "分布式存储原理与集群规划", "task": "完成 3 节点集群规划", "assessment": "课堂实操检查单"}
```

`outline` 逐周覆盖 1..weeks 各一次，内容、任务、评价三栏非空；各单元 hours 合计必须等于 totalHours。学习单元按行动领域归纳典型工作任务，不按学科章节拼凑。

## knowledgePoints（双向对齐，硬规则）

```json
{
  "id": "K1",
  "type": "skill",
  "text": "能完成 Hadoop 集群部署与基础调优",
  "capabilityId": "C-OPS-1",
  "unitId": "M1",
  "assessmentPoint": {"form": "实操", "criteria": "集群一键拉起且服务全绿", "passStandard": "45 分钟内独立完成"},
  "sourceIds": ["S_T05"]
}
```

每个知识点/技能点必须**上挂能力项**（任务包 capabilityRefs 的 capabilityId，或用户材料来源的能力项并给 sourceIds）且**下接考核点**（assessmentPoint 的 form/criteria/passStandard 三项齐全）。无考核点或无能力项挂接的知识点校验失败，不得进入大纲。任务包中 level=H 的能力项未被任何知识点支撑时告警。每个学习单元至少一个知识点。

## lessonSamples 与 trainingTasks（前两个模块成套）

```json
{"unitId": "M1", "title": "第 1 周单元教学设计", "hours": 4, "stages": [{"phase": "导入", "minutes": 15, "teacher": "…", "student": "…"}]}
```

```json
{
  "id": "T1",
  "unitId": "M1",
  "title": "Hadoop 集群部署实训",
  "background": "…",
  "requirements": ["…"],
  "deliverables": ["部署报告"],
  "scoring": [{"item": "集群可用性", "weight": 60, "standard": "服务全绿且重启不失效"}],
  "passStandard": "总分≥60",
  "safetyNotes": ["涉电设备断电操作"]
}
```

前两个学习单元（按顺序）各至少一份单元教学设计样例与一份实训任务书。教学环节分钟数合计与课时对应（periodMinutes，默认 45，超出告警）；实训评分权重合计 100，合格标准必填；涉及设备操作、用电用火、化学品而缺安全注意事项时告警并列入待确认。

## assessmentPlan（可执行评价方案）

```json
{"forms": [{"form": "过程考核", "weight": 40, "points": ["K1"], "method": "实训检查单逐项评分"}], "passStandard": "总评≥60 且实操单项≥60", "resit": "补考重做综合实训"}
```

各形式权重合计必须等于 100；points 引用存在的知识点 id；每种形式写明评分方法，课程级合格标准必填。

## resourceGaps（缺口清单）

```json
{"type": "generated", "item": "模块一实训指导书", "consumer": "courseware-studio", "note": "以本包实训任务书为输入"}
```

type 为 generated（注明下游技能与所需输入，课件类交 [courseware-studio](../../courseware-studio/SKILL.md)，其材料范围是教案与实训指导书）或 manual（人工准备）。不编造已有资源。

## complianceChecks（标准合规逐条核对）

```json
{"item": "课程定位与专业教学标准课程设置对接", "standardExcerpt": "专业核心课程应开出……", "sourceId": "S_STD", "courseRef": "M1", "status": "conform", "suggestion": null}
```

status 为 conform/conflict/pending。conform 与 conflict 必须附原文摘录并可回查来源（知识库 locator、用户材料或授权检索的官方 URL 与访问日期）；conflict 必须给建议，不静默改写课程内容；pending 条目在 status=final 时需要一条 scope=standards 的 decisions 授权。**禁止凭记忆编写标准条文。**

## decisions 与 openDecisions

```json
{"id": "D1", "question": "目标岗位库内样本不足，是否扩大产业范围？", "userReply": "扩大到整个机器人产业", "scope": "evidence", "askedAt": "2026-11-18"}
```

关键取舍（样本不足、合规冲突处理、模块与考核结构）必须留痕，userReply 为用户原话；会话内提供 course-input.json 时脚本回查原话出处，对不上校验失败。`openDecisions` 列尚未回答的问题（question + options），status=final 时必须为空。

## 构建产物

`python3 <技能目录>/scripts/course.py build course.json` 在校验全部通过后，把以下文件写入 `output/course-<短哈希>/`：

| 文件 | 内容 |
|---|---|
| course.md | 课程正文（课程定位与设计依据、整体设计三栏表、知识点清单、单元设计样例、实训任务书、评价方案、资源缺口、合规核对、决策与未决事项） |
| course.json | 回填指标数值与指纹后的结构化课程包 |
| validation.json | 硬规则校验结果、告警与统计 |
| course-files.json | 交付登记清单（name/path/sha256），供 register_delivery.py --files-from 使用 |

校验失败时 build 阻断并列出全部不达标项；修数后重跑。修订一律改 course.json 再重建，不手改产物。正文与结构化内容同源，交 [report-rendering](../../report-rendering/SKILL.md) 渲染网页。
