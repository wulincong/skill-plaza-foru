import test from 'node:test'
import assert from 'node:assert/strict'
import {requestedRegion,exactRegionMatches,turnRegionText,filterIntentProblems} from './report-request.mjs'
test('city request retains level, parent and name, rejects broader province',()=>{
 const actual={level:'city',province:'广东省',name:'广州市'}
 for(const text of ['生成广州的人工智能报告','广东广州人工智能报告','广州AI报告，只看大专学历']) {
  assert.deepEqual(requestedRegion(text).region,actual)
  assert.equal(exactRegionMatches(actual,text),true)
  assert.equal(exactRegionMatches({level:'province',name:'广东省'},text),false)
 }
})
test('ambiguous cities, counties and mismatched province cannot be treated as a whole province',()=>{
 for(const text of ['吉林人工智能报告','广州和深圳AI报告','广州天河区AI报告','山东广州AI报告'])assert.equal(exactRegionMatches({level:'province',name:'广东省'},text),false)
})
test('a follow-up can keep original geography while a real city change replaces it',()=>{
 const turn={requestText:'继续生成',originRequestText:'广州AI报告'}
 assert.equal(turnRegionText(turn),turn.originRequestText)
 assert.equal(requestedRegion('广东报告，改成深圳人工智能报告').region.name,'深圳市')
})

test('an unrequested work-year filter is rejected while the explicit diploma stays',()=>{
 const text='想看看深圳半导体的招聘情况，只看大专学历'
 assert(filterIntentProblems({education:['DAZHUAN'],experience:['GRADUATING']},text).length)
 assert(filterIntentProblems({education:[]},text).length)
 assert.deepEqual(filterIntentProblems({education:['DAZHUAN'],experience:[]},text),[])
 assert.deepEqual(filterIntentProblems({education:['DAZHUAN']},'请继续生成'),[])
})
