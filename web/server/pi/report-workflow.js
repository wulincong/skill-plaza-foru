/** Pi stays the sole model client. The model writes small evidence-bound parts. */
import { Type } from '@earendil-works/pi-ai'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { mkdirSync,writeFileSync,appendFileSync,readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { reportTask,reportDataReady,reportBuildReady,dataRefreshRequested } from './reportWorkflowPolicy.mjs'
import { compactReportContext } from './reportWorkflowContext.mjs'

const execute=promisify(execFile)
const installed=fileURLToPath(new URL('../../../.agents/skills/wechat-report/',import.meta.url))
const purpose=Type.Optional(Type.String({description:'给用户看的简短中文用途，不写路径、命令或结果'}))
const prose=(minimum,description,maximum=180)=>Type.String({minLength:minimum,maxLength:maximum,pattern:'^[^0-9{}<>]*$',description:description+'。禁止任何阿拉伯数字、事实ID、花括号或HTML；已给事实由程序原样插入，不复述统计。'})
const section=Type.Object({key:Type.String(),
  action:prose(30,'结合本地区城市、方向或工具，写具体课程项目、工作任务与学习产出'),
  validation:prose(30,'写项目组织、操作过程和学习成果评价标准，不写报告数据待核验'),decisionRule:prose(30,'写不同岗位条件对应的课程分流或项目层次，不写待审核或待确认')})
const claim=Type.Object({implication:prose(30,'按当前条目主题写决策：城市条目写条件匹配与合作顺序，薪酬条目写报价区间与求职预期，方向条目写工具与课程项目',100)})

export default function registerReportWorkflow(pi) {
  let current
  let requests=0
  let runId
  let revisionApplied
  let baseTools
  let baseThinking
  let queue=Promise.resolve()
  const serial=fn=>{const result=queue.then(fn,fn);queue=result.catch(()=>{});return result}
  const active=ctx=>ctx.model?.provider==='youcai' && reportTask(ctx.cwd) && reportDataReady(ctx.cwd)
  const actionThinking=process.env.WECHAT_REPORT_ACTION_THINKING?.trim() || 'off'
  const setStage=stage=>pi.setActiveTools(stage==='build'?['report_build']:stage==='core'?['report_core']:stage==='submit'?['report_submit']:['report_next'])
  const invoke=async(ctx,task,args=[],signal)=>{
    try {
      const result=await execute(join(installed,'.venv/bin/python'),[join(installed,'scripts/report.py'),'--workdir',join(ctx.cwd,'wechat-report'),task,...args],
        {cwd:ctx.cwd,signal,timeout:240000,maxBuffer:4*1024*1024})
      return result.stdout.trim()
    } catch(error) {
      const details=[error.stdout,error.stderr||error.message||'报告处理失败'].filter(Boolean).join('\n')
      const failed=String(error.stdout||'').split('\n').filter(line=>/FAIL|"status"\s*:\s*"failed"/.test(line))
      const causes=[...details.matchAll(/(?:^|\n)(?:ValueError|RuntimeError|AssertionError|TypeError):/g)]
      const cause=causes.length?details.slice(causes.at(-1).index).trim().split(/\nTraceback \(most recent call last\)/)[0]:undefined
      const message=failed.length?failed.join('\n'):cause??details.split('\n').slice(-9).join('\n')
      throw new Error(message.trim().slice(0,7000))
    }
  }
  const nextResult=output=>{
    const parsed=JSON.parse(output)
    current=parsed
    setStage(parsed.status==='analysis_ready'?'build':parsed.part?.task==='executive'?'core':'submit')
    return {content:[{type:'text',text:output}],details:{status:parsed.status}}
  }
  pi.registerTool({name:'report_next',label:'读取报告写作任务',promptSnippet:'开始或恢复报告；尚未取得本次范围数据时初始化并返回正确采集模板，数据就绪时返回短写作任务。',
    description:'获取报告的当前短批次，事实与不可变来源字段由程序提供。收到任务后调用report_submit填写文案，不要回复将要做什么。',
    parameters:Type.Object({purpose}),execute:(_id,_params,signal,_update,ctx)=>serial(async()=>{
      const task=reportTask(ctx.cwd)
      if(!reportDataReady(ctx.cwd)) {
        current=undefined
        const prepared=JSON.parse(await invoke(ctx,'init',[],signal))
        if(dataRefreshRequested(task?.requestText))prepared.planTemplate.execution={freshness:'live',deadlineMs:360000}
        return {content:[{type:'text',text:JSON.stringify({...prepared,status:'collection_required',
          next:'按当前用户范围resolve产业，照planTemplate填写plan.json，再执行collect。已有文件不代表当前范围已就绪；不得用旧范围写作。'})}],details:{status:'collection_required'}}
      }
      if(task?.revision && revisionApplied!==task.runId) {
        const output=await invoke(ctx,'revise',[task.runId],signal)
        revisionApplied=task.runId
        return nextResult(output)
      }
      return nextResult(await invoke(ctx,'next',[],signal))
    })})
  const submitPart=(id,params,signal,ctx)=>serial(async()=>{
      if(!reportDataReady(ctx.cwd))throw new Error("本次范围数据尚未就绪，请先report_next并按模板取数，不能沿用旧范围写作")
      if(!current || current.status!=='writing_required')return nextResult(await invoke(ctx,'next',[],signal))
      const part=JSON.parse(JSON.stringify(current.part))
      if(part.task.startsWith('sections:')) {
        if(!Array.isArray(params.sections))throw new Error('当前批次需要sections，填写返回任务中的全部章节')
        if(params.sections.length!==part.sections.length || new Set(params.sections.map(row=>row.key)).size!==part.sections.length || params.sections.some(row=>!part.sections.some(template=>template.key===row.key)))throw new Error('必须填写本批所有章节，各key只出现一次')
        part.sections=part.sections.map(template=>{
          const row=params.sections.find(row=>row.key===template.key)
          return {...template,action:row.action,validation:row.validation,decisionRule:row.decisionRule}
        })
      } else {
        if(!params.executive)throw new Error('当前批次需要executive、三条跨维度claims和limitations')
        part.executive={...part.executive,closing:params.executive.closing,
          claims:part.executive.claims.map((template,i)=>({...template,implication:params.executive.claims[i]?.implication}))}
        part.limitations=current.part.limitations
      }
      const folder=join(ctx.cwd,'wechat-report/output/analysis/submissions');mkdirSync(folder,{recursive:true})
      const file=join(folder,String(id).replace(/[^a-zA-Z0-9_-]/g,'_').slice(0,120)+'.json')
      writeFileSync(file,JSON.stringify(part),'utf8')
      return nextResult(await invoke(ctx,'accept',[file],signal))
    })

  pi.registerTool({name:'report_submit',label:'提交报告行动章节',
    promptSnippet:'补充当前章节的行动、验证与调整条件，工具返回下一阶段。',
    description:'程序已给定结构分析，只填本批全部章节key/action/validation/decisionRule。每项至少三十字，不写数字，不改事实和分析，不按学历或工资直接分配技能层次。收到executive阶段后改用report_core。',
    parameters:Type.Object({purpose,sections:Type.Array(section)}),
    execute:(id,params,signal,_update,ctx)=>submitPart(id,params,signal,ctx)})
  pi.registerTool({name:'report_core',label:'整理摘要与融合结论',
    promptSnippet:'核心阶段只写三条决策启示、综合启示和研究边界。',
    description:'总体判断与三项结构论证由程序给定。claims按顺序各填implication，三条启示分别回答城市匹配、薪酬预期、方向课程，closing说明实施顺序，研究范围由程序生成。不要出现待核验、待审核、待验证或先核实才能成稿。不改总体判断/标题/事实/分析，不写数字或内部写作提示。',
    parameters:Type.Object({purpose,claims:Type.Array(claim,{minItems:3,maxItems:3}),
      closing:prose(40,'综合三项结论，说明有条件的执行顺序')}),
    execute:(id,params,signal,_update,ctx)=>submitPart(id,{executive:params},signal,ctx)})
  pi.registerTool({name:'report_build',label:'生成并检查报告图片',promptSnippet:'所有批次完成后生成最终图片、参考文献、图片网页与ZIP。',
    description:'在analysis_ready后调用，使用固定代码连续完成真实数据/文案/图表/图片验收与交付。成功后直接结束，不再复述统计数字。',
    parameters:Type.Object({purpose}),execute:(_id,_params,signal,_update,ctx)=>serial(async()=>{
      if(!reportDataReady(ctx.cwd))throw new Error('本次范围数据尚未就绪，请先report_next并按模板取数，不能构建旧范围报告')
      try {
        const output=await invoke(ctx,'build',[],signal)
        return {content:[{type:'text',text:output}],details:{status:'images_built'},terminate:true}
      } catch(error) {
        return {content:[{type:'text',text:'构建未完成，数据和文案已保留。不得连续重试同一错误：'+error.message}],details:{status:'build_failed'},terminate:true}
      }
    })})
  pi.on('before_agent_start',(_event,ctx)=>{
    if(!baseTools)baseTools=pi.getActiveTools()
    if(!baseThinking)baseThinking=pi.getThinkingLevel()
    const task=reportTask(ctx.cwd)
    if(task?.runId!==runId){runId=task?.runId;requests=0;current=undefined}
    if(active(ctx)){pi.setThinkingLevel(actionThinking);setStage('next')}
    else {pi.setActiveTools(baseTools);pi.setThinkingLevel(baseThinking)}
  })
  pi.on('tool_result',(_event,ctx)=>{
    if(!active(ctx))return
    if(reportBuildReady(ctx.cwd,reportTask(ctx.cwd))) {pi.setActiveTools([]);return}
    if(!current) {pi.setThinkingLevel(actionThinking);setStage('next')}
  })
  pi.on('before_provider_request',(event,ctx)=>{
    if(!active(ctx))return
    const task=reportTask(ctx.cwd)
    if(reportBuildReady(ctx.cwd,task)) {
      pi.setActiveTools([])
      const complete={...event.payload,tool_choice:'none'};delete complete.tools
      return complete
    }
    requests++
    const payload=event.payload
    // No more tools after the bound. The server then reports a truthful failure
    // if the agent has still produced no valid deliverable.
    if(requests>18 && payload && typeof payload==='object') {
      pi.setActiveTools([])
      const stopped={...payload,tool_choice:'none'};delete stopped.tools
      return stopped
    }
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
    const meta=JSON.parse(readFileSync(join(ctx.cwd,'wechat-report/report_data.json'),'utf8')).meta
    const compact=compactReportContext({...payload,tools,tool_choice:'required'},current,task,{region:meta.region,industry:meta.industry,audience:meta.audience,filters:meta.filters})
    appendFileSync(join(ctx.cwd,'report-tool-contract.jsonl'),JSON.stringify({runId,request:requests,task:current?.part?.task??current?.status??'start',
      names:tools.map(tool=>tool.function?.name??tool.name),required:tools.map(tool=>(tool.function?.parameters??tool.parameters)?.required),toolChoice:'required',context:compact.metrics})+'\n')
    return compact.payload
  })
}
