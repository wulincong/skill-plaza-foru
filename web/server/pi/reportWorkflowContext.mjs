/** Limit provider context only inside the data-ready, tool-constrained report phase.
 * Persisted Pi history is unchanged. Keep all system rules, current user intent,
 * verified scope, exact current task and the latest in-turn correction.
 */
const textOf=content=>typeof content==='string'?content:Array.isArray(content)?content.filter(part=>part?.type==='text').map(part=>part.text??'').join('\n'):''
const size=messages=>messages.reduce((sum,message)=>sum+JSON.stringify(message).length,0)

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
  '\n'+(current?'当前受信任务（事实与分析只读，按当前工具提交）：'+JSON.stringify(current):'本轮范围数据已就绪，先调用report_next读取任务。')+
  (correction?'\n最近工具返回的纠错信息：'+correction:'')
 const content=Array.isArray(user.content)?[...user.content,{type:'text',text:context}]:textOf(user.content)+'\n\n'+context
 const reduced=[...messages.filter(message=>message.role==='system'||message.role==='developer'),{...user,content}]
 return {payload:{...payload,messages:reduced},metrics:{mode:'current-report-task',originalMessages:messages.length,sentMessages:reduced.length,originalChars:size(messages),sentChars:size(reduced)}}
}
