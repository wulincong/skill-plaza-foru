import { readFileSync, writeFileSync } from 'node:fs'
import { join, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFile } from 'node:child_process'
import { randomUUID } from 'node:crypto'
const script=fileURLToPath(new URL('./matching.py',import.meta.url))
const dictionaries=JSON.parse(readFileSync(new URL('../references/dictionaries.json',import.meta.url),'utf8'))
const types={industry:'INDUSTRY',education:'EDUCATION',salary:'SALARY',experience:'EXPERIENCE',positionType:'POSITION_TYPE'}

export function blockedJobCall(event,cwd) {
 const input=event.input||{},path=String(input.path||''),command=String(input.command||'')
 if(['write','edit'].includes(event.toolName)) {
  if(!resolve(cwd,path).startsWith(resolve(cwd)+sep))return '岗位匹配只能在会话工作区写文件。'
  if(/\.job-(?:matching|request|query)/.test(path))return '候选来源与用户请求由工具维护，不能改写。'
 }
 if(event.toolName==='bash' && /\.job-(?:matching|request|query)/.test(command)) {
  const clean=command.replace(/2>&1/g,'')
  const simple=clean.split(/&&|\||;|\n/).filter(x=>x.trim()).every(x=>/^\s*(?:cd|ls|stat|wc|head|tail|cat|grep|pwd)\b/.test(x))
  if(!simple||/[><`]|\$\(/.test(clean))return '来源只读；使用read工具或简单cat/head核验，不运行修改候选的脚本。'
 }
}
export default function registerJobMatching(pi) {
 pi.on('tool_call',(event,ctx)=>{const reason=blockedJobCall(event,ctx.cwd);if(reason)return {block:true,reason}})
 pi.registerTool({name:'job_candidates',label:'检索求职候选岗位',
  description:'按明确筛选条件查询优才招聘公开接口，最多100个去重岗位，返回完整JD、原始字段与真实详情链接。筛选Key以字典为准，不自动放宽条件。简历仅本地解析，绝不发送招聘接口。resumePath须为用户已上传的uploads附件；resumeText须逐字来自用户消息。不含简历时只做条件推荐，完整匹配分记null。返回snapshot/sha256必须原样写入评估文件。',
  parameters:{type:'object',properties:{filters:{type:'object',properties:{keyword:{type:'string'},city:{type:'string'},district:{type:'string'},...Object.fromEntries(Object.entries(types).map(([k,v])=>[k,{type:'string',enum:Object.keys(dictionaries[v])}]))},required:['keyword'],additionalProperties:false},resumePath:{type:'string'},resumeText:{type:'string'}},required:['filters'],additionalProperties:false},
  async execute(_id,params,signal,_update,ctx) {
   const state=join(ctx.cwd,'.job-query-state.json')
   const context=JSON.parse(readFileSync(join(ctx.cwd,'.job-request.json'),'utf8'))
   const file=join(ctx.cwd,'.job-query-'+randomUUID()+'.json')
   try {
    // The form includes an exact machine-readable scope; a model cannot broaden it.
    const last=typeof context.message==='string' && context.message.includes('【岗位接口筛选】') ? context.message : undefined
    if(last) {
     const scope=JSON.parse(last.split('【岗位接口筛选】')[1].split('\n')[1])
     if(JSON.stringify(Object.entries(scope).sort())!==JSON.stringify(Object.entries(params.filters).sort()))throw Error('查询条件与表单选择不一致，请保留用户原范围')
    }
    writeFileSync(file,JSON.stringify(params),{mode:0o600})
    const result=await new Promise((resolve,reject)=>execFile('python3',[script,'query',file],{cwd:ctx.cwd,signal,timeout:120000,maxBuffer:8*1024*1024},(error,stdout)=>{
     try{const data=JSON.parse(stdout);if(error||data.status==='error')reject(Error(data.message||'岗位查询失败'));else resolve(data)}catch{reject(Error('岗位查询进程未返回有效结果'))}
    }))
    writeFileSync(state,JSON.stringify({runId:context.runId,status:result.status,snapshot:result.snapshot,sha256:result.sha256}),{mode:0o640})
    return {content:[{type:'text',text:JSON.stringify(result)}],details:{owner:'job-matching',status:result.status,candidateCount:result.candidateCount}}
   } catch(error) {
    writeFileSync(state,JSON.stringify({runId:context.runId,status:'error'}),{mode:0o640})
    return {isError:true,content:[{type:'text',text:JSON.stringify({status:'error',message:String(error.message).slice(0,300)})}],details:{owner:'job-matching',status:'error'}}
   }
  }
 })
}
