# 周期档案与复诊对比

状态：随 teaching-diagnosis 技能首次交付（2026-11-18）。本文约定会话工作区内的周期档案目录、各文件 schema 与复诊对比规则。

## 目录结构

```
archive/
  <周期ID>/                 # 如 2026S1；同一周期重跑用新目录（2026S1-r2），不覆盖
    cycle.json              # 口径元数据（下述 schema）
    metrics.json            # analyze.py metrics 输出原样（含 caliber 与逐组样本量）
    measures.json           # 决策卡确认后的改进措施
    diagnosis.md            # 定稿诊断正文（交接渲染前的审定稿）
    risk.json               # 授权生成的风险名单（如生成过）
  growth.json               # 跨周期关键指标汇总（可选，由 compare 结果整理）
analysis/
  config.json               # 本周期数据映射与口径
  inspect.json / metrics.json / correlation.json / compare.json
```

`archive/` 与 `analysis/` 都在会话工作区内，不属于公开产物；delivery.json 的 web 目录不得包含它们。

## cycle.json schema

```json
{
  "cycleId": "2026S1",
  "label": "2025-2026学年第一学期",
  "period": {"start": "2025-09-01", "end": "2026-01-15"},
  "scope": {"classes": ["大数据2401"], "major": "大数据技术", "studentsTotal": 41},
  "caliber": {"attendanceDenominator": "all-records", "passScore": 60, "scoreAggregate": "student-course-mean"},
  "files": [{"role": "attendance", "name": "考勤.csv", "rows": 812}],
  "createdAt": "2026-11-18T…"
}
```

`caliber` 必须与 metrics.json 内的一致；compare 以两期 cycle/metrics 中的 caliber 与 scope 为可比性判据。

## measures.json schema

决策卡逐项确认后写入；未确认的不写入或标 `pending`：

```json
{
  "cycleId": "2026S1",
  "items": [
    {
      "id": "M1",
      "title": "数据库课程第 6-8 章增加课前预习任务单",
      "evidenceRef": "analysis/metrics.json#grades.byCourse.数据库",
      "appliesTo": {"courses": ["数据库"], "classes": ["大数据2401"]},
      "decision": "adopted",
      "adjustedNote": "",
      "decidedAt": "2026-11-18T…",
      "reviewCriteria": "下周期该课程及格率回到专业均值±3分内（同口径）"
    }
  ]
}
```

- `decision` ∈ `adopted / adjusted / deferred`；`adjusted` 必须带 `adjustedNote`（用户原话或忠实转述）。
- `reviewCriteria` 是复诊的核验办法；没有写就不进入下一周期的对照评估。
- `appliesTo.classes` 中未列入措施的班级即下一周期的**对照组**候选。

## 复诊流程

1. 读取上一周期 `archive/<prev>/`（同会话）或用户上传的上一期报告/指标文件（跨会话；上传件需先核对口径字段，缺 caliber 的历史报告只能做描述性对照，不做指标并列）。
2. 运行 `analyze.py compare --current analysis/metrics.json --previous archive/<prev>/metrics.json --control <对照班级,逗号分隔>`。
3. `status=caliber_mismatch` 时，如实报告差异（哪个字段不同），提供两种出路由用户选：按新口径重算上期（若原始数据在手）或只做现状描述、不并列。
4. `status=ok` 时：comparable 项做干预组/对照组分组呈现；`notComparable` 项（仅单侧存在、数值缺失）逐项列明，不静默丢弃。
5. 对照结论措辞："干预组均值变化 ΔX，对照组 ΔY，两者差异不等于干预效果，需结合措施内容与其他因素判断。"

## 成长档案（growth）

- 每周期结束把可比关键指标追加到 `archive/growth.json`：`[{cycleId, metric, group, value, n, caliber}]`。
- 趋势图只串联 caliber 相同且 group 相同的序列；周期数 ≥ 3 才画趋势线，2 个周期只画对照点。
- 用户在本会话内完成多个周期时自然累积；换会话后凭上传的历史档案或报告接续，接续处注明来源与口径核对结果。
