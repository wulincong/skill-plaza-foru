/** Real HTTP/SSE/history contract, with a deterministic Pi transport (no model calls). */
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { randomBytes } from 'node:crypto'
import { appendFileSync, mkdtempSync, rmSync, readFileSync, writeFileSync, readdirSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn, execFileSync } from 'node:child_process'
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
 if(c.type==='get_state' && process.cwd().endsWith('-early')) await new Promise(resolve=>setTimeout(resolve,120));
 if(c.type==='get_state')data={sessionId:nativeId,messageCount:messages.length,model};
 if(c.type==='set_model') {
  if(c.provider==='youcai' && !process.argv.some(a=>a.endsWith('/pi/youcai.js'))) throw Error('youcai extension missing');
  model={provider:c.provider,id:c.modelId,contextWindow:2000};data=model;
 }
 if(c.type==='get_messages')data={messages};
 if(c.type==='get_last_assistant_text')data={text:last};
 if(c.type==='prompt') {
  messages.push({role:'user',content:[{type:'text',text:c.message}]});
  if(c.message.includes('hold-for-refresh') && !c.message.includes('原始任务：')) {
   writeFileSync('checkpoint.txt','partial');
   send({type:'response',id:c.id,command:c.type,success:true,data});
   continue;
  }
  const emptyBuild=messages.some(m=>m.role==='user' && m.content[0].text.includes('empty-industry-fixture'));
  if(!c.message.includes('follow-up') && !emptyBuild) {
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
  last='完成';
  if(c.message.includes('follow-up ask-fixture') && c.message.includes('【在线对话提问约定】')) {
   const kind=c.message.match(/ask-fixture-(confirm|multiple|single|input)/)?.[1] || 'single';
   const question={kind,question:'怎样继续分析？',options:kind==='input'?[]:[{label:'大专经验不限',description:'54 条'},{label:'宽口径'}]};
   const fence=String.fromCharCode(96).repeat(3);
   last='已核对样本。'+String.fromCharCode(10,10)+fence+'plaza-question'+String.fromCharCode(10)+JSON.stringify(question)+String.fromCharCode(10)+fence;
  }
  if (emptyBuild) {
    last=c.message.startsWith('[plaza:report-continue:') ? '没有生成文件，构建未成功。' : '已完成报告。';
  }
  if (c.message.includes('broken-evidence-menu-fixture')) {
    const fence=String.fromCharCode(96).repeat(3),nl=String.fromCharCode(10);
    last=['已完成企业访谈摘录，缺少校内材料。请选择。',fence+'plaza-question',
      '{"kind":"single","question":"请选择","options":[{"label":"补充材料"},{"label":"扩大范围"},{"label":"按现有证据继续"}}]',fence].join(nl);
  }
  messages.push({role:'assistant',content:[{type:'text',text:last}]});
  mkdirSync('.pi-sessions',{recursive:true});writeFileSync(stateFile,JSON.stringify({messages,nativeId}));
 }
 send({type:'response',id:c.id,command:c.type,success:true,data});
 if(c.type==='prompt') {send({type:'agent_start'});send({type:'message_start',message:{role:'assistant'}});send({type:'message_update',assistantMessageEvent:{type:'text_delta',delta:last}});send({type:'message_end',message:messages.at(-1)});send({type:'agent_settled'})}
}
`

test('HTTP delivery, SSE, follow-up history, browser isolation and restart', { timeout: 60000 }, async t => {
  const temp = mkdtempSync(join(tmpdir(), 'plaza-delivery-api-'))
  t.after(() => rmSync(temp, { recursive: true, force: true }))
  const stateDir = join(temp, 'admin')
  const account = execFileSync(process.execPath, [join(serverDir, 'scripts/adminAccount.ts')], {
    env: { ...process.env, ADMIN_STATE_DIR: stateDir }, encoding:'utf8',
  })
  const password = /初始密码：(.+)/.exec(account)[1]
  let cookie
  const adminRequest = (path, options = {}) => fetch(base + '/api/admin/' + path, {
    ...options, headers: { Cookie:cookie, 'Content-Type':'application/json', 'X-Plaza-Admin':'1' },
  })
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
      cwd: dirname(serverDir), env: { ...process.env, ADMIN_STATE_DIR:stateDir, PORT: String(port), PI_MODEL: 'deepseek/deepseek-v4-pro', PI_CLI: cli, PI_SANDBOX_USER: '', PI_IDLE_MS: '1000', DELIVERY_PUBLIC_BASE_URL: base, DELIVERIES_DIR: store, TRACES_DIR: join(temp, 'traces') },
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
  const login = await fetch(base + '/api/admin/login', {method:'POST', headers:{ 'Content-Type':'application/json','X-Plaza-Admin':'1' },
    body:JSON.stringify({username:'admin', password})})
  assert.equal(login.status,200)
  cookie = login.headers.get('set-cookie').split(';')[0]
  await t.test('a pending industry decision hides even a fresh delivery and malformed control text in both streams',async t=>{
    for (const protocol of ['plaza','openai']) {
      const sessionId='decision-stream-'+randomBytes(10).toString('hex')
      t.after(()=>rmSync(join(serverDir,'workspace',sessionId),{recursive:true,force:true}))
      const res=await fetch(base+(protocol==='plaza'?'/api/chat':'/v1/chat/completions'),{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({skill:'industry-education-report',sessionId,interactive:protocol==='plaza',stream:true,
          messages:[{role:'user',content:'请生成产教简报 broken-evidence-menu-fixture'}]}),
      })
      assert.equal(res.status,200)
      const raw=await res.text()
      assert.doesNotMatch(raw,/plaza-question|交付失败|测试交付包/)
      assert.ok(existsSync(join(serverDir,'workspace',sessionId,'delivery.json')), 'fixture must actually write a fresh manifest')
      const prompts=JSON.parse(readFileSync(join(serverDir,'workspace',sessionId,'.pi-sessions','fixture.json'),'utf8')).messages
      assert.equal(prompts.filter(m=>m.role==='user').length,1,'a wait must not trigger a build retry')
      const frames=raw.split('\n').filter(s=>s.startsWith('data: {')).map(s=>JSON.parse(s.slice(6)))
      assert(!frames.some(f=>f.downloads?.length || f.webLinks?.length))
      if(protocol==='plaza'){
        const done=frames.findLast(f=>f.type==='done')
        assert.deepEqual(done.question.options.map(o=>o.label),['补充材料','扩大范围','按现有证据继续'])
        assert.equal(frames.filter(f=>f.type==='text').map(f=>f.delta).join(''),done.content)
      }else{
        const text=frames.map(f=>f.choices?.[0]?.delta?.content??'').join('')
        for(const label of ['补充材料','扩大范围','按现有证据继续']) assert.equal(text.split(label).length,2)
      }
    }
  })
  await t.test('an unbuilt industry report gets one retry; a plain explanation gets none',async t=>{
    for(const generate of [true,false]){
      const sessionId='decision-retry-'+randomBytes(10).toString('hex')
      const workspace=join(serverDir,'workspace',sessionId)
      t.after(()=>rmSync(workspace,{recursive:true,force:true}))
      const content=generate ? '生成产教决策报告 empty-industry-fixture' : '解释状态“已完成报告”的含义 empty-industry-fixture'
      const response=await fetch(base+'/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({skill:'industry-education-report',sessionId,messages:[{role:'user',content}]})})
      const frames=(await response.text()).split('\n').filter(l=>l.startsWith('data: {')).map(l=>JSON.parse(l.slice(6)))
      const final=frames.findLast(f=>f.type==='done')
      const prompts=JSON.parse(readFileSync(join(workspace,'.pi-sessions','fixture.json'),'utf8')).messages.filter(m=>m.role==='user')
      assert.equal(prompts.length,generate ? 2 : 1)
      assert(!final.downloads?.length)
      if(generate){
        assert.match(prompts[1].content[0].text,/^\[plaza:report-continue:/)
        assert.equal(final.resultType,'error')
        assert.match(final.content,/未产生可下载/)
        assert.doesNotMatch(frames.filter(f=>f.type==='text').map(f=>f.delta).join(''),/已完成报告/)
      }else assert.equal(final.resultType,'success')
    }
  })
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
    detail = await adminRequest('runs/' + followUp.runId).then(r => r.json())
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
    const runs = await adminRequest('runs').then(r => r.json())
    const resumed = runs.runs.find(run => run.userMessage === 'follow-up after restart')
    if (!resumed) { await pause(20); continue }
    detail = await adminRequest('runs/' + resumed.runId).then(r => r.json())
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
    const runs = await adminRequest('runs').then(r => r.json())
    const reset = runs.runs.find(run => run.userMessage === 'follow-up with reset engine')
    if (!reset) { await pause(20); continue }
    detail = await adminRequest('runs/' + reset.runId).then(r => r.json())
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
  await t.test('industry report can cite earlier user messages in a stateless OpenAI request and after recovery', async t => {
    const source = '排课表第3行：下学期全部课时已经占用。'
    const firstRequest = 'follow-up 请根据这份排课表判断能否增班。'
    const post = async (messages, extra = {}) => {
      const res = await fetch(base + '/v1/chat/completions', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill: 'industry-education-report', messages, ...extra }),
      })
      assert.equal(res.status, 200)
      const runId = (await res.json()).id.replace(/^chatcmpl-/, '')
      for (let i = 0; i < 100; i++) {
        const detail = await adminRequest('runs/' + runId).then(r => r.json())
        if (detail.item) return detail.item
        await pause(20)
      }
      assert.fail('industry report run not saved: ' + runId)
    }
    const first = await post([
      { role: 'system', content: '系统指令，不是材料' },
      { role: 'user', content: source }, { role: 'assistant', content: '假设可以开班。' },
      { role: 'user', content: source }, { role: 'user', content: firstRequest },
    ])
    const sid = first.clientSessionId
    const workspace = join(serverDir, 'workspace', sid)
    t.after(() => rmSync(workspace, { recursive: true, force: true }))
    const context = () => JSON.parse(readFileSync(join(workspace, 'industry-report-input.json'), 'utf8'))
    assert.deepEqual(first.industryUserSources, [source])
    assert.deepEqual(context().earlierMessages, [source])
    assert.equal(context().message, firstRequest)

    await stop(); await start()
    const upload = await fetch(base + '/api/upload', { method: 'POST', body: JSON.stringify({
      sessionId: sid, filename: '访谈.txt', dataText: '附件原文不能混入聊天引文。',
    }) }).then(r => r.json())
    const secondRequest = 'follow-up 再核对附件。'
    const second = await post([{ role: 'user', content: secondRequest }], { sessionId: sid, attachments: [upload] })
    assert.equal(second.industryUserSources, undefined)
    assert.deepEqual(context().earlierMessages, [source, firstRequest])
    assert.deepEqual(context().uploads, [upload.path])
    assert.equal(context().message, secondRequest)

    const third = await post([{ role: 'user', content: source }, { role: 'user', content: 'follow-up 修改标题。' }], { sessionId: sid })
    assert.equal(third.industryUserSources, undefined)
    assert.deepEqual(context().earlierMessages, [source, firstRequest, secondRequest])
    assert.deepEqual(context().uploads, [upload.path])
  })
  await t.test('a report may request a decision; the original session accepts one answer after restart', async t => {
    const sessionId = 'sess-' + randomBytes(16).toString('hex')
    t.after(() => rmSync(join(serverDir, 'workspace', sessionId), { recursive: true, force: true }))
    const post = (content, extra = {}) => fetch(base + '/api/chat', {
      method: 'POST', body: JSON.stringify({ sessionId, skill: 'career-guidance', interactive: true,
        requestId: randomBytes(16).toString('hex'), messages: [{ role: 'user', content }], ...extra }),
    })
    const body = await (await post('follow-up ask-fixture-single')).text()
    assert.doesNotMatch(body, /plaza-question|报告未生成/)
    const frames = body.split('\n').filter(line => line.startsWith('data: {')).map(line => JSON.parse(line.slice(6)))
    const done = frames.at(-1)
    assert.equal(done.content, '已核对样本。')
    assert.equal(done.question.kind, 'single')
    await stop(); await start()
    const history = await adminRequest('runs/' + done.runId).then(r => r.json())
    assert.equal(history.item.outcome, 'success')
    assert.deepEqual(history.conversation.at(-1).question, done.question)
    assert.equal(history.conversation.at(-1).text, done.content)
    assert.equal((await post('宽口径', { sessionId: sessionId + '-wrong', answerTo: done.runId })).status, 409)
    const submissions = await Promise.all([post('宽口径', { answerTo: done.runId }), post('另一个口径', { answerTo: done.runId })])
    assert.deepEqual(submissions.map(r => r.status).sort(), [200, 409])
    const reply = await submissions.find(r => r.ok).text()
    const answeredId = JSON.parse(reply.split('\n').find(line => line.includes('"type":"done"')).slice(6)).runId
    let answered
    for (let i = 0; i < 100; i++) {
      answered = await adminRequest('runs/' + answeredId).then(r => r.json())
      if (answered.conversation) break
      await pause(20)
    }
    assert.equal(answered.conversation.at(-2).answerTo, done.runId)
    assert.equal(answered.conversation.at(-2).text, answered.item.userMessage)
    assert.equal((await post('迟到的回复', { answerTo: done.runId })).status, 409)
    assert.equal((await post('普通回答不可作为提问', { answerTo: answeredId })).status, 409)
  })
  await t.test('refresh before receipt or during a turn, then resume once with original attachments', async t => {
    const id = () => randomBytes(16).toString('hex')
    const sessionId = 'sess-' + id()
    const workspace = join(serverDir, 'workspace', sessionId)
    t.after(() => rmSync(workspace, { recursive: true, force: true }))
    const interrupt = requestId => adminRequest('runs/session/' + sessionId + '/interrupt/' + requestId, { method: 'POST' }).then(r => r.json())
    const submit = (requestId, text, extra) => fetch(base + '/api/chat', {
      method: 'POST', body: JSON.stringify({ requestId, sessionId, skill: 'general', model: 'youcai', messages: [{ role: 'user', content: text }], ...extra }),
    })

    const before = id()
    const missing = await interrupt(before)
    assert.equal(missing.state, 'missing')
    assert.equal((await interrupt(before)).retryId, missing.retryId)
    assert.equal((await submit(before, 'late request')).status, 409)

    const upload = await fetch(base + '/api/upload', { method: 'POST', body: JSON.stringify({
      filename: 'input.txt', dataText: '附件内容证据', sessionId,
    }) }).then(r => r.json())
    const first = await submit(missing.retryId, 'follow-up hold-for-refresh', { attachments: [upload] })
    for (let i = 0; i < 100 && !existsSync(join(workspace, 'checkpoint.txt')); i++) await pause(20)
    assert(existsSync(join(workspace, 'checkpoint.txt')))
    const management = base + '/api/conversations/session/' + sessionId
    assert.equal((await fetch(management + '/archive', {method:'POST'})).status,409)
    assert.equal((await fetch(management, {method:'DELETE'})).status,409)
    assert.equal((await interrupt(before)).state, 'missing', 'stale pagehide cannot stop the replacement')
    assert.equal((await submit(missing.retryId, 'duplicate')).status, 409)
    assert.equal((await interrupt(missing.retryId)).state, 'settling')
    await first.text()
    let status
    for (let i = 0; i < 100; i++) {
      status = await interrupt(missing.retryId)
      if (status.state === 'saved') break
      await pause(20)
    }
    assert.equal(status.latest.outcome, 'aborted')
    const resumeOf = status.latest.runId
    const next = id()
    const resumed = await submit(next, '继续任务', { resumeOf })
    assert.match(await resumed.text(), /"type":"done"/)
    for (let i = 0; i < 100; i++) {
      status = await interrupt(next)
      if (status.state === 'saved') break
      await pause(20)
    }
    assert.equal(status.latest.outcome, 'success')
    assert.equal(status.latest.resumeSourceId, resumeOf)
    assert.equal(status.latest.tokenUsage.provider, 'youcai')
    assert.equal((await submit(id(), '继续任务', { resumeOf })).status, 409)
    const detail = await adminRequest('runs/' + status.latest.runId).then(r => r.json())
    const input = detail.trace.messages.filter(m => m.role === 'user').at(-1).parts[0].text
    assert.match(input, /原始任务：\nfollow-up hold-for-refresh/)
    assert.match(input, /附件内容证据/)
    assert.equal(detail.conversation.filter(m => m.role === 'user').at(-1).text, '继续任务')
  })

  await t.test('refresh after acceptance but before Pi starts restores the original first prompt', async t => {
    const sessionId = 'sess-' + randomBytes(16).toString('hex') + '-early'
    t.after(() => rmSync(join(serverDir, 'workspace', sessionId), { recursive: true, force: true }))
    const requestId = randomBytes(16).toString('hex')
    const request = (id, text, resumeOf) => fetch(base + '/api/chat', { method: 'POST', body: JSON.stringify({
      sessionId, requestId: id, resumeOf, skill: 'general', messages: [{ role: 'user', content: text }],
    }) })
    const interrupt = () => adminRequest('runs/session/' + sessionId + '/interrupt/' + requestId, { method: 'POST' }).then(r => r.json())
    const first = await request(requestId, 'follow-up before Pi')
    assert.equal((await interrupt()).state, 'settling')
    await first.text()
    const { latest } = await interrupt()
    assert.equal(latest.promptNotSent, true)
    assert.equal(latest.outcome, 'aborted')
    const detail = await adminRequest('runs/' + latest.runId).then(r => r.json())
    assert.deepEqual(detail.conversation.map(t => t.text), ['follow-up before Pi'])
    const resumed = await request(randomBytes(16).toString('hex'), '继续任务', latest.runId)
    assert.match(await resumed.text(), /"type":"done"/)
    let restored
    for (let i = 0; i < 100; i++) {
      const state = await interrupt()
      if (state.latest.runId !== latest.runId) {
        restored = await adminRequest('runs/' + state.latest.runId).then(r => r.json())
        break
      }
      await pause(20)
    }
    assert.deepEqual(restored.conversation.map(t => t.text), ['follow-up before Pi', '继续任务', '完成'])
    assert.match(restored.trace.messages[0].parts[0].text, /原始任务：\nfollow-up before Pi/)
  })

  await t.test('administration, catalog enforcement and shared conversations', async t => {
    const read = async path => (await adminRequest(path)).json()
    let {config} = await read('state')
    const save = async (section, fields) => {
      const res = await adminRequest(section, {method:'PUT', body:JSON.stringify({revision:config.revision, ...fields})})
      assert.equal(res.status,200)
      return config = await res.json()
    }
    assert.equal((await fetch(base + '/api/admin/runs')).status,401)
    assert.equal((await fetch(base + '/api/runs')).status,401)
    const legacy = await fetch(base + '/api/conversations').then(r => r.json())
    assert(legacy.total > 0)
    assert(legacy.runs.every(r => r.clientSessionId))
    assert.equal((await fetch(base + '/api/conversations/session/non-existent', {method:'DELETE'})).status,404)
    assert.equal((await fetch(base + '/api/admin/settings',{method:'PUT',headers:{Cookie:cookie}})).status,403)
    const id = 'career-guidance'
    await save('skills',{id,enabled:false})
    assert.equal((await fetch(base + '/api/skills').then(r=>r.json())).skills.some(s=>s.id===id),false)
    const chat = (path, body, key) => fetch(base + path,{method:'POST',headers:key?{'X-Plaza-Browser':key}:{},body:JSON.stringify(body)})
    for (const path of ['/api/chat','/v1/chat/completions']) {
      assert.equal((await chat(path,{skill:id,messages:[{role:'user',content:'disabled'}]})).status,400)
    }
    const initial = config.settings
    await save('settings',{settings:{...initial, defaultModel:'youcai',allowModelChoice:false}})
    const health = await fetch(base + '/api/health').then(r=>r.json())
    assert.deepEqual(health.chatModels.map(m=>m.id),['youcai'])
    assert.equal((await chat('/api/chat',{skill:'general',model:'deepseek-flash',messages:[{role:'user',content:'blocked'}]})).status,400)
    const secret=randomBytes(32).toString('hex')
    await save('keys',{action:'add',name:'test profile',secret})
    assert(!JSON.stringify(config).includes(secret))
    await save('keys',{action:'activate',id:config.keys[0].id})
    await stop(); await start()
    config=(await read('state')).config
    assert.equal(config.activeKey,config.keys[0].id)
    assert(config.disabledSkills.includes(id))
    await save('keys',{action:'activate',id:'environment'})
    await save('keys',{action:'delete',id:config.keys[0].id})
    await save('skills',{id,enabled:true})
    const a=randomBytes(32).toString('hex'), b=randomBytes(32).toString('hex')
    const sharedSkill = 'ai-interview'
    const catalog = await fetch(base + '/api/skills').then(r => r.json())
    assert.equal(catalog.skills.find(skill => skill.id === sharedSkill)?.installed, true)
    const run = async (key, text, options = {}) => {
      const response = await chat('/api/chat', {skill:sharedSkill, interactive:true, requestId:randomBytes(16).toString('hex'),
        messages:[{role:'user',content:text}], ...options}, key)
      assert.equal(response.status,200)
      const frames=(await response.text()).split('\n').filter(l=>l.startsWith('data: {')).map(l=>JSON.parse(l.slice(6)))
      const done = frames.find(f=>f.type==='done')
      assert.equal(done?.resultType,'success')
      const path = 'runs/'+done.runId
      for (let i=0;i<80 && (await adminRequest(path)).status===404;i++) await pause(25)
      return {detail:await read(path), done}
    }
    const history=(path,key,method='GET')=>fetch(base+'/api/conversations'+path,{method,headers:key?{'X-Plaza-Browser':key}:{}})
    const first=await run(a,'follow-up ask-fixture-single')
    assert.match(first.detail.trace.messages.find(m => m.role === 'user').parts[0].text, /^\/skill:ai-interview /)
    const sid=first.detail.item.clientSessionId, runId=first.done.runId
    assert.match(sid,/^web-/)
    t.after(()=>rmSync(join(serverDir,'workspace',sid),{recursive:true,force:true}))
    const list = await history('',b).then(r=>r.json())
    assert.equal(list.runs.find(r=>r.runId===runId).clientSessionId,sid)
    const detail = await history('/'+runId,b).then(r=>r.json())
    assert.equal(detail.item.clientSessionId,sid)
    assert.equal(detail.trace,undefined)
    assert(detail.conversation.some(m=>m.question))
    assert(detail.conversation.every(m=>!m.execution && !m.tools))
    assert.equal((await history('/'+runId+'/file/trace')).status,404)
    assert.equal((await adminRequest('runs/'+runId+'/file/trace')).status,200)
    const upload = await chat('/api/upload',{sessionId:sid, filename:'shared.txt', dataText:'shared-upload'},b).then(r=>r.json())
    assert.equal(upload.sessionId,sid)
    assert.equal((await history('/session/'+sid+'/archive',b,'POST')).status,200)
    const second=await run(b,'follow-up cross-browser',{sessionId:sid, answerTo:runId, attachments:[upload]})
    assert.equal(second.detail.item.clientSessionId,sid)
    assert.equal(second.detail.item.engineSessionId,first.detail.item.engineSessionId)
    assert.equal(second.detail.item.archived,true)
    assert(second.detail.conversation.some(m=>m.answerTo===runId))
    assert.equal((await chat('/api/chat',{sessionId:sid,skill:sharedSkill,requestId:randomBytes(16).toString('hex'),answerTo:runId,messages:[{role:'user',content:'duplicate'}]},a)).status,409)
    assert.equal((await history('/session/'+sid+'/unarchive',undefined,'POST')).status,200)
    const viaApi=await chat('/v1/chat/completions',{skill:sharedSkill,sessionId:sid,messages:[{role:'user',content:'follow-up via API'}]})
    assert.equal(viaApi.status,200)
    assert.equal((await viaApi.json()).choices[0].message.content,'完成')
    let apiRun
    for(let i=0;i<80 && !apiRun;i++) {
      apiRun=(await read('runs')).runs.find(r=>r.clientSessionId===sid && r.userMessage==='follow-up via API')
      if (!apiRun) await pause(25)
    }
    assert.equal(apiRun?.engineSessionId,first.detail.item.engineSessionId)
    assert.equal((await history('/session/'+sid,b,'DELETE')).status,200)
    assert.equal((await history('/'+runId,a)).status,404)

    // An old run without a client ID or native Pi workspace still continues under its original history key.
    const oldId='legacy-'+randomBytes(12).toString('hex')
    const legacyRecord={runId:oldId,ts:'2026-01-01T00:00:00.000Z',skill:sharedSkill,userMessage:'legacy-first',promptDigest:'legacy-first',
      outcome:'success',localReply:'legacy-answer',promptNotSent:true,files:{}}
    appendFileSync(join(temp,'traces/index.jsonl'),JSON.stringify(legacyRecord)+'\n')
    t.after(()=>rmSync(join(serverDir,'workspace',oldId),{recursive:true,force:true}))
    const old=await history('/'+oldId,b).then(r=>r.json())
    assert.equal(old.item.clientSessionId,oldId)
    const continued=await run(b,'follow-up legacy',{sessionId:old.item.clientSessionId})
    assert.equal(continued.detail.item.clientSessionId,oldId)
    assert.match(continued.detail.trace.messages[0].parts[0].text,/用户：legacy-first[\s\S]*助手：legacy-answer/)
    assert.deepEqual(continued.detail.conversation.filter(m=>m.role==='user').map(m=>m.text),['legacy-first','follow-up legacy'])
    await save('settings',{settings:initial})
    const rotated = await adminRequest('password',{method:'POST',body:JSON.stringify({currentPassword:password,password:randomBytes(18).toString('hex')})})
    assert.equal(rotated.status,200)
    assert.equal((await adminRequest('state')).status,401)
  })

})
