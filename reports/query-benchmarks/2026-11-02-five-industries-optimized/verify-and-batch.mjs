#!/usr/bin/env node
// Real, read-only verification. Batch timing and same-snapshot equivalence are separate runs.
import { readFile, writeFile, mkdir, access } from 'node:fs/promises'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn } from 'node:child_process'
import { performance } from 'node:perf_hooks'
import { randomUUID } from 'node:crypto'
import { validateRequest } from '../../../scripts/talent-data/core.mjs'
import { buildPlan, cohortWhere } from '../../../scripts/talent-data/compile.mjs'
import { context, planQuery } from '../../../scripts/talent-data/service.mjs'
import { readResult } from '../../../scripts/talent-data/artifacts.mjs'

const directory=fileURLToPath(new URL('.',import.meta.url))
const cli=fileURLToPath(new URL('../../../scripts/talent-data-query.mjs',import.meta.url))
const suite=JSON.parse(await readFile(join(directory,'queries.json'),'utf8'))
const parityOnly=process.argv[2]==='--parity-only'
if(process.argv.slice(2).some(a=>a!=='--parity-only'))throw new Error('仅支持 --parity-only')
const groups=[]
for(let i=0;i<suite.cases.length;i+=4) {
  const cases=suite.cases.slice(i,i+4)
  const request=structuredClone(cases[0].request)
  request.cohorts=cases.map(c=>({...c.request.cohorts[0],id:c.id}))
  groups.push({id:`B${groups.length+1}`,industry:cases[0].industry,cases,request})
}
const runId=`${new Date().toISOString().replaceAll(':','-')}-${randomUUID().slice(0,8)}`
const raw=join(directory,'raw',runId)
await mkdir(raw,{recursive:true})
for(const file of [...(parityOnly?[]:['batch-results.json']),'parity-results.json']) {
  try {await access(join(directory,file))} catch {continue}
  throw new Error(`已有 ${file}，不覆盖已记录的真实测量`)
}
const batch=parityOnly?JSON.parse(await readFile(join(directory,'batch-results.json'),'utf8')):{schema:'talent-query-batch-benchmark/1',runId,protocol:suite.protocol,results:[]}
for(const group of parityOnly?[]:groups) {
  const workspace=join(raw,group.id)
  await mkdir(workspace)
  await writeFile(join(workspace,'request.json'),JSON.stringify(group.request,null,2)+'\n')
  const startedAt=new Date().toISOString(),start=performance.now()
  console.log(JSON.stringify({event:'batch-start',id:group.id,industry:group.industry}))
  const processResult=await new Promise((resolve,reject)=>{
    const child=spawn(process.execPath,[cli,'query','--request','request.json'],{cwd:workspace,env:process.env})
    let stdout='',stderr=''
    child.stdout.on('data',c=>stdout+=c);child.stderr.on('data',c=>stderr+=c)
    child.on('error',reject)
    child.on('close',code=>resolve({code,stdout,stderr,wallMs:Math.round(performance.now()-start)}))
  })
  await writeFile(join(workspace,'stdout.json'),processResult.stdout)
  await writeFile(join(workspace,'stderr.txt'),processResult.stderr)
  if(processResult.code!==0)throw new Error(`合并请求失败：${group.id}`)
  const output=JSON.parse(processResult.stdout),result=await readResult(output.artifacts.result,workspace)
  if(result.status!=='complete'||!result.quality.allPass||result.execution.reused||result.freshness.mode!=='live')throw new Error('合并请求不是完整实时结果')
  const evidence=JSON.parse(await readFile(join(workspace,output.artifacts.evidence),'utf8'))
  const record={id:group.id,industry:group.industry,startedAt,finishedAt:new Date().toISOString(),wallMs:processResult.wallMs,
    sqlBatchMs:result.execution.sqlBatchMs,sqlCount:result.execution.queryCount,logicalCohortCount:result.execution.logicalCohortCount,
    sourceReadTime:result.freshness.sourceReadTime,counts:Object.fromEntries(result.metrics.map(m=>[m.cohortId,m.value])),
    rawResult:relative(directory,join(workspace,output.artifacts.result)),contentHash:result.contentHash,sqlFile:`sql/${group.id}.sql`}
  if(record.sqlCount!==1||record.logicalCohortCount!==4)throw new Error('未执行预期的一条物理 SQL / 四组统计')
  await writeFile(join(directory,record.sqlFile),evidence.queries.map(q=>q.sql+';').join('\n')+'\n')
  batch.results.push(record)
  await writeFile(join(directory,'batch-results.json'),JSON.stringify(batch,null,2)+'\n')
  console.log(JSON.stringify({event:'batch-finished',...record}))
}
batch.summary={requests:batch.results.length,answers:20,totalWallMs:batch.results.reduce((s,r)=>s+r.wallMs,0),totalSqlBatchMs:batch.results.reduce((s,r)=>s+r.sqlBatchMs,0)}
await writeFile(join(directory,'batch-results.json'),JSON.stringify(batch,null,2)+'\n')

// The source is live. Compare three equivalent plans inside ONE snapshot per industry:
// Direct relation JOIN + COUNT(DISTINCT p.id), new fused count, and four new individual counts.
// A legacy EXISTS conditional-aggregate verification timed out; see parity-attempt-failed.json.
const ctx=await context(),parity={schema:'talent-query-parity/1',runId,consistency:'one repeatable-read read-only transaction per industry',results:[]}
for(const group of groups) {
  const r=validateRequest(group.request),resolved=await planQuery(r,ctx),plan=buildPlan(r,resolved.cohorts)
  const fused=plan.jobs[0],first=plan.cohorts[0]
  const common={...first,filters:{...first.filters,region:{level:'national'},education:[],experience:[],jobType:[]},resolved:{...first.resolved,region:{level:'national'}}}
  const referenceSelect=fused.sql.slice(0,fused.sql.indexOf(' FROM (SELECT DISTINCT')).replace(/COALESCE\(SUM\(CASE WHEN (.*?) THEN 1 ELSE 0 END\),0\)/g,'COUNT(DISTINCT CASE WHEN $1 THEN p.id ELSE NULL END)')
  if(!referenceSelect.includes('COUNT(DISTINCT CASE'))throw new Error('独立校验聚合未生成')
  const noIndustry={...common,resolved:{...common.resolved,industries:{...common.resolved.industries,ids:[]}}}
  const referenceFrom=cohortWhere(noIndustry,{needsAddress:true,industryFirst:false}).replace('FROM c_company_position p','FROM c_position_chain pc JOIN c_company_position p ON p.id=pc.position_id')
  const reference={id:'reference-distinct',sql:`${referenceSelect} ${referenceFrom} AND pc.deleted=0 AND pc.industry_chain_id IN (${first.resolved.industries.ids.join(',')})`}
  const individual=plan.cohorts.flatMap(c=>buildPlan({...r,cohorts:[r.cohorts.find(x=>x.id===c.id)]},[c]).jobs)
  const jobs=[reference,fused,...individual],deadlineAt=Date.now()+240000
  console.log(JSON.stringify({event:'parity-start',industry:group.industry,statementCount:jobs.length}))
  const start=performance.now()
  const execution=await ctx.state.lock(`heavy:${ctx.sourceKey}`,deadlineAt,({onSpawn})=>ctx.adapter.run(jobs,{deadlineAt,timeoutMs:180000,consistent:true,onSpawn}))
  if(execution.error||execution.logs.length!==6||execution.logs.some(l=>!l.completed)) {
    await writeFile(join(raw,'parity-failure.json'),JSON.stringify({industry:group.industry,execution},null,2)+'\n')
    throw new Error(`同快照验证失败：${group.industry} ${JSON.stringify(execution.error)}`)
  }
  const logs=execution.logs,referenceCounts=logs[0].rows[0].counts,newCounts=logs[1].rows[0].counts
  const singleCounts=Object.fromEntries(logs.slice(2).map(log=>[log.id.split(':')[0],log.rows[0].count]))
  const checks=group.cases.map(c=>({id:c.id,referenceDistinct:referenceCounts[c.id],fused:newCounts[c.id],individual:singleCounts[c.id],pass:referenceCounts[c.id]===newCounts[c.id]&&newCounts[c.id]===singleCounts[c.id]}))
  const record={industry:group.industry,sourceReadTime:execution.sourceReadTime,completeTransaction:!execution.error,wallMs:Math.round(performance.now()-start),checks,sqlFile:`sql/${group.id}-parity.sql`}
  await writeFile(join(directory,record.sqlFile),jobs.map(j=>`-- ${j.id}\n${j.sql};`).join('\n\n')+'\n')
  parity.results.push(record)
  await writeFile(join(directory,'parity-results.json'),JSON.stringify(parity,null,2)+'\n')
  console.log(JSON.stringify({event:'parity-finished',...record}))
  if(checks.some(c=>!c.pass))throw new Error('新旧查询在同快照下不相等')
}
parity.allPass=parity.results.flatMap(r=>r.checks).every(c=>c.pass)
await writeFile(join(directory,'parity-results.json'),JSON.stringify(parity,null,2)+'\n')
