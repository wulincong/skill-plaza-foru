# 038 · tech-forecast 技能：契约泛化、证据链、投标规格与快照层

**状态**：已实现（2026-10-12 技能接入与契约泛化、10-13 证据链 v2 与投标规格替换、10-13 快照层；2026-10-12~16 多轮真实运行均 success 且报告服务端校验通过）。原 036（技能接入与契约泛化）、038（证据链 v2）、040（投标规格替换）、041（快照层）及运行观察 045/046/065 中的持久事实于 2026-10-19 合并，见 076。

## 动机

投标需求「新岗位·新技术预判」要求新增一个产出 HTML 报告的技能（技术成熟度雷达 / 技能演进桑基 / 新兴岗位预测 / 培训方向建议 / 新兴技能预测）。接入前 workspace/report.html 捕获链路在 `web/server` 写死 `skill === 'career-guidance'`，必须先泛化。第一版报告被用户反馈「不纯粹」（预判主要来自模型通用知识、查询稀疏），推动证据链 v2；随后用户交付投标版技能规格全文，整体替换 SKILL.md；再为高频「广东×AI/机器人」组合沉淀库内快照层，消除逐会话 4–15 分钟的重复查询与口径漂移。

## 契约泛化（HtmlReportContract）

- `web/server/lib/skills.ts` 新增 `HtmlReportContract`（sections / userReportContract / fileProtocol / firstTurnRules / heatmapChecks）与 `HTML_REPORT_CONTRACTS`、`HTML_REPORT_SKILLS`；career-guidance 原常量改由 `reportFileProtocol(chartRule)` / `sectionsContract(sections)` 工厂生成（career-guidance 生成串与重构前逐字节一致）。
- 接入点：`web/server/index.ts` 的 `captureWorkspaceHtmlReport`、legacy HTML 回落、done 文案与 finalOutcome 改为 `HTML_REPORT_SKILLS.has(skill)`；`saveHtmlReport` 按 contract 的 `heatmapChecks` 决定热点图专项校验（tech-forecast 传 false 跳过 CH_CITY 检查）。`piRunner.buildPrompt` 按 contract 拼装（首轮 firstTurnRules、后续轮重申 contract+fileProtocol；非契约技能行为不变）。
- **技能本体内置主仓库**（2026-10-12 用户决策：不做独立父仓库、不走 submodule；初版曾以 submodule 挂载，同日转普通目录并移除 `.gitmodules` 条目）。这是对父子仓库模式的已登记例外（README「技能组织模式」注明）：省去远端与指针维护，代价是技能历史与主仓库耦合。前端 `web/src/data/skills.ts` 与 `useTaskConfigs.ts` 登记 industry 分类条目与表单（region/domains/horizon/institution/majors/context + 可选资料上传）。
- chart-visualization 在子模块阶段新增 `references/radar-chart.md`（1–5 刻度、单图最多 3–4 个多边形）与 `sankey-chart.md`（两阶段节点合计 ≤20、流量必须写口径与证据来源），SKILL.md 索引同步。2026-11-03 已原样转为主仓库内置目录，见 092。
- 否决：复制 career-guidance 四点硬编码（第三份技能出现时不可维护）；把报告校验挪进各技能 SKILL.md（服务端校验不可被提示词绕过）。

## 证据链 v2：四级证据与横截面

- **四级证据等级**：库内实测 / 公开来源（联网检索，必须注明标题、网站、日期，关键结论两个独立来源印证）/ 内置文档 / 分析推断。落地于 SKILL.md、`references/output-schemas.md`、`skills.ts` 契约与 `SKILL_PROMPTS['tech-forecast']`。
- **title-trend 否决（口径红线）**：岗位库 `create_time` 是爬虫抓取批次时间而非真实发布时间（`career-guidance/references/data/岗位库数据源.md`、2025-07 单月 150 万条导入批次印证），**禁止把岗位库按月/按年聚合计数当作需求趋势**；趋势只能标「公开来源」或「分析推断」，折线图仅限公开来源提供真实时间序列。
- **横截面关键词计划**：`references/technology-snapshots.md` 标准关键词表——每个领域一组「新兴切片 vs 传统对照切片」（如 `大模型` vs `Java`/`软件测试`、`机器人` vs `数控`）；谓词语义 keywords 之间 AND、roleTerms 之间 OR。
- **web-search 工具**：`scripts/web-search.mjs`（零依赖）。`--query` 走 `cn.bing.com/search?...&ensearch=1`（**必须带 ensearch=1**，否则按首字降级返回无关结果；DuckDuckGo 本网络不可达）；`--fetch` 抓正文（strip 标签、2MB/2 万字上限）。沙箱声明写入 `sandboxAgentsMd()` 无条件节；检索纪律（来源分级、防注入、不大段复制、失败标「公开来源未检索」）写入 SKILL.md。
- **凭据配齐**：`web/.env` 补齐 `MYSQL_*` 后 `mysqlConfigured()` 为真，沙箱 AGENTS.md 正规注入岗位库工具节，消除早期「Agent 自行从数据文档翻凭据注入环境」的隐式依赖。

### web-search 降级形态与兜底（2026-10-13~16 多轮实测汇总）

- `looksRelevant` 按「任意 token 命中」放行：查询含裸年份 token（2025/2026）时，降级返回的无关页摘要带年份即被放行，360 兜底不触发；**即便无年份 token，cn.bing 对纯行业咨询类中文查询也会整批返回主题错位的缓存/推荐结果**（百科/酒店/电商页）。`ok:true` 不等于相关性，Agent 须自行判废。
- `--fetch` 不解码 GBK（按 utf8 硬解，央广网等返回乱码）；绕行 `curl -s URL | iconv -f GBK -t UTF-8`。`text/xml`（含 RSS、sitemap）不在支持内容类型被拒。
- 可用兜底（按稳定性排序）：① 直连权威站点首页/文章 URL（worldfootwear、cntac、miit、gov.cn 等多次成功）；② `--fetch "https://cn.bing.com/search?q=<urlencoded>"` 拿渲染后结果页文本（能确认「某来源存在某主题/日期」，但 `<a>` 被剥离拿不到 deep link）。
- 自动化检索避免把裸年份写进 query；改进方向：looksRelevant 忽略纯数字 token 并要求领域 token 命中比例阈值、fetch 按 charset 探测并回退 GBK/Big5、对文库/下载站（renrendoc/book118/docin）信誉降权、低相关时自动追加 Bing 页 fetch 兜底。

## 投标规格替换（v3 七章）

- frontmatter `name` 保持 `tech-forecast` 不改中文——它是 Pi `--skill` 加载与 `/skill:tech-forecast` 的匹配键；中文名落在正文 h1 与 `agents/openai.yaml` 的 `interface.display_name`（「新岗位·新技术报告生成」）。
- **服务端契约必须同步**：`TECH_FORECAST_REPORT_SECTIONS` 更新为新七章（分析摘要 / 新兴技术成熟度分析 / 技能演进路径分析 / 新兴岗位预测分析 / 新兴技能预测分析 / 人才培养方向研判 / 数据说明与评估局限）；契约逐轮重申，不同步会让 Agent 收到两套矛盾章节指令。`references/output-schemas.md` 骨架同步。
- v2 全部口径红线保留：禁止月度聚合当趋势、公开来源引用格式、标准关键词表横截面。
- 用户原文含 U+2011 非断行连字符，会导致服务端 figure 校验正则失配，正文统一 ASCII 连字符。

## 快照层（references/data/）

- `.agents/skills/tech-forecast/references/data/`：`README.md` 为覆盖索引与扩充约定（命名 `<省拼音>-<领域>.md`；**超过 90 天视为过期**；地区×领域×关键词命中现有文件才可引用，未命中走实时查询并标「快照未覆盖，实时查询」）。现有 `guangdong-ai.md`、`guangdong-robotics.md`、`guangdong-textile.md`，保留开发侧绝对条数与 `n<50` 小样本警示。
- SKILL.md「库内实测」为**快照优先**：命中即引用并注明快照日期；未命中、过期或缺维度才实时查库并标注。
- 已知限制：快照固化了默认 `roleTerms`（软件岗词），非软件域（如机器人运维/调试）被收窄，仍需实时补查——快照没有省掉全部查询；多轮实测「快照 + 实时复核」逐项一致，快照是可靠基线。
- **报告生成方式**：图坐标一律用一次性脚本计算生成（恢复脚本路线），不手写大规模 SVG 坐标；图数继续增长时尤其如此。

## 专业型切片落法（无快照领域，实测沉淀）

- `roleTerms` 必须显式指定**专业角色词**（设计/开发/打版/制版/工艺），不能沿用工具默认软件岗词；`keywords` 用单字领域词（鞋/服装）最大化召回，再由角色词收窄；上游材料词（鞋材/皮革）与数字化新兴切片常零命中或个位数命中——样本口径不成立时不进正文，证据层降为公开来源 + 分析推断，不因零命中改写为实测。
- 入库日期筛选：白名单工具参数集不含日期谓词（未知参数直接抛错），且 `create_time` 非真实发布时间；用户要求日期切片时不伪造口径，按在架横截面出数并在数据说明章写明。若业务确需，应在 SQL 模板加显式日期谓词并受控开放参数（如 `ingestSince`），同时注明「入库时间≠发布时间、不得用于趋势」。

## 成本与取舍

- 契约泛化多一层按技能查表的间接，换取新增 HTML 报告技能只登记一份 contract；热点图校验以选项实现，避免拆散 htmlReport.ts 既有测试。
- 横截面对比替代时间序列换取口径诚实，代价是趋势列证据强度依赖公开报道质量；联网检索走 cn.bing HTML 解析而非付费 API，零成本但有反爬降级风险（ensearch=1 是当前实测稳定形态）。
- 快照优先换秒级引用与跨会话可比，代价是快照维护与非覆盖切片的实时补查。
- 否决：给 Agent 裸 curl 搜索（解析不稳定、无统一输出形状）；把失准的 `--query` 结果当公开来源引用；用 Bing 页摘要替代正式正文引用（仅作线索）。

## 后续扩展路线

- 自建趋势观测（月度定时对固定关键词计划跑 title-top 追加快照，2–3 个月后形成口径自洽的真时间序列）；快照超 90 天自动刷新；`references/data/` 补鞋类（`guangdong-footwear.md`，登记专业角色词口径）等新领域；标准关键词表补「鞋类/皮革箱包」行与「建议 roleTerms」列。
- `web-search.mjs` 相关性硬阈值、charset 探测、域名信誉降权、低相关自动 fetch 兜底（见上节改进方向）。
- 受控日期参数（`ingestSince`）按需开放；radar/sankey 专项结构化校验（当前仅泛型 figure 校验）。
- chart-visualization 原 `dfcdafa`/`75e10d0` 提交的内容已由 092 原样内置主仓库，旧子仓库 push 待办不再适用。

## 验证要点（多轮真实运行汇总）

- v1（2026-10-12）、v2（10-13，20 条横截面查询、四级证据标注全文落地）、v3 投标七章、纺织/鞋类等多轮真实运行均 outcome success，报告 `validateCompleteHtmlReport`（heatmapChecks=false）`pass:true`、errors 空；v2 基线报告 `/api/reports/20261013-141110-4a3z` 可长期对比。
- 单测 `htmlReport.test.ts`、`cd web && npm run build`、`/api/health` 各轮均通过。逐次运行的耗时/调用量/字节明细不再保留（原运行观察记录已于 2026-10-19 清理，产物以 traces 与报告文件为准）。
