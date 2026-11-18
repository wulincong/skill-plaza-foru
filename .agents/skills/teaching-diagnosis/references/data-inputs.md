# 输入识别与数据质量检查

状态：随 teaching-diagnosis 技能首次交付（2026-11-18）。本文约定各类输入表的识别口径、`analyze.py inspect` 的检查项与 `analysis/config.json` 的写法。

## 输入角色与必需性

| 角色 | config.files 键 | 必需性 | 用途 |
|---|---|---|---|
| 考勤记录 | `attendance` | 必需 | 出勤趋势、出勤风险、缺勤-成绩关联 |
| 成绩数据 | `grades` | 必需 | 成绩分布、学业风险、教学结果 |
| 评教数据 | `evaluation` | 归因必需三选一 | 评教低分与教学环节关联 |
| 课堂行为记录 | `behavior` | 归因必需三选一 | 课堂表现佐证 |
| 教学进度记录 | `progress` | 归因必需三选一 | 进度偏差 |
| 上一周期材料 | 上传文件，不进 config | 可选 | 复诊对比与成长档案 |

归因用的三选一数据都没有时，仍可完成现状描述，但归因章节只能写"未评估"并说明缺什么。

## 列名识别

`analyze.py` 按三级顺序解析列：**config.columns 显式指定 > 别名精确匹配 > 别名包含匹配**。别名表（大小写不敏感）：

- 学号：`学号/学生学号/studentno/studentid/id`；姓名：`姓名/学生姓名/name`
- 班级：`班级/班级名称/行政班/班别`；专业：`专业/专业名称`
- 课程：`课程/课程名称/科目`；教师：`教师/任课教师/授课教师/上课教师/老师`
- 日期：`日期/考勤日期/上课日期/记录日期/时间`；节次：`节次/课时`
- 考勤状态：`考勤状态/出勤状态/考勤结果/考勤情况/状态`
- 成绩/评分：`成绩/分数/总评成绩/期末成绩/评分/得分/评教分数/评教得分/总分`
- 计划进度：`计划进度/计划章节/应授章节/计划内容`；实际进度：`实际进度/实际章节/已授章节/实际内容/已讲`
- 周次：`周次/教学周`；评教人数：`评价人数/参评人数/参评学生数/样本数`

inspect 输出每个文件的列清单与数值/日期探测结果。**发现别名识别错列（如同表有"平时成绩/期末成绩"两列）时，在 config.columns 中显式指定正确列，不要依赖猜。**

## config.json 写法

放 `analysis/config.json`，相对路径先按工作区当前目录、再按 config 所在目录解析：

```json
{
  "cycleId": "2026S1",
  "period": {"label": "2025-2026学年第一学期", "start": "2025-09-01", "end": "2026-01-15"},
  "scope": {"classes": ["大数据2401", "大数据2402"], "major": "大数据技术"},
  "files": {
    "attendance": "uploads/考勤.csv",
    "grades": "uploads/成绩.xlsx",
    "evaluation": "uploads/评教.csv",
    "progress": "uploads/进度.csv"
  },
  "columns": {
    "grades": {"score": "总评成绩"}
  },
  "caliber": {"attendanceDenominator": "all-records", "passScore": 60},
  "rules": {"minCorrelationStudents": 30, "minTeacherSamples": 10},
  "thresholds": {"absenceRate": 0.2, "absenceCount": 10, "meanScore": 60, "failCourses": 2}
}
```

- `files` 的值可以是路径字符串，或 `{"path": "uploads/成绩.xlsx", "sheet": "期末"}` 指定工作表。
- `columns` 只写需要覆盖别名的项。
- `caliber.attendanceDenominator`：`all-records`（默认，分母含迟到/请假/缺勤全部有效记录）或 `excluding-excused`（剔除请假）。改口径会写进 metrics.json 并参与 compare 的口径一致性校验。
- `caliber.passScore`：及格线，默认 60。
- `rules`/`thresholds` 通常省略，用[分析规则](analysis-rules.md)的默认值。

## 格式容错

- **CSV**：依次尝试 `utf-8-sig / utf-8 / gb18030` 解码；分隔符自动嗅探（`,` `\t` `;` `|`）。Excel 直接导出的 CSV 常为 GBK，可正常读入。
- **XLSX**：解析共享字符串、内联字符串、数字与日期单元格（按数字格式识别日期并转为 `YYYY-MM-DD`）；合并单元格只保留左上角取值并在 inspect 中提示。**.xls 老格式不支持**——请用户另存为 .xlsx 或 CSV。
- **成绩列**：`92%` 这类百分数按比例解析（0.92）并在 inspect 标注 `percentLike`，提示核对是百分制还是通过率口径。非数值（缺考、等级制）计入质量警告、不入统计。

## inspect 检查项与处理约定

每文件输出：行数、编码、分隔符/工作表、各列空值率与 distinct、数值列极值、日期列范围、完全重复行数、合并单元格与重复列名提示。

发现以下问题的处理：

1. **完全重复行**：去重前先向用户报告数量，确认是导出问题还是真实重复，不擅自删改。
2. **考勤与成绩学生集合不齐**（metrics 的 quality 警告）：报告双侧差集规模，请用户确认是学号规则不一致还是数据缺失，未经确认不把差集学生静默丢弃或补造。
3. **日期越出周期边界**：列出越界日期与条数，由用户决定是否纳入。
4. **范围外班级**：列出与 scope 不符的班级，确认扩围还是剔除；扩围后 scope 与周期口径同步更新。
5. **状态用词无法识别**： unrecognized 状态不入分母，质量警告中列条数，请用户统一用词或提供对照表。

任何一项影响核心结论且无法从数据判定时，结束本轮用决策卡问一个可回答的问题；次要缺项就地说明。
