import { fileURLToPath } from 'node:url'
import { readMysqlConfig } from '../mysql-config.mjs'
import { MysqlAdapter, assertReadCapability } from './db.mjs'
import { StateStore } from './state.mjs'
import { EntityResolver } from './entities.mjs'
import { validateRequest, semanticRequest, hash, VERSION, fail, now } from './core.mjs'
import { buildPlan } from './compile.mjs'
import { buildResult, resultContentHash } from './metrics.mjs'
import { persistResult } from './artifacts.mjs'

export async function context(options={}) {
  const cfg=options.cfg??readMysqlConfig()
  const sourceKey=hash({host:cfg.MYSQL_HOST,port:String(cfg.MYSQL_PORT??3306),user:cfg.MYSQL_USER,database:cfg.MYSQL_DATABASE,engine:VERSION})
  const state=options.state??new StateStore(process.env.TALENT_QUERY_STATE_DIR??fileURLToPath(new URL('../../web/server/workspace/.talent-query-state',import.meta.url)))
  await state.init()
  return {cfg,sourceKey,state,signal:options.signal,adapter:options.adapter??new MysqlAdapter(cfg,{signal:options.signal})}
}
async function capability(ctx,deadlineAt) {
  const key=hash({source:ctx.sourceKey,capability:1})
  if(await ctx.state.read('dictionaries',key,86400000))return
  await ctx.state.lock(`light:${ctx.sourceKey}`,deadlineAt,async({onSpawn})=>{
    if(await ctx.state.read('dictionaries',key,86400000))return
    const rows=await assertReadCapability(ctx.adapter,deadlineAt,onSpawn)
    await ctx.state.write('dictionaries',key,{rows})
  },ctx.signal)
}
async function resolvedPlan(request,ctx,deadlineAt) {
  const resolver=new EntityResolver({...ctx,deadlineAt})
  const cohorts=await resolver.cohorts(request.cohorts)
  return {plan:buildPlan(request,cohorts),resolutionEvidence:resolver.evidence}
}
export async function planQuery(raw,options={}) {
  const request=validateRequest(raw),ctx=await context(options),deadlineAt=Date.now()+Math.min(30000,request.execution.deadlineMs)
  const {plan}=await resolvedPlan(request,ctx,deadlineAt)
  return {schema:'talent-plan/1',request,cohorts:plan.cohorts,cost:plan.cost,queryCount:plan.queryCount,logicalCohortCount:plan.logicalCohortCount,jobs:plan.jobs.map(j=>({id:j.id,kind:j.kind,...(j.cohortIds?{cohortIds:j.cohortIds}:{}),dimensions:j.dimensions??[j.dimension].filter(Boolean)})),description:plan.description,executesAggregates:false}
}
export async function resolveEntity(kind,name,options={}) {
  const ctx=await context(options),resolver=new EntityResolver({...ctx,deadlineAt:Date.now()+15000})
  return {schema:'talent-entities/1',...await resolver.search(kind,name)}
}
function usableCache(envelope,key,semantic,maxAgeMs) {
  if(!envelope)return false
  const p=envelope.payload
  const readAt=Date.parse(p.result?.freshness?.dataReadAt),age=Date.now()-readAt
  return p.sourceKey===key && p.semanticHash===semantic && typeof p.result?.snapshotId==='string' && Number.isFinite(age)&&age>=0&&age<=maxAgeMs && ['complete','empty'].includes(p.result?.status) && resultContentHash(p.result)===p.result.contentHash && p.result.quality.allPass
}
export async function query(raw,options={}) {
  const entered=Date.now(),startedAt=now(),stages={}
  const stage=async(name,work)=>{
    const start=Date.now();options.onStage?.({stage:name,state:'started'})
    try {const value=await work();options.onStage?.({stage:name,state:'completed',durationMs:Date.now()-start});return value}
    catch(error){options.onStage?.({stage:name,state:'failed',durationMs:Date.now()-start,code:error.code??'EXECUTION_ERROR'});throw error}
    finally{stages[name]=Date.now()-start}
  }
  const request=await stage('validation',()=>validateRequest(raw)),deadlineAt=entered+request.execution.deadlineMs
  const ctx=await stage('setup',()=>context(options)),semanticHash=hash(semanticRequest(request))
  let cached,cacheKey,plan,resolutionEvidence=[],coalesced=false
  if(request.execution.freshness==='snapshot-only') {
    cached=await ctx.state.read('snapshots',request.execution.snapshotId,request.execution.maxAgeMs)
    if(!usableCache(cached,ctx.sourceKey,semanticHash,request.execution.maxAgeMs))fail('SNAPSHOT_UNAVAILABLE','指定快照不存在、已过期或与本次完整统计条件不一致')
    cacheKey=cached.payload.cacheKey
  } else {
    const resolved=await stage('resolution',()=>resolvedPlan(request,ctx,deadlineAt))
    plan=resolved.plan;resolutionEvidence=resolved.resolutionEvidence
    cacheKey=hash({semanticHash,resolution:plan.cohorts.map(c=>c.fingerprint),source:ctx.sourceKey})
    cached=request.execution.freshness==='cache-ok'?await stage('cache_lookup',()=>ctx.state.read('cache',cacheKey,request.execution.maxAgeMs)):null
    if(!usableCache(cached,ctx.sourceKey,semanticHash,request.execution.maxAgeMs))cached=null
  }
  let payload=cached?.payload
  if(!payload) {
    const requestQueuedAt=Date.now()
    options.onStage?.({stage:'request_queue',state:'started'})
    payload=await ctx.state.lock(`request:${cacheKey}`,deadlineAt,async({waited})=>{
      stages.request_queue=Date.now()-requestQueuedAt
      options.onStage?.({stage:'request_queue',state:'completed',durationMs:stages.request_queue})
      const afterWait=await ctx.state.read('cache',cacheKey,request.execution.maxAgeMs)
      if(usableCache(afterWait,ctx.sourceKey,semanticHash,request.execution.maxAgeMs)&&(request.execution.freshness==='cache-ok'||waited&&afterWait.writtenAt>=entered)) {coalesced=waited;return afterWait.payload}
      await stage('capability',()=>capability(ctx,deadlineAt))
      const queuedAt=Date.now()
      options.onStage?.({stage:'database_queue',state:'started'})
      return ctx.state.lock(`heavy:${ctx.sourceKey}`,deadlineAt,async({onSpawn})=>{
        const queueMs=Date.now()-queuedAt
        stages.database_queue=queueMs
        options.onStage?.({stage:'database_queue',state:'completed',durationMs:queueMs})
        const executed=await stage('database',()=>ctx.adapter.run(plan.jobs,{deadlineAt,timeoutMs:request.execution.timeoutMs,consistent:true,onSpawn}))
        options.onStage?.({stage:'database_result',state:executed.error?'failed':'completed',code:executed.error?.code,queryCount:executed.logs?.length??0,
          statements:(executed.logs??[]).map(log=>({id:log.id,completed:log.completed,serverElapsedMs:log.serverElapsedMs??null}))})
        const result=await stage('aggregation',()=>buildResult(request,plan,{...executed,startedAt}))
        result.execution.queueMs=queueMs
        const item={sourceKey:ctx.sourceKey,semanticHash,cacheKey,result,evidence:{schema:'talent-evidence/1',engine:VERSION,request,resolution:resolutionEvidence,queries:executed.logs,error:executed.error??null,sourceReadTime:executed.sourceReadTime,contentHash:result.contentHash}}
        if(['complete','empty'].includes(result.status)&&result.quality.allPass) {
          result.snapshotId=hash({sourceKey:ctx.sourceKey,contentHash:result.contentHash,dataReadAt:result.freshness.dataReadAt})
          await stage('cache_write',async()=>{await ctx.state.write('snapshots',result.snapshotId,item);await ctx.state.write('cache',cacheKey,item)})
        }
        return item
      },ctx.signal)
    },ctx.signal)
  }
  const result=structuredClone(payload.result)
  result.request=request
  result.cacheKey=cacheKey
  result.freshness.servedAt=now()
  const reused=Boolean(cached)||coalesced||result.freshness.executedAt!==startedAt
  result.freshness.mode=reused?(request.execution.freshness==='snapshot-only'?'snapshot':coalesced?'coalesced':'cache'):'live'
  result.freshness.cacheAgeMs=reused?Math.max(0,Date.now()-Date.parse(result.freshness.dataReadAt)):0
  result.execution={...result.execution,reused,totalMs:Date.now()-entered,stages}
  if(resultContentHash(result)!==result.contentHash)fail('INVALID_ARTIFACT','缓存结果与当前请求内容不一致')
  return stage('artifacts',()=>persistResult(result,payload.evidence,options.workspace??process.cwd(),request.output.exports))
}
