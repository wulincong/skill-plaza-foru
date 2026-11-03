/** Deterministic report-library calls. No model-produced paths or URLs are executed. */
import { spawn } from 'node:child_process'
import { createHmac } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import type { DeliveryLinks } from './delivery.ts'
import type { ChatQuestion } from '../../shared/chatQuestion.ts'

const script = fileURLToPath(new URL('../../../scripts/report_library.py', import.meta.url))
const secretFile = fileURLToPath(new URL('../report-library/bridge.key', import.meta.url))

export interface CatalogReport extends DeliveryLinks {
  id: string; title: string; region: string; industry: string; dataAt: string; pageCount: number;
}
interface CatalogResult { status: string; report?: CatalogReport; reportId?: string; message?: string }
export interface LocalReportReply extends DeliveryLinks {
  content: string; question?: ChatQuestion; reportId?: string; kind: string;
}

export function catalog(action: string, input: object): Promise<CatalogResult> {
  return new Promise((resolve, reject) => {
    const child = spawn(process.env.REPORT_PYTHON || '/usr/bin/python3', ['-B',script,action], {stdio:['pipe','pipe','pipe']})
    child.stdout.setEncoding('utf8'); child.stderr.setEncoding('utf8')
    let stdout = '', stderr = ''
    const timer=setTimeout(()=>{child.kill();reject(new Error('报告库响应超时'))},20_000)
    child.stdout.on('data', b=>{stdout+=b;if(stdout.length>2*1024*1024)child.kill()})
    child.stderr.on('data', b=>{stderr+=b;if(stderr.length>10000)child.kill()})
    child.on('error',error=>{clearTimeout(timer);reject(error)})
    child.on('close', code=>{
      clearTimeout(timer)
      try {const result=JSON.parse(stdout); if(code!==0)reject(new Error(result.message || '报告库校验失败'));else resolve(result)}
      catch {reject(new Error('报告库返回格式错误'))}
    })
    child.stdin.end(JSON.stringify(input))
  })
}

export const saveQuestion = (): ChatQuestion => ({kind:'confirm',question:'是否将这份报告存入公众号后台草稿箱？',options:[{label:'保存到草稿箱'},{label:'暂不保存'}],note:'只存草稿，不群发。'})

export async function saveDraft(sessionId: string, reportId: string): Promise<{state:string;message:string}> {
  const timestamp=String(Math.floor(Date.now()/1000))
  const body=JSON.stringify({sessionId,reportId})
  const signature=createHmac('sha256',readFileSync(secretFile)).update(timestamp+'\n'+body).digest('hex')
  const response=await fetch(process.env.REPORT_DRAFT_BRIDGE || 'http://127.0.0.1:8080/internal/reports/draft',{
    method:'POST',headers:{'Content-Type':'application/json','X-Report-Time':timestamp,'X-Report-Signature':signature},
    body,signal:AbortSignal.timeout(120_000),
  })
  const result=await response.json() as any
  if(!response.ok || result.state==='failed')throw new Error(result.message || '公众号草稿保存失败')
  return result
}

export async function localReportReply(sessionId: string, skill: string, text: string, attachments=false): Promise<LocalReportReply | undefined> {
  if(!['wechat-report','general'].includes(skill) || attachments)return
  let consent: CatalogResult
  try {consent=await catalog('consent',{sessionId,text})}
  catch {
    if (/草稿|^(?:确定|确认|好的|可以|需要|保存)$/.test(text.trim()))
      return {content:'未能核实当前成品版本，尚未执行保存草稿。报告仍然保留，请稍后重试。',kind:'draft-failed'}
    return
  }
  if(consent.status==='declined')return {content:'好的，这份报告暂不保存到公众号草稿箱。',kind:'declined'}
  if(consent.status==='confirmed' && consent.reportId){
    try {
      const result=await saveDraft(sessionId,consent.reportId)
      return {content:result.message,reportId:consent.reportId,kind:'draft'}
    }catch(error){
      return {content:'草稿尚未保存：'+(error instanceof Error?error.message:'公众号接口暂不可用')+'。报告成品仍然保留，可稍后重试。',reportId:consent.reportId,kind:'draft-failed'}
    }
  }
  if (/草稿/.test(text)) return {content:'请先在当前对话生成或打开需要保存的报告，再明确回复“保存到草稿箱”。确认后会将文字总结放在前面、报告图片放在后面存入公众号草稿箱。',kind:'draft-guidance'}
  const found=await catalog('lookup',{sessionId,text})
  if(found.status!=='hit' || !found.report)return
  const report=found.report
  const date=new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',dateStyle:'medium'}).format(new Date(report.dataAt))
  return {content:`已找到同范围的报告，共${report.pageCount}张图片，数据读取于${date}。`,question:saveQuestion(),
          webLinks:report.webLinks,downloads:report.downloads,reportId:report.id,kind:'cache'}
}

export async function registerReport(input: {workspace:string;sessionId:string;runId:string} & DeliveryLinks): Promise<CatalogReport | undefined> {
  const result=await catalog('register',input)
  return result.status==='ready'?result.report:undefined
}
