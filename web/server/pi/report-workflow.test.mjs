import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtempSync,mkdirSync,writeFileSync,rmSync,existsSync} from 'node:fs'
import {join,dirname} from 'node:path'
import {tmpdir} from 'node:os'
import {createHash} from 'node:crypto'
import {fileURLToPath,pathToFileURL} from 'node:url'
const loader=process.env.PI_EXTENSION_LOADER || join(dirname(process.execPath),'../lib/node_modules/@earendil-works/pi-coding-agent/dist/core/extensions/loader.js')

test('a verified report build closes write tools for the remaining model response',{skip:!existsSync(loader)},async()=>{
 const root=mkdtempSync(join(tmpdir(),'report-complete-'))
 try {
  const folder=join(root,'wechat-report/output/report');mkdirSync(folder,{recursive:true})
  let tools=['read','write','bash']
  const {loadExtensions,createExtensionRuntime}=await import(pathToFileURL(loader).href)
  const runtime={...createExtensionRuntime(),getActiveTools:()=>tools,getThinkingLevel:()=> 'medium',setThinkingLevel(){},setActiveTools(value){tools=value}}
  const loaded=await loadExtensions([fileURLToPath(new URL('./report-workflow.js',import.meta.url))],root,undefined,runtime)
  assert.deepEqual(loaded.errors,[])
  const hooks=Object.fromEntries([...loaded.extensions[0].handlers].map(([name,list])=>[name,list[0]]))
  const ctx={cwd:root,model:{provider:'youcai'}}
  writeFileSync(join(root,'report-turn.json'),JSON.stringify({schema:'plaza-report-turn/1',enabled:true,runId:'test',startedAt:Date.now()-1000,requestText:'广东省机器人报告'}))
  writeFileSync(join(root,'wechat-report/report_data.json'),JSON.stringify({meta:{region:'广东省',industry:'机器人'},city_profiles:[]}))
  hooks.before_agent_start({},ctx)
  assert.deepEqual(tools,['report_next'])
  const manifest=JSON.stringify({pages:[]}),sha=createHash('sha256').update(manifest).digest('hex')
  writeFileSync(join(folder,'manifest.json'),manifest)
  writeFileSync(join(folder,'quality.json'),JSON.stringify({all_pass:true,manifest_sha256:sha}))
  writeFileSync(join(folder,'build_receipt.json'),JSON.stringify({startedAt:new Date().toISOString(),manifestSha256:sha,deliveryManifest:{web:[]}}))
  hooks.tool_result({},ctx)
  assert.deepEqual(tools,[])
  const payload={messages:[],tools:[{name:'write'}],tool_choice:'auto'}
  const response=hooks.before_provider_request({payload},ctx)
  assert.equal(response.tool_choice,'none');assert.equal(response.tools,undefined)
  assert.equal(payload.tools.length,1)
 } finally {rmSync(root,{recursive:true,force:true})}
})
