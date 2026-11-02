import test from 'node:test'
import assert from 'node:assert/strict'
import {request,result,analysis} from './test-fixtures/analysis-fixture.mjs'
import {buildResult,resultContentHash} from './metrics.mjs'
import {hash,semanticRequest} from './core.mjs'

test('actual aggregate SQL preserves first match, missing geography and weighted group salaries',()=>{
  const {result:r,plan}=result()
  assert.equal(r.status,'complete');assert(r.quality.allPass)
  assert.equal(plan.queryCount,5)
  const metric=n=>r.metrics.find(m=>m.name===n)
  assert.equal(metric('positions.count').value,4)
  assert.equal(metric('companies.count').value,2)
  assert.deepEqual(Object.fromEntries(metric('track.distribution').rows.map(r=>[r.track,r.count])),{algo:2,control:1,__other__:1})
  assert.equal(metric('city_track.cross').rows.reduce((n,r)=>n+r.count,0),4)
  assert.equal(metric('city_track.cross').missingN,1)
  assert.equal(metric('salary.summary').value.median,10.5)
  assert.equal(metric('track_salary.summary').rows.find(r=>r.track==='algo').summary.median,10.5)
  assert.equal(metric('track_salary.summary').rows.find(r=>r.track==='control').validN,0)
})
test('skill aggregation counts posts once, ignores letter case, preserves overlap and missing descriptions',()=>{
  const {result:r}=result()
  const m=r.metrics.find(m=>m.name==='skills.distribution')
  assert.equal(m.describedN,2);assert.equal(m.missingN,2)
  const rows=Object.fromEntries(m.rows.map(r=>[r.skill,r]))
  assert.equal(rows.Python.count,2);assert.equal(rows.Python.share,.5);assert.equal(rows.Python.describedShare,1)
  assert.equal(rows.ROS.count,1);assert.equal(rows.ROS2.count,1);assert.equal(rows['C++'].count,1)
  const cells=r.metrics.find(m=>m.name==='track_skills.cross').rows
  assert.equal(cells.find(r=>r.track==='control'&&r.skill==='Python').describedN,0)
  assert.equal(cells.find(r=>r.track==='control'&&r.skill==='Python').describedShare,null)
})
test('analysis limits, missing rules and duplicate words cannot fall back to defaults',()=>{
  for(const extra of [{analysis:undefined},{analysis:{tracks:analysis.tracks,skills:['Python','python']}},{analysis:{tracks:[{key:'x',label:'x',titleAny:[]}],skills:['x']}},{analysis:{tracks:Array(13).fill(analysis.tracks[0]),skills:['x']}}])assert.throws(()=>request(extra))
  assert.throws(()=>request({analysis:{tracks:[{...analysis.tracks[0],sql:'SELECT 1'}],skills:['Python']}}))
  assert.throws(()=>request({analysis:{tracks:[{key:'__OTHER__',label:'保留项',titleAny:['x']}],skills:['Python']}}))
})
test('empty and missing salary keep distinct states; aggregate evidence never contains description text',()=>{
  const {result:r,execution:e}=result({}, {empty:true})
  assert.equal(r.status,'empty')
  assert(r.metrics.every(m=>m.status==='empty'))
  const n=result({}, {noSalary:true}).result
  assert.equal(n.metrics.find(m=>m.name==='salary.summary').status,'unavailable')
  assert(n.metrics.find(m=>m.name==='track_salary.summary').rows.every(r=>r.summary.median===null))
  assert(!JSON.stringify(e.logs.map(j=>j.rows)).includes('Python Python'))
})
test('bad/partial analytical aggregates are rejected instead of fabricated zeros',()=>{
  const f=result()
  const broken=structuredClone(f.execution)
  broken.logs.find(j=>j.id==='all:skills').rows[0].hits.Python=999
  assert.throws(()=>buildResult(f.request,f.plan,broken),/提及数/)
  const missing=structuredClone(f.execution)
  missing.logs=missing.logs.filter(j=>j.id!=='all:tracks')
  const r=buildResult(f.request,f.plan,missing)
  assert.equal(r.metrics.find(m=>m.name==='track.distribution').status,'failed')
  assert.equal(r.status,'partial')
})
test('analysis policies bind hashes and old results without analysis remain verifiable',()=>{
  const a=request(),b=request({analysis:{...analysis,tracks:analysis.tracks.toReversed()}})
  assert.notEqual(hash(semanticRequest(a)),hash(semanticRequest(b)))
  const r=result().result
  assert.equal(resultContentHash(r),r.contentHash)
})
test('no descriptions means unavailable skill evidence instead of a measured zero demand',()=>{
  const r=result({}, {noDescription:true}).result
  assert.equal(r.metrics.find(m=>m.name==='skills.distribution').status,'unavailable')
  assert(r.errors.some(e=>e.code==='NO_VALID_DESCRIPTION'))
})
test('city aliases merge before publishing analytical cross rows',()=>{
  const f=result(),e=structuredClone(f.execution)
  const rows=e.logs.find(j=>j.id==='all:tracks').rows
  rows.splice(0,rows.length,{province:'广东',city:'广州',track:'algo',count:1},{province:'广东省',city:'广州市',track:'algo',count:1},{province:'广东省',city:'广州市',track:'control',count:1},{province:'广东省',city:'广州市',track:'__other__',count:1})
  const r=buildResult(f.request,f.plan,e)
  const m=r.metrics.find(m=>m.name==='city_track.cross')
  assert.equal(m.rows.length,3);assert.equal(m.rows.find(r=>r.track==='algo').count,2)
})
test('track salary disagreement fails even when the grand total still matches',()=>{
  const f=result(),e=structuredClone(f.execution)
  const row=e.logs.find(j=>j.id==='all:salary').rows.find(r=>r.track==='algo')
  row.track='control'
  const r=buildResult(f.request,f.plan,e)
  assert.equal(r.metrics.find(m=>m.name==='track_salary.summary').status,'failed')
  assert.equal(r.metrics.find(m=>m.name==='salary.summary').status,'complete')
  assert(!r.quality.allPass)
})
