import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, writeFile, readFile, rm, symlink } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { spawnSync, spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { validateRequest, hash, sqlString, likeTerm } from './core.mjs'
import { buildPlan, cohortWhere } from './compile.mjs'
import { salaryStatistics, buildResult } from './metrics.mjs'
import { StateStore } from './state.mjs'
import { query, planQuery, resolveEntity } from './service.mjs'
import { readResult, persistExport, preview, exportContent, withinWorkspace } from './artifacts.mjs'
import { MysqlAdapter } from './db.mjs'

const request=(metrics=['positions.count','education.distribution','salary.summary'],extra={})=>({schema:'talent-query/1',cohorts:[{id:'all',filters:{region:{level:'national'}}}],metrics,...extra})
const resolveCohorts=r=>r.cohorts.map(c=>({...c,resolved:{region:{level:'national',name:'中国'},industries:{ids:[],entities:[],version:null},roles:{ids:[],entities:[],version:null}},fingerprint:hash(c.filters)}))
const base=(n=4)=>({count:n,latestUpdate:'2026-10-31 12:00:00',missingCompany:n?1:0,missingAddress:0,missing_city:0,missing_province:0,missing_title:0,missing_source:0,companies:n?2:0})
const cube=()=>[{education:'BENKE',experience:'LESS_THAN_3',jobType:'SHEZHAO',count:3},{education:null,experience:'BUXIAN',jobType:'SHIXI',count:1}]
const salary=()=>[{status:'valid',mid:6.5,count:3},{status:'missing',mid:null,count:1}]
function execution(plan,overrides={}) {
  return {startedAt:new Date().toISOString(),dataReadAt:new Date().toISOString(),sourceReadTime:'2026-11-02 00:00:00',elapsedMs:3,returnedBytes:200,logs:plan.jobs.map(j=>({...j,completed:true,elapsedMs:1,rows:j.kind==='base'?[base()]:j.kind==='salary'?salary():j.kind==='cube'?cube():[{[j.dimension]:'sample',count:4}]})),...overrides}
}
async function temporary(t) {const dir=await mkdtemp(join(tmpdir(),'talent-query-test-'));t.after(()=>rm(dir,{recursive:true,force:true}));return dir}
class FakeAdapter {
  calls=[]
  async run(jobs,options) {
    this.calls.push({jobs,options})
    if(jobs[0].id==='capability')return {logs:[{id:'capability',completed:true,rows:['c_company_position','c_company_address','c_position_chain'].map(name=>({name,engine:'InnoDB'}))}]}
    await new Promise(r=>setTimeout(r,25))
    return execution({jobs})
  }
}
async function fixture(t) {
  const root=await temporary(t),workspace=join(root,'workspace');await mkdir(workspace)
  return {workspace,state:new StateStore(join(root,'state')),cfg:{MYSQL_HOST:'fixture',MYSQL_USER:'fixture',MYSQL_DATABASE:'fixture',MYSQL_PASSWORD:'not-a-secret'},adapter:new FakeAdapter()}
}

test('requests have no implicit geography, industry or software keywords',()=>{
  assert.throws(()=>validateRequest(request([], {cohorts:[{id:'x',filters:{}}]})),/region/)
  const r=validateRequest(request())
  assert.deepEqual(r.cohorts[0].filters.title,{any:[],all:[],exclude:[]})
  assert.deepEqual(r.cohorts[0].filters.industries,[])
  const sql=cohortWhere(resolveCohorts(r)[0])
  assert(!sql.includes('Java')&&!sql.includes('广东')&&!sql.includes('后端'))
  assert(sql.includes('LEFT JOIN'))
})
test('unknown fields, invalid dates, unbounded budgets and unsupported metrics are rejected',()=>{
  for(const r of [request(['salary.imagined']),{...request(),sql:'SELECT 1'},request(undefined,{execution:{deadlineMs:999999}}),request(undefined,{cohorts:[{id:'x',filters:{region:{level:'national'},updatedAt:{from:'2026-02-30'}}}]})])assert.throws(()=>validateRequest(r))
  assert.throws(()=>validateRequest(request(undefined,{cohorts:[{id:'x',filters:{region:{level:'national'},majors:[1822]}}]})),/majors/)
})
test('SQL string encoding cannot introduce quotes and LIKE meta characters are literal',()=>{
  const term="机器人' OR 1=1 -- %_!\\"
  assert.match(sqlString(term),/^CONVERT\(X'[0-9a-f]+' USING utf8mb4\)$/)
  const decoded=Buffer.from(/X'([0-9a-f]+)'/.exec(likeTerm(term))[1],'hex').toString()
  assert(decoded.includes('!%')&&decoded.includes('!_')&&decoded.includes('!!'))
  const r=validateRequest(request(undefined,{cohorts:[{id:'x',filters:{region:{level:'national'},title:{any:[term]}}}]}))
  const sql=cohortWhere(resolveCohorts(r)[0]);assert(!sql.includes('OR 1=1'));assert(sql.includes("ESCAPE '!"))
})
test('industry relations are EXISTS and role IDs match complete comma tokens',()=>{
  const r=validateRequest(request()),c=resolveCohorts(r)[0]
  c.resolved.industries.ids=['15','16'];c.resolved.roles.ids=['123']
  const sql=cohortWhere(c)
  assert(sql.includes('EXISTS (SELECT 1 FROM c_position_chain'))
  assert(sql.includes("LIKE '%,123,%'"))
  assert(!sql.includes('JOIN c_position_chain'))
})
test('education and experience reuse one cube and never request description',()=>{
  const r=validateRequest(request(['positions.count','education.distribution','experience.distribution','education_experience.cross']))
  const plan=buildPlan(r,resolveCohorts(r))
  assert.equal(plan.jobs.length,2)
  assert.equal(plan.jobs.filter(j=>j.kind==='cube').length,1)
  assert(!plan.jobs.some(j=>j.sql.includes('description')))
})
test('weighted salary quantiles use sample ranks and retain decimal values',()=>{
  const s=salaryStatistics([{status:'valid',mid:1.25,count:1},{status:'valid',mid:3.75,count:1},{status:'missing',mid:null,count:2}])
  assert.equal(s.summary.median,2.5)
  assert.equal(s.summary.p25,1.875)
  assert.equal(s.summary.p75,3.125)
  assert.equal(s.validN,2);assert.equal(s.excludedN,2)
  assert.equal(s.distribution.reduce((a,b)=>a+b.count,0),2)
})
test('distribution denominator stays complete when stdout preview is clipped',()=>{
  const r=validateRequest(request(['positions.count','education.distribution'])),plan=buildPlan(r,resolveCohorts(r))
  const e=execution(plan)
  e.logs.find(j=>j.kind==='base').rows=[{...base(100),missingCompany:0}]
  e.logs.find(j=>j.kind==='cube').rows=[{education:'BENKE',count:30},{education:'DAZHUAN',count:20},{education:'BUXIAN',count:50}]
  const result=buildResult(r,plan,e),m=result.metrics.find(m=>m.name==='education.distribution')
  assert.equal(m.denominator,100);assert.equal(m.rows.find(row=>row.education==='BENKE').share,.3)
  const clipped=preview(result,1).metrics.find(m=>m.name==='education.distribution')
  assert.equal(clipped.rows.length,1);assert.equal(clipped.denominator,100);assert(clipped.previewTruncated)
})
test('top N includes other and missing instead of renormalizing',()=>{
  const r=validateRequest(request(['title.top'])),plan=buildPlan(r,resolveCohorts(r)),e=execution(plan)
  e.logs.find(j=>j.kind==='base').rows=[{...base(100),missing_title:10}]
  e.logs.find(j=>j.dimension==='title').rows=[{title:'A',count:30},{title:'B',count:20}]
  const m=buildResult(r,plan,e).metrics[0]
  assert.equal(m.otherCount,40);assert.equal(m.missingN,10);assert.equal(m.rows[0].share,.3)
})
test('empty, no valid salary, failed query and inconsistent totals stay distinct',()=>{
  const r=validateRequest(request()),plan=buildPlan(r,resolveCohorts(r))
  const empty=execution(plan)
  for(const log of empty.logs)log.rows=log.kind==='base'?[base(0)]:[]
  assert.equal(buildResult(r,plan,empty).status,'empty')
  const noSalary=execution(plan);noSalary.logs.find(j=>j.kind==='salary').rows=[{status:'missing',mid:null,count:4}]
  const result=buildResult(r,plan,noSalary)
  assert.equal(result.status,'partial');assert.equal(result.metrics.find(m=>m.name==='salary.summary').value.median,null)
  const bad=execution(plan);bad.logs.find(j=>j.kind==='cube').rows=[{education:'BENKE',count:3}]
  const rejected=buildResult(r,plan,bad);assert.equal(rejected.status,'partial');assert(!rejected.quality.allPass)
  const failed=buildResult(r,plan,execution(plan,{logs:[],error:{code:'QUERY_TIMEOUT',message:'timeout'}}))
  assert.equal(failed.status,'failed');assert.equal(failed.cohorts[0].positions,null)
})
test('concurrent identical requests execute one statistical batch across service instances',async t=>{
  const f=await fixture(t)
  const [a,b]=await Promise.all([query(request(),f),query(request(),f)])
  assert.equal(f.adapter.calls.filter(c=>c.jobs[0].kind==='base').length,1)
  assert.equal(a.contentHash,b.contentHash);assert.notEqual(a.requestId,b.requestId)
  assert.equal((await readResult(a.artifacts.result,f.workspace)).contentHash,a.contentHash)
})
test('cache preserves read date, live bypasses it, snapshot cannot change predicates',async t=>{
  const f=await fixture(t)
  const a=await query(request(),f),b=await query(request(),f)
  assert.equal(b.freshness.mode,'cache');assert.equal(a.freshness.dataReadAt,b.freshness.dataReadAt)
  await query(request(undefined,{execution:{freshness:'live'}}),f)
  assert.equal(f.adapter.calls.filter(c=>c.jobs[0].kind==='base').length,2)
  const snapshot=await query(request(undefined,{execution:{freshness:'snapshot-only',snapshotId:a.snapshotId}}),f)
  assert.equal(snapshot.freshness.mode,'snapshot')
  assert.equal(snapshot.freshness.dataReadAt,a.freshness.dataReadAt)
  await assert.rejects(query(request(['positions.count'],{execution:{freshness:'snapshot-only',snapshotId:a.snapshotId}}),f),/快照/)
})
test('all requested metrics in a cached result come from one read batch',async t=>{
  const f=await fixture(t)
  await query(request(['education.distribution']),f)
  await query(request(['education.distribution','salary.summary']),f)
  assert.equal(f.adapter.calls.filter(c=>c.jobs[0].kind==='base').length,2)
})
test('failed/partial results are not usable cache entries',async t=>{
  const f=await fixture(t)
  const original=f.adapter.run.bind(f.adapter)
  f.adapter.run=async(jobs,options)=>jobs[0].id==='capability'?original(jobs,options):execution({jobs},{logs:[],error:{code:'QUERY_TIMEOUT',message:'timeout'}})
  const a=await query(request(),f),b=await query(request(),f)
  assert.equal(a.status,'failed');assert.equal(b.freshness.mode,'live')
})
test('tampered or missing result artifacts cannot be inspected or exported',async t=>{
  const f=await fixture(t),a=await query(request(),f)
  await writeFile(join(f.workspace,a.artifacts.summary),'tampered')
  await assert.rejects(readResult(a.artifacts.result,f.workspace),/指纹/)
})
test('exports use saved results, contain no SQL, and protect CSV formula cells',async t=>{
  const f=await fixture(t),a=await query(request(),f),calls=f.adapter.calls.length
  const exported=await persistExport(await readResult(a.artifacts.result,f.workspace),'csv',f.workspace)
  assert.equal(f.adapter.calls.length,calls)
  const csv=await readFile(join(f.workspace,exported.file),'utf8')
  assert(!csv.includes('SELECT ')&&!csv.includes('password'))
  const manipulated=structuredClone(a);manipulated.metrics=[{metricId:'=SUM(A1)',cohortId:'x',status:'complete',unit:'x',denominator:1,value:1}]
  assert(exportContent(manipulated,'csv').includes("'=SUM(A1)"))
})
test('unknown city returns clarification; it never executes an aggregate',async t=>{
  const f=await fixture(t)
  f.adapter.run=async jobs=>({logs:jobs.map(j=>({...j,completed:true,rows:[]}))})
  await assert.rejects(query(request(undefined,{cohorts:[{id:'x',filters:{region:{level:'city',name:'不存在市'}}}]}),f),e=>e.code==='NEEDS_CLARIFICATION')
})
test('dictionary name ambiguity is returned instead of choosing first row',async t=>{
  const f=await fixture(t)
  f.adapter.run=async jobs=>({logs:jobs.map(j=>({...j,completed:true,rows:[{id:'1',name:'测试',pid:'0',level:0},{id:'2',name:'测试',pid:'0',level:0}]}))})
  const r=request(undefined,{cohorts:[{id:'x',filters:{region:{level:'national'},industries:[{name:'测试'}]}}]})
  await assert.rejects(planQuery(r,f),e=>e.code==='NEEDS_CLARIFICATION'&&e.details.candidates.length===2)
})
test('global heavy lock serializes different request keys',async t=>{
  const f=await fixture(t),original=f.adapter.run.bind(f.adapter)
  let active=0,peak=0
  f.adapter.run=async(jobs,options)=>{
    if(jobs[0].id==='capability')return original(jobs,options)
    active++;peak=Math.max(peak,active)
    try{return await original(jobs,options)}finally{active--}
  }
  await Promise.all([query(request(['positions.count']),f),query(request(['education.distribution']),f)])
  assert.equal(peak,1)
})
test('queue deadline expires without running work; stale dead-owner locks recover',async t=>{
  const dir=await temporary(t),s=new StateStore(dir);await s.init()
  let ran=false
  await assert.rejects(s.lock('expired',Date.now()-1,async()=>{ran=true}),e=>e.code==='DEADLINE_EXCEEDED')
  assert(!ran)
  const directory=join(dir,'locks',hash('dead'))
  await mkdir(directory);await writeFile(join(directory,'owner.json'),JSON.stringify({pid:2147483647,host:(await import('node:os')).hostname()}))
  assert.equal(await s.lock('dead',Date.now()+2000,async()=>42),42)
})
test('cache checksum failure is a miss',async t=>{
  const dir=await temporary(t),s=new StateStore(dir);await s.init();const key=hash('cache')
  await s.write('cache',key,{n:1})
  const file=join(dir,'cache',`${key}.json`),data=JSON.parse(await readFile(file,'utf8'));data.payload.n=2;await writeFile(file,JSON.stringify(data))
  assert.equal(await s.read('cache',key),null)
})
test('mysql framing preserves Unicode, literal NULL and JSON null',async t=>{
  const dir=await temporary(t),bin=join(dir,'mysql.mjs')
  const script=`#!/usr/bin/env node
let text='';for await(const chunk of process.stdin)text+=chunk;
console.log(JSON.stringify({_talent:'snapshot',sourceReadTime:'original-clock'}));
const ids=[...text.matchAll(/'_talent','begin','id',CONVERT\\(X'([0-9a-f]+)'/g)].map(m=>Buffer.from(m[1],'hex').toString());
for(const id of ids){console.log(JSON.stringify({_talent:'begin',id}));console.log(JSON.stringify({row:{text:'中文\\nnext',literal:'NULL',empty:null,n:7}}));console.log(JSON.stringify({_talent:'end',id}));}
console.log(JSON.stringify({_talent:'finished'}));
`
  await writeFile(bin,script,{mode:0o700})
  const before=process.env.MYSQL_BIN;process.env.MYSQL_BIN=bin
  try {
    const db=new MysqlAdapter({MYSQL_HOST:'fixture',MYSQL_USER:'fixture',MYSQL_PASSWORD:'fixture',MYSQL_DATABASE:'fixture'})
    const result=await db.run([{id:'test',sql:"SELECT JSON_OBJECT('row',JSON_OBJECT('n',1))"}],{deadlineAt:Date.now()+5000,timeoutMs:1000})
    assert.equal(result.error,undefined);assert.deepEqual(result.logs[0].rows,[{text:'中文\nnext',literal:'NULL',empty:null,n:7}])
  }finally{if(before===undefined)delete process.env.MYSQL_BIN;else process.env.MYSQL_BIN=before}
})
test('capabilities CLI does not require database configuration or disclose SQL',()=>{
  const p=spawnSync(process.execPath,['scripts/talent-data-query.mjs','capabilities'],{encoding:'utf8',env:{...process.env,MYSQL_HOST:'',MYSQL_USER:'',MYSQL_PASSWORD:'',MYSQL_DATABASE:''}})
  assert.equal(p.status,0)
  const out=JSON.parse(p.stdout);assert.equal(out.schema,'talent-capabilities/1');assert(!p.stdout.includes('MYSQL_PASSWORD'))
})

test('unfinished transaction is partial even when all result frames arrived',()=>{
  const r=validateRequest(request(['positions.count'])),plan=buildPlan(r,resolveCohorts(r))
  const result=buildResult(r,plan,execution(plan,{error:{code:'DATABASE_ERROR',message:'connection lost'}}))
  assert.equal(result.status,'partial');assert(!result.quality.allPass);assert(!result.consistency.completeTransaction)
})
test('industry tree accepts the real negative root-parent sentinel',async t=>{
  const f=await fixture(t)
  f.adapter.run=async jobs=>({logs:jobs.map(j=>({...j,completed:true,rows:[{id:'1',name:'根',pid:'-1',level:-1},{id:'2',name:'子',pid:'1',level:0}]}))})
  const planned=await planQuery(request(['positions.count'],{cohorts:[{id:'x',filters:{region:{level:'national'},industries:[{id:'1'}]}}]}),f)
  assert.deepEqual(planned.cohorts[0].resolved.industries.ids,['1','2'])
})
test('true independent CLI processes share cache and serialize the source queue',async t=>{
  const dir=await temporary(t),state=join(dir,'state'),log=join(dir,'calls.jsonl')
  const fixtureBin=join(dir,'mysql-fixture.mjs')
  await writeFile(fixtureBin,await readFile(new URL('test-fixtures/mysql.mjs',import.meta.url)),{mode:0o700})
  const cli=fileURLToPath(new URL('../talent-data-query.mjs',import.meta.url))
  const run=async(name,metrics)=>{
    const workspace=join(dir,name);await mkdir(workspace);await writeFile(join(workspace,'request.json'),JSON.stringify(request(metrics)))
    return new Promise((resolve,reject)=>{
      const child=spawn(process.execPath,[cli,'query','--request','request.json'],{cwd:workspace,env:{...process.env,MYSQL_HOST:'fixture',MYSQL_PORT:'3306',MYSQL_USER:'fixture',MYSQL_PASSWORD:'fixture',MYSQL_DATABASE:'fixture',MYSQL_BIN:fixtureBin,TALENT_QUERY_STATE_DIR:state,TALENT_FIXTURE_LOG:log}})
      let out='',err='';child.stdout.on('data',c=>out+=c);child.stderr.on('data',c=>err+=c)
      child.on('error',reject);child.on('close',code=>{try{assert.equal(code,0,err+out);resolve(JSON.parse(out))}catch(e){reject(e)}})
    })
  }
  const [a,b]=await Promise.all([run('a',['positions.count']),run('b',['positions.count'])])
  assert.equal(a.contentHash,b.contentHash)
  assert.equal((await readFile(log,'utf8')).trim().split('\n').map(JSON.parse).filter(e=>e.kind==='start').length,1)
  await Promise.all([run('c',['companies.count']),run('d',['positions.count','education.distribution'])])
  const events=(await readFile(log,'utf8')).trim().split('\n').map(JSON.parse)
  let active=0,peak=0
  for(const event of events){active+=event.kind==='start'?1:-1;peak=Math.max(peak,active)}
  assert.equal(peak,1);assert.equal(active,0)
})

test('cache age is measured from original data read, not cache file creation',async t=>{
  const f=await fixture(t),a=await query(request(),f),entry=await f.state.read('cache',a.cacheKey)
  entry.payload.result.freshness.dataReadAt=new Date(Date.now()-901000).toISOString()
  await f.state.write('cache',a.cacheKey,entry.payload)
  await query(request(),f)
  assert.equal(f.adapter.calls.filter(c=>c.jobs[0].kind==='base').length,2)
})
test('known empty cohorts still have a valid zero count difference',()=>{
  const r=validateRequest(request(['positions.count'],{cohorts:[{id:'a',filters:{region:{level:'national'}}},{id:'b',filters:{region:{level:'national'}}}]})),plan=buildPlan(r,resolveCohorts(r)),e=execution(plan)
  e.logs.find(j=>j.id==='b:base').rows=[base(0)]
  const result=buildResult(r,plan,e)
  assert.equal(result.comparisons[0].value,-4)
})
test('request and artifact path checks reject a symlink outside the workspace',async t=>{
  const dir=await temporary(t),workspace=join(dir,'workspace');await mkdir(workspace)
  await writeFile(join(dir,'outside.json'),'{}');await symlink(join(dir,'outside.json'),join(workspace,'request.json'))
  await assert.rejects(withinWorkspace('request.json',workspace),e=>e.code==='INVALID_PATH')
})
test('mysql failure keeps prior completed queries and rejects the unfinished metric',async t=>{
  const dir=await temporary(t),bin=join(dir,'mysql.mjs')
  const source=(await readFile(new URL('test-fixtures/mysql.mjs',import.meta.url),'utf8')).replace(/^#!.*\n/,'')
  await writeFile(bin,'#!/usr/bin/env node\nprocess.env.TALENT_FIXTURE_FAIL="all:cube";\n'+source,{mode:0o700})
  const db=new MysqlAdapter({MYSQL_HOST:'fixture',MYSQL_USER:'fixture',MYSQL_PASSWORD:'fixture',MYSQL_DATABASE:'fixture'})
  const r=validateRequest(request(['positions.count','education.distribution'])),plan=buildPlan(r,resolveCohorts(r))
  const executed=await db.spawn(bin,plan.jobs,{deadlineAt:Date.now()+5000,timeoutMs:1000,consistent:true})
  assert.equal(executed.error.code,'QUERY_TIMEOUT')
  assert.equal(executed.logs[0].completed,true);assert.equal(executed.logs[1].completed,false)
  const result=buildResult(r,plan,{...executed,startedAt:new Date().toISOString()})
  assert.equal(result.status,'partial');assert(!result.quality.allPass)
  assert.equal(result.metrics.find(m=>m.name==='positions.count').value,4)
  assert.equal(result.metrics.find(m=>m.name==='education.distribution').status,'failed')
})
test('geographic aliases merge before TOP N instead of splitting one city code',()=>{
  const r=validateRequest(request(['city.distribution'],{output:{topN:1}})),plan=buildPlan(r,resolveCohorts(r)),e=execution(plan)
  e.logs.find(j=>j.dimension==='city').rows=[{province:'广东',city:'广州',count:2},{province:'广东省',city:'广州市',count:2}]
  const metric=buildResult(r,plan,e).metrics[0]
  assert.equal(metric.rows.length,1);assert.equal(metric.rows[0].count,4)
  assert.equal(metric.rows[0].province,'广东省');assert.equal(metric.rows[0].city,'广州市')
  assert.equal(metric.rows[0].code,'440100');assert.equal(metric.otherCount,0)
})
