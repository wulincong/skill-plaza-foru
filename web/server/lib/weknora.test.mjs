import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createServer } from 'node:http'
import { createKnowledgeService, openKnowledgeRelay } from './weknora.ts'

const listen = server => new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve(`http://127.0.0.1:${server.address().port}`)))
test('limited relay rejects unknown routes, cross-library requests and invalid IDs without exposing keys', async t => {
  const dir = mkdtempSync(join(tmpdir(), 'weknora-'))
  t.after(() => rmSync(dir, {recursive:true,force:true}))
  let calls = 0
  const service = createKnowledgeService({ key:'hidden-key', kbIds:['kb'], storeDir:dir, publicBase:'http://example.test',
    execute:async () => { calls++; return {status:'empty',items:[]} } })
  const relay = await openKnowledgeRelay(undefined, service)
  t.after(() => relay.close())
  assert.equal((await fetch(relay.url + '/other', {method:'POST',body:'{}'})).status,404)
  for (const body of [{operation:'search',kb:'other',query:'x'},{operation:'chunks',kb:'kb',document:'../secret'}, {operation:'documents',kb:'kb',page:0}]) {
    const r=await fetch(relay.url,{method:'POST',body:JSON.stringify(body)})
    assert.equal(r.ok,false)
    assert.equal((await r.text()).includes('hidden-key'),false)
  }
  assert.equal(calls,0)
  const r=await fetch(relay.url,{method:'POST',body:JSON.stringify({operation:'search',kb:'kb',query:'topic'})})
  assert.equal((await r.json()).status,'empty')
  assert.equal(calls,1)
})

test('category documents mint persistent per-document links; source authentication stays on server', async t => {
  const dir=mkdtempSync(join(tmpdir(),'materials-'))
  t.after(()=>rmSync(dir,{recursive:true,force:true}))
  const seen=[]
  const options={key:'private-key',kbIds:['kb'],storeDir:dir,publicBase:'http://example.test',
    execute:async()=>({status:'ok',items:[{id:'doc',knowledge_base_id:'kb',tag_id:'course',title:'课程.docx'}]}),
    fetchImpl:async(url,init)=>{seen.push({url,headers:init.headers});if(url.endsWith('/knowledge/doc'))return Response.json({success:true,data:{id:'doc',knowledge_base_id:'kb'}});return new Response('file-content',{headers:{'content-type':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}})}}
  const service=createKnowledgeService(options)
  const result=await service.execute({operation:'documents',kb:'kb',tag:'course'})
  const link=result.items[0].preview_url
  assert.match(link,/http:\/\/example.test\/api\/learning-materials\/[a-f0-9]{48}\/preview/)
  assert.equal(JSON.stringify(result).includes('private-key'),false)
  const afterRestart=createKnowledgeService(options)
  const server=createServer((req,res)=>{if(!afterRestart.handleMaterial(req,res))res.writeHead(404).end()})
  const base=await listen(server)
  t.after(()=>{server.close();server.closeAllConnections()})
  const url=base+new URL(link).pathname
  const response=await fetch(url)
  assert.equal(response.status,200)
  assert.equal(await response.text(),'file-content')
  assert.match(response.headers.get('content-disposition'),/^attachment/)
  assert.equal(seen[0].headers['X-API-Key'],'private-key')
  assert.equal((await fetch(url,{method:'POST'})).status,405)
  assert.equal((await fetch(base+'/api/learning-materials/'+'0'.repeat(48)+'/preview')).status,404)
  assert.equal((await fetch(base+'/api/learning-materials/invalid/preview')).status,404)
})

test('wrong-library upstream rows never receive document grants; service errors are sanitized', async t=>{
  const dir=mkdtempSync(join(tmpdir(),'scope-'));t.after(()=>rmSync(dir,{recursive:true,force:true}))
  const common={key:'secret',kbIds:['kb'],storeDir:dir,publicBase:'http://example.test'}
  const service=createKnowledgeService({...common,execute:async()=>({status:'ok',items:[{id:'doc',knowledge_base_id:'other'}]})})
  await assert.rejects(()=>service.execute({operation:'documents',kb:'kb'}),/范围/)
  const broken=createKnowledgeService({...common,execute:async()=>{throw new Error('secret')}})
  const relay=await openKnowledgeRelay(undefined,broken);t.after(()=>relay.close())
  const response=await fetch(relay.url,{method:'POST',body:JSON.stringify({operation:'tags',kb:'kb'})})
  assert.equal(response.status,502)
  assert.equal((await response.text()).includes('secret'),false)
})

test('learning tool hook prevents rebuilding receipts and writing into skill installation',async()=>{
  const {blockedLearningCall}=await import('../../../.agents/skills/weknora-retrieval/scripts/pi-tools.mjs')
  assert.ok(blockedLearningCall({toolName:'write',input:{path:'/repo/.agents/skills/student-learning/.weknora-evidence.jsonl'}},'/tmp/work'))
  assert.ok(blockedLearningCall({toolName:'write',input:{path:'.weknora-evidence.jsonl'}},'/tmp/work'))
  assert.ok(blockedLearningCall({toolName:'bash',input:{command:'echo fake > .weknora-evidence.jsonl'}},'/tmp/work'))
  assert.equal(blockedLearningCall({toolName:'write',input:{path:'learning-plan.json'}},'/tmp/work'),undefined)
  assert.equal(blockedLearningCall({toolName:'bash',input:{command:'python3 /repo/.agents/skills/student-learning/scripts/build.py /tmp/work/learning-plan.json'}},'/tmp/work'),undefined)
})

test('missing configuration fails closed and upstream failures do not echo credentials',async t=>{
  assert.throws(()=>createKnowledgeService({key:'',kbIds:['kb'],storeDir:'/tmp/unused',publicBase:'http://example.test'}),/配置/)
  const dir=mkdtempSync(join(tmpdir(),'denied-material-'));t.after(()=>rmSync(dir,{recursive:true,force:true}))
  const service=createKnowledgeService({key:'must-not-escape',kbIds:['kb'],storeDir:dir,publicBase:'http://example.test',
    execute:async()=>({status:'ok',items:[{id:'doc',knowledge_base_id:'kb',title:'book'}]}),
    fetchImpl:async()=>new Response('must-not-escape',{status:403})})
  const result=await service.execute({operation:'documents',kb:'kb'})
  const server=createServer((req,res)=>service.handleMaterial(req,res))
  const base=await listen(server);t.after(()=>{server.close();server.closeAllConnections()})
  const response=await fetch(base+new URL(result.items[0].preview_url).pathname)
  assert.equal(response.status,403)
  assert.equal((await response.text()).includes('must-not-escape'),false)
})


test('moving a document out of the granted library revokes its old material link',async t=>{
  const dir=mkdtempSync(join(tmpdir(),'moved-material-'));t.after(()=>rmSync(dir,{recursive:true,force:true}))
  let downloads=0
  const service=createKnowledgeService({key:'private',kbIds:['kb'],storeDir:dir,publicBase:'http://example.test',
    execute:async()=>({status:'ok',items:[{id:'doc',knowledge_base_id:'kb',title:'book'}]}),
    fetchImpl:async url=>{if(url.endsWith('/knowledge/doc'))return Response.json({success:true,data:{id:'doc',knowledge_base_id:'another-library'}});downloads++;return new Response('private-content')}})
  const result=await service.execute({operation:'documents',kb:'kb'})
  const server=createServer((req,res)=>service.handleMaterial(req,res));const base=await listen(server)
  t.after(()=>{server.close();server.closeAllConnections()})
  const response=await fetch(base+new URL(result.items[0].preview_url).pathname)
  assert.equal(response.status,403)
  assert.equal(downloads,0)
})
