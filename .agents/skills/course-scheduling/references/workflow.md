# 工作流细则

从用户输入到交付的完整命令序列。`<技能目录>` 为本技能安装路径；产物一律写在会话工作区（当前目录），不在技能目录生成或修改文件。

## 首轮：数据就位

1. uploads/ 无模板数据时：`python3 <技能目录>/scripts/schedule.py template --out 模板`，把 `模板/排课模板.xlsx`（或逐表 csv）登记进 delivery.json 的 files 交付给用户填写。
2. 有数据时：`ingest uploads/<文件...> --out problem.json`。
   - 校验失败：逐条转述 errors 中会改变结果的问题，用决策卡（单选）或文本请用户补充；**等回复，不猜默认值**。
   - 通过：读摘要确认任务/教室/教师/周数与用户描述一致，异常（如任务数对不上）先问再排。
3. 用户粘贴在对话里的表格：按 [输入契约](input-contract.md) 的列写成 csv 文件再 ingest，不要手写 problem.json 里的任务行。

## 求解与对比呈现

```sh
python3 <技能目录>/scripts/schedule.py solve problem.json --out run
python3 <技能目录>/scripts/schedule.py page run/solutions.json --out page.json
```

1. 读 run/solutions.json 摘要：`recommend`、各方案 unplaced/指标、effectiveHours。
2. 对比网页：读取共享 report-rendering 技能（`.agents/skills/report-rendering/SKILL.md`），按其页面模型验收 page.json 后渲染：

```sh
python3 <report-rendering目录>/scripts/render.py page.json --out output/public/schedule-plan
python3 <report-rendering目录>/scripts/register_delivery.py output/public/schedule-plan --name 排课方案对比
```

3. 对话回复：总分总摘要（推荐哪个方案与理由 → 各方案关键指标与差异 → 未排入/学时影响提示），末尾附 `plaza-question` 单选卡：
   - 无未排入：选项 方案一/方案二/方案三/重新生成（note 说明等待选择后导出）。
   - 有未排入：先呈现归因摘要，选项为各放松建议 + 接受未排入 + 补充材料。
4. **等待用户答复（answerTo）后才导出**；等待期间不写 delivery。

## 导出与交付

```sh
python3 <技能目录>/scripts/schedule.py export run/solutions.json --plan <用户选定> --out 交付
python3 <技能目录>/scripts/schedule.py manifest 交付 --out files.json
python3 <report-rendering目录>/scripts/register_delivery.py output/public/schedule-plan --name 排课方案对比 --files-from files.json
```

`manifest` 为交付目录生成带 sha256 的 files.json；`register_delivery --files-from` 把课表 xlsx 与 ics 登记为下载项（同名网页声明原样保留）。最终回复只报短状态与平台返回的链接。用户要求教师版/班级版日历时加 `--scope teacher:ID` / `class:ID` 重新导出并重新登记。

## 增量重排（调停课）

1. 用户给已有课表（模板 已有课表 表）+ 变更需求（停开/临时不可用/新增）。
2. 把变更改写进 problem.json 的 `existing.changes`（结构见输入契约；新增任务的完整定义写在 `add.task`）。
3. `solve problem.json --out run-inc --incremental`。
4. 变更清单（moved/removed/added/kept）摘要进对话；`export` 的 xlsx 自动带变更清单 sheet。
5. 每轮 run 目录保留，用户要回退时用上一轮 solutions 重新导出。

## 沙盘推演

复制 problem.json 改参数（压缩周数/替换教室清单/追加任务）→ solve → 对比两轮指标差异（未排入、连排达成率、实训室负载、学时损失）呈现；不渲染新网页时也可以表格形式给差异。

## 纪律

- 求解结果数字以 solutions.json 为准，页面上不出现与文件不一致的数值。
- 失败如实说明（如 ingest 退出码 2 的错误清单），不伪造课表或链接。
- 不向用户暴露 schema 字段名、内部路径、求解器实现细节；用「教师时间不冲突」「实训台套数」这类业务语言。
