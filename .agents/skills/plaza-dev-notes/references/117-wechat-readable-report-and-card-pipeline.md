# 公众号易读报告、独立导语与卡片链路

状态：已实现；真实素材、草稿创建和API回读通过；最终手机审美验收由用户完成。

## 动机

旧草稿将全部图片文字再次拼接到图片前，各章重复教学实施视角；消息卡片使用全局空封面。用户要求参照其广东人工智能PDF和授权仓库 Official-Account-Skill 的 article-styles/copywriting，使导语独立、正文易读、缓存按真实地区产业区分。

## 约定和接入点

- `.agents/skills/wechat-report/scripts/article_content.py:26`
- `.agents/skills/wechat-report/scripts/readable_layout.py:11`
- `.agents/skills/wechat-report/scripts/editorial_projects.py:89`
- `.agents/skills/wechat-report/scripts/editorial_prose.py:8`
- `scripts/report_library.py:20`
- `scripts/report_drafts.py:103`
- `web/server/pi/report-workflow.js:54`

- `wechat-editorial-prose/3`：摘要加三条融合结论；正文按招聘格局、入口、门槛、薪酬与交叉分析组织。学历/经验、城市方向/相对专长、能力网络/方向能力合并，仍保留全部分析与指标绑定。重复事实通过 `section-distinct` 投影去重，不能在渲染后任意删数字。
- 图后短评由Pi提供；内部validation/decisionRule和不展示的核心辅助字段由程序填充。`report_submit`只写key/action，`report_core`只写closing。固定模板先预检，避免让模型反复修复不可修改的程序文案。
- 公开短评禁止把描述提及推成企业偏好、能力强度或重要性测量，禁止把条件交叉推成影响机制，禁止在未测量的章节增加城市交叉薪酬/技能。旧稿重新组装时仅修复违规短评，`analysis.editorialRepairs`留存原因；不得放宽来源与数字校验。
- `wechat-article-lead/2`读取 `references/article-styles.md` 的机器可读规则并保存指纹，生成约五百字独立导语；不复制图片摘要全文。预览和真实草稿复用同一HTML；正文全部在图片前，方法和文献保留在图片报告末尾。
- 分享封面900×500，位于公开站点assets/share-cover.png，不作为报告正文页或PNG压缩包额外页。卡片标题含地区与产业，描述由已验证岗位量/企业数组成。机器人只接受该份交付的同源封面，不能执行模型伪造的图片URL。
- 卡片标题、摘要和封面在机器人report_sessions持久化并向旧表增列；优先发送news，显式失败才退回文本链接。缓存回调可直接回复news，查询和暂不保存保持原卡片。真实微信客户消息收件箱外观仍需用户手机验收，不用合成回调代称真人收件。
- 默认成品库 `education-readable-editorial-v4.2`。完整章节还必须使用对应根产业的默认分类；归一化只忽略OR词序和空roleIds，保留首命中规则顺序。自定义分类保持custom-scope，旧报告保留。复合索引覆盖省份/产业/版本/状态/数据日期，避免缓存查询扫描大段元数据。
- 七个指定广东产业各有显式方向与词表，不能套用AI分析。新增广东统计公报、汽车应用和商贸政策资料；产业产量、政策部署与岗位统计分别解释，不据产量推算人才需求。

## 成本与取舍

选择绑定统计与短模型文本，而非让小模型重写整篇后再逐一核对数字。合并相关页以减少重复，保留字号和全部证据，不靠缩小图片、裁内容或删除图表过关。未采用复制全文的长导语、按学历分配技术层次、凭单次快照推断增长或用高词频等同实际技能的重要性。

未引入公众号凭据到广场工作区。公司Secret仍只在服务器私有运行配置中，草稿通过既有签名桥保存；仅发布草稿，不群发或发布。API回读的text/plain需按UTF-8解析，不能把客户端解码乱码误判为真实后台内容乱码。

## 验证与后续

已验证：主库30项单元回归（含误推断、独立导语和自定义分类缓存污染）；机器人33项；Pi工具和范围8项；十三范围当前构建、图表布局和数值绑定通过。逐份检查导语、合并章节和图表篡改均被拒绝。真实草稿与同版本幂等回读见traces/readable-v4-real-draft-summary.json；真实gunicorn九范围签名回调见traces/readable-v4-live-callbacks.json。冷启动实测与细分耗时保存在traces/readable-v4-cold-*.json，不把复用统计或仅重排耗时当成首次取数时间。

三轮内容检查分别处理固定教学视角与重复、版式与独立导语、未测量推断。最终图片和验收包由用户审阅；新产业仍须先解析真实根节点和声明规则。后续可扩充已核对官方来源，不能使用搜索摘要直接写数字。

补充验收（2026-11-05）：真实Vue页面缓存交付0.46秒，并通过页面确认保存机器人草稿；最新AI草稿官方接口回读549字符导语和17张图片通过。安徽AI未命中缓存的真实签名消息耗时106秒，返回报告卡片并保留保存提示；测试最初逐字要求“公众号后台草稿箱”，实际回复“公众号草稿箱”，功能正确，已按语义核对并记录原始日志。最终13范围共39次导语/段落/图表篡改拒绝，见readable-v42-final-binding-audit.json。机器人补丁806f67d（wechat-report-followup-v4.2-20261105）在新报告SSE正文非空时保留结构化存稿追问，并尊重用户已取消的状态。
