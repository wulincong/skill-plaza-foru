/* JD 原文抽样脱敏（jd-excerpt-redaction/1）。
   MySQL 5.7 无 REGEXP_REPLACE，SQL 侧只做截断；联系方式在执行日志进入
   结果组装与证据落盘之前统一掩蔽，使 result.json 与 evidence.json 看到
   同一份已脱敏文本。掩蔽从宽：宁可误伤相邻文本，不让联系方式留在工件。 */
const MASK = '〔已脱敏〕'
const PATTERNS = [
  /https?:\/\/[\w\-./?%&=:#]+|www\.[\w\-./?%&=:#]+/gi,
  /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g,
  /(?:\+?86[-\s]?)?1[3-9]\d{9}/g,
  /\d{3,4}-\d{7,8}/g,
  /(?:微信|weixin|wx|vx|v信|qq(?:群?号?)?|q\s?q)[\s:：]*[A-Za-z0-9_-]{4,}/gi,
]
export const REDACTION_POLICY = 'jd-excerpt-redaction/1'
export function redactExcerpt(text) {
  let out = String(text)
  for (const pattern of PATTERNS) out = out.replaceAll(pattern, MASK)
  return out
}
export function redactSampledDescriptions(plan, logs) {
  const sampleIds = new Set((plan?.jobs ?? []).filter(job => job.kind === 'description-samples').map(job => job.id))
  for (const log of logs ?? []) if (sampleIds.has(log.id)) {
    for (const row of log.rows ?? []) if (typeof row.excerpt === 'string') row.excerpt = redactExcerpt(row.excerpt)
    log.redaction = REDACTION_POLICY
  }
  return logs
}
