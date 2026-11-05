/** Limit provider context only inside the data-ready, tool-constrained report phase.
 * Persisted Pi history is unchanged. Keep all system rules, current user intent,
 * verified scope, exact current task and the latest in-turn correction.
 */
const textOf=content=>typeof content==='string'?content:Array.isArray(content)?content.filter(part=>part?.type==='text').map(part=>part.text??'').join('\n'):''
const size=messages=>messages.reduce((sum,message)=>sum+JSON.stringify(message).length,0)


export function writingView(current) {
 if(!current || current.status!=='writing_required')return current
 const result=structuredClone(current)
 // Tool assembly uses the authoritative original task. The writer needs readable
 // evidence and templates, not repeated source-path and metric-binding arrays.
 if(Array.isArray(result.evidence))result.evidence=result.evidence.map(group=>Array.isArray(group)?group.map(fact=>({text:fact.text})): {...group,facts:group.facts?.map(fact=>({text:fact.text}))})
 if(result.part?.sections)result.part.sections=result.part.sections.map(({key,title,interpretation})=>({key,title,interpretation}))
 if(result.part?.executive)result.part.executive={opening:result.part.executive.opening,claims:result.part.executive.claims.map(({title,interpretation})=>({title,interpretation}))}
 if(result.part)for(const key of ['evidenceHash','schema','reasoningPolicy'])delete result.part[key]
 if(result.officialRegionalEvidence)result.officialRegionalEvidence.sources=result.officialRegionalEvidence.sources.map(({title,period,kind,facts,applicationFocus})=>({title,period,kind,facts,applicationFocus}))
 return result
}

export function compactReportContext(payload,current,task,scope) {
 if(!Array.isArray(payload.messages))return {payload,metrics:{mode:'unchanged'}}
 const messages=payload.messages
 const lastUser=messages.findLastIndex(message=>message.role==='user')
 const lastTool=messages.findLastIndex(message=>message.role==='tool')
 const user=lastUser>=0?messages[lastUser]:{role:'user',content:task.requestText??''}
 let correction=''
 if(lastTool>lastUser && lastUser>=0) {
  const text=textOf(messages[lastTool].content)
  let sameTask=false
  try {
   const parsed=JSON.parse(text)
   sameTask=Boolean(current && parsed.status===current.status && (parsed.part?.task??null)===(current.part?.task??null))
  } catch {}
  if(!sameTask)correction=text.slice(0,7000)
 }
 const context='【当前报告执行资料】\n当前范围与读者：'+JSON.stringify(scope??{})+
  '\n原始本轮要求：'+(task.requestText??'')+
  (task.originRequestText?'\n发起报告时的用户要求（范围按本轮选择更新）：'+task.originRequestText:'')+
  '\n'+(current?'当前受信任务（事实与分析只读，按当前工具提交）：'+JSON.stringify(writingView(current)):'本轮范围数据已就绪，先调用report_next读取任务。')+
  (correction?'\n最近工具返回的纠错信息：'+correction:'')
 const content=Array.isArray(user.content)?[...user.content,{type:'text',text:context}]:textOf(user.content)+'\n\n'+context
 const reduced=[...messages.filter(message=>message.role==='system'||message.role==='developer'),{...user,content}]
 return {payload:{...payload,messages:reduced},metrics:{mode:'current-report-task',originalMessages:messages.length,sentMessages:reduced.length,originalChars:size(messages),sentChars:size(reduced)}}
}
