import test from 'node:test'
import assert from 'node:assert/strict'
import {compactReportContext} from './reportWorkflowContext.mjs'

test('data-ready report context retains rules, latest intent, scope and exact task without growing history',()=>{
 const current={status:'writing_required',part:{task:'sections:salary',evidenceHash:'verified',sections:[{key:'salary',findingIds:['salary.quantiles']}]}}
 const payload={messages:[{role:'system',content:'固定规则'},{role:'user',content:'旧请求'},{role:'assistant',content:'旧过程'.repeat(50000)},
  {role:'user',content:'请继续，保留地区和学历'},{role:'assistant',tool_calls:[{id:'call'}]},{role:'tool',tool_call_id:'call',content:JSON.stringify(current)}],tools:[{name:'report_submit'}]}
 const before=structuredClone(payload)
 const {payload:result,metrics}=compactReportContext(payload,current,{requestText:'请继续'},{region:'深圳市',industry:'人工智能',education:['硕士']})
 assert.deepEqual(payload,before)
 assert.deepEqual(result.tools,payload.tools)
 assert.deepEqual(result.messages.map(row=>row.role),['system','user'])
 assert(result.messages[1].content.includes('salary.quantiles'))
 assert(result.messages[1].content.includes('深圳市'))
 assert(result.messages[1].content.includes('保留地区和学历'))
 assert(metrics.sentChars<metrics.originalChars/10)
})

test('latest tool correction and user image parts remain, earlier-turn errors do not leak',()=>{
 const image={type:'image_url',image_url:{url:'data:image/png;base64,test'}}
 const messages=[{role:'system',content:'规则'},{role:'tool',content:'旧错误'},
  {role:'user',content:[{type:'text',text:'修改建议'},image]},{role:'assistant',tool_calls:[{id:'call'}]},
  {role:'tool',tool_call_id:'call',content:'当前批次需要全部章节'}]
 const result=compactReportContext({messages},{status:'writing_required',part:{task:'sections:salary'}},{requestText:'修改建议'},{}).payload
 assert.deepEqual(result.messages[1].content[1],image)
 const text=result.messages[1].content.at(-1).text
 assert(text.includes('当前批次需要全部章节'))
 assert(!text.includes('旧错误'))
})

test('unsupported provider payload stays unchanged',()=>{
 const payload={prompt:'unknown'}
 assert.equal(compactReportContext(payload,undefined,{},{}).payload,payload)
})
