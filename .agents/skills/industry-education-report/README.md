# 产教决策报告

围绕真实决定取证，生成完整报告并通过 report-rendering 交付网页。人才查询交由 talent-data-query；关键范围、证据缺口和方案取舍需要用户判断时先询问。业务构建完成后继续呈现与平台交付，不以聊天摘要结束。[使用指南](docs/index.md) · [报告契约](references/data-contract.md)

在会话工作区运行 `python3 <技能目录>/scripts/report.py build report.json --review review.md`，新报告使用 edition=full。validate、preview、verify 保留历史稿回查能力。
