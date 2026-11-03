---
name: wechat-report
description: 基于共享人才数据库统计生成地区与产业的微信公众号人才需求报告，交付可审阅大纲、图文页面、文章和内部核查表；适用于产业人才观察和院校人才培养分析。
---

# 微信公众号人才需求报告

本技能负责研究问题、分析和呈现；真实统计唯一依赖 **talent-data-query**。共享工具负责解析实体、统计、薪酬、方向分类、技能词和证据；本技能不维护数据库连接、SQL、行业字典或第二套统计算法。

## 环境与取数

先读 [project-installation.md](references/project-installation.md)，按本次实际加载目录取得安装路径、创建会话工作副本。安装目录只读；Node 收集入口优先使用安装目录的绝对路径，Python 脚本在工作副本运行，解释器使用安装目录 .venv/bin/python。

1. 根据用户要求明确省/市/全国、产业或岗位名范围、时间范围、读者与分析角度。产业、岗位类型、名称包含是不同条件；先用 talent-data-query 的 resolve 选择实体。未要求时间窗时统计全时间范围的在招记录，不能自动添加旧版近365天或AI条件。
2. 读取共享 Skill 的请求/指标规范，写 wechat-report-plan/1 计划。格式、章节与方向/技能规则见 [data-aggregation.md](references/data-aggregation.md)。只请求本报告需要的统计。
3. 调用安装目录 scripts/collect_data.mjs --plan plan.json，通过共享 CLI 获得统计并生成工作副本的 report_data.json、report_binding.json。部署路径由 TALENT_DATA_QUERY_CLI 或受信 --query-cli 指定；不要读取密码或创建本技能数据库配置。
4. 检查返回状态与 coverage，失败或缺失不填零、不回退旧数据。需要新增统计时扩展共享查询能力。方向及技能没有明确规则时先用基础章节，不套用固定AI分类；用户要求完整版时先补齐规则再查询。
5. 只有用户明确要求演示时才使用 example/report_data.json，后续命令均带 --demo，并标注离线样例。

业务指标只读完整结果，stdout 为预览。数据读取时间不是岗位发布时间；企业关联地址不是已核验的实际工作地，岗位记录数不是实际招聘人数。跨产业样本可能重叠，不能直接加总。

## 大纲、图文与交付

- 用 scripts/gen_outline.py 生成大纲，先交付 output/outline/outline.md 审阅；确认后渲染。默认章节可随已完成统计调整，空数据/无薪酬/单城市不硬套固定结论。
- 正文、图表引用绑定中的 metricId、字段和完整分母。量化句由 bound_report.py 的类型化事实投影生成，变更句式需扩充相应事实类型；叙述与建议可编辑，数字变化需重新查询。大纲 bindings 随投影更新并校验；不以“这个数字在别处出现过”作为通过依据。分析推断和课程建议明确为分析，单次横截面不生成市场增速或招聘趋势。
- 依次运行 verify_data.py --stage data、render_report.py、build_article.py、verify_data.py --stage final。前置校验中的渲染状态为 pending，不能作为最终通过。工作副本保留数据；大纲确认即使超过15分钟也直接读本地结果，不重新查库。
- evidence_sheet.py 从实际 evidence 生成 output/internal/evidence_核查表.xlsx，包含真实SQL和查询引用，仅供内部审计。pack_delivery.py 依据本次图片 manifest 打包公开产物，并生成 output/public/site、output/public/report.zip 和会话根 delivery.json；工作副本在 wechat-report/ 时传 --workspace ..。网页目录只复制文章与已验证图片，公开ZIP排除内部核查表、来源绑定和查询证据。
- 输出先正文与图表一致，再检查实际图片、裁切、缺图和热力图。报告末尾保留数据来源、方法、日期与缺口；章末总结写洞察和行动启示。
- 在广场运行时，由平台读取 delivery.json 保存产物并提供网页分享和资源下载按钮，不自行拼接URL；本地工具运行时保留同样文件供调用方接管。仅当用户明确要求推送且已配置公众号时执行 publish_draft.py，只存草稿，不自动群发或发布。密钥、令牌只留本地。

文案、图表与微信操作按需读 [copywriting.md](references/copywriting.md)、[chart-gallery.md](references/chart-gallery.md)、[image-spec.md](references/image-spec.md)、[article-styles.md](references/article-styles.md)、[wechat-publishing.md](references/wechat-publishing.md)。文章从同一已绑定大纲生成；引用范文时以本次真实指标替换并核验。
