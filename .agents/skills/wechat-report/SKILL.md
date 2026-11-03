---
name: wechat-report
description: 以真实人才统计、可复核结构分析、多维多类型图和参考文献生成公众号报告，直接交付纯图片成品，不审核大纲。
---

# 微信公众号人才需求报告

真实统计唯一依赖talent-data-query。程序计算同口径比较与可复核结构分析，Pi填写面向行业的行动、验证、调整条件和决策启示。既不让模型猜收入/比例，也不从学历或工资标签推断任务难度。用户只审核最终图片，不请求大纲确认。

## 先取回正确范围

1. 只有必需地区或产业缺失才询问。普通报告默认面向院校人才培养与校企合作；未指定时间用全时间范围的在招记录。不自动添加AI、近一年或其他学历。产业、岗位类型、岗位名称分别处理。
2. 通过共享工具`resolve --kind industry --name 产业名`确认唯一level=0根产业ID；同名细链不能替代根产业。保留用户全部地域、学历、经验、名称和时间条件。
3. 用安装目录`.venv/bin/python scripts/report.py --workdir 当前会话/wechat-report init`初始化。工作区只存数据、文案与输出，不复制/修改脚本，不修补BASE。平台提供真实绝对路径。
4. 在数据目录写最小plan.json：schema=wechat-report-plan/1、filters包含地域及已确认的产业ID。人工智能和智能制造可在安装目录collect_data.mjs调用时加`--profile 人工智能`或`--profile 智能制造`，程序从只读`assets/industry_profiles.json`补入对应方向规则、词表、完整默认章节和院校读者。**profile不替你选择产业、不改变filters**；产业不符即失败。其他主题需显式提供适用analysis，不能回退AI词表。
5. 在该数据目录执行安装目录的`collect_data.mjs --plan plan.json --profile 对应产业名`。不需要另行复制脚本或SQL。首次查询前会包含同筛选城市学历/薪酬必需指标，单城也不扩大范围。默认profile覆盖地域、学历×经验、薪酬、入门条件、方向、城市×方向、相对集中度及能力关联。细节见[data-aggregation.md](references/data-aggregation.md)。已有同范围真实数据直接复用，修改地区或筛选必须重取；未查询统计不补零。

最小计划的结构如下，只替换地区、上一步已解析的产业ID并保留用户其他筛选；profile写在采集命令上，不放入JSON：

```json
{"schema":"wechat-report-plan/1","filters":{"region":{"level":"province","name":"用户指定省份"},"industries":[{"id":"本次resolve根节点字符串ID","includeDescendants":true}]}}
```

## 数据就绪后使用专用工具

平台提供`report_next / report_submit / report_core / report_build`时必须优先调用，不再用通用文件工具写整篇JSON。

1. `report_next`读取当前短批次及预检。程序已给定title、findingIds、interpretation等结构结论，保留它们。
2. `report_submit`只提交本批全部章节的key、action、validation、decisionRule，各至少三十字。行动明确对象、任务、产出；验证明确真实岗位/企业/学生产出证据；调整条件明确什么结果会改变建议及如何调整。不复述数字或内部写作提示。
3. 工具直接返回下一批，持续提交。到executive阶段使用`report_core`，按顺序提交三个claims的implication，以及closing和limitations。opening由本次真实筛选与结构分析给定，形成总分总；不把单城筛选说成地域集聚，不把条件覆盖率说成录用率。
4. 到analysis_ready后`report_build`连续完成预检、分析重验、内部排版、数据验收、真实渲染、图片质检、文章、核查与纯图片打包。不要中途以计划结束。失败保留真实数据与进度，不用旧交付声明假称成功，也不反复重试同一错误。

无专用工具时使用同一受信入口：`report.py ... next`，照模板只补可编辑字段并保存report_part.json，再`report.py ... accept report_part.json`，持续到analysis_ready后build。也可analyze取得受信writing_draft，补完行动/启示后assemble与build。显式修改用revise按本轮标识重开文案并归档旧稿，不只重渲染旧建议。命令见[安装与命令](references/project-installation.md)。

## 内容与图表门槛

结构分析与事实由同一保存结果重算，模型不能改受信结论。标题、指标与比例有真实来源；建议不能仅凭高薪扩招，不能按学历或薪酬分配技能难度，不能将上四分位当工资封顶，不能将低词频反推课程缺口。因果、增长、短缺、实际录用与供给缺口没有对应证据时不下结论。研究边界面向读者，不能复制“已给事实”“不补零”等写作指令。见[研究分析](references/research-analysis.md)。

整篇最多一张柱状图，且联合城市薪酬中位数、学历份额和岗位量三个指标。其余按真实关系使用连接、条件比例点图/矩阵、面积与薪酬、分位区间、方向集中度、能力关联等。单城或单学历不强凑跨组比较，省略原因保留在内部选图记录。不把连接当人才流动，不用边际比例猜联合收入。见[图表](references/chart-gallery.md)。

## 交付与公众号

build产生有序PNG、纯图片网页、仅PNG的ZIP及会话根delivery.json，平台只返回真实产物链接。正文SQL、分析JSON、内部核查表不进入公开交付。官方背景与文后参考文献由核验目录附后，年份/范围/分母独立；全行业年度研发数据不能证明AI岗位样本代表性。

成品末尾由平台询问是否存公众号草稿。用户明确确认后才走私有草稿桥：全部文字总结、方法与参考文献在前，全部报告图片在后；不发布或群发。长页需要上传分段时保留所有像素，原成品PNG不改。Pi不读取公众号凭据、不直接运行publish_draft.py。

成功后仅回复“报告图片已生成，请审核成品”，由平台展示资源与保存询问。没有有效产物就明确未完成，不输出假成功。
