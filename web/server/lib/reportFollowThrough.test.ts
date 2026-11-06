import test from 'node:test'
import assert from 'node:assert/strict'
import {needsReportFollowThrough,omitReportContinuations,continuationMarker,sumUsage,reportRequested} from './reportFollowThrough.ts'

test('a report plan alone is continued, with a strict bound and no forced clarification',()=>{
  const base={skill:'wechat-report',request:'请完成广东人工智能报告',answer:'现在我将生成报告',hasDelivery:false,hasQuestion:false,attempts:0}
  assert(needsReportFollowThrough(base))
  for(const extra of [{hasDelivery:true},{hasQuestion:true},{attempts:2},{skill:'general'},{request:'报告是什么意思'},{answer:'请提供需要分析的地区和产业'}])
    assert(!needsReportFollowThrough({...base,...extra}))
})
test('internal continuations do not shift original conversation run mapping',()=>{
  const internal=continuationMarker('r1')+' continue'
  const trace={messages:[{role:'user',content:'真实要求'},{role:'assistant',content:'计划'},{role:'user',content:internal},{role:'assistant',content:'完成'}]}
  const cleaned=omitReportContinuations(trace,[{runId:'r1',reportContinuations:1}])
  assert.deepEqual(cleaned.messages.filter((m:any)=>m.role==='user').map((m:any)=>m.content),['真实要求'])
  assert.equal(omitReportContinuations(trace,[{runId:'other',reportContinuations:1}]).messages.length,4)
  assert.deepEqual(sumUsage({inputTokens:10,outputTokens:2,totalTokens:12,costUsd:0},{inputTokens:20,outputTokens:3,totalTokens:23,costUsd:0}),{inputTokens:30,outputTokens:5,totalTokens:35,costUsd:0})
})

test('natural report intent does not depend on help-me-generate or talent-report words',()=>{
 for(const text of ['广州AI报告','来一份广州人工智能报告','想看看山东机器人行业的人才需求','想看看深圳半导体的招聘情况，只看大专学历'])assert.equal(reportRequested(text),true,text)
 for(const text of ['AI是什么','报告怎么生成','不要生成广州人工智能报告'])assert.equal(reportRequested(text),false,text)
})
