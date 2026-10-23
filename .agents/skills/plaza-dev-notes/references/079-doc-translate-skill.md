# 079 · doc-translate 技能：PDF 翻译 + XeLaTeX 宏结构重排 + 译文 PDF 交付协议

**状态**：已实现（2026-10-23：真实浏览器上传→表单交接→DeepSeek/Pi 翻译→低权沙箱 XeLaTeX 编译→PDF 预览/下载→历史恢复通过；构建与 21 项回归通过。长文档与复杂版式的质量/超时边界仍待验证）。

## 动机

用户要做文档翻译技能（PDF 输入）。调研后的方向决策：不引入 BabelDOC/pdf2zh（torch 级依赖），改用**提取→翻译→XeLaTeX 重排**的自研链路；用户明确"不追求彻底格式对齐，只对齐单栏/双栏/纸张大小这种大结构"。机器上 TeX Live 2023（xeCJK/ctex/geometry/fontspec/longtable/booktabs/hyperref）与 poppler 全家、CJK 字体（WenQuanYi/AR PL）齐备且在沙箱 PATH 可达，零新增系统组件。

## 约定细节

### 技能层（`.agents/skills/doc-translate/`）

- `SKILL.md`：六步工作流（输入确认→宏结构探测→提取→翻译→重排→校验交付）；边界=只对齐宏观结构、扫描件/加密 PDF 如实拒绝、产物固定 `workspace/translation.pdf`。当前 cwd 已是 workspace，实际写 `./translation.pdf`；脚本与 references 通过加载说明中的技能绝对目录访问（`SKILL.md:25`）。
- `scripts/detect-layout.mjs`：`pdfinfo`（页数/纸张）+ `pdftotext -bbox-layout`（分栏）+ 纯文本量（扫描件线索）→ 单行 JSON。**分栏判别按"行中心点 vs 页宽中线"归类**（两侧各 ≥4 行且居中行 ≤20% 判双栏页，多数表决）——不能按行端点判：LaTeX `columnsep` 仅约 10pt，左栏行右端点可越过"中线-14pt"类阈值（实测踩过）；文本行 <8 的页（封面/插图页）不参与表决。
- `references/latex-rebuild.md`：纸张/分栏选项映射（**标准纸必须用纸名选项**，`paperwidth=612pt` 实测引入约 2pt 偏差）、模板骨架（xeCJK + WenQuanYi Zen Hei）、特殊字符转义表、排错表（缺字形黑框→数学模式等）。
- `references/structure-detection.md`：脚本字段、判别依据与校正方法。

### 注册（`web/server/lib/skills.ts`）

- `SKILL_PROMPTS['doc-translate']`（回落+通用约束）+ `INSTALLED_SKILLS` 新增。
- 新增导出 `PDF_REPORT_SKILLS = {doc-translate}`：产出 `workspace/translation.pdf` 的技能集合（与 `HTML_REPORT_SKILLS` 同构的工件门控）。
- **不进** `HTML_REPORT_CONTRACTS`（无 report.html、无固定章节契约）。

### 译文 PDF 交付协议（复用 HTML 报告管道，前端零协议改动）

- `traceExport.ts`：`traceFilePath(runId,'pdf')` → `traces/<runId>.translation.pdf`；`RunRecord.files.pdf?: string`。
- `web/server/index.ts:1172` `captureWorkspacePdfReport()`：终态/超时/断连三处捕获（与 `captureWorkspaceHtmlReport` 并列调用）；校验逻辑在 `web/server/lib/pdfReport.ts:21`，要求普通文件、≤64MB、`pdfinfo` 页数>0（5 秒超时），拒绝符号链接。`index.ts:1116` 在本轮执行前记录 inode/size/mtime/ctime 指纹，捕获时拒绝未改变的上一轮译文，避免追问/失败时交付旧文件；拷贝进 traces、记 `record.files.pdf`。
- 终态 done（`web/server/index.ts:1468`）：有工件时 `content` 保留模型最终说明；无工件时保留模型原因并追加"译文未生成：…"，不以通用文案覆盖缺输入/不支持等原因。`reportUrl` 与 HTML 报告共用 `/api/reports/:runId`；`ExperiencePage.vue:404` 将译文最终说明作为权威正文，`ReportOutput.vue:14` 用 `artifactName` 展示"查看/下载译文 PDF"。
- `handleHtmlReport`（`web/server/index.ts:492`）：html 工件优先，否则 pdf 分支（`application/pdf`、inline 预览；`/download` 或 `?download=1` 强制 attachment）。2026-10-23 文件名修正：`pdfReport.ts:9` 从本轮上传的原文 PDF 生成 `<原文件名去扩展名>-译文.pdf`；续译没有新附件时，取同会话/同技能、不晚于该运行的最近一次 PDF 附件，避免后来上传的文件反向改变旧记录命名。无原文名才用显式 `taskTitle`，再回落 `译文.pdf`，**不使用 promptDigest**。旧记录直接按已有 attachments 解析，无需迁移。预览与下载均带 `filename`/RFC 5987 `filename*`，并编码单引号/括号等字符，PDF 阅读器内下载也使用同一名称。
- 前端：`ExperiencePage` 历史恢复 `reportUrl` 判断 `files.html || files.pdf`；`RunDetailPage` 原始数据区补"译文 PDF"链接；`runsMock.ts` files 类型加 `pdf`。

### 附件上传实装（前端此前是禁用占位）

- `ExperiencePage.vue`：回形针从 `title="演示环境不支持附件"` 的 span 换成真按钮 + 隐藏 file input（`accept=.pdf,.docx,.doc,.md,.txt`，复用 `useUpload.ts` 的校验/上传，单文件 6MB、最多 5 个）。
- **沙箱目录一致性**：上传前无会话则先起对话骨架（`currentConvId`），上传带 `convSessions.get(key)`，返回的 `sessionId` 回写——保证附件落进随后 `/api/chat` 使用的同一沙箱目录（沿 068 表单任务"沿用表单上传的沙箱会话"的同一约束）。
- 附件生命周期：**技能切换（pickSkill/clearSkill）与新对话即清空**——send 时换技能会删旧引擎会话（技能会话绑定，见 067），旧目录里的附件会被孤儿化，故清空是正确性要求而非体验选择。附件随消息一次性消费，上屏文本附 `[附件] 文件名`。
- 样式 `.exp-attach-btn/.exp-attach-chip` 等入 `styles.css`（沿用 --sk-* 令牌）。
- 演示示例：`ExperiencePage` 的 `DEMOS` 补 doc-translate 条目（示例问题 chips 随 EXAMPLES 渲染；缺了它=新技能在示例行不可发现——首版漏配，2026-10-20 补）。

### 可用入口与真实失败（2026-10-23 收口）

- `web/src/data/useTaskConfigs.ts:64` 注册专用任务表单：目标语言（必填）、范围（留空全文）、术语要求、原文 PDF 上传；`UseTaskConfig.requiredUpload = {accept:'.pdf', label:'原文 PDF'}`，`UsePage.vue:252` 提交前校验必传文件。此前未注册表单，会回落至产业报告字段且没有 PDF 上传位。
- 文档表单 `knowledge:[]`，不显示 Mock 知识库，不向模型传入虚构资料选择；任务标题取原文件名+目标语言。`UsePage.vue:159` 明确要求生成译文 PDF 后只返回简短交付说明。
- `ExperiencePage.vue` 在上传前完成技能/沙箱绑定（`onAttachPicked`），避免从 general 换到 doc-translate 后，`send()` 才弃旧会话，连新上传文件所在会话一起丢掉。上传期间禁止发送，上传结果在会话/技能已改变时不再写入当前对话，待发附件最多 5 个。
- 真实请求失败一律保留真实运行标记并显示原因，不再转演示；SSE `error` 和未收到 `done` 的断流必须抛错（`useChatApi.ts:96`，详见 008）。翻译离线时保留输入、发送前重探测，不展示模拟翻译结果；翻译示例只保留使用引导，不含虚构页数/术语量。

## 成本与取舍

- **否决 BabelDOC/pdf2zh 做重排引擎**：唯一能"译文放回原版式"的路线，但 torch 级依赖 + 独立 venv + 沙箱可达性都要新建边界；宏结构对齐的需求用 XeLaTeX 已覆盖。留作后续路线。
- **否决 weasyprint/无头 Chrome 生成 PDF**：本机都可 pip/即用，但 HTML→PDF 需要另一套排版规范；TeX 对分栏/纸张/数学式的表达是声明式的，与"宏结构对齐"的语义一一对应。
- **reportUrl 复用而非新路由**：前端零协议改动是最大收益；代价是 `/api/reports` 语义从"HTML 报告"泛化为"运行交付物"（doc 注释已改）。
- 校验口径只做工件有效性与本轮更新检查：内容质量（翻译好坏、结构是否真对齐）由技能流程负责，服务端不重排版式判断。否决"文件存在就复用"：会把上一轮译文误认为失败轮次的新结果。否决真实失败后自动展示演示：会掩盖未加载技能、编译错误等实际不可用原因。
- 下载文件名确定性取附件元数据，不由模型猜测，也不把对话摘要当文档标题；因此直接聊天和表单的默认文件名一致。代价是暂不在默认文件名中追加目标语言；未来若需要，应使用显式语言字段，而不是解析任意用户指令。

## 后续扩展路线

- 扫描件 OCR：装 `tesseract-ocr + tesseract-ocr-chi-sim` 或走多模态模型（模型收图能力待验证）后放开 `likelyScanned` 分支。
- pdf-tool/docx 组件技能化：detect-layout 与提取知识先留在 doc-translate 内，出现第二个消费者（如合同解析、docx 翻译）时按 chart-visualization 的共享模式抽出去。
- 上传上限 6MB 对图文 PDF 偏紧，视真实使用反馈再调 `MAX_UPLOAD_FILE_BYTES`。
- 超长文档的翻译上下文预算：分批提取已约定（10–20 页/批），真实跑通后按 token 记录回填（参考 026）。

## 验证

- detect-layout.mjs（2026-10-20 实测）：xelatex 生成的 A4 满页单栏 → `columns:1`；letter 双栏 5 页 80 段 → `columns:2`、`paper.label:"letter"`；纸张 label 与 pdfinfo 标注一致。
- XeLaTeX 冒烟：xeCJK + WenQuanYi Zen Hei 的 A4 单栏/letter 双栏均编译通过，中文断行正常。
- 静态与构建：`node --experimental-strip-types --check` index.ts/skills.ts/traceExport.ts 通过；`vue-tsc --noEmit && vite build` 通过；`htmlReport.test.ts` 12 过 0 挂。
- 报告路由探针（临时 PORT=8791 实例）：伪造 `traces/<id>.translation.pdf` → inline 200 `application/pdf`、`/download` 200 attachment（`filename*=UTF-8''译文.pdf`）、清理后 404；`/api/skills` 含 doc-translate（installed:true）。探针进程已终止，伪造文件已删。
- 2026-10-23 真实验证：原后端进程启动于 10 月 20 日，`/api/skills` 仅 6 项、不含翻译；重启后为 7 项且 `doc-translate.installed=true`。真实浏览器通过专用表单上传 2 页英文 A4 PDF 并提交（运行 `20261023-144638-fykb`），DeepSeek/Pi 在 plaza-sandbox 下完成翻译与两遍 XeLaTeX 编译，生成 A4 中文 PDF；页面真实标记、内联链接、历史恢复均通过。预览和 `/download` 实测 200/application/pdf，下载 attachment 文件名含原文标题与目标语言；提取译文核对标题、列表、参数、产品标识符、参考文献通过。另一真实 API 上传运行亦成功；具体产物以 traces 为准，不把样本文档质量外推至所有输入。
- `node --test web/src/composables/useChatApi.test.mjs web/server/lib/pdfReport.test.mjs web/server/lib/htmlReport.test.ts`：21 过 0 挂；新增覆盖 SSE 错误/回调抛错/断流/HTTP 错误、PDF 缺失/无效/超大/符号链接/上一轮工件。`npm run build` 通过。
- 浏览器异常回归（拦截 chat、实际 upload）：general 换翻译后上传 sessionId 与提交 sessionId 一致，SSE 错误及 HTTP 400 原因持续可见，无演示回落/伪工件链接；缺 PDF 的表单提交被阻止。低权用户生成的 `.tex/.pdf/.log` 属主为 plaza-sandbox，已关闭原沙箱编译待验证项。
- 2026-10-23 下载命名回归：用户记录原文 `endtoend.pdf`、摘要“请翻译一下这个文档”，复现原下载名误用摘要；修正后 inline、`/download`、`?download=1` 三条路径均返回 `endtoend-译文.pdf`，原 HTML 下载头保持一致。原文/续译/历史时间边界/无附件回落/中文及标点命名检查通过，现有 PDF 工件回归 4 项通过；Chrome 原生下载建议名已核对。
- **待验证**：6MB 上限、20 分钟超时和长文档分批翻译的完整性；复杂双栏/公式/跨页表格的真实翻译质量；目标语言所需字体覆盖。OCR 仍未实现。
- 运维事实（2026-10-20 首跑、2026-10-23 再次实证）：**新增技能只改 skills.ts 不热加载，正在运行的后端仍是旧注册表**——/api/chat 对新 skill 400「缺少或未知的 skill」，而 /api/upload 照常成功。旧前端还会回落演示；2026-10-23 起真实失败直接显示错误。上线新技能的固定动作=重启后端 + 前端硬刷新；只改 `PLAZA_ENV=prod` 不会加载新代码或修复执行链路。
