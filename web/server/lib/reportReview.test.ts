import test from 'node:test'
import assert from 'node:assert/strict'
import {reviewDelivery,saveQuestion} from './reportLibrary.ts'
import {reportRevisionRequested,reportRequested} from './reportFollowThrough.ts'

test('delivered report has inspectable resources and no premature save question',()=>{
 const report={id:'r1',title:'东莞市人工智能报告',region:'东莞市',industry:'人工智能',dataAt:'2026-11-16',pageCount:14,webLinks:[{name:'图片报告',url:'https://example.test/report'}],downloads:[{name:'图片ZIP',url:'https://example.test/report.zip'}]}
 const delivery=reviewDelivery(report)
 assert.equal(delivery.reportId,'r1')
 assert.deepEqual(delivery.webLinks,report.webLinks)
 assert.deepEqual(delivery.downloads,report.downloads)
 assert.equal(delivery.question,undefined)
 assert.match(delivery.content,/确认报告质量/)
 assert.doesNotMatch(delivery.content,/是否.*草稿/)
 assert.match(saveQuestion().question,/是否.*草稿/)
})

test('natural same-conversation revisions continue generation instead of returning a plan',()=>{
 for(const text of ['改成更简洁的表述','把摘要精简一下','补充学历与经验的解释','删掉重复段落','重新生成报告']) {
  assert.equal(reportRevisionRequested(text),true,text)
  assert.equal(reportRequested(text,true),true,text)
 }
 for(const text of ['不要修改报告','请问怎么修改报告','为什么删除了段落'])assert.equal(reportRevisionRequested(text),false,text)
})
