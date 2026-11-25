# 122 · teaching-diagnosis：学勤与教学诊断技能、表格附件通道与伴生挂载表

状态：已实现（单测 16 项、服务端 67 项、构建与接口冒烟通过；真实 Pi 端到端探针结果见文末回填）。

动机：职业院校诊改要求在课程、教师、学生层面持续诊断改进，现有产品止步于数据看板。新增 T10「学勤与教学诊断」智能体，基于周期内考勤、成绩、评教等上传数据完成"诊断 → 归因 → 决策卡措施 → 复诊 → 成长档案"闭环。此前平台上没有任何技能消费用户上传的结构化表格——上传白名单只有 pdf/docx/doc/md/txt，这是本技能的硬前置。

## 约定细节

### 技能接入（四点）

- `web/server/lib/skills.ts`：`SKILL_PROMPTS` 增 `teaching-diagnosis` 条目；`INSTALLED_SKILLS` 增 slug；新增 `TEACHING_DIAGNOSIS_TURN_SUFFIX`（逐轮重申口径纪律、样本量、相关非因果、名单授权、网页交付）。
- `web/server/lib/piRunner.ts` buildPrompt：按 ai-interview/resume-police 的既有分支模式追加 teaching-diagnosis 逐轮规则。
- 交付走**通用 delivery.json 通道**（`readDeliveryManifest`，index.ts captureDelivery），不登记 `HTML_REPORT_CONTRACTS`（无固定 report.html）、不加服务端业务契约——区别于 career-guidance/tech-forecast（固定路径）与 industry（四原件强校验）。
- 前端表单：`web/src/data/useTaskConfigs.ts` 新增 `teaching-diagnosis` 配置（考勤与成绩必传 `.csv,.xlsx`，评教/行为/进度与上期材料可选上传位）。

### 伴生技能挂载表 SKILL_COMPANION_MOUNTS（新约定）

`skills.ts` 新增 `SKILL_COMPANION_MOUNTS: Record<string, readonly string[]>`：主技能 → 追加 `--skill` 挂载的伴生技能（不进广场卡片、不切换主会话）。piRunner.createSession 原 industry 硬编码分支改为查表；industry 的 `pi-tools.mjs` 扩展仍按技能名单特判。当前条目：

- `industry-education-report`: talent-data-query / chart-visualization / report-rendering（原行为不变）
- `teaching-diagnosis`: chart-visualization / report-rendering

新增伴生型技能今后只改表，不改 runner。

### 上传白名单扩展（新约定）

- `web/server/index.ts` `UPLOAD_EXT_WHITELIST` 与 `web/src/composables/useUpload.ts` `ALLOWED_EXTS` 同步加入 `.csv`、`.xlsx`（前后端必须同步改，错误文案已更新）。
- `.csv/.xlsx` 不走 `.md/.txt` 的内联注入，保持 index.ts 的"请先读取该文件"提示；大表由技能脚本读取，避免 16000 字截断破坏表格。
- `UsePage.vue` requiredUpload 校验改为支持逗号分隔多扩展名（`.csv,.xlsx` 单必传位覆盖两种格式）。

### 技能本体与脚本

目录 `.agents/skills/teaching-diagnosis/`：SKILL.md（流程与五条业务规则：口径纪律、小样本不推断、相关非因果、隐私聚合优先、不排名）、references 三篇（data-inputs 输入识别与质量检查、analysis-rules 指标口径/样本量门槛/表述纪律、archive-schema 周期档案 schema）、`scripts/analyze.py`（**纯标准库**，子命令 inspect/metrics/correlate/risk/compare）、`scripts/test_analyze.py`（16 项单测，xlsx/日期序列/gbk 编码/口径拦截全覆盖，fixture 由测试内生成不入库）、docs/index.md + data-preparation.md、agents/openai.yaml。

关键设计：

- **统计先跑脚本不做心算**：三层指标（班级/教师/专业）、Pearson+Spearman、风险名单、跨期 compare 全部由 analyze.py 算出并逐组带 n；`compare` 对两期 `caliber` 不一致直接 `caliber_mismatch` 拒绝并列（口径纪律的代码化）。
- **xlsx 读取**：zipfile+ElementTree 解析 sharedStrings/inlineStr/数字/日期样式（numFmtId 14-22、45-47 与自定义日期码），合并单元格取左上角；CSV 按 utf-8-sig/utf-8/gb18030 回落、分隔符嗅探。`.xls` 老格式明确不支持（请用户转存）。
- **隐私通道**：报告网页仅聚合结果；个体名单默认不生成，须决策卡确认授权后 `analyze.py risk --csv` 出独立文件（utf-8-sig），走 delivery.json 的 files 通道，与 web 分离。平台无 RBAC，"仅授权角色可见"落为"独立文件 + 生成前确认 + 交付说明提醒"，边界如实写进技能文档。
- **周期档案**：`archive/<周期ID>/{cycle,metrics,measures}.json + diagnosis.md`；决策卡采纳/调整/暂缓结果写 measures.json，未确认只标 pending；`appliesTo.classes` 之外的班级即复诊对照组，compare 的 `--control` 与对照组汇总呼应。

## 成本与取舍

- **否决自建 .venv（pandas/openpyxl）**：wechat-report 模式要求安装目录带 venv，部署与低权沙箱 PATH 复杂；stdlib 方案零安装、沙箱直接可跑。代价：xlsx 解析是"尽力而为"子集（不支持 .xls、公式值取缓存、日期样式识别有限），失败时按数据质量检查路径如实报告并请用户转 CSV。
- **否决 HTML_REPORT_CONTRACTS 固定 report.html 通道**：该通道为单页报告设计且服务端校验章节结构；本技能要交付"网页报告 + 独立名单文件"双产物，delivery.json 通用通道原生支持 web+files，无需新增服务端契约。
- **否决服务端业务校验（industry 式四原件收据）**：本技能的验收点是行为纪律（样本量、口径、隐私）而非结构收据，先靠 SKILL.md + 逐轮 suffix + 决策卡约束；若后续发现模型绕过纪律，再加服务端校验（届时复用 reportParse 模式）。
- **表单必传位合并考勤+成绩**：requiredUpload 只支持一个 accept，合并为 `.csv,.xlsx` 一位多文件，避免前端再引入"多个必传位"新概念。

## 后续扩展路线

- 复诊/成长档案目前依赖同会话工作区或用户上传上期材料；跨会话持久档案可接 120 的稳定工作区设计。
- 课堂行为记录（behavior）目前只入 inspect，未做行为-出勤联合分析；待真实数据形态明确后扩 analyze.py。
- 若管理侧需要名单的真正权限控制，需平台级 RBAC/签名链接，超出本技能边界。

## 验证记录（2026-11-18）

- `python3 test_analyze.py`：16 项全过（csv 双编码/分隔符、xlsx inline/工作表选择/日期序列→2025-09-01、出勤与成绩指标手算对账、相关小样本降级、风险阈值与 CSV、compare 口径拦截与对照组汇总、inspect 重复行、config 缺必需文件报错）。
- `npm run build`（vue-tsc + vite）通过；`node --test` 服务端 67 项全过。
- `npm run docs:index`：18 技能 21 页，公开技能 10 个（含新卡）。
- 重启后端后 `/api/health` OK；`/api/skills` 含 teaching-diagnosis（installed:true，frontmatter 读取正常）；`/api/upload` csv/xlsx 200、exe 400。
- 环境 incidental：重启暴露 `web/server/traces` 属主为 zjf（wlc 无法 chmod 0700，服务起不来）。已按"重命名旧目录→新建 wlc 属主目录→原地移回 1338 个历史文件（属主不变、路径不变）"恢复，未动 deliveries。
- 真实 Pi 端到端探针（2026-11-18，youcai 模型，会话 sess-t10-probe-20261118，探针数据两班 70 人 ×12 次课，故意埋入评教班级列错填与 3 名高危学生）：
  - 第 1 轮：读三份附件后先输出口径核对表（发现考勤仅覆盖 9 月 12 次课、成绩无学期列、评教班级列错填课程名——后两处为探针数据故意缺陷，全部被抓出），以 multiple 决策卡结束等待确认，33s。
  - 第 2 轮：确认后跑脚本完成三层指标与相关分析，输出全部带 n 与分母；相关表述为"观察到关联，非因果"并列混杂因素（n=35≥30 允许推断）；三条改进建议（REC-001/002/003）以决策卡提交，123s。
  - 第 3 轮：全部采纳 → measures.json 留档（含证据引用）；诊断报告网页经 report-rendering 交付，done 帧带 webLinks（/p/ 真实链接）；网页正文聚合核查无任何个体痕迹（学生学号/高危名单关键词零命中）；明确"风险名单未生成（需另行授权）"。
  - 第 4 轮：用户授权后 `analyze.py risk --csv` 名单经 delivery.json files 通道交付（downloads 链接），utf-8-sig CSV 含 27 名触发默认阈值个体，高危学生（缺勤 11/12）识别正确。
  - 探针发现的技能行为缺口与修正：技能未**主动**以决策卡询问名单授权（只在文本说明"需另行授权"）。已在 SKILL.md「隐私与名单」段补充"存在触发阈值个体时主动以决策卡询问授权与阈值"。次要观察：archive 周期目录出现过带空格/不带空格两个变体、diagnosis 用了 .json 而非 .md——schema 为指导性约定，暂不加服务端强校验，留待多周期使用后再收紧。
  - answerTo 协议坑：/api/chat 带 answerTo 时必须同时传 32 位 hex requestId（index.ts:841-844 校验），前端 useChatApi 总是生成；裸 curl 探针漏传会得 400"任务标识无效"。
