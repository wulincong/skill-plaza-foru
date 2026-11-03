/** Real HTTP/SSE/history contract, with a deterministic Pi transport (no model calls). */
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtempSync, rmSync, writeFileSync, readdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn } from 'node:child_process'
import { createServer } from 'node:http'

const serverDir = dirname(fileURLToPath(import.meta.url))
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
const fixture = String.raw`#!/usr/bin/env node
import {createInterface} from 'node:readline';
import {mkdirSync,writeFileSync,readFileSync,existsSync,chmodSync} from 'node:fs';
if(process.argv.includes('--version')) {console.log('delivery-test');process.exit(0)}
const [provider,id]=process.argv[process.argv.indexOf('--model')+1].split('/');
let model={provider,id,contextWindow:1000};
const stateFile='.pi-sessions/fixture.json';
let saved=process.argv.includes('--continue')&&existsSync(stateFile)?JSON.parse(readFileSync(stateFile,'utf8')):null;
let messages=saved?.messages||[],nativeId=saved?.nativeId||String(Date.now()),last='';
const send=x=>process.stdout.write(JSON.stringify(x)+'\n');
for await(const line of createInterface({input:process.stdin})) {
 const c=JSON.parse(line); let data={};
 if(c.type==='get_state')data={sessionId:nativeId,messageCount:messages.length,model};
 if(c.type==='set_model') {
  if(c.provider==='youcai' && !process.argv.some(a=>a.endsWith('/pi/youcai.js'))) throw Error('youcai extension missing');
  model={provider:c.provider,id:c.modelId,contextWindow:2000};data=model;
 }
 if(c.type==='get_messages')data={messages};
 if(c.type==='get_last_assistant_text')data={text:last};
 if(c.type==='prompt') {
  messages.push({role:'user',content:[{type:'text',text:c.message}]});
  if(!c.message.includes('follow-up')) {
   mkdirSync('output/public/site',{recursive:true});
   writeFileSync('output/public/site/index.html','<!doctype html><html><head><title>Delivery browser test</title><link rel="stylesheet" href="style.css"></head><body><img src="image.svg"><script src="script.js"></script></body></html>');
   writeFileSync('output/public/site/style.css','body{color:rgb(12,34,56)}');
   writeFileSync('output/public/site/image.svg','<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"/>');
   writeFileSync('output/public/site/data.json','{"value":42}');
   writeFileSync('output/public/site/script.js',"addEventListener('load',async()=>{const d=document.body.dataset;d.image=String(document.querySelector('img').naturalWidth);d.color=getComputedStyle(document.body).color;try{localStorage.getItem('test');d.storage='leaked'}catch{d.storage='blocked'}try{d.data=String((await(await fetch('data.json')).json()).value)}catch{d.data='failed'}try{await fetch('/api/health');d.api='leaked'}catch{d.api='blocked'}d.complete='true'})");
   writeFileSync('output/public/report.zip','test archive');
   if(existsSync('delivery.json'))chmodSync('delivery.json',0o640);
   writeFileSync('delivery.json',JSON.stringify({web:[{name:'测试网页',directory:'output/public/site',entry:'index.html'}],files:[{name:'测试交付包',path:c.message.includes('invalid')?'missing.zip':'output/public/report.zip'}]}));
   if(c.message.includes('unreadable'))chmodSync('delivery.json',0);
  }
  last='完成';messages.push({role:'assistant',content:[{type:'text',text:last}]});
  mkdirSync('.pi-sessions',{recursive:true});writeFileSync(stateFile,JSON.stringify({messages,nativeId}));
 }
 send({type:'response',id:c.id,command:c.type,success:true,data});
 if(c.type==='prompt') {send({type:'agent_start'});send({type:'message_start',message:{role:'assistant'}});send({type:'message_update',assistantMessageEvent:{type:'text_delta',delta:last}});send({type:'message_end',message:messages.at(-1)});send({type:'agent_settled'})}
}
`

test('HTTP delivery, SSE, follow-up history, browser isolation and restart', { timeout: 60000 }, async t => {
  const temp = mkdtempSync(join(tmpdir(), 'plaza-delivery-api-'))
  t.after(() => rmSync(temp, { recursive: true, force: true }))
  const cli = join(temp, 'pi.mjs'), store = join(temp, 'deliveries')
  writeFileSync(cli, fixture, { mode: 0o755 })
  const probe = createServer()
  await new Promise(resolve => probe.listen(0, '127.0.0.1', resolve))
  const port = probe.address().port
  await new Promise(resolve => probe.close(resolve))
  const base = `http://127.0.0.1:${port}`
  let child, logs = '', sessionId
  const stop = async () => { if (!child || child.exitCode !== null) return; const stopped = new Promise(resolve => child.once('exit', resolve)); child.kill(); await stopped }
  t.after(stop)
  const start = async () => {
    child = spawn(process.execPath, [join(serverDir, 'index.ts')], {
      cwd: dirname(serverDir), env: { ...process.env, PORT: String(port), PI_MODEL: 'deepseek/deepseek-v4-pro', PI_CLI: cli, PI_SANDBOX_USER: '', PI_IDLE_MS: '1000', DELIVERY_PUBLIC_BASE_URL: base, DELIVERIES_DIR: store, TRACES_DIR: join(temp, 'traces') },
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    child.stdout.on('data', d => { logs += d }); child.stderr.on('data', d => { logs += d })
    for (let i = 0; i < 100; i++) {
      if (child.exitCode !== null) throw new Error(logs)
      if (await fetch(base + '/api/health').then(r => r.ok).catch(() => false)) return
      await pause(30)
    }
    throw new Error('server not ready: ' + logs)
  }
  await start()
  const request = async (message, protocol = 'plaza', stream = true, history = [], model) => {
    const response = await fetch(base + (protocol === 'plaza' ? '/api/chat' : '/v1/chat/completions'), {
      method: 'POST', headers: { 'Content-Type': 'application/json', Origin: base },
      body: JSON.stringify({ skill: 'general', messages: [...history, { role: 'user', content: message }], sessionId, stream, model }),
    })
    const body = await response.text()
    if (!stream && protocol === 'openai') return JSON.parse(body)
    const frames = body.split('\n').filter(l => l.startsWith('data: {')).map(l => JSON.parse(l.slice(6)))
    sessionId ||= frames.find(f => f.type === 'session')?.sessionId
    assert(!frames.some(f => f.type === 'error'), body)
    return frames.findLast(f => f.type === 'done' || f.webLinks)
  }
  const health = await fetch(base + '/api/health').then(r => r.json())
  assert.deepEqual(health.chatModels.map(m => m.id), ['deepseek-flash', 'deepseek-pro', 'youcai'])
  assert.equal(health.defaultChatModel, 'deepseek-pro')
  const invalidModel = await fetch(base + '/api/chat', { method: 'POST', body: JSON.stringify({ skill: 'general', model: 'unknown' }) })
  assert.equal(invalidModel.status, 400)
  const done = await request('generate', 'plaza', true, [], 'deepseek')
  assert(done?.webLinks?.length, JSON.stringify(done) + logs)
  const url = done.webLinks[0].url
  assert.equal((await fetch(url)).status, 200)
  const download = await fetch(done.downloads[0].url)
  assert.match(download.headers.get('content-disposition'), /^attachment;/)
  assert.equal(await download.text(), 'test archive')

  const followUp = await request('follow-up', 'plaza', true, [], 'youcai')
  assert.equal(followUp.webLinks, undefined)
  let detail
  for (let i = 0; i < 100; i++) {
    detail = await fetch(base + '/api/runs/' + followUp.runId).then(r => r.json())
    if (detail.conversation) break
    await pause(20)
  }
  assert.deepEqual(detail.conversation.filter(t => t.role === 'assistant').map(t => t.provider), ['deepseek', 'youcai'])
  assert.equal(detail.conversation[3].durationMs, followUp.durationMs)
  assert.equal(detail.item.durationMs, followUp.durationMs)
  assert.equal(detail.conversation[1].model, 'deepseek-v4-pro')
  assert.equal(detail.item.tokenUsage.provider, 'youcai')
  assert.equal(detail.item.agentEnv.model, 'youcai/youcai')
  assert.equal(detail.item.tokenUsage.contextWindowTokens, 2000)
  assert.equal(detail.conversation[1].webLinks[0].url, url)
  assert.equal(detail.conversation[3].webLinks, undefined)

  await stop(); await start()
  await request('follow-up after restart', 'openai', false, [{ role: 'user', content: 'generate' }, { role: 'assistant', content: '完成' }])
  for (let i = 0; i < 100; i++) {
    const runs = await fetch(base + '/api/runs').then(r => r.json())
    const resumed = runs.runs.find(run => run.userMessage === 'follow-up after restart')
    if (!resumed) { await pause(20); continue }
    detail = await fetch(base + '/api/runs/' + resumed.runId).then(r => r.json())
    if (detail.item?.files?.trace) break
    await pause(20)
  }
  assert.equal(detail.trace.messages.filter(m => m.role === 'user').length, 3, 'engine must resume persisted context')
  assert.equal(detail.trace.messages.filter(m => m.role === 'user').at(-1).parts[0].text, 'follow-up after restart', 'a resumed context must not receive duplicate flattened history')
  assert.equal(detail.conversation.length, 6, 'resumed cumulative snapshots must not duplicate history')
  assert.equal(detail.conversation[1].webLinks[0].url, url)

  // Legacy resets can start a different native session in the same conversation.
  await stop()
  rmSync(join(serverDir, 'workspace', sessionId, '.pi-sessions'), { recursive: true, force: true })
  await start()
  await request('follow-up with reset engine', 'openai', false, [{ role: 'user', content: 'original user context' }, { role: 'assistant', content: 'original answer context' }])
  for (let i = 0; i < 100; i++) {
    const runs = await fetch(base + '/api/runs').then(r => r.json())
    const reset = runs.runs.find(run => run.userMessage === 'follow-up with reset engine')
    if (!reset) { await pause(20); continue }
    detail = await fetch(base + '/api/runs/' + reset.runId).then(r => r.json())
    if (detail.item?.files?.trace) break
    await pause(20)
  }
  assert.equal(detail.trace.messages.filter(m => m.role === 'user').length, 1)
  assert.match(detail.trace.messages.find(m => m.role === 'user').parts[0].text, /【对话历史】.*用户：original user context[\s\S]*【当前消息】\nfollow-up with reset engine/s)
  assert.equal(detail.conversation.at(-2).text, 'follow-up with reset engine', 'the injected history must stay out of the user bubble')
  assert.equal(detail.conversation.length, 8, 'history must retain both old and new engine sessions')
  assert.equal(detail.conversation[1].downloads[0].url, done.downloads[0].url)

  // Chrome is optional in CI; installed on the Linux deployment used for acceptance.
  if (process.env.DELIVERY_BROWSER) {
    const browser = spawn(process.env.DELIVERY_BROWSER, ['--headless', '--no-sandbox', '--disable-gpu', '--no-proxy-server', '--disable-dev-shm-usage', '--user-data-dir=' + join(temp, 'chrome'), '--dump-dom', '--virtual-time-budget=5000', url])
    let dom = '', errors = ''
    browser.stdout.on('data', d => { dom += d }); browser.stderr.on('data', d => { errors += d })
    assert.equal(await new Promise(resolve => browser.once('exit', resolve)), 0, errors)
    assert.match(dom, /data-complete="true"/, dom + errors)
    assert.match(dom, /data-image="2"/, dom)
    assert.match(dom, /data-data="42"/, dom + errors)
    assert.match(dom, /data-color="rgb\(12, 34, 56\)"/, dom)
    assert.match(dom, /data-storage="blocked"/, dom)
    assert.match(dom, /data-api="blocked"/, dom)
  }
  const json = await request('generate', 'openai', false)
  assert.equal(json.webLinks.length, 1)
  const streaming = await request('generate', 'openai', true)
  assert.equal(streaming.downloads.length, 1)
  const failed = await request('invalid')
  assert.match(failed.content, /产物交付失败/)
  assert.equal(failed.webLinks, undefined)
  if (process.getuid?.() !== 0) {
    const denied = await request('unreadable')
    assert.match(denied.content, /产物交付失败.*无法读取 delivery.json/)
    assert.equal(denied.downloads, undefined)
  }
  assert.equal(readdirSync(store).filter(s => !s.startsWith('.')).length, 3)
  rmSync(join(serverDir, 'workspace', sessionId), { recursive: true, force: true })
  await stop(); await start()
  assert.equal((await fetch(url)).status, 200)
})
