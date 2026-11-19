# 内部评估格式

先写全部候选的简短评估，再preview获取前20名，只为返回的这些岗位写详细分析，不自行重排。snapshot/sha256来自job_candidates；id是字符串，不能丢失长整数精度。

```json
{
  "snapshot":".job-matching/工具返回ID.json",
  "sha256":"工具返回指纹",
  "summary":"优先岗位方向、真实优势、主要限制和投递顺序。",
  "assessments":[{"id":"岗位ID","eligibility":"review","skills":3,"experience":2,"direction":4,"preferences":4,"reason":"基于实际JD和经历的一句判断；硬门槛不足必须指出"}],
  "details":[{"id":"程序选中岗位ID","evidence":[{"jd":"逐字来自该岗位positionDescription的要求","resume":"逐字来自工具返回resume的相关经历，没有则空字符串","status":"部分证明"}],"gaps":"具体差距和字段冲突；未知不当不符合","advice":"本次投递前最值得采取的行动及适用条件"}]
}
```

无简历时skills/experience为null，evidence.resume为空，状态“信息不足”。全部候选明确排除时details=[]，报告说明范围和放宽条件选择。不要以摘要输入代替用户附件原文；引文必须能在对应JD和真实简历中找到。程序只核对出处，语义是否支撑等级还要逐项复核。
