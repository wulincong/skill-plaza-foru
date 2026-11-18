# 求解契约（assign.py / read_roster.py）

**状态**：随智能分班技能实现，当前版本 solver 1.0.0。字段以 `scripts/assign.py` 的实际校验为准；本文与脚本不一致时以脚本报错为准并回来修订本文。

## students.json

`read_roster.py` 产出 `{"students": [...]}`；手工构造时遵守同一形状：

| 字段 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| id | string | 是 | 学号或编号，全局唯一；名单缺失时读取脚本按行号生成 `R0002` 形式占位并计入异常 |
| name | string | 否 | 姓名；对外报告可用编号替代 |
| gender | string | 否 | 统一为 男/女；其他取值保留原文并计入异常 |
| region | string | 否 | 生源地区；只用于均衡维度与聚合统计 |
| score | number | 否 | 成绩；非数字按异常处理 |
| assessment | object | 否 | 测评画像，值为数值（如 `{"logic": 72, "hands_on": 80}`）；分层模式的聚类输入 |
| preference | string[] | 否 | 方向志愿按顺序排列（第一志愿在前） |

未知列保留在 `extra`，不参与求解。字段完整性报告（读取脚本 stdout）必须转述给用户，不得省略缺失说明。

## params.json

```json
{
  "taskTitle": "2026级智能制造学院新生分班",
  "mode": "balanced",
  "classCount": 6,
  "capacityPerClass": 50,
  "seed": 20261118,
  "dimensions": [
    {"field": "score", "weight": 0.7},
    {"field": "gender", "weight": 0.3}
  ],
  "constraints": [
    {"type": "same-class", "students": ["2026001", "2026002"], "reason": "双胞胎同班", "applicant": "家长申请"},
    {"type": "different-class", "students": ["2026003", "2026004"], "reason": "教务备案需回避"}
  ],
  "classLabels": ["1班", "2班"],
  "searchRounds": 60,
  "searchWindow": 8,
  "layerCount": 3,
  "assessmentFields": ["logic", "hands_on"],
  "directions": [{"name": "智能制造", "classCount": 3}],
  "attempt": 1
}
```

- `mode`：`balanced`（均衡）或 `tiered`（分层），二选一。
- `classCount` + `capacityPerClass`：均衡模式必填两者；总容量必须不小于学生数。
- `seed`：可缺省。缺省时由输入指纹推导；重掷（attempt 2）的种子由首解种子加盐推导，全部写入审计。
- `dimensions`：均衡维度，默认成绩 0.7 + 性别 0.3。field 必须是名单里实际存在的列：数值列按均值均衡（可用值需过半），分类列按构成均衡；权重归一化后使用。可加 region 等列。
- `constraints`：只登记用户申报过并注明理由的条目。`same-class` 任意人数（同班单元），`different-class` 恰好两人。未申报的不写、不推测。
- `classLabels`：可选自定义班名，数量须等于 classCount。
- `layerCount` / `assessmentFields`：分层模式参数。缺省层数 3；画像字段缺省取所有 assessment 数值键。没有可用画像字段时分层模式拒绝求解。
- `directions`：分层模式的方向与各方向班级数。缺省时按第一志愿需求把 classCount 个班按最大余数法分给出现过的志愿方向（每个方向至少 1 个班）。
- `attempt`：1 = 首次求解（默认），2 = 一次受控重掷。没有 3。

## 一次受控重掷（状态机）

- 状态文件默认 `output/placement-state.json`，记录每次求解的输入指纹（params 去掉 attempt 后与学生名单的联合哈希）、attempt、种子与结果哈希。
- 同一输入：attempt 2 要求先有 attempt 1；attempt 2 之后拒绝一切再次求解。修改任何参数或名单即视为新任务，从 attempt 1 重新开始。
- `--fresh-state`：跳过重掷链校验，用于复现（配合审计清单里的 reproduceCommand）或演示，不推进状态。
- 复现口径：同输入 + 同种子 + --fresh-state 得到相同分班与统计（result.json 除 generatedAt 外一致）；求解日志为哈希链，manifest.solverLogHead 与之核对可发现事后篡改。

## result.json 要点

- `meta`：任务名、模式、班级数、容量、学生数、生成时间。
- `audit`：seed / effectiveSeed / attempt / paramsSha256 / studentsSha256 / inputFingerprint / solverLogHead。
- `fieldCompleteness`：各字段可用/缺失计数。
- `classes[]`：每班 label、人数、容量、性别构成、成绩均值/标准差/极值、生源地区 top、（分层）方向、层次构成、画像均值、志愿满足数。
- `balance`（均衡模式）：每个维度的班级均值/构成、均值差（max−min）、缺失计数；`heterogeneity` 为班内成绩标准差均值与总体标准差的对照。
- `preference`（分层模式）：满足率、按志愿序的分布、未满足原因分类（班级容量 / 画像分布 / 未填报）、逐人未满足明细、层次规模、各方向层名额与占用。
- `constraints[]`：每条约束是否满足及说明。均衡模式回避约束在求解内强制；分层模式同班约束在容量允许时归并，否则如实标未满足。
- 班额：均衡模式各班人数保持初解的 ±1（蛇形铺班 + 仅同规模单元交换），不出现明显偏班；多人同班约束单元会造成 ±1 偏差。
- `assignment[]`：逐生班级（含层次、志愿满足情况），是名册 CSV 的数据源。

## 报错与处理

- 容量不足 / 方向班级数与 classCount 不一致 / 分层缺画像字段 / 约束引用不存在的学生：按报错修改参数后重跑，不要绕过脚本。
- 名单列识别错误：用 `--map 列名=字段` 重跑读取脚本，不要手工编辑 students.json 掩盖问题。
- 混班（分层模式层人数无法整班装箱）是如实结果：日志有 layer_mixed 事件，报告需说明混班构成，不得隐瞒。
