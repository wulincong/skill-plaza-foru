# 107 · WeKnora 知识检索基础 Skill

**状态**　仓库内的基础 Skill 已实现，处于未上线状态。已通过独立 CLI 验证目录定位、整库和限定文档检索、来源复核。广场侧接入暂缓。

**动机**　让广场业务技能引用另一团队维护的资料。广场已有共享取数 Skill 的接入方式，见 `web/server/index.ts:162-165`。Pi 显式加载获准的扩展和所选 Skill，见 `web/server/lib/piRunner.ts:545-559`。

### 实例验证 · 2026-11-04

对团队提供的 HTTPS REST 地址进行了只读探测。`GET /api/v1/system/info` 报告版本 `0.6.0`。请求自有库列表时，无凭据返回 HTTP 401，首组凭据通过 `X-API-Key` 鉴权后返回 HTTP 200、`success: true` 和空数组。共享库列表 `GET /api/v1/shared-knowledge-bases` 也返回 200 和空数组。

`POST /api/v1/knowledge-search` 仅传查询词返回 HTTP 400，实例要求至少给出库或文档 ID。[v0.6.0 检索接口](https://github.com/Tencent/WeKnora/blob/v0.6.0/docs/api/knowledge-search.md)

换用第二组凭据后，可见 31 个自有库、0 个共享库，其中 7 个自有库报告了非零文档数。列表中「纺织专业教学标准知识库」的 `chunk_count` 为 0，但该库能返回实际检索命中，因此不能用列表分块计数判断能否检索。

在该库查询「现代非织造技术专业面向哪些典型工作任务和职业岗位？」得到 8 条结果，目标专业教学标准排第 8。按目录定位同名 PDF，再以 `knowledge_ids` 单独指定该文档，得到 1 条带原文的命中。`GET /chunks/{knowledge_id}` 返回的第 0 号原文分块确认了「非织造工艺与生产管理」等岗位。整库命中返回的 `content` 含比其分块 `id` 所指原文更长的上下文，引用某一分块时应逐段核对。用户点名文档时，建议在授权库目录中先定位该文档，再限制检索范围。

### 基础组件与验收 · 2026-11-04

入口 `.agents/skills/weknora-retrieval/SKILL.md:1` 供受信调用方独立使用。`scripts/retrieve.py:43`（本段路径相对该 Skill）从进程环境取得凭据和必填库白名单，固定 HTTPS 目的地，拒绝重定向。`scripts/retrieve.py:134` 按获准 ID 读取库元信息，校验请求范围及文档归属。`scripts/retrieve.py:93` 实现整库检索与仅传 `knowledge_ids` 的文档检索，返回带来源标识的有界预览。`scripts/retrieve.py:110` 提供目录和原文分块分页，逐项核对库与文档归属；原文分块保留完整正文。空结果与失败分别使用 `empty` 和具体错误状态。环境白名单只适用于受信进程，未来线上由宿主负责授权。

通过真实入口复验纺织库：列出单个获准库，按标题找到目标 PDF，整库查询得到 8 条结果，限定该文档得到 1 条，原文首两页读取成功并在第一页复核岗位表述。无匹配目录返回 `empty`，白名单外的库请求返回 `forbidden`。技能格式校验和 6 项离线回归通过，覆盖来源范围、文档检索参数、空结果和故障。广场 `GET /api/skills` 实测返回 9 项，未列出该组件；本次没有把它接入在线会话或业务技能。

### 未来广场接入与取舍

- 首期由业务 Skill 调共享检索工具，后端按当前调用者的授权范围选择库 ID，向固定上游发送 `query` 和 `knowledge_base_id`。只向模型交付相关片段，保留 `knowledge_title`、`knowledge_id`、分块 `id` 和 `content`，以便引用。分别处理无命中、无权限和上游失败。
- 上游凭据由广场后端持有。当前沙箱配置显式允许读取 `web/.env`，见 `scripts/setup-pi-sandbox.sh:103-106`。应使用沙箱无读取权限的后端专用凭据配置，将调用限制在获准会话和库。资料向哪些广场用户开放，由资料方确认。
- 0.6.0 的官方 MCP 适配器还要单独运行，工具目录同时包含检索和创建、删除。仅为广场增加检索时，REST 更容易限定调用面，也沿用现有 Skill 入口。若资料方将来为多个客户端统一发布限库、限工具的 MCP 端点，可再评估；上游 v0.8.2 已加入按空间发布端点的能力。该实例是否另行部署 MCP 适配器仍未验证。[v0.6.0 MCP 说明](https://github.com/Tencent/WeKnora/blob/v0.6.0/mcp-server/README.md) · [v0.8.2 发布记录](https://github.com/Tencent/WeKnora/releases/tag/v0.8.2)

**后续验收**　资料方确定各用户或业务技能可以使用的库范围。广场侧待验证指定文档定位、引用来源、无命中和越权拒绝。生产凭据通过双方约定的秘密渠道交接。
