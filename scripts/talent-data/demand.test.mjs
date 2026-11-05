import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, readFile, rm, copyFile, chmod } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { queryDemand, prepareDemand, validateDemand } from './demand.mjs'
import { StateStore } from './state.mjs'
import { readResult } from './artifacts.mjs'
import { MysqlAdapter } from './db.mjs'
import registerTools, { blockedQueryCall } from '../../.agents/skills/talent-data-query/scripts/pi-tools.mjs'

const demand={samples:[{region:{level:'province',name:'广东'},industries:['智能网联汽车']}],metrics:['positions.count','education.distribution']}
async function fixture(t) {
  const root=await mkdtemp(join(tmpdir(),'talent-demand-'));t.after(()=>rm(root,{recursive:true,force:true}))
  const workspace=join(root,'workspace');await mkdir(workspace)
  const calls=[]
  const adapter={async run(jobs){
    calls.push(jobs)
    const logs=jobs.map(job=>{
      let rows
      if(job.id==='dictionary-industry')rows=[{id:'14',name:'智能网联汽车',pid:'0',level:0},{id:'141',name:'智能网联汽车',pid:'14',level:1}]
      else if(job.id==='capability')rows=['c_company_position','c_company_address','c_position_chain'].map(name=>({name,engine:'InnoDB'}))
      else if(job.kind==='base')rows=[Object.fromEntries(job.fields.map(field=>[field,field==='count'?4:0]))]
      else if(job.kind==='cube')rows=[{education:'BENKE',count:4}]
      else throw new Error('unexpected job')
      return {...job,rows,completed:true,elapsedMs:0,serverElapsedMs:7.5,finishedAt:new Date().toISOString()}
    })
    return {logs,dataReadAt:new Date().toISOString(),sourceReadTime:'2026-11-05 00:00:00',elapsedMs:10,returnedBytes:100}
  }}
  return {workspace,state:new StateStore(join(root,'state')),cfg:{MYSQL_HOST:'fixture',MYSQL_USER:'fixture',MYSQL_DATABASE:'fixture',MYSQL_PASSWORD:'fixture'},adapter,calls,turn:{runId:'run-1',messages:['生成广东智能网联汽车人才需求报告']}}
}
test('industry demand selects the unique level-zero root and preserves its descendants',async t=>{
  const f=await fixture(t),request=await prepareDemand(demand,f)
  assert.deepEqual(request.cohorts[0].filters.industries,[{id:'14',includeDescendants:true}])
  assert.deepEqual(request.cohorts[0].filters.title,{any:[],all:[],exclude:[]})
  const result=await queryDemand(demand,f)
  assert.equal(result.status,'complete')
  const statistical=f.calls.find(jobs=>jobs.some(j=>j.kind==='base'))
  assert(statistical[0].sql.includes('industry_candidates'))
  assert(statistical[0].sql.includes('14,141'))
  assert(!statistical[0].sql.includes('p.name LIKE'))
  assert.equal((await readResult(result.artifacts.result,f.workspace)).metrics[0].denominator,4)
})
test('a report cannot replace a named industry with a cheaper-looking keyword',async t=>{
  const f=await fixture(t)
  for(const title of ['智能网联汽车','自动驾驶','车联网']) {
    const result=await queryDemand({...demand,samples:[{region:{level:'province',name:'广东'},title:{any:[title]}}]},f)
    assert.equal(result.errors[0].code,'SCOPE_MISMATCH')
  }
  assert.equal(f.calls.length,0)
  const fixed=await queryDemand(demand,f);assert.equal(fixed.status,'complete')
})
test('explicit name matching remains available and no SQL or budget can be supplied',()=>{
  const named={samples:[{region:{level:'city',name:'佛山'},title:{any:['Java']},updatedAt:{from:'2026-10-30',to:'2026-11-02'}}],metrics:['positions.count']}
  assert.equal(validateDemand(named,{messages:['统计佛山岗位名称包含 Java 的岗位']}).cohorts[0].filters.title.any[0],'Java')
  for(const extra of [{sql:'SELECT 1'},{timeoutMs:999999},{request:'request.json'}])assert.throws(()=>validateDemand({...named,...extra}),/不支持/)
})
test('unknown industry never falls back to title; ambiguity is returned before aggregation',async t=>{
  const f=await fixture(t),result=await queryDemand({...demand,samples:[{region:{level:'national'},industries:['未登记产业']}]},{...f,turn:{runId:'unknown',messages:[]}})
  assert.equal(result.errors[0].code,'NEEDS_CLARIFICATION')
  assert(!f.calls.some(jobs=>jobs.some(job=>job.kind==='base')))
})
test('a timed-out batch stops further attempts across calls and preserves its artifact',async t=>{
  const f=await fixture(t),original=f.adapter.run.bind(f.adapter)
  f.adapter.run=async jobs=>jobs.some(j=>j.kind==='base')?{logs:[],error:{code:'QUERY_TIMEOUT',message:'fixture timeout'},elapsedMs:12,returnedBytes:0}:original(jobs)
  const first=await queryDemand(demand,f)
  assert.equal(first.status,'failed');assert(first.handoff.stopped)
  assert.equal((await readResult(first.artifacts.result,f.workspace)).status,'failed')
  const second=await queryDemand({...demand,metrics:['positions.count']},f)
  assert.equal(second.errors[0].code,'QUERY_STOPPED')
  const events=(await readFile(join(f.workspace,'.talent-query/events.jsonl'),'utf8')).trim().split('\n').map(JSON.parse)
  assert.equal(events.filter(e=>e.stage==='database'&&e.state==='started').length,1)
  assert(events.some(e=>e.stage==='database_result'&&e.code==='QUERY_TIMEOUT'))
})
test('identical requests reuse verified artifacts, while metrics have a bounded additional batch',async t=>{
  const f=await fixture(t),a=await queryDemand(demand,f),b=await queryDemand(demand,f)
  assert.equal(a.requestId,b.requestId);assert(b.handoff.reused)
  await queryDemand({...demand,metrics:['positions.count']},f)
  const blocked=await queryDemand({...demand,metrics:['education.distribution']},f)
  assert.equal(blocked.errors[0].code,'QUERY_BUDGET_EXCEEDED')
  assert.equal(f.calls.filter(jobs=>jobs.some(j=>j.kind==='base')).length,2)
})
test('diagnostics identify the owner, run, request, stages and server timing without SQL',async t=>{
  const f=await fixture(t),result=await queryDemand(demand,f)
  const events=(await readFile(join(f.workspace,'.talent-query/events.jsonl'),'utf8')).trim().split('\n').map(JSON.parse)
  for(const stage of ['scope_resolution','resolution','request_queue','database_queue','database','aggregation','artifacts','handoff'])assert(events.some(e=>e.stage===stage))
  assert(events.every(e=>e.owner==='talent-data-query'&&e.runId==='run-1'&&e.traceId===result.handoff.traceId))
  assert.equal(events.find(e=>e.stage==='database_result').statements[0].serverElapsedMs,7.5)
  assert(!JSON.stringify(events).includes('SELECT '))
})
test('cancellation interrupts the real adapter child and queued locks',async t=>{
  const f=await fixture(t),controller=new AbortController()
  const old=process.env.MYSQL_BIN
  const bin=join(f.workspace,'mysql-fixture.mjs')
  await copyFile(new URL('./test-fixtures/mysql.mjs',import.meta.url),bin);await chmod(bin,0o755)
  process.env.MYSQL_BIN=bin
  try {
    const adapter=new MysqlAdapter(f.cfg,{signal:controller.signal})
    const pending=adapter.run([{id:'x:base',sql:'SELECT 1'}],{deadlineAt:Date.now()+10000})
    setTimeout(()=>controller.abort(),50)
    assert.equal((await pending).error.code,'QUERY_ABORTED')
    await f.state.init()
    let release;const held=f.state.lock('held',Date.now()+10000,()=>new Promise(r=>{release=r}))
    while(!release)await new Promise(r=>setTimeout(r,1))
    await assert.rejects(f.state.lock('held',Date.now()+10000,()=>{},controller.signal),e=>e.code==='QUERY_ABORTED')
    release();await held
  } finally {if(old===undefined)delete process.env.MYSQL_BIN;else process.env.MYSQL_BIN=old}
})
test('native tools own query calls and guards block CLI, hand-written queries and credentials',()=>{
  const registered=[],hooks={}
  registerTools({registerTool:tool=>registered.push(tool),on:(name,fn)=>{hooks[name]=fn}})
  assert.deepEqual(registered.map(t=>t.name),['talent_query','talent_query_capabilities','talent_inspect'])
  for(const command of ['timeout 180 node /repo/scripts/talent-data-query.mjs query --request request.json','node /repo/.agents/skills/talent-data-query/scripts/query.mjs query --request request.json','node /repo/scripts/mysql-query.mjs "SELECT 1"','python3 -c "import pymysql"'])assert(hooks.tool_call({toolName:'bash',input:{command}})?.block)
  assert(blockedQueryCall({toolName:'write',input:{path:'request.json',content:'{"schema":"talent-query/1"}'}}))
  assert(blockedQueryCall({toolName:'read',input:{path:'/repo/web/.env'}}))
  assert.equal(blockedQueryCall({toolName:'read',input:{path:'/repo/.agents/skills/talent-data-query/SKILL.md'}}),undefined)
  assert.equal(blockedQueryCall({toolName:'bash',input:{command:'python3 /repo/.agents/skills/chart-visualization/scripts/figure.py verify f.json --out charts'}}),undefined)
  assert.equal(blockedQueryCall({toolName:'write',input:{path:'report.json',content:'{"schema":"industry-report/1"}'}}),undefined)
})
