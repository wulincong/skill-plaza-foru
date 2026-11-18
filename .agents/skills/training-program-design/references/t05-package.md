# 课程开发任务包（交 T05）

培养方案定稿后，`program.py build` 自动生成课程开发任务包，供下游课程开发技能（T05）直接消费。任务包与方案同源（同一 program.json），不手工另写。

## 文件

- `t05-package.json`：结构化任务包，schema `t05-course-development/1`。
- `t05-overview.md`：人读总览（课程清单、优先级依据、证据索引）。

## t05-package.json 结构

```json
{
  "schema": "t05-course-development/1",
  "program": {"majorName": "大数据技术", "majorCode": "510205", "version": "2026-1", "asOf": "2026-11-18"},
  "tasks": [
    {
      "courseId": "CS1",
      "courseName": "Hadoop 大数据平台运维",
      "category": "professional-core",
      "credits": 4.5,
      "theoryHours": 40,
      "practiceHours": 32,
      "semesters": [3],
      "assessment": "考试",
      "capabilityRefs": [{"capabilityId": "C-OPS-1", "level": "H"}],
      "evidenceRefs": {"metricIds": ["M_JG1_SKILLS"], "sourceIds": ["S_STD"]},
      "developmentNotes": "设置理由与岗位证据摘要"
    }
  ],
  "evidenceIndex": {
    "metrics": {"M_JG1_SKILLS": {"label": "…", "value": 0, "unit": "…", "sourceIds": []}},
    "sources": {"S_STD": {"title": "…", "locator": "…", "url": "…"}}
  }
}
```

`evidenceIndex` 内嵌方案证据的精简索引，T05 开发课程标准时可直接回查能力项与岗位证据的原始口径，不需要重新取数。

## 边界

- 任务包只包含方案已定稿课程；draft 方案生成的任务包在 `program.status` 中保留 draft 标记，T05 侧应提示未定稿。
- 证据索引不包含查询内部文件（evidence.json、SQL）；共享统计仍指向 `data/tq-…/result.json` 工件。
- 修订方案时重新 build 生成新任务包，新旧包按 delivery 版本区分，不覆盖。
