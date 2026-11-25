---
name: 产教课程开发
description: 为课程组与骨干教师把培养方案课程卡片开发为完整课程：JD 原文抽样驱动典型工作任务、知识点上挂能力项下接考核点、标准合规逐条核对，交付课程包网页与结构化课程包。岗位统计与 JD 抽样由 talent-data-query 提供，呈现交给 report-rendering。
---

# 产教课程开发

**交付目标。** 按[课程包契约](references/course-contract.md)编写 course.json，`course.py validate` 通过后 `build` 生成课程正文、结构化课程包、校验记录与交付清单，最终通过 [report-rendering](../report-rendering/SKILL.md) 交付可打开的网页并登记全部文件。不以聊天摘要或对话中的表格代替课程包交付；未决决策清零前 status 保持 draft。

**先补输入。** 必需：课程名称与课程定位、目标岗位或岗位族、总课时数。直接给 [T03 培养方案](../training-program-design/SKILL.md)的课程开发任务包（t05-package.json）时，以上信息从任务包读取并逐项复述确认；任务包为 draft 时提示未定稿再继续。可选：课程标准草案、现有资源清单（教材、课件、实训条件）、学生起点与程度、开课学期。缺必需项逐项询问，不自行假设课时、学期或办学层次。

**岗位事实与任务提炼。** 岗位口径全部遵循 [talent-data-query](../talent-data-query/SKILL.md)：在线用 `talent_query` 按目标产业或岗位族请求 positions.count、title.top 与 description.samples（JD 原文抽样），`talent_inspect` 核验；不写查询 JSON、SQL 或连接脚本。典型工作任务必须来自 description.samples 的样本原文或用户材料：workTasks 的 jdRefs 登记 positionId、脱敏摘录指纹 hash 与逐字摘录 quote，校验脚本会核对指纹与原文子串。禁止用模型常识补充岗位事实、任务表述或设备型号。样本不足或查询失败时说明缺口，提供「补充材料」「扩大范围」「按现有证据继续」，结束本轮等待真实回复；目标岗位在库内无样本又无材料时，课程定位标 insufficient 并请用户决策，不静默降级。

**任务驱动与双向对齐。** 行动领域归纳自典型工作任务，学习单元（模块）覆盖全部任务，不按学科章节拼凑。每个知识点/技能点上挂能力项（任务包 capabilityRefs 或用户材料能力项并给来源）、下接考核点（形式、评分要点、合格标准）；无考核点或无能力项挂接的知识点校验失败，不得进入大纲。评价方案必须可执行：每种考核形式写明评分方法与权重（合计 100）并挂接知识点，课程级合格标准必填。

**单元设计与实训任务书。** 至少为前两个模块编写单元教学设计样例（环节、时长、师生活动）与实训任务书（任务背景、要求、成果、评分要点、合格标准）。实训评分权重合计 100；涉及设备操作、用电用火、化学品必须写安全注意事项并列入待确认。

**标准合规逐条核对。** 课程标准与技能标准条文一律以知识库（凭据可用时按 [weknora-retrieval](../weknora-retrieval/SKILL.md)）、用户提供的原文或授权检索的官方公开原文为准，禁止凭记忆编写。核对表逐条给出原文摘录、来源、课程对应点与结论（conform/conflict/pending）；冲突项明确列出并给处理建议，不静默改写课程内容；取不到原文的条目标 pending 并请用户决策，未获授权不得带 pending 定稿。

**资源缺口与交接。** 资源缺口清单逐项标注 generated（注明下游技能与所需输入——课件类交 [courseware-studio](../courseware-studio/SKILL.md)，其材料范围是教案与实训指导书）或 manual（人工准备），不编造已有资源。

**需要人判断时询问。** 关键取舍——模块划分、考核结构、合规冲突处理、样本不足——说清已知、备选与影响，问一个可回答的问题；支持决策卡时用单选或输入卡，普通文本入口列同样问题。结束本轮等待真实回复，「请生成」、沉默都不等于授权带缺口定稿。用户选择记入 decisions（含原话），course-input.json 可回查；未回答的问题进 openDecisions。

**构建与交付。** 用技能脚本绝对路径，不 cd 到技能目录。草稿先 `python3 <技能目录>/scripts/course.py validate course.json`，按 validation 输出修正结构与证据；定稿 `python3 <技能目录>/scripts/course.py build course.json`，产物在 output/course-<短哈希>/。build 成功只代表业务交接完成。随后立即读取 report-rendering，把课程正文与结构化课程包交给它渲染网页，并用 `python3 <渲染技能目录>/scripts/register_delivery.py <web目录> --files-from output/course-<短哈希>/course-files.json` 登记课程包全部文件。只有平台产生真实网页入口才算交付成功；未成功说明停在哪一步并保留工件。最终回复简述课程包结论与未决项，使用平台返回的链接；不列工作区路径、内部字段或工具过程。
