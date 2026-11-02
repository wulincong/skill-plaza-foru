import test from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { validateRequest, hash } from './core.mjs'
import { buildPlan } from './compile.mjs'
import { buildResult, resultContentHash } from './metrics.mjs'

const filters=(region={level:'national'},extra={})=>({region,industries:[{id:'15'}],...extra})
const request=(cohorts,metrics=['positions.count'])=>validateRequest({schema:'talent-query/1',cohorts,metrics})
function resolved(r) {
  return r.cohorts.map(c=>({...c,fingerprint:hash(c.filters),resolved:{
    region:c.filters.region.level==='national'?{level:'national',name:'中国'}:c.filters.region.level==='province'?{level:'province',name:'广东省',aliases:['广东省','广东']}:{level:'city',name:c.filters.region.name,province:'广东省',provinceAliases:['广东省','广东'],aliases:[c.filters.region.name,c.filters.region.name.slice(0,-1)]},
    industries:{ids:c.filters.industries.length?['15','16']:[],entities:[],version:'fixture'},roles:{ids:[],entities:[],version:null}
  }}))
}
const cohorts=[
  {id:'national',filters:filters()},
  {id:'gd',filters:filters({level:'province',name:'广东省'})},
  {id:'gz',filters:filters({level:'city',province:'广东省',name:'广州市'},{education:['DAZHUAN','GAOZHI']})},
  {id:'sz',filters:filters({level:'city',province:'广东省',name:'深圳市'},{experience:['ON_CAMPUS','GRADUATING']})}
]
// Execute the compiler's actual count SQL against an independent, in-memory relational fixture.
// Only the UTF-8 literal syntax is translated; no production database is written.
function executeCount(sql,empty=false) {
  const translated=sql.replace(/CONVERT\(X'([0-9a-f]*)' USING utf8mb4\)/g,(_,hex)=>"'"+Buffer.from(hex,'hex').toString('utf8').replaceAll("'","''")+"'")
  const python=`import sys,json,sqlite3
data=json.load(sys.stdin)
c=sqlite3.connect(':memory:')
c.executescript('CREATE TABLE c_company_position(id INTEGER PRIMARY KEY,publish_state TEXT,deleted INT,company_address_id INT,education TEXT,experience TEXT,type TEXT,name TEXT,update_time TEXT); CREATE TABLE c_company_address(id INTEGER PRIMARY KEY,province TEXT,city TEXT); CREATE TABLE c_position_chain(position_id INT,industry_chain_id INT,deleted INT);')
c.executemany('INSERT INTO c_company_address VALUES(?,?,?)',[(10,'广东省','广州市'),(20,'广东','深圳'),(30,None,'广州市')])
if not data['empty']:
 rows=[(1,'PUBLISHING',0,10,'DAZHUAN','GRADUATING','SHEZHAO','算法工程师','2026-10-31'),(2,'PUBLISHING',0,20,'BENKE','ON_CAMPUS','SHIXI','算法工程师','2026-10-31'),(3,'PUBLISHING',0,None,'GAOZHI','BUXIAN','SHEZHAO','算法工程师','2026-10-31'),(4,'PUBLISHING',0,30,'DAZHUAN','GRADUATING','SHEZHAO','算法工程师','2026-10-31'),(5,'PUBLISHING',0,10,'DAZHUAN','GRADUATING','SHEZHAO','算法工程师','2026-10-31'),(6,'CLOSED',0,10,'DAZHUAN','GRADUATING','SHEZHAO','算法工程师','2026-10-31'),(7,'PUBLISHING',1,10,'DAZHUAN','GRADUATING','SHEZHAO','算法工程师','2026-10-31'),(8,'PUBLISHING',0,20,'DAZHUAN','GRADUATING','SHEZHAO','算法工程师','2026-10-31')]
 c.executemany('INSERT INTO c_company_position VALUES(?,?,?,?,?,?,?,?,?)',rows)
 c.executemany('INSERT INTO c_position_chain VALUES(?,?,?)',[(1,15,0),(1,16,0),(2,15,0),(3,16,0),(4,15,0),(5,999,0),(6,15,0),(7,15,0),(8,15,1)])
print(json.dumps([json.loads(row[0])['row'] for row in c.execute(data['sql'])],ensure_ascii=False))`
  const p=spawnSync('python3',['-c',python],{input:JSON.stringify({sql:translated,empty}),encoding:'utf8'})
  assert.equal(p.status,0,p.stderr)
  return JSON.parse(p.stdout)
}
function execution(plan,rows) {
  return {logs:plan.jobs.map((job,i)=>({id:job.id,sql:job.sql,rows:rows[i],completed:true})),startedAt:'2026-11-02T00:00:00Z',dataReadAt:'2026-11-02T00:00:01Z',sourceReadTime:'2026-11-02 00:00:00',elapsedMs:10,returnedBytes:100}
}

test('count-only projects COUNT and omits address and diagnostic aggregates nationally',()=>{
  const r=request([cohorts[0]]),p=buildPlan(r,resolved(r)),sql=p.jobs[0].sql
  assert(sql.includes('SELECT DISTINCT pc.position_id'))
  assert(!sql.includes('c_company_address'))
  for(const field of ['MAX(', 'TRIM(', 'missing_', 'company_archive_id'])assert(!sql.includes(field))
  assert.deepEqual(executeCount(sql),[{count:4}])
})
test('four count cohorts compile to one actual aggregate and preserve independent filters',()=>{
  const r=request(cohorts),p=buildPlan(r,resolved(r))
  assert.equal(p.jobs.length,1);assert.equal(p.jobs[0].kind,'cohort-counts')
  const rows=executeCount(p.jobs[0].sql)
  assert.deepEqual(rows,[{counts:{national:4,gd:2,gz:1,sz:1}}])
  const result=buildResult(r,p,execution(p,[rows]))
  assert.deepEqual(result.metrics.map(m=>m.value),[4,2,1,1])
  assert(result.metrics.every(m=>m.evidenceIds[0]===p.jobs[0].id))
  assert.equal(result.execution.queryCount,1);assert.equal(result.execution.logicalCohortCount,4)
  assert(result.quality.allPass)
})
test('separate count requests equal fused results with duplicate links and missing geography',()=>{
  const actual=cohorts.map(c=>{
    const r=request([c]),p=buildPlan(r,resolved(r))
    return executeCount(p.jobs[0].sql)[0].count
  })
  assert.deepEqual(actual,[4,2,1,1])
})
test('empty merged candidate sets return four explicit zero counts, not null',()=>{
  const r=request(cohorts),p=buildPlan(r,resolved(r)),rows=executeCount(p.jobs[0].sql,true)
  assert.deepEqual(rows,[{counts:{national:0,gd:0,gz:0,sz:0}}])
  const result=buildResult(r,p,execution(p,[rows]))
  assert.equal(result.status,'empty');assert(result.quality.allPass)
})
test('city-only merged counts retain the union filter instead of widening to national rows',()=>{
  const r=request(cohorts.slice(2)),p=buildPlan(r,resolved(r)),sql=p.jobs[0].sql
  assert(sql.includes(' AND ((a.province'))
  assert.deepEqual(executeCount(sql),[{counts:{gz:1,sz:1}}])
})
test('only requested diagnostic fields are computed and unavailable metadata remains null',()=>{
  const r=request([cohorts[0]]),p=buildPlan(r,resolved(r))
  const result=buildResult(r,p,execution(p,[[{count:4}]]))
  assert.equal(result.cohorts[0].missingAddressN,null)
  assert.equal(result.freshness.sourceLatestUpdateAt,null)
  assert.equal(result.quality.dataQualityEvaluated,false)
  const diagnostic=request([cohorts[0]],['positions.count','data_quality.summary'])
  const dp=buildPlan(diagnostic,resolved(diagnostic))
  assert(dp.jobs[0].sql.includes('c_company_address'));assert(dp.jobs[0].sql.includes('MAX(p.update_time)'))
  const values={count:4,latestUpdate:'2026-10-31',missingCompany:0,missingAddress:1,missing_city:1,missing_province:2,missing_title:0,missing_source:0}
  const assessed=buildResult(diagnostic,dp,execution(dp,[[values]]))
  assert(assessed.quality.dataQualityEvaluated)
  assert.equal(assessed.metrics.find(m=>m.name==='data_quality.summary').value.missing_city,1)
})
test('different industries or shared keyword/time criteria are not accidentally fused',()=>{
  const r=request([cohorts[0],{id:'other',filters:filters(undefined,{title:{any:['机器人']}})}]),c=resolved(r)
  assert.equal(buildPlan(r,c).jobs.length,2)
  c[1].filters.title=c[0].filters.title;c[1].resolved.industries.ids=['999']
  assert.equal(buildPlan(r,c).jobs.length,2)
  const dated=request([{id:'dated',filters:filters(undefined,{updatedAt:{from:'2026-10-01'}})}])
  const sql=buildPlan(dated,resolved(dated)).jobs[0].sql
  assert(!sql.includes('industry_candidates'));assert(sql.includes('EXISTS'));assert(sql.includes('p.update_time >='))
})
test('partial fused responses cannot silently produce complete results',()=>{
  const r=request(cohorts),p=buildPlan(r,resolved(r))
  assert.throws(()=>buildResult(r,p,execution(p,[[{counts:{national:4}}]])),/合并计数/)
  const failed=buildResult(r,p,{...execution(p,[]),logs:[],error:{code:'QUERY_TIMEOUT',message:'timeout'}})
  assert.equal(failed.status,'failed');assert(failed.metrics.every(m=>m.status==='failed'))
})
test('version 1.0 content hashes use the stored engine version after upgrade',()=>{
  const r=request([cohorts[0]]),engine='talent-query-engine/1.0.0'
  const result={schema:'talent-result/1',engine,status:'complete',request:r,cohorts:[],metrics:[],comparisons:[],quality:{allPass:true}}
  const originalSemantic={schema:r.schema,sourceId:r.sourceId,cohorts:r.cohorts,metrics:r.metrics,policies:r.policies,topN:r.output.topN,engine}
  const originalHash=hash({...result,request:originalSemantic})
  assert.equal(resultContentHash(result),originalHash)
})
