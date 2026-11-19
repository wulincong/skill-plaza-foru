# 126 · 岗位智能匹配与真实招聘接口

**状态**：已实现。真实接口取回100个去重候选、真实低权Pi生成带简历匹配报告和LAN表单已验；100候选全量模型评估至20岗的端到端质量/耗时尚未专项实测，程序25选20回归已通过。

## 动机与方案

学生选择求职条件后查询最多100个候选，按JD与真实简历推荐最多20个，交付匹配度、依据、差距与建议。接口筛选和分页、去重、评分、引文和网页由程序维护，模型做逐岗语义判断；不复用人才统计库，不新增另一个模型客户端，不自动投递或联系企业。

## 已核实接口及字典

2026-11-19从招聘平台官网静态JS和公开API核实：

- POST `https://job.foru-ai.com/api/business/front/lookForWork/queryListForPage`，请求 `{size:100,current:1,model:{keyword,city,...}}`；响应data.records/total/pages/current/size，code=0，默认size10。广州前端实际total112，size100一次返回100个不同ID。
- GET `/api/oauth/dictionaryItem/codes?codes%5B%5D=EDUCATION&codes%5B%5D=SALARY&codes%5B%5D=INDUSTRY&codes%5B%5D=POSITION_TYPE&codes%5B%5D=EXPERIENCE`，返回真实字典。冻结到技能references/dictionaries.json，前端jobDictionaries.ts使用相同快照。接口变化需同步刷新两处并复验。
- 工作性质positionType：SHIXI实习/XIAOZHAO校招/SHEZHAO全职/JIANZHI兼职；行业IT与用户最初INTERNET等推测不同；LESS_THAN_5K实际3–5k，LESS_THAN_3实际1–3年，不使用最初推测字典。
- 毕业状态无独立字段。未选experience时在校/应届映射ON_CAMPUS/GRADUATING；已选经验则保留该Key，毕业状态只用于匹配。下拉“不限”省略条件。学历接口为岗位要求精确筛选（DAZHUAN实测22条），不是自动包含所有低学历门槛。
- minSalary/maxSalary实测表现似乎要求岗位区间覆盖目标，未取得后台谓词，首期不实现猜测的区间交集；只用官方salary档位。薪资展示按网站K/月，奖金、薪数、实习结算不保证。
- 官方详情链接 `https://job.foru-ai.com/#/station/detail/{positionId}`；详情只读GET `/api/business/front/lookForWork/getDetailByPositionId/{id}`。列表正文positionDescription、详情positionDesc。本次查询无需凭据，若后续接口要求鉴权应独立托管，不把401当空结果。

## 接入与数据

- `web/src/data/useTaskConfigs.ts`注册job-matching：岗位、城市必填，薪资/工作性质/行业/学历/毕业状态/经验六个下拉，简历摘要、可选PDF/DOCX/TXT/MD附件及补充说明。`jobFilters`把label转真实Key，UsePage.buildPrompt在原始用户需求后追加“岗位接口筛选”JSON。
- `web/server/lib/skills.ts`注册已安装技能；`piRunner.ts`显式挂载job-matching、report-rendering和技能pi-tools.mjs。`index.ts`每轮写 `.job-request.json`，含runId、当前原话、用户消息及实际附件路径，仅本地保存。
- 原生工具job_candidates在当前工作区运行Python matching.py，固定上游，只传filters到招聘接口；本地解析简历不出站。当前表单JSON锁定查询范围，自然语言后续授权以当前message为准，不锁死旧表单。
- `matching.py query`请求100、按ID去重并必要时翻页，达到100即停；记录总数、实际候选、读取时间、筛选和分页异常。非成功、格式异常和重复分页分别处理。ID用字符串，避免长整型精度丢失。
- 候选存 `.job-matching/<uuid>.json`，工具返回snapshot/sha256、原始JD和规范字段；`.job-query-state.json`记录本轮成功/空/失败。简历摘要自动从表单提取，单个用户附件可自动解析；多附件需显式指定实际上传文件。PDF扫描件停止，不编造；DOCX读取前检查正文解压大小。

## 匹配、来源与交付

内部job-assessments.json包含snapshot/sha256、summary、全部候选assessments、前20详细details。assessments有id、eligibility=pass/review/exclude、skills/experience/direction/preferences各0–4或null及理由。权重40/30/20/10，未知维度不计为零，而是不输出完整总分；无简历禁止输出完整匹配分。先pass后review，再按分排序，ID稳定打破并列。exclude不进推荐。

`matching.py preview`返回程序前20名；模型仅补这些详细JD/简历证据、差距和建议。`build`核对候选全部覆盖、ID无重复、来源指纹与本轮runId、推荐集合、引文出处。后续轮次改条件必须重新查询，不复用上一轮快照。来源/请求/状态禁止write/edit，简单只读命令及read核验允许，避免只读也被拦导致循环。

JD与简历引文各最多300字，建议10–60字短摘录；支持空白与全半角归一后定位，但报告引用仍用对应原文片段，不能凭归一规则改语义。网页所有字段递归脱敏常见手机号、邮箱及简历中明确住址，原始简历及快照不进公开目录。脱敏不能保证识别任意隐晦个人信息，模型仍须只摘录岗位相关经历。

构建以评估文件所在目录定位工作区，不依赖shell cwd，禁止技能安装目录；render/register子进程显式cwd。共享minimal渲染后登记delivery.json，来源有真实岗位链接、读取时间与范围，分数不是概率，少于20如实呈现。没有匹配结果提示用户选择放宽，失败不产出冒充成功的报告。

## 成本、取舍与验证

直接使用公开接口与Python标准库，复用Pi和现有报告交付，避免新增数据库/接口账户。代价是字典快照需维护，语义匹配仍依赖模型，尚无自动简历真实性验证。联系方式规则脱敏只覆盖常见格式；不声称匿名化保证。只读取招聘资料，不执行投递/收藏/联系。

已验证：Python13项（分页100/去重/字典/错误/未知评分/20条排序/引文/隐私/跨轮/工作区）；Node下拉、查询范围与hook4项，及已有HTTP/交付相邻回归通过；技能格式、文档索引与Vue生产构建通过。Chrome1280/390核实六个下拉、真实Key提交、报告无横向溢出与官方详情链接。用户同时修改AGENTS.md存在末尾空行告警，本次不覆盖该文件；本次文件单独diff检查。

真实低权Pi/优才样例查询广州前端实习，实际1条，仅推荐1条；初轮暴露遗漏简历参数，已改表单摘要自动读取。复测20261119-142058-lx9r返回含真实简历证据、75/100及学历/应届待核验的报告，96秒完成；这不代表100选20的耗时承诺。真实100条查询另行成功，程序25选20构建已验。公开报告入口由当前副本LAN4189生成，wlc服务未改。

## 后续

对100候选全量匹配做同输入质量与耗时验收；核实岗位有效性、字段与JD矛盾处理；按需要增加用户可调权重或明确的必选条件。多城市、多简历和招聘接口鉴权变化另做接入验证。未实现自动投递和录用预测。

## 报告面向求职决策与量化对比 · 2026-11-19

已实现：用户要求不展示检索条件等过程。matching.py的build_page移除检索条件、参数、候选和接口总数，将资料日期和来源保留到页脚；岗位列表保留真实薪资、链接和资格限制。summary明确不复述检索过程。新增岗位量化对比（单岗为匹配指标）：四维按40/30/20/10权重换算分、原有综合分、已评估维度n/4，均取自已校验assessment，未知显示未评估而非0；综合分不完整时仍未评估。摘要指标仅统计推荐岗位、可优先考虑和资格待核验数量。没有新增生成评分的模型调用或改变排序，也不输出推测的成功概率。公开分页异常改为业务限制提示，原始取数信息仍保存在内部快照。

验证：岗位匹配Python回归15项通过，含隐藏过程与未知维度不补零；真实渲染HTML断言与1280/390浏览器无页面溢出通过，文档索引检查通过。模板从磁盘加载，后续报告直接采用新格式，无需重启后端。

## 期望城市选填 · 2026-11-19

用户调整：仅目标岗位必填。表单city取消required，jobFilters忽略空白城市；原生工具filters.required仅keyword；Python允许省略city，传空白时清理后不发上游。未指定城市不推测所在地，不在已有简历城市上自动增加限制。城市填值时原有精准条件与scope锁定不变。技能与指南同步更新。

验证：16项Python、4项Node回归及Vue构建通过；真实接口省略city成功获取100个去重候选。新会话原生工具从磁盘加载新schema，无需重启或中断已有任务。
