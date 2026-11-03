/** Pi stays the sole model client. The model writes small evidence-bound parts. */
import { Type } from '@earendil-works/pi-ai'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { mkdirSync,writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { reportTask,reportDataReady,reportBuildReady } from './reportWorkflowPolicy.mjs'

const execute=promisify(execFile)
const installed=fileURLToPath(new URL('../../../.agents/skills/wechat-report/',import.meta.url))
const purpose=Type.Optional(Type.String({description:'给用户看的简短中文用途，不写路径、命令或结果'}))
const prose=(minimum,description,maximum=180)=>Type.String({minLength:minimum,maxLength:maximum,pattern:'^[^0-9{}<>]*$',description:description+'。禁止任何阿拉伯数字、事实ID、花括号或HTML；已给事实由程序原样插入，不复述统计。'})
const section=Type.Object({key:Type.String(),title:prose(4,'本章的结构发现或有条件决策，不用决定/确保/保障',40),findingIds:Type.Optional(Type.Array(Type.String())),
  interpretation:prose(40,'解释事实之间的结构关系与决策取舍，不能只复述比例或编造原因'),
  action:prose(30,'写明谁针对哪些岗位做什么、产出什么清单或任务'),
  validation:prose(30,'写明复核对象、样本字段和判断依据'),decisionRule:prose(30,'写明何种复核结果会改变当前建议及怎样调整，不以高薪直接决定扩招')})
const claim=Type.Object({title:prose(6,'数据支持的跨维度结构结论，不用决定/确保/保障',32),findingIds:Type.Optional(Type.Array(Type.String())),interpretation:prose(40,'联合本条不同维度事实，说明含义及取舍',140),implication:prose(30,'据此提出可验证的决策与下一步',120)})

export default function registerReportWorkflow(pi) {
  let current
  let requests=0
  let runId
  let revisionApplied
  let baseTools
  let queue=Promise.resolve()
  const serial=fn=>{const result=queue.then(fn,fn);queue=result.catch(()=>{});return result}
  const active=ctx=>ctx.model?.provider==='youcai' && reportTask(ctx.cwd) && reportDataReady(ctx.cwd)
  const setStage=stage=>pi.setActiveTools(stage==='build'?['report_build']:stage==='submit'?['report_submit']:['report_next'])
  const invoke=async(ctx,task,args=[],signal)=>{
    try {
      const result=await execute(join(installed,'.venv/bin/python'),[join(installed,'scripts/report.py'),'--workdir',join(ctx.cwd,'wechat-report'),task,...args],
        {cwd:ctx.cwd,signal,timeout:240000,maxBuffer:4*1024*1024})
      return result.stdout.trim()
    } catch(error) {
      const details=String(error.stderr||error.message||'报告处理失败')
      const message=details.includes('ValueError:')?details.split('ValueError:').at(-1):details.split('\n').slice(-9).join('\n')
      throw new Error(message.trim().slice(0,7000))
    }
  }
  const nextResult=output=>{
    const parsed=JSON.parse(output)
    current=parsed
    setStage(parsed.status==='analysis_ready'?'build':'submit')
    return {content:[{type:'text',text:output}],details:{status:parsed.status}}
  }
  pi.registerTool({name:'report_next',label:'读取报告写作任务',promptSnippet:'获取当前短批次、事实和分析问题。仅开始或恢复时调用。',
    description:'获取报告的当前短批次，事实与不可变来源字段由程序提供。收到任务后调用report_submit填写文案，不要回复将要做什么。',
    parameters:Type.Object({purpose}),execute:(_id,_params,signal,_update,ctx)=>serial(async()=>{
      const task=reportTask(ctx.cwd)
      if(task?.revision && revisionApplied!==task.runId) {
        const output=await invoke(ctx,'revise',[task.runId],signal)
        revisionApplied=task.runId
        return nextResult(output)
      }
      return nextResult(await invoke(ctx,'next',[],signal))
    })})
  pi.registerTool({name:'report_submit',label:'提交报告分析章节',promptSnippet:'提交当前批次文案。程序保存进度并返回下一批，直到analysis_ready。',
    description:'只填写当前任务的章节或核心发现文案。不要填写schema/hash/task，程序自动绑定；findingIds可不填以保留已给事实。校验失败修正本批，禁止改脚本。每章解释至少四十字，行动/验证/调整条件各至少三十字。',
    parameters:Type.Object({purpose,sections:Type.Optional(Type.Array(section)),
      executive:Type.Optional(Type.Object({opening:prose(40,'总体判断与主要决策矛盾'),claims:Type.Array(claim,{minItems:3,maxItems:3}),closing:prose(40,'综合三项结论，提出有条件的执行顺序')})),
      limitations:Type.Optional(Type.Array(prose(20,'具体说明数据边界及不能推出什么')))}),
    execute:(id,params,signal,_update,ctx)=>serial(async()=>{
      if(!current || current.status!=='writing_required')return nextResult(await invoke(ctx,'next',[],signal))
      const part=JSON.parse(JSON.stringify(current.part))
      if(part.task.startsWith('sections:')) {
        if(!Array.isArray(params.sections))throw new Error('当前批次需要sections，填写返回任务中的全部章节')
        part.sections=params.sections.map(row=>({...row,findingIds:row.findingIds??part.sections.find(template=>template.key===row.key)?.findingIds??[]}))
      } else {
        if(!params.executive)throw new Error('当前批次需要executive、三条跨维度claims和limitations')
        part.executive={...params.executive,claims:params.executive.claims.map((row,i)=>({...row,findingIds:row.findingIds??part.executive.claims[i]?.findingIds??[]}))}
        part.limitations=params.limitations??[]
      }
      const folder=join(ctx.cwd,'wechat-report/output/analysis/submissions');mkdirSync(folder,{recursive:true})
      const file=join(folder,String(id).replace(/[^a-zA-Z0-9_-]/g,'_').slice(0,120)+'.json')
      writeFileSync(file,JSON.stringify(part),'utf8')
      return nextResult(await invoke(ctx,'accept',[file],signal))
    })})
  pi.registerTool({name:'report_build',label:'生成并检查报告图片',promptSnippet:'所有批次完成后生成最终图片、参考文献、图片网页与ZIP。',
    description:'在analysis_ready后调用，使用固定代码连续完成真实数据/文案/图表/图片验收与交付。成功后直接结束，不再复述统计数字。',
    parameters:Type.Object({purpose}),execute:(_id,_params,signal,_update,ctx)=>serial(async()=>{
      const output=await invoke(ctx,'build',[],signal)
      return {content:[{type:'text',text:output}],details:{status:'images_built'},terminate:true}
    })})
  pi.on('before_agent_start',(_event,ctx)=>{
    if(!baseTools)baseTools=pi.getActiveTools()
    const task=reportTask(ctx.cwd)
    if(task?.runId!==runId){runId=task?.runId;requests=0;current=undefined}
    if(active(ctx)){pi.setThinkingLevel('low');setStage('next')}
    else pi.setActiveTools(baseTools)
  })
  pi.on('tool_result',(_event,ctx)=>{
    if(active(ctx) && !current && !reportBuildReady(ctx.cwd,reportTask(ctx.cwd))) {pi.setThinkingLevel('low');setStage('next')}
  })
  pi.on('before_provider_request',(event,ctx)=>{
    if(!active(ctx))return
    const task=reportTask(ctx.cwd)
    if(reportBuildReady(ctx.cwd,task))return
    requests++
    // After the bound, let the server return a truthful failure instead of looping.
    if(requests>40)return
    const payload=event.payload
    if(!payload || typeof payload!=='object' || !Array.isArray(payload.tools) || !payload.tools.length)return
    const tools=payload.tools.map(tool=>{
      if(tool.function?.name!=='report_submit'||!current?.part)return tool
      const schema=structuredClone(tool.function.parameters)
      const sections=current.part.task.startsWith('sections:')
      schema.required=sections?['sections']:['executive','limitations']
      const keys=sections?['purpose','sections']:['purpose','executive','limitations']
      schema.properties=Object.fromEntries(Object.entries(schema.properties).filter(([key])=>keys.includes(key)))
      if(sections) {
        schema.properties.sections.minItems=current.part.sections.length
        schema.properties.sections.maxItems=current.part.sections.length
        schema.properties.sections.items.properties.key.enum=current.part.sections.map(row=>row.key)
      } else {
        schema.properties.limitations.minItems=2
        schema.properties.limitations.maxItems=5
      }
      return {...tool,function:{...tool.function,parameters:schema}}
    })
    return {...payload,tools,tool_choice:'required'}
  })
}
