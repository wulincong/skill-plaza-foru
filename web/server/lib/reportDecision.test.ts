import test from 'node:test'
import assert from 'node:assert/strict'
import {reportTurnIntent,needsReportFollowThrough} from './reportFollowThrough.ts'

test('an answered scope decision keeps report intent across several clarification turns',()=>{
 const first={runId:'r1',skill:'wechat-report',userMessage:'帮我生成广东省机器人人才需求产业报告',question:{question:'请选择产业范围'}}
 const answer='使用机器人产业 (ID=15) + 自定义分析规则'
 assert.deepEqual(reportTurnIntent(answer,false,[first],'r1'),{enabled:true,originRequestText:first.userMessage})
 const second={runId:'r2',skill:'wechat-report',userMessage:answer,answerTo:'r1',question:{question:'请选择报告读者'}}
 assert.equal(reportTurnIntent('院校专业负责人',false,[first,second],'r2').enabled,true)
 assert.equal(needsReportFollowThrough({skill:'wechat-report',request:answer,answer:'现在开始绘图',hasData:true,hasDelivery:false,hasQuestion:false,attempts:0,requested:true}),true)
 for(const response of ['取消','不需要了','为什么选这个产业','发生什么问题了'])assert.equal(reportTurnIntent(response,true,[first],'r1').enabled,false)
 assert.equal(reportTurnIntent(answer,false,[first]).enabled,false)
 assert.equal(reportTurnIntent(answer,false,[first,second],'r1').enabled,false)
 assert.equal(reportTurnIntent(answer,false,[{...first,skill:'general'}],'r1').enabled,false)
 assert.equal(reportTurnIntent('保存到草稿箱',true,[{...first,question:{question:'是否存入公众号草稿箱？'}}],'r1').enabled,false)
 assert.equal(reportTurnIntent('好的',true,[{...first,userMessage:'报告是什么意思'}],'r1').enabled,false)
})
