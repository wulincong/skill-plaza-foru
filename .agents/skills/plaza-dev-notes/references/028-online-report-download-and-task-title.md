# 028 · 在线报告下载与结构化任务标题

- 状态：已实现（2026-09-29；真实浏览器下载与历史运行回归待验证）。
- 动机：在线运行已有独立 HTML 报告查看接口，但用户结果区没有下载入口；运行历史直接截取完整 prompt，导致标题包含 `$career-guidance`、字段标签和内部执行指令，难以阅读。
- 约定细节：
  - 前端结构化表单为运行请求增加可选 `taskTitle`；career-guidance 按“目标岗位或方向 + 本次任务 + 分析”生成，例如“IT 技术支持 / 网络运维实习生岗位匹配分析”。
  - 服务端限制 `taskTitle` 长度为 120 字符并清理控制字符；`RunRecord.taskTitle` 保存用户可读标题，`promptDigest` 优先使用该标题，旧客户端或对话模式仍回退到原始消息摘要。接入点：`web/src/pages/UsePage.vue:161-174`、`web/src/composables/useChatApi.ts:55-83`、`web/server/index.ts:407-411,476,616-625`、`web/server/lib/traceExport.ts:143-147`。
  - `/api/reports/:runId` 默认继续内联查看；增加 `?download=1` 后返回 `Content-Disposition: attachment`，文件名取任务标题并清理路径/特殊字符。用户报告组件在查看链接旁显示“下载报告”。接入点：`web/server/index.ts:294-317`、`web/src/components/ReportOutput.vue:25-32`。
- 成本与取舍：首期下载 HTML 而非服务端生成 PDF，完整保留内联样式和 SVG 图表，避免引入 PDF 转换器、字体和部署依赖；浏览器打印/PDF 可作为后续增强。标题由表单确定性生成，不让模型生成，避免历史列表再次出现提示词或不稳定标题。
- 后续扩展路线：真实 career-guidance 运行确认历史标题、在线查看、下载文件名和中文文件名兼容性；再评估浏览器打印入口和 PDF/Markdown 导出。
- 验证：`cd web && npm run build` 已通过；独立 server tsconfig 不存在，服务端专用 TypeScript 检查待补充；真实接口下载与浏览器验收待验证。

2026-10-23 补注：上述任务标题命名继续用于 HTML 报告；译文 PDF 的文件名优先取原文附件名并追加“-译文”，不使用 `promptDigest`，避免下载名成为“请翻译一下这个文档.pdf”。预览和下载响应都带文件名，旧运行无需迁移；接入点与实测见 [079](079-doc-translate-skill.md)。
