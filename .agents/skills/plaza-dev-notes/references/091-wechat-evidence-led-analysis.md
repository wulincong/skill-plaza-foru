# 091 · wechat-report：先完成真实数据分析，再生成报告

**状态**：已实现（2026-11-03）。63项共享查询/报告集成测试、技能格式校验通过；使用原山东真实结果完成分析、大纲、11页渲染、文章、核查表和公开包验证。未验证真实在线模型的新会话行为；旧会话脚本副本需同步更新，不能把开发侧验证说成线上智能体已验收。

## 动机

087接入共享取数后，默认大纲仅有少量事实模板，运行可以跳过分析直接渲染；数据/图片通过不代表研究充分。用户明确要求对真实数据深入分析后再生成报告。目标是在报告链路中保留可追溯比较、智能体解释与行动建议，并拦住原始骨架。

## 协议与接入

- 共享取数、report_data.json与report_binding.json协议不变。不新增数据库入口，不重算原始薪酬分位；报告侧只对已保存聚合做份额、条件比例、差异、集中度与子样本比较。新增原始统计仍通过talent-data-query取得。
- `.agents/skills/wechat-report/scripts/report_analysis.py:40` 的derive_findings输出带id、section、text、kind、paths及必要分母/样本量的事实；覆盖地域集中度、类别份额、学历×经验条件比例、薪酬分位、职教池与总体/城市比较、方向/技能交叉。它只整理证据，不自动编造解释。全国范围不按未限定省份的城市名连接职教池与总体；技能事实分别保留有描述/全岗位分母，词间不加总；小样本方向薪酬/LQ不作强弱排名。
- `report_analysis.py:219` 的wechat-analysis-evidence/1包含来源数据SHA-256、来源contentHash、findings、requiredSections和coverageGaps。未请求维度也进入缺口，不能因当前请求complete就宣称完整研究。
- `report_analysis.py:409` 生成output/analysis/analysis_evidence.json/md及analysis_draft.json。主智能体必须读完整结果，独立撰写工作副本根report_analysis.json；脚本不把空结构自动写成完成稿。
- **wechat-analysis/1**：sourceDataSha256、sourceContentHash、evidenceHash绑定证据版本；executive包含findingIds与跨维度synthesis；sections包含key、结论式title、findingIds、interpretation、action、validation；limitations记录边界，coverageGaps如实保留。事实不足时补查询或披露缺口，不填猜测数字。
- `report_analysis.py:252` 验证各可用主题的分析覆盖、相关事实/比较引用、综合判断的维度、空稿/重复建议、未绑定数字和版本指纹。原数据内带数字的类别/技能标签可以原样引用；不能利用这一例外写新增比例。只有规模计数或空样本不能生成研究报告。
- `scripts/gen_outline.py:162`、`:190` 要求真实数据的--analysis（默认report_analysis.json），生成**wechat-outline/3**，嵌入analysis及各页analysis_key。数字段落使用finding投影，解释/建议/验证文字逐项保留；演示仍需显式--demo，且不能冒充真实报告。
- `scripts/bound_report.py:72` 按findingId重算文字并验证输入字段，`:126` 同时验证源指标与报告中的分析正文。render_report、build_article、verify_data、pack_delivery沿原入口调用，因此删除analysis、改正文或跳过分析均不能继续。旧/2大纲要补完分析再生成；历史静态网页/已保存下载不被本次改动重写。
- `scripts/verify_data.py:34` 单列分析覆盖检查，并明确解释合理性仍需审阅。检查器不能证明自然语言必然有洞察；主智能体仍须判断证据是否支持解释、建议是否面向当前读者。
- `scripts/render_report.py:289` 按更长的分析/总结/附录估算高度，取消2800px截断上限。仍是估算，不声称任意长文本均不会溢出。
- `scripts/pack_delivery.py:93` 从公开大纲移除内部analysis协议；网页保留事实、解释与建议，内部证据和SQL仍不进入公开包。
- `SKILL.md:15`、`:24` 与references/research-analysis.md明确研究顺序、补取数/未覆盖边界和实际内容审阅；copywriting.md合并为一套有效规范，取消每屏固定字数与旧AI/广东示例，不以填充篇幅当作深入分析。

## 验证与证据边界

- `node --test --test-reporter=dot scripts/talent-data/*.test.mjs`：63/63通过。报告测试包含跳过分析/空稿、旧证据、错误主题、删章节、重复行动、单维度综合判断、量化文案或字段篡改、只有计数的伪研究，以及真实标签ROS2与未绑定数字的区别。保留原数据工件、查询适配、空薪酬/无描述、缺图和公开包隔离测试。
- skill-creator的quick_validate.py使用本机python通过；技能.venv没有PyYAML，未为格式检查修改报告依赖。Python脚本AST及git diff --check通过。
- 真实验证采用原运行保存的40507条山东智能制造记录，report_data.json逐字节未变，未重新查库。由本次开发智能体据证据撰写分析，不使用合成测试文案。原始来源、分析稿和结果摘要在reports/query-benchmarks/2026-11-03-wechat-analysis/{reviewed-analysis.json,validation.json}；raw/session保存本地源工件与生成产物并被忽略。
- 数据绑定、完整分析保留、11页Chrome渲染、render_check、文章、内部工作簿、公开ZIP通过。目检学历、职教和附录页内容及页脚；未声称每张图片逐字OCR或所有主题/长度验收。
- 本次不补查原计划缺失的岗位方向/技能，报告明确披露，不能将其用于具体技术课程配置；也未重写原在线会话或调用公众号。

## 成本与取舍

- 保留“程序计算事实、智能体解释与提出行动”的分工。否决仅增加提示词、恢复旧固定结论或放开任意数字模板：这些不能防止骨架继续进入渲染，也会破坏统计对象绑定。
- 分析稿与报告内容重复保存，校验时重建证据有额外成本；换取数字可复算、解释不会在渲染时丢失、修改分析后必须重新生成的边界。
- 事实按有限派生规则计算，仍不覆盖所有研究问题；需要新事实时扩展派生类型，需要原始指标时扩展共享查询。自然语言校验只能作为完整性门槛，不能替代对论证的审阅。
- 本次不部署新模型、不改前端或源库，不把未查维度填成零，也不在统计和生成之间重复刷新同一数据。

## 后续路线

1. 在隔离新会话验证在线智能体是否主动规划方向/技能、读取完整证据并写出合格分析；旧工作副本保留用户数据与品牌，更新scripts/references后再继续。
2. 按真实研究问题扩展分母明确的比较、方向/技能策略及事实投影；对未覆盖维度说明原因，不默认所有产业共用同一套词表。
3. 更长文案、更多方向和不同主题需要独立布局验证；如估算不能满足，再引入实际DOM测高/分页，不能静默裁切分析。
