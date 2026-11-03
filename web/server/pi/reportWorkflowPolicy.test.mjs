import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtempSync,mkdirSync,writeFileSync,rmSync} from 'node:fs'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {createHash} from 'node:crypto'
import {reportTask,reportDataReady,reportBuildReady,reportScopeMatches} from './reportWorkflowPolicy.mjs'

test('only server-enabled report turns activate workflow',()=>{
 const root=mkdtempSync(join(tmpdir(),'report-policy-'))
 try {
  assert.equal(reportTask(root),undefined)
  writeFileSync(join(root,'report-turn.json'),JSON.stringify({schema:'plaza-report-turn/1',enabled:false}))
  assert.equal(reportTask(root),undefined)
  writeFileSync(join(root,'report-turn.json'),JSON.stringify({schema:'plaza-report-turn/1',enabled:true,runId:'run1',startedAt:1}))
  assert.equal(reportTask(root).runId,'run1')
  assert.equal(reportDataReady(root),false)
  mkdirSync(join(root,'wechat-report'));writeFileSync(join(root,'wechat-report/report_data.json'),JSON.stringify({meta:{region:'广东省',industry:'人工智能'}}))
  assert.equal(reportDataReady(root),true)
 } finally {rmSync(root,{recursive:true,force:true})}
})

test('a different region, sector or new filters cannot silently reuse saved aggregates',()=>{
 const root=mkdtempSync(join(tmpdir(),'report-scope-'))
 try {
  mkdirSync(join(root,'wechat-report'))
  const meta={region:'广东省',industry:'人工智能'}
  writeFileSync(join(root,'wechat-report/report_data.json'),JSON.stringify({meta}))
  const task={schema:'plaza-report-turn/1',enabled:true,startedAt:Date.now()+60000}
  const ready=text=>{writeFileSync(join(root,'report-turn.json'),JSON.stringify({...task,requestText:text}));return reportDataReady(root)}
  assert.equal(ready('帮我生成广东省人工智能人才需求报告'),true)
  assert.equal(ready('帮我生成山东省人工智能人才需求报告'),false)
  assert.equal(ready('帮我生成广东省智能制造人才需求报告'),false)
  assert.equal(ready('帮我生成广东省人工智能本科生人才需求报告'),false)
  assert.equal(ready('请继续'),true)
  writeFileSync(join(root,'report-turn.json'),JSON.stringify({...task,revision:true,requestText:'优化核心发现和薪酬图的解释'}))
  assert.equal(reportDataReady(root),true)
  writeFileSync(join(root,'report-turn.json'),JSON.stringify({...task,revision:true,requestText:'改为只看本科岗位，优化报告'}))
  assert.equal(reportDataReady(root),false)
  assert.equal(reportScopeMatches(meta,'广东和山东人工智能对比报告'),false)
 } finally {rmSync(root,{recursive:true,force:true})}
})

test('only a fresh successful build matching final manifest is complete',()=>{
 const root=mkdtempSync(join(tmpdir(),'report-policy-'))
 try {
  const folder=join(root,'wechat-report/output/report');mkdirSync(folder,{recursive:true})
  const task={startedAt:Date.now()-1000}
  const manifest=JSON.stringify({pages:[{file:'page_01.png'}]})
  const sha=createHash('sha256').update(manifest).digest('hex')
  writeFileSync(join(folder,'manifest.json'),manifest)
  writeFileSync(join(folder,'quality.json'),JSON.stringify({all_pass:true,manifest_sha256:sha}))
  writeFileSync(join(root,'delivery.json'),'{}')
  const receipt={startedAt:new Date().toISOString(),manifestSha256:sha}
  writeFileSync(join(folder,'build_receipt.json'),JSON.stringify(receipt))
  assert.equal(reportBuildReady(root,task),true)
  writeFileSync(join(folder,'manifest.json'),'changed')
  assert.equal(reportBuildReady(root,task),false)
  writeFileSync(join(folder,'manifest.json'),manifest)
  writeFileSync(join(folder,'build_receipt.json'),JSON.stringify({...receipt,startedAt:'2000-01-01'}))
  assert.equal(reportBuildReady(root,task),false)
  writeFileSync(join(folder,'build_receipt.json'),JSON.stringify(receipt))
  writeFileSync(join(folder,'quality.json'),JSON.stringify({all_pass:false,manifest_sha256:sha}))
  assert.equal(reportBuildReady(root,task),false)
 } finally {rmSync(root,{recursive:true,force:true})}
})
