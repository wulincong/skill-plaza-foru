import test from 'node:test'
import assert from 'node:assert/strict'
import {dataRefreshRequested,collectionExecution} from './refresh_policy.mjs'
import {buildRequest,applyProfile,inferProfileName} from './collect_data.mjs'

test('explicit source refresh cannot be served from a previous query snapshot',()=>{
 const plan={execution:{freshness:'snapshot-only',snapshotId:'old',deadlineMs:90000},filters:{region:{level:'province',name:'山东省'}}}
 const before=structuredClone(plan)
 const result=collectionExecution(plan,{schema:'plaza-report-turn/1',enabled:true,requestText:'请重新查询源库最新数据，生成山东省人工智能报告'})
 assert.equal(result.freshness,'live');assert.equal(result.snapshotId,undefined);assert.equal(result.deadlineMs,90000);assert.deepEqual(plan,before)
})
test('presentation revisions and explicit non-refresh preserve the intended query mode',()=>{
 for(const text of ['不要重新查询数据，只优化最新的图片','保留数据，使用最新的代码和格式','无需刷新数据，只改排版'])assert.equal(dataRefreshRequested(text),false,text)
 const plan={execution:{freshness:'cache-ok'}}
 assert.equal(collectionExecution(plan,{schema:'plaza-report-turn/1',enabled:true,requestText:'优化摘要，保留数据'}).freshness,'cache-ok')
 assert.equal(collectionExecution(plan,{schema:'untrusted',enabled:true,requestText:'重新查询'}).freshness,'cache-ok')
})
test('collection errors identify the actual malformed top-level fields without dropping filters',()=>{
 const plan={schema:'wechat-report-plan/1',filters:{region:{level:'province',name:'广东省'}},profile:'人工智能'}
 assert.throws(()=>buildRequest(plan),/profile.*允许字段/);assert.equal(plan.filters.region.name,'广东省')
})
test('custom analysis is preserved rather than silently overwritten by a profile',()=>{
 const plan={analysis:{custom:true}}
 assert.throws(()=>applyProfile(plan,{name:'人工智能',analysis:{canonical:true}}),/移除analysis.*移除--profile/)
 assert.deepEqual(plan.analysis,{custom:true})
})

test('a missing optional flag still selects the exact known root profile without changing filters',()=>{
 const plan={filters:{region:{level:'province',name:'广东省'},industries:[{id:'26',includeDescendants:true}]}}
 const before=structuredClone(plan);const profiles={'人工智能':{name:'人工智能'},'智能制造':{name:'智能制造'}}
 const candidates={'人工智能':[{id:'26',name:'人工智能',level:0},{id:'99',name:'人工智能',level:2}],'智能制造':[{id:'17',name:'智能制造',level:0}]}
 assert.equal(inferProfileName(plan,profiles,candidates),'人工智能');assert.deepEqual(plan,before)
 assert.equal(inferProfileName({...plan,analysis:{custom:true}},profiles,candidates),undefined)
 assert.equal(inferProfileName({...plan,filters:{...plan.filters,industries:[{id:'99',includeDescendants:true}]}},profiles,candidates),undefined)
})
