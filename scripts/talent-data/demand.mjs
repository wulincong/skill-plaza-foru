// Business callers describe samples and metrics. This module owns query construction.
import { readFileSync, mkdirSync, writeFileSync, renameSync, appendFileSync, lstatSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { randomUUID } from 'node:crypto'
import { METRICS, ENUMS, object, textValue, validateRequest, hash, fail, QueryError } from './core.mjs'
import { context, query } from './service.mjs'
import { EntityResolver } from './entities.mjs'
import { preview, readResult } from './artifacts.mjs'

const string={type:'string',minLength:1,maxLength:80}
const strings={type:'array',items:string,maxItems:8}
const obj=(properties,required=[])=>({type:'object',properties,required,additionalProperties:false})
export const demandParameters=obj({
  samples:{type:'array',minItems:1,maxItems:4,description:'按问题一次列出需要的比较样本；产业名称由查询技能解析。',items:obj({
    region:obj({level:{enum:['national','province','city'],type:'string'},name:string,province:string},['level']),
    industries:{...strings,description:'整个产业使用名称，例如智能网联汽车；不能改成岗位名称搜索。'},
    roles:{...strings,description:'仅明确按岗位类型筛选时填写其名称。'},
    title:obj({any:strings,all:strings,exclude:strings}),
    ...Object.fromEntries(Object.entries(ENUMS).map(([key,values])=>[key,{type:'array',items:{type:'string',enum:Object.keys(values)},maxItems:20}])),
    updatedAt:obj({from:string,to:string}),
  },['region'])},
  metrics:{type:'array',minItems:1,maxItems:20,items:{type:'string',enum:Object.keys(METRICS)},description:'一次声明当前论证需要的全部指标；纯数量问题才仅选positions.count。'},
  analysis:obj({
    tracks:{type:'array',minItems:1,maxItems:12,items:obj({key:string,label:string,titleAny:strings,roleIds:{type:'array',items:string,maxItems:40}},['key','label'])},
    skills:{type:'array',minItems:1,maxItems:60,items:string},
  }),
  freshness:{type:'string',enum:['cache-ok','live'],description:'默认cache-ok；用户明确要求刷新才选live。'},
  purpose:{type:'string',maxLength:80,description:'面向用户的简短取数用途'},
},['samples','metrics'])

const catalog=JSON.parse(readFileSync(fileURLToPath(new URL('../../.agents/skills/talent-data-query/data/position-catalog.json',import.meta.url)),'utf8'))
const industryNames=[...new Set(catalog.industries.filter(i=>i.level===0).map(i=>i.name))].sort((a,b)=>b.length-a.length)
export function requestedIndustries(messages=[]) {
  let required=[]
  for(const message of messages) {
    // An explicit title-only request may supersede a previous industry task.
    if(/(?:岗位|职位)(?:名|名称).{0,8}(?:包含|含有|含|匹配)|仅按岗位名|只按岗位名/.test(message)){required=[];continue}
    const found=industryNames.filter(name=>message.includes(name)).filter(name=>!industryNames.some(other=>other!==name&&other.includes(name)&&message.includes(other)))
    if(found.length && /产业|行业|领域|人才需求/.test(message))required=found
  }
  return required
}

export function validateDemand(raw,{messages=[]}={}) {
  object(raw,['samples','metrics','analysis','freshness','purpose'],'取数需求')
  if(!Array.isArray(raw.samples)||!raw.samples.length||raw.samples.length>4)fail('INVALID_REQUEST','samples需要1–4个样本')
  const required=requestedIndustries(messages)
  const cohorts=raw.samples.map((sample,index)=>{
    object(sample,['region','industries','roles','title','education','experience','jobType','updatedAt'],'样本')
    const selectors=key=>{
      if(sample[key]!==undefined&&(!Array.isArray(sample[key])||sample[key].length>8))fail('INVALID_REQUEST',`${key}最多8个名称`)
      return (sample[key]??[]).map(name=>({name:textValue(name,80,key),includeDescendants:true}))
    }
    return {id:`sample_${index+1}`,filters:{...sample,industries:selectors('industries'),roles:selectors('roles')}}
  })
  const chosen=cohorts.flatMap(c=>c.filters.industries.map(i=>i.name))
  if(required.some(name=>!chosen.includes(name)))fail('SCOPE_MISMATCH',`当前用户任务要求产业：${required.join('、')}。必须保留产业筛选；不能自行用岗位名换词代替。若要变更口径，先向用户说明并取得选择。`,{requiredIndustries:required})
  return validateRequest({schema:'talent-query/1',cohorts,metrics:raw.metrics,...(raw.analysis?{analysis:raw.analysis}:{}),execution:{freshness:raw.freshness??'cache-ok'},output:{previewRows:10,topN:20,exports:[]}})
}

export async function prepareDemand(raw,options={}) {
  const request=validateDemand(raw,options)
  const ctx=await context(options)
  const resolver=new EntityResolver({...ctx,deadlineAt:Date.now()+Math.min(15000,options.remainingMs??15000)})
  for(const cohort of request.cohorts) {
    for(const selector of cohort.filters.industries) {
      const match=await resolver.search('industry',selector.name)
      const roots=match.candidates.filter(row=>row.name===selector.name&&row.level===0)
      if(roots.length!==1)fail('NEEDS_CLARIFICATION','未唯一识别一级产业；请明确目录中的产业名称，不自动改用名称关键词',{entity:selector.name,candidates:match.candidates})
      selector.id=roots[0].id;delete selector.name
    }
  }
  return request
}

// A durable per-turn budget survives Pi retries/restarts. It does not infer user permission.
export async function queryDemand(raw,{workspace,turn,signal,onProgress,...options}) {
  if(!workspace||!turn?.runId)fail('INVALID_REQUEST','受管取数需要工作区和本轮运行标识')
  const directory=join(workspace,'.talent-query')
  mkdirSync(directory,{recursive:true,mode:0o2770})
  if(lstatSync(directory).isSymbolicLink())fail('INVALID_PATH','查询运行目录不得为符号链接')
  const stateFile=join(directory,`${hash(turn.runId)}.json`),traceId=`td-${randomUUID()}`
  let state={consumedMs:0,batches:0}
  try{state=JSON.parse(readFileSync(stateFile,'utf8'))}catch(error){if(error.code!=='ENOENT')throw error}
  const save=()=>{const temp=stateFile+'.tmp';writeFileSync(temp,JSON.stringify(state),{mode:0o640});renameSync(temp,stateFile)}
  const started=Date.now(),events=[]
  const record=event=>{
    const entry={schema:'talent-query-stage/1',owner:'talent-data-query',runId:turn.runId,traceId,at:new Date().toISOString(),...event}
    appendFileSync(join(directory,'events.jsonl'),JSON.stringify(entry)+'\n',{mode:0o640})
    events.push(entry);onProgress?.(entry)
  }
  record({stage:'demand',state:'started'})
  let invoked=false
  try {
    if(signal?.aborted)fail('QUERY_ABORTED','查询已取消')
    if(state.stopped||state.inFlight){state.stopped=true;fail('QUERY_STOPPED','本轮取数已失败或中断，停止自动重试。报告侧应说明缺口并等待用户选择。')}
    const normalized=validateDemand(raw,{messages:turn.messages})
    const demandHash=hash(normalized)
    if(state.demandHash===demandHash&&state.result) {
      const result=await readResult(state.result,workspace)
      record({stage:'reuse',state:'completed',result:result.artifacts.result})
      return {...preview(result,10),handoff:{owner:'talent-data-query',traceId,runId:turn.runId,reused:true,wallMs:Date.now()-started}}
    }
    const remaining=240000-state.consumedMs
    if(remaining<1000||state.batches>=2)fail('QUERY_BUDGET_EXCEEDED','本轮取数预算已用尽，请基于已有结果说明缺口，不继续试查。')
    record({stage:'scope_resolution',state:'started'})
    const request=await prepareDemand(raw,{...options,signal,messages:turn.messages,remainingMs:remaining})
    record({stage:'scope_resolution',state:'completed',durationMs:Date.now()-started,
      samples:request.cohorts.map(c=>({id:c.id,region:c.filters.region,industries:c.filters.industries})),metrics:request.metrics})
    if(remaining-(Date.now()-started)<1000)fail('QUERY_BUDGET_EXCEEDED','本轮取数预算已用尽，未启动统计查询。')
    request.execution.deadlineMs=remaining-(Date.now()-started)
    request.execution.timeoutMs=Math.min(120000,request.execution.deadlineMs)
    state.inFlight=true;state.batches++;save();invoked=true
    const result=await query(request,{...options,workspace,signal,onStage:record})
    state.result=result.artifacts.result;state.demandHash=demandHash
    if(result.status==='failed'||result.errors?.some(e=>['QUERY_TIMEOUT','DEADLINE_EXCEEDED','QUERY_ABORTED','DATABASE_ERROR'].includes(e.code)))state.stopped=true
    record({stage:'handoff',state:result.status,result:result.artifacts.result,requestId:result.requestId,
      wallMs:Date.now()-started,execution:result.execution,errors:result.errors})
    return {...preview(result,10),handoff:{owner:'talent-data-query',traceId,runId:turn.runId,wallMs:Date.now()-started,stopped:Boolean(state.stopped)}}
  } catch(error) {
    const code=error instanceof QueryError||error.code==='CONFIG_MISSING'?error.code:'EXECUTION_ERROR'
    if(invoked||!['INVALID_REQUEST','NEEDS_CLARIFICATION','SCOPE_MISMATCH','UNSUPPORTED','QUERY_TOO_BROAD'].includes(code))state.stopped=true
    const failedStage=events.findLast(event=>event.state==='started')?.stage??'demand'
    const message=error instanceof QueryError||error.code==='CONFIG_MISSING'?error.message:'查询技能执行失败，请按诊断标识检查查询记录'
    record({stage:'handoff',state:'failed',failedStage,code,wallMs:Date.now()-started})
    return {schema:'talent-error/1',status:['INVALID_REQUEST','NEEDS_CLARIFICATION','SCOPE_MISMATCH','UNSUPPORTED','QUERY_TOO_BROAD'].includes(code)?'needs_clarification':'failed',errors:[{code,message,retryable:false,...(error.details??{})}],handoff:{owner:'talent-data-query',runId:turn.runId,traceId,failedStage,wallMs:Date.now()-started,stopped:Boolean(state.stopped)}}
  } finally {
    state.consumedMs+=Date.now()-started;state.inFlight=false;save()
  }
}
