# 公众号易读报告、独立导语与卡片链路

状态：已实现；真实素材、草稿创建和API回读通过；最终手机审美验收由用户完成。

当前交付、文案与缓存约定以[记录125](125-report-review-before-draft.md)为准；下面保留各轮历史验证。固定出口已启用，见记录122。

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


### 2026-11-13 按官方新增草稿文档复核

状态：字段校验补强、实际广场API到公众号草稿创建、官方回读和重复保存幂等验证均通过，固定出口未启用且不是当前接口可用的前提。

本轮核对2026-11-02更新的官方draft_add文档及上传正文图片、永久素材、getDraft四份文档。官方draft_get旧猜测路径404，实际文档为api_getdraft.html；业务接口仍为POST /cgi-bin/draft/get。文档文本和响应SHA256见traces/wechat-draft-official-docs-20261113，不能以第三方教程的旧字段限制代替官方当前契约。

代码接入：scripts/report_drafts.py新增draft_fields，上传前验证标题、摘要、原文URL。标题按32字限制，替换此前64字节截断，避免过早截短中文标题；摘要按当前120字限制截断（官方变更记录2026-07-14已对齐120字）。显式article_type=news，支持独立HTML导语在前、图片在后；newspic仅支持相应图片消息结构，不能误用来承载本产品长导语。原文URL校验HTTP(S)、无内嵌用户名密码、UTF-8不超过1024字节。JSON始终ensure_ascii=False，新增回归防止把中文写成字面Unicode转义。正文少于2万字符/1MB、正文图片上传取得微信URL、永久素材封面、确认版本和不确定状态保护保持原逻辑。

用户明确要求逐项执行实际草稿流程后，使用独立验收会话绑定已交付的河源市AI成品，走实际/v1/chat/completions保存指令、Node本地成品确认、带签名的/internal/reports/draft及官方微信API，没有直接绕过pending确认。公司账号后缀b940，当前办公网出口14.19.90.74已放行，WECHAT_API_PROXY为空；服务空闲后只重启wechat-bot加载新模块，签名GET和无确认草稿联网前拒绝验证通过。

实际草稿为“河源市人工智能产业人才需求观察报告”，14张归档PNG哈希一致，最大674796字节，均低于正文上传1MB限制。实际创建14.892秒；官方draft/get回读约0.201秒：article_type=news、17字标题、29字摘要、542字导语、14张微信CDN图片、永久封面和原文URL匹配，图片后无额外文字。微信回读把img.src规范化为data-src，验收脚本须同时识别；最初只识别src造成校验误报，修正后只回读原草稿，没有重新创建。草稿数54→55；重复保存0.233秒返回同一media_id，数量仍55。未调用发布/群发接口，也未给真实粉丝发送测试信息。

回归：36项主库草稿/成品库/公开分析检查、12项机器人传输/草稿桥检查通过。证据为traces/wechat-draft-official-audit-20261113.json，只留media_id哈希，不留token或AppSecret。独立验收会话不向用户原公众号会话发送模拟指令；用户后续在原会话保存相同版本会复用现有草稿。

结论与后续：当前草稿链路已经实测可用；没有固定公网出口不会在当前IP已被放行时自动阻断草稿。记录122的专用固定出口仍待服务器管理员授权，它解决将来办公网IP变化后的长期稳定性，不作为本次草稿验收的前置依赖。后台视觉效果由用户搜索上述标题查看。

官方来源：
- https://developers.weixin.qq.com/doc/service/api/draftbox/draftmanage/api_draft_add.html
- https://developers.weixin.qq.com/doc/service/api/material/permanent/api_uploadimage.html
- https://developers.weixin.qq.com/doc/service/api/material/permanent/api_addmaterial.html
- https://developers.weixin.qq.com/doc/service/api/draftbox/draftmanage/api_getdraft.html
