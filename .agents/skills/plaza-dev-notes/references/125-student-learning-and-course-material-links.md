# 125 · 学生个性化学习规划与课程教材入口

**状态**：当前工作区实现完成；真实知识库、真实 Pi/优才模型及浏览器下载已验证。在线服务从另一仓库目录运行，本次未同步、未重启；生产低权 plaza-sandbox、生产域名材料入口与完整八周计划待部署后验收。

## 动机

学生提交目标岗位、学习目标、当前基础和时间后，需要先匹配团队课程包，再拿到每天能做的任务与教材。只有检索片段不能充当学习资源，带 X-API-Key 的上游 URL 也不能直接作为浏览器可点入口。复用现有表单、Pi、Python 检索和 HTML 交付，不新增模型客户端或学习管理数据库。

## 输入与接入点

- `.agents/skills/student-learning/SKILL.md:1` 定义完整/部分/无匹配、访问故障、先修与预算、教材绑定及交付边界；`docs/index.md:1` 说明读者、证据门槛、设计原则和使用方法。
- `web/src/data/useTaskConfigs.ts:65` 只有 role（必填）、goal、foundation、availability；`web/src/data/skills.ts:62` 注册卡片，`UsePage.vue:133` 使用岗位命名任务。知识库不出现在学生表单，默认万维自建课程库 `b627daef-d505-4f16-9ee9-76474a6e5bde`。
- `web/server/lib/skills.ts:155` 注册回落规则，`:208` 加入安装集合，`:212` 声明共享数据依赖。`piRunner.ts:567` 挂载 student-learning、weknora-retrieval、report-rendering 及知识库原生工具，`:576` 开启受限中继；会话回收/子进程退出关闭中继，初始化失败也清理。
- `web/server/index.ts:1906` 将实际用户消息存入 `.learning-request.json`，供故障后自主规划的授权原话回查。该文件不作为公开产物。

## 检索与宿主边界

`weknora-retrieval/scripts/retrieve.py:128` 起新增 `tags --kb [--keyword --page]`，适配实例的 data 内嵌 data/total/page/page_size。`documents --tag` 先核对分类属于指定库，随后以 tag_id 筛选，并逐项检查文档分类、库归属。所有分页返回 items/next_page。`:124` 同时保留 content_preview/content_truncated，避免 matched_content 为生成问题时丢失答案。

`web/server/lib/weknora.ts`：

- 宿主从环境或技能 `.env`（600）读 Key；`LEARNING_KB_IDS` 限定学习会话库，默认上述 ID。如另有 `WEKNORA_KB_IDS`，学习范围必须在其内。上游固定 HTTPS，不接受任意地址或重定向。
- `openKnowledgeRelay` 监听 loopback 随机端口和 256 位随机路径，会话仅取得 `.weknora-runtime.json` 的限库能力凭证；原生工具 `weknora_retrieve` 支持 tags/documents/search/chunks。宿主用参数数组运行 Python，Key 仅进子进程环境，错误不回显 stderr 或上游正文。调用可取消，另有90秒执行上限。PiRunner 显式剔除 WEKNORA_API_KEY 后经 JsonlChannel.env 启动 Pi，覆盖非 sudo 运行时，防止宿主环境凭据继承；Python 子进程仍由宿主单独注入 Key。
- 查询结果/失败写 `.weknora-evidence.jsonl`，带宿主本轮 runId、不含 Key。构建器按本轮 runId 检查故障，旧成功记录不能绕过本轮失败后的用户选择；无本轮故障时允许复用已核证据。`pi-tools.mjs` 的 tool_call hook 阻止改写来源、通道、用户消息记录和向会话外 write/edit。它约束正常模型行为，不声称抵御任意间接程序或同 UID 恶意进程。
- 当前受信本地 CLI 仍可独立使用；低权会话必须显式挂载工具，不能读取技能 `.env`。

## 教材入口与持久性

只有校验过库与分类的 documents 结果能签发逐文档 192 位随机授权。记录 `{kb, document, title}` 存在 `DELIVERIES_DIR/learning-materials/<token>.json`，目录700、文件600；不进 Git。结果附 `preview_url` 和 `download_url`，origin 复用 `DELIVERY_PUBLIC_BASE_URL`，不把上游 Key 放进 URL。

`GET/HEAD /api/learning-materials/:token/(preview|download)` 先从固定上游读取文档当前元信息，核对 ID 与 knowledge_base_id，迁出授权库即失效；再获取对应文件，验证当前配置库范围；不带公开目录列表，不接受任意路径。PDF 预览内联，Word/其他类型附件下载，nosniff/no-store 和 sandbox；上游无权限/删除/故障明确失败，不回显敏感正文。能力记录独立于临时 Pi 通道，宿主重启后仍可使用；上游权限与文件仍须有效。

与现有分享报告一致，**持链接可访问**，不是账户制学生身份鉴权。用户已要求报告附教材并可点击；否决在报告中暴露 API Key，也不把 Key 填入查询串。代价是转发教材链接会授予对应单文档访问；后续可增加有效期、撤销、学生登录与访问审计。默认不永久缓存教材副本，不承诺资料方删除后仍可下载。

`delivery.ts:114` 检测报告中的逐文档平台入口并存可选 `materialDownloads` 元信息；`:230` 仅这些网页增加 `sandbox allow-downloads`。保留不透明来源、不允许弹窗、表单、同源凭据与主站 API fetch。其他报告 CSP 保持原规则。真实浏览器验证教材可从报告点击下载。

## 计划构建与报告

内部 `learning-plan.json` 约定见 `student-learning/references/plan-format.md`：profile、mode=full/partial/self、summary、assumptions、days_per_week、minutes_per_day、courses（分类ID与文档ID）、stages/days/tasks（任务、分钟、教材引用、完成标准）、adjustments。构建器从宿主来源记录核对分类名、教材归属及实际授权链接；已匹配课程至少用于一个任务，每天任务总分钟不得超预算，按学习日数计算周数。

`student-learning/scripts/build.py:136` 以计划文件所在目录定位工作区，可显式 --workdir，不依赖 shell cwd；拒绝把技能安装目录作为工作区。子进程均在该工作区执行，调用共享渲染器 minimal 主题并登记 delivery.json。真实模型曾 cd 到技能目录后试图重建缺失来源，已通过工作区定位、禁止改来源与回归修复，失败样例不计验收通过。

无匹配自主规划仍需成功查询留证。服务故障后只有用户明确选择才能继续，fallback_authorization 引用实际用户消息；构建器核对原话来源并在成品说明未完成库内核验，不把失败当空结果。原话包含关系仅验证来源，语义授权及课程难度仍由智能体与用户核对。

每日任务用共享 actions 的富文本链接，避免普通 table 单元格仅转义文本导致链接不可点击。共享 report.css 将嵌套 actions 的 h3–h6 统一任务字号，修复层级较深时标题过小。正文不出现内部 schema/工具过程；没有观测统计不强制凑统计图。

## 验证与限制

- Python 检索14项、学习计划9项通过；覆盖分类分页、归属、问题命中与正文、真实链接、任务预算、故障授权和从其他 cwd 构建。
- Node 新增中继/教材/工具hook测试6项、四字段注册1项；HTTP/SSE/恢复/交付与静态网页回归通过。另有模型中继、会话、问题卡与 PDF 相邻回归通过。技能格式、文档索引、Vue 类型检查及生产构建通过。
- 真实 Key 的分类与目录查询成功，拿到“智能模型训练”课程包教材并检索内容。真实 Pi/优才模型产出五学习日计划，修复后复用真实来源成功构建并登记工作区网页。Chrome 在1280/390宽度检查四字段与报告，无横向溢出；报告实际含18处教材入口，点击成功下载课程大纲 Word，无页面错误。
- 测试在本工作区和 /tmp 独立运行，不覆盖在线仓库。当前执行者 zjf 无 wlc 的免密 sudo，因此没有以 plaza-sandbox 真跑本次新工具；宿主配置文件权限、会话共享组和生产材料持久目录仍需部署验收。测试的本地能力链接不宣称当前线上可访问。
- 时间预算结构检查不解析任意自然语言时间；必须人工/模型对照学生原话，八周或更长计划的可执行性尚未实测。

## 后续路线

同步变更到服务仓库，凭据交由服务用户持有并保持沙箱不可读；确认无活跃任务后仅重启后端，检查 health、低权取证、报告与教材访问。之后按需要增加学生账户鉴权、能力链接撤销/期限和进度反馈，不在首期实现打卡或成绩系统。

## 独立审查回填

基于本会话代码的独立审查发现4项，均已修复并回归：宿主环境 Key 继承、旧成功掩盖本轮故障、文档迁库旧链接越权、故障自主规划仍声称无匹配。审查未读取磁盘，范围限制保留；真实低权与生产部署仍待验。
