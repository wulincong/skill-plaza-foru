# 087 · 报告智能体接入共享人才查询：实现、适配与证据绑定

**状态**：已实现并通过开发用户真实只读取数及17页报告全链路验证（2026-11-02，talent-query-engine/1.2.0）。57项查询/接入自动测试通过，前端构建通过。低权Pi在线链路、运行服务重启后的新会话验收仍待验证；本轮未重启服务、未调用微信、未改源库DDL。原设计由 Git 标签 design-report-query-integration-20261102 保留，本文回填实际实现。

**产教决策报告更新（2026-11-04）**：新报告已接入共享统计，05 快照保留为显式历史复现入口。本文原有离线约定为迁移前状态。见 [109](109-industry-report-query-handoff.md)。

2026-11-03 补充状态：已核对真实在线基础报告的共享取数、绑定与生成记录；报告分析层存在内容完整性缺口，见文末。取数/渲染通过不能作为分析质量验收通过；高级章节与完整低权链路仍不能据此标为全部验收。

同日后续：用户明确要求真实深入分析后再生成报告，强制分析阶段与wechat-outline/3已实现，见 [091-wechat-evidence-led-analysis.md](091-wechat-evidence-led-analysis.md)。文末原因排查保留为当时事实，后续路线中分析阶段/门槛与文案收敛由091接续；在线模型新会话及更广研究维度仍待验证。

## 动机与范围

wechat-report 原先独立连接数据库、拉取全部描述、在Python计算统计，再重建复核SQL，和共享查询形成两套入口。用户明确要求删除其全部旧数据库查询，统一替换为 talent-data-query 并解耦。

现在的关系：报告计划 → 共享CLI查询 → 标准结果与实际证据 → 纯报告适配 → 大纲/图文/核查表。主智能体保持 wechat-report，数据依赖不启动新模型会话，也不创建新前端卡片。报告侧没有数据库客户端、配置加载或SQL生成。

## 实际接入点

| 位置 | 行为 |
|---|---|
| .agents/skills/wechat-report/scripts/collect_data.mjs:14 | buildRequest 将报告章节展开成共享指标；总体命名all，职教样本命名vocational；子样本与用户原有学历/经验限制取交集，交集为空不放宽范围 |
| .agents/skills/wechat-report/scripts/collect_data.mjs:31 | 仅通过公开 capabilities/query/inspect 调用共享CLI；支持从本会话保存的result重新适配。没有导入共享数据库内部模块 |
| .agents/skills/wechat-report/scripts/adapt_query_result.mjs:5 | 纯 talent-result/1 → wechat-report-data/2 转换；字段来源、比例单位、完整城市频数、子样本、覆盖状态 |
| .agents/skills/wechat-report/scripts/bound_report.py:31 | 校验原工件清单/哈希和报告数据，并调用纯JS适配器重建比对；后续流程不查库 |
| .agents/skills/wechat-report/scripts/bound_report.py:10 | 注册类型化量化事实，固定句子的统计对象及输入字段，避免把企业数写成岗位数 |
| .agents/skills/wechat-report/scripts/gen_outline.py:10 | 基于实际存在的数据生成大纲；空样本/无薪酬/缺描述/单城不使用旧固定AI或广东结论 |
| .agents/skills/wechat-report/scripts/verify_data.py:14 | 数据验收与final渲染验收分开；前置渲染为pending；逐投影检查正文/图表及来源版本 |
| .agents/skills/wechat-report/scripts/evidence_sheet.py:16 | 核查表消费真实 evidence，逐语句耗时标为未可靠测量，批次耗时单列 |
| .agents/skills/wechat-report/scripts/render_report.py:835 | 实测Chrome窗口与内容视口差，补偿截图并裁成要求尺寸；容器与截图使用同一估算高度，修复本轮实测页脚裁切 |
| .agents/skills/wechat-report/scripts/pack_delivery.py:10 | 公开ZIP按本次manifest取图，不按glob收集；不包含内部SQL工作簿、绑定文件和查询工件 |
| scripts/talent-data/core.mjs:53、:62、:152 | 新增5项共享统计，严格analysis输入、19项指标上限；方向规则/词表顺序参与语义缓存键和内容指纹 |
| scripts/talent-data/compile.mjs:79 | 无时间窗时继续产业候选优先；方向/城市方向共享频数；技能词一次条件聚合；薪酬按方向中点频数复用 |
| scripts/talent-data/analysis.mjs:20 | 聚合数据对账、方向/薪酬/技能分组数量交叉检查、地域别名归并、描述缺失分母；不输出描述明细 |
| scripts/talent-data/metrics.mjs:60 | 组装新指标与错误；没有有效描述返回NO_VALID_DESCRIPTION/unavailable，保留空集和执行失败的区别 |
| web/server/lib/skills.ts:196、web/server/index.ts:143 | 声明wechat-report → talent-data-query数据依赖及受信入口；兼容白名单优先提示只适用于未迁移技能 |

已删除：scripts/fetch_data.py、scripts/db_setup.py、scripts/report_common.py（旧固定分组与重复推导）、position_type_dict.json。移除requirements中的PyMySQL，清理安装/数据规范和编辑台字典入口，历史演示JSON去除旧SQL并标明demo。没有删除或修改用户已有的brand.json改动，也没有读取/复制真实微信配置。

## 协议与分工

### 报告计划

wechat-report-plan/1接受 filters、sections、analysis、audience、industryLabel、execution。地区必须明确；不默认AI、Java、广东或近365天。filters/execution由共享查询继续严格校验，计划不接受SQL。

基础章节为overview/geography/requirements/salary/vocational；可选tracks/city_tracks/lq/track_salary/skills/track_skills。章节映射只包含声明的指标，整体数量/企业/质量为必需基础。方向或技能章节缺少规则会被共享工具拒绝，不生成假零。

词表和归类规则属于共享统计策略；报告只提交普通数据配置。analysis.tracks最多12组，每组有唯一key/label及titleAny或roleIds，按顺序首个命中；未分类独立。名称词有界，roleIds按完整岗位类型ID匹配、仅校验数值格式，调用方先通过共享resolve确认；不自动展开或当产业ID使用。analysis.skills最多60个词，LOWER子串匹配，每岗位每词至多一次，多词可重叠。不是分词、词界或同义归并。

新增实际指标：track.distribution、city_track.cross、track_salary.summary、skills.distribution、track_skills.cross。策略说明见 talent-data-query/references/analysis.md。这些是显式规则归类的岗位方向，不能冒充官方产业赛道。规则/词表没有AI默认值，适用于不同产业的受控配置。

LQ在报告侧用完整城市×方向频数派生：(本市方向数/本市总数)/(全样本方向数/全样本总数)，全样本分母含不可归属城市记录，零分母不计算。它不增加SQL，也不等于动态趋势证据。

### 结果与绑定

- 共享层仍输出talent-result/1及evidence/manifest，旧无analysis结果按原引擎哈希验证；版本参与新缓存键。
- report_data.json采用wechat-report-data/2，包含原渲染所需的展示字段、范围、公共枚举标签、coverage，不含查询SQL。
- report_binding.json采用wechat-report-binding/1：adapterVersion、来源requestId/contentHash/原读取时间/清单指纹、报告文件SHA-256、字段→metricId列表、适配选项和覆盖情况。
- 数据适配从完整city_education.cross频数统计城市；不从TOP N行数反推城市总数。源share为0–1，展示pct转换一次。
- 薪酬统一salary-policy/1：保留小数、100K/月上限、加权线性分位数、六档分布。原500K上限/整数化/七档方法没有在报告侧保留第二套实现，旧报告不能无声拼接为新口径。
- 大纲采用wechat-outline/2，绑定数据文件指纹与来源contentHash；正文量化句使用类型化claim，图表使用有界投影，metricIds需与输入字段对应。变更数字需重新取数；新增量化句式需注册相应事实类型，非量化分析可编辑。
- 文章从同一已验证大纲生成，保留data/voc/scene三个导语参数，不再使用固定城市、薪酬或产业演进结论。
- --result是本地工件消费，不受15分钟查询缓存TTL限制。大纲确认后继续读保存的结果；主动刷新生成新数据版本并重新审阅，不混用不同时点缓存。

**展示标题修订与重复取数（2026-11-03，现状核实，优化待实现）。** 济南运行 `20261103-233541-dgg7` 只改计划的 `industryLabel` 后再次执行带 `freshness:live` 的 `--plan`。核对两次共享请求、cacheKey、contentHash 和 15 个指标均相同，两次 execution.reused 均为 false。标签参与适配展示（`wechat-report/scripts/adapt_query_result.mjs:23`），写作证据包含整个展示数据文件的 SHA（`report_analysis.py:222`），故第二次写作拒绝旧进度（`writing_batches.py:44`）。同范围展示修订应优先考虑用原有已验签统计重建展示，核对事实引用后只重做受影响内容；真正的筛选、指标或规则变更仍需重新核验统计。直接放松指纹校验会允许跨口径混稿。本次未实现展示修订入口，也未测量优化后的耗时。
- 没有描述或有效薪酬可保留基础报告并明确coverage unavailable；执行失败/对账失败不生成新报告数据，不自动换样例。
- 演示必须显式--demo；旧演示数据不属于实时验收证据。公开打包只接受真实绑定数据；内部证据留output/internal。

## 验证与产物

持久验证摘要：reports/query-benchmarks/2026-11-02-wechat-integration/validation.json及接入验证.md。该目录raw/session保留本地原工件/图片/核查表/ZIP，gitignore；运行观察留产物，不另建手记。

- node --test scripts/talent-data/*.test.mjs：57/57。包括原39项，以及实际编译SQL在独立SQLite关系数据上的互斥规则、大小写/重复词、重叠词、加权薪酬、缺失地址/描述、空集、部分失败、方向分组对账；没有写生产库。
- 接入测试覆盖公开CLI收集、职教交集不扩样、保存结果不查库、工件篡改、企业数误作岗位数、图表错数、缺图失败、空样本/无薪酬/无描述、真实evidence工作簿。协议peer数据均明确为合成数据。
- 真实只读小样本为广州低空经济、大专/高职、全时间在招，完成总体及职教组32个指标结果、10条统计SQL，17页大纲/PNG/长图/文章/内部工作簿/公开ZIP均跑通；原取数耗时约17.5秒。该样本及自定义规则不代表全产业赛道，也不能外推省域性能。
- 最终编译SQL与实际10条证据逐条相同，使用最终统计实现从已保存聚合帧重建的contentHash与原结果相同；后续报告重适配没有重新查询。
- 最终渲染检查通过；热力图既有全矩阵相关检测未达阈值，但其定向探针兜底通过，不能称逐格OCR核验。人工查看热力图/附录及页脚，修正了视口截断和原彩色检查跳过顶部短图的问题。
- npm run build（web）通过；index.ts语法、Python语法、Skill格式与链接检查通过。低权Pi、本轮服务更新后的新会话、极大范围/长文案版式仍待独立验收，不能冒充已测。

## 成本与取舍

- 保留原Python图片渲染与图表样式，通过数据适配接入；去掉旧无条件模板和预设结论，需要维护较少量的受检事实投影。它不是旧版所有段落逐字保留，也没有把“数字池中出现过”当成完整语义校验。
- 共享层增加有限方向/技能表达能力，避免每份报告重复搬运描述和算法；代价是更宽请求可能达到现有分组/字节/时间预算。没有引入任意SQL/正则、自动抽样或自动猜行业规则。
- 同一组完整报告通常base/cube/tracks/skills/salary五条SQL，两个样本十条；基础版每组三条。连接/事务复用不意味着物理只扫描一次，多组高级统计尚未合并；重查询队列和缓存只约束共享入口。
- 适配后每个报告阶段都校验本地工件并重建展示数据，有Node子进程开销，换取跨语言单一适配规则；不额外连接数据库。
- 核查表直接消费实际evidence并移到内部目录；公开包不携带SQL。最终图片检查仍有既有启发式边界，不因一次报告通过就宣称全面修复083中的全部交付/编辑/超长布局问题。
- 复用现有CLI配置和Linux环境，不新增服务或连接池；现有凭据隔离与状态目录权限边界沿用078/085。安装环境中已有包不等于仍被业务依赖，本轮不无关重建整个.venv。

## 后续扩展路线

1. 部署更新后验证低权Pi主会话、共享CLI、状态目录及会话隔离；旧会话仍需重新加载技能说明。
2. 为真实产业制定经过审阅的方向/技能配置，扩展类型化事实选择器与更丰富的分析表达；有需要再增加词界、同义词及专业关联。
3. 按真实省域/全国负载验证组合基数和时间窗口路径，评估多组高级统计复用；索引/预汇总按086独立评估，不归因于本轮尚未创建的索引。
4. career-guidance与tech-forecast继续逐项迁移；离线报告保持禁库契约。长文本布局、逐格图文验证、交付验收凭证消费等按083独立推进。

## 2026-11-03 · 基础报告的分析生成与质量验收缺口

**状态**：原因已核实，待修复。本轮只读核对原始运行、保存的查询工件和报告源文件，未重新查询数据库、重渲染或修改业务脚本。

**动机**：用户反馈最近报告分析偏少。需区分统计失败、分析计划缺项、正文生成不足和页面显示遗漏，避免用增加页数或放宽证据校验代替分析能力。

### 持久事实与接入点

- `SKILL.md:17` 允许方向/技能没有规则时使用基础章节；`references/data-aggregation.md:7` 的基础示例没有 `analysis`。因此普通“生成某地区某产业报告”的请求可以只选择 overview/geography/requirements/salary/vocational，而没有 tracks、city_tracks、lq、track_salary、skills、track_skills。现有 coverage 只反映已声明章节，未请求的高级分析不会显示为缺口；`scripts/gen_outline.py:136`、`:154` 会据此写“本次声明的统计章节已完成”，不能将其解释为完整产业分析已完成。
- 共享取数迁移提交 `270fa72` 同时重写了报告生成与验证。当前 `scripts/bound_report.py:10` 仅注册六类量化句式；`scripts/gen_outline.py:76`、`:84`、`:88`、`:96` 主要填充样本规模、城市数量、同组样本说明和薪酬中位数，招聘类型/学历/经验共用同一句说明；学历×经验页没有解释段落。`scripts/gen_outline.py:123` 的职教页只输出岗位池规模/占比与通用建议，未利用已取得的池内城市和薪酬等信息；`:133` 的培养建议是固定两句。该默认产物是报告骨架，不能视作已经完成研究分析。
- `scripts/build_article.py:36` 直接复制大纲段落、总结并插入图片，不补充数据解读。运行智能体若没有在大纲生成后明确执行分析与改写，渲染和文章构建不会自动补足内容。
- 量化段落被 `scripts/bound_report.py:140` 限定为已注册的 claim；扩展有证据的排名、占比、差异、集中度或子样本比较，需增加类型化事实/派生投影。约束不禁止非量化分析，但当前只提供六类事实且缺少分析阶段，会限制可直接生成的具体论证。
- `scripts/verify_data.py:26` 检查工件/指标绑定、禁语、图片版本和完整性，没有检查章节分析覆盖、重复模板、数据解读或可执行建议。`references/copywriting.md:28` 的短导语规则与 `:40`、`:67` 的每屏两段/250–320字规则仍有冲突，且本次运行未读取该文档；不能把这份旧规范当作已经执行的质量门槛。

### 验证边界

- 原始依据为 `web/server/traces/20261103-105417-hggy.json`、`20261103-105654-bnss.json` 及其会话 workspace 中的 plan、result、outline、article。最近的 `20261103-105929-o9hp.json` 仅处理交付路径，没有重新分析报告。详细运行事实继续以这些原工件为准，不单建运行观察记录。
- 使用安装目录 `.venv/bin/python -B` 在原会话工作副本中只读执行 `load_data`、`verify_outline` 和内存 `build_outline`，经 JSON 序列化统一 tuple/list 后与保存的大纲完全一致；共享指标全部 complete。该证据确认正文未经过后续分析改写，且内容偏少已存在于源大纲，不归因于前端漏显。未重新调用数据库或生成任何报告工件。
- Git 对比确认迁移前模板有更多结构解读，但其中包含已在083核实的固定AI/广东结论与无证据判断，不能直接恢复旧模板作为修复。

**成本与取舍**：保留共享查询和严格指标绑定；不靠取消校验、恢复旧硬编码结论或机械填充字数增加篇幅。本次是原因排查，只记录持久缺口，不顺带更改报告模式或重新生成用户已审阅的产物。

**后续路线（待实现）**：明确基础/完整报告的覆盖要求与未请求项展示；按行业确认方向规则和技能词；在统计与渲染之间补充基于具体指标的结构解读、比较、分析推断与院校行动建议；扩充相应类型化事实；统一文案规范并增加分析覆盖、重复文案及建议具体性的验收。高级取数和分析表达需分别验收，不能只以页数或现有 PASS 判定完成。
