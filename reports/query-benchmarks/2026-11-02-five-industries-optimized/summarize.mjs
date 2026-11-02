#!/usr/bin/env node
// Derive all comparison figures from measured artifacts, never from rounded table cells.
import {readFile,writeFile} from 'node:fs/promises'
const load=async path=>JSON.parse(await readFile(new URL(path,import.meta.url),'utf8'))
const baseline=await load('../2026-11-02-five-industries/results.json')
const current=await load('results.json'),batch=await load('batch-results.json'),parity=await load('parity-results.json')
const stats=rows=>{
  const total=rows.reduce((s,r)=>s+r.wallMs,0),sorted=[...rows].sort((a,b)=>a.wallMs-b.wallMs)
  return {requests:rows.length,totalMs:total,meanMs:total/rows.length,min:{id:sorted[0].id,ms:sorted[0].wallMs},max:{id:sorted.at(-1).id,ms:sorted.at(-1).wallMs}}
}
if(current.results.length!==20||current.results.some(r=>!r.success)||batch.results.length!==5||!parity.allPass||parity.results.length!==5)throw new Error('测量/同快照验证未完成')
const old=stats(baseline.results),optimized=stats(current.results),merged=stats(batch.results)
const batchCounts=Object.assign({},...batch.results.map(r=>r.counts))
const comparisons=current.results.map(r=>{
  const before=baseline.results.find(b=>b.id===r.id)
  return {id:r.id,industry:r.industry,label:r.label,baselinePositions:before.positions,optimizedPositions:r.positions,delta:r.positions-before.positions,
    baselineWallMs:before.wallMs,optimizedWallMs:r.wallMs,speedup:before.wallMs/r.wallMs,batchMatches:batchCounts[r.id]===r.positions}
})
const output={schema:'talent-query-benchmark-comparison/1',baseline:old,optimized,merged,
  independentSpeedup:old.totalMs/optimized.totalMs,independentTimeReduction:1-optimized.totalMs/old.totalMs,
  mergedSpeedupAgainstBaseline:old.totalMs/merged.totalMs,mergedSpeedupAgainstIndependent:optimized.totalMs/merged.totalMs,
  mergedAmortizedMsPerAnswer:merged.totalMs/20,baselineCountMatches:comparisons.filter(c=>c.delta===0).length,
  batchCountMatches:comparisons.filter(c=>c.batchMatches).length,sameSnapshotChecks:parity.results.flatMap(r=>r.checks).length,sameSnapshotAllPass:parity.allPass,comparisons}
if(output.batchCountMatches!==20||output.sameSnapshotChecks!==20)throw new Error('计数对账未通过')
await writeFile(new URL('comparison.json',import.meta.url),JSON.stringify(output,null,2)+'\n')
const sec=ms=>(ms/1000).toFixed(3),ratio=n=>n.toFixed(2)
const lines=['# 统计查询优化复测','',
  `引擎从 ${baseline.engine} 升级至 ${current.engine}。20 条筛选条件保持原样，全部成功；没有读取岗位描述或岗位明细，没有创建索引或修改源库结构。`,'',
  '| 完整请求耗时 | 原基准：20次请求 | 优化后：20次独立请求 |',
  '|---|---:|---:|',
  `| 平均 | ${sec(old.meanMs)} 秒 | ${sec(optimized.meanMs)} 秒 |`,
  `| 最长 | ${sec(old.max.ms)} 秒（${old.max.id}） | ${sec(optimized.max.ms)} 秒（${optimized.max.id}） |`,
  `| 最短 | ${sec(old.min.ms)} 秒（${old.min.id}） | ${sec(optimized.min.ms)} 秒（${optimized.min.id}） |`,
  `| 累计 | ${sec(old.totalMs)} 秒 | ${sec(optimized.totalMs)} 秒 |`,'',
  `本轮独立查询平均提速 ${ratio(output.independentSpeedup)} 倍，耗时减少 ${(output.independentTimeReduction*100).toFixed(2)}%。极值可能属于不同查询；逐条对照见下表。`,'',
  '## 合并统计','',
  `将同一产业四个样本组放在一次请求中，以条件聚合共享产业候选集合：实际执行 5 次请求、5 条统计 SQL，得到同样 20 项答案。累计 ${sec(merged.totalMs)} 秒，平均每次四组请求 ${sec(merged.meanMs)} 秒；相对原 20 次请求整轮约快 ${ratio(output.mergedSpeedupAgainstBaseline)} 倍，相对优化后独立查询约快 ${ratio(output.mergedSpeedupAgainstIndependent)} 倍。`,'',
  `按 20 项答案分摊约 ${sec(output.mergedAmortizedMsPerAnswer)} 秒/项，这是批处理摊销值，不是单条查询延迟。合并结果与本轮独立结果 20/20 一致。`,'',
  '| 产业 | 四组请求耗时/秒 | 物理统计 SQL 数 |', '|---|---:|---:|',
  ...batch.results.map(r=>`| ${r.industry} | ${sec(r.wallMs)} | ${r.sqlCount} |`),'',
  '## 数量核验与测量限制','',
  `原基准与本轮跨时点对比 ${output.baselineCountMatches}/20 数量一致。智慧交通三项变化：${comparisons.filter(c=>c.delta!==0).map(c=>`${c.id}：${c.baselinePositions} → ${c.optimizedPositions}（${c.delta>0?'+':''}${c.delta}）`).join('；')}。产业字典版本、子树和请求条件保持相同。`,'',
  '为排查改写引起的集合变化，对每个产业另开一个 REPEATABLE READ 只读事务，在同一快照中比较“直接关联产业关系后 COUNT(DISTINCT 岗位ID)”参照、优化后的四组聚合和四条独立计数：20/20 全部相等，五个事务均完整结束。参照与新路径采用不同的去重方式，保持原产业/在招/删除/地域/学历/经验条件。读取时间与校验值见 parity-results.json。跨时点数量变化不能改写为“与历史基准完全相同”。','',
  '额外验证最初采用旧 EXISTS 全表入口加四组条件聚合，在智慧交通一项触发 180 秒超时，未得到计数；失败记录见 parity-attempt-failed.json，该 SQL 没有冒充成功或记为零。随后换用上述直接关联去重参照。正确性验证的额外执行不计入两轮已完成的性能测量，旧完整耗时仍引用原始基准。','',
  '全部使用 freshness=live，串行、每种请求测一次，未清空 MySQL 缓冲池，未隔离业务库其他负载，原基准与新测量不是同一数据快照。这些是本轮观察值，不是受控冷缓存实验或延迟承诺。wallMs 从 CLI 启动前到关闭后；sqlBatchMs 包含连接与传输，逐语句 stdout 帧的 elapsedMs 不作为 SQL 服务端计时。','',
  '## 已落地的查询改造','',
  '- 按需聚合字段：只计数时只计算 COUNT，不额外计算全部字段缺失量和 MAX(update_time)。全国计数省去地址关联，地域条件仍保留原省市别名和地址规则。',
  '- 无时间窗的产业查询先筛产业关系，DISTINCT position_id 后主键关联岗位，避免一岗多产业重复；带时间窗保留原有入口。',
  '- 共同筛选条件相同的最多四组纯计数自动合并条件聚合，真实 SQL/证据 ID 与逻辑样本组数分别记录。',
  '- 完整质量检查增加为可选 data_quality.summary；未请求的缺失量/源最大更新时间标为 null 或未评估。数据读取时间继续保留。',
  '- 引擎版本隔离统计缓存，旧版本工件按原引擎版本验签。','',
  '## 数据库优化空间','',
  '实际 EXPLAIN 显示 Q01/Q03/Q17/Q19 已使用产业关系 chain_id 范围检索，岗位按 PRIMARY eq_ref 关联；Q17 的产业关系估计 584323 行、去重派生集合估计 292161 行。EXPLAIN 数字是优化器估计，不是实测扫描量。当前索引仍需回表读取 deleted，并保留多产业去重的临时集合。','',
  '1. 优先试验产业关系覆盖索引 `(industry_chain_id, deleted, position_id)`。现有 `(industry_chain_id, position_id)` 未覆盖 deleted；新索引有望减少回表，但不能消除跨产业 ID 的岗位去重，也没有经过建索引后的性能实测。',
  '2. 对无产业限制的地域统计，另评估岗位索引 `(company_address_id, publish_state, deleted)`，支持先筛城市地址再查岗位。当前主表没有以 company_address_id 为首列的索引；本次产业优先基准不能证明它会继续提速。',
  '3. 高频固定报表可维护带明确刷新时间的统计层或轻量事实表，正确处理上下架、删除、地域变化与多产业重复。任意多产业并集不能直接相加预汇总计数。',
  '4. 现有地址表已有 city/province 入口，先复用；岗位名 FULLTEXT 的中文召回不等价于“名称包含”，不能直接替换 LIKE。',
  '索引草案见 proposed-indexes.sql，仅供评审，本轮没有执行 DDL。information_schema 显示岗位表数据约 15.57 GiB、索引约 4.75 GiB，产业关系约 2444 万行是 InnoDB 估计；建索引前需评估全量构建的磁盘/IO、写入成本与维护窗口，在测试库比较计划和同口径结果后再决定，不能自动删除旧索引。','',
  '## 20 条逐项记录','',
  '| 编号 | 查询 | 原数量 | 新数量 | 原耗时/秒 | 新耗时/秒 | 提速倍数 |', '|---|---|---:|---:|---:|---:|---:|',
  ...comparisons.map(c=>`| ${c.id} | ${c.label} | ${c.baselinePositions} | ${c.optimizedPositions} | ${sec(c.baselineWallMs)} | ${sec(c.optimizedWallMs)} | ${ratio(c.speedup)} |`),'',
  '## 产物与复现','',
  '- [原始基准](../2026-11-02-five-industries/计时结果.md)、[本轮独立查询](计时结果.md)、[计时CSV](timings.csv)。',
  '- [对比JSON](comparison.json)、[合并测量](batch-results.json)、[同快照对账](parity-results.json)。',
  '- [真实索引/表元数据](database-metadata.json)、[执行计划](explain-optimized.json)、[待评审索引SQL](proposed-indexes.sql)。',
  '- queries.json 与 sql/ 保留原条件和实际 SQL；raw/ 中完整结果与 manifest 留本机，避免提交可变运行文件。','',
  '首次运行：`node reports/query-benchmarks/2026-11-02-five-industries-optimized/run.mjs`；随后 `node reports/query-benchmarks/2026-11-02-five-industries-optimized/verify-and-batch.mjs`；最后 `node reports/query-benchmarks/2026-11-02-five-industries-optimized/summarize.mjs`。已有测量时脚本拒绝静默覆盖；run.mjs 的 --resume/--rerun 语义见脚本。追加独立实验请使用新的结果目录。','']
await writeFile(new URL('优化复测.md',import.meta.url),lines.join('\n'))
console.log(JSON.stringify({independentSpeedup:output.independentSpeedup,meanSeconds:optimized.meanMs/1000,batchTotalSeconds:merged.totalMs/1000,sameSnapshotAllPass:parity.allPass}))
