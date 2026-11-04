# 107 · WeKnora 知识检索接入选型

**状态**　设计建议，待团队确定目标库和使用范围。已验证实例版本、REST 鉴权和检索参数校验。尚未实现 Skill，也未取得实际文档命中。

**动机**　让广场业务技能引用另一团队维护的资料。广场已有共享取数 Skill 的接入方式，见 `web/server/index.ts:162-165`。Pi 显式加载获准的扩展和所选 Skill，见 `web/server/lib/piRunner.ts:545-559`。

### 实例验证 · 2026-11-04

对团队提供的 HTTPS REST 地址进行了只读探测。`GET /api/v1/system/info` 报告版本 `0.6.0`。请求自有库列表时，无凭据返回 HTTP 401，使用 `X-API-Key` 返回 HTTP 200、`success: true` 和空数组。共享库列表 `GET /api/v1/shared-knowledge-bases` 也返回 200 和空数组。这个结果仅描述本次凭据的列表视图。

`POST /api/v1/knowledge-search` 仅传查询词返回 HTTP 400，实例要求至少给出库或文档 ID。命中字段依据同版本文档，待用指定库复核。[v0.6.0 检索接口](https://github.com/Tencent/WeKnora/blob/v0.6.0/docs/api/knowledge-search.md)

### 建议接口与取舍

- 首期由业务 Skill 调共享检索工具，后端按当前调用者的授权范围选择库 ID，向固定上游发送 `query` 和 `knowledge_base_id`。只向模型交付相关片段，保留 `knowledge_title`、`knowledge_id`、分块 `id` 和 `content`，以便引用。分别处理无命中、无权限和上游失败。
- 上游凭据由广场后端持有。当前沙箱配置显式允许读取 `web/.env`，见 `scripts/setup-pi-sandbox.sh:103-106`。应使用沙箱无读取权限的后端专用凭据配置，将调用限制在获准会话和库。资料向哪些广场用户开放，由资料方确认。
- 0.6.0 的官方 MCP 适配器还要单独运行，工具目录同时包含检索和创建、删除。仅为广场增加检索时，REST 更容易限定调用面，也沿用现有 Skill 入口。若资料方将来为多个客户端统一发布限库、限工具的 MCP 端点，可再评估；上游 v0.8.2 已加入按空间发布端点的能力。该实例是否另行部署 MCP 适配器仍未验证。[v0.6.0 MCP 说明](https://github.com/Tencent/WeKnora/blob/v0.6.0/mcp-server/README.md) · [v0.8.2 发布记录](https://github.com/Tencent/WeKnora/releases/tag/v0.8.2)

**后续验收**　资料方提供已授权且已索引的库 ID、一条已知能命中的问题及预期来源文档。先用 REST 比对返回片段和原文，再在广场验证引用、无命中和越权拒绝。生产凭据通过双方约定的秘密渠道交接。
