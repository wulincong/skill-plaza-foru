import {test} from 'node:test'
import assert from 'node:assert/strict'
import {mkdtempSync,writeFileSync,readFileSync,rmSync} from 'node:fs'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import register, {blockedJobCall} from '../../../.agents/skills/job-matching/scripts/pi-tools.mjs'

test('job source protection permits simple reads but rejects snapshot writes',()=>{
 assert.ok(blockedJobCall({toolName:'write',input:{path:'.job-matching/source.json'}},'/tmp/work'))
 assert.ok(blockedJobCall({toolName:'write',input:{path:'/repo/file'}},'/tmp/work'))
 assert.ok(blockedJobCall({toolName:'bash',input:{command:'echo fake > .job-query-state.json'}},'/tmp/work'))
 assert.equal(blockedJobCall({toolName:'bash',input:{command:'cat .job-matching/source.json'}},'/tmp/work'),undefined)
 assert.equal(blockedJobCall({toolName:'bash',input:{command:'python3 /repo/job-matching/scripts/matching.py build job-assessments.json'}},'/tmp/work'),undefined)
})
test('form query scope cannot be widened and the failure is recorded for this turn',async t=>{
 const root=mkdtempSync(join(tmpdir(),'job-tool-'));t.after(()=>rmSync(root,{recursive:true,force:true}))
 writeFileSync(join(root,'.job-request.json'),JSON.stringify({runId:'r',message:'【岗位接口筛选】\n'+JSON.stringify({keyword:'前端',city:'广州'})}))
 let tool;register({on(){},registerTool(value){tool=value}})
 const result=await tool.execute('id',{filters:{keyword:'前端',city:'深圳'}},undefined,undefined,{cwd:root})
 assert.equal(result.isError,true)
 assert.equal(JSON.parse(readFileSync(join(root,'.job-query-state.json'),'utf8')).status,'error')
 assert.match(result.content[0].text,/范围|条件/)
})
