# 输入契约

模板表与 problem.json 的字段定义。`ingest` 把模板 CSV/XLSX 解析为 `problem.json`（schema `course-scheduling/1`）；`validate` 校验两者通用。

## 模板表

| 表 | 必填 | 列 |
| --- | --- | --- |
| 信息 | 是 | 项目、内容（学校名称、学期名称、开学周一、总周数、教学日） |
| 班级 | 是 | 班级ID、班级名称、人数、专业 |
| 教师 | 否 | 教师ID、姓名、授课偏好（集中/分散/不限） |
| 教室 | 是 | 教室ID、类型、容量、设备名称、台套数、备注 |
| 教学任务 | 是 | 任务ID、课程、班级、任课教师、周学时、连排节数、教室类型、最低容量、设备名称、台套数要求、固定教室、课程类别、备注 |
| 作息时间 | 是 | 节次、名称、开始时间、结束时间、时段（上午/下午） |
| 校历 | 是 | 周次、标记（正常/假期/考试窗口/企业轮岗）、名称、范围、备注 |
| 占用约束 | 否 | 约束ID、名称、对象类型、对象、周次、星期、节次、备注 |
| 已有课表 | 否 | 任务ID、星期、开始节次、节数、教室 |
| 权重设置 | 否 | 权重项、数值 |

约定：

- 多值单元格用分号分隔：班级 `电商2401;电商2402`（混编）、教师 `T19;T23`（双师）。
- 列名支持常用别名（`授课班级`→`班级`、`连排`→`连排节数` 等），大小写与空白不敏感；无法识别的列会报错。
- CSV 以 UTF-8（可带 BOM）、逗号分隔；文件名含表名关键词即可识别（如 `05-教学任务.csv`）；xlsx 按工作表名识别。
- 校历每教学周一行；`范围` 写 `全校` 或 `班级:智造2401;智造2402`（也支持 `教师:`、`教室:` 前缀）。
- 占用约束的 `周次` 留空 = 每周生效（模板级硬约束）；`星期`/`节次` 支持 `周一;周五`、`5-8`、`全天` 写法。

## problem.json 结构

```json
{
  "schema": "course-scheduling/1",
  "meta": { "school": "示范职业技术学院", "semester": "2026-2027学年第一学期" },
  "calendar": { "startWeek": "2026-09-07", "weeks": 20 },
  "timetable": {
    "days": ["周一", "周二", "周三", "周四", "周五"],
    "periods": [
      { "id": 1, "label": "第1节", "start": "08:30", "end": "09:15", "session": "上午" }
    ]
  },
  "classes": [{ "id": "网络2401", "name": "计算机网络技术2401班", "size": 42, "program": "计算机网络技术" }],
  "teachers": [{ "id": "T01", "name": "陈建华", "preference": "balanced" }],
  "rooms": [{ "id": "S101", "type": "实训", "capacity": 40, "equipment": "数控机床", "sets": 16, "note": "" }],
  "tasks": [{
    "id": "R056", "course": "直播运营实战",
    "classes": "电商2401", "teachers": "T19;T23",
    "hoursPerWeek": 4, "consecutive": 2,
    "room": { "type": "实训", "equipment": "直播工位", "sets": 24 },
    "category": "实训", "note": "双师协同"
  }],
  "blocks": [{
    "id": "RK-01", "name": "教研例会",
    "scope": { "teachers": ["T03"] },
    "days": ["周五"], "periods": [5, 6, 7, 8]
  }],
  "weights": { "teacherCompact": 1.0, "afternoonPe": 5.0, "categoryStagger": 2.0, "roomStability": 1.0, "balance": 1.0 },
  "options": { "planCount": 3, "seeds": [11, 23, 37] },
  "existing": {
    "placements": [{ "taskId": "R001", "day": "周一", "startPeriod": 1, "length": 2, "room": "A101" }],
    "changes": [
      { "kind": "cancel", "taskId": "R068", "note": "停开" },
      { "kind": "unavailable", "scope": { "teachers": ["T08"] }, "days": ["周一"], "note": "教师外出培训" },
      { "kind": "add", "task": { "id": "R101", "course": "网络安全进阶", "classes": "大数据2401", "teachers": "T21", "hoursPerWeek": 2, "consecutive": 1, "room": { "type": "机房" } }, "note": "新开课" }
    ]
  }
}
```

字段要点：

- `blocks.scope`：省略 = 全校；`classes`/`teachers`/`rooms` 三选一。`weeks` 省略或覆盖全部周 = 模板级硬约束；部分周 = 日历事件（见约束文档）。
- `tasks.room` 全部可选：`type` 教室类型精确匹配，`minCapacity` 最低容量（缺省取班级人数之和），`equipment`+`sets` 设备与台套数下限，`fixed` 固定教室。
- `category` 用于软约束（`体育` 触发午后不排，其余类别参与同类错峰）。
- 引用班级/教师/教室可用 ID 或名称；ID 优先。

## 校验规则（validate / ingest）

- 必填表齐全；ID 唯一；引用的对象存在；周学时/容量为正整数。
- 连排节数不超过同一时段的最长连续节次（否则警告该单元难以排入）。
- 校验失败输出 `{ok: false, errors: [...]}`，退出码 2；逐条转述给用户补数据，不要自行猜测补默认值。
