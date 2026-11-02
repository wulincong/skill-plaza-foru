#!/usr/bin/env node
import { readFile, stat } from 'node:fs/promises'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { capabilities, fail, QueryError } from './talent-data/core.mjs'
import { planQuery, resolveEntity, query } from './talent-data/service.mjs'
import { withinWorkspace, preview, readResult, persistExport } from './talent-data/artifacts.mjs'

const HELP=`人才数据库查询（talent-query/1）
  node scripts/talent-data-query.mjs capabilities
  node scripts/talent-data-query.mjs resolve --kind region|industry|role --name 名称
  node scripts/talent-data-query.mjs plan --request request.json
  node scripts/talent-data-query.mjs query --request request.json
  node scripts/talent-data-query.mjs inspect --result data/<id>/result.json
  node scripts/talent-data-query.mjs export --result data/<id>/result.json --format json|csv|markdown
在当前会话工作区执行；只接受结构化请求，不接受 SQL。完整结果和内部证据落入 data/。
退出码：complete/empty=0；partial=3；需澄清/修正请求=2；执行失败=1。`

function argumentsFor(argv) {
  const command=argv[0]
  const allowed={capabilities:[],resolve:['kind','name'],plan:['request'],query:['request'],inspect:['result'],export:['result','format']}[command]
  if(!allowed)fail('INVALID_REQUEST','未知操作，请使用 --help')
  const options={}
  for(let i=1;i<argv.length;i+=2) {
    const key=argv[i].startsWith('--')?argv[i].slice(2):''
    if(!allowed.includes(key)||options[key]!==undefined||argv[i+1]===undefined)fail('INVALID_REQUEST',`不支持或重复的参数：${argv[i]}`)
    options[key]=argv[i+1]
  }
  for(const key of allowed)if(!options[key])fail('INVALID_REQUEST',`缺少 --${key}`)
  return {command,options}
}
export async function runCli(argv=process.argv.slice(2),{workspace=process.cwd(),emit=value=>process.stdout.write(JSON.stringify(value)+'\n'),...serviceOptions}={}) {
  if(!argv.length||argv[0]==='--help'){process.stdout.write(HELP+'\n');return 0}
  try {
    const {command,options}=argumentsFor(argv)
    let output,code=0
    if(command==='capabilities')output=capabilities()
    if(command==='resolve')output=await resolveEntity(options.kind,options.name,serviceOptions)
    if(command==='plan'||command==='query') {
      const file=await withinWorkspace(options.request,workspace)
      if((await stat(file)).size>65536)fail('INVALID_REQUEST','请求文件超过 64KB 上限')
      let raw
      try {raw=JSON.parse(await readFile(file,'utf8'))}catch{fail('INVALID_REQUEST','请求文件不是有效 JSON')}
      if(command==='plan')output=await planQuery(raw,serviceOptions)
      else {
        const result=await query(raw,{...serviceOptions,workspace})
        output=preview(result,result.request.output.previewRows)
        code={complete:0,empty:0,partial:3,failed:1}[result.status]??1
      }
    }
    if(command==='inspect'||command==='export') {
      const result=await readResult(options.result,workspace)
      if(command==='inspect')output=preview(result,10)
      else {
        if(!['json','csv','markdown'].includes(options.format))fail('INVALID_REQUEST','format 支持 json/csv/markdown')
        output=await persistExport(result,options.format,workspace)
      }
    }
    emit(output)
    process.exitCode=code
    return code
  } catch(error) {
    const known=error instanceof QueryError||error.code==='CONFIG_MISSING'
    const code=known?error.code:error instanceof SyntaxError?'INVALID_REQUEST':'EXECUTION_ERROR'
    const clarification=['INVALID_REQUEST','UNSUPPORTED','NEEDS_CLARIFICATION','QUERY_TOO_BROAD'].includes(code)
    emit({schema:'talent-error/1',status:clarification?'needs_clarification':'failed',errors:[{code,message:known?error.message:'查询工具执行失败，请核对请求文件、工件与运行环境',retryable:false,...(error.details??{})}]})
    process.exitCode=clarification?2:1
    return process.exitCode
  }
}
if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href)await runCli()
