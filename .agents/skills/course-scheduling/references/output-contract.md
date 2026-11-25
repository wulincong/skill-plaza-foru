# 输出契约

`solve` 写入 `<out>/solutions.json` 与 `<out>/problem.json`（规范化快照，`page`/`export` 凭同目录快照还原问题）；`page` 写 page.json（report-rendering 页面模型）；`export` 写课表 xlsx 与 ics。所有命令成功输出一行 JSON 摘要，失败输出 `{ok:false, errors:[...]}` 且退出码 2。

## solutions.json（schema `course-scheduling/solutions/1`）

```json
{
  "schema": "course-scheduling/solutions/1",
  "generatedAt": "2026-11-18T12:00:00",
  "mode": "full | incremental",
  "fingerprint": "problem 内容指纹",
  "problem": { "school": "", "semester": "", "weeks": 20, "days": 5, "periods": 8,
               "taskCount": 68, "classCount": 10, "roomCount": 15, "teacherCount": 26, "blockCount": 15 },
  "plans": [{
    "id": "A", "name": "教师集中型", "seed": 11, "weights": {},
    "placements": [{
      "taskId": "R056", "meeting": 0, "course": "直播运营实战",
      "classes": ["电商2401"], "teachers": ["T19", "T23"],
      "day": "周一", "start": 7, "periods": [7, 8], "length": 2,
      "room": "S103", "category": "实训",
      "fixed": false, "origin": null,
      "basis": ["HC-01 教师时间不冲突", "HC-02 班级时间不冲突", "…"]
    }],
    "unplaced": [{
      "taskId": "R900", "meeting": 0, "course": "智能网联汽车实训",
      "classes": [], "teachers": [], "length": 2, "full": true,
      "reasons": [{ "constraint": "HC-04 教室类型与容量匹配", "count": 1, "detail": "无满足…的教室" }],
      "suggestions": ["放宽教室要求：…"]
    }],
    "metrics": { "…见下" },
    "verified": true, "violations": [],
    "incremental": { "changes": [], "kept": 126, "moved": [], "removed": [], "added": [] }
  }],
  "effectiveHours": [{ "class": "智造2401", "events": ["企业轮岗…"], "lostWeeks": [9], "lostHours": 24 }],
  "recommend": "A"
}
```

- `verified`：求解后独立复核硬约束的结果，必须为 true；`violations` 应为空。
- `basis`：该排入满足的约束条目（可解释性）；`unplaced.reasons` 为阻断证据。
- `recommend`：未排入最少 → 连排达成率最高 → 教室利用率最高。

## 指标口径（metrics）

| 指标 | 口径 |
| --- | --- |
| conflicts | 硬约束冲突数，恒为 0（未排入不算冲突） |
| unplacedMeetings / unplacedTasks | 未进入课表的教学单元/任务 |
| placedHours / plannedHours | 排入学时 / 任务总学时 |
| roomUtilization | 已用教室·节次 ÷（教室数×天数×节次） |
| roomByType | 分教室类型的利用率 |
| consecutiveRate | 满连排单元排入数 ÷ 要求连排的单元数（尾节不计入分母，见 tailMeetings） |
| labLoad | 实训类教室逐间周节次、峰值、均值与基尼系数（0 完全均衡） |
| teacherLoad | 教师周节次与到校天数 |
| classDailyMax | 班级单日最多节次 |

## 导出文件

- **课表.xlsx**：方案说明 / 班级课表 / 教师课表 / 教室课表（逐对象周课表矩阵，单元格含课程、教师、教室）/ 指标 / 未排入归因（有则）/ 变更清单（增量则）/ 教学任务。
- **课程日历.ics**：每个教学单元一个 VEVENT，`RRULE:FREQ=WEEKLY` 至学期末，受轮岗/窗口/假期影响的周次写入 `EXDATE`；`--scope class:ID|teacher:ID` 可筛选。
- page.json 数字全部来自 solutions.json；智能体只润色文字，不改数值、不增删方案。
