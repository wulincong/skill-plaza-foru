---
name: wechat-report
description: 基于共享人才数据库统计生成地区与产业的微信公众号人才需求报告，交付可审阅大纲、图文页面、文章和内部核查表；适用于产业人才观察和院校人才培养分析。
---

# 微信公众号人才需求报告

本技能负责研究问题、深入分析和呈现；真实统计唯一依赖 **talent-data-query**。共享工具负责解析实体、统计、薪酬、方向分类、技能词和证据；本技能不维护数据库连接、SQL、行业字典或第二套统计算法。**先完成真实数据分析，再生成报告；图表、数字罗列和固定建议不算完成分析。**

## 环境与取数

先读 [project-installation.md](references/project-installation.md)，按本次实际加载目录取得安装路径、创建会话工作副本。安装目录只读；Node 收集入口优先使用安装目录的绝对路径，Python 脚本在工作副本运行，解释器使用安装目录 .venv/bin/python。

1. 根据用户要求明确省/市/全国、产业或岗位名范围、时间范围、读者与分析角度。产业、岗位类型、名称包含是不同条件；先用 talent-data-query 的 resolve 选择实体。未要求时间窗时统计全时间范围的在招记录，不能自动添加旧版近365天或AI条件。
2. 先读 [research-analysis.md](references/research-analysis.md)，按需要回答的问题拟定研究维度，再读共享 Skill 的请求/指标规范，写 wechat-report-plan/1 计划。格式、章节与方向/技能规则见 [data-aggregation.md](references/data-aggregation.md)。通常应研究地域差异、学历×经验、总体与职教子样本薪酬、岗位方向及能力组合；按相关性选择，不只照抄基础示例。
3. 调用安装目录 scripts/collect_data.mjs --plan plan.json，通过共享 CLI 获得统计并生成工作副本的 report_data.json、report_binding.json。部署路径由 TALENT_DATA_QUERY_CLI 或受信 --query-cli 指定；不要读取密码或创建本技能数据库配置。
4. 读取完整结果与 coverage，失败或缺失不填零、不回退旧数据。方向及技能按研究主题提出显式规则/词表并核实适用性，不套用固定AI分类；规则归类须披露覆盖率。需要新增统计时通过共享查询补齐。维度未请求或不可用必须说明原因，不能把基础统计称作完整产业分析。
5. 只有用户明确要求演示时才使用 example/report_data.json，后续命令均带 --demo，并标注离线样例。

业务指标只读完整结果，stdout 为预览。数据读取时间不是岗位发布时间；企业关联地址不是已核验的实际工作地，岗位记录数不是实际招聘人数。跨产业样本可能重叠，不能直接加总。

## 大纲、图文与交付

- 运行 scripts/report_analysis.py，读取 output/analysis/analysis_evidence.md、完整 report_data.json 及必要的共享结果。脚本只整理可复核事实，**不会替你完成分析**。按研究规范独立撰写 report_analysis.json，逐维度形成“具体发现与比较 → 结构解释/待验证推断 → 面向读者的行动 → 验证方式”，并做跨维度综合判断：synthesis 总判断 + 2-4 张结论卡（动作短语标题 + 决策要点，每卡认领支撑事实，数字只出现在其后的事实段落）。空样本直接反馈缺口，不生成研究报告。
- scripts/gen_outline.py 必须消费已完成的分析稿，缺失、占位、数据版本不符或章节缺项即停止。先交付 output/outline/outline.md 中的实际分析与图表供审阅，不能只展示标题、页数和“亮点”；确认后渲染。旧工作副本需同步本次 scripts/references，保留原数据和用户品牌/文案。
- 正文数字使用带字段、分母和公式的 findingIds，图表绑定 metricId；量化事实由保存数据重新计算校验。新增所需事实应扩充报告侧派生投影，新增原始统计仍走共享查询。解释和建议由智能体结合证据撰写，不能恢复固定行业/地区结论；单次横截面不生成市场增速或招聘趋势。检查器可验证分析结构和数字引用，解释合理性仍须逐章审阅。
- 依次运行 verify_data.py --stage data、render_report.py、build_article.py、verify_data.py --stage final。前置校验中的渲染状态为 pending，不能作为最终通过。工作副本保留数据；大纲确认即使超过15分钟也直接读本地结果，不重新查库。
- evidence_sheet.py 从实际 evidence 生成 output/internal/evidence_核查表.xlsx，包含真实SQL和查询引用，仅供内部审计。pack_delivery.py 依据本次图片 manifest 打包公开产物，并生成 output/public/site、output/public/report.zip 和会话根 delivery.json；工作副本在 wechat-report/ 时传 --workspace ..。网页目录只放标题与已验证分页图片（图内已含全部文字，不再重复正文）；文字版文章在公开 ZIP 的 article/ 内。公开ZIP排除内部核查表、来源绑定和查询证据。
- 输出先正文与图表一致，再检查实际图片、裁切、缺图和热力图。报告末尾保留数据来源、方法、日期与缺口；章末总结写洞察和行动启示。
- 在广场运行时，由平台读取 delivery.json 保存产物并提供网页分享和资源下载按钮，不自行拼接URL；本地工具运行时保留同样文件供调用方接管。仅当用户明确要求推送且已配置公众号时执行 publish_draft.py，只存草稿，不自动群发或发布。密钥、令牌只留本地。

文案、图表与微信操作按需读 [copywriting.md](references/copywriting.md)、[chart-gallery.md](references/chart-gallery.md)、[image-spec.md](references/image-spec.md)、[article-styles.md](references/article-styles.md)、[wechat-publishing.md](references/wechat-publishing.md)。文章从同一已绑定大纲生成；引用范文时以本次真实指标替换并核验。
