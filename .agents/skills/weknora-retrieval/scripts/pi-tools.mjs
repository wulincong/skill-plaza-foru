import { readFileSync } from 'node:fs'
import { join, resolve, sep } from 'node:path'

export function blockedLearningCall(event, cwd) {
  const input=event.input || {}, path=String(input.path || ''), command=String(input.command || '')
  if (['write','edit'].includes(event.toolName)) {
    const target=resolve(cwd,path)
    if (!target.startsWith(resolve(cwd)+sep)) return '学习会话只能在当前工作区写文件，不能改动技能安装目录。'
    if (/\.(?:weknora-(?:evidence|runtime)|learning-request)/.test(path)) return '知识库来源与授权记录由宿主维护，不能生成或改写。'
  }
  if (event.toolName==='bash' && /\.weknora-(?:evidence|runtime)|\.learning-request|weknora-retrieval\/.*\.env|WEKNORA_API_KEY/.test(command)) return '知识库记录和凭据由宿主维护；请调用 weknora_retrieve，来源校验由构建器完成。'
}

export default function registerWeKnora(pi) {
  pi.on('tool_call',(event,ctx)=>{const reason=blockedLearningCall(event,ctx.cwd);if(reason)return {block:true,reason}})

  pi.registerTool({
    name:'weknora_retrieve', label:'查询课程知识库',
    description:'共享 WeKnora 检索。先 tags 查课程包分类，再 documents 按 tag 列教材，search 查内容，chunks 核对原文。kb 为调用方指定的获准库 ID。分页按 next_page 继续。documents 返回 preview_url/download_url 是可直接放进学习报告的教材入口；不要使用需要 Key 的 *_api_url。接口错误不能当作无匹配，失败时停止并请用户选择。',
    parameters:{type:'object',properties:{
      operation:{type:'string',enum:['tags','documents','search','chunks']},
      kb:{type:'string',description:'获准知识库 ID，默认万维自建课程库 b627daef-d505-4f16-9ee9-76474a6e5bde'},
      keyword:{type:'string',description:'tags/documents 可选名称关键词'},
      tag:{type:'string',description:'documents 可选分类 ID，来自 tags'},
      query:{type:'string',description:'search 的问题'},
      document:{type:'string',description:'search 可选、chunks 必填的文档 ID'},
      page:{type:'integer',minimum:1,description:'tags/documents/chunks 页码，默认1'},
    },required:['operation','kb'],additionalProperties:false},
    async execute(_id,params,signal,_update,ctx) {
      try {
        const runtime=JSON.parse(readFileSync(join(ctx.cwd,'.weknora-runtime.json'),'utf8'))
        const response=await fetch(runtime.url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(params),signal})
        const result=await response.json()
        return {content:[{type:'text',text:JSON.stringify(result)}],isError:!response.ok,details:{owner:'weknora-retrieval',status:result.status}}
      } catch {
        return {content:[{type:'text',text:JSON.stringify({status:'unavailable',message:'本会话知识库通道不可用，请停止查询并说明缺口。'})}],isError:true,details:{owner:'weknora-retrieval',status:'unavailable'}}
      }
    },
  })
}
