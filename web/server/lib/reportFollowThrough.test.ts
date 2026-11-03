import test from 'node:test'
import assert from 'node:assert/strict'
import {needsReportFollowThrough,omitReportContinuations,continuationMarker,sumUsage} from './reportFollowThrough.ts'

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
