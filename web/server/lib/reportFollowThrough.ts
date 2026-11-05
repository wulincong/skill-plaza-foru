/** Bounded continuation when a report agent ends with a plan but no deliverable. */
import type { UsageSummary } from './traceExport.ts'

export function reportRevisionRequested(text:string):boolean {
  return /修改|优化|重写|调整|加强|改进|重新生成/.test(text) && !/^(?:请)?(?:不要|别|不用|不需要)|^(?:请问)?(?:如何|怎么|为什么)/.test(text.trim())
}

export function reportRequested(text: string,hasData=false): boolean {
  if (/^(?:请)?(?:不要|别|不用|不需要)(?:再)?(?:生成|修改|优化|制作|重写)/.test(text.trim())) return false
  if (/^(?:请)?继续(?:生成|完成)?[。！!\s]*$/.test(text.trim())) return true
  if (/^(?:请问)?(?:什么是|如何|怎么|为什么|介绍|解释|报告是什么意思)/.test(text.trim())) return false
  return hasData && reportRevisionRequested(text) || /报告|人才需求/.test(text) && /生成|制作|完成|交付|出一份|帮我|修改|重新|继续|优化|加强|调整/.test(text)
}

interface ReportDecisionRun {
  runId: string; skill: string; userMessage?: string; answerTo?: string;
  question?: {question: string};
}

/** Follow only the current session's validated decision chain, never unrelated history. */
export function reportTurnIntent(text:string,hasData:boolean,runs:ReportDecisionRun[],answerTo?:string): {enabled:boolean; originRequestText?:string} {
  if (reportRequested(text,hasData)) return {enabled:true}
  if (/^(?:请)?(?:不要|别|不用|不需要|取消|停止|结束|暂不|算了)|^(?:请问)?(?:如何|怎么|为什么|发生什么|出了什么)/.test(text.trim())) return {enabled:false}
  if (!answerTo || runs.at(-1)?.runId !== answerTo) return {enabled:false}
  let current=runs.at(-1)
  const seen=new Set<string>()
  while(current && !seen.has(current.runId)) {
    seen.add(current.runId)
    if(current.skill!=='wechat-report' || !current.question || /草稿/.test(current.question.question)) return {enabled:false}
    if(current.userMessage && reportRequested(current.userMessage,hasData)) return {enabled:true,originRequestText:current.userMessage}
    current=current.answerTo ? runs.find(run=>run.runId===current!.answerTo) : undefined
  }
  return {enabled:false}
}

export const reportScopeQuestion=(answer:string):boolean=>/请(?:提供|说明|告诉我|明确).*(?:地区|地域|省份|行业|产业)|希望(?:分析|研究).*(?:地区|行业)|(?:哪个|哪些|什么|何种).*(?:地区|地域|省份|行业|产业)/.test(answer)

export function needsReportFollowThrough(input: {skill:string;request:string;answer:string;hasDelivery:boolean;hasQuestion:boolean;hasData?:boolean;attempts:number;requested?:boolean}): boolean {
  if(input.skill!=='wechat-report'||!(input.requested ?? reportRequested(input.request,input.hasData))||input.hasDelivery||input.hasQuestion||input.attempts>=2)return false
  return Boolean(input.hasData)||!reportScopeQuestion(input.answer)
}

export function sumUsage(a: UsageSummary | undefined,b: UsageSummary | undefined): UsageSummary | undefined {
  if(!a)return b
  if(!b)return a
  const out: UsageSummary={}
  for(const key of ['inputTokens','outputTokens','cacheReadTokens','totalTokens','costUsd'] as const)
    if(a[key]!==undefined||b[key]!==undefined)out[key]=(a[key]??0)+(b[key]??0)
  return out
}

export function continuationMarker(runId:string):string {return `[plaza:report-continue:${runId}]`}

export function reportRuntimeHint(installed:string,workspace:string,hasData:boolean):string {
  const q=(value:string)=>"'"+value.replaceAll("'","'\\''")+"'"
  const directory=workspace+'/wechat-report'
  const command=`${q(installed+'/.venv/bin/python')} ${q(installed+'/scripts/report.py')} --workdir ${q(directory)}`
  return `\n\n【平台报告执行环境】\n受信数据目录：${directory}。不要复制或修改Python脚本，不修补BASE。\n${hasData?'已有数据只用于同范围续写或修订；先核对地区、产业和筛选口径，改变范围必须重新准备plan并取数。':'尚未取数时先运行 '+command+' init；按技能准备plan.json后，在该数据目录运行安装目录collect_data.mjs。'}\n有report_next/report_submit/report_core/report_build专用工具时必须优先调用：report_next读取任务→report_submit填写章节行动、验证与调整条件→report_core提交三条决策启示、综合启示和局限→analysis_ready后report_build。标题、事实选择、总体判断和结构分析由程序按当前数据计算，不改写这些受信字段。程序负责保存与绑定，无需文件工具。\n文案完全不含阿拉伯数字；程序会展开findingIds事实。解释指标之间的关系，行动明确对象/任务/产出，decisionRule说明哪些复核结果会改变建议；不能仅据高薪建议扩招。\n仅无专用工具时使用受信CLI：${command} next，再填写 ${directory}/report_part.json，用 ${command} accept report_part.json提交；analysis_ready后运行 ${command} build。\n不得以计划或承诺结束，不请求大纲确认。`
}

export function omitReportContinuations(trace:any,runs:Array<{runId:string;reportContinuations?:number}>):any {
  if(!Array.isArray(trace?.messages))return trace
  const markers=runs.filter(run=>run.reportContinuations).map(run=>continuationMarker(run.runId))
  if(!markers.length)return trace
  return {...trace,messages:trace.messages.filter((message:any)=>{
    if(message?.role!=='user')return true
    const content = message.content ?? message.parts
    const text = typeof content === 'string' ? content :
      Array.isArray(content) ? content.map((part: any) => part?.text ?? '').join('') : ''
    return !markers.some(marker=>text.startsWith(marker))
  })}
}
