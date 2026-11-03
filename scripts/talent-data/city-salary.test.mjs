import test from 'node:test'
import assert from 'node:assert/strict'
import {result,foundation,extended} from './test-fixtures/analysis-fixture.mjs'
import {buildResult} from './metrics.mjs'
import {adaptResult} from '../../.agents/skills/wechat-report/scripts/adapt_query_result.mjs'

test('city salary joins the same frequency query and preserves global weighted median',()=>{
  const f=result({metrics:[...foundation,...extended,'city_salary.summary']})
  assert.equal(f.plan.queryCount,5)
  assert.equal(f.result.status,'complete')
  const metric=f.result.metrics.find(m=>m.name==='city_salary.summary')
  assert.equal(metric.rows.reduce((n,row)=>n+row.count,0),4)
  const guangzhou=metric.rows.find(row=>row.city==='广州市')
  assert.equal(guangzhou.count,2);assert.equal(guangzhou.validN,1)
  assert.equal(guangzhou.summary.median,15);assert.equal(guangzhou.excludedN,1)
  assert.equal(metric.rows.find(row=>row.city==='杭州市').summary.median,6)
  assert.equal(metric.missingN,1)
  assert.equal(f.result.metrics.find(m=>m.name==='salary.summary').value.median,10.5)
})

test('city salary does not require track rules and never drops missing geography',()=>{
  const f=result({metrics:['positions.count','city_salary.summary'] ,analysis:undefined})
  assert.equal(f.plan.queryCount,2)
  assert.match(f.plan.jobs.find(j=>j.kind==='salary').sql,/c_company_address/)
  const metric=f.result.metrics.find(m=>m.name==='city_salary.summary')
  assert.equal(metric.status,'complete');assert.equal(metric.missingN,1)
  assert.equal(metric.rows.find(row=>row.city===null).validN,0)
})

test('city mismatches are detected even if the grand total agrees',()=>{
  const f=result({metrics:[...foundation,...extended,'city_salary.summary']})
  const execution=structuredClone(f.execution)
  const row=execution.logs.find(log=>log.kind==='salary').rows.find(row=>row.city==='杭州市')
  row.city='广州市';row.province='广东省'
  const r=buildResult(f.request,f.plan,execution)
  assert.equal(r.metrics.find(m=>m.name==='city_salary.summary').status,'failed')
  assert.equal(r.metrics.find(m=>m.name==='salary.summary').status,'complete')
  assert(!r.quality.allPass)
})

test('empty and invalid salary remain distinguishable without invented city medians',()=>{
  const extra={metrics:[...foundation,'city_salary.summary'],analysis:undefined}
  const empty=result(extra,{empty:true}).result
  assert.equal(empty.metrics.find(m=>m.name==='city_salary.summary').status,'empty')
  const r=result(extra,{noSalary:true}).result
  assert(r.metrics.find(m=>m.name==='city_salary.summary').rows.every(row=>row.validN===0&&row.summary.median===null))
})

test('report city profiles bind salary and education to the same city population',()=>{
  const f=result({metrics:[...foundation,...extended,'city_salary.summary']})
  const {data,fieldMetrics}=adaptResult(f.result,{sections:['overview','geography']})
  const hangzhou=data.city_profiles.find(row=>row.city==='杭州市')
  assert.equal(hangzhou.count,1);assert.equal(hangzhou.median,6)
  assert.equal(hangzhou.bachelorCount,1);assert.equal(hangzhou.bachelorShare,100)
  assert.deepEqual(fieldMetrics['/city_profiles'],['all/city_salary.summary','all/city_education.cross'])
  const broken=structuredClone(f.result)
  broken.metrics.find(m=>m.name==='city_salary.summary').rows.find(row=>row.city==='杭州市').count=2
  assert.throws(()=>adaptResult(broken),/基数不一致/)
})
