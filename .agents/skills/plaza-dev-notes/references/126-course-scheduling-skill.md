# 126 · course-scheduling 排课智能体

**状态**　已实现。技能本体、广场接入、前端表单与真实 Pi 端到端全部通过；浏览器端人工验收待用户。

## 动机

教务排课需要前置沙盘：通用教务软件强于执行与归档，弱于产教场景推演。职业院校特有约束——企业轮岗批次、1+X 考试窗口、产业学院混编班、双师协同同堂——需要一个可解释、零冲突、可增量调整的求解器。定位是教务系统**之前**的推演工具，不替换教务系统，与既有技能（分班、诊断）同属教务链路。

## 约定细节

### 技能本体（`.agents/skills/course-scheduling/`）

- 入口 `SKILL.md` + 用户文档 `docs/index.md` + 契约 `references/{input-contract,constraints,output-contract,workflow}.md`；模板资产 `assets/templates/`（`schedule.py template` 生成后提交）；示例学校数据集 `examples/demo-school/`（8 张 CSV，兼作测试 fixture 与前端演示附件源）。
- CLI `scripts/schedule.py`（子命令 template/ingest/validate/solve/page/export/manifest），实现拆在 `scripts/scheduling/` 包：`model.py`（规范化与校验）、`solver.py`（求解与增量）、`metrics.py`、`xlsxio.py`（stdlib 极简 xlsx 读写）、`icsexport.py`、`pagegen.py`、`exportfiles.py`、`templates.py`（模板生成与解析）。
- **周课表模板 + 校历例外模型**：求解输出每周模式 (day, start, room)；`blocks`（占用块）统一表达不可用时段/轮岗/考试窗口/假期——无 `weeks` 或覆盖全部周为模板级硬约束（每周生效），部分周为日历事件（ics EXDATE + 按班级学时损失统计，`metrics.effective_hours_notes`）。
- **硬约束零冲突**：教师/班级/教室重叠、容量类型、台套数、连排（同时段连续、不跨午休）、占用块、双师多教师同堂、混编多班级同步；由构造保证，`solver.verify_plan` 独立复核写进 solutions.json（`verified` 字段）。排不进的教学单元进归因（逐约束阻断计数 + 按代价排序的放松建议），绝不输出带冲突课表。
- **求解算法**：最受限优先贪心 + 保可行移动局部搜索（`solver.py`），确定性种子；三套方案 = 三组权重侧写（教师集中/负载均衡/折中，`model.PLAN_PROFILES`）×种子去重；软约束权重用户可配（`weights`）。增量模式（`solver.solve_incremental`）：已有排入 fixed，变更 cancel/unavailable/add，偏离原时段按 换天100>换节次10>换教室1 计代价，输出 kept/moved/removed/added 变更清单。
- **导出**：课表 xlsx（方案说明/班级/教师/教室三视图/指标/归因/变更清单/教学任务 sheet）；ics 为浮动时间 VEVENT + `RRULE:FREQ=WEEKLY` + EXDATE（按 75 字节折叠、CRLF，混编课取两班轮岗周并集）。`page` 生成 report-rendering page.json（数字全部来自 solutions.json）；`manifest` 生成 files.json 配合 `register_delivery.py --files-from` 登记下载项（同 123 分班的住宅模式）。

### 接入点

- `web/server/lib/skills.ts`：`SKILL_PROMPTS['course-scheduling']`、`INSTALLED_SKILLS`、`SKILL_COMPANION_MOUNTS['course-scheduling'] = ['chart-visualization','report-rendering']`（伴生挂载表在 122 引入，本技能不再改 piRunner）。
- 上传白名单 `.csv/.xlsx` 已由 122 扩展（`web/server/index.ts:86`），本技能未改。
- 不登记 `HTML_REPORT_CONTRACTS`：对比网页走 delivery.json web+files 双通道（同 industry/123 模式），不走 workspace/report.html 固定协议。
- 前端：`web/src/data/skills.ts` 富卡片（teaching 分类）、`useTaskConfigs.ts` 工作台表单（8 个上传位带 `demoFile`）、`demoFiles.ts` 从 examples 目录 `?raw` 导入 8 张演示表。

## 成本与取舍

- **求解器纯 Python 标准库**（否决 OR-Tools CP-SAT：约 50MB 依赖需提交 .venv，沙箱维护成本高；求解模块已隔离可后换）。示例规模（68 任务/131 单元/15 教室/10 班级）三方案求解 <2 秒。
- **stdlib xlsxio**（否决 openpyxl/.venv 与"只收 CSV"）：模板由自家 writer 生成、用户回填，读写闭环可控；复杂工作簿报错并引导转 CSV（约 320 行，zipfile+ElementTree）。
- **决策卡在导出前**：solve 轮交付对比网页 + plaza-question 选方案，answerTo 轮才 export（等待期间不构建，符合 095/110 约定）。
- 增量模式单方案（最小扰动），多方案侧写只用于整学期排课——折中方案在增量场景没有决策意义。
- 教师偏好按人（集中/分散），学校级取向通过方案侧写表达，不再引入第二层权重。

## 验证

- `python3 .agents/skills/course-scheduling/tests/test_schedule.py`：14 项全过（模板/解析回环、三方案零冲突且互异、指标一致、同种子确定性、双师混编占用块、不可行归因、增量最小扰动、xlsx 回环 + openpyxl 交叉读、ics EXDATE 周次核对、page.json 结构、CLI 端到端）。
- `node --test`（web/server）78 项全过；`npm run build`（vue-tsc + vite）通过；`npm run docs:index`/`docs:check` 收录 docs/index.md。
- 重启后端后 `/api/skills` 含 course-scheduling（installed: true，14 技能）。
- 真实 Pi（youcai）端到端（2026-11-18 探针 `sess-sched-e2e-mwlmo1gp`）：第一轮 65 秒完成 ingest→solve→page→report-rendering 渲染→登记，done 带对比网页链接与 4 选项单选决策卡（指标与本地 solutions 完全一致：190 学时/连排 100%/利用率 32%）；answerTo 答复轮 32 秒完成 export→manifest→register_delivery，课表 xlsx（19138B）与 ics（51519B）下载链接、对比网页均 200。注意点：探针直连 /api/chat 带 answerTo 时必须同时带 32 位 hex requestId，否则 400「任务标识无效」（index.ts:851 的组合校验，前端 useChatApi 总是带）。

## 后续路线

- 沙盘场景预设（压缩教学周/校区搬迁/新增专业的参数化入口），当前以改 problem.json 重跑对比支持。
- ics 按教师/班级分文件批量导出；xlsx 班级课表分 sheet。
- 求解器瓶颈监控：任务数显著增长（>300）时评估引入 CP-SAT。
- 与教务系统的模板格式对账（真实学校字段映射层）。
