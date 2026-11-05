// Skill-owned adapter: the report runner only mounts it and supplies user context.
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { demandParameters, queryDemand } from '../../../../scripts/talent-data/demand.mjs'
import { capabilities } from '../../../../scripts/talent-data/core.mjs'
import { readResult } from '../../../../scripts/talent-data/artifacts.mjs'

export function blockedQueryCall(event) {
  const input=event.input??{},path=String(input.path??''),command=String(input.command??'')
  if(['write','edit'].includes(event.toolName)&&/(?:^|\/)\.talent-query(?:\/|$)|talent-query-turn\.json|industry-report-input\.json/.test(path))return '查询运行记录由工具维护，不能改写。'
  if(['read','bash'].includes(event.toolName)&&/(?:^|[\s/"'])\.env(?:$|[\s/"'])|mysql-config|db_config\.json|MYSQL_PASSWORD|MYSQL_PWD/.test(path+' '+command))return '数据库配置由查询技能内部读取，报告侧不能读取或使用连接配置。'
  const code=event.toolName==='bash'?command:['write','edit'].includes(event.toolName)&&/\.(?:py|m?js|cjs|sh)$/.test(path)?String(input.content??input.newText??''):''
  if(/mysql-query|career-market-query|scripts\/talent-data\/|pymysql|mysql2?|MySQLdb|createConnection|SELECT\s+.+\s+FROM\s+c_(?:company|position)|\.talent-query\/|talent-query-turn\.json/i.test(code))return '人才取数只能调用 talent_query，由 talent-data-query 构造和执行；不能直接连接数据库或调用底层实现。'
  if(/(?:talent-data-query\.mjs|talent-data-query\/scripts\/query\.mjs)/.test(code)) {
    if(!/(?:query\.mjs["']?\s+(?:inspect|export|catalog|capabilities)\b)/.test(code))return '报告侧不构造查询文件或运行 query/plan/resolve；请把样本与指标提交给 talent_query。'
    // Only a single offline operation is allowed through the compatibility CLI.
    if(/[;|\n]|&&|\$\(|`/.test(code))return '离线核验请用 talent_inspect，避免把查询操作拼入命令。'
  }
  if(event.toolName==='write') {
    try{if(JSON.parse(input.content).schema==='talent-query/1')return 'talent-query/1 是查询技能内部请求；报告只向 talent_query 提交业务样本和指标。'}catch{}
  }
}

export default function registerTalentQuery(pi,{queryImpl=queryDemand}={}) {
  let queue=Promise.resolve()
  const serial=fn=>{const answer=queue.then(fn,fn);queue=answer.catch(()=>{});return answer}
  const turn=ctx=>{
    const value=JSON.parse(readFileSync(join(ctx.cwd,'talent-query-turn.json'),'utf8'))
    if(value.schema!=='talent-query-turn/1'||!value.runId||!Array.isArray(value.messages))throw new Error('缺少本轮查询上下文，无法执行取数')
    return value
  }
  pi.registerTool({name:'talent_query',label:'查询人才统计',parameters:demandParameters,
    promptSnippet:'唯一的人才统计取数入口。提交地域、产业名称、筛选和指标，由 talent-data-query 解析产业、生成请求、执行和留证。',
    description:'按 talent-data-query 规则取数。整个产业用 industries，明确的岗位名条件才用 title；一次声明所需指标。不接受 SQL、请求文件或超时参数。失败后停止自动重试，说明缺口并等待用户选择。返回完整工件路径与查询诊断。',
    execute:(_id,params,signal,update,ctx)=>serial(async()=>{
      const result=await queryImpl(params,{workspace:ctx.cwd,turn:turn(ctx),signal,
        onProgress:event=>{
          if(event.state==='started')update?.({content:[{type:'text',text:'正在执行人才数据查询'}],details:{owner:'talent-data-query',traceId:event.traceId,stage:event.stage}})
        }})
      if(['failed','needs_clarification'].includes(result.status))throw new Error(JSON.stringify(result))
      return {content:[{type:'text',text:JSON.stringify(result)}],details:{owner:'talent-data-query',status:result.status,...result.handoff}}
    })})
  pi.registerTool({name:'talent_query_capabilities',label:'读取人才查询能力',parameters:{type:'object',properties:{},additionalProperties:false},
    description:'离线读取共享查询技能支持的指标、枚举和边界；不连接数据库。',execute:async()=>({content:[{type:'text',text:JSON.stringify(capabilities())}],details:{owner:'talent-data-query'}})})
  pi.registerTool({name:'talent_inspect',label:'核验人才统计',parameters:{type:'object',properties:{resultPath:{type:'string',description:'工具返回的本会话 result.json 路径'}},required:['resultPath'],additionalProperties:false},
    description:'离线核验完整人才统计、工件指纹和来源。使用已有证据写报告或修订时调用，不重新查库。',execute:async(_id,params,_signal,_update,ctx)=>{
      const result=await readResult(params.resultPath,ctx.cwd)
      return {content:[{type:'text',text:JSON.stringify(result)}],details:{owner:'talent-data-query',requestId:result.requestId,status:result.status}}
    }})
  pi.on('tool_call',event=>{const reason=blockedQueryCall(event);if(reason)return {block:true,reason}})
  pi.on('before_agent_start',()=>({message:{customType:'talent-query-contract',display:false,content:
    '本会话的人才统计只使用 talent_query。业务侧不生成查询JSON、不调用查询CLI、不套timeout或自行重试。查询技能最新规则如下：\n'+
    readFileSync(fileURLToPath(new URL('../SKILL.md',import.meta.url)),'utf8')}}))
}
