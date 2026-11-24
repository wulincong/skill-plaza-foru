# 评测输入JSON

在会话根目录写JSON；不要在技能目录写产物。以下为具体岗位示例，id必须来自本轮工具，quote逐字摘真实原文；示例文本不可套作实际证据。

```json
{
  "snapshot": ".job-matching/工具返回的文件.json",
  "sha256": "工具返回的sha256",
  "targetRole": "前端开发",
  "mode": "position",
  "selectedJobs": [{"id":"工具返回的字符串岗位ID","reason":"用户选定的前端开发实习岗位"}],
  "summary": "结合实际材料给结论、主要优势与最需要验证的能力，不能写查询过程。",
  "qualifications": [{
    "name":"学历", "status":"待确认",
    "sources":[{"positionId":"同上ID","quote":"本科及以上"}],
    "studentQuote":"", "reason":"未提交学历材料，需要确认"
  }],
  "competencies": [{
    "id":"component-dev", "name":"组件开发", "dimension":"前端开发",
    "weight":100, "requiredLevel":3, "observedLevel":null,
    "sources":[{"positionId":"同上ID","quote":"独立完成页面开发","basis":"inferred","reason":"页面独立交付需要组织和复用页面组件"}],
    "evidence":[],
    "explanation":"缺少独立开发过程与成果描述，暂不能判断。",
    "improvement":{"task":"完成含加载、空态与失败态的列表组件","deliverable":"代码仓库、演示及测试记录","check":"可复现三种状态且解释组件接口设计","priority":"优先验证"}
  }]
}
```

direction模式选1–10份JD，通常5–10份；少于5份自动列出覆盖限制。position只选1份。表单指定ID必须一致。targetRole与查询目标保持一致。JD引用只能来自selectedJobs。长ID用字符串。qualifications为数组，JD没有明确门槛时可为空，不虚构门槛。每个能力有来源与行动，权重正整数且总计100。observedLevel必须显式给null或整数，不可遗漏；非空需至少一条学生引文，evidence的kind表明材料类型。每条引文不超过300字，建议10–60字。

学生证据只能来自工具返回resume或studentMaterials。别将工作目标、招聘JD或AI解释当学生证据。0级也必须有学生明确未掌握的原话；未提及设null。完整综合分只有全部指标均有等级时才计算。资格条件单列，不能混进能力权重，也不能因为能力分高而忽略不符合的门槛。
